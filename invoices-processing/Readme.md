# Invoice Processing with Azure AI

This project demonstrates business invoice processing using Azure AI services.

## Project Overview

This project builds an intelligent invoice processing system that:

1. **Extracts structured data** from invoice PDFs (totals, line items, vendor information)
2. **Enables natural language Q&A** - Answer questions like "What was the total on invoice X?" using conversational AI
3. **Provides accurate citations** - Ground all responses in source documents with precise references
4. **Minimizes custom code** - Leverage Azure managed services (**Azure Document Intelligence**, **Azure AI Search**, **Azure OpenAI**) to reduce development complexity

This approach combines Azure AI Document Intelligence's pre-trained invoice model with Azure OpenAI's Retrieval-Augmented Generation (RAG) pattern to create a solution for document-based question answering.

**Tech Stack:** Azure Document Intelligence + Azure AI Search + Azure OpenAI (GPT-5.1)

## How It Works

This solution implements a **Retrieval-Augmented Generation (RAG)** pattern to answer questions about invoices:

### User Query Flow

1. **Natural Language Input**
   - You ask a question: *"What was the total on invoice INV-2025-0001?"*
   - No special syntax required - just plain English

2. **Intelligent Retrieval**
   - Azure AI Search performs keyword search (BM25) across indexed invoices
   - Retrieves top 3 most relevant invoice documents
   - Matches on invoice ID, vendor name, dates, and content

3. **Context Augmentation**
   - Retrieved invoices are formatted into structured context
   - Includes: invoice_id, vendor, date, total, currency
   - Context is injected into the LLM prompt

4. **AI-Powered Generation**
   - Azure OpenAI (GPT-5.1) processes the question + context
   - Generates natural language answer grounded in retrieved data
   - Ensures response accuracy by referencing actual invoice details

5. **Cited Response**
   - You receive a clear answer with verifiable citations
   - Includes: invoice ID, vendor name, date, and amount
   - All information traceable back to source documents

### Example Session

```
You: What was the total on invoice INV-2025-0001?

Chatbot: The total on invoice INV-2025-0001 was EUR 12,027.40. 
         This invoice is from Contoso Retail, dated 2025-09-21.
```

**Why RAG?**

- **Accuracy**: Answers grounded in actual data, not hallucinations
- **Traceability**: Every response includes source citations
- **Fresh Data**: Works with current invoices without retraining models
- **Verifiable**: Users can validate answers against source documents

## Architecture Diagram

1. **Azure AI Document Intelligence**
   - Uses prebuilt invoice model
   - Extracts: invoice ID, vendor, dates, totals, line items
   - No custom parsing needed

2. **Azure AI Search**
   - Stores extracted invoice data
   - Keyword search (BM25)
   - Filters: vendor, date, amount, currency

3. **Azure OpenAI (RAG Pattern)**
   - Retrieves relevant invoices from search
   - Generates natural language answers
   - Provides citations with invoice details

```console
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA INGESTION PIPELINE                         │
└─────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │ Invoice PDFs │
    │ (invoices/)  │
    └──────┬───────┘
           │
           ▼
    ┌──────────────────────┐
    │  Azure AI Document   │
    │   Intelligence API   │
    │  (prebuilt-invoice)  │
    └──────────┬───────────┘
               │ Extract: invoice_id, vendor,
               │          dates, totals, content
               ▼
    ┌──────────────────────┐
    │  Extracted Data      │
    │  extraction_invoices │
    │     .jsonl           │
    └──────────┬───────────┘
               │
               │ Upload documents
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          AZURE AI SEARCH INDEX                          │
│  ┌────────────────────────────────────────────────────────────────┐     │
│  │ Fields: invoice_id, vendor, invoice_date, due_date,            │     │
│  │         currency, subtotal, tax, shipping, total, content      │     │
│  │                                                                │     │
│  │ Index Type: Keyword search (BM25)                              │     │
│  └────────────────────────────────────────────────────────────────┘     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     │
┌────────────────────────────────────┴─────────────────────────────────────┐
│                         RAG QUERY PIPELINE                               │
└──────────────────────────────────────────────────────────────────────────┘

    ┌──────────────┐
    │ User Question│
    └──────┬───────┘
           │ "What was the total on invoice INV-2025-0001?"
           ▼
    ┌──────────────────┐
    │   chatbot.py     │
    └──────┬───────────┘
           │
           │ 1. Search query
           ▼
    ┌──────────────────┐
    │ Azure AI Search  │◄───── Retrieve relevant invoices
    │  (keyword search)│
    └──────┬───────────┘
           │ Returns: top 3 matching invoices
           │
           │ 2. Build context with retrieved data
           ▼
    ┌──────────────────┐
    │  Azure OpenAI    │
    │   (gpt-5.1)      │
    └──────┬───────────┘
           │ Generate answer using invoice context
           ▼
    ┌──────────────────────────────┐
    │  Response with Citations     │
    │  • Answer                    │
    │  • Invoice ID                │
    │  • Vendor                    │
    │  • Date                      │
    └──────────────────────────────┘
```

## Project Structure

```
home/
├── .env                              # Azure credentials (create this)
├── requirements.txt                  # Python dependencies
│
├── Main Scripts
│   ├── generate_realistic_invoices.py   # Generate test PDFs
│   ├── extract_and_index.py             # Extract & index pipeline
│   ├── chatbot.py                       # RAG chatbot (main app)
│   └── query.py                         # Simple search viewer
│
├── Utility Scripts
│   ├── generate_manifest.py             # Create file manifest
│   ├── validate_manifest.py             # Validate manifest integrity
│   ├── debug_extraction.py              # Debug Document Intelligence
│   ├── list_indexes.py                  # List all search indexes and documents
│   └── reset_index.py                   # Delete and recreate search index
│
├── Configuration
│   ├── .env                             # Environment variables (Azure credentials)
│   └── setup_azure_resources.ps1        # Azure provisioning script
│
├── Documentation
│   ├── Readme.md                        # Original documentation
│   ├── readme1.md                       # This file (improved structure)
│   ├── Setup-guide.md                   # Detailed setup guide
│   └── troubleshooting1.md              # Debugging guide
│
└── Data
    └── invoices/
        ├── invoice_INV-2025-0001.pdf    # Generated PDFs
        ├── ...
        ├── manifest_invoices.json       # File listing
        └── extraction_invoices.jsonl    # Extracted data
```

## Generated Dataset (PDF Generation)

To generate realistic invoice PDFs for development and testing that Document Intelligence can extract:
```powershell
# Generate invoices for testing
python generate_realistic_invoices.py

# When prompted:
# - Press Enter for first 5 invoices
# - Type 'all' for all 120 invoices
# - Type a number for specific count
```

Each PDF contains:

- Professional invoice layout
- Header: Invoice ID, vendor, dates, terms
- Line items table: SKU, description, quantity, price
- Totals: Subtotal, tax, shipping, total
- Multi-currency support (USD, EUR, GBP, etc.)
- Files generated: `invoice_INV-2025-0001.pdf` through `invoice_INV-2025-0120.pdf`
- Location: `invoices/` folder

The PDFs are always generated the same way, not random.

### Manifest Structure
The manifest file `invoices/manifest_invoices.json` is created by the script `generate_manifest.py` <br>
The `invoices/manifest_invoices.json` file lists all PDF files:

```json
{
  "output_dir": "invoices",
  "num_expected": 120,
  "num_created": 120,
  "pdf_files": [
    "invoice_INV-2025-0001.pdf",
    "invoice_INV-2025-0002.pdf",
    // ... 118 more files
  ]
}
```

The manifest file `invoices/manifest_invoices.json` does NOT contain the full invoice data but it contains the full list of PDF files to be processed.

## Invoice Document Structure

Each generated invoice PDF contains business invoice data with the following components:

### Header Information

- **Vendor Details**: Company name and address
- **Invoice Number**: Format `INV-2025-XXXX`
- **Dates**: Invoice date and due date
- **Payment Terms**: Standard business terms
- **Bill To**: Customer information
- **Currency**: Multi-currency support (USD, EUR, GBP, etc.)

### Line Items Table

Structured table with columns:

- **SKU** - Product/service identifier
- **Description** - Item details
- **Qty** - Quantity ordered
- **Unit Price** - Price per unit
- **Line Total** - Extended amount (Qty × Unit Price)

### Financial Totals Section

- `Amount (Excl. Tax)`: Sum of all line items (before tax)
- `VAT Amount`: Region-appropriate tax calculation
- `Delivery`: Delivery charges
- `Total Amount Due`: Final amount due

### Citation Anchor

Each invoice includes an embedded anchor marker: `ANCHOR: invoice_id=<ID>` to facilitate precise citation generation in RAG responses.

### Data Variance for Real-World Testing

Two label variants are alternated across invoices to simulate real-world document diversity while remaining extraction-friendly:

- "Subtotal" vs "Amount (Excl. Tax)"
- "Tax (VAT)" vs "VAT Amount"
- "Shipping" vs "Delivery"
- "Total" vs "Total Amount Due"

## Solution Architecture

This solution is based on three Azure AI services to achieve intelligent document processing with minimal custom code:

### 1. Data Extraction (Using Pre-trained Model)

**Azure AI Document Intelligence - Invoice Prebuilt Model**

- Automatically extracts structured data from invoice PDFs:
  - Invoice metadata: InvoiceId, VendorName, InvoiceDate, DueDate
  - Financial totals: InvoiceTotal, SubTotal, TotalTax (as currency objects)
  - Line items: Description, Quantity, UnitPrice, Amount
  - Payment terms and addresses
- **Field Structure**: Currency fields use nested `valueCurrency` object:
  ```python
  # Accessing extracted totals
  total_field = fields["InvoiceTotal"]
  currency_data = total_field._data.get("valueCurrency", {})
  amount = currency_data.get("amount")  # e.g., 12027.4
  currency_code = currency_data.get("currencyCode")  # e.g., "EUR"
  ```
- **Benefit**: No custom parsing logic required - the pre-trained model handles varied invoice formats


### 2. Intelligent Search & Retrieval

**Azure AI Search - Keyword Search (BM25)**

- Index structure:
  - Invoice metadata fields (invoice_id, vendor, date, total) - filterable and facetable
  - Full-text searchable content field for keyword matching
  - Financial fields (subtotal, tax, shipping, total) for sorting and filtering
- **Search strategy**: BM25 keyword search for precise matching
- **Benefit**: Fast, accurate exact matches on invoice IDs, vendor names, and text content
- **Future enhancement**: Vector embeddings can be added for semantic search capabilities (see Next Steps section)

### 3. Natural Language Q&A with Citations

**Azure OpenAI - Retrieval-Augmented Generation (RAG)**

- Processes natural language questions like:
  - "What was the total on invoice X?"
  - "Which vendor had the highest invoice last quarter?"
  - "Show me all line items for SKU-12345"
- Grounds responses in retrieved documents from Azure AI Search
- Returns citations with:
  - Source invoice_id and document reference
  - Specific text snippets near anchor points
  - Clickable links to original PDF locations
- **Benefit**: Accurate, verifiable answers with full traceability to source documents

## Implementation Pipeline

### Quick Start

1. **Generate Invoice PDFs** (if not already generated):
   ```powershell
   python generate_realistic_invoices.py
   # Press Enter to generate first 5 invoices
   ```

2. **Extract and Index Invoices**:

   ```powershell
   python extract_and_index.py
   # Extracts invoice data using Document Intelligence SDK
   # Creates search index
   # Indexes all extracted invoices
   ```

**What it does:**
1. Reads invoices from `invoices/` folder
2. Calls Document Intelligence API to extract invoice data programmatically for each PDF
3. Extracts structured data (invoice ID, vendor, totals, etc.)
4. Creates Azure AI Search index
5. Uploads documents to Azure AI Search index

**Output:** 
- `invoices/extraction_invoices.jsonl` (extracted data)
- Azure AI Search index with all invoices

3. **Query Invoices**:
   ```powershell
   # Simple search without AI
   python query.py
   
   # RAG-powered chatbot (Interactive)
   python chatbot.py

   # Demo mode (single query)
   python chatbot.py --demo
   ```

### Detailed Steps

### Step 1: Document Extraction

```powershell
python extract_and_index.py
```

- **Action**: Calls Azure AI Document Intelligence (prebuilt-invoice model) on PDFs in `invoices/`
- **Output**: `invoices/extraction_invoices.jsonl` - One JSON record per invoice
- **Data captured**:
  - Header fields (invoice_id, vendor, dates, currency)
  - Financial totals (subtotal, tax, shipping, total)
  - Line items with descriptions and amounts
- **Processing**: Currently set to process first 5 invoices (modify line 50 for more)

Example extracted record:
```json
{
  "invoice_id": "INV-2025-0001",
  "vendor": "Contoso Retail",
  "invoice_date": "2025-09-21",
  "due_date": "2025-10-05",
  "currency": "EUR",
  "subtotal": 10002.0,
  "tax": 2000.4,
  "shipping": 25.0,
  "total": 12027.4,
  "content": "Invoice INV-2025-0001 from Contoso Retail dated 2025-09-21. Total: EUR 12027.40",
  "source_file": "invoice_INV-2025-0001.pdf"
}
```

After running `extract_and_index.py`, you'll have:

- **`extraction_invoices.jsonl`** - One JSON record per invoice with all extracted fields
  - Format: One JSON object per line
  - Fields: invoice_id, vendor, dates, currency, totals, content, source_file
  - Used for: Indexing in Azure AI Search

Example record:
```json
{"invoice_id": "INV-2025-0001", "vendor": "Contoso Retail", "invoice_date": "2025-09-21", "due_date": "2025-10-05", "currency": "EUR", "subtotal": 10002.0, "tax": 2000.4, "shipping": 25.0, "total": 12027.4, "content": "Invoice INV-2025-0001 from Contoso Retail dated 2025-09-21. Total: EUR 12027.40", "source_file": "invoice_INV-2025-0001.pdf"}
```

### Step 2: Create Search Index

The `extract_and_index.py` script automatically creates an **Azure AI Search index** with schema:

- **Key**: `invoice_id` (String, unique identifier)
- **Metadata fields**: 
  - `vendor` (Searchable, filterable)
  - `invoice_date`, `due_date` (Filterable, sortable)
  - `currency` (Filterable)
- **Financial fields**: 
  - `subtotal`, `tax`, `shipping`, `total` (Double, filterable, sortable)
- **Search field**: 
  - `content` - Full-text searchable content for keyword queries
- **Source field**: 
  - `source_file` - PDF filename reference

**Note**: The current implementation uses keyword search.

### Step 3: Populate Index

The indexing happens automatically in `extract_and_index.py`:

- Uploads extracted invoice documents to Azure AI Search
- Enables immediate querying via keyword search
- Supports filtering by vendor, date, total amount

### Step 4: Query & Chat

**Simple Search** (`query.py`):

```powershell
python query.py
```

- Lists all indexed invoices
- Shows invoice_id, vendor, date, total

**RAG Chatbot** (`chatbot.py`):
```powershell
# Interactive mode
python chatbot.py

# Demo mode (single query)
python chatbot.py --demo
```

- **Retrieval**: Searches Azure AI Search for relevant invoices
- **Generation**: Uses Azure OpenAI to compose natural language answers
- **Citations**: Includes invoice details in responses

Example queries in natural language:

- "What invoices do we have from Contoso?" or "Show me all invoices from Contoso"
- "Show me invoices from April 2025"
- "What's the total for invoice INV-2025-0001?"
- "Which vendor has the most recent invoice?"
- "Which vendor had the highest invoice?"
 

## Project Files

### Main Scripts

| Command                          | Description |
|----------------------------------|-----------------------------|
| `generate_realistic_invoices.py` | Generates properly formatted invoice PDFs using ReportLab |
| `extract_and_index.py` | Extracts invoice data using Document Intelligence and indexes in Azure AI Search |
| `chatbot.py` | RAG-powered chatbot for conversational invoice queries (main chatbot application) |
| `query.py` | Simple search script to list all indexed invoices (no AI) |

### Utility Scripts

| Command                | Description         |
|------------------------|---------------------|
| `generate_manifest.py` | Creates manifest file listing all invoice PDFs |
| `validate_manifest.py` | Validates consistency and integrity of manifest file |
| `debug_extraction.py`  | Debug tool to inspect Document Intelligence output |
| `list_indexes.py`      | Lists all search indexes and displays indexed documents with statistics |
| `reset_index.py`       | Deletes and optionally recreates search index for reset/cleanup |


### Configuration Files

| File                        | Description            |
|-----------------------------|------------------------|
| `setup_azure_resources.ps1` | PowerShell script to provision Azure resources |
| `requirements.txt`          | Python package dependencies |
| `openai-connection.json`    | OpenAI connection configuration for AI Foundry |

### Output Files

| File                                | Description           |
|-------------------------------------|-----------------------|
| `invoices/manifest_invoices.json`   | List of all PDF files |
| `invoices/extraction_invoices.jsonl`| Extracted invoice data (generated by extract_and_index.py) |
| `debug_output.json` | Raw Document Intelligence response (generated by debug_extraction.py) |



## Extraction Outputs

**Location**: `invoices/`

After running `extract_and_index.py`, you'll have:

- **`extraction_invoices.jsonl`** - One JSON record per invoice with all extracted fields
  - Format: One JSON object per line
  - Fields: invoice_id, vendor, dates, currency, totals, content, source_file
  - Used for: Indexing in Azure AI Search

Example record:
```json
{"invoice_id": "INV-2025-0001", "vendor": "Contoso Retail", "invoice_date": "2025-09-21", "due_date": "2025-10-05", "currency": "EUR", "subtotal": 10002.0, "tax": 2000.4, "shipping": 25.0, "total": 12027.4, "content": "Invoice INV-2025-0001 from Contoso Retail dated 2025-09-21. Total: EUR 12027.40", "source_file": "invoice_INV-2025-0001.pdf"}
```

## Troubleshooting: Index creation fails

**Solution:**
- Ensure Search service is Basic tier or higher
- Check admin key permissions
- Delete existing index if schema changed



## Key Benefits

### Production-Ready Design
- **Scalable**: Handles thousands of invoices with Azure's managed services
- **Maintainable**: Minimal custom code reduces technical debt
- **Reliable**: Pre-trained models provide consistent extraction quality
- **Traceable**: Every answer includes verifiable citations to source documents

### Cost-Effective
- Leverages managed Azure AI services (no infrastructure management)
- Pay-per-use pricing model scales with actual usage
- Reduces development time by using pre-built models

### Accurate & Verifiable
- Keyword search provides precise invoice matching
- RAG pattern grounds all responses in actual document content  
- Responses include invoice details for verification
- Document Intelligence ensures accurate data extraction

## Technical Implementation Details

### Architecture Decision: Direct API vs Agent Framework

The project uses **direct Azure OpenAI API calls** instead of an agent framework.

**Why no agent framework?**
This project uses **direct Azure OpenAI API calls** instead of agent frameworks, for the following reasons:

- Simpler implementation and debugging
- Fewer dependencies (just `openai` + `azure-search-documents`)
- Full control over conversation flow
- No complex authentication issues
- Easier to customize


**Implementation pattern:**
```python
# 1. Search Azure AI Search for relevant invoices
search_results = search_invoices(query, top=3)

# 2. Create context from search results
context = create_context_from_results(search_results)

# 3. Call OpenAI with context
response = client.chat.completions.create(
    model="gpt-5.1-deployment",
    messages=[
        {"role": "system", "content": "You are an invoice assistant..."},
        {"role": "user", "content": f"Context: {context}\n\nQuestion: {question}"}
    ],
    max_completion_tokens=500  # Note: GPT-5.1 uses max_completion_tokens
)
```

### Document Intelligence Field Structures

Understanding the nested field structure is critical for correct data extraction:

**Currency Fields:**
```python
{
  "type": "currency",
  "valueCurrency": {
    "amount": 12027.4,
    "currencyCode": "EUR",
    "currencySymbol": "EUR"
  },
  "content": "EUR 12,027.40",
  "confidence": 0.918
}

# Access pattern:
total_field = fields["InvoiceTotal"]
value_currency = total_field._data.get("valueCurrency", {})
amount = value_currency.get("amount")  # 12027.4
currency = value_currency.get("currencyCode")  # "EUR"
```

**Date Fields:**
```python
{
  "type": "date",
  "valueDate": "2025-09-21",
  "content": "2025-09-21",
  "confidence": 0.983
}

# Access pattern:
date_field = fields["InvoiceDate"]
date_value = date_field._data.get("valueDate")  # "2025-09-21"
```

**String Fields:**
```python
{
  "type": "string",
  "valueString": "INV-2025-0001",
  "content": "INV-2025-0001",
  "confidence": 0.983
}

# Access pattern:
id_field = fields["InvoiceId"]
invoice_id = id_field._data.get("valueString")  # "INV-2025-0001"
```

### Search Index Schema

```python
SearchIndex(
    name="invoices-index",
    fields=[
        SimpleField(name="invoice_id", type=SearchFieldDataType.String, key=True),
        SearchableField(name="vendor", type=SearchFieldDataType.String, filterable=True),
        SearchableField(name="invoice_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SearchableField(name="due_date", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="currency", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="subtotal", type=SearchFieldDataType.Double, filterable=True),
        SimpleField(name="tax", type=SearchFieldDataType.Double, filterable=True),
        SimpleField(name="shipping", type=SearchFieldDataType.Double, filterable=True),
        SimpleField(name="total", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SearchableField(name="content", type=SearchFieldDataType.String),
        SimpleField(name="source_file", type=SearchFieldDataType.String)
    ]
)
```

### RAG Implementation Pattern

```python
# 1. Search for relevant invoices
search_results = search_invoices(user_query, top=3)

# 2. Build context from results
context = create_context_from_results(search_results)

# 3. Generate answer with OpenAI
response = client.chat.completions.create(
    model="gpt-5.1-deployment",
    messages=[
        {"role": "system", "content": "You are an invoice assistant..."},
        {"role": "user", "content": f"Context: {context}\n\nQuestion: {user_query}"}
    ],
    max_completion_tokens=500  # GPT-5.1 uses this instead of max_tokens
)
```


### Why No PDF Parsing Library?

The project follows the **"Minimize custom code"** principle:

- **Document Intelligence handles everything:**
  - OCR (when needed)
  - Field extraction
  - Table parsing
  - Currency and date recognition
  - Multi-language support
- **No need for:** PyPDF2, pdfplumber, or custom regex parsing
- **Process:** Read PDF bytes → Send to API → Get structured JSON
- **Benefits:** 
  - More robust and accurate than custom parsing
  - Handles varied invoice formats automatically
  - Pre-trained model continuously improved by Microsoft
  - No maintenance of custom extraction logic

### Debugging Workflow

**Before batch processing, always debug with a single document:**

1. **Use debug_extraction.py to inspect API response:**
   ```powershell
   python debug_extraction.py
   ```
   - Shows all available fields
   - Displays field types and structures
   - Saves raw response to `debug_output.json`

2. **Verify field access patterns work correctly**

3. **Test with one document before processing batch**

### GPT-5.1 API Differences

Important: GPT-5.1 model uses different parameters than GPT-4:

```python
# Wrong - causes "unsupported_parameter" error
response = client.chat.completions.create(
    model="gpt-5.1-deployment",
    messages=messages,
    max_tokens=500  # Not supported in GPT-5.1
)

# Correct
response = client.chat.completions.create(
    model="gpt-5.1-deployment",
    messages=messages,
    max_completion_tokens=500  # Use this instead
)
```

### Key Learnings

1. **PDF formatting matters** - Document Intelligence expects specific layouts:
   - Clear field labels ("Invoice Number:", "Total:")
   - Professional table structure
   - Formatted currency values

2. **Field access is nested** - Always use `._data.get("valueCurrency", {})` for currency amounts

3. **Debug first** - Inspect one document completely before batch processing

4. **Direct API > Agent framework** - For this use case, simpler is better

5. **Index schema is immutable** - Delete and recreate if schema needs changes

### Current Limitations

- Only keyword search (no vector/semantic search)
- Processes first 5 invoices by default
- No embeddings generation
- No conversation memory persistence
- No filtering UI



## Next Steps

### Getting Started

1. **Generate Invoice PDFs**:
   ```powershell
   python generate_realistic_invoices.py
   ```
   Press Enter to generate first 5 invoices for testing

2. **Extract and Index**:
   ```powershell
   python extract_and_index.py
   ```
   Extracts invoice data using Document Intelligence and indexes in Azure AI Search

3. **Verify Indexing**:
   ```powershell
   python query.py
   ```
   View all indexed invoices and verify totals are correct

4. **Test the Chatbot**:
   ```powershell
   # Demo mode - single query
   python chatbot.py --demo
   
   # Interactive mode - conversation
   python chatbot.py
   ```

### Scaling Up

To process all 120 invoices:
1. Edit `extract_and_index.py` line 50
2. Change: `pdf_files = manifest_data.get('pdf_files', [])[:5]`
3. To: `pdf_files = manifest_data.get('pdf_files', [])`
4. Run: `python extract_and_index.py`

### Future Enhancements

1. **Add vector search with embeddings:**
   - Add `content_vector` field to index schema
   - Generate embeddings using Azure OpenAI text-embedding-ada-002
   - Populate vector field during indexing
   - Use hybrid search (keyword + vector) for semantic queries

2. **Process all 120 invoices** with batch processing and progress tracking

3. **Add advanced filtering:**
   - By vendor name
   - By date range
   - By amount range
   - By currency type

4. **Implement conversation persistence:**
   - Save chat history to database
   - Resume previous conversations
   - Track user sessions

5. **Add validation against manifest data** for quality assurance

### Additional Resources


- **Setup Guide:** See [Setup-guide.md](Setup-guide.md) for detailed Azure setup instructions
- **Azure Documentation:**
  - [Document Intelligence Invoice Model](https://learn.microsoft.com/azure/ai-services/document-intelligence/concept-invoice)
  - [Azure AI Search](https://learn.microsoft.com/azure/search/)
  - [Azure OpenAI Service](https://learn.microsoft.com/azure/ai-services/openai/)
