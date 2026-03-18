# Populate local .env for server.py and client.py using Azure CLI
#
# Usage:
#   .\populate_env.ps1 -ResourceGroup <rg> -DeploymentName <deployment>
#
# Optional:
#   .\populate_env.ps1 -ResourceGroup <rg> -ParametersFile .\parameters.json -OutputPath .\.env
#   If -DeploymentName is omitted, the latest successful deployment in the resource group is used.
param(
    [Parameter(Mandatory = $true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory = $false)]
    [string]$DeploymentName = "",

    [Parameter(Mandatory = $false)]
    [string]$ParametersFile = ".\parameters.json",

    [Parameter(Mandatory = $false)]
    [string]$OutputPath = ".\.env"
)

$ErrorActionPreference = "Stop"

function Write-Info {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Cyan
}

function Write-Warn {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Ok {
    param([string]$Message)
    Write-Host "[OK]   $Message" -ForegroundColor Green
}



function Resolve-DeploymentName {
    param(
        [string]$Rg,
        [string]$RequestedName
    )

    if ($RequestedName) {
        return $RequestedName
    }

    # Prefer the latest successful deployment to avoid partial/failed runs.
    $latestSucceeded = az deployment group list --resource-group $Rg --query "sort_by([?properties.provisioningState=='Succeeded'], &properties.timestamp)[-1].name" --output tsv 2>$null
    if ($LASTEXITCODE -eq 0 -and $latestSucceeded) {
        return [string]$latestSucceeded
    }

    $latestAny = az deployment group list --resource-group $Rg --query "sort_by(@, &properties.timestamp)[-1].name" --output tsv 2>$null
    if ($LASTEXITCODE -eq 0 -and $latestAny) {
        Write-Warn "No successful deployment found. Using latest deployment '$latestAny'."
        return [string]$latestAny
    }

    throw "No deployments found in resource group '$Rg'."
}

function Get-DeploymentOutputValue {
    param(
        [string]$Rg,
        [string]$Name,
        [string]$OutputName
    )

    $value = az deployment group show --resource-group $Rg --name $Name --query "properties.outputs.$OutputName.value" --output tsv 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "az deployment group show failed for output '$OutputName' (RG='$Rg', deployment='$Name'): $value"
        return ""
    }

    return [string]$value
}

function Get-ParamValueFromFile {
    param(
        [string]$Path,
        [string]$ParamName,
        [string]$DefaultValue = ""
    )

    if (-not (Test-Path $Path)) {
        return $DefaultValue
    }

    try {
        $p = Get-Content -Raw -Path $Path | ConvertFrom-Json
        if ($p.parameters -and $p.parameters.$ParamName -and $p.parameters.$ParamName.value) {
            return [string]$p.parameters.$ParamName.value
        }
    }
    catch {
        Write-Warn "Could not parse parameters file '$Path': $($_.Exception.Message)"
    }

    return $DefaultValue
}

function Resolve-AiProjectEndpoint {
    param(
        [string]$Rg,
        [string]$CognitiveAccountName,
        [string]$FoundryEndpointFallback
    )

    # Query the Cognitive Services account to get AI Foundry API endpoint
    $accountInfo = az cognitiveservices account show --resource-group $Rg --name $CognitiveAccountName --query "{endpoint:properties.endpoint, endpoints:properties.endpoints}" --output json 2>$null | ConvertFrom-Json

    if (-not $accountInfo) {
        Write-Warn "Could not retrieve Cognitive Services account. Falling back to foundry account endpoint."
        return $FoundryEndpointFallback
    }

    # Look for AI Foundry API endpoint in the endpoints dictionary
    if ($accountInfo.endpoints -and $accountInfo.endpoints.'AI Foundry API') {
        $foundryEndpoint = [string]$accountInfo.endpoints.'AI Foundry API'
        if ($foundryEndpoint) {
            return $foundryEndpoint.TrimEnd('/')
        }
    }

    # Fallback: try Azure AI Model Inference API endpoint
    if ($accountInfo.endpoints -and $accountInfo.endpoints.'Azure AI Model Inference API') {
        $inferenceEndpoint = [string]$accountInfo.endpoints.'Azure AI Model Inference API'
        if ($inferenceEndpoint) {
            Write-Warn "AI Foundry API endpoint not found. Using Azure AI Model Inference API endpoint."
            return $inferenceEndpoint.TrimEnd('/')
        }
    }

    # Last resort: use main endpoint
    if ($accountInfo.endpoint) {
        Write-Warn "AI Foundry API endpoint not found. Using default Cognitive Services endpoint."
        return ([string]$accountInfo.endpoint).TrimEnd('/')
    }

    # Ultimate fallback
    Write-Warn "Could not determine AI Foundry endpoint. Using fallback value."
    return $FoundryEndpointFallback
}



try {
    az version | Out-Null
}
catch {
    throw "Azure CLI not found. Install Azure CLI first: https://learn.microsoft.com/cli/azure/install-azure-cli"
}
    
$resolvedDeploymentName = Resolve-DeploymentName -Rg $ResourceGroup -RequestedName $DeploymentName
Write-Info "Reading deployment outputs from '$resolvedDeploymentName' in '$ResourceGroup'..."
$aiProjectName = Get-DeploymentOutputValue -Rg $ResourceGroup -Name $resolvedDeploymentName -OutputName "aiProjectName"

if (-not $aiProjectName) {
    # Fallback to parameters file
    $aiProjectName = Get-ParamValueFromFile -Path $ParametersFile -ParamName "aiProjectName" -DefaultValue "ai-project"
    Write-Warn "aiProjectName output not found; using '$aiProjectName' from parameters/default."
}

$modelDeploymentName = Get-DeploymentOutputValue -Rg $ResourceGroup -Name $resolvedDeploymentName -OutputName "modelDeploymentName"
if (-not $modelDeploymentName) {
    $modelDeploymentName = Get-ParamValueFromFile -Path $ParametersFile -ParamName "modelDeploymentName" -DefaultValue "gpt-4.1-mini"
    Write-Warn "modelDeploymentName output not found; using '$modelDeploymentName' from parameters/default."
}

$foundryAccountName = Get-DeploymentOutputValue -Rg $ResourceGroup -Name $resolvedDeploymentName -OutputName "foundryAccountName"
if (-not $foundryAccountName) {
    $foundryAccountName = Get-ParamValueFromFile -Path $ParametersFile -ParamName "foundryAccountName" -DefaultValue "foundry-ai-acct"
    Write-Warn "foundryAccountName output not found; using '$foundryAccountName' from parameters/default."
}

$foundryAccountEndpoint = Get-DeploymentOutputValue -Rg $ResourceGroup -Name $resolvedDeploymentName -OutputName "foundryAccountEndpoint"

Write-Info "Resolving AI Foundry endpoint from Cognitive Services account '$foundryAccountName'..."
$projectEndpoint = Resolve-AiProjectEndpoint -Rg $ResourceGroup -CognitiveAccountName $foundryAccountName -FoundryEndpointFallback $foundryAccountEndpoint

if (-not $projectEndpoint) {
    throw "Could not resolve PROJECT_ENDPOINT."
}

# Local defaults for running both apps on the same machine.
$mcpServerUrl = "http://localhost:8000/mcp"

$envContent = @"
# Local runtime configuration (generated by populate_env.ps1)
PROJECT_ENDPOINT="$projectEndpoint"
MODEL_DEPLOYMENT_NAME="$modelDeploymentName"
MCP_SERVER_URL="$mcpServerUrl"
"@

Set-Content -Path $OutputPath -Value $envContent -Encoding UTF8

Write-Ok "Wrote .env file to '$OutputPath'"
Write-Host ""
Write-Host "Resolved values:" -ForegroundColor White
Write-Host "  DEPLOYMENT_NAME=$resolvedDeploymentName" -ForegroundColor Gray
Write-Host "  PROJECT_ENDPOINT=$projectEndpoint" -ForegroundColor Gray
Write-Host "  MODEL_DEPLOYMENT_NAME=$modelDeploymentName" -ForegroundColor Gray
Write-Host "  MCP_SERVER_URL=$mcpServerUrl" -ForegroundColor Gray
Write-Host ""
Write-Host "Run locally:" -ForegroundColor White
Write-Host "  1) python server.py" -ForegroundColor Gray
Write-Host "  2) python client.py" -ForegroundColor Gray
