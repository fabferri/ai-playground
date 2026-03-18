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
$armTemplateFile = 'container-apps.json' 
$armTemplateParametersFile = 'container-apps.parameters.json'
$populateParametersScriptFile = 'populate-container-apps-params.ps1'
$inputvarFile = 'init.json'

$pathFiles = Split-Path -Parent $PSCommandPath
$templateFile = "$pathFiles\$armTemplateFile"
$parametersFile = "$pathFiles\$armTemplateParametersFile"
$populateParametersScript = "$pathFiles\$populateParametersScriptFile"
$inputvarFile = "$pathFiles\$inputvarFile"

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

    if (-not (Test-Path $populateParametersScript)) {
        throw "Helper script not found: $populateParametersScript"
    }

    # Populate app-layer parameters automatically from infra deployment outputs
    Write-ColorOutput "Populating app-layer parameters from infrastructure outputs..." "Yellow"
    $helperArgs = @{
        SubscriptionName = $subscriptionName
        ResourceGroupName = $rgName
        ParametersFile = $armTemplateParametersFile
    }

    & $populateParametersScript @helperArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to populate '$armTemplateParametersFile'."
    }

    Write-ColorOutput "✓ Parameters file populated successfully" "Green"
    Write-Host ""

    # Validate ARM template before deployment
    Write-ColorOutput "Validating deployment template..." "Yellow"
    az deployment group validate `
        --resource-group $rgName `
        --template-file $TemplateFile `
        --parameters $ParametersFile `
        --output json | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "Template validation failed. See error details above."
    }

    Write-ColorOutput "✓ Template validation passed" "Green"
    Write-Host ""

 
    # Deploy ARM template
    Write-ColorOutput "Starting deployment..." "Yellow"
    Write-Host ""

    $deploymentStartTime = Get-Date

    # Deploy using Azure CLI
    az deployment group create `
        --resource-group $rgName `
        --name $DeploymentName `
        --template-file $TemplateFile `
        --parameters $ParametersFile `
        --output json | Out-Null

    if ($LASTEXITCODE -ne 0) {
        throw "Deployment failed. Check the error messages above."
    }

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
