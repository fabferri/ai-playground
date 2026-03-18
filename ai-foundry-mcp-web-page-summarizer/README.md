# Web Page Summarization Using Azure AI Foundry and MCP Server on Azure Container Apps

## 1. Introduction

This repository presents an end-to-end implementation that combines **Azure AI Foundry**, the **Model Context Protocol (MCP)**, and **Azure Container Apps** into a single deployable solution. The purpose of the project is to demonstrate how an MCP server can expose AI-enabled tools over Streamable HTTP transport, invoke a model deployed in Azure AI Foundry, and make that capability available to MCP-compatible hosts through a standard JSON-RPC interface.

Within this architecture, each platform serves a distinct role:

| Platform | Role |
|----------|------|
| **Azure AI Foundry** | Managed model hosting, inference API, and AI services via the Foundry SDK |
| **Model Context Protocol (MCP)** | Open standard for AI clients and hosts to discover and call remote tools over HTTP (JSON-RPC 2.0) |
| **Azure Container Apps** | Serverless, auto-scaling container runtime with VNet integration and HTTPS ingress |

## 2. What You'll Build

**Use case: "Summarise a URL"**

The solution implements a practical scenario in which the contents of a public web page are summarised through an MCP tool backed by a model hosted in Azure AI Foundry. The deployment consists of two containerised applications that operate together:

1. **MCP Server** (`server.py`) — Exposes the `summarize_url(url)` tool at the `/mcp` endpoint. Retrieves and cleans web page content, then submits it to a Foundry-deployed model for summarisation.

2. **MCP Client** (`client.py`) — Provides a browser interface for submitting URLs. Forwards each request to the MCP server through JSON-RPC and renders the summary.

For detailed endpoint paths, operational characteristics, and web page analysis behaviour, see [Architecture Components](#5-architecture-components).

After deployment, any MCP-capable host, including GitHub Copilot in VS Code and Foundry Agent Service, can connect to `https://<your-app>.<region>.azurecontainerapps.io/mcp` and invoke `summarize_url`. This allows the same backend capability to be consumed either interactively through the client application or programmatically through the MCP protocol.

```Console
User (Azure VM in VNet) → Client ACA (internal, :8080) → MCP Server ACA (:8000/mcp) → Azure AI Foundry
```

## 3. Architecture Overview

The architecture implements an MCP-based AI service on Azure that combines managed inference, containerised application hosting, and network isolation into a single deployment model. The solution is designed to expose AI-enabled tools through a standards-based interface. MCP transport is provided through an HTTP endpoint at `/mcp` using JSON-RPC, which keeps host integration simple and standards-aligned. Application hosting is delegated to Azure Container Apps, which provides HTTPS ingress, managed infrastructure, and automatic scaling. Model interaction is handled through the Azure AI Foundry SDK.

The architecture uses virtual network integration with a delegated Azure Container Apps subnet and private endpoints to support controlled network access. Authentication is based on a User-Assigned Managed Identity, which eliminates embedded credentials while enabling Azure resource access, image pulls from Azure Container Registry, and connectivity to Foundry services. Client access is restricted to VNet-internal ingress (see [MCP Client Container](#52-mcp-client-container-clientpy) for the full access model), reinforcing the overall security model and limiting exposure of the application surface.

The architecture diagram is shown below:

[![1]][1]

Communication between the project components:

[![2]][2]

**Workflow**:
```
User on Azure VM → Opens http://<client-fqdn> → Submits URL →
Client sends MCP request → Server fetches content → 
Azure AI Foundry generates summary → Result displayed to user
```

**Security architecture considerations**

- **Network Isolation**: Client app is internal-only, accessible solely from VNet-connected VMs
- **No Public Credentials**: UAMI-based authentication — no embedded secrets
- **Private Connectivity**: Optional private endpoints for Foundry, Key Vault, Storage
- **VNet Rules**: Foundry account restricted to ACA subnet only
- **Principle of Least Privilege**: UAMI has only required permissions (AcrPull, Foundry access)

## 4. Repository Layout

| File        | Purpose  |
|-------------|----------|
| `server.py` | MCP server implementation (FastMCP) with `summarize_url` tool, health endpoints, Foundry integration |
| `client.py` | MCP client with web interface (FastAPI)
 for user interaction, MCP JSON-RPC client |
| `init.json` | ARM template for initialization resources: subscription name, resource group, location|
| `main.json` | ARM template deploying infrastructure only: VNet, ACA environment, UAMI, ACR, Foundry account, private endpoints, DNS |
| `parameters.json` | Parameters for infrastructure deployment (`main.json`) |
| `main-deploy.ps1` | PowerShell script to deploy infrastructure (`main.json`) |
| `container-apps.json` | ARM template deploying application layer: ACR pull role assignment + server/client container apps |
| `container-apps.parameters.json` | Parameters for application-layer deployment after images are pushed in ACR |
| `container-apps.ps1` | PowerShell script to deploy container apps (`container-apps.json`) |
| `arm-deploy.sh` | Deployment script (Bash) |
| `populate-container-apps-params.ps1` | Fills `container-apps.parameters.json` from infra deployment outputs and ACR metadata |
| `populate_env.ps1` | PowerShell script to extract ARM outputs and populate `.env` file |
| `populate_env.py`   | Python script to extract ARM outputs and populate `.env` file |
| `Dockerfile`        | Container image for MCP server (Python 3.11-slim, FastMCP, dependencies) |
| `Dockerfile.client` | Container image for MCP client web UI
 (Python 3.11-slim, FastAPI, dependencies) |
| `requirements.txt`  | Python dependencies for MCP server |
| `requirements-client.txt` | Python dependencies for MCP client |
| `troubleshooting.md` | Troubleshooting guide |
| `DEPLOYMENT_FIXES.md` | Deployment fixes and known issues |


## 5. Architecture Components

This solution deploys two containerized applications working together:

### 5.1. MCP Server Container (`server.py`)

The MCP server is a FastMCP-based application that exposes AI-powered tools through the Model Context Protocol. It listens on port 8000 and can be configured with either external (public HTTPS) or internal ingress depending on deployment requirements.

**Core Tool — `summarize_url`**

The server exposes a single MCP tool, `summarize_url(url)`, which performs the following operations:

1. Validates the submitted URL and verifies that it uses an accepted scheme.
2. Fetches the target web page over HTTP with configurable timeout and redirect handling.
3. Extracts the primary article content using `trafilatura`, stripping boilerplate elements such as navigation menus, footers, advertisements, and embedded scripts.
4. Truncates the cleaned text to a maximum of 50 KB to remain within model token limits.
5. Submits the processed content to a model deployed in Azure AI Foundry for summarisation.
6. Returns the AI-generated summary to the calling client through the MCP JSON-RPC interface.

**Endpoints**

| Path | Purpose |
|------|---------|
| `/mcp` | Primary MCP protocol endpoint (JSON-RPC 2.0 over Streamable HTTP) |
| `/health` | Lightweight liveness probe — returns `{"status": "ok"}` (HTTP 200) |
| `/healthz` | Deep readiness check — verifies Foundry connectivity. Returns `{"status": "ok", "foundry": "connected", "models_available": N, "model_deployment": "<name>"}` (HTTP 200) on success, or `{"status": "degraded", "foundry": "disconnected", "error": "<details>"}` (HTTP 503) on failure |

**Operational Characteristics**

- **Framework**: FastMCP (Python 3.11)
- **Configuration**: All runtime settings are supplied through environment variables (`.env` file or container environment)
- **Error handling**: Structured logging with descriptive error messages; returns HTTP 503 when the Foundry backend is unreachable
- **Authentication**: `DefaultAzureCredential` via UAMI (see [Architecture Overview](#3-architecture-overview) for identity and credential details)

#### 5.1.1. Web Page Analysis considerations

To improve summarization speed and reduce token usage, the server performs a content-cleaning step before sending text to the model:

- Fetches raw HTML from the target URL.
- Extracts the main readable content and removes boilerplate markup.
- Sends cleaner text to Foundry for summarization.

Why this is faster:

- Less noise means fewer tokens processed by the model.
- Smaller prompts reduce inference latency and cost.
- Cleaner context generally improves summary quality and consistency.

Known limits and trade-offs:

- JavaScript-heavy pages may still need headless rendering (Playwright/Puppeteer) when content is not present in server-side HTML.
- For speed on JavaScript-heavy pages, add a lightweight render step that uses Playwright to fetch the page and return the rendered HTML, then run the same extraction step on that HTML. Cache rendered results for a short TTL to avoid repeated rendering costs for the same URL.
- PDFs and image-based pages require dedicated text extraction/OCR for best results.
- If extraction fails for a page shape, the service falls back to raw HTML to preserve functionality.

### 5.2. MCP Client Container (`client.py`)

The MCP client is a FastAPI-based web application that provides a browser interface for submitting URLs to the MCP server and viewing the resulting AI-generated summaries. It listens on port 8080 and is deployed with internal-only ingress, meaning it is not exposed to the public internet.

**Access Model**

The client is accessible exclusively from Azure virtual machines attached to the same virtual network as the Container Apps environment. Service discovery within Azure Container Apps is used to locate the MCP server; the server address is supplied through the `MCP_SERVER_URL` environment variable, which is populated automatically during deployment.

**Request Flow**

When a user submits a URL through the web interface, the client constructs a JSON-RPC 2.0 request targeting the `summarize_url` tool on the MCP server. The server processes the request, invokes Azure AI Foundry for summarisation, and returns the result. The client then renders the summary in the browser.


**Endpoints**

| Path | Purpose |
|------|---------|
| `/` | Web interface for URL submission and summary display |
| `/health` | Lightweight liveness probe — returns `{"status": "ok", "service": "mcp-client"}` (HTTP 200) |
| `/healthz` | Readiness check — verifies MCP server connectivity. Returns `{"status": "ok", "service": "mcp-client", "mcp_server": "connected", "mcp_server_url": "<URL>"}` (HTTP 200) on success, or `{"status": "degraded", "service": "mcp-client", "mcp_server": "disconnected", "error": "<details>"}` (HTTP 503) on failure |

**Operational Characteristics**

- **Framework**: FastAPI (Python 3.11)
- **UI**: Responsive web interface with form validation, loading indicators, and user-friendly error messages
- **Protocol**: Implements MCP JSON-RPC client with structured error handling
- **Configuration**: Runtime settings supplied through environment variables (`MCP_SERVER_URL`)

## 6. Step-by-Step deployment

Use this exact order to avoid image and dependency errors:

1. Deploy infrastructure with `main.json` (no container apps).
2. Read ACR outputs from the infra deployment (`generatedAcrName`, `registryResourceId`).
3. Build and push images to that same ACR (`mcp-server:latest`, `mcp-client:latest`).
4. Deploy application layer with `container-apps.json`.
5. Read app URLs from the app deployment outputs.

### 6.1. STEP 1: Deploy infrastructure

Run the powershell script to deploy the infrastructure:
 
```powershell
.\main-deploy.ps1
```

Infrastructure deployment creates:
- Virtual Network (`aca-vnet`)
- **ACA Delegated Subnet**: Required for Azure Container Apps
  - Delegation: `Microsoft.App/environments`
- Service Endpoint: `Microsoft.CognitiveServices` (for Foundry access)
- **Private Endpoints Subnet**: Hosts all private endpoints
- Azure Container Apps Environment
- User-Assigned Managed Identity (UAMI)
- **ACR Pull Role Assignment**
   - Assigns `AcrPull` role to the User-Assigned Managed Identity
   - Enables passwordless image pull from ACR
- Foundry AI Services account with VNet integration
   - Account kind: `AIServices` (Foundry Tools account)
   - Public access: controlled by `enableCognitiveServicesPublicAccess`
   - VNet rules: ACA subnet is always configured in `networkAcls.virtualNetworkRules`
   - Firewall default action: `Allow` when `enableCognitiveServicesPublicAccess=true`, otherwise `Deny`
- Private Endpoints
   - Foundry account private endpoint
   - Key Vault
   - Storage Account
- DNS zones (with VNet links):
   - `privatelink.azurecr.io`
   - `privatelink.cognitiveservices.azure.com`
   - `privatelink.vaultcore.azure.net`
   - `privatelink.blob.core.windows.net`


**Key Configuration Parameters** in `main.json`

| Flag | Type | Default | Allowed Values | Purpose |
|------|------|---------|----------------|---------|
| `internalEnvironment` | bool | `false` | `true`, `false` | Makes ACA environment internal when `true` |
| `enablePrivateEndpoints` | bool | `true` | `true`, `false` | Creates private endpoints for supported services |
| `createDnsZones` | bool | `true` | `true`, `false` | Creates and links private DNS zones |
| `enableAIPublicNetworkAccess` | bool | `true` | `true`, `false` | Controls AI Hub/Project public access |
| `enableACRPublicNetworkAccess` | bool | `true` | `true`, `false` | Controls ACR public access |
| `enableCognitiveServicesPublicAccess` | bool | `true` | `true`, `false` | Controls Cognitive Services public access and ACL default action |

**ACR configuration notes**:
- In **parameters.json** the **registryResourceId** can be left **empty**. When empty, `main.json` **automatically generates** a deterministic ACR name based on the resource group using: `acr{uniqueString(subscription().id, resourceGroup().id)}`
- The template outputs include: `generatedAcrName`, `registryResourceId`
- Resolve the ACR login server from `registryResourceId` with: `az acr show --ids <registryResourceId> --query loginServer -o tsv`
- If you prefer to use your own pre-existing ACR, provide `registryResourceId`


### 6.2. STEP 2: collect Fondry project endpoint, model and then update the value in .env file

The file **.env** contains the foundry endpoints, ai model and MCP server URL:
```bash
PROJECT_ENDPOINT="AZURE_FOUNDRY_PROJECT_ENDPOINT"
MODEL_DEPLOYMENT_NAME="NAME_OF_AI_MODEL"
MCP_SERVER_URL="http://localhost:8000/mcp"
```

Run the following commands to fill up the value in **.env** file:
```powershell
# assign the correct name to the resource group variable
$rgName='RESOURCE_GROUP_NAME'

# List all deployments in a resource group
az deployment group list --resource-group $rgName --query "[].name" -o tsv

# Get the latest deployment name (results are returned in reverse chronological order)
az deployment group list --resource-group $rgName --query "[0].name" -o tsv

# List with timestamps for context
az deployment group list --resource-group $rgName --query "[].{name:name, timestamp:properties.timestamp, state:properties.provisioningState}" -o table

# Get the deployment name that contains the Foundry project
az deployment group list --resource-group $rgName --query "[?properties.outputs.aiProjectName != null] | [0].name" -o tsv

# This filters deployments to only those that have aiProjectName in their outputs, then returns the first match. 
$deploymentName=az deployment group list --resource-group $rgName --query "[?properties.outputs.foundryAccountEndpoint != null] | [0].name" -o tsv

# script to fill up the value in .env file
.\populate_env.ps1 -ResourceGroup $rgName -DeploymentName $deploymentName
```

As an alternative, variable values in the **.env** file can be populated using a Python script::

```powershell
python .\populate_env.py --resource-group <RESOURCE_GROUP_NAME> --deployment-name <DEPLOYMENT_NAME>
```

NOTE: python script **populate_env.py** does not accept the powershell variables $rgName and  $deploymentName but only string.

### 6.3. STEP 3 (optional): Local testing

This step is not andatory but it is a good practice to test the MCP server and client locally before deploying to Azure container apps.

Creation of the python virtual enviroments for the MCP server and client:

```bash
# 1. Create virtual environment for server
python -m venv venv-server
.\venv-server\Scripts\Activate.ps1
python.exe -m pip install --upgrade pip
pip install -r requirements.txt
deactivate

# 2. Create virtual environment for client
python -m venv venv-client
.\venv-client\Scripts\Activate.ps1
python.exe -m pip install --upgrade pip
pip install -r requirements-client.txt
deactivate

# 3. Check the correct values of oundry project endpoint and model name in .env file
PROJECT_ENDPOINT="https://<FOUNDRY_PROJECT_NAME>.services.ai.azure.com"
MODEL_DEPLOYMENT_NAME="gpt-5.4"


# 4. Run the server
.\venv-server\Scripts\Activate.ps1
python server.py
```
The logs at termina inform uvicorn is running: "Uvicorn running on http://0.0.0.0:8000"

In another terminal session, check the MCP server endpoints:

```powershell
# Basic health check
curl http://localhost:8000/health

# Foundry connectivity check
curl http://localhost:8000/healthz

$init = Invoke-WebRequest -Uri "http://localhost:8000/mcp" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{ "Accept" = "application/json, text/event-stream" } `
  -Body '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"curl-test","version":"1.0"}},"id":1}'

$sessionId = $init.Headers["Mcp-Session-Id"] | Select-Object -First 1
Write-Host "Session ID: $sessionId"
Write-Host "Response: $($init.Content)"

Invoke-WebRequest -Uri "http://localhost:8000/mcp" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{ "Accept" = "application/json, text/event-stream"; "Mcp-Session-Id" = $sessionId } `
  -Body '{"jsonrpc":"2.0","method":"notifications/initialized"}'

$result = Invoke-WebRequest -Uri "http://localhost:8000/mcp" `
  -Method POST `
  -ContentType "application/json" `
  -Headers @{ "Accept" = "application/json, text/event-stream"; "Mcp-Session-Id" = $sessionId } `
  -Body '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"summarize_url","arguments":{"url":"https://learn.microsoft.com/azure/vpn-gateway/design"}},"id":2}'

$result.Content
```

### 6.4. STEP 4 (optional): Run the client locally

Activate the python virtual session for the client:
```
.\venv-client\Scripts\Activate.ps1
python client.py
```

The log in the terminal shows: "Uvicorn running on http://0.0.0.0:8080"

A direct way to test the application:
```powershell
# curl the client on port 8080, which handles the MCP handshake internally:
# This returns HTML with the summary. 
# The client's POST / endpoint accepts form-encoded data and manages the full MCP session lifecycle for you.
curl -X POST http://localhost:8080/ -d "url=https://learn.microsoft.com/azure/vpn-gateway/design"
```

Open a web browser and connect to the client:

```powershell
Start-Process "http://localhost:8080/"
```

### 6.5. STEP 5: Build and Push the MCP server Container Images to the ACR

The ACR task is recommended for building container images directly in Azure Container Registry and does not require Docker to be installed locally.

Executing ACR Tasks requires the following prerequisites:

- Azure CLI installed and authenticated (az login)
- Sufficient permissions to push images to the target Azure Container Registry
- Source files (for example, Dockerfile, server.py, requirements.txt) available in the current working directory

```bash
# Get your ACR name from acr list
$rgName= 'NAME_RESOURCE_GROUP_NAME'
$acrName = (az acr list --resource-group $rgName --query "[0].name" -o tsv)
echo "ACR Name: $acrName"

# Build and push the server image to the ACR
az acr build --registry $acrName --image mcp-server:latest --file Dockerfile .
```

The command streams to the terminal the build logs in real-time. Build typically takes 10-15 minutes depending on dependencies. Watch for "Successfully tagged" and "Successfully pushed" messages.

**Verify the image was pushed**:
```powershell
# List all repositories (images) in the registry
az acr repository list --name $acrName --output table
   
# Show tags for the specific image
az acr repository show-tags --name $acrName --repository mcp-server --output table

# the build actually pushed by checking recent runs
az acr repository show --name $acrName --repository mcp-server

# Optional: show image details (digest, size, created time)
az acr repository show --name $acrName --image mcp-server:latest

# USE THIS COMMAND ONLY IF REQUIRED - Delete a specific image tag
# az acr repository delete --name $acrName --image mcp-server:latest --yes

# USE THIS COMMAND ONLY IF REQUIRED - Delete entire repository (all tags)
# az acr repository delete --name $acrName --repository mcp-server --yes
```

**What Happens During the Build**:

1. **Upload Phase**:
   - ACR Tasks creates a temporary build context
   - Uploads source files (Dockerfile, code, requirements) to Azure Storage
   - Only files not excluded by `.dockerignore` are uploaded
   - Upload size is displayed (typically a few MB)

2. **Build Phase**:
   - Azure spins up a dedicated build agent
   - Executes each Dockerfile instruction (FROM, COPY, RUN, etc.)
   - Installs Python dependencies from `requirements.txt`
   - Progress is streamed to your terminal in real-time

3. **Push Phase**:
   - Built image is automatically tagged with your specified name
   - Pushed to your ACR registry
   - Image layers are deduplicated for efficiency

4. **Cleanup**:
   - Build context and temporary files are automatically removed
   - Build agent is deallocated

<ins>**Advanced Options (NOT used in this deployment and reported for reference only)**</ins>:

```powershell
# Build with build arguments
az acr build --registry $acrName --image mcp-server:v1.0 --build-arg PYTHON_VERSION=3.11 .

# Build from a specific Git branch
az acr build `
  --registry $acrName `
  --image mcp-server:latest `
  https://github.com/yourorg/yourrepo.git#main:path/to/dockerfile

# Build with no cache (force rebuild)
az acr build --registry $acrName --image mcp-server:latest --no-cache .

# Build on a specific platform
az acr build --registry $acrName --image mcp-server:latest --platform linux/amd64 .
```

### 6.5. STEP 5: Build and Push the MCP Client Container Images to the ACR

Build in Azure and push the client image to the ACR using the same approach:

```powershell
az acr build --registry $acrName --image mcp-client:latest -f Dockerfile.client .

# verifies the images
az acr repository list --name $acrName --output table

# check the tag associated with the images
az acr repository list --name $acrName -o tsv | ForEach-Object { az acr repository show-tags --name $acrName --repository $_ -o tsv } 

```

**Troubleshooting**:

| Issue | Solution |
|-------|----------|
| **Access denied** | Verify you have `AcrPush` or `Contributor` role on the ACR: `az role assignment list --scope <acr-resource-id> --assignee $(az account show --query user.name -o tsv)` |
| **Upload timeout** | Check network connectivity, reduce source files with `.dockerignore` |
| **Build fails on RUN** | Check Dockerfile syntax, verify base image is accessible |
| **Out of memory** | Reduce dependencies or use multi-stage build |
| **Image not found after build** | Verify registry name is correct, check for typos in image name |

**Cost Optimization**:
- ACR Tasks charges per build minute (typically $0.10-0.30 per build)
- Use `.dockerignore` to minimize upload size
- Leverage layer caching for faster rebuilds

**Advantages of the ACR tasks**:
- No Docker installation required
- Faster builds with cloud resources (multi-core VMs)
- Built-in layer caching across builds
- No local disk space consumed
- Automatic image push to registry
- Build logs are archived for troubleshooting


### 6.6. STEP 6: Deploy the Azure Container Apps for Server and Client (container-apps.json)

The deployment process follows a staged approach: infrastructure is provisioned first, and container applications are deployed only after the container images are available in Azure Container Registry (ACR).
After successfully building and pushing both container images `mcp-server:latest` and `mcp-client:latest` to ACR, the application layer can be deployed using the `container-apps.json` ARM template.

In the projects includes two scripts:

- `populate-container-apps-params.ps1` resolves `foundryproject`, and `modelDeploymentName` from infra outputs and populate the values in `container-apps.parameters.json`
- `container-apps.ps1` executes two actions in sequence: it recalls the helper script `populate-container-apps-params.ps1` and then deploys the `container-apps.json`

Run the powershell script:

```bash
.\container-apps.ps1
```

The `container-apps.json` template creates:

1. **MCP Server Container App** (`mcp-foundry-app`) — Pulls `mcp-server:latest` from ACR. See [Architecture Components](#51-mcp-server-container-serverpy) for endpoints, configuration, and operational details.

2. **MCP Client Container App** (`mcp-client-app`) — Pulls `mcp-client:latest` from ACR. See [Architecture Components](#52-mcp-client-container-clientpy) for endpoints, configuration, and operational details.


### 6.7. Deployment Outputs

After successful deployment, the template provides:

| Output                   | Description                       |
|--------------------------|-----------------------------------|
| `foundryAccountEndpoint` | Azure AI Foundry account endpoint |
| `foundryAccountName`     | Azure AI Foundry account name |
| `acaSubnetId`            | ACA subnet resource ID |
| `privateEndpointSubnetId` | Private endpoints subnet resource ID |
| `generatedAcrName`       | Deterministic ACR name generated by template |
| `registryResourceId`     | Effective ACR resource ID used |
| `aiHubName`              | AI Hub name |
| `aiProjectName`          | AI Project name |
| `aiHubId`                | AI Hub resource ID |
| `aiProjectId`            | AI Project resource ID |
| `keyVaultName`           | Key Vault name (if created by template) |
| `storageAccountName`     | Storage account name (if created by template) |
| `modelDeploymentName`    | Model deployment name |
| `modelDeploymentId`      | Model deployment resource ID |

Endpoints
| Output | Description | Example (with `internalEnvironment: true`) |
| `containerAppFqdn` | MCP Server fully qualified domain name | `mcp-foundry-app.internal.<aca-env-hash>.<region>.azurecontainerapps.io` |
| `containerAppUrl` | Full MCP endpoint URL (with `/mcp` path) | `https://mcp-foundry-app.internal.<aca-env-hash>.<region>.azurecontainerapps.io/mcp` |
| `clientAppFqdn` | MCP Client fully qualified domain name | `mcp-client-app.<aca-env-hash>.<region>.azurecontainerapps.io` |
| `clientAppUrl` | Client web interface URL | `https://mcp-client-app.<aca-env-hash>.<region>.azurecontainerapps.io` |

**Note on `internalEnvironment`**

When `internalEnvironment` is `true` (the default in `container-apps.parameters.json`), two independent mechanisms control network access:

 | Setting | Scope | Effect |
 |---------|-------|--------|
 | ACA environment `internal: true` | Environment-wide | No app in this environment is reachable from the public internet, regardless of its own ingress setting. All traffic must originate from within the VNet. |
 | App ingress `external: false` | Per-app | The app is reachable **only by other apps inside the same ACA environment** (not by VMs or other VNet resources). The FQDN includes `.internal.` (e.g. `mcp-foundry-app.internal.…`). |
 | App ingress `external: true` | Per-app | The app is reachable **from anywhere inside the VNet** (including VMs in `subnet1`). The FQDN does **not** include `.internal.` (e.g. `mcp-client-app.…`). |

In this deployment:

- **MCP Server** — ingress `external: [not(internalEnvironment)]` → `false`. Only the client app (same ACA environment) can reach it.
- **MCP Client** — ingress `external: true` (hardcoded). VMs in `subnet1` can reach it through the browser, but it remains hidden from the public internet because the environment is internal.

Container apps which have **.internal.** in their FQDN are only reachable from other container apps in the same ACA environment. A VM in the VNet cannot access them, even though the DNS resolves. The ACA load balancer rejects the request with a 404 because the source is not an app within the environment.

 **Access Matrix**:

| Source                    | Client (external: true)  | Server (external: false, .internal.) |
| ------------------------- | -------------------------| ------------------------------------ |
| VM in VNet                | Yes                      | No (404)                             |
| Client app (same ACA env) | Yes                      | Yes                                  |
| Public internet           | No (internal env)        | No                                   |


### 6.8. STEP 7: Verification deployment of container apps  

After deployment, verify DNS resolution, container app status, health endpoints, and log output. See [Post-Deployment: Testing Health Endpoints](#7-post-deployment-testing-health-endpoints) for the full verification procedure.

If you encounter issues after deployment — such as image pull errors, missing environment variables, client-to-server connectivity failures, or health probe failures — see [Troubleshooting](#8-troubleshooting) for detailed diagnosis steps and solutions.

---

### 6.9. STEP 8: Access the MCP Client

The client uses internal-only ingress (see [MCP Client Container](#52-mcp-client-container-clientpy) for details). Access it from a VM in the same VNet:

1. **Deploy or use an existing Azure VM** in the same VNet as the Container Apps
   ```powershell
   az vm create `
     --resource-group $rgName `
     --name test-vm `
     --image Win2022Datacenter `
     --vnet-name aca-vnet `
     --subnet subnet1 `
     --admin-username azureuser `
     --size Standard_B2s_v2
     # You will be prompted to enter a password for the admin user
     # Note: subnet1 is used instead of aca-subnet (which is delegated to Container Apps)
   ```

2. **Connect to the VM**:
   ```powershell
   # Via RDP (Remote Desktop)
   mstsc /v:<vm-public-ip>
   ```

3. **Access the web interface** from within the Azure VM
Collect the `clientAppFQDN` by command:

```powershell
$clientAppFQDN= (az containerapp show --name mcp-client-app --resource-group $rgName --query "properties.configuration.ingress.fqdn" -o tsv) 
write-host $clientAppFQDN
```
The value `$clientAppFQDN` is used in next step in the Azure VM to open the web app web.
 
In the Azure VM run the powershell:

```powershell
# test access to the client web app page
Invoke-WebRequest -Uri "http://<clientAppFQDN>" -UseBasicParsing
```

```powershell
# Get the client FQDN <clientAppFQDN> from previous step. 
# The command open in browser (Edge/Chrome) with the web app:
Start-Process "http://<clientAppFQDN>"
```

Using the Web Interface in Azure VM:

- **Open the client URL** in your browser
- **Enter a URL** in the form (e.g., `https://learn.microsoft.com/en-us/azure/vpn-gateway/design`)
- **Click "Summarize"**
- **View the AI-generated summary** displayed on the page


## 7. Post-Deployment: Testing Health Endpoints

Collect the name and FQDN of the container apps:

```powershell
# list of container applications
az containerapp list --resource-group $rgName --query "[].{name:name, fqdn:properties.configuration.ingress.fqdn}" -o table

Name             Fqdn
---------------  ----------------------------------------------------------------------------------
mcp-foundry-app  mcp-foundry-app.internal.<environment-unique-id>.swedencentral.azurecontainerapps.io
mcp-client-app   mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io


# Client app FQDN
az containerapp show --name mcp-client-app --resource-group $rgName --query "properties.configuration.ingress.fqdn" -o tsv

# Server app FQDN
az containerapp show --name mcp-foundry-app --resource-group $rgName --query "properties.configuration.ingress.fqdn" -o tsv
```

Verifing that Azure VM can reach the client:

```console
# verify DNS resolution
# This should return a private IP (e.g., 10.x.x.x). 
# If it returns a public IP or fails, the private DNS zone link is missing.
nslookup mcp-client-app.<environment-unique-id>.<region>.azurecontainerapps.io
Server:  UnKnown
Address:  168.63.129.16

Non-authoritative answer:
Name:    mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io
Address:  10.10.0.24
```

To verify the server is healthy, you have two options:

   - Option1: Use the client's **/healthz** — it checks server connectivity for you:
   ```powershell
   curl https://mcp-client-app.mangoglacier-9b00afc8.swedencentral.azurecontainerapps.io/healthz
   ```
  - Option2: Check container logs via Azure CLI (see [Troubleshooting](#8-troubleshooting) for log commands and additional diagnostics)

Example of command output:

```console
curl -k https://mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io/health
{"status":"ok","service":"mcp-client"}

curl -v https://mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io/health
* Host mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io:443 was resolved.
* IPv6: (none)
* IPv4: 10.10.0.24
*   Trying 10.10.0.24:443...
* ALPN: curl offers h2,http/1.1
* TLSv1.3 (OUT), TLS handshake, Client hello (1):
* SSL Trust Anchors:
*   Native: Windows System Stores ROOT+CA
* TLSv1.3 (IN), TLS handshake, Server hello (2):
* TLSv1.3 (IN), TLS handshake, Unknown (8):
* TLSv1.3 (IN), TLS handshake, Certificate (11):
* TLSv1.3 (IN), TLS handshake, CERT verify (15):
* TLSv1.3 (IN), TLS handshake, Finished (20):
* TLSv1.3 (OUT), TLS handshake, Finished (20):
* SSL connection using TLSv1.3 / TLS_AES_256_GCM_SHA384 / [blank] / UNDEF
* ALPN: server accepted h2
* Server certificate:
*   subject: C=US; ST=WA; L=Redmond; O=Microsoft Corporation; CN=<environment-unique-id>.azurecontainerapps.io
*   start date: Mar 11 15:55:09 2026 GMT
*   expire date: Aug 25 23:59:59 2026 GMT
*   issuer: C=US; O=Microsoft Corporation; CN=Microsoft Azure RSA TLS Issuing CA 04
*   Certificate level 0: Public key type ? (2048/112 Bits/secBits), signed using sha384WithRSAEncryption
*   Certificate level 1: Public key type ? (4096/128 Bits/secBits), signed using sha384WithRSAEncryption
*   subjectAltName: "mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io" matches cert's "*.<environment-unique-id>.swedencentral.azurecontainerapps.io"
* OpenSSL verify result: 0
* SSL certificate verified via OpenSSL.
* Established connection to mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io (10.10.0.24 port 443) from 10.10.0.132 port 60047
* using HTTP/2
* [HTTP/2] [1] OPENED stream for https://mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io/health
* [HTTP/2] [1] [:method: GET]
* [HTTP/2] [1] [:scheme: https]
* [HTTP/2] [1] [:authority: mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io]
* [HTTP/2] [1] [:path: /health]
* [HTTP/2] [1] [user-agent: curl/8.19.0]
* [HTTP/2] [1] [accept: */*]
> GET /health HTTP/2
> Host: mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io
> User-Agent: curl/8.19.0
> Accept: */*
>
* Request completely sent off
< HTTP/2 200
< date: Mon, 16 Mar 2026 08:09:32 GMT
< server: uvicorn
< content-length: 38
< content-type: application/json
<
{"status":"ok","service":"mcp-client"}* Connection #0 to host mcp-client-app.<environment-unique-id>.swedencentral.azurecontainerapps.io:443 left intact
```

## 8. Troubleshooting

Common issues and solutions:

### 8.1. Client Can't Reach Server

**Symptoms**: Client reports "Failed to connect to MCP server"

**Checks**:
```bash
# Verify both apps are in same ACA environment
az containerapp list -g $rgName --query "[].{name:name,env:properties.environmentId}" -o table

# Check client environment variable
az containerapp show -n mcp-client-app -g $rgName `
  --query "properties.template.containers[0].env[?name=='MCP_SERVER_URL'].value"

# View server logs
az containerapp logs show --name mcp-foundry-app -g $rgName --follow

# View client logs
az containerapp logs show --name mcp-client-app -g $rgName --follow
```

**Solutions**:

- Ensure `MCP_SERVER_URL` is set correctly in client
- Verify server is running and healthy (`/health` endpoint)
- Check ACA environment is properly configured

### 8.2. Server Can't Reach Foundry

**Symptoms**: `/healthz` returns 503, logs show "Failed to connect to Foundry"

**Checks**:
```powershell
# Verify server environment variables (PROJECT_ENDPOINT, MODEL_DEPLOYMENT_NAME)
az containerapp show -n mcp-foundry-app -g $rgName --query "properties.template.containers[0].env"

# foundry accounts list in the resource group
az cognitiveservices account list -g $rgName --query "[].{name:name, kind:kind, location:location}" -o table

Name             Kind        Location
---------------  ----------  -------------
foundry-ai-acct  AIServices  swedencentral

# Check VNet rules on Foundry account
az cognitiveservices account show -n foundry-ai-acct -g $rgName --query "properties.networkAcls"

# get the list of UAMI account
az identity list -g $rgName --query "[].{name:name, principalId:principalId, clientId:clientId, location:location}" -o table

# Verify UAMI has permissions assigned through RBAC
az role assignment list --assignee <uami-principal-id> --all

# Check service endpoints on ACA subnet
az network vnet subnet show --vnet-name aca-vnet --name aca-subnet -g $rgName --query "serviceEndpoints"
```

**Solutions**:
- Add `Microsoft.CognitiveServices` service endpoint to ACA subnet
- Verify VNet rules allow ACA subnet in Foundry account
- Confirm UAMI has proper role assignment on Foundry
- Check private endpoint is connected (if using PE)

### 8.3. Container Image Pull Failures

**Symptoms**: Container app shows "ImagePullBackOff" or "ErrImagePull"

**Checks**:
```bash
# list of the User Assigned Managed Idenentity (UAMI)
az identity list -g $rgName --query "[].{name:name, principalId:principalId, clientId:clientId, location:location}" -o table

# collect the PricipalId for the User Assigned Managed Idenentity (UAMI)
$uamiPrincipalId=(az identity list -g $rgName --query "[].{principalId:principalId}" -o tsv) 

# 
$acrId=(az acr show --name $acrName --query "id" -o tsv)

# Verify UAMI has AcrPull role
az role assignment list --scope $acrId --assignee $uamiPrincipalId

# Check ACR registry configuration
az containerapp show -n mcp-foundry-app -g $rgName --query "properties.configuration.registries"
```

**Solutions**:
- Ensure UAMI has `AcrPull` role on the ACR
- Verify `registryResourceId` parameter is correct in ARM template
- Check ACR allows access (not behind restrictive firewall)
- Confirm image exists in ACR: `az acr repository list -n <acrName>`

#### 8.3.1. Deployment Failures

**Common ARM template errors**:

| Error | Cause | Solution |
|-------|-------|----------|
| Subnet already in use | Pre-existing delegation | Use different subnet or remove delegation |
| DNS zone already exists | Zone conflict | Set `createDnsZones: false` |
| Invalid resource ID | Wrong ACR ID format | Use full resource ID from `az acr show` |
| Quota exceeded | Region limits | Choose different region or request quota increase |

### 8.4. Cleanup

Remove all deployed resources:

```bash
# Delete resource group (removes all resources)
az group delete --name $rgName --yes --no-wait

# Verify deletion
az group show --name $rgName
```

**Note**: Delete operation is asynchronous. Resources will be removed in the background.

#### 8.5. Management
```bash
# Scale server replicas
az containerapp update --name mcp-foundry-app -g $rgName --min-replicas 2 --max-replicas 5

# Update server image
az containerapp update --name mcp-foundry-app -g $rgName --image <yourACR>.azurecr.io/mcp-server:v2

# Restart container app
az containerapp revision restart --name mcp-foundry-app -g $rgName
```

---

## 9. ANNEX: check availability of API version for the cognitive service model

```powershell
$location= 'swedencentral'
az cognitiveservices model list --location $location --query "[?kind=='OpenAI'].{Name:model.name, Version:model.version, Format:model.format}" --output table
```

## 10. ANNEX: toggle Cognitive Services public access and firewall default action

```powershell
# Purpose: Enable public network access on the Azure Cognitive Services account
az resource update `
  --resource-group $rgName `
  --name foundry-ai-acct `
  --resource-type Microsoft.CognitiveServices/accounts `
  --set properties.publicNetworkAccess=Enabled

# Purpose: Verify public network access is enabled
az resource show `
  --resource-group $rgName `
  --name foundry-ai-acct `
  --resource-type Microsoft.CognitiveServices/accounts `
  --query "properties.publicNetworkAccess" `
  --output tsv

# Purpose: Allow traffic by default at firewall level (network ACL default action)
az resource update `
  --resource-group $rgName `
  --name foundry-ai-acct `
  --resource-type Microsoft.CognitiveServices/accounts `
  --set properties.networkAcls.defaultAction=Allow

# Purpose: Verify default firewall action is set to Allow
az resource show `
  --resource-group $rgName `
  --name foundry-ai-acct `
  --resource-type Microsoft.CognitiveServices/accounts `
  --query "properties.networkAcls.defaultAction" `
  --output tsv
```

## 11. ANNEX: check and update Cognitive Services account SKU

```powershell
# Purpose: Check current account SKU
az resource show `
  --resource-group $rgName `
  --name foundry-ai-acct `
  --resource-type Microsoft.CognitiveServices/accounts `
  --query "sku" `
  --output json

# Purpose: Attempt to upgrade account SKU (example)
az resource update `
  --resource-group $rgName `
  --name foundry-ai-acct `
  --resource-type Microsoft.CognitiveServices/accounts `
  --set sku.name=S1 sku.capacity=1
```

Validity for `gpt-5.4` in `swedencentral`:

- The command syntax is valid Azure CLI.
- For `Microsoft.CognitiveServices/accounts` with `kind=AIServices` in `swedencentral`, available account SKU is `S0`.
- `S1` is not available there, so the update to `sku.name=S1` is expected to fail.
- `gpt-5.4` deployment itself is valid in `swedencentral`; keep account SKU at `S0` and use deployment SKU/settings for model throughput.

Optional check:

```powershell
$location= 'swedencentral'
# Purpose: List valid account SKUs for AIServices in the target region
az cognitiveservices account list-skus `
  --kind AIServices `
  --location $location `
  --output table
```

## 12. ANNEX:  Build Locally and Push to ACR (not used in current deployment)

Build locally required docker installed in your host.

Build the image on your local machine, then upload to ACR:

```bash
# 1. Build image locally
docker build -t mcp-server:local .

# 2. Authenticate with ACR
az acr login --name $acrName

# 3. Tag for ACR
docker tag mcp-server:local <acrName>.azurecr.io/mcp-server:latest

# 4. Push to ACR
docker push <acrName>.azurecr.io/mcp-server:latest

# build and push the the client to the ACR
docker build -f Dockerfile.client -t mcp-client:local .
az acr login --name <acrName>
docker tag mcp-client:local <acrName>.azurecr.io/mcp-client:latest
docker push <acrName>.azurecr.io/mcp-client:latest
```
---

## <a name="license"></a>License

This project is licensed under the MIT License - See [LICENSE](../LICENSE) file for details.


- `Tag: Azure container Apps, MCP` <br>
- `version1.0` <br>
- `date: 18-03-2026`

<!--Image References-->

[1]: ./media/architecture-diagram.png "network diagram"
[2]: ./media/communication-flows.png "communication flows"

<!--Link References-->