<properties
pageTitle= 'Azure AI Foundry multi-model deployment and interactive chat'
description= "Azure AI Foundry multi-model deployment and interactive chat"
documentationcenter= "https://github.com/fabferri"
services="AI Foundry"
authors="fabferri"
editor="fabferri"/>

<tags
   ms.service="configuration-Example"
   ms.devlang="python"
   ms.topic="article"
   ms.tgt_pltfrm="AI Foundry"
   ms.workload="OpenAI Model"
   ms.date="09/11/2025"
   ms.author="fabferri" />

# Azure AI Foundry multi-model deployment and interactive chat

Python scripts for deploying Azure OpenAI models to Azure AI Foundry, managing capacity upgrades, and interacting with AI agents through an interactive chat interface.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Project Scripts](#project-scripts)
  - [01_client.py - Infrastructure Deployment](#01_clientpy---infrastructure-deployment)
  - [02_chat-with-agent.py - Interactive Chat](#02_chat-with-agentpy---interactive-chat)
  - [03_check-deployment.py - Deployment Verification](#03_check-deploymentpy---deployment-verification)
  - [04_upgrade-deployment.py - Capacity Management](#04_upgrade-deploymentpy---capacity-management)
- [Configuration File](#configuration-file)
- [Logging System](#logging-system)
- [Error Handling](#error-handling)
- [Model Configuration](#model-configuration)
- [Troubleshooting](#troubleshooting)

---

## Overview

This project provides an end-to-end solution for Azure AI Foundry deployment and usage, transforming the manual process into automated workflows.

### Architecture and Workflow

The project follows a modular workflow with four specialized scripts:

1. **Deployment Phase** (`01_client.py`): Creates Azure AI Foundry infrastructure (resource group, AI Services, project) and deploys selected OpenAI models using configuration from `init.json`. Generates `project_config.json` with deployment results.

2. **Interactive Chat** (`02_chat-with-agent.py`): Dynamically queries Azure for deployed models, presents interactive selection menu, and enables streaming conversations with AI agents.

3. **Deployment Verification** (`03_check-deployment.py`): Queries Azure Management API for deployment status, analyzes SKU configurations and rate limits, and provides optimization recommendations.

4. **Capacity Management** (`04_upgrade-deployment.py`): Discovers current deployments from Azure and enables interactive capacity/SKU upgrades (Standard 2x-10x, GlobalStandard) via Management API.

**Key Design Patterns:**
- **Dynamic Querying**: Scripts query Azure in real-time rather than relying solely on configuration files, ensuring they always work with current deployment state
- **Dual Logging**: Console displays user-friendly INFO messages while log files capture DEBUG-level technical details with timestamps
- **Modular Independence**: Each script can run independently after initial deployment

## Quick Start

### 1. Deploy Infrastructure and Models

Configure models in `01_client.py`:

```python
MODELS_TO_DEPLOY = ["gpt-4o", "gpt-4o-mini"]  # Deploy multiple models
# OR
MODELS_TO_DEPLOY = ["gpt-4o"]  # Deploy single model
```

Run deployment:

```bash
python 01_client.py
```

Generated: `project_config.json` and `deployment_log_YYYYMMDD_HHMMSS.log`

### 2. Chat with AI Agent

```bash
python 02_chat-with-agent.py
```

The script loads configuration from `init.json`, generates the endpoint URL dynamically, queries Azure for deployed models, and presents an interactive selection menu.

Generated: `chat_session_log_YYYYMMDD_HHMMSS.log`

### 3. Verify and Monitor Deployments

```bash
python 03_check-deployment.py
```

Shows deployment status, SKU configurations and rate limits.

### 4. Upgrade Model Capacity (Optional)

```bash
python 04_upgrade-deployment.py
```

Dynamically queries deployed models and offers interactive capacity upgrade options.

## Project Scripts

### 01_client.py - Infrastructure Deployment

**Purpose:** Creates Azure AI Foundry infrastructure and deploys OpenAI models.

**Configuration:**

```python
# In 01_client.py - modify these variables
subscription_name = 'Your-Subscription-Name'
resource_group_name = 'foundry-01'
foundry_resource_name = 'fabfoundryresource1'
foundry_project_name = 'fabfoundryproject1'
location = 'uksouth'

# Select models to deploy
MODELS_TO_DEPLOY = ["gpt-4o", "gpt-4o-mini"]  # Choose from available models
```

**Key Functions:**

- `get_subscription_id_by_name()`: Resolves subscription ID from display name
- `ensure_resource_group_exists()`: Creates resource groups with tagging
- `ensure_cognitive_services_resource_exists()`: Creates AI Services resource
- `deploy_multiple_models()`: Deploys selected models in parallel
- `save_project_config()`: Generates project_config.json

**Output:** `project_config.json`, `deployment_log_YYYYMMDD_HHMMSS.log`

### 02_chat-with-agent.py - Interactive Chat

**Purpose:** Interactive chat interface with Azure AI agents using deployed models.

**Key Functions:**

- `load_init_config()`: Loads configuration from `init.json`
- `generate_foundry_endpoint()`: Constructs endpoint URL dynamically
- `get_deployed_models_dynamically(project)`: Queries Azure for deployed models with regex-based model name extraction
- `select_model_interactive(models)`: Interactive model selection
- `create_ai_agent()`: Creates agent for selected model
- `stream_agent_response()`: Handles streaming responses

**Output:** `chat_session_log_YYYYMMDD_HHMMSS.log`

### 03_check-deployment.py - Deployment Verification

**Purpose:** Checks deployment status, monitors rate limits, and provides optimization recommendations.

**Key Functions:**

- `check_deployment_status()`: Queries and displays deployment information
- `analyze_deployment_config()`: Analyzes configuration and provides recommendations
- `get_usage_recommendations()`: Provides optimization tips

### 04_upgrade-deployment.py - Capacity Management

**Purpose:** Upgrades model capacity dynamically to handle higher throughput.

**Upgrade Options:**
- **Moderate** (Standard SKU, Capacity 2): 2x performance
- **Significant** (Standard SKU, Capacity 5): 5x performance
- **Premium** (GlobalStandard SKU, Capacity 2): Global load balancing
- **Custom**: User-specified SKU and capacity

**Key Functions:**

- `get_deployments_dynamically(project, config)`: Queries Azure for deployments
- `select_deployment_to_upgrade()`: Interactive deployment selection
- `upgrade_deployment_capacity()`: Performs capacity upgrade via Management API

**Output:** Updated deployment configuration in Azure

## Prerequisites

### Azure Requirements

- Active Azure subscription
- Appropriate permissions to create resources and resource groups
- Azure CLI installed and authenticated (`az login`)

### Python Environment

- Python 3.13 or later
- Virtual environment (recommended)

### Required Permissions

- `Contributor` role on the target subscription or resource group
- `Cognitive Services Contributor` for AI Services creation
- `Resource Group Contributor` for resource group management

## Installation

1. **Clone or download this project**

   ```bash
   git clone <repository-url>
   cd ai-foundry-01
   ```

2. **Create and activate virtual environment**

   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # or
   source .venv/bin/activate  # Linux/Mac
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Create init.json configuration file**

   Create `init.json` in the project root directory with your Azure configuration. See the [Configuration File](#configuration-file) section for detailed structure and field descriptions.

## Logging System

**Log Files Generated:**

- `deployment_log_YYYYMMDD_HHMMSS.log` (by 01_client.py)
- `chat_session_log_YYYYMMDD_HHMMSS.log` (by 02_chat-with-agent.py)

**Format:** `YYYYMMDD_HHMMSS` (e.g., 20240115_143022)

## Model Configuration

### Supported Models

The project supports the following OpenAI models with parametric configuration in `01_client.py`:

| Model | Version | Status | Notes |
|-------|---------|--------|-------|
| gpt-4o | 2024-11-20 | Available | Latest OpenAI model |
| gpt-4o-mini | 2024-07-18 | Available | Cost-effective option |
| gpt-4 | 0613 | Region-limited | Not available in UK South |
| gpt-35-turbo | 0125 | Available | Fast and reliable |

**Default SKU:** Standard with Capacity 1 (~20 requests/min, ~10K tokens/min). Use `04_upgrade-deployment.py` to scale capacity or upgrade to GlobalStandard SKU.

## Configuration File

### init.json

**Required by:** `01_client.py` (deployment) and `02_chat-with-agent.py` (chat interface)

**Purpose:** Stores Azure subscription and resource configuration used for deployment and dynamic model access.

**Structure:**

```json
{
  "subscription_name": "your-subscription-name",
  "resource_group_name": "your-resource-group",
  "foundry_resource_name": "your-foundry-resource",
  "foundry_project_name": "your-project-name",
  "location": "your-azure-region"
}
```

**Notes:**

- Must be created **before** running `01_client.py` or `02_chat-with-agent.py`
- File must be in the same directory as the scripts
- Validation errors will show detailed messages if fields are missing
- `02_chat-with-agent.py` can run independently with just `init.json` (no dependency on `project_config.json`)


**Note:** `01_client.py`, `02_chat-with-agent.py`, `03_check-deployment.py` and `04_upgrade-deployment.py` now use `init.json`

## Project Structure

```text
ai-foundry-chat-with-agent-01/
├── 01_client.py                          # Infrastructure deployment script
├── 02_chat-with-agent.py                 # Interactive AI agent chat interface
├── 03_check-deployment.py                # Deployment verification and monitoring
├── 04_upgrade-deployment.py              # Capacity upgrade tool
├── init.json                             # Initial configuration (required for all scripts)
├── project_config.json                   # Generated configuration (after 01_client.py)
├── requirements.txt                      # Python dependencies
├── README.md                             # This documentation
├── deployment_log_YYYYMMDD_HHMMSS.log    # Generated by 01_client.py
├── chat_session_log_YYYYMMDD_HHMMSS.log  # Generated by 02_chat-with-agent.py
└── .venv/                                # python Virtual environment (after installation)
```

## Error Handling

The project implements error handling across all scripts:

### Automatic Recovery

- **Soft-deleted Resource Restoration**: Automatically detects and recovers soft-deleted Azure resources
- **Retry Logic**: Built-in exponential backoff for transient Azure API failures
- **CTRL-C Handling**: Graceful exit with proper cleanup in 01_client.py and 04_upgrade-deployment.py


## Troubleshooting

### Common Issues

**1. Authentication Errors**

**Symptom:** `DefaultAzureCredential failed to retrieve a token`

**Solution:** Run `az login` and ensure you're authenticated to the correct tenant

**2. Permission Denied**

**Symptom:** `AuthorizationFailed` or insufficient permissions

**Solution:** Verify you have `Contributor` role on subscription or resource group

**3. init.json Not Found**

**Symptom:** `init.json not found in current directory` or `Failed to load init.json`

**Solution:** Create `init.json` with required fields (subscription_name, resource_group_name, foundry_resource_name, foundry_project_name, location) before running `01_client.py` or `02_chat-with-agent.py`

**4. project_config.json Not Found**

**Symptom:** `Configuration file not found` (when running `03_check-deployment.py` or `04_upgrade-deployment.py`)

**Solution:** Run `01_client.py` first to create the infrastructure and generate `project_config.json`

**5. No Models Available**

**Symptom:** "No deployed models found"

**Solution:** Run `01_client.py` to deploy models, or check deployment status with `03_check-deployment.py`

**6. Rate Limiting Errors**

**Symptom:** HTTP 429 "Too Many Requests"

**Solution:** Use `04_upgrade-deployment.py` to increase capacity, or implement request throttling

### Debug Steps

1. **Check Log Files**: Review timestamped log files for detailed error information
2. **Verify Configuration**: Check `init.json` has correct values for all required fields
3. **Check Deployments**: Run `03_check-deployment.py` to verify deployment status
4. **Azure Portal**: Review Azure Activity Log for detailed API error information

---

## Annex: Azure CLI Commands for Deployment Management

### Check Model Deployment Units and Capacity

These Azure CLI commands allow you to inspect deployment details, SKU types, and capacity units directly from the command line.

#### 1. List All Deployments in your Cognitive Services account

```azurecli-interactive
az cognitiveservices account deployment list `
  --name fabfoundryresource4 `
  --resource-group foundry-04 `
  --subscription "Hybrid-PM-Test-2"
```

#### 2. Get Specific Deployment Details

```azurecli-interactive
az cognitiveservices account deployment show `
  --name fabfoundryresource4 `
  --resource-group foundry-04 `
  --deployment-name fabfoundryresource4-gpt35-turbo-deployment `
  --subscription "Hybrid-PM-Test-2"
```

#### 3. List all deployments with model names, versions, SKUs, and capacity (Table Format)

```azurecli-interactive
az cognitiveservices account deployment list `
  --name fabfoundryresource4 `
  --resource-group foundry-04 `
  --subscription "Hybrid-PM-Test-2" `
  --query "[].{Name:name, Model:properties.model.name, Version:properties.model.version, SKU:sku.name, Capacity:sku.capacity}" `
  --output table
```

#### 4. Check Specific Deployment Capacity (Table Format)

```azurecli-interactive
az cognitiveservices account deployment show `
  --name fabfoundryresource4 `
  --resource-group foundry-04 `
  --deployment-name fabfoundryresource4-gpt35-turbo-deployment `
  --subscription "Hybrid-PM-Test-2" `
  --query "{DeploymentName:name, Model:properties.model.name, Version:properties.model.version, SKU:sku.name, Capacity:sku.capacity, ProvisioningState:properties.provisioningState}" `
  --output table
```

#### 5. Get Full Deployment Details (JSON Format)

Retrieve complete deployment configuration in JSON format:

```powershell
az cognitiveservices account deployment show `
  --name fabfoundryresource4 `
  --resource-group foundry-04 `
  --deployment-name fabfoundryresource4-gpt35-turbo-deployment `
  --subscription "Hybrid-PM-Test-2" `
  --output json
```

### Key Output Fields

When reviewing deployment information, focus on these key fields:

- **`sku.name`**: SKU type (Standard, GlobalStandard)
- **`sku.capacity`**: Number of capacity units
  - Standard: 1-10 units
  - GlobalStandard: 1-100 units
- **`properties.model.name`**: Model identifier (e.g., gpt-35-turbo, gpt-4o)
- **`properties.model.version`**: Model version (e.g., 0125, 2024-11-20)
- **`properties.provisioningState`**: Deployment status (Succeeded, Failed, Creating, Updating)

### Rate Limits by Capacity

Understanding capacity units helps estimate rate limits:

- **Standard SKU**: ~20 requests/min per unit, ~10K tokens/min per unit
- **GlobalStandard SKU**: Higher limits with global load balancing and better availability

### Common CLI Use Cases

**Check deployment status after upgrade:**

```powershell
az cognitiveservices account deployment show --name <resource-name> --resource-group <rg-name> --deployment-name <deployment-name> --query "properties.provisioningState"
```

**Compare capacities across all deployments:**

```powershell
az cognitiveservices account deployment list --name <resource-name> --resource-group <rg-name> --query "[].{Name:name, Capacity:sku.capacity}" --output table
```

**Monitor upgrade completion:**

```powershell
az cognitiveservices account deployment show --name <resource-name> --resource-group <rg-name> --deployment-name <deployment-name> --query "{State:properties.provisioningState, Capacity:sku.capacity}" --output table
```

## License

This project is licensed under the MIT License - See [LICENSE](../LICENSE) file for details.

`Tag: Azure AI Foundry models, OpenAI` <br>
`date: 09-11-2025`