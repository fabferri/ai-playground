# Deploy MCP Server ARM template to Azure
#
# DESCRIPTION
#    This script deploys the main.json ARM template with parameters.json to create
#    the complete MCP server infrastructure including:
#    - Virtual Network with ACA and Private Endpoint subnets
#    - Azure Container Apps Environment with MCP server and client apps
#    - User-Assigned Managed Identity
#    - Azure AI Foundry account with VNet integration
#    - Private Endpoints and DNS zones
$armTemplateFile = 'main.json' 
$armTemplateParametersFile = 'parameters.json'
$inputvarFile = 'init.json'

$pathFiles = Split-Path -Parent $PSCommandPath
$templateFile = "$pathFiles\$armTemplateFile"
$parametersFile = "$pathFiles\$armTemplateParametersFile"
$inputvarFile = "$pathFiles\$inputvarFile"

# Collect subscription Name, Resource Group and location from the init.json file
try {
    $arrayParams = (Get-Content -Raw $inputvarFile | ConvertFrom-Json)
    $subscriptionName = $arrayParams.subscriptionName
    $rgName = $arrayParams.resourceGroupName
    $location = $arrayParams.location
    Write-Host "$(Get-Date) - values from file: "$inputvarFile -ForegroundColor Yellow
    if (!$subscriptionName) { Write-Host 'variable $subscriptionName is null' ; Exit }   else { Write-Host '   subscriptionName......: '$subscriptionName -ForegroundColor Yellow }
    if (!$rgName) { Write-Host 'variable $rgName is null' ; Exit }                       else { Write-Host '   resourceGroupName.....: '$rgName -ForegroundColor Yellow }
    if (!$location) { Write-Host 'variable $location is null' ; Exit }                   else { Write-Host '   location..............: '$location -ForegroundColor Yellow }
 
} 
catch {
    Write-Host 'error in reading the template file: '$inputvarFile -ForegroundColor Yellow
    Exit
}


# Set error action preference
$ErrorActionPreference = 'Stop'

# Helper function to write colored output
function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = "White"
    )
    Write-Host $Message -ForegroundColor $Color
}
function Get-DeploymentProvisioningState {
    param(
        [object]$DeploymentResult
    )

    if (-not $DeploymentResult) {
        return "Unknown"
    }

    $topLevelState = $DeploymentResult.PSObject.Properties['ProvisioningState']
    if ($topLevelState -and $topLevelState.Value) {
        return [string]$topLevelState.Value
    }

    if ($DeploymentResult.properties -and $DeploymentResult.properties.provisioningState) {
        return [string]$DeploymentResult.properties.provisioningState
    }

    return "Unknown"
}

function Get-ValidationParameterValue {
    param(
        [object]$ValidationResult,
        [string]$Name
    )

    if (-not $ValidationResult -or -not $ValidationResult.properties -or -not $ValidationResult.properties.parameters) {
        return $null
    }

    $paramEntry = $ValidationResult.properties.parameters.PSObject.Properties[$Name]
    if (-not $paramEntry -or -not $paramEntry.Value) {
        return $null
    }

    $valueProp = $paramEntry.Value.PSObject.Properties['value']
    if ($valueProp) {
        return $valueProp.Value
    }

    return $null
}

function Purge-DeletedKeyVaultIfNeeded {
    param(
        [string]$KeyVaultName
    )

    if ([string]::IsNullOrWhiteSpace($KeyVaultName)) {
        return
    }

    Write-ColorOutput "Checking soft-deleted state for Key Vault '$KeyVaultName'..." "Yellow"
    $deletedCount = az keyvault list-deleted --query "[?name=='$KeyVaultName'] | length(@)" --output tsv 2>$null

    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($deletedCount) -or $deletedCount -eq "0") {
        Write-ColorOutput "No soft-deleted Key Vault found for '$KeyVaultName'." "Green"
        return
    }

    Write-ColorOutput "Purging soft-deleted Key Vault '$KeyVaultName'..." "Yellow"
    az keyvault purge --name $KeyVaultName --location $location | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to purge Key Vault '$KeyVaultName'."
    }

    # Wait until purge is complete before template deployment starts.
    for ($i = 1; $i -le 20; $i++) {
        $remaining = az keyvault list-deleted --query "[?name=='$KeyVaultName'] | length(@)" --output tsv 2>$null
        if ($LASTEXITCODE -eq 0 -and ($remaining -eq "0" -or [string]::IsNullOrWhiteSpace($remaining))) {
            Write-ColorOutput "✓ Key Vault '$KeyVaultName' purged" "Green"
            return
        }
        Start-Sleep -Seconds 10
    }

    throw "Key Vault '$KeyVaultName' purge did not complete in time."
}

function Get-CognitiveServicesRestoreMode {
    param(
        [string]$AccountName,
        [string]$ResourceGroup,
        [string]$Location
    )

    $deletedJson = az cognitiveservices account list-deleted `
        --query "[?name=='$AccountName' && location=='$Location']" `
        --output json 2>$null

    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($deletedJson)) {
        return $false
    }

    $deletedList = $deletedJson | ConvertFrom-Json
    if ($deletedList.Count -eq 0) {
        return $false
    }

    # Verify the resource ID matches the target resource group (case-insensitive)
    $targetRgPattern = "/resourceGroups/$ResourceGroup/"
    $match = $deletedList | Where-Object { $_.id -imatch [regex]::Escape($targetRgPattern) }
    if (-not $match) {
        Write-ColorOutput "Soft-deleted account '$AccountName' exists in a different resource group — skipping restore" "Yellow"
        return $false
    }

    Write-ColorOutput "Soft-deleted Cognitive Services account '$AccountName' found — will restore via ARM template (restore=true)" "Yellow"
    return $true
}

function Wait-CognitiveServicesAccountReady {
    param(
        [string]$AccountName,
        [string]$ResourceGroup,
        [int]$MaxMinutes = 20
    )

    for ($i = 1; $i -le ($MaxMinutes * 2); $i++) {
        $state = az cognitiveservices account show --name $AccountName --resource-group $ResourceGroup --query "properties.provisioningState" --output tsv 2>$null
        if ($LASTEXITCODE -eq 0 -and $state -eq 'Succeeded') {
            Write-ColorOutput "✓ Cognitive Services account '$AccountName' is in Succeeded state" "Green"
            return $true
        }

        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($state)) {
            Write-ColorOutput "Waiting for Cognitive Services account '$AccountName' provisioning state. Current: $state" "Yellow"
        }

        Start-Sleep -Seconds 30
    }

    return $false
}

function Get-ParameterFileValue {
    param(
        [string]$ParameterFilePath,
        [string]$ParameterName,
        [string]$DefaultValue = ""
    )

    if (-not (Test-Path $ParameterFilePath)) {
        return $DefaultValue
    }

    try {
        $parameterJson = Get-Content -Path $ParameterFilePath -Raw | ConvertFrom-Json
        $paramProp = $parameterJson.parameters.PSObject.Properties[$ParameterName]
        if ($paramProp -and $paramProp.Value -and $paramProp.Value.value) {
            return [string]$paramProp.Value.value
        }
    }
    catch {
        # Fall through to default when parameter file cannot be parsed.
    }

    return $DefaultValue
}

# Returns $true when the three key AI resources are all in Succeeded state,
# meaning a previous deployment already completed the infrastructure.
function Test-InfrastructureAlreadyDeployed {
    param(
        [string]$ResourceGroup,
        [string]$FoundryAccountName,
        [string]$AiHubName,
        [string]$AiProjectName
    )

    $csState = az cognitiveservices account show `
        --name $FoundryAccountName `
        --resource-group $ResourceGroup `
        --query "properties.provisioningState" `
        --output tsv 2>$null
    if ($LASTEXITCODE -ne 0 -or $csState -ne 'Succeeded') { return $false }

    $hubState = az resource show `
        --resource-group $ResourceGroup `
        --name $AiHubName `
        --resource-type "Microsoft.MachineLearningServices/workspaces" `
        --query "properties.provisioningState" `
        --output tsv 2>$null
    if ($LASTEXITCODE -ne 0 -or $hubState -ne 'Succeeded') { return $false }

    $projectState = az resource show `
        --resource-group $ResourceGroup `
        --name $AiProjectName `
        --resource-type "Microsoft.MachineLearningServices/workspaces" `
        --query "properties.provisioningState" `
        --output tsv 2>$null
    if ($LASTEXITCODE -ne 0 -or $projectState -ne 'Succeeded') { return $false }

    return $true
}


# Main script execution
try {
    Write-ColorOutput "==================================================" "Cyan"
    Write-ColorOutput "   MCP Server ARM Template Deployment Script" "Cyan"
    Write-ColorOutput "==================================================" "Cyan"
    Write-Host ""
    Write-ColorOutput "Selecting subscription: $subscriptionName" "Yellow"
    az account set --subscription $subscriptionName | Out-Null
        

    
    $timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $DeploymentName = "mcp-deployment-$timestamp"
    

    Write-Host ""
    Write-Host "Deployment Configuration:" 
    Write-Host "  Subscription:      $subscriptionName"
    Write-Host "  Resource Group:    $rgName"
    Write-Host "  Location:          $location"
    Write-Host "  Template File:     $TemplateFile"
    Write-Host "  Parameters File:   $ParametersFile"
    Write-Host ""

    # Check if resource group exists
    Write-ColorOutput "Checking if resource group '$rgName' exists..." "Yellow"
    $rgExists = az group exists --name $rgName
    
    if ($rgExists -eq "true") {
        Write-ColorOutput "✓ Resource group '$rgName' already exists" "Green"
    }
    else {
        Write-ColorOutput "Creating resource group '$rgName' in '$location'..." "Yellow"
        az group create --name $rgName --location $location | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-ColorOutput "✓ Resource group created successfully" "Green"
        }
        else {
            throw "Failed to create resource group '$rgName'"
        }
    }

    Write-Host ""

    # Validate template files exist
    if (-not (Test-Path $TemplateFile)) {
        throw "Template file not found: $TemplateFile"
    }

    if (-not (Test-Path $ParametersFile)) {
        throw "Parameters file not found: $ParametersFile"
    }

    $foundryAccountName = Get-ParameterFileValue -ParameterFilePath $ParametersFile -ParameterName 'foundryAccountName' -DefaultValue 'foundry-ai-acct'
    $aiHubNameParam     = Get-ParameterFileValue -ParameterFilePath $ParametersFile -ParameterName 'aiHubName'          -DefaultValue 'ai-hub'
    $aiProjectNameParam = Get-ParameterFileValue -ParameterFilePath $ParametersFile -ParameterName 'aiProjectName'      -DefaultValue 'ai-project'
    $modelDeploymentNameParam = Get-ParameterFileValue -ParameterFilePath $ParametersFile -ParameterName 'modelDeploymentName' -DefaultValue 'gpt-5.4'
    $keyVaultNameParam  = Get-ParameterFileValue -ParameterFilePath $ParametersFile -ParameterName 'keyVaultName'       -DefaultValue ''
    $storageNameParam   = Get-ParameterFileValue -ParameterFilePath $ParametersFile -ParameterName 'storageAccountName' -DefaultValue ''

    $restoreCognitiveServicesAccount = Get-CognitiveServicesRestoreMode `
        -AccountName $foundryAccountName `
        -ResourceGroup $rgName `
        -Location $location

    $deploymentParameterArgs = @($ParametersFile, "restoreCognitiveServicesAccount=$restoreCognitiveServicesAccount")

    Write-ColorOutput "Cognitive Services restore mode: $restoreCognitiveServicesAccount" "Yellow"

    # Validate ARM template before deployment
    Write-ColorOutput "Validating deployment template..." "Yellow"
    $validation = az deployment group validate `
        --resource-group $rgName `
        --template-file $TemplateFile `
        --parameters $deploymentParameterArgs `
        --output json 2>&1

    if ($LASTEXITCODE -ne 0) {
        throw "Template validation failed. Azure CLI output: $($validation | Out-String)"
    }

    $validationResult = $validation | ConvertFrom-Json

    $keyVaultNameForDeployment = Get-ValidationParameterValue -ValidationResult $validationResult -Name 'keyVaultName'
    Purge-DeletedKeyVaultIfNeeded -KeyVaultName $keyVaultNameForDeployment

    Write-ColorOutput "✓ Template validation passed" "Green"
    Write-Host ""

    # -----------------------------------------------------------------------
    # Pre-check: if all key resources are already Succeeded from a previous
    # deployment, bypass the ARM re-deployment to avoid the update→Accepted
    # cycle on the Cognitive Services account that blocks ML Hub/Project.
    # -----------------------------------------------------------------------
    Write-ColorOutput "Checking if infrastructure is already fully deployed..." "Yellow"
    if (Test-InfrastructureAlreadyDeployed `
            -ResourceGroup $rgName `
            -FoundryAccountName $foundryAccountName `
            -AiHubName $aiHubNameParam `
            -AiProjectName $aiProjectNameParam) {

        Write-Host ""
        Write-ColorOutput "==================================================" "Green"
        Write-ColorOutput "   Infrastructure Already Deployed ✓" "Green"
        Write-ColorOutput "==================================================" "Green"
        Write-Host ""
        Write-Host "  All key resources are in Succeeded state." -ForegroundColor Gray
        Write-Host "  Skipping ARM deployment to avoid update-cycle conflicts." -ForegroundColor Gray
        Write-Host ""

        $existingEndpoint = az cognitiveservices account show `
            --name $foundryAccountName `
            --resource-group $rgName `
            --query "properties.endpoint" `
            --output tsv 2>$null

        $acrName = az acr list `
            --resource-group $rgName `
            --query "[0].name" `
            --output tsv 2>$null

        $acrLoginServer = az acr show `
            --name $acrName `
            --resource-group $rgName `
            --query "loginServer" `
            --output tsv 2>$null

        Write-ColorOutput "Deployment Outputs (from existing resources):" "Yellow"
        Write-Host ""
        if ($existingEndpoint) {
            Write-Host "  Foundry Endpoint:      " -NoNewline; Write-ColorOutput $existingEndpoint "Cyan"
        }
        if ($acrLoginServer) {
            Write-Host "  Registry Server:       " -NoNewline; Write-ColorOutput $acrLoginServer "Cyan"
        }
        Write-Host "  AI Hub Name:           " -NoNewline; Write-ColorOutput $aiHubNameParam "Cyan"
        Write-Host "  AI Project Name:       " -NoNewline; Write-ColorOutput $aiProjectNameParam "Cyan"
        Write-Host "  Model Deployment:      " -NoNewline; Write-ColorOutput $modelDeploymentNameParam "Cyan"
        if ($keyVaultNameParam) {
            Write-Host "  Key Vault Name:        " -NoNewline; Write-ColorOutput $keyVaultNameParam "Cyan"
        }
        if ($storageNameParam) {
            Write-Host "  Storage Account Name:  " -NoNewline; Write-ColorOutput $storageNameParam "Cyan"
        }

        Write-Host ""
        Write-ColorOutput "Next Steps:" "Yellow"
        Write-Host ""
        Write-Host "  Use 'az deployment group list -g $rgName' to inspect prior deployments." -ForegroundColor Gray
        Write-Host ""
        return
    }

    Write-ColorOutput "Infrastructure not yet fully deployed — proceeding with ARM deployment." "Yellow"
    Write-Host ""

    # Deploy ARM template
    Write-ColorOutput "Starting deployment..." "Yellow"
    Write-Host ""

    $deploymentStartTime = Get-Date

    # Deploy using Azure CLI (retry on transient Azure-side errors)
    $deployment = $null
    $maxAttempts = 6
    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        # Use a fresh deployment name every attempt so ARM does not conflict with the
        # prior failed deployment entry.
        $AttemptDeploymentName = "$DeploymentName-a$attempt"

        if ($attempt -gt 1) {
            Write-ColorOutput "Retrying deployment (attempt $attempt of $maxAttempts, name: $AttemptDeploymentName)..." "Yellow"
        }

        $deployment = az deployment group create `
            --resource-group $rgName `
            --name $AttemptDeploymentName `
            --template-file $TemplateFile `
            --parameters $deploymentParameterArgs `
            --output json 2>&1

        if ($LASTEXITCODE -eq 0) {
            $DeploymentName = $AttemptDeploymentName
            break
        }

        $deploymentErrorText = ($deployment | Out-String)

        $isTransient = $deploymentErrorText -match 'AccountProvisioningStateInvalid' `
            -or $deploymentErrorText -match 'in state Accepted' `
            -or $deploymentErrorText -match 'internal server error' `
            -or $deploymentErrorText -match 'ResourceDeploymentFailure'

        if ($isTransient -and $attempt -lt $maxAttempts) {
            Write-ColorOutput "Transient Azure error detected. Checking Cognitive Services state..." "Yellow"
            $ready = Wait-CognitiveServicesAccountReady -AccountName $foundryAccountName -ResourceGroup $rgName -MaxMinutes 5
            if (-not $ready) {
                Write-ColorOutput "Waiting 60 seconds before retry..." "Yellow"
                Start-Sleep -Seconds 60
            }
            continue
        }

        throw "Deployment failed after $attempt attempt(s). Azure CLI output: $deploymentErrorText"
    }

    if ($LASTEXITCODE -ne 0) {
        throw "Deployment failed after $maxAttempts attempts."
    }

    $deploymentResult = $deployment | ConvertFrom-Json
    $deploymentEndTime = Get-Date
    $deploymentDuration = $deploymentEndTime - $deploymentStartTime

    Write-Host ""
    Write-ColorOutput "==================================================" "Green"
    Write-ColorOutput "   Deployment Completed Successfully! ✓" "Green"
    Write-ColorOutput "==================================================" "Green"
    Write-Host ""
    Write-Host "  Duration:         $($deploymentDuration.ToString('mm\:ss'))" -ForegroundColor Gray
    Write-Host "  Deployment Name:  $DeploymentName" -ForegroundColor Gray
    Write-Host ""

    $provisioningState = Get-DeploymentProvisioningState -DeploymentResult $deploymentResult

    # Extract and display outputs
    Write-ColorOutput "Deployment Outputs:" "Yellow"
    Write-Host ""
    $outputs = if ($deploymentResult.PSObject.Properties['Outputs']) {
        $deploymentResult.Outputs
    }
    elseif ($deploymentResult.properties -and $deploymentResult.properties.outputs) {
        $deploymentResult.properties.outputs
    }
    else {
        $null
    }

    if (-not $outputs) {
        Write-ColorOutput "No deployment outputs found. Deployment may have failed or returned no outputs." "Yellow"
    }

    $foundryAccountEndpoint = $outputs['foundryAccountEndpoint'].Value
    $effectiveRegistryServer = $outputs['effectiveRegistryServer'].Value
    $aiHubName = $outputs['aiHubName'].Value
    $aiProjectName = $outputs['aiProjectName'].Value
    $keyVaultName = $outputs['keyVaultName'].Value
    $storageAccountName = $outputs['storageAccountName'].Value
    $modelDeploymentName = $outputs['modelDeploymentName'].Value
        
    if ($foundryAccountEndpoint) {
        Write-Host "  Foundry Endpoint:      " -NoNewline
        Write-ColorOutput $foundryAccountEndpoint "Cyan"
    }
    if ($effectiveRegistryServer) {
        Write-Host "  Registry Server:       " -NoNewline
        Write-ColorOutput $effectiveRegistryServer "Cyan"
    }
    if ($aiHubName) {
        Write-Host "  AI Hub Name:           " -NoNewline
        Write-ColorOutput $aiHubName "Cyan"
    }
    if ($aiProjectName) {
        Write-Host "  AI Project Name:       " -NoNewline
        Write-ColorOutput $aiProjectName "Cyan"
    }
    if ($modelDeploymentName) {
        Write-Host "  Model Deployment:      " -NoNewline
        Write-ColorOutput $modelDeploymentName "Cyan"
    }
    if ($keyVaultName) {
        Write-Host "  Key Vault Name:        " -NoNewline
        Write-ColorOutput $keyVaultName "Cyan"
    }
    if ($storageAccountName) {
        Write-Host "  Storage Account Name:  " -NoNewline
        Write-ColorOutput $storageAccountName "Cyan"
    }
    

    Write-Host ""
    Write-ColorOutput "Next Steps:" "Yellow"
    Write-Host ""
    Write-Host "  1. Populate .env file with deployment outputs:" -ForegroundColor Gray
    Write-Host "     python populate_env.py -g $rgName -d $DeploymentName" -ForegroundColor White
    Write-Host ""
    Write-Host "  2. Verify deployment outputs:" -ForegroundColor Gray
    if ($provisioningState -ne 'Succeeded') {
        Write-ColorOutput "     Deployment state is '$provisioningState'." "Yellow"
    }
    elseif ($foundryAccountEndpoint) {
        Write-Host "     Foundry endpoint: $foundryAccountEndpoint" -ForegroundColor White
    }
    Write-Host ""
    Write-Host "  3. Inspect deployment in Azure CLI:" -ForegroundColor Gray
    if ($provisioningState -eq 'Succeeded') {
        Write-Host "     az deployment group show -g $rgName -n $DeploymentName --query properties.outputs" -ForegroundColor White
    }
    Write-Host ""

    Write-ColorOutput "Deployment logs can be viewed with:" "Gray"
    Write-Host "  az deployment group show -g $rgName -n $DeploymentName" -ForegroundColor White
    Write-Host ""

}
catch {
    Write-Host ""
    Write-ColorOutput "==================================================" "Red"
    Write-ColorOutput "   Deployment Failed! ✗" "Red"
    Write-ColorOutput "==================================================" "Red"
    Write-Host ""
    Write-ColorOutput "Error: $($_.Exception.Message)" "Red"
    Write-Host ""
    exit 1
}
