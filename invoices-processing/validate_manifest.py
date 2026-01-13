"""
Manifest Validation Script

This script validates the consistency and integrity of the manifest_invoices_.json file.
It checks for:
- Missing or duplicate invoice IDs
- Missing required fields
- Mathematical accuracy (subtotal + tax + shipping = total)
- Sequence completeness (INV-2025-0001 through INV-2025-0120)
- Data distribution statistics

Usage:
    python validate_manifest.py
"""

import json
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def validate_manifest(manifest_path):
    """
    Validate the manifest file for consistency and integrity.
    
    Args:
        manifest_path: Path to the manifest JSON file
        
    Returns:
        dict: Validation results with counts and error details
    """
    # Read the manifest file
    with open(manifest_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f'Total records: {len(data)}')
    print()
    
    # Initialize tracking variables
    invoice_ids = set()
    missing_fields = []
    math_errors = []
    duplicate_ids = []
    sequence_gaps = []
    
    required_fields = [
        'invoice_id', 'vendor', 'currency', 'invoice_date', 
        'due_date', 'terms', 'subtotal', 'tax', 'shipping', 
        'total', 'file_path'
    ]
    
    # Validate each record
    for i, record in enumerate(data):
        # Check for missing fields
        for field in required_fields:
            if field not in record:
                missing_fields.append(f'Record {i}: missing field {field}')
        
        # Check for duplicate invoice IDs
        inv_id = record.get('invoice_id', '')
        if inv_id in invoice_ids:
            duplicate_ids.append(f'Duplicate invoice_id: {inv_id}')
        else:
            invoice_ids.add(inv_id)
        
        # Check math: subtotal + tax + shipping should equal total
        subtotal = record.get('subtotal', 0)
        tax = record.get('tax', 0)
        shipping = record.get('shipping', 0)
        total = record.get('total', 0)
        
        calculated_total = round(subtotal + tax + shipping, 2)
        recorded_total = round(total, 2)
        
        if abs(calculated_total - recorded_total) > 0.01:
            math_errors.append(
                f'{inv_id}: Expected {calculated_total}, got {recorded_total} '
                f'(subtotal:{subtotal} + tax:{tax} + shipping:{shipping})'
            )
    
    # Check invoice ID sequence
    expected_ids = [f'INV-2025-{str(i).zfill(4)}' for i in range(1, 121)]
    actual_ids = [record['invoice_id'] for record in data]
    
    for exp_id in expected_ids:
        if exp_id not in actual_ids:
            sequence_gaps.append(f'Missing invoice: {exp_id}')
    
    # Print results
    print('=== CONSISTENCY CHECK RESULTS ===')
    print()
    
    print(f'Missing fields: {len(missing_fields)}')
    if missing_fields:
        for err in missing_fields[:10]:
            print(f'  - {err}')
        if len(missing_fields) > 10:
            print(f'  ... and {len(missing_fields) - 10} more')
    print()
    
    print(f'Duplicate IDs: {len(duplicate_ids)}')
    if duplicate_ids:
        for err in duplicate_ids[:10]:
            print(f'  - {err}')
        if len(duplicate_ids) > 10:
            print(f'  ... and {len(duplicate_ids) - 10} more')
    print()
    
    print(f'Math errors (subtotal+tax+shipping != total): {len(math_errors)}')
    if math_errors:
        for err in math_errors[:10]:
            print(f'  - {err}')
        if len(math_errors) > 10:
            print(f'  ... and {len(math_errors) - 10} more')
    print()
    
    print(f'Sequence gaps: {len(sequence_gaps)}')
    if sequence_gaps:
        for err in sequence_gaps[:10]:
            print(f'  - {err}')
        if len(sequence_gaps) > 10:
            print(f'  ... and {len(sequence_gaps) - 10} more')
    print()
    
    # Gather statistics
    currencies = {}
    vendors = {}
    for record in data:
        curr = record.get('currency', 'Unknown')
        currencies[curr] = currencies.get(curr, 0) + 1
        vendor = record.get('vendor', 'Unknown')
        vendors[vendor] = vendors.get(vendor, 0) + 1
    
    print('=== STATISTICS ===')
    print(f'Currencies: {currencies}')
    print(f'Vendors: {vendors}')
    print()
    
    # Final verdict
    has_errors = (missing_fields or duplicate_ids or math_errors or sequence_gaps)
    if not has_errors:
        print(' All consistency checks PASSED!')
    else:
        print(' Issues found - see details above')
    
    return {
        'total_records': len(data),
        'missing_fields': len(missing_fields),
        'duplicate_ids': len(duplicate_ids),
        'math_errors': len(math_errors),
        'sequence_gaps': len(sequence_gaps),
        'currencies': currencies,
        'vendors': vendors,
        'passed': not has_errors
    }


if __name__ == '__main__':
    # Get the manifest file path from environment variable
    manifest_file = os.getenv('MANIFEST_FILE', 'invoices/manifest_invoices.json')
    script_dir = Path(__file__).parent
    manifest_path = script_dir / manifest_file
    
    if not manifest_path.exists():
        print(f'Error: Manifest file not found at {manifest_path}')
        exit(1)
    
    # Run validation
    results = validate_manifest(manifest_path)
    
    # Exit with appropriate code
    exit(0 if results['passed'] else 1)
