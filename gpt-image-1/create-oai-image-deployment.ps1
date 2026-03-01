<#
.SYNOPSIS
    Provisions an Azure AI Foundry (AIServices) resource and deploys the
    gpt-image-1.5 model with GlobalStandard SKU.

.DESCRIPTION
    This script uses the Azure CLI to:
      1. Create a resource group (if it does not exist).
      2. Create an AIServices Cognitive Services account with retry logic
         for name conflicts.
      3. Deploy the gpt-image-1.5 model (version 2025-12-16).
      4. Optionally create a Foundry project linked to the account.
      5. Optionally update the local .env file with the endpoint, API key,
         and deployment name.

    Prerequisites:
      - Azure CLI installed and logged in (az login).
      - A subscription with access to gpt-image-1.5
        (request via aka.ms/oai/gptimage1.5access).

.NOTES
    Supported regions (GlobalStandard): westus3, eastus2, uaenorth,
    polandcentral, swedencentral.
#>

$resourceGroupName = 'rg-oai-images4'
$location = 'swedencentral'
$OpenAIAccountName = 'oai-images-test'
$DeploymentName = 'gpt-image-1.5'
$ModelName = 'gpt-image-1.5'
$ModelVersion = '2025-12-16'
$ModelFormat = 'OpenAI'
$SkuName = 'GlobalStandard'
$SkuCapacity = 1
$EnvFilePath = '.env'
$ResourceKind = 'AIServices'
$CreateFoundryProject = $false
$FoundryProjectName = 'foundry-images-prj'


$subscriptionId = az account show --query "id" --output tsv
Write-Host "Current Azure subscription ID: $subscriptionId" -ForegroundColor Green

function Set-VarInEnv {
    param(
        [Parameter(Mandatory = $true)][string]$Content,
        [Parameter(Mandatory = $true)][string]$Key,
        [Parameter(Mandatory = $true)][string]$Value
    )

    $escapedValue = $Value.Replace('"', '\"')
    $line = '{0}="{1}"' -f $Key, $escapedValue
    $pattern = '(?m)^\s*' + [regex]::Escape($Key) + '\s*=.*$'

    if ([string]::IsNullOrWhiteSpace($Content)) {
        return $line + [Environment]::NewLine
    }

    $regex = [regex]::new($pattern)
    if ($regex.IsMatch($Content)) {
        return $regex.Replace($Content, [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $line })
    }

    return $Content.TrimEnd() + [Environment]::NewLine + $line + [Environment]::NewLine
}


$null = az account show --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "You are not logged in to Azure CLI. Run: az login"
}

if ($SubscriptionId) {
    Write-Host "Setting subscription: $SubscriptionId" -ForegroundColor Cyan
    az account set --subscription $SubscriptionId
}

Write-Host "Ensuring resource group exists..." -ForegroundColor Cyan
az group create --name $resourceGroupName --location $location --output none

Write-Host "Checking Foundry resource..." -ForegroundColor Cyan
$accountExists = $true
az cognitiveservices account show --name $OpenAIAccountName --resource-group $resourceGroupName --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    $accountExists = $false
}

if (-not $accountExists) {
    $baseAccountName = ($OpenAIAccountName -replace '[^a-zA-Z0-9-]', '').ToLower()
    if ([string]::IsNullOrWhiteSpace($baseAccountName)) {
        throw "OpenAI account name is invalid after sanitization. Provide a valid value in `$OpenAIAccountName."
    }

    $created = $false
    $maxAttempts = 6

    for ($attempt = 1; $attempt -le $maxAttempts; $attempt++) {
        if ($attempt -eq 1) {
            $candidateName = $baseAccountName
        }
        else {
            $suffix = Get-Random -Minimum 1000 -Maximum 9999
            $trimmedBase = $baseAccountName
            if ($trimmedBase.Length -gt 48) {
                $trimmedBase = $trimmedBase.Substring(0, 48)
            }
            $candidateName = "{0}-{1}" -f $trimmedBase, $suffix
        }

        Write-Host "Creating Foundry resource: $candidateName" -ForegroundColor Cyan

        $createOutput = az cognitiveservices account create `
            --name $candidateName `
            --resource-group $resourceGroupName `
            --location $location `
            --kind $ResourceKind `
            --sku s0 `
            --custom-domain $candidateName `
            --allow-project-management `
            --output none 2>&1

        if ($LASTEXITCODE -eq 0) {
            $OpenAIAccountName = $candidateName
            $created = $true
            break
        }

        $createErrorText = ($createOutput | Out-String).Trim()
        if ($createErrorText -match 'CustomDomainInUse') {
            Write-Host "Account name/subdomain '$candidateName' unavailable. Retrying with a new name..." -ForegroundColor Yellow
            continue
        }

        throw "Foundry resource creation failed for '$candidateName'. Azure CLI error: $createErrorText"
    }

    if (-not $created) {
        throw "Failed to create Foundry resource after $maxAttempts attempts. Please set a different `$OpenAIAccountName and retry."
    }
}
else {
    Write-Host "Foundry resource already exists." -ForegroundColor Yellow
}

if ($CreateFoundryProject) {
    Write-Host "Ensuring Foundry project exists..." -ForegroundColor Cyan
    az cognitiveservices account project show `
        --name $OpenAIAccountName `
        --resource-group $resourceGroupName `
        --project-name $FoundryProjectName `
        --output none 2>$null

    if ($LASTEXITCODE -ne 0) {
        Write-Host "Creating Foundry project '$FoundryProjectName'..." -ForegroundColor Cyan
        az cognitiveservices account project create `
            --name $OpenAIAccountName `
            --resource-group $resourceGroupName `
            --project-name $FoundryProjectName `
            --location $location `
            --output none
    }
    else {
        Write-Host "Foundry project '$FoundryProjectName' already exists." -ForegroundColor Yellow
    }
}

Write-Host "Checking model deployment..." -ForegroundColor Cyan
$deploymentExists = $true
az cognitiveservices account deployment show `
    --name $OpenAIAccountName `
    --resource-group $resourceGroupName `
    --deployment-name $DeploymentName `
    --output none 2>$null
if ($LASTEXITCODE -ne 0) {
    $deploymentExists = $false
}

if (-not $deploymentExists) {
    Write-Host "Creating deployment '$DeploymentName' for model '$ModelName'..." -ForegroundColor Cyan
    $deploymentOutput = az cognitiveservices account deployment create `
        --name $OpenAIAccountName `
        --resource-group $resourceGroupName `
        --deployment-name $DeploymentName `
        --model-name $ModelName `
        --model-version $ModelVersion `
        --model-format $ModelFormat `
        --sku-name $SkuName `
        --sku-capacity $SkuCapacity `
        --output none 2>&1

    if ($LASTEXITCODE -ne 0) {
        $deploymentErrorText = ($deploymentOutput | Out-String).Trim()
        if ($deploymentErrorText -match 'DeploymentModelNotSupported') {
            throw "DeploymentModelNotSupported for model '$ModelName' version '$ModelVersion' in region '$location' with SKU '$SkuName'. Check that this subscription is approved for gpt-image-1.5 limited access and that the model/version is available in this region. Raw Azure CLI error: $deploymentErrorText"
        }

        throw "Azure deployment creation failed. Raw Azure CLI error: $deploymentErrorText"
    }
}
else {
    Write-Host "Deployment '$DeploymentName' already exists." -ForegroundColor Yellow
}

Write-Host "Retrieving endpoint and key..." -ForegroundColor Cyan
$endpoint = az cognitiveservices account show `
    --name $OpenAIAccountName `
    --resource-group $resourceGroupName `
    --query "properties.endpoint" `
    --output tsv

$apiKey = az cognitiveservices account keys list `
    --name $OpenAIAccountName `
    --resource-group $resourceGroupName `
    --query "key1" `
    --output tsv

Write-Host ""
Write-Host "Deployment ready." -ForegroundColor Green
Write-Host "Endpoint: $endpoint"
Write-Host "Deployment name: $DeploymentName"

$shouldUpdateEnv = Read-Host "Update .env automatically with endpoint, api key, and deployment? (y/N)"

if ($shouldUpdateEnv -match "^(?i:y|yes)$") {
    $resolvedEnvPath = Resolve-Path -Path $EnvFilePath -ErrorAction SilentlyContinue
    if (-not $resolvedEnvPath) {
        $fullPath = Join-Path -Path (Get-Location) -ChildPath $EnvFilePath
        New-Item -Path $fullPath -ItemType File -Force | Out-Null
        $resolvedEnvPath = Resolve-Path -Path $fullPath
    }

    $content = Get-Content -Path $resolvedEnvPath -Raw
    $content = Set-VarInEnv -Content $content -Key "AZURE_OPENAI_ENDPOINT" -Value $endpoint
    $content = Set-VarInEnv -Content $content -Key "AZURE_OPENAI_API_KEY" -Value $apiKey
    $content = Set-VarInEnv -Content $content -Key "AZURE_OPENAI_DEPLOYMENT" -Value $DeploymentName

    Set-Content -Path $resolvedEnvPath -Value $content -Encoding UTF8
    Write-Host ".env updated: $resolvedEnvPath" -ForegroundColor Green
}
else {
    Write-Host "Skipped .env update." -ForegroundColor Yellow
}

Write-Host "Done." -ForegroundColor Green
