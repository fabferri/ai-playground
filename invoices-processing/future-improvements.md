## feature improvements



### 1. Implement Vector Embeddings

Vector search with embeddings can be added for semantic queries.
For better semantic search, you can add embeddings support:

1. Deploy an embedding model in Azure OpenAI (e.g., text-embedding-3-small)
2. Add a vector field to the search index schema
3. Generate embeddings during indexing:

## Deploy embedding model in Azure OpenAI:**

Enable semantic queries with embeddings:

```powershell
az cognitiveservices account deployment create `
  --name your-openai-resource `
  --resource-group your-rg `
  --deployment-name embedding-deployment `
  --model-name text-embedding-3-small `
  --model-version "1" `
  --model-format OpenAI `
  --sku-name "Standard" `
  --sku-capacity 1
```

**2. Update index schema with vector field:**
```python
from azure.search.documents.indexes.models import VectorSearch, HnswAlgorithmConfiguration

SearchField(
    name="content_vector",
    type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
    searchable=True,
    vector_search_dimensions=1536,
    vector_search_profile_name="vector-profile"
)
```


**3. Generate embeddings during indexing:**
```python
from openai import AzureOpenAI

def generate_embedding(text: str) -> list[float]:
    client = AzureOpenAI(
        azure_endpoint=os.getenv("OPENAI_ENDPOINT"),
        api_key=os.getenv("OPENAI_KEY"),
        api_version=os.getenv("OPENAI_API_VERSION", "2024-08-01-preview")
    )
    
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    
    return response.data[0].embedding
```

### 2. Process All Invoices

By default, [extract_and_index.py](extract_and_index.py) processes only the first 5 invoices for quick testing. To process all invoices, update line 50:

```python
# Change from:
pdf_files = manifest_data.get('pdf_files', [])[:5]

# To:
pdf_files = manifest_data.get('pdf_files', [])
```

### 3. Add More Chatbot Capabilities

Enhance the chatbot with additional functions:

```python
def get_invoice_summary(date_range: str) -> str:
    """Get summary statistics for invoices in a date range."""
    # Implementation here
    pass

def export_invoice_data(invoice_ids: List[str], format: str = "csv") -> str:
    """Export invoice data in specified format."""
    # Implementation here
    pass
```

### 4. Implement Multi-turn Conversations

You can add conversation history to [chatbot.py](chatbot.py) by maintaining a messages list:

```python
conversation_history = []

while True:
    user_query = input("You: ")
    conversation_history.append({"role": "user", "content": user_query})
    
    # Get response with history
    response = client.chat.completions.create(
        model=OPENAI_DEPLOYMENT,
        messages=conversation_history
    )
    
    conversation_history.append({"role": "assistant", "content": response.choices[0].message.content})
```

### 5. Add Advanced Filtering

```python
# Filter by date range
results = search_client.search(
    search_text="*",
    filter="invoice_date ge '2025-09-01' and invoice_date le '2025-09-30'",
    order_by=["total desc"]
)

# Filter by vendor and amount
results = search_client.search(
    search_text="*",
    filter="vendor eq 'Contoso' and total gt 10000"
)
```


### 6. Add Managed Identity Authentication (Optional)

For production environments, you can migrate from API keys to **Azure Managed Identity**:

1. Install the azure-identity package:
   ```bash
   pip install azure-identity
   ```

2. Assign appropriate RBAC roles to your managed identity
3. Update your code to use `DefaultAzureCredential`:

```python
from azure.identity import DefaultAzureCredential

credential = DefaultAzureCredential()

# Use with Document Intelligence
doc_client = DocumentIntelligenceClient(
    endpoint=DOC_INTEL_ENDPOINT,
    credential=credential
)

# Use with Search
search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=SEARCH_INDEX_NAME,
    credential=credential
)
```

**Note**: The current implementation uses API keys (`AzureKeyCredential`) for simplicity.
