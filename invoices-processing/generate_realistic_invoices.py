"""
Generate realistic invoice PDFs that Azure Document Intelligence can recognize.

This script creates properly formatted invoices with:
- Clear field labels ("Invoice Number:", "Total:", etc.)
- Proper table structure for line items
- Number formatting with currency symbols
- Standard invoice layout

Required module:
  pip install reportlab

"""

import json
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_RIGHT, TA_LEFT


def load_manifest():
    """Load invoice data from manifest file"""
    # Try the detailed manifest first (from readme)
    readme_path = Path("readme.md")
    
    if readme_path.exists():
        print("\nReading invoice data from readme.md...")
        invoices = []
        # We'll just create sample invoices using the file list
        manifest_path = Path("invoices/manifest_invoices.json")
        if manifest_path.exists():
            with open(manifest_path, 'r') as f:
                manifest_data = json.load(f)
            pdf_files = manifest_data.get('pdf_files', [])
            
            # Create sample invoice data for each PDF
            # Real vendor names extracted from original PDFs
            vendors = [
                "Adventure Works",
                "Alpine Ski House",
                "Contoso Retail",
                "Fabrikam Services",
                "Litware Consulting",
                "Northwind Traders",
                "Proseware Ltd",
                "Tailspin Toys",
                "Wide World Importers",
                "Woodgrove Bank"
            ]
            
            # 100 unique customer names with addresses
            customers = [
                ("Apex Holdings", "100 Market St, Reading RG1 2BN, United Kingdom"),
                ("Blue Yonder Airlines", "500 Aviation Way, Heathrow TW6 2GA, United Kingdom"),
                ("City Power & Light", "250 Grid Rd, Manchester M1 1AE, United Kingdom"),
                ("Coho Vineyard", "75 Wine Estate Ln, Napa CA 94558, United States"),
                ("Southridge Video", "300 Media Plaza, Los Angeles CA 90028, United States"),
                ("Global Imports Ltd", "88 Trade Center, London E14 5AB, United Kingdom"),
                ("Pacific Tech Solutions", "1200 Tech Park, San Francisco CA 94105, United States"),
                ("Metro Transit Authority", "450 Rail St, Boston MA 02108, United States"),
                ("Harvest Foods Inc", "320 Farm Rd, Des Moines IA 50309, United States"),
                ("Sterling Pharmaceuticals", "600 Medical Plaza, Basel 4056, Switzerland"),
                ("Quantum Robotics", "777 Innovation Dr, Tokyo 100-0001, Japan"),
                ("Alpine Construction", "55 Builder Ave, Denver CO 80202, United States"),
                ("Ocean Freight Services", "900 Port Blvd, Rotterdam 3011, Netherlands"),
                ("Velocity Motors", "1500 Auto Park, Detroit MI 48201, United States"),
                ("Summit Financial Group", "200 Wall St, New York NY 10005, United States"),
                ("Green Energy Solutions", "425 Solar Way, Austin TX 78701, United States"),
                ("Royal Textiles", "150 Fashion St, Manchester M2 4PD, United Kingdom"),
                ("Tech Innovators GmbH", "88 Hauptstrasse, Munich 80331, Germany"),
                ("Cloud Services Corp", "2000 Data Center Rd, Seattle WA 98101, United States"),
                ("Premier Healthcare", "350 Hospital Dr, Chicago IL 60601, United States"),
                ("Digital Marketing Pro", "275 Creative Ln, Miami FL 33131, United States"),
                ("Industrial Equipment Ltd", "600 Factory Rd, Birmingham B1 1AA, United Kingdom"),
                ("Sunrise Properties", "800 Real Estate Ave, Phoenix AZ 85001, United States"),
                ("Global Logistics", "1100 Warehouse St, Singapore 018956, Singapore"),
                ("Modern Furniture Co", "450 Design Blvd, Milan 20121, Italy"),
                ("Advanced Aerospace", "2500 Flight Path, Houston TX 77002, United States"),
                ("Smart Home Systems", "175 IoT Plaza, San Jose CA 95113, United States"),
                ("Financial Advisors Inc", "900 Investment Dr, Boston MA 02109, United States"),
                ("Retail Solutions Group", "650 Commerce St, Dallas TX 75201, United States"),
                ("Enterprise Software", "1800 Code Way, Redmond WA 98052, United States"),
                ("Manufacturing Partners", "425 Industrial Ave, Cleveland OH 44114, United States"),
                ("Legal Services Ltd", "300 Law Center, Edinburgh EH1 1YZ, United Kingdom"),
                ("Educational Resources", "550 Campus Dr, Cambridge MA 02138, United States"),
                ("Media Production House", "700 Studio Ln, Burbank CA 91502, United States"),
                ("Architecture Studio", "225 Design Plaza, Barcelona 08001, Spain"),
                ("Hospitality Group", "1000 Hotel Circle, Las Vegas NV 89101, United States"),
                ("Biotech Research", "850 Science Park, Cambridge CB2 1TN, United Kingdom"),
                ("Agricultural Supplies", "400 Harvest Way, Kansas City MO 64101, United States"),
                ("Fashion Retail Chain", "950 Style Ave, Paris 75001, France"),
                ("Automotive Parts Inc", "1300 Engine Rd, Stuttgart 70173, Germany"),
                ("Insurance Brokers", "500 Risk Management Dr, Hartford CT 06103, United States"),
                ("Consulting Partners", "725 Advisory St, Dubai 00000, UAE"),
                ("Telecommunications Ltd", "1600 Network Blvd, Stockholm 111 21, Sweden"),
                ("Food Distribution", "875 Grocery Way, Minneapolis MN 55401, United States"),
                ("Construction Materials", "1100 Supply Rd, Toronto M5H 2N2, Canada"),
                ("Printing Services", "350 Press Ave, Brooklyn NY 11201, United States"),
                ("Event Management Co", "625 Conference Dr, Orlando FL 32801, United States"),
                ("Security Solutions", "1400 Guard Plaza, Washington DC 20001, United States"),
                ("Travel Agency Group", "550 Vacation Ln, Honolulu HI 96813, United States"),
                ("Pharmaceutical Dist", "900 Medicine Way, Brussels 1000, Belgium"),
                ("Electronics Retail", "1250 Gadget St, Shenzhen 518000, China"),
                ("Property Management", "475 Rental Ave, San Diego CA 92101, United States"),
                ("Catering Services", "800 Culinary Blvd, New Orleans LA 70112, United States"),
                ("Training Institute", "350 Education Dr, Atlanta GA 30303, United States"),
                ("Research Laboratory", "1500 Discovery Way, Oxford OX1 2JD, United Kingdom"),
                ("Transportation Co", "675 Fleet St, Melbourne 3000, Australia"),
                ("Chemical Industries", "1900 Laboratory Rd, Frankfurt 60311, Germany"),
                ("Marketing Agency", "425 Brand Plaza, Toronto M5J 2N8, Canada"),
                ("IT Support Services", "1050 Help Desk Dr, Dublin D02 AF30, Ireland"),
                ("Medical Equipment", "750 Healthcare Way, Boston MA 02110, United States"),
                ("Publishing House", "550 Book St, London WC2N 5DU, United Kingdom"),
                ("Engineering Firm", "1300 Technical Ave, Zurich 8001, Switzerland"),
                ("Accounting Services", "400 Finance Plaza, Sydney 2000, Australia"),
                ("Packaging Solutions", "825 Container Rd, Hamburg 20095, Germany"),
                ("Fitness Centers", "950 Wellness Way, Los Angeles CA 90017, United States"),
                ("Waste Management", "600 Recycle Dr, Portland OR 97201, United States"),
                ("Dental Practices", "375 Smile Ave, Denver CO 80203, United States"),
                ("Veterinary Clinics", "525 Pet Care Ln, Austin TX 78702, United States"),
                ("Beauty Salons Chain", "700 Style St, Milan 20122, Italy"),
                ("Car Rental Services", "1100 Auto Dr, Miami FL 32132, United States"),
                ("Plumbing Contractors", "450 Pipe Way, Phoenix AZ 85002, United States"),
                ("Electrical Services", "875 Voltage Rd, Houston TX 77003, United States"),
                ("HVAC Solutions", "625 Climate Dr, Chicago IL 60602, United States"),
                ("Landscaping Co", "550 Garden Ave, Seattle WA 98102, United States"),
                ("Pest Control Inc", "425 Exterminator St, Tampa FL 33601, United States"),
                ("Moving Services", "900 Relocation Blvd, Dallas TX 75202, United States"),
                ("Storage Facilities", "1200 Warehouse Ave, Atlanta GA 30304, United States"),
                ("Cleaning Services", "350 Janitor Way, San Francisco CA 94106, United States"),
                ("Security Guard Co", "725 Protection Plaza, Las Vegas NV 89102, United States"),
                ("Courier Services", "1050 Delivery Dr, Memphis TN 38103, United States"),
                ("Equipment Rental", "575 Lease St, Indianapolis IN 46204, United States"),
                ("Auction House", "800 Bid Ave, New York NY 10006, United States"),
                ("Art Gallery", "475 Culture Ln, Paris 75002, France"),
                ("Music Production", "650 Sound Plaza, Nashville TN 37203, United States"),
                ("Film Studio", "1400 Cinema Blvd, Los Angeles CA 90029, United States"),
                ("Gaming Company", "950 Play St, Tokyo 100-0002, Japan"),
                ("Sports Equipment", "725 Athletic Dr, Portland OR 97202, United States"),
                ("Outdoor Gear Co", "825 Adventure Way, Denver CO 80204, United States"),
                ("Marine Supplies", "600 Nautical Ave, Miami FL 33133, United States"),
                ("Aviation Services", "1500 Hangar Rd, Dallas TX 75203, United States"),
                ("Railway Operations", "875 Track St, London EC1A 1BB, United Kingdom"),
                ("Shipping Lines", "1100 Ocean Way, Hamburg 20457, Germany"),
                ("Customs Brokers", "525 Import Plaza, Rotterdam 3012, Netherlands"),
                ("Freight Forwarders", "950 Cargo Blvd, Singapore 018957, Singapore"),
                ("Warehouse Logistics", "1250 Distribution Dr, Chicago IL 60603, United States"),
                ("Supply Chain Mgmt", "700 Logistics Ave, Frankfurt 60312, Germany"),
                ("Procurement Services", "625 Vendor St, Dubai 00001, UAE"),
                ("Quality Assurance", "850 Testing Way, Munich 80332, Germany"),
                ("Environmental Services", "475 Green Plaza, Stockholm 111 22, Sweden"),
            ]
            
            for i, pdf_file in enumerate(pdf_files, 1):
                invoice_id = pdf_file.replace("invoice_", "").replace(".pdf", "")
                customer = customers[i % len(customers)]
                
                # Determine currency based on customer address
                address = customer[1]
                if "United States" in address:
                    currency = "USD"
                elif "United Kingdom" in address:
                    currency = "GBP"
                elif any(country in address for country in ["Germany", "Switzerland", "Italy", "Spain", "France", "Belgium", "Netherlands", "Sweden"]):
                    currency = "EUR"
                else:
                    currency = "USD"  # Default to USD for other countries
                
                invoices.append({
                    "invoice_id": invoice_id,
                    "vendor": vendors[i % len(vendors)],
                    "currency": currency,
                    "invoice_date": f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}",
                    "due_date": f"2025-{((i + 1) % 12) + 1:02d}-{(i % 28) + 1:02d}",
                    "terms": "Net 30" if i % 2 == 0 else "Net 14",
                    "bill_to_name": customer[0],
                    "bill_to_address": customer[1],
                    "subtotal": 10000.0 + (i * 127.5),
                    "tax": (10000.0 + (i * 127.5)) * 0.2,
                    "shipping": 25.0 if i % 3 == 0 else 0.0,
                    "total": (10000.0 + (i * 127.5)) * 1.2 + (25.0 if i % 3 == 0 else 0.0),
                    "line_items": []
                })
        
        return invoices
    
    return []


def create_invoice_pdf(invoice_data, output_path):
    """
    Create a realistic invoice PDF that Document Intelligence can parse.
    
    Args:
        invoice_data: Dictionary with invoice fields
        output_path: Path to save the PDF file
    """
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    company_style = ParagraphStyle(
        'CompanyTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.black,
        spaceAfter=20,
        alignment=TA_LEFT,
    )
    
    label_style = ParagraphStyle(
        'Label',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
    )
    
    # Company Name/Header - centered
    centered_company_style = ParagraphStyle(
        'CenteredCompany',
        parent=company_style,
        alignment=1,  # Center alignment
    )
    
    story.append(Paragraph(invoice_data['vendor'], centered_company_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Create left and right columns for invoice info
    left_column = [
        f"<b>Invoice:</b> {invoice_data['invoice_id']}<br/><br/>",
        f"<b>Due Date:</b> {invoice_data['due_date']}<br/><br/>",
        f"<b>Bill To:</b> {invoice_data.get('bill_to_name', 'City Power & Light')}<br/>",
        f"{invoice_data.get('bill_to_address', '250 Grid Rd, Manchester M1 1AE, United Kingdom')}",
    ]
    
    right_column = [
        f"<b>Date:</b> {invoice_data['invoice_date']}<br/><br/>",
        f"<b>Terms:</b> {invoice_data.get('terms', 'Net 30')}<br/><br/>",
        f"<b>Currency:</b> {invoice_data['currency']}",
        "",
    ]
    
    # Two-column layout
    header_data = [
        [
            Paragraph('<br/>'.join(left_column), label_style),
            Paragraph('<br/>'.join(right_column), label_style)
        ]
    ]
    
    header_table = Table(header_data, colWidths=[3.5*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('RIGHTPADDING', (0, 0), (-1, -1), 0),
    ]))
    
    story.append(header_table)
    story.append(Spacer(1, 0.2*inch))
    
    # Add ANCHOR field for Document Intelligence
    anchor_style = ParagraphStyle(
        'Anchor',
        parent=styles['Normal'],
        fontSize=11,
        textColor=colors.black,
    )
    story.append(Paragraph(f"<b>ANCHOR: invoice_id={invoice_data['invoice_id']}</b>", anchor_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Line Items Table with more realistic data
    line_items = invoice_data.get('line_items', [])
    
    # If no line items in manifest, generate sample items based on subtotal
    if not line_items:
        subtotal = invoice_data.get('subtotal', 0)
        if subtotal > 0:
            # Generate 5-8 line items with SKUs
            product_templates = [
                ("Enterprise software subscription (annual)", 399.00),
                ("Laptop workstation", 1199.00),
                ("Premium support (per seat)", 49.00),
                ("Custom integration module", 2499.00),
                ("IoT gateway device", 129.00),
                ("Network firewall appliance", 649.00),
                ("Data migration service (hour)", 145.00),
                ("Cloud storage (per TB-month)", 89.00),
            ]
            
            # Pick random items that sum close to subtotal
            remaining = subtotal
            line_items = []
            for i, (desc, unit_price) in enumerate(product_templates):
                if i == len(product_templates) - 1:
                    # Last item gets remaining amount
                    qty = max(1, int(remaining / unit_price))
                    line_total = remaining
                else:
                    qty = max(1, int((subtotal / len(product_templates)) / unit_price))
                    line_total = qty * unit_price
                    remaining -= line_total
                
                line_items.append({
                    "sku": f"SKU-{1001 + i * 1000 + (i * 202) % 1000}",
                    "description": desc,
                    "quantity": qty,
                    "unit_price": unit_price,
                    "line_total": line_total
                })
    
    # Build line items table with SKU column
    table_data = [
        ['SKU', 'Description', 'Qty', 'Unit Price', 'Line Total']
    ]
    
    for item in line_items:
        # Wrap description in Paragraph to prevent overflow
        desc_paragraph = Paragraph(item.get('description', 'Item'), styles['Normal'])
        table_data.append([
            item.get('sku', 'SKU-0000'),
            desc_paragraph,
            str(item.get('quantity', 1)),
            f"{invoice_data['currency']} {item.get('unit_price', 0):,.2f}",
            f"{invoice_data['currency']} {item.get('line_total', 0):,.2f}"
        ])
    
    items_table = Table(table_data, colWidths=[0.9*inch, 2.7*inch, 0.6*inch, 1.2*inch, 1.2*inch])
    items_table.setStyle(TableStyle([
        # Header row - light gray background exactly like the image
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#e0e0e0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),  # SKU left
        ('ALIGN', (1, 0), (1, 0), 'LEFT'),  # Description left
        ('ALIGN', (2, 0), (2, 0), 'CENTER'),  # Qty center
        ('ALIGN', (3, 0), (-1, 0), 'RIGHT'),  # Prices right
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 0), (-1, 0), 8),
        
        # Data rows - more spacing to match image
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),  # SKU left
        ('ALIGN', (1, 1), (1, -1), 'LEFT'),  # Description left
        ('ALIGN', (2, 1), (2, -1), 'CENTER'),  # Quantity center
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),  # Prices right
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        
        # Grid - simple black lines
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        
        # Word wrap for all cells
        ('WORDWRAP', (0, 0), (-1, -1), True),
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 0.4*inch))
    
    # Totals Section (right-aligned) with proper labels
    subtotal = invoice_data.get('subtotal', 0)
    tax = invoice_data.get('tax', 0)
    shipping = invoice_data.get('shipping', 0)
    total = invoice_data.get('total', 0)
    currency = invoice_data.get('currency', 'USD')
    
    # Calculate tax percentage
    tax_pct = (tax / subtotal * 100) if subtotal > 0 else 7
    
    totals_data = [
        ['', 'Amount (Excl. Tax)', f'{currency} {subtotal:,.2f}'],
        ['', f'VAT Amount ({tax_pct:.0f}%)', f'{currency} {tax:,.2f}'],
        ['', 'Delivery', f'{currency} {shipping:,.2f}'],
        ['', 'Total Amount Due', f'{currency} {total:,.2f}'],
    ]
    
    totals_table = Table(totals_data, colWidths=[3*inch, 2*inch, 1.6*inch])
    totals_table.setStyle(TableStyle([
        # Right align all text
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        
        # Font styling - standard size
        ('FONTNAME', (1, 0), (1, 2), 'Helvetica'),
        ('FONTSIZE', (1, 0), (1, 2), 11),
        ('FONTNAME', (2, 0), (2, 2), 'Helvetica'),
        ('FONTSIZE', (2, 0), (2, 2), 11),
        
        # Total row - bold
        ('FONTNAME', (1, 3), (2, 3), 'Helvetica-Bold'),
        ('FONTSIZE', (1, 3), (2, 3), 11),
        
        # Padding
        ('TOPPADDING', (0, 0), (-1, 2), 4),
        ('BOTTOMPADDING', (0, 0), (-1, 2), 4),
        ('TOPPADDING', (0, 3), (-1, 3), 6),
        ('BOTTOMPADDING', (0, 3), (-1, 3), 4),
    ]))
    
    story.append(totals_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Footer - simple italic text
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Helvetica-Oblique',
    )
    story.append(Paragraph("Thank you for your business.", footer_style))
    
    # Build PDF
    doc.build(story)


def main():
    """Generate realistic invoice PDFs from manifest data"""
    print("="*70)
    print("GENERATING REALISTIC INVOICE PDFs")
    print("="*70)
    
    # Load manifest
    invoices = load_manifest()
    
    if not invoices:
        print("\nNo invoices found in manifest. Exiting.")
        return
    
    print(f"\nFound {len(invoices)} invoices in manifest")
    
    # Create output directory
    output_dir = Path("invoices")
    output_dir.mkdir(exist_ok=True)
    
    # Ask how many to generate
    print(f"\nHow many invoices would you like to generate?")
    print(f"  - Press Enter to generate first 5 (recommended for testing)")
    print(f"  - Type 'all' to generate all {len(invoices)}")
    print(f"  - Type a number (e.g., 10) to generate that many")
    
    user_input = input("\nYour choice: ").strip().lower()
    
    if user_input == 'all':
        count = len(invoices)
    elif user_input == '' or user_input == '5':
        count = min(5, len(invoices))
    else:
        try:
            count = int(user_input)
            count = min(count, len(invoices))
        except ValueError:
            print("Invalid input. Generating first 5 invoices.")
            count = 5
    
    print(f"\nGenerating {count} invoice PDFs...")
    print("-"*70)
    
    # Generate PDFs
    for i, invoice in enumerate(invoices[:count], 1):
        invoice_id = invoice.get('invoice_id', f'INV-{i:04d}')
        output_path = output_dir / f"invoice_{invoice_id}.pdf"
        
        try:
            create_invoice_pdf(invoice, output_path)
            print(f"{i:3d}. {invoice_id:20s} | {invoice['vendor']:30s} | {invoice['currency']} {invoice['total']:>10,.2f}")
        except Exception as e:
            print(f"{i:3d}. {invoice_id:20s} | ERROR: {e}")
    
    print("-"*70)
    print(f"\nSUCCESS: Generated {count} invoice PDFs in '{output_dir}' folder")
    print("\nNext steps:")
    print("1. Run: py create_azure_project.py")
    print("   This will extract data using Document Intelligence and index it")
    print("2. Run: py chatbot.py")
    print("   Test the chatbot with your newly indexed invoices")
    print("\n" + "="*70)


if __name__ == "__main__":
    main()
