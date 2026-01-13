"""
Generate manifest_invoices.json from PDF files in the invoices folder

WHY THIS FILE IS REQUIRED:
The manifest_invoices.json file serves as a central index for the invoice processing pipeline:

1. **File Discovery**: Lists all invoice PDFs to be processed, eliminating the need
   to repeatedly scan the filesystem during batch operations.

2. **Processing Tracker**: The extract_and_index.py script uses this manifest to:
   - Determine which PDFs to extract with Document Intelligence
   - Track processing progress across multiple runs
   - Validate that all expected invoices are present

3. **Ground Truth Reference**: Contains metadata that can be used to:
   - Cross-validate extraction results
   - Generate quality control reports
   - Join with search index data during ingestion

4. **Reproducibility**: Ensures consistent processing order and makes the pipeline
   deterministic by defining exactly which files to process.

This script scans the invoices folder for PDF files and creates/updates the manifest
to reflect the current state of available invoice files.
"""

import json
from pathlib import Path
from typing import List, Dict, Any


def scan_invoice_folder(folder_path: Path) -> List[str]:
    """
    Scan the invoices folder and return a list of PDF files.
    
    Args:
        folder_path: Path to the invoices folder
        
    Returns:
        List of PDF filenames sorted alphabetically
    """
    if not folder_path.exists():
        print(f"WARNING: Folder does not exist: {folder_path}")
        return []
    
    # Get all PDF files
    pdf_files = [f.name for f in folder_path.glob("*.pdf")]
    
    # Sort alphabetically
    pdf_files.sort()
    
    return pdf_files


def generate_manifest(
    pdf_files: List[str],
    output_dir: str = "invoices",
    manifest_filename: str = "manifest_invoices.json"
) -> Dict[str, Any]:
    """
    Generate manifest dictionary from list of PDF files.
    
    Args:
        pdf_files: List of PDF filenames
        output_dir: Directory containing the PDFs
        manifest_filename: Name of the manifest file
        
    Returns:
        Manifest dictionary
    """
    manifest = {
        "output_dir": output_dir,
        "num_expected": len(pdf_files),
        "num_created": len(pdf_files),
        "pdf_files": pdf_files,
        "manifest": manifest_filename
    }
    
    return manifest


def save_manifest(manifest: Dict[str, Any], output_path: Path) -> None:
    """
    Save manifest to JSON file.
    
    Args:
        manifest: Manifest dictionary
        output_path: Path where to save the manifest
    """
    # Ensure parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write JSON with pretty formatting
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    
    print(f"Manifest saved to: {output_path}")


def main():
    """Main execution function."""
    # Define paths
    invoices_folder = Path("invoices")
    manifest_path = invoices_folder / "manifest_invoices.json"
    
    print("=" * 60)
    print("Invoice Manifest Generator")
    print("=" * 60)
    print()
    
    # Scan for PDF files
    print(f"Scanning folder: {invoices_folder}")
    pdf_files = scan_invoice_folder(invoices_folder)
    
    if not pdf_files:
        print("ERROR: No PDF files found in the invoices folder")
        print(f"Please ensure PDF files are placed in: {invoices_folder.absolute()}")
        return
    
    print(f"Found {len(pdf_files)} PDF files")
    
    # Show first and last few files
    if len(pdf_files) <= 10:
        print("\nPDF files:")
        for pdf in pdf_files:
            print(f"  - {pdf}")
    else:
        print("\nFirst 5 PDF files:")
        for pdf in pdf_files[:5]:
            print(f"  - {pdf}")
        print("  ...")
        print("\nLast 5 PDF files:")
        for pdf in pdf_files[-5:]:
            print(f"  - {pdf}")
    
    # Generate manifest
    print("\nGenerating manifest...")
    manifest = generate_manifest(
        pdf_files=pdf_files,
        output_dir=invoices_folder.name,
        manifest_filename="manifest_invoices.json"
    )
    
    # Save manifest
    save_manifest(manifest, manifest_path)
    
    print()
    print("=" * 60)
    print("Manifest Generation Complete")
    print("=" * 60)
    print()
    print("Manifest summary:")
    print(f"  - Total PDFs: {manifest['num_created']}")
    print(f"  - Output directory: {manifest['output_dir']}")
    print(f"  - Manifest file: {manifest_path}")
    print()
    print("You can now use this manifest with extract_and_index.py")


if __name__ == "__main__":
    main()
