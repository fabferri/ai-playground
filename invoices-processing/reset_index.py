"""
Reset Azure AI Search index - Delete and optionally recreate

This utility script helps you reset your Azure AI Search index by:
1. Deleting the existing search index (removes all indexed documents)
2. Optionally recreating an empty index with the same schema

Use Cases:
    - Clear all indexed documents to start fresh
    - Fix schema conflicts or corruption
    - Clean up before reprocessing invoices
    - Reset to default state

CAUTION:
    This operation is DESTRUCTIVE and CANNOT BE UNDONE.
    All indexed invoice documents will be permanently deleted.

Usage:
    python reset_index.py

Prerequisites:
    - .env file with SEARCH_ENDPOINT, SEARCH_KEY, SEARCH_INDEX_NAME
    - Azure AI Search service with existing index

Dependencies:
    - azure-search-documents
    - python-dotenv
"""

import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
)

# Load environment variables
load_dotenv()

# Configuration
SEARCH_ENDPOINT = os.getenv('SEARCH_ENDPOINT')
SEARCH_KEY = os.getenv('SEARCH_KEY')
SEARCH_INDEX_NAME = os.getenv('SEARCH_INDEX_NAME')


def delete_index(index_name):
    """Delete the search index"""
    print("="*70)
    print(f"DELETING INDEX: {index_name}")
    print("="*70)
    
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    try:
        # Check if index exists
        try:
            index_client.get_index(index_name)
            print(f"\nIndex '{index_name}' found. Deleting...")
        except Exception:
            print(f"\nIndex '{index_name}' does not exist. Nothing to delete.")
            return False
        
        # Delete the index
        index_client.delete_index(index_name)
        print(f"✓ Index '{index_name}' deleted successfully")
        return True
        
    except Exception as e:
        print(f"\nERROR deleting index: {e}")
        return False
    finally:
        index_client.close()


def create_empty_index(index_name):
    """Create a new empty index with invoice schema"""
    print("\n" + "="*70)
    print(f"CREATING NEW INDEX: {index_name}")
    print("="*70)
    
    # Define the index schema (same as extract_and_index.py)
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
    
    index = SearchIndex(name=index_name, fields=fields)
    
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    try:
        result = index_client.create_index(index)
        print(f"\n✓ Empty index '{result.name}' created successfully")
        print(f"  Fields: {len(fields)}")
        return True
    except Exception as e:
        print(f"\nERROR creating index: {e}")
        return False
    finally:
        index_client.close()


def main():
    """Main execution"""
    print("\n" + "="*70)
    print("AZURE AI SEARCH - INDEX RESET UTILITY")
    print("="*70)
    
    if not SEARCH_INDEX_NAME:
        print("\nERROR: SEARCH_INDEX_NAME not found in .env file")
        return
    
    print(f"\nTarget Index: {SEARCH_INDEX_NAME}")
    print(f"Endpoint: {SEARCH_ENDPOINT}")
    
    # Confirm deletion
    print("\n" + "!"*35)
    print("WARNING: This will DELETE all indexed invoice documents!")
    print("This operation CANNOT be undone.")
    print("!"*35)
    
    response = input("\nType 'DELETE' to confirm deletion, or anything else to cancel: ")
    
    if response.strip() != "DELETE":
        print("\n✗ Operation cancelled. No changes made.")
        return
    
    # Step 1: Delete the index
    deleted = delete_index(SEARCH_INDEX_NAME)
    
    if not deleted:
        print("\nReset operation incomplete.")
        return
    
    # Step 2: Ask if user wants to recreate
    print("\n" + "-"*70)
    recreate = input("\nRecreate empty index with same schema? (y/n): ")
    
    if recreate.lower() in ['y', 'yes']:
        create_empty_index(SEARCH_INDEX_NAME)
    else:
        print("\n✓ Index deleted. No new index created.")
    
    print("\n" + "="*70)
    print("RESET COMPLETE!")
    print("="*70)
    
    if recreate.lower() in ['y', 'yes']:
        print("\nNext steps:")
        print("1. Run: py extract_and_index.py")
        print("   - Extract and index invoice data")
        print("2. Run: py query.py")
        print("   - Verify indexed invoices")
    else:
        print("\nNext step:")
        print("Run: py extract_and_index.py")
        print("   - This will recreate the index and populate it with invoice data")
    
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    main()
