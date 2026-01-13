# Invoice Processing with Azure AI - Setup Guide

## Prerequisites: Python Environment

- Python 3.10 or higher
- pip package manager
- python virtual enviroment

## Step 1: Run the setup_azure_resources.ps1

The PowerShell script `setup_azure_resources.ps1` automates the Azure resource provisioning:

- Creates a resource group and a timestamp-based naming suffix
- Provisions **Azure AI Document Intelligence** resource
- Provisions **Azure OpenAI** resource with gpt-5.1 deployment
- Provisions **Azure AI Search** service (Basic tier)
- Handles soft-deleted resource purging automatically
- Saves all configuration to `.env` file with proper syntax

**To run:**
```powershell
.\setup_azure_resources.ps1
```

**Output:** 
- `.env` file with all Azure endpoints and keys
- All resources ready to use

**Note:** The script reuses existing timestamps to maintain consistent naming across resources.

---

you can retrieve **Azure AI Document Intelligence** manually by:

```powershell
$tail= 'yyyyMMddHHmm' # <- replace with the effective used value

# how to get Azure AI Document Intelligence endpoint
az cognitiveservices account show --name doc-intel-invoice-rag-$tail --resource-group invoice-rag --query properties.endpoint --output tsv

# how to get Azure AI Document Intelligence key
az cognitiveservices account keys list --name doc-intel-invoice-rag-$tail --resource-group invoice-rag --query key1 --output tsv
```

You can retrieve **Azure AI Search** manually by:

```powershell
# Get the Azure AI Search does NOT return the endpoint
az search service show --name srch-invoice-rag-$tail --resource-group invoice-rag  --output tsv

# to build the endpoint manually
$searchEndpoint = "https://srch-invoice-rag-$tail.search.windows.net"

# Get the Azure AI Search admin key 
az search admin-key show --service-name srch-invoice-rag-$tail --resource-group invoice-rag --query primaryKey --output tsv
```

You can retrieve **Azure OpenAI** manually by:
```powershell
# Cognitive Services  endpoint
az cognitiveservices account show --name doc-intel-invoice-rag-$tail --resource-group invoice-rag --query properties.endpoint

# Cognitive Services  key
az cognitiveservices account keys list --name doc-intel-invoice-rag-$tail --resource-group invoice-rag --query key1 --output tsv
```

**Note**: The `setup_azure_resources.ps1` script deploys **gpt-5.1** by default.

## Step 2: Install Dependencies in virtual envirnment

```bash
pip install -r requirements.txt
```

## Step 3: check endpoints and keys to access to Azure Resources

Correct execution of **setup_azure_resources.ps1** should fill in the `.env` with all variables required to access to Azure resources:

```bash
# Azure AI Document Intelligence
DOC_INTEL_ENDPOINT=https://your-doc-intelligence.cognitiveservices.azure.com/
DOC_INTEL_KEY=your-key-here

# Azure AI Search
SEARCH_ENDPOINT=https://your-search-service.search.windows.net
SEARCH_KEY=your-admin-key-here
SEARCH_INDEX_NAME=invoices-index

# Azure OpenAI (for chatbot)
OPENAI_ENDPOINT=https://your-openai.openai.azure.com/
OPENAI_KEY=your-key-here
OPENAI_DEPLOYMENT=gpt-5.1-deployment
OPENAI_API_VERSION=2024-08-01-preview

# Project Configuration
INVOICES_FOLDER=invoices
MANIFEST_FILE=invoices/manifest_invoices.json
```

## Step 4: Prepare Your Invoice Files

Check if the invoice PDFs are in the `invoices` folder. <br>
in case the `invoices` folder is empty, generate the test invoices:

```bash
python generate_realistic_invoices.py
```

**Options:**
- Press **Enter** → Generate first 5 invoices (quick test)
- Type **'all'** → Generate all 120 invoices
- Type a **number** → Generate specific count

**Output:** `invoices/invoice_INV-2025-XXXX.pdf`

Ensure your invoice PDFs are in the `invoices/` folder and that `manifest_invoices.json` exists in the `invoices/` folder.

The manifest should have this structure:
```json
{
  "output_dir": "invoices",
  "num_expected": 120,
  "num_created": 120,
  "pdf_files": [
    "invoice_INV-2025-0001.pdf",
    "invoice_INV-2025-0002.pdf",
    ...
  ]
}
```

**generate_manifest.py**  is a utility script for regenerating the manifest file when needed, but it's not part of the standard workflow since **generate_realistic_invoices.py** handles manifest creation automatically.

You can run **generate_manifest.py** in three cases:

```bash
# Scenario 1: You manually added PDFs to invoices/ folder
python generate_manifest.py

# Scenario 2: manifest_invoices.json was deleted
python generate_manifest.py

# Scenario 3: You want to rebuild the manifest from current PDFs
python generate_manifest.py
```

## Step 5: Run the Extraction and Indexing

Execute the main script to:

- Extract invoice data from PDFs using Document Intelligence
- Create the Azure AI Search index
- Index the extracted invoices

```bash
python extract_and_index.py
```

## Step 6: Understanding the Workflow

### 1. Invoice Extraction

The script uses **Azure AI Document Intelligence** with the prebuilt invoice model to extract:
- Invoice ID, vendor, dates
- Line items (SKU, description, quantity, prices)
- Totals (subtotal, tax, shipping, total)

### 2. Index Creation

Creates an **Azure AI Search** index with:
- **Structured fields**: invoice_id, vendor, dates, currency, totals
- **Searchable content**: Full-text keyword search on content field
- **Filters and sorting**: Filterable and sortable fields for precise queries

### 3. Chatbot Q&A

Uses **Azure OpenAI** with direct API calls to create a RAG-based chatbot:

- **Search**: Queries Azure AI Search for relevant invoices
- **RAG pattern**: Retrieves relevant invoices then generates answers
- **Citations**: Includes invoice_id, vendor, and date in responses

## Testing the Chatbot

Run the chatbot interactively:

```bash
python chatbot.py
```

Example queries to test:

- "What was the total on invoice INV-2025-0001?"
- "Show me all invoices from Contoso Retail"
- "What invoices are from April 2025?"
- "Which vendor has the highest invoice?"

## Recommended Azure OpenAI Models

Based on this RAG use case, here are recommended models:

| Model       | Best For | Context | Cost-Efficiency |
|-------------|----------|---------|-----------------||
| **gpt-5.1** | Advanced reasoning, best quality (default in setup script) | 200K | High |
| **gpt-4o**  | Balanced performance, good for RAG | 128K | High |
| **gpt-4o-mini** | Fast responses, cost-effective | 128K | Very High |


---

`date: 13-01-2026` <br>