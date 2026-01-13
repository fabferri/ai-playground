"""
This script queries and displays invoices from an Azure AI Search index.
It connects to Azure AI Search using credentials from environment variables,
retrieves all indexed invoices, and prints them in a formatted table showing
invoice ID, vendor, date, and total amount.
"""

import os
from dotenv import load_dotenv
from azure.search.documents import SearchClient
from azure.core.credentials import AzureKeyCredential

# Load environment variables from .env file
load_dotenv()

SEARCH_ENDPOINT = os.getenv('SEARCH_ENDPOINT')
SEARCH_KEY = os.getenv('SEARCH_KEY')
SEARCH_INDEX_NAME = os.getenv('SEARCH_INDEX_NAME')

search_client = SearchClient(
    endpoint=SEARCH_ENDPOINT,
    index_name=SEARCH_INDEX_NAME,
    credential=AzureKeyCredential(SEARCH_KEY)
)


print('=' * 70)
print('INVOICES IN SEARCH INDEX')
print('=' * 70)
print()

for i, r in enumerate(search_client.search('*', top=10), 1):
    print(f"{i}. ID: {r['invoice_id']:15} | Vendor: {r.get('vendor', 'Unknown'):25} | Date: {r.get('invoice_date', 'N/A'):12} | Total: {r.get('total', 0)}")

print()
print('=' * 70)
print('You can search by:')
print('  - Invoice ID: sc.search("INV-2025-0001")')
print('  - Vendor: sc.search("Contoso")')
print('  - Any text in content: sc.search("your search term")')
print('=' * 70)

print('='*70)
print('ALL INVOICES')
print('='*70)

results = search_client.search(
    search_text='*',
    top=10,
    select=['invoice_id', 'vendor', 'total', 'currency'],
    order_by=['invoice_id']
)

for i, r in enumerate(results):
    print(f"{i}. ID: {r['invoice_id']:15} | Vendor: {r.get('vendor', 'Unknown'):25} | Total: {r.get('total', 0)}")