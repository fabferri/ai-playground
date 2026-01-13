"""
Extract invoice data using Azure Document Intelligence and index with Azure AI Search

This script performs three main operations:
1. Extracts invoice data from PDF files using Azure Document Intelligence prebuilt invoice model
2. Creates an Azure AI Search index with appropriate schema for invoice documents
3. Uploads extracted invoice data to the search index for querying

IMPORTANT - Processing Limit:
    By default, this script processes only the FIRST 5 invoices (line 50).
    To process all invoices, change:
        pdf_files = manifest_data.get('pdf_files', [])[:5]
    To:
        pdf_files = manifest_data.get('pdf_files', [])
    
    Or specify a different number:
        pdf_files = manifest_data.get('pdf_files', [])[:10]  # First 10 invoices

Prerequisites:
    - .env file with DOC_INTEL_ENDPOINT, DOC_INTEL_KEY, SEARCH_ENDPOINT, SEARCH_KEY
    - Invoice PDFs in the invoices/ folder
    - manifest_invoices.json file listing all PDF files

Output:
    - invoices/extraction_invoices.jsonl - Extracted invoice data
    - Azure AI Search index populated with invoice documents
"""

import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
)

# Load environment variables from .env file
load_dotenv()

# Configuration - Azure Document Intelligence
DOC_INTEL_ENDPOINT = os.getenv('DOC_INTEL_ENDPOINT')
DOC_INTEL_KEY = os.getenv('DOC_INTEL_KEY')

# Configuration - Azure AI Search
SEARCH_ENDPOINT = os.getenv('SEARCH_ENDPOINT')
SEARCH_KEY = os.getenv('SEARCH_KEY')
SEARCH_INDEX_NAME = os.getenv('SEARCH_INDEX_NAME')

# Paths
INVOICES_FOLDER = os.getenv('INVOICES_FOLDER', 'invoices')
MANIFEST_FILE = os.getenv('MANIFEST_FILE', 'invoices/manifest_invoices.json')


async def extract_invoices():
    """Extract invoice data using Document Intelligence prebuilt invoice model"""
    print("="*70)
    print("STEP 1: Extracting Invoice Data")
    print("="*70)
    
    # Load manifest to get PDF list
    with open(MANIFEST_FILE, 'r') as f:
        manifest_data = json.load(f)
    
    # Get all PDF files listed in the manifest
    pdf_files = manifest_data.get('pdf_files', [])
    
    print(f"\nProcessing {len(pdf_files)} invoice PDFs...")
    print("-"*70)
    
    extracted_invoices = []
    
    # Create Document Intelligence client
    async with DocumentIntelligenceClient(
        endpoint=DOC_INTEL_ENDPOINT,
        credential=AzureKeyCredential(DOC_INTEL_KEY)
    ) as doc_client:
        
        for pdf_file in pdf_files:
            pdf_path = Path(INVOICES_FOLDER) / pdf_file
            
            if not pdf_path.exists():
                print(f"   SKIP: {pdf_file} not found")
                continue
            
            print(f"\nProcessing: {pdf_file}")
            
            try:
                # Read PDF file
                with open(pdf_path, "rb") as f:
                    pdf_bytes = f.read()
                
                # Analyze invoice using prebuilt model
                poller = await doc_client.begin_analyze_document(
                    "prebuilt-invoice",
                    pdf_bytes
                )
                result = await poller.result()
                
                # Extract structured fields
                for document in result.documents:
                    invoice_data = {
                        "invoice_id": None,
                        "vendor": None,
                        "invoice_date": None,
                        "due_date": None,
                        "currency": "USD",
                        "subtotal": 0.0,
                        "tax": 0.0,
                        "shipping": 0.0,
                        "total": 0.0,
                        "content": "",
                        "source_file": pdf_file
                    }
                    
                    # Extract header fields
                    fields = document.fields
                    if fields:
                        # Invoice ID
                        if "InvoiceId" in fields:
                            invoice_data["invoice_id"] = fields["InvoiceId"].get("content") or fields["InvoiceId"].get("value_string")
                        
                        # Vendor
                        if "VendorName" in fields:
                            invoice_data["vendor"] = fields["VendorName"].get("content") or fields["VendorName"].get("value_string")
                        
                        # Dates
                        if "InvoiceDate" in fields:
                            date_val = fields["InvoiceDate"].get("content") or fields["InvoiceDate"].get("value_date")
                            invoice_data["invoice_date"] = str(date_val) if date_val else None
                        
                        if "DueDate" in fields:
                            date_val = fields["DueDate"].get("content") or fields["DueDate"].get("value_date")
                            invoice_data["due_date"] = str(date_val) if date_val else None
                        
                        # Currency - extract from InvoiceTotal field
                        if "InvoiceTotal" in fields:
                            total_field = fields["InvoiceTotal"]
                            value_currency = total_field._data.get("valueCurrency", {})
                            if value_currency:
                                invoice_data["currency"] = value_currency.get("currencyCode", "USD")
                                invoice_data["total"] = value_currency.get("amount", 0.0)
                        
                        # Extract subtotal
                        if "SubTotal" in fields:
                            subtotal_field = fields["SubTotal"]
                            value_currency = subtotal_field._data.get("valueCurrency", {})
                            if value_currency:
                                invoice_data["subtotal"] = value_currency.get("amount", 0.0)
                        
                        # Extract tax
                        if "TotalTax" in fields:
                            tax_field = fields["TotalTax"]
                            value_currency = tax_field._data.get("valueCurrency", {})
                            if value_currency:
                                invoice_data["tax"] = value_currency.get("amount", 0.0)
                        
                        # Build content for search
                        invoice_data["content"] = (
                            f"Invoice {invoice_data['invoice_id']} from {invoice_data['vendor']} "
                            f"dated {invoice_data['invoice_date']}. "
                            f"Total: {invoice_data['currency']} {invoice_data['total']:.2f}"
                        )
                    
                    extracted_invoices.append(invoice_data)
                    print(f"   Extracted: {invoice_data['invoice_id']} - Total: {invoice_data['currency']} {invoice_data['total']:.2f}")
            
            except Exception as e:
                print(f"   ERROR: {str(e)}")
    
    print("-"*70)
    print(f"\nExtracted {len(extracted_invoices)} invoices")
    
    # Save to JSON file
    output_file = Path(INVOICES_FOLDER) / "extraction_invoices.jsonl"
    with open(output_file, 'w') as f:
        for invoice in extracted_invoices:
            f.write(json.dumps(invoice) + "\n")
    
    print(f"Saved to: {output_file}")
    
    return extracted_invoices


def create_search_index():
    """Create Azure AI Search index"""
    print("\n" + "="*70)
    print("STEP 2: Creating Search Index")
    print("="*70)
    
    fields = [
        SimpleField(
            name="invoice_id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
            sortable=True
        ),
        SearchableField(name="vendor", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="invoice_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="due_date", type=SearchFieldDataType.String, filterable=True, sortable=True),
        SimpleField(name="currency", type=SearchFieldDataType.String, filterable=True),
        SimpleField(name="subtotal", type=SearchFieldDataType.Double),
        SimpleField(name="tax", type=SearchFieldDataType.Double),
        SimpleField(name="shipping", type=SearchFieldDataType.Double),
        SimpleField(name="total", type=SearchFieldDataType.Double, filterable=True, sortable=True),
        SearchableField(name="content", type=SearchFieldDataType.String, analyzer_name="en.microsoft"),
        SimpleField(name="source_file", type=SearchFieldDataType.String)
    ]
    
    index = SearchIndex(name=SEARCH_INDEX_NAME, fields=fields)
    
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    try:
        result = index_client.create_or_update_index(index)
        print(f"\nSearch index created/updated: {result.name}")
    except Exception as e:
        print(f"\nERROR creating index: {e}")
        raise
    finally:
        index_client.close()


def index_invoices(invoices):
    """Upload invoices to search index"""
    print("\n" + "="*70)
    print("STEP 3: Indexing Invoices")
    print("="*70)
    
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=SEARCH_INDEX_NAME,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    try:
        result = search_client.upload_documents(documents=invoices)
        print(f"\nIndexed {len(result)} invoices successfully")
    except Exception as e:
        print(f"\nERROR indexing: {e}")
        raise
    finally:
        search_client.close()


async def main():
    """Main execution"""
    print("\n" + "="*70)
    print("INVOICE EXTRACTION AND INDEXING")
    print("="*70 + "\n")
    
    # Step 1: Extract invoices
    invoices = await extract_invoices()
    
    if not invoices:
        print("\nNo invoices extracted. Exiting.")
        return
    
    # Step 2: Create search index
    create_search_index()
    
    # Step 3: Index invoices
    index_invoices(invoices)
    
    print("\n" + "="*70)
    print("COMPLETE!")
    print("="*70)
    print("\nNext steps:")
    print("1. Run: py query.py")
    print("   - View all indexed invoices")
    print("2. Run: py chatbot.py")
    print("   - Ask questions about your invoices")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
