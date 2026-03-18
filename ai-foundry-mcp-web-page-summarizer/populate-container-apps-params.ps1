<#
SYNOPSIS
    Populates container-apps.parameters.json from infrastructure deployment outputs.

DESCRIPTION
    This script queries Azure deployment outputs to resolve values required by
    container-apps.parameters.json, including:
    - acaSubnetId
    - registryServer
    - registryResourceId
    - foundryAccountName
    - modelDeploymentName

    It also sets server/client image tags and internalEnvironment flag.

USAGE
    ./populate-container-apps-params.ps1 -SubscriptionName <subscription> -ResourceGroupName <rg>
#>



param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionName,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $false)]
    [string]$ParametersFile = ".\container-apps.parameters.json",

    [Parameter(Mandatory = $false)]
    [string]$ServerImage = 'mcp-server:latest',

    [Parameter(Mandatory = $false)]
    [string]$ClientImage = 'mcp-client:latest',

    [Parameter(Mandatory = $false)]
    [string]$UamiName = 'mcp-uami',

    [Parameter(Mandatory = $false)]
    [bool]$InternalEnvironment = $true
)


$ErrorActionPreference = 'Stop'

function Write-ColorOutput {
    param(
        [string]$Message,
        [string]$Color = 'White'
    )

    Write-Host $Message -ForegroundColor $Color
}

function Get-OutputValue {
    param(
        [object]$Outputs,
        [string]$Name
    )

    if (-not $Outputs) {
        return $null
    }

    $entry = $null

    if ($Outputs -is [System.Collections.IDictionary]) {
        if (-not $Outputs.Contains($Name)) {
            return $null
        }
        $entry = $Outputs[$Name]
    }
    else {
        $prop = $Outputs.PSObject.Properties[$Name]
        if (-not $prop) {
            return $null
        }
        $entry = $prop.Value
    }

    if ($null -eq $entry) {
        return $null
    }

    if ($entry -is [string]) {
        return $entry
    }

    $valueProp = $entry.PSObject.Properties['value']
    if ($valueProp) {
        return $valueProp.Value
    }

    $valueProp = $entry.PSObject.Properties['Value']
    if ($valueProp) {
        return $valueProp.Value
    }

    return $entry
}

function Resolve-AcaSubnetId {
    param(
        [string]$Rg
    )

    $defaultVnetName = 'aca-vnet'
    $defaultSubnetName = 'aca-subnet'

    $defaultSubnetId = az network vnet subnet show `
        --resource-group $Rg `
        --vnet-name $defaultVnetName `
        --name $defaultSubnetName `
        --query id `
        --output tsv 2>$null

    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($defaultSubnetId)) {
        return [string]$defaultSubnetId
    }

    $vnetsRaw = az network vnet list --resource-group $Rg --output json
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list virtual networks in resource group '$Rg'."
    }

    $vnets = $vnetsRaw | ConvertFrom-Json
    foreach ($vnet in @($vnets)) {
        $subnetId = az network vnet subnet list `
            --resource-group $Rg `
            --vnet-name $vnet.name `
            --query "[?delegations[?serviceName=='Microsoft.App/environments']].id | [0]" `
            --output tsv

        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($subnetId)) {
            return [string]$subnetId
        }
    }

    return ''
}

function Ensure-AcrPullRoleAssignment {
    param(
        [string]$Rg,
        [string]$IdentityName,
        [string]$RegistryResourceId
    )

    $principalId = az identity show --resource-group $Rg --name $IdentityName --query principalId --output tsv
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($principalId)) {
        throw "Failed to resolve principalId for user-assigned identity '$IdentityName' in resource group '$Rg'."
    }

    $existingAssignment = az role assignment list `
        --assignee-object-id $principalId `
        --scope $RegistryResourceId `
        --query "[?roleDefinitionName=='AcrPull'].id | [0]" `
        --output tsv

    if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($existingAssignment)) {
        Write-Host "Verified AcrPull role on registry for identity '$IdentityName'." -ForegroundColor Gray
        return
    }

    Write-ColorOutput "Assigning AcrPull to '$IdentityName' on registry scope..." 'Yellow'
    az role assignment create `
        --assignee-object-id $principalId `
        --assignee-principal-type ServicePrincipal `
        --role AcrPull `
        --scope $RegistryResourceId `
        --output none

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to assign AcrPull role to '$IdentityName' on registry '$RegistryResourceId'."
    }

    Write-Host "Assigned AcrPull role to identity '$IdentityName'." -ForegroundColor Gray
}

try {
    Write-ColorOutput '==================================================' 'Cyan'
    Write-ColorOutput ' Populate container-apps.parameters.json script' 'Cyan'
    Write-ColorOutput '==================================================' 'Cyan'
    Write-Host ''

    $scriptDir = Split-Path -Parent $PSCommandPath
    $parametersPath = Join-Path $scriptDir $ParametersFile

    if (-not (Test-Path $parametersPath)) {
        throw "Parameters file not found: $parametersPath"
    }

    if ($SubscriptionName) {
        Write-ColorOutput "Selecting subscription: $SubscriptionName" 'Yellow'
        az account set --subscription $SubscriptionName | Out-Null
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to select subscription '$SubscriptionName'."
        }
    }

    Write-ColorOutput "Checking Azure login context..." 'Yellow'
    az account show --output none
    if ($LASTEXITCODE -ne 0) {
        throw 'Azure CLI is not authenticated. Run: az login'
    }

    Write-ColorOutput 'Querying resources in resource group...' 'Yellow'

    # Check if resource group exists
    $rgExists = az group exists --name $ResourceGroupName --output tsv
    if ($LASTEXITCODE -ne 0 -or $rgExists -ne 'true') {
        throw "Resource group '$ResourceGroupName' does not exist."
        exit 0
    }
    Write-Host "Resource group '$ResourceGroupName' found." -ForegroundColor Gray

    # Get delegated ACA subnet ID
    Write-ColorOutput 'Resolving ACA delegated subnet...' 'Yellow'
    $acaSubnetId = Resolve-AcaSubnetId -Rg $ResourceGroupName

    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($acaSubnetId)) {
        throw "Failed to resolve delegated ACA subnet in resource group '$ResourceGroupName'."
    }

    Write-Host "Found ACA subnet ID: $acaSubnetId" -ForegroundColor Gray

    # Get Container Registry
    Write-ColorOutput 'Resolving Container Registry (ACR)...' 'Yellow'
    $acrListRaw = az acr list --resource-group $ResourceGroupName --output json
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to list container registries in resource group '$ResourceGroupName'."
    }

    $acrList = $acrListRaw | ConvertFrom-Json
    if ($acrList.Count -eq 0) {
        throw "No container registries found in resource group '$ResourceGroupName'."
    }

    $acr = $acrList[0]
    $registryResourceId = $acr.id
    Write-Host "Found ACR: $($acr.name)" -ForegroundColor Gray
    Write-Host "registryResourceId: $registryResourceId" -ForegroundColor Gray

    Write-ColorOutput 'Ensuring UAMI can pull from ACR...' 'Yellow'
    Ensure-AcrPullRoleAssignment -Rg $ResourceGroupName -IdentityName $UamiName -RegistryResourceId $registryResourceId

    # Get AI Foundry Account
    Write-ColorOutput 'Resolving AI Foundry account...' 'Yellow'
    $foundryRaw = az resource list `
        --resource-group $ResourceGroupName `
        --resource-type "Microsoft.CognitiveServices/accounts" `
        --output json
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to query AI Foundry accounts in resource group '$ResourceGroupName'."
    }

    $foundryList = $foundryRaw | ConvertFrom-Json
    if ($foundryList.Count -eq 0) {
        $foundryAccountName = Read-Host "No AI Foundry account found. Enter Foundry account name"
    }
    else {
        $foundryAccount = $foundryList[0]
        $foundryAccountName = $foundryAccount.name
        Write-Host "Found AI Foundry account: $foundryAccountName" -ForegroundColor Gray
    }

    # Get Model Deployment Name
    Write-ColorOutput 'Resolving model deployment...' 'Yellow'
    if ($foundryAccountName) {
        $modelDeploymentList = az cognitiveservices account deployment list `
          --resource-group "$ResourceGroupName" `
          --name "$foundryAccountName" `
          --query "[].properties.model.name" `
          --output tsv
        if ($LASTEXITCODE -eq 0 -and $modelDeploymentList) {
            # Ensure we have an array of deployment names
            $deploymentNames = @($modelDeploymentList -split "`r?`n" | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
            Write-ColorOutput "found list of models: $($deploymentNames -join ', ')" 'Green'
            if ($deploymentNames -contains 'gpt-5.4') {
                $modelDeploymentName = 'gpt-5.4'
                Write-Host "Selected model deployment: $modelDeploymentName" -ForegroundColor Gray
            }
            else {
                Write-ColorOutput "Model deployment 'gpt-5.4' not found in AI Foundry account '$foundryAccountName'." 'Red'
                Write-ColorOutput "Available deployments: $($deploymentNames -join ', ')" 'Yellow'
                exit 1
            }
        }
        else {
            $modelDeploymentName = Read-Host "Failed to query model deployments. Enter model deployment name"
        }
    }
    else {
        $modelDeploymentName = Read-Host "No Foundry account name available. Enter model deployment name"
    }
    
    if ([string]::IsNullOrWhiteSpace($registryResourceId)) {
        throw "Failed to resolve container registry in resource group '$ResourceGroupName'."
    }

    if ([string]::IsNullOrWhiteSpace($foundryAccountName)) {
        $foundryAccountName = Read-Host "Output 'foundryAccountName' not found. Enter Foundry account name"
    }

    if ([string]::IsNullOrWhiteSpace($modelDeploymentName)) {
        $modelDeploymentName = Read-Host "Output 'modelDeploymentName' not found. Enter model deployment name"
    }

    Write-ColorOutput 'Resolving ACR login server from registryResourceId...' 'Yellow'
    $registryServer = az acr show --name $acr.name --query loginServer --output tsv
    write-ColorOutput "az acr show output: $registryServer" 'Yellow'
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($registryServer)) {
        throw "Failed to resolve ACR login server from registryResourceId '$registryResourceId'."
    } else {
        Write-ColorOutput "Resolved ACR login server: $registryServer" 'Green'
    }

    $parametersJson = Get-Content -Path $parametersPath -Raw | ConvertFrom-Json

    if (-not $parametersJson.parameters) {
        throw "Invalid parameters file format: missing 'parameters' object."
    }

    write-ColorOutput "registryServer: $registryServer" 'Yellow'
    write-ColorOutput "acaSubnetId: $acaSubnetId" 'Yellow'
    write-ColorOutput "containerImage: $ServerImage" 'Yellow'
    write-ColorOutput "clientContainerImage: $ClientImage" 'Yellow'
    write-ColorOutput "foundryAccountName: $foundryAccountName" 'Yellow'
    write-ColorOutput "modelDeploymentName: $modelDeploymentName" 'Yellow'
    write-ColorOutput "internalEnvironment: $InternalEnvironment" 'Yellow'

    $parametersJson.parameters.acaSubnetId.value = $acaSubnetId
    $parametersJson.parameters.registryServer.value = $registryServer
    $parametersJson.parameters.serverContainerImage.value = $ServerImage
    $parametersJson.parameters.clientContainerImage.value = $ClientImage
    $parametersJson.parameters.foundryAccountName.value = $foundryAccountName
    $parametersJson.parameters.modelDeploymentName.value = $modelDeploymentName
    $parametersJson.parameters.internalEnvironment.value = $InternalEnvironment

    $updatedJson = $parametersJson | ConvertTo-Json -Depth 20
    # $updatedJson
    Set-Content -Path $parametersPath -Value $updatedJson -Encoding UTF8

    Write-Host ''
    Write-ColorOutput 'container-apps.parameters.json updated successfully.' 'Green'
    Write-Host ''
    Write-Host 'Resolved values:' -ForegroundColor Gray
    Write-Host "  acaSubnetId:         $acaSubnetId" -ForegroundColor Gray
    Write-Host "  registryServer:       $registryServer" -ForegroundColor Gray
    Write-Host "  containerImage:       $ServerImage" -ForegroundColor Gray
    Write-Host "  clientContainerImage: $ClientImage" -ForegroundColor Gray
    Write-Host "  registryResourceId:   $registryResourceId" -ForegroundColor Gray
    Write-Host "  foundryAccountName:   $foundryAccountName" -ForegroundColor Gray
    Write-Host "  modelDeploymentName:  $modelDeploymentName" -ForegroundColor Gray
    Write-Host "  internalEnvironment:  $InternalEnvironment" -ForegroundColor Gray
    Write-Host ''
    Write-Host 'Next:' -ForegroundColor Yellow
    Write-Host "  ./container-apps.ps1" -ForegroundColor White
}
catch {
    Write-Host ''
    Write-ColorOutput 'Failed to populate container-apps.parameters.json.' 'Red'
    Write-ColorOutput $_.Exception.Message 'Red'
    Write-Host ''
    exit 1
}
