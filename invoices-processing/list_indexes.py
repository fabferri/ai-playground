"""
List all Azure AI Search indexes and optionally show documents in a specific index

This utility script helps you explore your Azure AI Search service by:
1. Listing all available search indexes
2. Displaying statistics for each index (document count, storage size)
3. Showing all documents within each index with their field values

Usage:
    python list_indexes.py

Prerequisites:
    - .env file with SEARCH_ENDPOINT and SEARCH_KEY configured
    - Azure AI Search service with at least one index created

Output:
    - All index names with field counts
    - Document count and storage size per index
    - All indexed documents with extracted fields (invoice_id, vendor, total, etc.)

Dependencies:
    - azure-search-documents
    - python-dotenv
"""

import os
from dotenv import load_dotenv
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient

# Load environment variables
load_dotenv()

# Configuration
SEARCH_ENDPOINT = os.getenv('SEARCH_ENDPOINT')
SEARCH_KEY = os.getenv('SEARCH_KEY')


def list_all_indexes():
    """List all search indexes in the Azure AI Search service"""
    print("="*70)
    print("AZURE AI SEARCH INDEXES")
    print("="*70)
    
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    try:
        indexes = index_client.list_indexes()
        index_list = list(indexes)
        
        if not index_list:
            print("\nNo indexes found.")
            return []
        
        print(f"\nFound {len(index_list)} index(es):\n")
        
        for idx in index_list:
            print(f"Index Name: {idx.name}")
            print(f"  Fields: {len(idx.fields)}")
            print(f"  Field Names: {', '.join([f.name for f in idx.fields])}")
            print()
        
        return [idx.name for idx in index_list]
    
    except Exception as e:
        print(f"\nERROR listing indexes: {e}")
        return []
    finally:
        index_client.close()


def list_documents_in_index(index_name):
    """List all documents in a specific index"""
    print("="*70)
    print(f"DOCUMENTS IN INDEX: {index_name}")
    print("="*70)
    
    search_client = SearchClient(
        endpoint=SEARCH_ENDPOINT,
        index_name=index_name,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    try:
        # Search for all documents
        results = search_client.search(
            search_text="*",
            select="*",
            top=1000
        )
        
        documents = list(results)
        
        if not documents:
            print("\nNo documents found in this index.")
            return
        
        print(f"\nFound {len(documents)} document(s):\n")
        
        for i, doc in enumerate(documents, 1):
            print(f"{i}. Document:")
            for key, value in doc.items():
                if key.startswith('@'):
                    continue  # Skip metadata fields
                # Truncate long content
                if isinstance(value, str) and len(value) > 100:
                    value = value[:100] + "..."
                print(f"   {key}: {value}")
            print()
    
    except Exception as e:
        print(f"\nERROR listing documents: {e}")
    finally:
        search_client.close()


def get_index_statistics(index_name):
    """Get statistics and detailed information for a specific index"""
    print("="*70)
    print(f"INDEX STATISTICS: {index_name}")
    print("="*70)
    
    index_client = SearchIndexClient(
        endpoint=SEARCH_ENDPOINT,
        credential=AzureKeyCredential(SEARCH_KEY)
    )
    
    try:
        # Get statistics
        stats = index_client.get_index_statistics(index_name)
        # Handle both dict and object responses
        if isinstance(stats, dict):
            doc_count = stats.get('document_count', 0)
            storage_size = stats.get('storage_size', 0)
        else:
            doc_count = stats.document_count
            storage_size = stats.storage_size
        
        print(f"\nDocument Count: {doc_count}")
        print(f"Storage Size: {storage_size:,} bytes ({storage_size / 1024:.2f} KB)")
        
        # Get full index definition for more details
        index = index_client.get_index(index_name)
        
        print(f"\n--- Index Schema Details ---")
        print(f"Total Fields: {len(index.fields)}")
        print(f"\nField Configuration:")
        
        for field in index.fields:
            print(f"\n  • {field.name}")
            print(f"    Type: {field.type}")
            attributes = []
            if getattr(field, 'key', False):
                attributes.append("KEY")
            if getattr(field, 'searchable', False):
                attributes.append("Searchable")
            if getattr(field, 'filterable', False):
                attributes.append("Filterable")
            if getattr(field, 'sortable', False):
                attributes.append("Sortable")
            if getattr(field, 'facetable', False):
                attributes.append("Facetable")
            if getattr(field, 'retrievable', True):
                attributes.append("Retrievable")
            
            if attributes:
                print(f"    Attributes: {', '.join(attributes)}")
        
        # Show scoring profiles if any
        if hasattr(index, 'scoring_profiles') and index.scoring_profiles:
            print(f"\nScoring Profiles: {len(index.scoring_profiles)}")
            for profile in index.scoring_profiles:
                print(f"  • {profile.name}")
        
        # Show suggesters if any
        if hasattr(index, 'suggesters') and index.suggesters:
            print(f"\nSuggesters: {len(index.suggesters)}")
            for suggester in index.suggesters:
                print(f"  • {suggester.name} (fields: {', '.join(suggester.source_fields)})")
        
        # Show vector search configuration if any
        if hasattr(index, 'vector_search') and index.vector_search:
            print(f"\nVector Search: Configured")
        
    except Exception as e:
        print(f"\nERROR getting statistics: {e}")
    finally:
        index_client.close()


def main():
    """Main execution"""
    print("\n" + "="*70)
    print("AZURE AI SEARCH - INDEX EXPLORER")
    print("="*70 + "\n")
    
    # Step 1: List all indexes
    index_names = list_all_indexes()
    
    if not index_names:
        print("\nNo indexes to explore.")
        return
    
    # Step 2: Show details for each index
    for index_name in index_names:
        print()
        get_index_statistics(index_name)
        input("\nPress Enter to continue and view documents...")
        print()
        list_documents_in_index(index_name)
    
    print("="*70)
    print("COMPLETE!")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
