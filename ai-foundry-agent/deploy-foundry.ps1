# =============================================================================
# Azure AI Foundry Service and Project Deployment Script
# =============================================================================
# This script creates:
# 1. Resource Group
# 2. Azure AI Account (AIHub or AIServices based on $accountKind variable)
#    - AIHub: Creates an AI Hub account (for ML workspace integration)
#    - AIServices: Creates an AI Services account (standalone Foundry service)
# 3. Azure AI Foundry Project
# 4. GPT-4o Model Deployment
# =============================================================================

# -----------------------------------------------------------------------------
# Configuration Variables - Customize these values
# -----------------------------------------------------------------------------
$resourceGroup = "foundry-agent-200"
$location = "swedencentral"                                    # Supported regions: eastus, westus, etc.

# Account Kind: Choose between "AIHub" or "AIServices"
# - AIHub: Creates an AI Hub account (integrates with Azure ML workspace)
# - AIServices: Creates an AI Services account (standalone Foundry service)
$accountKind = "AIServices"                             # Options: "AIHub" or "AIServices"

# Generate deterministic random number based on resource group name hash
$rgHash = [Math]::Abs($resourceGroup.GetHashCode()) % 99999

# Set account name prefix based on account kind
if ($accountKind -eq "AIHub") {
    $accountName = "ai-hub-$rgHash"                     # Must be globally unique
} else {
    $accountName = "ai-services-$rgHash"                 # Must be globally unique
}

$projectName = "prj-multiagent"
$modelDeploymentName = "gpt-4o"
$modelName = "gpt-4o"
$modelVersion = "2024-11-20"
$skuCapacity = 10                                       # TPM capacity (10 = 10K TPM)

# -----------------------------------------------------------------------------
# Login to Azure (if not already logged in)
# -----------------------------------------------------------------------------
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Azure AI Foundry Deployment Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if already logged in
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "Logging in to Azure..." -ForegroundColor Yellow
    az login
    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to login to Azure" -ForegroundColor Red
        exit 1
    }
}
else {
    Write-Host "Already logged in as: $($account.user.name)" -ForegroundColor Green
    Write-Host "Subscription: $($account.name)" -ForegroundColor Green
}
Write-Host ""

# -----------------------------------------------------------------------------
# Step 1: Create Resource Group
# -----------------------------------------------------------------------------
Write-Host "Step 1: Creating Resource Group..." -ForegroundColor Yellow
az group create `
    --name $resourceGroup `
    --location $location `
    --output table

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create resource group" -ForegroundColor Red
    exit 1
}
Write-Host "Resource Group created successfully!" -ForegroundColor Green
Write-Host ""

# -----------------------------------------------------------------------------
# Step 2: Create Azure AI Account (AIHub or AIServices)
# -----------------------------------------------------------------------------
Write-Host "Step 2: Creating Azure AI Account (Kind: $accountKind)..." -ForegroundColor Yellow
Write-Host "This may take a few minutes..." -ForegroundColor Gray

az cognitiveservices account create `
    --name $accountName `
    --resource-group $resourceGroup `
    --kind $accountKind `
    --sku S0 `
    --location $location `
    --custom-domain $accountName `
    --output table

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create AI Account ($accountKind)" -ForegroundColor Red
    exit 1
}
Write-Host "AI Account ($accountKind) created successfully!" -ForegroundColor Green
Write-Host ""

# -----------------------------------------------------------------------------
# Step 3: Create Azure AI Foundry Project
# -----------------------------------------------------------------------------
Write-Host "Step 3: Creating Azure AI Foundry Project..." -ForegroundColor Yellow

az cognitiveservices account project create `
    --name $accountName `
    --resource-group $resourceGroup `
    --project-name $projectName `
    --location $location `
    --output table

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create AI Foundry Project" -ForegroundColor Red
    exit 1
}
Write-Host "AI Foundry Project created successfully!" -ForegroundColor Green
Write-Host ""

# -----------------------------------------------------------------------------
# Step 4: Deploy GPT-4o Model (Optional)
# -----------------------------------------------------------------------------
$createModel = Read-Host "Do you want to deploy the GPT-4o model? (Y/N) [Default: Y]"
if ([string]::IsNullOrWhiteSpace($createModel)) { $createModel = "Y" }

if ($createModel -eq "Y" -or $createModel -eq "y") {
    Write-Host "Step 4: Deploying GPT-4o Model..." -ForegroundColor YellowGateway subnet?
    Write-Host "This may take a few minutes..." -ForegroundColor Gray

    az cognitiveservices account deployment create `
        --name $accountName `
        --resource-group $resourceGroup `
        --deployment-name $modelDeploymentName `
        --model-name $modelName `
        --model-version $modelVersion `
        --model-format OpenAI `
        --sku-capacity $skuCapacity `
        --sku-name "Standard" `
        --output table

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Failed to deploy GPT-4o model" -ForegroundColor Red
        exit 1
    }
    Write-Host "GPT-4o Model deployed successfully!" -ForegroundColor Green
} else {
    Write-Host "Step 4: Skipping model deployment..." -ForegroundColor Yellow
}
Write-Host ""

# -----------------------------------------------------------------------------
# Step 5: Get Project Endpoint and Display Configuration
# -----------------------------------------------------------------------------
Write-Host "Step 5: Retrieving Project Configuration..." -ForegroundColor Yellow

# Get the AI account endpoint
$accountInfo = az cognitiveservices account show `
    --name $accountName `
    --resource-group $resourceGroup `
    --output json | ConvertFrom-Json

$endpoint = $accountInfo.properties.endpoint

# Get the project info
$projectInfo = az cognitiveservices account project show `
    --name $accountName `
    --resource-group $resourceGroup `
    --project-name $projectName `
    --output json | ConvertFrom-Json

# Construct the project endpoint
$projectEndpoint = "https://$accountName.services.ai.azure.com/api/projects/$projectName"

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Resource Group:      $resourceGroup" -ForegroundColor White
Write-Host "Account Kind:        $accountKind" -ForegroundColor White
Write-Host "Account Name:        $accountName" -ForegroundColor White
Write-Host "Project Name:        $projectName" -ForegroundColor White
Write-Host "Model Deployment:    $modelDeploymentName" -ForegroundColor White
Write-Host "Location:            $location" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ".env Configuration" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Add the following to your .env file:" -ForegroundColor Yellow
Write-Host ""
Write-Host "PROJECT_ENDPOINT=`"$projectEndpoint`"" -ForegroundColor Green
Write-Host "MODEL_DEPLOYMENT_NAME=`"$modelDeploymentName`"" -ForegroundColor Green
Write-Host ""

# -----------------------------------------------------------------------------
# Step 6: Optionally update the .env file
# -----------------------------------------------------------------------------
$envFilePath = Join-Path $PSScriptRoot ".env"
$updateEnv = Read-Host "Do you want to update the .env file automatically? (y/n)"

if ($updateEnv -eq "y" -or $updateEnv -eq "Y") {
    $envContent = @"
PROJECT_ENDPOINT="$projectEndpoint"
MODEL_DEPLOYMENT_NAME="$modelDeploymentName"
"@
    Set-Content -Path $envFilePath -Value $envContent
    Write-Host ".env file updated successfully!" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Next Steps" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "1. Ensure you are logged in with Azure CLI: az login" -ForegroundColor White
Write-Host "2. Assign 'Cognitive Services User' role to your account for authentication" -ForegroundColor White
Write-Host "3. Run your agent script: python agent_triage.py" -ForegroundColor White
Write-Host ""

# -----------------------------------------------------------------------------
# Display Role Assignment Command
# -----------------------------------------------------------------------------
Write-Host "To assign the required role, run:" -ForegroundColor Yellow
$subscriptionId = (az account show --query id -o tsv)
Write-Host "az role assignment create --assignee `"<your-user-principal-name-or-object-id>`" --role `"Cognitive Services User`" --scope `"/subscriptions/$subscriptionId/resourceGroups/$resourceGroup/providers/Microsoft.CognitiveServices/accounts/$accountName`"" -ForegroundColor Gray
Write-Host ""
