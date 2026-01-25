# Azure AI Foundry Agent - Expense Assistant

## Overview

This project demonstrates how to build an **AI-based corporate expense assistant** using an <ins>Azure AI Foundry Agent</ins>. The agent helps employees navigate expense policies, answer reimbursement questions, and submit expense claims through a conversational interface.

What this project does:

- **Answers expense policy questions** - Employees can ask about meal limits, travel allowances, approval requirements, and other policy details
- **Processes expense claims** - Collects claim information (email, description, amount) through natural conversation
- **Generates claim files** - Creates downloadable expense claim documents using the agent's code interpreter capability
- **Demonstrates Azure AI Foundry patterns** - Shows infrastructure deployment, agent creation, and chat interaction

### Key Features

| Feature                | Description |
|------------------------|-------------|
| **File Search**        | Agent searches uploaded policy documents to provide accurate answers |
| **Code Interpreter**   | Generates expense claim files that users can download |
| **Conversational UI**  | Interactive terminal chat for natural language interaction |
| **Two Implementation Options** | Choose between SDK (simpler) or REST API (more control) |

### Use Case

A typical conversation flow:
1. User asks: *"What's the maximum I can claim for meals?"*
2. Agent responds with policy details from the uploaded documents
3. User says: *"I'd like to submit a claim for lunch"*
1. Agent asks for email alias: *"frank@contoso.com"*
1. Agent asks for description, and amount through conversation: *"Breakfast in NY cost me $20"*
1. Agent generates and provides a downloadable claim file

---

## Quick Start

### Step 1: Deploy Infrastructure

Run the PowerShell script to create all required Azure resources:

```powershell
.\deploy-infrastructure.ps1
```

This script creates:

- Resource Group
- AI Services Account with project management enabled
- Foundry Project
- Model Deployment (GPT-4.1)

### Step 2: Interact with the Agent

After infrastructure deployment, you can interact with the expense agent using **two alternatives**:

| Option    | File           | Description |
|-----------|----------------|-------------|
| **SDK**   | `chat_sdk.py`  | Uses the Azure AI Projects SDK - cleaner code, automatic polling |
| **REST**  | `chat_rest.py` | Uses direct REST API calls - more control, educational |

#### Option A: Using the SDK (Recommended)

```powershell
pip install -r requirements.txt
python chat_sdk.py
```

#### Option B: Using REST API

```powershell
pip install -r requirements.txt
python chat_rest.py
```

Both scripts provide an interactive chat interface where you can:

- Ask questions about expense policies
- Submit expense claims
- Download generated claim files

---

## Architecture

An **Azure AI Services account** (also called **Azure Cognitive Services account**) is the top-level Azure resource that provides access to AI capabilities.

In the Azure AI Foundry hierarchy:
```console
Azure Subscription
  └── Resource Group 
        └── AI Services Account
              ├── Model Deployments (gpt-4.1, etc.)
              └── Foundry Projects
                    └── Agents (expense-agent)
                          └── Threads & Messages

```
The account is created by **deploy-infrastructure.ps1** using:

- **kind = "AIServices"** - Full AI Services (includes OpenAI, Vision, Speech, etc.)
- **allowProjectManagement = true** - Enables Foundry projects for agent development
Think of it as the container that holds your AI capabilities, while the project is where you organize your specific <ins>agents</ins> and <ins>workflows</ins>.

### Agent Components

The expense-agent uses three key components that extend its capabilities beyond a basic chat model:

```console
Agent (expense-agent)
├── Vector Store ──────► File Search Tool ──────► Answers policy questions
│   └── Expenses_Policy.docx (embedded)
│
└── Code Interpreter Tool ──────► Generates downloadable files
```

#### Vector Store

A **Vector Store** is a specialized database that stores document embeddings (numerical representations of text). When you upload a file like `Expenses_Policy.docx`:

1. The document is chunked into smaller sections
2. Each chunk is converted to a vector embedding
3. Embeddings are stored in the vector store for semantic search

This enables the agent to find relevant information even when the user's question doesn't exactly match the document text.

#### File Search Tool

The **File Search** tool (`file_search`) allows the agent to:

- Search through uploaded documents using semantic similarity
- Retrieve relevant passages to answer user questions
- Cite sources from the knowledge base

When enabled, the agent automatically searches the attached vector store(s) when answering questions, grounding responses in your actual policy documents rather than relying solely on its training data.

#### Code Interpreter Tool

The **Code Interpreter** tool (`code_interpreter`) gives the agent the ability to:

- Write and execute Python code in a sandboxed environment
- Perform calculations and data analysis
- Generate files (text, CSV, images, etc.) that users can download. In our project generate text files like expense claim
- Process uploaded files programmatically

In this project, the code interpreter is used to create expense claim text files that users can download after submitting their claim details.


#### How They Work Together

| User Request               | Agent Action | Tool Used |
|----------------------------|--------------|-----------|
| "What's the meal limit?"   | Searches policy document | File Search |
| "Submit a $45 lunch claim" | Collects details, generates claim file | Code Interpreter |
| "Can I expense a flight to NYC?" | Searches travel policy section | File Search |

---

## Project Files

| File           | Description |
|----------------|-------------|
| `deploy-infrastructure.ps1` | PowerShell script to deploy all Azure resources |
| `chat_sdk.py`  | Interactive chat using Azure AI Projects SDK |
| `chat_rest.py` | Interactive chat using REST API calls |
| `expense_sdk.py`  | Agent deployment script using Azure SDK |
| `expense_rest.py` | Agent deployment script using REST API calls |
| `Expenses_Policy.docx` | Corporate expense policy document (uploaded to agent's vector store) |
| `requirements.txt` | Python package dependencies |
| `.env` | Environment variables (endpoint, agent name, model deployment) |

---

## Python Scripts Comparison

### Scripts Overview

| Script              | Purpose              | API Method | Interactive |
|---------------------|----------------------|------------|-------------|
| **expense_rest.py** | Deploy expense agent | REST API   | No  |
| **expense_sdk.py**  | Deploy expense agent | Azure SDK  | No  |
| **chat_rest.py**    | Chat with agent      | REST API   | Yes |
| **chat_sdk.py**     | Chat with agent      | Azure SDK  | Yes |

### Deployment Scripts Actions

| Step | **expense_rest.py**      | **expense_sdk.py**   |
|------|--------------------------|----------------------|
| 1    | List existing agents     | List existing agents |
| 2    | Create or get agent      | Delete & recreate agent |
| 3    | Upload policy file       | Upload policy file |
| 4    | Create/get vector store  | Create/get vector store |
| 5    | Add file to vector store | Add file to vector store |
| 6    | Update agent with tools  | Update agent with tools |
| 7    | Test agent               | Test agent  |

### Chat Scripts Actions

| Action             | chat_rest.py | chat_sdk.py |
|--------------------|--------------|-------------|
| Find agent by name | ✓ | ✓ |
| Create thread      | ✓ | ✓ |
| Send messages      | ✓ | ✓ |
| Process responses  | ✓ | ✓ |
| Interactive loop   | ✓ | ✓ |

### REST vs SDK Implementation Differences

| Aspect             | REST Scripts | SDK Scripts |
|--------------------|--------------|-------------|
| **Authentication** | `AzureCliCredential` + manual token | `DefaultAzureCredential` (auto) |
| **API Version**    | Manual (`2025-05-01`) | SDK-managed internally |
| **HTTP Handling**  | Manual `requests` calls | SDK methods |
| **Dependencies**   | `requests`, `azure-identity` | `azure-ai-projects`, `azure-ai-agents` |
| **Error Handling** | HTTP status codes | SDK exceptions |

---

## Configuration

Before running the scripts, configure the `.env` file with your Azure AI Foundry project details:

```dotenv
AZURE_EXISTING_AIPROJECT_ENDPOINT="https://<your-account>.services.ai.azure.com/api/projects/<your-project>"
AZURE_EXISTING_AGENT_ID="expense-agent"
AZURE_MODEL_DEPLOYMENT="gpt-4.1"
AZURE_API_VERSION="2025-05-01"
```

> **Note**: The `deploy-infrastructure.ps1` script outputs the endpoint URL after deployment. Update `.env` accordingly.

---

## Prerequisites

1. **Azure CLI installed** - [Install Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
2. **Python 3.9+** with pip
3. **Login to Azure**:
   ```bash
   az login
   ```

4. **Set your subscription** (optional):
   ```bash
   az account set --subscription "<your-subscription-id>"
   ```

---

## Deployment 

The `deploy-infrastructure.ps1` script automates all these steps:

- Step 1: Check and purge soft-deleted AI Services account (if exists)
- Step 2: Create Resource Group
- Step 3: Create Azure AI Services Account (with allowProjectManagement enabled)
- Step 4: Verify account provisioning and allowProjectManagement
- Step 5: Create Foundry Project
- Step 6: Deploy Model (gpt-4.1)
- Step 7: Get Project Endpoint
- Step 8: Update .env file with project endpoint



### Create an AI Services account

Create an **AI Services account** with a custom domain (required for Foundry projects):

```powershell
az cognitiveservices account create `
        --name $AccountName `
        --resource-group $ResourceGroup `
        --kind "AIServices" `
        --sku "S0" `
        --location $Location `
        --custom-domain $AccountName
```

> The `--custom-domain` parameter sets a globally unique domain name and is required for Foundry projects. This also enables project management capabilities.


### Create a project

Create a project within the AI Services account. The project is required for agents to be visible in the Foundry portal. <br>

- **Agents are scoped to projects** - When you create an agent via the REST API or SDK, you target the project endpoint (/api/projects/$ProjectName/assistants), not the account directly
- **Portal organization** - The Azure AI Foundry portal organizes resources by project. Without a project, there's no container to display the agents


```powershell
az cognitiveservices account project create `
    --name $AccountName `
    --resource-group $ResourceGroup `
    --project-name $ProjectName `
    --location $Location
```


### Deploy a Model (e.g., GPT-4.1)

Deploy a model to the AI Services account. Model deployments are created at the **account level** and are automatically available to all projects within that account.

- Model deployments are at the account level - not the project level
- Projects inherit access - All projects under an account can use its model deployments

```console
AI Services Account 
├── Model Deployments (gpt-4.1, etc.) ← Created here
└── Foundry Project 
    └── Agents (expense-agent) ← Uses models from parent account
```

```powershell
az cognitiveservices account deployment create `
    --name $accountName `
    --resource-group $ResourceGroup `
    --deployment-name gpt-4.1 `
    --model-name gpt-4.1 `
    --model-version "2025-04-14" `
    --model-format OpenAI `
    --sku-capacity 10 `
    --sku-name GlobalStandard
```

```powershell
# List all model deployments in the account
az cognitiveservices account deployment list `
    --name $AccountName `
    --resource-group $ResourceGroup `
    --query "[].{name:name, model:properties.model.name, version:properties.model.version}" `
    -o table
```

> **Note**: The project will automatically have access to all model deployments created in its parent account $AccountName. When creating an agent in the project, reference the deployment name (e.g., `gpt-4.1`) in the `model` field.

---

## Clean Up Resources

Delete all resources when done:

```powershell
# List all agents and get their IDs
az rest --method GET `
    --url "https://$AccountName.services.ai.azure.com/api/projects/$ProjectName/assistants?api-version=2025-05-01" `
    --resource "https://ai.azure.com" `
    --query "data[].{id:id, name:name, model:model}"

# Store agent ID in a variable
$agentId = az rest --method GET `
    --url "https://$AccountName.services.ai.azure.com/api/projects/$ProjectName/assistants?api-version=2025-05-01" `
    --resource "https://ai.azure.com" `
    --query "data[?name=='expense-agent'].id" -o tsv

Write-Host "Agent ID: $agentId"

$endpoint = "https://$AccountName.services.ai.azure.com/api/projects/$ProjectName"

# delete the agent
az rest --method DELETE `
    --url "$endpoint/assistants/$agentId`?api-version=2025-05-01" `
    --resource "https://ai.azure.com"

# Delete model deployment
az cognitiveservices account deployment delete `
    --name $AccountName `
    --resource-group $ResourceGroup `
    --deployment-name gpt-4.1

# Delete the Foundry project (must be deleted before the account)
az cognitiveservices account project delete `
    --name $AccountName `
    --resource-group $ResourceGroup `
    --project-name $ProjectName

# Delete the AI Services account
az cognitiveservices account delete `
    --name $AccountName `
    --resource-group $ResourceGroup

# Delete the resource group (deletes everything)
az group delete --name $ResourceGroup --yes --no-wait
```

---

## Important: Agent Deletion and Recovery

>  **Azure AI Agents do NOT support soft delete.** When you delete an agent, it is **permanently deleted** and cannot be recovered.

### Deletion Behavior by Resource

| Resource            | Soft Delete | Recovery Options |
|---------------------|-------------|------------------|
| **Agents**          |  **No**     | Must redeploy from source code/IaC - gets new ID |
| **Threads**         |  **No**     | Unrecoverable (eDiscovery via Purview only) |
| **Files/Knowledge** |  **No**     | Must re-upload |
| **Azure AI Workspace** |  **Yes** | Recoverable during retention period |

---

## Reference
[Explore AI Agent development](https://microsoftlearning.github.io/mslearn-ai-agents/Instructions/01-agent-fundamentals.html)