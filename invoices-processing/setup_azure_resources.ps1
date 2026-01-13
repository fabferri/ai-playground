# =============================================================================
# Azure AI Foundry Invoice RAG - Resource Provisioning Script (PowerShell)
# =============================================================================
# This script creates all required Azure resources for the invoice processing project:
# - Resource Group - Container for all resources
# - Azure Storage Account (required for AI Hub)
# - Azure Key Vault (required for AI Hub)
# - Azure AI Foundry Hub & Project (formerly Azure AI Studio)
# - Azure AI Document Intelligence - For invoice extraction
# - Azure AI Search -  For indexing and retrieval
# - Azure OpenAI with model deployment
# =============================================================================

$ErrorActionPreference = "Stop"

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

function Get-ExistingResourceTimestamp {
    <#
    .SYNOPSIS
        Checks for existing resources with timestamp suffix in the resource group
    .DESCRIPTION
        Searches for resources ending with yyyyMMddHHmm format and returns the timestamp
    .PARAMETER ResourceGroupName
        The name of the resource group to search
    .RETURNS
        String with timestamp (yyyyMMddHHmm) if found, otherwise $null
    #>
    param (
        [Parameter(Mandatory=$true)]
        [string]$ResourceGroupName
    )
    
    try {
        # Get all resources in the resource group
        $resources = az resource list --resource-group $ResourceGroupName --query "[].name" -o tsv
        
        if ([string]::IsNullOrEmpty($resources)) {
            return $null
        }
        
        # Pattern for 12-digit timestamp (yyyyMMddHHmm)
        $timestampPattern = '\d{12}$'
        
        foreach ($resourceName in $resources) {
            if ($resourceName -match $timestampPattern) {
                # Extract the timestamp (last 12 digits)
                $timestamp = $resourceName.Substring($resourceName.Length - 12)
                Write-Host "Found existing resource with timestamp: $resourceName" -ForegroundColor Green
                return $timestamp
            }
        }
        
        # No resources with timestamp pattern found
        return $null
    }
    catch {
        Write-Host "Warning: Could not check for existing resources: $_" -ForegroundColor Yellow
        return $null
    }
}

# =============================================================================
# CONFIGURATION - Update these values
# =============================================================================

# Subscription and Location
$SubscriptionName = "Hybrid-PM-Test-2"  # Change to your Azure subscription name
$Location = "swedencentral"             # Change to your preferred region

# Resource naming (base names)
$ResourceGroup = "invoice-rag"
$AIHubName = "aihub-invoice-rag"               # unique within resource group
$AIProjectName = "aiproj-invoice-rag"          # unique within the AI Hub

# Model deployment
$OpenAIModelName = "gpt-5.1"
$OpenAIDeploymentName = "gpt-5.1-deployment"
$OpenAIModelVersion = "2025-11-13"

# Tags
$Tags = @{
    Project = "InvoiceRAG"
    Environment = "Dev"
}

# =============================================================================
# Set Subscription
# =============================================================================
$SubscriptionId = (az account list --query "[?name=='$SubscriptionName'].id" -o tsv)
if ([string]::IsNullOrEmpty($SubscriptionId)) {
     Write-Host "Error: Subscription '$SubscriptionName' not found" -ForegroundColor Red
     exit 1
}
Write-Host "Found subscription ID: $SubscriptionId" -ForegroundColor Green
Write-Host ""
Write-Host "Setting active subscription..." -ForegroundColor Yellow
az account set --subscription $SubscriptionId
$CurrentSubscription = az account show --query name -o tsv
Write-Host "Active subscription: $CurrentSubscription" -ForegroundColor Green

# =============================================================================
# Create Resource Group
# =============================================================================

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Step 1: Creating Resource Group" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

az group create `
  --name $ResourceGroup `
  --location $Location `
  --tags Project=InvoiceRAG Environment=Dev

Write-Host "Resource group created: $ResourceGroup" -ForegroundColor Green

# =============================================================================
# Determine Timestamp for Resource Names
# =============================================================================

# Check for existing resources and reuse timestamp if found
$existingTimestamp = Get-ExistingResourceTimestamp -ResourceGroupName $ResourceGroup
if ($existingTimestamp) {
    $tail = $existingTimestamp
    Write-Host "Reusing existing timestamp: $tail" -ForegroundColor Cyan
} else {
    $tail = (Get-Date -Format 'yyyyMMddHHmm')
    Write-Host "Generated new timestamp: $tail" -ForegroundColor Cyan
}

# Define resource names with timestamp
$DocIntelligenceName = "doc-intel-invoice-rag-$tail" # Must be globally unique
$SearchServiceName = "srch-invoice-rag-$tail"  # Must be globally unique, lowercase
$OpenAIName = "openai-invoice-rag-$tail"       # Must be globally unique
$StorageAccountName = "invoice$tail"    # Must be globally unique (max 24 chars)
$KeyVaultName = "invoice$tail"          # Must be globally unique (max 24 chars)

Write-Host "" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Resource Names:" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "  Document Intelligence: $DocIntelligenceName" -ForegroundColor White
Write-Host "  Search Service:        $SearchServiceName" -ForegroundColor White
Write-Host "  OpenAI Service:        $OpenAIName" -ForegroundColor White
Write-Host "  Storage Account:       $StorageAccountName" -ForegroundColor White
Write-Host "  Key Vault:             $KeyVaultName" -ForegroundColor White
Write-Host "  Timestamp:             $tail" -ForegroundColor White
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""


# =============================================================================
# Create Storage Account (required for AI Hub)
# =============================================================================

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Step 2: Creating Storage Account" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

az storage account create `
  --name $StorageAccountName `
  --resource-group $ResourceGroup `
  --location $Location `
  --sku Standard_LRS `
  --kind StorageV2 `
  --tags Project=InvoiceRAG Environment=Dev

Write-Host "Storage account created: $StorageAccountName" -ForegroundColor Green

# =============================================================================
# Create Key Vault (required for AI Hub)
# =============================================================================

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Step 3: Creating Key Vault" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

az keyvault create `
  --name $KeyVaultName `
  --resource-group $ResourceGroup `
  --location $Location `
  --tags Project=InvoiceRAG Environment=Dev

Write-Host "Key Vault created: $KeyVaultName" -ForegroundColor Green

# =============================================================================
# Create Azure AI Hub (formerly Azure AI Studio Hub)
# =============================================================================

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Step 4: Creating Azure AI Hub" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

# Get resource IDs
$StorageId = az storage account show --name $StorageAccountName --resource-group $ResourceGroup --query id -o tsv
$KeyVaultId = az keyvault show --name $KeyVaultName --resource-group $ResourceGroup --query id -o tsv

az ml workspace create `
  --kind hub `
  --resource-group $ResourceGroup `
  --name $AIHubName `
  --location $Location `
  --storage-account $StorageId `
  --key-vault $KeyVaultId `
  --tags Project=InvoiceRAG Environment=Dev

Write-Host "AI Hub created: $AIHubName" -ForegroundColor Green

# =============================================================================
# Create Azure AI Project
# =============================================================================

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Step 5: Creating Azure AI Project" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

$HubId = az ml workspace show --name $AIHubName --resource-group $ResourceGroup --query id -o tsv

az ml workspace create `
  --kind project `
  --resource-group $ResourceGroup `
  --name $AIProjectName `
  --location $Location `
  --hub-id $HubId `
  --tags Project=InvoiceRAG Environment=Dev

Write-Host "AI Project created: $AIProjectName" -ForegroundColor Green

# =============================================================================
# Create Azure AI Document Intelligence
# =============================================================================

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Step 6: Creating Azure AI Document Intelligence" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

# Check for soft-deleted resources and purge if needed
try {
    $softDeleted = az cognitiveservices account list-deleted --query "[?name=='$DocIntelligenceName'].name" -o tsv 2>$null
    if ($softDeleted) {
        Write-Host "Found soft-deleted resource '$DocIntelligenceName'. Purging..." -ForegroundColor Yellow
        az cognitiveservices account purge --name $DocIntelligenceName --location $Location
        Write-Host "Soft-deleted resource purged. Waiting 10 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
} catch {
    Write-Host "Warning: Could not check for soft-deleted resources: $_" -ForegroundColor Yellow
}

az cognitiveservices account create `
  --name $DocIntelligenceName `
  --resource-group $ResourceGroup `
  --kind FormRecognizer `
  --sku S0 `
  --location $Location `
  --yes `
  --tags Project=InvoiceRAG Environment=Dev

Write-Host "Document Intelligence created: $DocIntelligenceName" -ForegroundColor Green

# Get endpoint and key
$DocIntelEndpoint = az cognitiveservices account show `
  --name $DocIntelligenceName `
  --resource-group $ResourceGroup `
  --query properties.endpoint -o tsv

$DocIntelKey = az cognitiveservices account keys list `
  --name $DocIntelligenceName `
  --resource-group $ResourceGroup `
  --query key1 -o tsv

# =============================================================================
# Create Azure AI Search
# =============================================================================

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Step 7: Creating Azure AI Search" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

az search service create `
  --name $SearchServiceName `
  --resource-group $ResourceGroup `
  --location $Location `
  --sku basic `
  --partition-count 1 `
  --replica-count 1 `
  --tags Project=InvoiceRAG Environment=Dev

Write-Host "Search service created: $SearchServiceName" -ForegroundColor Green

# Get endpoint and key
$SearchEndpoint = "https://$SearchServiceName.search.windows.net"

$SearchKey = az search admin-key show `
  --resource-group $ResourceGroup `
  --service-name $SearchServiceName `
  --query primaryKey -o tsv

# =============================================================================
# Create Azure OpenAI
# =============================================================================

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Step 8: Creating Azure OpenAI Service" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

# Check for soft-deleted resources and purge if needed
try {
    $softDeleted = az cognitiveservices account list-deleted --query "[?name=='$OpenAIName'].name" -o tsv 2>$null
    if ($softDeleted) {
        Write-Host "Found soft-deleted resource '$OpenAIName'. Purging..." -ForegroundColor Yellow
        az cognitiveservices account purge --name $OpenAIName --location $Location
        Write-Host "Soft-deleted resource purged. Waiting 10 seconds..." -ForegroundColor Yellow
        Start-Sleep -Seconds 10
    }
} catch {
    Write-Host "Warning: Could not check for soft-deleted resources: $_" -ForegroundColor Yellow
}

az cognitiveservices account create `
  --name $OpenAIName `
  --resource-group $ResourceGroup `
  --kind OpenAI `
  --sku S0 `
  --location $Location `
  --yes `
  --tags Project=InvoiceRAG Environment=Dev

Write-Host "Azure OpenAI created: $OpenAIName" -ForegroundColor Green

# Get endpoint and key
$OpenAIEndpoint = az cognitiveservices account show `
  --name $OpenAIName `
  --resource-group $ResourceGroup `
  --query properties.endpoint -o tsv

$OpenAIKey = az cognitiveservices account keys list `
  --name $OpenAIName `
  --resource-group $ResourceGroup `
  --query key1 -o tsv

# =============================================================================
# Deploy OpenAI Model
# =============================================================================

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Step 9: Deploying OpenAI Model" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

az cognitiveservices account deployment create `
  --resource-group $ResourceGroup `
  --name $OpenAIName `
  --deployment-name $OpenAIDeploymentName `
  --model-name $OpenAIModelName `
  --model-version $OpenAIModelVersion `
  --model-format OpenAI `
  --sku-capacity 10 `
  --sku-name "GlobalStandard"

Write-Host "Model deployment created: $OpenAIDeploymentName" -ForegroundColor Green

# =============================================================================
# Get AI Project Endpoint
# =============================================================================

Write-Host ""
Write-Host "Getting AI Project endpoint..." -ForegroundColor Yellow

# Get workspace details as JSON
$WorkspaceJson = az ml workspace show `
  --name $AIProjectName `
  --resource-group $ResourceGroup `
  -o json | ConvertFrom-Json

# Try to get the MLFlow tracking URI (preferred for AI Foundry projects)
$MLFlowUri = $WorkspaceJson.mlflow_tracking_uri

if ([string]::IsNullOrEmpty($MLFlowUri)) {
    Write-Host "Warning: mlflow_tracking_uri not found. Trying discovery_url..." -ForegroundColor Yellow
    
    # Fall back to discovery URL
    $DiscoveryUrl = $WorkspaceJson.discovery_url
    
    if ([string]::IsNullOrEmpty($DiscoveryUrl)) {
        Write-Host "Warning: Both URIs are empty. Constructing manually..." -ForegroundColor Yellow
        
        # Construct manually as last resort
        $WorkspaceLocation = $WorkspaceJson.location
        $ProjectEndpoint = "https://$WorkspaceLocation.api.azureml.ms/mlflow/v1.0/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.MachineLearningServices/workspaces/$AIProjectName"
        Write-Host "Constructed endpoint: $ProjectEndpoint" -ForegroundColor Yellow
    } else {
        # Use discovery URL and convert to API endpoint
        $ProjectEndpoint = $DiscoveryUrl -replace "discovery", "api"
        Write-Host "Using discovery URL: $ProjectEndpoint" -ForegroundColor Green
    }
} else {
    # Use MLFlow tracking URI (best option for AI Foundry)
    $ProjectEndpoint = $MLFlowUri
    Write-Host "Found MLFlow tracking URI: $ProjectEndpoint" -ForegroundColor Green
}

# =============================================================================
# Output Configuration
# =============================================================================

Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Green
Write-Host "RESOURCE PROVISIONING COMPLETE" -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Copy these values to your create_azure_project.py configuration:" -ForegroundColor Yellow
Write-Host ""
Write-Host "# Azure AI Foundry Project" -ForegroundColor Cyan
Write-Host "FOUNDRY_PROJECT_ENDPOINT = `"$ProjectEndpoint`""
Write-Host "FOUNDRY_MODEL_DEPLOYMENT = `"$OpenAIDeploymentName`""
Write-Host ""
Write-Host "# Azure AI Document Intelligence" -ForegroundColor Cyan
Write-Host "DOCUMENT_INTELLIGENCE_ENDPOINT = `"$DocIntelEndpoint`""
Write-Host "DOCUMENT_INTELLIGENCE_KEY = `"$DocIntelKey`""
Write-Host ""
Write-Host "# Azure AI Search" -ForegroundColor Cyan
Write-Host "SEARCH_ENDPOINT = `"$SearchEndpoint`""
Write-Host "SEARCH_KEY = `"$SearchKey`""
Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Resource Details:" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Resource Group:        $ResourceGroup"
Write-Host "Location:              $Location"
Write-Host "AI Hub:                $AIHubName"
Write-Host "AI Project:            $AIProjectName"
Write-Host "Document Intelligence: $DocIntelligenceName"
Write-Host "Search Service:        $SearchServiceName"
Write-Host "OpenAI Service:        $OpenAIName"
Write-Host "Model Deployment:      $OpenAIDeploymentName"
Write-Host ""
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host "Next Steps:" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Save the configuration values above to create_azure_project.py"
Write-Host "2. Install Python dependencies:"
Write-Host "   pip install agent-framework-azure-ai --pre"
Write-Host "   pip install -r requirements.txt"
Write-Host "3. Run the setup script:"
Write-Host "   python create_azure_project.py"
Write-Host ""
Write-Host "To view resources in Azure Portal:"
Write-Host "https://portal.azure.com/#@/resource/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup"
Write-Host ""
Write-Host "To delete all resources when done:"
Write-Host "az group delete --name $ResourceGroup --yes --no-wait"
Write-Host ""

# =============================================================================
# Save Configuration to .env File
# =============================================================================

$ConfigFile = ".env"

$ConfigContent = @"
# Azure AI Search
SEARCH_ENDPOINT=$SearchEndpoint
SEARCH_KEY=$SearchKey
SEARCH_INDEX_NAME=invoices-index

# Azure OpenAI
OPENAI_ENDPOINT=$OpenAIEndpoint
OPENAI_KEY=$OpenAIKey
OPENAI_DEPLOYMENT=$OpenAIDeploymentName
OPENAI_API_VERSION=2024-08-01-preview

# Azure Document Intelligence
DOC_INTEL_ENDPOINT=$DocIntelEndpoint
DOC_INTEL_KEY=$DocIntelKey

# Project Configuration
INVOICES_FOLDER=invoices
MANIFEST_FILE=invoices/manifest_invoices.json
"@

Set-Content -Path $ConfigFile -Value $ConfigContent -Encoding UTF8

Write-Host "==========================================================================" -ForegroundColor Green
Write-Host "Configuration saved to: $ConfigFile" -ForegroundColor Green
Write-Host "==========================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Resource Details:" -ForegroundColor Cyan
Write-Host "  Resource Group:        $ResourceGroup" -ForegroundColor White
Write-Host "  Location:              $Location" -ForegroundColor White
Write-Host "  AI Hub:                $AIHubName" -ForegroundColor White
Write-Host "  AI Project:            $AIProjectName" -ForegroundColor White
Write-Host "  Document Intelligence: $DocIntelligenceName" -ForegroundColor White
Write-Host "  Search Service:        $SearchServiceName" -ForegroundColor White
Write-Host "  OpenAI Service:        $OpenAIName" -ForegroundColor White
Write-Host "  Model Deployment:      $OpenAIDeploymentName" -ForegroundColor White
Write-Host ""
