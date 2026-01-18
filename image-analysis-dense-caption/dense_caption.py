"""
Azure AI Vision ImageAnalysis Dense Caption Example

This script demonstrates how to use Azure AI Vision to analyze images
and extract dense captions (detailed descriptions for multiple regions).

Features:
    - CAPTION: Single sentence describing the entire image
    - DENSE_CAPTIONS: Up to 10 detailed descriptions for different regions with bounding boxes
    - OBJECTS: Specific objects detected with bounding boxes (~100 types)
    - TAGS: Broad image concepts without bounding boxes (1000+ categories)

Prerequisites:
    pip install azure-ai-vision-imageanalysis python-dotenv pillow

Configuration:
    Create a .env file with:
    VISION_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/
    VISION_KEY=<your-subscription-key>

Supported Regions:
    Dense Captions feature is only available in: eastus, westus, westus2,
    westeurope, francecentral, northeurope, australiaeast, southeastasia,
    japaneast, koreacentral, centralindia

Usage:
    1. Place images in the ./pictures folder
    2. Run: python dense_caption.py
    3. Check ./output folder for results

Output:
    - {image}_analysis.json: Detailed JSON analysis for each image
    - {image}_annotated.png: Image with bounding boxes and tags legend
    - summary_report.json: Machine-readable summary of all images
    - summary_report.txt: Human-readable summary report
"""

# =============================================================================
# IMPORTS
# =============================================================================
import os
import json
import glob
from datetime import datetime
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont
from azure.ai.vision.imageanalysis import ImageAnalysisClient
from azure.ai.vision.imageanalysis.models import VisualFeatures
from azure.core.credentials import AzureKeyCredential

# =============================================================================
# CONFIGURATION
# =============================================================================
# Load environment variables from .env file
load_dotenv()


# =============================================================================
# CREDENTIAL MANAGEMENT
# =============================================================================


def get_credentials():
    """Get Azure AI Vision credentials from .env file."""
    endpoint = os.getenv("VISION_ENDPOINT")
    key = os.getenv("VISION_KEY")
    
    if not endpoint or not key:
        print("Missing VISION_ENDPOINT or VISION_KEY in .env file")
        print("Create a .env file with:")
        print("  VISION_ENDPOINT=https://<your-resource>.cognitiveservices.azure.com/")
        print("  VISION_KEY=<your-subscription-key>")
        exit(1)
    
    return endpoint, key


# =============================================================================
# AZURE AI VISION CLIENT
# =============================================================================
def create_client(endpoint: str, key: str) -> ImageAnalysisClient:
    """Create and return an ImageAnalysisClient."""
    return ImageAnalysisClient(
        endpoint=endpoint,
        credential=AzureKeyCredential(key)
    )


# =============================================================================
# IMAGE ANALYSIS FUNCTIONS
# =============================================================================
def analyze_image_from_url(client: ImageAnalysisClient, image_url: str):
    """
    Analyze an image from URL and extract dense captions.
    
    Args:
        client: The ImageAnalysisClient instance
        image_url: URL of the image to analyze
    
    Returns:
        ImageAnalysisResult object containing analysis results
    """
    result = client.analyze_from_url(
        image_url=image_url,
        visual_features=[
            VisualFeatures.CAPTION,         # Main image description
            VisualFeatures.DENSE_CAPTIONS,  # Detailed regional descriptions
            VisualFeatures.OBJECTS,         # Object detection with bounding boxes
            VisualFeatures.TAGS,            # Broad image concepts/keywords
        ],
        gender_neutral_caption=True,  # Use gender-neutral terms in captions
    )
    return result


def analyze_image_from_file(client: ImageAnalysisClient, image_path: str):
    """
    Analyze an image from local file and extract dense captions.
    
    Args:
        client: The ImageAnalysisClient instance
        image_path: Path to the local image file
    
    Returns:
        ImageAnalysisResult object containing analysis results
    """
    with open(image_path, "rb") as f:
        image_data = f.read()
    
    result = client.analyze(
        image_data=image_data,
        visual_features=[
            VisualFeatures.CAPTION,         # Main image description
            VisualFeatures.DENSE_CAPTIONS,  # Detailed regional descriptions
            VisualFeatures.OBJECTS,         # Object detection with bounding boxes
            VisualFeatures.TAGS,            # Broad image concepts/keywords
        ],
        gender_neutral_caption=True,  # Use gender-neutral terms in captions
    )
    return result


# =============================================================================
# OUTPUT FUNCTIONS
# =============================================================================

def print_results(result):
    """Print the image analysis results to console."""
    print("\n" + "=" * 60)
    print("Image Analysis Results")
    print("=" * 60)
    
    # Print main caption
    if result.caption is not None:
        print("\nMain Caption:")
        print(f"   '{result.caption.text}'")
        print(f"   Confidence: {result.caption.confidence:.4f}")
    
    # Print dense captions (descriptions for multiple regions)
    if result.dense_captions is not None:
        print(f"\nDense Captions ({len(result.dense_captions.list)} regions detected):")
        for i, caption in enumerate(result.dense_captions.list, 1):
            bbox = caption.bounding_box
            print(f"\n   Region {i}:")
            print(f"      Text: '{caption.text}'")
            print(f"      Confidence: {caption.confidence:.4f}")
            print(f"      Bounding Box: x={bbox.x}, y={bbox.y}, w={bbox.width}, h={bbox.height}")
    
    # Print detected objects
    if result.objects is not None and len(result.objects.list) > 0:
        print(f"\nDetected Objects ({len(result.objects.list)} objects):")
        for i, obj in enumerate(result.objects.list, 1):
            bbox = obj.bounding_box
            tag_name = obj.tags[0].name if obj.tags else "unknown"
            tag_conf = obj.tags[0].confidence if obj.tags else 0
            print(f"   {i}. '{tag_name}' (Confidence: {tag_conf:.4f})")
            print(f"      Bounding Box: x={bbox.x}, y={bbox.y}, w={bbox.width}, h={bbox.height}")
    
    # Print tags (broader image concepts)
    if result.tags is not None and len(result.tags.list) > 0:
        print(f"\nImage Tags ({len(result.tags.list)} tags):")
        for tag in result.tags.list:
            print(f"   - '{tag.name}' (Confidence: {tag.confidence:.4f})")
    
    # Print image metadata
    print(f"\nImage Metadata:")
    print(f"   Width: {result.metadata.width}px")
    print(f"   Height: {result.metadata.height}px")
    print(f"   Model Version: {result.model_version}")
    print("=" * 60)


def save_results(result, image_source: str, output_dir: str = "output"):
    """
    Save the image analysis results to a JSON file in the output folder.
    
    Args:
        result: The ImageAnalysisResult object
        image_source: The source of the image (URL or file path)
        output_dir: Directory to save the output file
    
    Returns:
        Path to the saved file
    """
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Build results dictionary
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "image_source": image_source,
        "metadata": {
            "width": result.metadata.width,
            "height": result.metadata.height,
            "model_version": result.model_version
        },
        "caption": None,
        "dense_captions": [],
        "objects": [],
        "tags": []
    }
    
    # Add main caption
    if result.caption is not None:
        output_data["caption"] = {
            "text": result.caption.text,
            "confidence": result.caption.confidence
        }
    
    # Add dense captions
    if result.dense_captions is not None:
        for caption in result.dense_captions.list:
            bbox = caption.bounding_box
            output_data["dense_captions"].append({
                "text": caption.text,
                "confidence": caption.confidence,
                "bounding_box": {
                    "x": bbox.x,
                    "y": bbox.y,
                    "width": bbox.width,
                    "height": bbox.height
                }
            })
    
    # Add detected objects
    if result.objects is not None:
        for obj in result.objects.list:
            bbox = obj.bounding_box
            tag_name = obj.tags[0].name if obj.tags else "unknown"
            tag_conf = obj.tags[0].confidence if obj.tags else 0
            output_data["objects"].append({
                "name": tag_name,
                "confidence": tag_conf,
                "bounding_box": {
                    "x": bbox.x,
                    "y": bbox.y,
                    "width": bbox.width,
                    "height": bbox.height
                }
            })
    
    # Add tags (broader image concepts)
    if result.tags is not None:
        for tag in result.tags.list:
            output_data["tags"].append({
                "name": tag.name,
                "confidence": tag.confidence
            })
    
    # Generate filename based on image source
    if os.path.isfile(image_source):
        base_name = os.path.splitext(os.path.basename(image_source))[0]
        filename = f"{base_name}_analysis.json"
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"url_analysis_{timestamp}.json"
    
    filepath = os.path.join(output_dir, filename)
    
    # Save to file
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\nResults saved to: {filepath}")
    return filepath, output_data


def generate_annotated_image(image_path: str, result, output_dir: str = "output"):
    """
    Generate an annotated image with bounding boxes and labels for detected objects.
    
    Args:
        image_path: Path to the original image
        result: The ImageAnalysisResult object
        output_dir: Directory to save the annotated image
    
    Returns:
        Path to the saved annotated image
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # Open the original image
    img = Image.open(image_path)
    draw = ImageDraw.Draw(img)
    
    # Try to load a font, fall back to default if not available
    try:
        # Try common font paths
        font_size = max(12, min(img.width, img.height) // 40)
        font_paths = [
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc"
        ]
        font = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                font = ImageFont.truetype(font_path, font_size)
                break
        if font is None:
            font = ImageFont.load_default()
    except:
        font = ImageFont.load_default()
    
    # Define colors for different object types
    colors = [
        (255, 0, 0),      # Red
        (0, 255, 0),      # Green
        (0, 0, 255),      # Blue
        (255, 255, 0),    # Yellow
        (255, 0, 255),    # Magenta
        (0, 255, 255),    # Cyan
        (255, 128, 0),    # Orange
        (128, 0, 255),    # Purple
        (0, 128, 255),    # Light Blue
        (255, 0, 128),    # Pink
    ]
    
    # Draw bounding boxes for detected objects
    if result.objects is not None:
        for i, obj in enumerate(result.objects.list):
            bbox = obj.bounding_box
            tag_name = obj.tags[0].name if obj.tags else "unknown"
            tag_conf = obj.tags[0].confidence if obj.tags else 0
            
            # Get color for this object
            color = colors[i % len(colors)]
            
            # Draw rectangle
            x1, y1 = bbox.x, bbox.y
            x2, y2 = bbox.x + bbox.width, bbox.y + bbox.height
            draw.rectangle([x1, y1, x2, y2], outline=color, width=3)
            
            # Create label text
            label = f"{tag_name} ({tag_conf:.0%})"
            
            # Get text bounding box for background
            text_bbox = draw.textbbox((x1, y1), label, font=font)
            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]
            
            # Draw background rectangle for text
            padding = 4
            bg_x1 = x1
            bg_y1 = y1 - text_height - padding * 2 if y1 > text_height + padding * 2 else y2
            bg_x2 = x1 + text_width + padding * 2
            bg_y2 = bg_y1 + text_height + padding * 2
            
            draw.rectangle([bg_x1, bg_y1, bg_x2, bg_y2], fill=color)
            
            # Draw text in black for better readability
            text_x = bg_x1 + padding
            text_y = bg_y1 + padding
            draw.text((text_x, text_y), label, fill=(0, 0, 0), font=font)
    
    # Add tags legend at the bottom of the image
    if result.tags is not None and len(result.tags.list) > 0:
        # Get top tags (limit to avoid overflow)
        top_tags = [tag.name for tag in result.tags.list[:15]]
        tags_text = "Tags: " + ", ".join(top_tags)
        
        # Calculate text size
        tags_bbox = draw.textbbox((0, 0), tags_text, font=font)
        tags_width = tags_bbox[2] - tags_bbox[0]
        tags_height = tags_bbox[3] - tags_bbox[1]
        
        # Create a new image with extra space at bottom for tags
        new_height = img.height + tags_height + 20
        new_img = Image.new("RGB", (img.width, new_height), (255, 255, 255))
        new_img.paste(img, (0, 0))
        
        # Draw tags on the white bar at bottom
        new_draw = ImageDraw.Draw(new_img)
        
        # Wrap text if too long
        if tags_width > img.width - 20:
            # Split tags into multiple lines
            lines = []
            current_line = "Tags: "
            for tag in top_tags:
                test_line = current_line + tag + ", "
                test_bbox = new_draw.textbbox((0, 0), test_line, font=font)
                if test_bbox[2] - test_bbox[0] > img.width - 20:
                    lines.append(current_line.rstrip(", "))
                    current_line = tag + ", "
                else:
                    current_line = test_line
            if current_line:
                lines.append(current_line.rstrip(", "))
            
            # Resize image if needed for multiple lines
            total_text_height = len(lines) * (tags_height + 5)
            new_height = img.height + total_text_height + 15
            new_img = Image.new("RGB", (img.width, new_height), (255, 255, 255))
            new_img.paste(img, (0, 0))
            new_draw = ImageDraw.Draw(new_img)
            
            # Draw each line
            y_pos = img.height + 5
            for line in lines:
                new_draw.text((10, y_pos), line, fill=(0, 0, 0), font=font)
                y_pos += tags_height + 5
        else:
            new_draw.text((10, img.height + 5), tags_text, fill=(0, 0, 0), font=font)
        
        img = new_img
    
    # Generate output filename
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    output_filename = f"{base_name}_annotated.png"
    output_path = os.path.join(output_dir, output_filename)
    
    # Save the annotated image
    img.save(output_path)
    print(f"Annotated image saved to: {output_path}")
    
    return output_path


def get_image_files(pictures_dir: str = "pictures"):
    """
    Get all image files from the pictures directory.
    
    Args:
        pictures_dir: Path to the pictures directory
    
    Returns:
        List of image file paths
    """
    supported_extensions = [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"]
    image_files = []
    
    if not os.path.exists(pictures_dir):
        print(f"Pictures directory not found: {pictures_dir}")
        return image_files
    
    for ext in supported_extensions:
        image_files.extend(glob.glob(os.path.join(pictures_dir, f"*{ext}")))
        image_files.extend(glob.glob(os.path.join(pictures_dir, f"*{ext.upper()}")))
    
    return sorted(set(image_files))


def generate_summary_report(all_results: list, output_dir: str = "output"):
    """
    Generate a summary report of all analyzed images with detected objects.
    
    Args:
        all_results: List of tuples (image_path, analysis_data)
        output_dir: Directory to save the report
    """
    os.makedirs(output_dir, exist_ok=True)
    
    report = {
        "report_generated": datetime.now().isoformat(),
        "total_images_analyzed": len(all_results),
        "images": []
    }
    
    # Collect all unique objects across all images
    all_objects_summary = {}
    
    for image_path, data in all_results:
        image_name = os.path.basename(image_path) if os.path.isfile(image_path) else image_path
        
        # Get objects for this image
        objects_in_image = []
        if "objects" in data:
            for obj in data["objects"]:
                obj_name = obj["name"]
                objects_in_image.append({
                    "name": obj_name,
                    "confidence": obj["confidence"]
                })
                # Track in summary
                if obj_name not in all_objects_summary:
                    all_objects_summary[obj_name] = []
                all_objects_summary[obj_name].append(image_name)
        
        # Get tags for this image
        tags_in_image = [tag["name"] for tag in data.get("tags", [])]
        
        image_entry = {
            "file": image_name,
            "caption": data.get("caption", {}).get("text", "N/A") if data.get("caption") else "N/A",
            "objects_detected": objects_in_image,
            "tags": tags_in_image,
            "dense_captions_count": len(data.get("dense_captions", []))
        }
        report["images"].append(image_entry)
    
    # Add objects summary (which objects appear in which files)
    report["objects_summary"] = []
    for obj_name, files in sorted(all_objects_summary.items()):
        report["objects_summary"].append({
            "object": obj_name,
            "count": len(files),
            "found_in_files": files
        })
    
    # Save JSON report
    report_path = os.path.join(output_dir, "summary_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    # Generate text report
    text_report_path = os.path.join(output_dir, "summary_report.txt")
    with open(text_report_path, "w", encoding="utf-8") as f:
        f.write("="*70 + "\n")
        f.write("AZURE AI VISION - IMAGE ANALYSIS SUMMARY REPORT\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("="*70 + "\n\n")
        
        f.write(f"Total Images Analyzed: {len(all_results)}\n\n")
        
        f.write("-"*70 + "\n")
        f.write("OBJECTS DETECTED BY FILE\n")
        f.write("-"*70 + "\n\n")
        
        for image_entry in report["images"]:
            f.write(f"File: {image_entry['file']}\n")
            f.write(f"  Caption: {image_entry['caption']}\n")
            if image_entry["objects_detected"]:
                f.write(f"  Objects ({len(image_entry['objects_detected'])}):\n")
                for obj in image_entry["objects_detected"]:
                    f.write(f"    - {obj['name']} (confidence: {obj['confidence']:.2%})\n")
            else:
                f.write("  Objects: None detected\n")
            
            # Write tags
            if image_entry.get("tags"):
                f.write(f"  Tags ({len(image_entry['tags'])}): {', '.join(image_entry['tags'])}\n")
            f.write("\n")
        
        f.write("-"*70 + "\n")
        f.write("OBJECTS SUMMARY (Object -> Files)\n")
        f.write("-"*70 + "\n\n")
        
        for obj_summary in report["objects_summary"]:
            f.write(f"{obj_summary['object']} (found {obj_summary['count']} time(s)):\n")
            for file in obj_summary["found_in_files"]:
                f.write(f"    - {file}\n")
            f.write("\n")
    
    print(f"\n" + "="*60)
    print("SUMMARY REPORT GENERATED")
    print("="*60)
    print(f"JSON Report: {report_path}")
    print(f"Text Report: {text_report_path}")
    print(f"Total images analyzed: {len(all_results)}")
    print(f"Unique objects detected: {len(all_objects_summary)}")
    
    return report_path


def main():
    """Main function to analyze all images in the pictures folder."""
    
    # Get credentials
    endpoint, key = get_credentials()
    
    # Create client
    client = create_client(endpoint, key)
    
    print("\nAzure AI Vision - Dense Caption & Object Detection Analysis")
    print("="*60)
    
    # Configuration
    pictures_dir = "pictures"
    output_dir = "output"
    
    # Get all image files from pictures folder
    image_files = get_image_files(pictures_dir)
    
    if not image_files:
        print(f"\nNo images found in '{pictures_dir}' folder.")
        print("Supported formats: .jpg, .jpeg, .png, .gif, .bmp, .webp")
        return
    
    print(f"\nFound {len(image_files)} image(s) in '{pictures_dir}' folder")
    print("-"*60)
    
    # Store all results for summary report
    all_results = []
    
    # Analyze each image
    for i, image_path in enumerate(image_files, 1):
        image_name = os.path.basename(image_path)
        print(f"\n[{i}/{len(image_files)}] Analyzing: {image_name}")
        
        try:
            result = analyze_image_from_file(client, image_path)
            print_results(result)
            filepath, output_data = save_results(result, image_path, output_dir)
            all_results.append((image_path, output_data))
            
            # Generate annotated image with bounding boxes
            generate_annotated_image(image_path, result, output_dir)
        except Exception as e:
            print(f"   Error analyzing {image_name}: {str(e)}")
            continue
    
    # Generate summary report
    if all_results:
        generate_summary_report(all_results, output_dir)


if __name__ == "__main__":
    main()
