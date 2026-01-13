"""
Debug script to see exactly what Document Intelligence extracts from PDFs
"""

import asyncio
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from azure.ai.documentintelligence.aio import DocumentIntelligenceClient
from azure.core.credentials import AzureKeyCredential

# Load environment variables from .env file
load_dotenv()

# Configuration
DOC_INTEL_ENDPOINT = os.getenv('DOC_INTEL_ENDPOINT')
DOC_INTEL_KEY = os.getenv('DOC_INTEL_KEY')

async def debug_single_invoice():
    """Analyze one invoice and print all extracted fields"""
    
    # Test with first invoice
    pdf_path = Path("invoices/invoice_INV-2025-0001.pdf")
    
    print("="*70)
    print(f"DEBUGGING: {pdf_path.name}")
    print("="*70)
    
    async with DocumentIntelligenceClient(
        endpoint=DOC_INTEL_ENDPOINT,
        credential=AzureKeyCredential(DOC_INTEL_KEY)
    ) as doc_client:
        
        with open(pdf_path, "rb") as f:
            pdf_bytes = f.read()
        
        print("\nAnalyzing with Document Intelligence prebuilt-invoice model...")
        
        poller = await doc_client.begin_analyze_document(
            "prebuilt-invoice",
            pdf_bytes
        )
        result = await poller.result()
        
        print("\n" + "="*70)
        print("EXTRACTED FIELDS:")
        print("="*70)
        
        for idx, document in enumerate(result.documents):
            print(f"\nDocument {idx + 1}:")
            print("-"*70)
            
            fields = document.fields
            
            if not fields:
                print("NO FIELDS FOUND!")
                continue
            
            # Print all field names
            print(f"\nAvailable fields: {list(fields.keys())}")
            
            # Print each field in detail
            for field_name, field_value in fields.items():
                print(f"\n{field_name}:")
                print(f"  Type: {field_value.get('value_type', 'unknown')}")
                print(f"  Content: {field_value.get('content')}")
                print(f"  Value: {field_value}")
                
                # Check for nested properties
                if hasattr(field_value, '__dict__'):
                    print(f"  Properties: {field_value.__dict__}")
        
        # Also save the full result to JSON for inspection
        output_file = "debug_output.json"
        print(f"\n\nSaving full result to {output_file}...")
        
        # Convert result to dict
        result_dict = {
            "documents": []
        }
        
        for doc in result.documents:
            doc_dict = {
                "fields": {}
            }
            for field_name, field_value in doc.fields.items():
                doc_dict["fields"][field_name] = str(field_value)
            result_dict["documents"].append(doc_dict)
        
        with open(output_file, 'w') as f:
            json.dump(result_dict, f, indent=2)
        
        print(f"Full output saved to {output_file}")
        print("\n" + "="*70)

if __name__ == "__main__":
    asyncio.run(debug_single_invoice())
