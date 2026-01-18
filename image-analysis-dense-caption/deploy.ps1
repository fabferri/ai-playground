<#
.SYNOPSIS
    Deploys Azure AI Vision (Computer Vision) resource for Dense Caption analysis.

.DESCRIPTION
    This script creates all necessary Azure resources to run the Dense Caption project:
    - Resource Group
    - Azure AI Vision (Computer Vision) service
    
    After deployment, it updates the .env file with the endpoint and key.

.PARAMETER ResourceGroupName
    Name of the Azure Resource Group to create/use.

.PARAMETER Location
    Azure region for deployment. Dense Captions feature is only available in:
    eastus, westus, westus2, westeurope, francecentral, northeurope, australiaeast, 
    southeastasia, japaneast, koreacentral, centralindia.

.PARAMETER VisionAccountName
    Name for the Azure AI Vision account.

.PARAMETER Sku
    Pricing tier: F0 (Free) or S1 (Standard).

.EXAMPLE
    .\deploy.ps1 -ResourceGroupName "rg-vision-demo" -Location "eastus" -VisionAccountName "vision-dense-caption"
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$ResourceGroupName = "vision-dense-caption",

    [Parameter(Mandatory = $false)]
    [ValidateSet("eastus", "westus", "westus2", "westeurope", "francecentral", "northeurope", "australiaeast", "southeastasia", "japaneast", "koreacentral", "centralindia")]
    [string]$Location = "northeurope",

    [Parameter(Mandatory = $false)]
    [string]$VisionAccountName = "vision-dense-caption-$((Get-Random -Maximum 9999))",

    [Parameter(Mandatory = $false)]
    [ValidateSet("F0", "S1")]
    [string]$Sku = "S1"
)

$ErrorActionPreference = "Stop"

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Azure AI Vision Deployment Script" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Check if Azure CLI is installed
try {
    $azVersion = az version --output json | ConvertFrom-Json
    Write-Host (Get-Date)"- Azure CLI version: $($azVersion.'azure-cli')" -ForegroundColor Green
}
catch {
    Write-Host (Get-Date)"- Azure CLI is not installed. Please install it from: https://docs.microsoft.com/cli/azure/install-azure-cli" -ForegroundColor Red
    exit 1
}

# Check if logged in to Azure
Write-Host (Get-Date)"- Checking Azure login status..." -ForegroundColor Yellow
$account = az account show --output json 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host (Get-Date)"-Not logged in to Azure. Starting login..." -ForegroundColor Yellow
    az login
    $account = az account show --output json | ConvertFrom-Json
}
Write-Host (Get-Date)"- Logged in as: $($account.user.name)" -ForegroundColor Green
Write-Host (Get-Date)"- Subscription: $($account.name) ($($account.id))" -ForegroundColor Gray

# Create Resource Group
Write-Host (Get-Date)"- Creating Resource Group: $ResourceGroupName..." -ForegroundColor Yellow
az group create `
    --name $ResourceGroupName `
    --location $Location `
    --output none

Write-Host (Get-Date)"- Resource Group created/verified" -ForegroundColor Green

# Create Azure AI Vision (Computer Vision) account
Write-Host (Get-Date)"- Creating Azure AI Vision account: $VisionAccountName..." -ForegroundColor Yellow
Write-Host (Get-Date)"-   SKU: $Sku | Location: $Location" -ForegroundColor Gray

az cognitiveservices account create `
    --name $VisionAccountName `
    --resource-group $ResourceGroupName `
    --kind ComputerVision `
    --sku $Sku `
    --location $Location `
    --yes `
    --output none

Write-Host (Get-Date)"- Azure AI Vision account created" -ForegroundColor Green

# Get the endpoint
Write-Host (Get-Date)"- Retrieving endpoint..." -ForegroundColor Yellow
$endpoint = az cognitiveservices account show `
    --name $VisionAccountName `
    --resource-group $ResourceGroupName `
    --query "properties.endpoint" `
    --output tsv

Write-Host (Get-Date)"- Endpoint: $endpoint" -ForegroundColor Green

# Get the key
Write-Host (Get-Date)"- Retrieving access key..." -ForegroundColor Yellow
$keys = az cognitiveservices account keys list `
    --name $VisionAccountName `
    --resource-group $ResourceGroupName `
    --output json | ConvertFrom-Json

$key = $keys.key1
Write-Host (Get-Date)"- Access key retrieved" -ForegroundColor Green

# Update .env file
Write-Host (Get-Date)"- Updating .env file..." -ForegroundColor Yellow
$envPath = Join-Path $PSScriptRoot ".env"
$envContent = @"
# Azure AI Vision credentials
# Deployed on: $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Resource Group: $ResourceGroupName
# Account Name: $VisionAccountName

VISION_ENDPOINT=$endpoint
VISION_KEY=$key
"@

Set-Content -Path $envPath -Value $envContent
Write-Host (Get-Date)"- .env file updated" -ForegroundColor Green

# Summary
Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "`nResource Details:" -ForegroundColor White
Write-Host "  Resource Group:  $ResourceGroupName" -ForegroundColor Gray
Write-Host "  Account Name:    $VisionAccountName" -ForegroundColor Gray
Write-Host "  Location:        $Location" -ForegroundColor Gray
Write-Host "  SKU:             $Sku" -ForegroundColor Gray
Write-Host "  Endpoint:        $endpoint" -ForegroundColor Gray

Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "  1. Install Python dependencies:" -ForegroundColor White
Write-Host "     pip install -r requirements.txt" -ForegroundColor Gray
Write-Host "`n  2. Run the Dense Caption script:" -ForegroundColor White
Write-Host "     python dense_caption.py" -ForegroundColor Gray

Write-Host "`nTo delete all resources when done:" -ForegroundColor Yellow
Write-Host "     az group delete --name $ResourceGroupName --yes --no-wait" -ForegroundColor Gray
Write-Host ""
