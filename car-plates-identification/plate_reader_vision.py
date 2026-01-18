"""
License Plate Reader using Azure AI Vision - Image Analysis (Read OCR)
================================================================================

This script performs the following workflow:
1. Scans all images in the 'pictures' folder
2. Sends each image to Azure AI Vision's Read OCR API
3. Extracts text and identifies potential license plates using pattern matching
4. Draws green bounding boxes around detected plates
5. Saves annotated images to the 'output-vision' folder
6. Displays a summary of all detected plates

Requirements:
- Azure AI Vision resource (Computer Vision) with valid endpoint and API key
- Python packages: azure-ai-vision-imageanalysis, Pillow, python-dotenv

Usage:
    python plate_reader_vision.py
"""

# =============================================================================
# IMPORTS
# =============================================================================
import os
import re
import csv
import json
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

# =============================================================================
# CONFIGURATION
# =============================================================================
# Load environment variables from .env file (AZURE_VISION_ENDPOINT, AZURE_VISION_API_KEY)
load_dotenv()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_license_plate(text: str) -> bool:
    """
    Determine if the detected text matches typical license plate patterns.
    
    License plate identification heuristics:
    - Length: Most plates are 3-12 characters (after removing spaces/special chars)
    - Content: Usually contains a mix of letters and numbers
    - Pattern: Alphanumeric combinations are strong indicators
    
    Args:
        text: The text string to analyze
        
    Returns:
        True if the text appears to be a license plate, False otherwise
        
    Examples:
        >>> is_license_plate("ABC 1234")  # Returns True
        >>> is_license_plate("HELLO")     # Returns True (could be vanity plate)
        >>> is_license_plate("The quick") # Returns False (too long, no numbers)
    """
    # Step 1: Clean the text - remove spaces and special characters
    clean_text = re.sub(r'[^A-Za-z0-9]', '', text)
    
    # Step 2: Check length constraints
    # License plates are typically 3-12 characters
    if len(clean_text) < 3 or len(clean_text) > 12:
        return False
    
    # Step 3: Check for alphanumeric content
    has_letter = any(c.isalpha() for c in clean_text)
    has_digit = any(c.isdigit() for c in clean_text)
    
    # Step 4: Return True if text contains letters OR digits
    # Most license plates have both, but vanity plates may be letters only
    return has_letter or has_digit


def get_bounding_box_from_polygon(polygon: list) -> tuple:
    """
    Convert a polygon (list of x,y coordinates) to a rectangular bounding box.
    
    Azure Vision returns text positions as 4-point polygons (quadrilaterals).
    This function converts them to simple rectangles for easier drawing.
    
    Args:
        polygon: List of coordinates in format [x1, y1, x2, y2, x3, y3, x4, y4]
                 representing the four corners of the text region
                 
    Returns:
        Tuple of (left, top, right, bottom) representing the bounding rectangle
        
    Example:
        >>> polygon = [10, 20, 100, 20, 100, 50, 10, 50]
        >>> get_bounding_box_from_polygon(polygon)
        (10, 20, 100, 50)
    """
    # Extract all X coordinates (even indices: 0, 2, 4, 6)
    x_coords = [polygon[i] for i in range(0, len(polygon), 2)]
    
    # Extract all Y coordinates (odd indices: 1, 3, 5, 7)
    y_coords = [polygon[i] for i in range(1, len(polygon), 2)]
    
    # Return the bounding rectangle: (left, top, right, bottom)
    return (min(x_coords), min(y_coords), max(x_coords), max(y_coords))


# =============================================================================
# IMAGE ANNOTATION FUNCTION
# =============================================================================

def draw_plate_boxes(image_path: str, detected_plates: list, output_path: str) -> str:
    """
    Create an annotated copy of the image with bounding boxes around detected plates.
    
    This function:
    1. Opens the original image
    2. Draws green rectangles around each detected plate
    3. Adds corner markers for better visibility
    4. Labels each plate with its text and confidence score
    5. Saves the annotated image to the output path
    
    Args:
        image_path: Path to the original image file
        detected_plates: List of plate dictionaries, each containing:
                        - 'text': The plate text
                        - 'polygon': Bounding coordinates [x1,y1,x2,y2,x3,y3,x4,y4]
                        - 'confidence': Detection confidence (0.0 to 1.0)
        output_path: Path where the annotated image will be saved
        
    Returns:
        The output path where the annotated image was saved
    """
    # ----- Step 1: Load the original image -----
    image = Image.open(image_path)
    draw = ImageDraw.Draw(image)
    
    # ----- Step 2: Configure fonts for labels -----
    # Try to load Arial font; fall back to default if not available
    try:
        font = ImageFont.truetype("arial.ttf", 20)       # Main label font
        small_font = ImageFont.truetype("arial.ttf", 14) # Reserved for future use
    except (IOError, OSError):
        # Font file not found - use PIL's default bitmap font
        font = ImageFont.load_default()
        small_font = font
    
    # ----- Step 3: Define colors for annotations -----
    box_color = (0, 255, 0)       # Green for bounding boxes
    text_bg_color = (0, 255, 0, 200)  # Green with transparency (unused)
    text_color = (0, 0, 0)        # Black for label text
    
    # ----- Step 4: Draw annotations for each detected plate -----
    for plate in detected_plates:
        polygon = plate["polygon"]
        text = plate["text"]
        confidence = plate.get("confidence", 0)
        
        # Calculate the bounding box from the polygon
        bbox = get_bounding_box_from_polygon(polygon)
        left, top, right, bottom = bbox
        
        # ----- Draw the main bounding rectangle -----
        line_width = 3
        draw.rectangle([left, top, right, bottom], outline=box_color, width=line_width)
        
        # ----- Draw corner markers for enhanced visibility -----
        # Corner markers make the box stand out more in busy images
        corner_length = 15
        
        # Top-left corner (horizontal and vertical lines)
        draw.line([(left, top), (left + corner_length, top)], fill=box_color, width=line_width + 2)
        draw.line([(left, top), (left, top + corner_length)], fill=box_color, width=line_width + 2)
        
        # Top-right corner
        draw.line([(right - corner_length, top), (right, top)], fill=box_color, width=line_width + 2)
        draw.line([(right, top), (right, top + corner_length)], fill=box_color, width=line_width + 2)
        
        # Bottom-left corner
        draw.line([(left, bottom - corner_length), (left, bottom)], fill=box_color, width=line_width + 2)
        draw.line([(left, bottom), (left + corner_length, bottom)], fill=box_color, width=line_width + 2)
        
        # Bottom-right corner
        draw.line([(right - corner_length, bottom), (right, bottom)], fill=box_color, width=line_width + 2)
        draw.line([(right, bottom - corner_length), (right, bottom)], fill=box_color, width=line_width + 2)
        
        # ----- Draw the label with plate text and confidence -----
        label = f"{text} ({confidence:.0%})"
        
        # Calculate label dimensions for proper positioning
        text_bbox = draw.textbbox((0, 0), label, font=font)
        text_width = text_bbox[2] - text_bbox[0]
        text_height = text_bbox[3] - text_bbox[1]
        
        # Position label above the bounding box (or below if no room)
        label_x = left
        label_y = top - text_height - 8
        if label_y < 0:  # If label would go above image edge, put it below the box
            label_y = bottom + 4
        
        # Draw a filled background rectangle for the label (improves readability)
        padding = 4
        draw.rectangle(
            [label_x - padding, label_y - padding, 
             label_x + text_width + padding, label_y + text_height + padding],
            fill=box_color
        )
        
        # Draw the label text on top of the background
        draw.text((label_x, label_y), label, fill=text_color, font=font)
    
    # ----- Step 5: Save the annotated image -----
    image.save(output_path)
    return output_path


# =============================================================================
# AZURE AI VISION OCR FUNCTION
# =============================================================================

def extract_plate_with_position(client: ImageAnalysisClient, image_path: str) -> dict:
    """
    Use Azure AI Vision Read OCR to extract text from an image and identify license plates.
    
    This function:
    1. Reads the image file as binary data
    2. Sends it to Azure AI Vision's Read OCR API
    3. Iterates through all detected text blocks and lines
    4. Filters text that matches license plate patterns
    5. Returns plate text with bounding coordinates and confidence scores
    
    Args:
        client: Authenticated ImageAnalysisClient instance
        image_path: Path to the image file to analyze
        
    Returns:
        Dictionary containing:
        - 'image': Image filename
        - 'image_path': Full path to the image
        - 'detected_plates': List of detected plates with text, polygon, confidence
        - 'all_text': List of all text detected in the image
        - 'status': 'success' or 'error'
        - 'error': Error message (only if status is 'error')
    """
    image_name = os.path.basename(image_path)
    
    try:
        # ----- Step 1: Read the image file as binary data -----
        with open(image_path, "rb") as f:
            image_data = f.read()
        
        # ----- Step 2: Call Azure AI Vision Read OCR API -----
        # VisualFeatures.READ enables text extraction (OCR)
        result = client.analyze(
            image_data=image_data,
            visual_features=[VisualFeatures.READ]
        )
        
        detected_plates = []
        all_text = []
        
        # ----- Step 3: Process OCR results -----
        if result.read is not None:
            # Iterate through text blocks (regions of text)
            for block in result.read.blocks:
                # Iterate through lines within each block
                for line in block.lines:
                    line_text = line.text
                    all_text.append(line_text)
                    
                    # ----- Step 4: Check if this line matches license plate pattern -----
                    if is_license_plate(line_text):
                        # Extract bounding polygon coordinates
                        polygon = []
                        if line.bounding_polygon:
                            for point in line.bounding_polygon:
                                polygon.extend([point.x, point.y])
                        
                        # Calculate average confidence from individual word confidences
                        word_confidences = [word.confidence for word in line.words if hasattr(word, 'confidence')]
                        avg_confidence = sum(word_confidences) / len(word_confidences) if word_confidences else 0.0
                        
                        # ----- Step 5: Store plate information -----
                        detected_plates.append({
                            "text": line_text,           # The plate text
                            "polygon": polygon,          # Bounding coordinates
                            "confidence": avg_confidence, # OCR confidence score
                            "words": [                   # Individual word details
                                {
                                    "text": word.text,
                                    "confidence": getattr(word, 'confidence', 0.0),
                                    "polygon": [p.x for p in word.bounding_polygon] + [p.y for p in word.bounding_polygon] if word.bounding_polygon else []
                                }
                                for word in line.words
                            ]
                        })
        
        # Return successful result with all extracted data
        return {
            "image": image_name,
            "image_path": image_path,
            "detected_plates": detected_plates,
            "all_text": all_text,
            "status": "success"
        }
        
    except Exception as e:
        # Return error result if OCR fails
        return {
            "image": image_name,
            "image_path": image_path,
            "detected_plates": [],
            "all_text": [],
            "status": "error",
            "error": str(e)
        }


# =============================================================================
# MAIN FUNCTION
# =============================================================================

def main():
    """
    Main entry point - orchestrates the license plate detection workflow.
    
    Workflow:
    1. Load configuration from environment variables
    2. Validate Azure credentials are configured
    3. Set up input (pictures) and output folders
    4. Initialize Azure AI Vision client
    5. Process each image:
       a. Extract text using OCR
       b. Identify license plates
       c. Generate annotated image with bounding boxes
    6. Display summary of all results
    """
    
    # =========================================================================
    # STEP 1: Load Configuration
    # =========================================================================
    # Read Azure AI Vision credentials from environment variables
    ENDPOINT = os.environ.get("AZURE_VISION_ENDPOINT", "")
    API_KEY = os.environ.get("AZURE_VISION_API_KEY", "")
    
    # =========================================================================
    # STEP 2: Validate Configuration
    # =========================================================================
    if not ENDPOINT or not API_KEY:
        print("=" * 70)
        print("CONFIGURATION REQUIRED")
        print("=" * 70)
        print("\nPlease set the following environment variables in your .env file:")
        print("  - AZURE_VISION_ENDPOINT: Your Azure AI Vision endpoint URL")
        print("  - AZURE_VISION_API_KEY: Your Azure AI Vision API key")
        print("\nExample .env file entries:")
        print('  AZURE_VISION_ENDPOINT=https://your-resource.cognitiveservices.azure.com/')
        print('  AZURE_VISION_API_KEY=your-api-key')
        print("=" * 70)
        return
    
    # =========================================================================
    # STEP 3: Set Up Folder Paths
    # =========================================================================
    script_dir = Path(__file__).parent
    pictures_folder = script_dir / "pictures"     # Input folder with images
    output_folder = script_dir / "output-vision"  # Output folder for annotated images
    
    # Create output folder if it doesn't exist
    output_folder.mkdir(exist_ok=True)
    
    # Verify pictures folder exists
    if not pictures_folder.exists():
        print(f"Error: Pictures folder not found at {pictures_folder}")
        return
    
    # =========================================================================
    # STEP 4: Discover Image Files
    # =========================================================================
    # Supported image formats for Azure AI Vision
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    
    # Get list of all image files in the pictures folder
    image_files = [
        f for f in pictures_folder.iterdir() 
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    
    if not image_files:
        print(f"No image files found in {pictures_folder}")
        return
    
    print(f"Found {len(image_files)} image(s) to process")
    print(f"Output folder: {output_folder}")
    print("=" * 70)
    
    # =========================================================================
    # STEP 5: Initialize Azure AI Vision Client
    # =========================================================================
    client = ImageAnalysisClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(API_KEY)
    )
    
    # =========================================================================
    # STEP 6: Process Each Image
    # =========================================================================
    results = []
    for i, image_path in enumerate(sorted(image_files), 1):
        print(f"\nProcessing [{i}/{len(image_files)}]: {image_path.name}")
        
        # ----- Call Azure AI Vision to extract text and identify plates -----
        result = extract_plate_with_position(client, str(image_path))
        results.append(result)
        
        # ----- Display results for this image -----
        if result["status"] == "success":
            plates = result["detected_plates"]
            if plates:
                # Plates were detected - display details
                print(f"  Found {len(plates)} potential plate(s):")
                for plate in plates:
                    # Get bounding box coordinates for display
                    bbox = get_bounding_box_from_polygon(plate["polygon"]) if plate["polygon"] else "N/A"
                    print(f"    - {plate['text']} (confidence: {plate['confidence']:.2%})")
                    print(f"      Position: {bbox}")
                
                # ----- Generate annotated image with bounding boxes -----
                output_path = output_folder / f"annotated_{image_path.name}"
                
                # Ensure output format is compatible (convert unusual formats to PNG)
                if output_path.suffix.lower() not in ['.png', '.jpg', '.jpeg']:
                    output_path = output_path.with_suffix('.png')
                
                # Draw bounding boxes and save the annotated image
                draw_plate_boxes(str(image_path), plates, str(output_path))
                print(f"  Annotated image saved: {output_path.name}")
            else:
                # No plates detected in this image
                print(f"  No license plates detected")
                # Show first few text items found (for debugging)
                if result["all_text"]:
                    print(f"  All detected text: {', '.join(result['all_text'][:5])}")
        else:
            # OCR failed for this image
            print(f"  Error: {result.get('error', 'Unknown error')}")
    
    # =========================================================================
    # STEP 7: Display Summary Report
    # =========================================================================
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"{'Image':<25} {'Plates Found':<35} {'Status':<10}")
    print("-" * 70)
    
    # Display results for each image in a table format
    for result in results:
        status = "✓" if result["status"] == "success" else "✗"
        plates = ", ".join([p["text"] for p in result["detected_plates"]]) if result["detected_plates"] else "None"
        # Truncate long plate strings for display
        if len(plates) > 33:
            plates = plates[:30] + "..."
        print(f"{result['image']:<25} {plates:<35} {status:<10}")
    
    # =========================================================================
    # STEP 8: Display Statistics
    # =========================================================================
    successful = sum(1 for r in results if r["status"] == "success")
    plates_found = sum(1 for r in results if r["detected_plates"])
    total_plates = sum(len(r["detected_plates"]) for r in results)
    
    print("-" * 70)
    print(f"Total images processed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"Images with plates: {plates_found}")
    print(f"Total plates detected: {total_plates}")
    print(f"Annotated images saved to: {output_folder}")
    
    # =========================================================================
    # STEP 9: Save Results to Files (CSV and JSON)
    # =========================================================================
    # Generate timestamp for filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ----- Save to CSV -----
    csv_file = output_folder / f"vision_results_{timestamp}.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(["Image", "Plate_Number", "Confidence", "Bounding_Box", "Status", "Error"])
        # Write data rows - one row per detected plate
        for result in results:
            if result["status"] == "success" and result["detected_plates"]:
                for plate in result["detected_plates"]:
                    bbox = plate.get("bounding_box", [])
                    bbox_str = f"{bbox}" if bbox else ""
                    writer.writerow([
                        result.get("image", ""),
                        plate.get("text", ""),
                        f"{plate.get('confidence', 0):.2f}",
                        bbox_str,
                        "success",
                        ""
                    ])
            elif result["status"] == "success":
                # No plates found in this image
                writer.writerow([
                    result.get("image", ""),
                    "NO_PLATE_FOUND",
                    "",
                    "",
                    "success",
                    ""
                ])
            else:
                # Error processing this image
                writer.writerow([
                    result.get("image", ""),
                    "",
                    "",
                    "",
                    "error",
                    result.get("error", "Unknown error")
                ])
    
    # ----- Save to JSON -----
    json_file = output_folder / f"vision_results_{timestamp}.json"
    json_output = {
        "timestamp": datetime.now().isoformat(),
        "total_images": len(results),
        "successful": successful,
        "images_with_plates": plates_found,
        "total_plates_detected": total_plates,
        "results": results
    }
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    
    # ----- Also save a "latest" version for easy access -----
    csv_latest = output_folder / "vision_results_latest.csv"
    json_latest = output_folder / "vision_results_latest.json"
    
    # Copy to latest CSV
    with open(csv_latest, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "Plate_Number", "Confidence", "Bounding_Box", "Status", "Error"])
        for result in results:
            if result["status"] == "success" and result["detected_plates"]:
                for plate in result["detected_plates"]:
                    bbox = plate.get("bounding_box", [])
                    bbox_str = f"{bbox}" if bbox else ""
                    writer.writerow([
                        result.get("image", ""),
                        plate.get("text", ""),
                        f"{plate.get('confidence', 0):.2f}",
                        bbox_str,
                        "success",
                        ""
                    ])
            elif result["status"] == "success":
                writer.writerow([
                    result.get("image", ""),
                    "NO_PLATE_FOUND",
                    "",
                    "",
                    "success",
                    ""
                ])
            else:
                writer.writerow([
                    result.get("image", ""),
                    "",
                    "",
                    "",
                    "error",
                    result.get("error", "Unknown error")
                ])
    
    # Copy to latest JSON
    with open(json_latest, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 70)
    print("RESULTS SAVED")
    print("=" * 70)
    print(f"CSV:  {csv_file}")
    print(f"JSON: {json_file}")
    print(f"\nLatest results also saved to:")
    print(f"  - {csv_latest}")
    print(f"  - {json_latest}")


# =============================================================================
# SCRIPT ENTRY POINT
# =============================================================================
if __name__ == "__main__":
    # Run the main function when script is executed directly
    main()
