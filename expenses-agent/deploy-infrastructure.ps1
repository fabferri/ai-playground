# =============================================================================
# Azure AI Foundry Infrastructure Deployment Script
# =============================================================================
# This script creates the Azure infrastructure required for the expense-agent.
# It performs Steps 1-4 from Readme.md using Azure CLI.
#
# Actions performed:
#   Step 1: Check and purge soft-deleted AI Services account (if exists)
#   Step 2: Create Resource Group
#   Step 3: Create Azure AI Services Account (with allowProjectManagement enabled)
#   Step 4: Verify account provisioning and allowProjectManagement
#   Step 5: Create Foundry Project
#   Step 6: Deploy Model (gpt-4.1)
#   Step 7: Get Project Endpoint
#   Step 8: Update .env file with project endpoint
#
# Prerequisites:
#   - Azure CLI installed and logged in (az login)
#   - Sufficient permissions to create resources
#
# Usage:
#   .\deploy-infrastructure.ps1
# =============================================================================

# Configuration - Modify these values as needed
$ResourceGroup = "expenses"
$Location = "swedencentral"
$AccountName = "expenses-resources"
$ProjectName = "expenses-project"
$ModelName = "gpt-4.1"
$ModelVersion = "2025-04-14"
$SkuCapacity = 10

# =============================================================================
# Helper Functions
# =============================================================================

function Write-Step {
    param([string]$StepNumber, [string]$Description)
    Write-Host ""
    Write-Host ("=" * 60) -ForegroundColor Cyan
    Write-Host "STEP $StepNumber : $Description" -ForegroundColor Cyan
    Write-Host ("=" * 60) -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host (Get-date)"- $Message" -ForegroundColor Green
}

function Write-Info {
    param([string]$Message)
    Write-Host (Get-date)"- $Message" -ForegroundColor White
}

function Write-Warning {
    param([string]$Message)
    Write-Host (Get-date)"- $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host (Get-date)"-   $Message" -ForegroundColor Red
}

# =============================================================================
# Check Prerequisites
# =============================================================================

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Magenta
Write-Host "AZURE AI FOUNDRY INFRASTRUCTURE DEPLOYMENT" -ForegroundColor Magenta
Write-Host ("=" * 60) -ForegroundColor Magenta

Write-Host ""
Write-Host "Checking prerequisites..." -ForegroundColor White

# Check if Azure CLI is installed
try {
    $azVersion = az version --query '"azure-cli"' -o tsv 2>$null
    if ($LASTEXITCODE -ne 0) {
        $azVersion = (az version | ConvertFrom-Json).'azure-cli'
    }
    Write-Success "Azure CLI version: $azVersion"
} catch {
    Write-Error "Azure CLI is not installed. Please install it from https://aka.ms/installazurecli"
    exit 1
}

# Check if logged in
$account = az account show 2>$null | ConvertFrom-Json
if ($LASTEXITCODE -ne 0) {
    Write-Error "Not logged in to Azure. Please run 'az login' first."
    exit 1
}
Write-Success "Logged in as: $($account.user.name)"
Write-Success "Subscription: $($account.name)"

$SubscriptionId = $account.id

# =============================================================================
# STEP 1: Purge Soft-Deleted AI Services Account (if exists)
# =============================================================================

Write-Step "1" "Check and Purge Soft-Deleted AI Services Account"

Write-Info "Checking for soft-deleted AI Services account '$AccountName'..."

# List soft-deleted accounts and check if our account is there
$deletedAccounts = az cognitiveservices account list-deleted --query "[?name=='$AccountName']" 2>$null | ConvertFrom-Json

if ($deletedAccounts -and $deletedAccounts.Count -gt 0) {
    Write-Warning "Found soft-deleted account '$AccountName'. Purging..."
    az cognitiveservices account purge `
        --name $AccountName `
        --resource-group $ResourceGroup `
        --location $Location `
        --output none 2>$null
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Soft-deleted account purged successfully"
    } else {
        Write-Warning "Could not purge account (may not exist or already purged)"
    }
} else {
    Write-Success "No soft-deleted account found"
}

# =============================================================================
# STEP 2: Create Resource Group
# =============================================================================

Write-Step "2" "Create Resource Group"

$rgExists = az group exists --name $ResourceGroup 2>$null
if ($rgExists -eq "true") {
    Write-Warning "Resource group '$ResourceGroup' already exists"
} else {
    Write-Info "Creating resource group '$ResourceGroup' in '$Location'..."
    az group create --name $ResourceGroup --location $Location --output none
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Resource group created successfully"
    } else {
        Write-Error "Failed to create resource group"
        exit 1
    }
}

# =============================================================================
# STEP 3: Create Azure AI Services Account
# =============================================================================

Write-Step "3" "Create Azure AI Services Account"

# Check if account exists and has allowProjectManagement enabled
$existingAccount = az cognitiveservices account show --name $AccountName --resource-group $ResourceGroup 2>$null | ConvertFrom-Json
$accountExists = $LASTEXITCODE -eq 0

if ($accountExists) {
    $allowProjectMgmt = $existingAccount.properties.allowProjectManagement
    if ($allowProjectMgmt -eq $true) {
        Write-Warning "AI Services account '$AccountName' already exists with allowProjectManagement enabled"
    } else {
        Write-Warning "AI Services account '$AccountName' exists but allowProjectManagement is NOT enabled"
        Write-Info "Deleting and recreating the account to enable allowProjectManagement..."
        
        # Delete the existing account
        az cognitiveservices account delete --name $AccountName --resource-group $ResourceGroup --output none
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Failed to delete existing AI Services account"
            exit 1
        }
        
        # Wait for deletion to complete
        Start-Sleep -Seconds 5
        
        # Purge the soft-deleted account
        Write-Info "Purging soft-deleted account..."
        az cognitiveservices account purge --name $AccountName --resource-group $ResourceGroup --location $Location --output none 2>$null
        Start-Sleep -Seconds 5
        
        $accountExists = $false
    }
}

if (-not $accountExists) {
    Write-Info "Creating AI Services account '$AccountName' with project management enabled..."
    Write-Info "This may take a few minutes..."
    
    # Use Azure CLI to create the account - this properly enables allowProjectManagement
    # The --custom-domain parameter is required for Foundry projects
    az cognitiveservices account create `
        --name $AccountName `
        --resource-group $ResourceGroup `
        --kind "AIServices" `
        --sku "S0" `
        --location $Location `
        --custom-domain $AccountName `
        --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "AI Services account created successfully"
    } else {
        Write-Error "Failed to create AI Services account"
        exit 1
    }
}

# =============================================================================
# STEP 4: Verify Account Provisioning and allowProjectManagement
# =============================================================================

Write-Step "4" "Verify Account Provisioning"

Write-Info "Waiting for account to be fully provisioned..."
$maxAttempts = 12
$attempt = 0
$accountReady = $false

do {
    $attempt++
    Start-Sleep -Seconds 10
    
    $accountInfo = az cognitiveservices account show `
        --name $AccountName `
        --resource-group $ResourceGroup `
        --query "{provisioningState: properties.provisioningState, allowProjectManagement: properties.allowProjectManagement}" `
        -o json 2>$null | ConvertFrom-Json
    
    if ($accountInfo.provisioningState -eq "Succeeded" -and $accountInfo.allowProjectManagement -eq $true) {
        $accountReady = $true
        Write-Success "Account provisioned successfully with allowProjectManagement enabled"
    } else {
        Write-Info "Attempt $attempt/$maxAttempts : State=$($accountInfo.provisioningState), allowProjectManagement=$($accountInfo.allowProjectManagement)"
    }
} while (-not $accountReady -and $attempt -lt $maxAttempts)

if (-not $accountReady) {
    Write-Error "Account provisioning failed or allowProjectManagement is not enabled after $maxAttempts attempts"
    Write-Error "Please delete the account manually and run the script again"
    exit 1
}

# =============================================================================
# STEP 5: Create Foundry Project
# =============================================================================

Write-Step "5" "Create Foundry Project"

# Check if project exists using Azure CLI
$projectExists = az cognitiveservices account project show `
    --name $AccountName `
    --resource-group $ResourceGroup `
    --project-name $ProjectName 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Warning "Foundry project '$ProjectName' already exists"
} else {
    Write-Info "Creating Foundry project '$ProjectName'..."
    
    az cognitiveservices account project create `
        --name $AccountName `
        --resource-group $ResourceGroup `
        --project-name $ProjectName `
        --location $Location `
        --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Foundry project created successfully"
    } else {
        Write-Error "Failed to create Foundry project"
        exit 1
    }
}

# =============================================================================
# STEP 6: Deploy Model (Optional - may already exist)
# =============================================================================

Write-Step "6" "Deploy Model (gpt-4.1)"

$deploymentExists = az cognitiveservices account deployment show `
    --name $AccountName `
    --resource-group $ResourceGroup `
    --deployment-name $ModelName 2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Warning "Model deployment '$ModelName' already exists"
} else {
    Write-Info "Deploying model '$ModelName'..."
    Write-Info "This may take a few minutes..."
    
    az cognitiveservices account deployment create `
        --name $AccountName `
        --resource-group $ResourceGroup `
        --deployment-name $ModelName `
        --model-name $ModelName `
        --model-version $ModelVersion `
        --model-format OpenAI `
        --sku-capacity $SkuCapacity `
        --sku-name GlobalStandard `
        --output none
    
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Model deployed successfully"
    } else {
        Write-Warning "Model deployment failed - may need to be done manually"
    }
}

# =============================================================================
# Get Project Endpoint
# =============================================================================

Write-Step "7" "Get Project Endpoint"

$projectInfo = az rest --method GET --uri $projectUri 2>$null | ConvertFrom-Json
if ($LASTEXITCODE -eq 0 -and $projectInfo.properties.endpoints) {
    $projectEndpoint = $projectInfo.properties.endpoints.'AI Foundry API'
    Write-Success "Project endpoint: $projectEndpoint"
} else {
    # Construct endpoint manually
    $projectEndpoint = "https://$AccountName.services.ai.azure.com/api/projects/$ProjectName"
    Write-Info "Constructed endpoint: $projectEndpoint"
}

# =============================================================================
# Update .env File
# =============================================================================

Write-Step "8" "Update .env File"

$envFile = Join-Path $PSScriptRoot ".env"

if (Test-Path $envFile) {
    Write-Info "Reading existing .env file..."
    $envContent = Get-Content $envFile -Raw
    
    # Update or add AZURE_EXISTING_AIPROJECT_ENDPOINT
    if ($envContent -match 'AZURE_EXISTING_AIPROJECT_ENDPOINT=') {
        $envContent = $envContent -replace 'AZURE_EXISTING_AIPROJECT_ENDPOINT=.*', "AZURE_EXISTING_AIPROJECT_ENDPOINT=`"$projectEndpoint`""
        Write-Info "Updated AZURE_EXISTING_AIPROJECT_ENDPOINT"
    } else {
        $envContent += "`nAZURE_EXISTING_AIPROJECT_ENDPOINT=`"$projectEndpoint`""
        Write-Info "Added AZURE_EXISTING_AIPROJECT_ENDPOINT"
    }
    
    # Update or add AZURE_EXISTING_AGENT_ID
    if ($envContent -match 'AZURE_EXISTING_AGENT_ID=') {
        $envContent = $envContent -replace 'AZURE_EXISTING_AGENT_ID=.*', 'AZURE_EXISTING_AGENT_ID="expense-agent"'
        Write-Info "Updated AZURE_EXISTING_AGENT_ID"
    } else {
        $envContent += "`nAZURE_EXISTING_AGENT_ID=`"expense-agent`""
        Write-Info "Added AZURE_EXISTING_AGENT_ID"
    }
    
    # Write back to file
    $envContent | Set-Content $envFile -NoNewline
    Write-Success ".env file updated successfully"
} else {
    # Create new .env file
    Write-Info "Creating new .env file..."
    @"
AZURE_EXISTING_AIPROJECT_ENDPOINT="$projectEndpoint"
AZURE_EXISTING_AGENT_ID="expense-agent"
AZURE_LOCATION="$Location"
AZURE_SUBSCRIPTION_ID="$SubscriptionId"
"@ | Set-Content $envFile
    Write-Success ".env file created successfully"
}

# =============================================================================
# Summary
# =============================================================================

Write-Host ""
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host ("=" * 60) -ForegroundColor Green
Write-Host ""
Write-Host "Resources Created:" -ForegroundColor White
Write-Host "  Resource Group:     $ResourceGroup" -ForegroundColor Gray
Write-Host "  Location:           $Location" -ForegroundColor Gray
Write-Host "  AI Services Account: $AccountName" -ForegroundColor Gray
Write-Host "  Foundry Project:    $ProjectName" -ForegroundColor Gray
Write-Host "  Model Deployment:   $ModelName" -ForegroundColor Gray
Write-Host ""
Write-Host "Project Endpoint:" -ForegroundColor White
Write-Host "  $projectEndpoint" -ForegroundColor Yellow
Write-Host ""
Write-Host "Next Steps:" -ForegroundColor White
Write-Host "  1. Run expense.py to deploy the agent:" -ForegroundColor Gray
Write-Host "     python expense.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "  2. Or use the REST API commands in Readme.md" -ForegroundColor Gray
Write-Host ""
