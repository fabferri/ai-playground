"""
License Plate Reader using Azure AI Foundry (GPT-4o Vision)
================================================================================

This script performs the following workflow:
1. Scans all images in the 'pictures' folder
2. Sends each image to Azure AI Foundry's GPT-4o vision model
3. Uses AI to intelligently identify and extract license plate numbers
4. Displays results with a summary table

Key Features:
- Uses GPT-4o's vision capabilities for intelligent plate recognition
- Handles multiple plates in a single image
- Works with various image formats (JPEG, PNG, GIF, BMP, WebP)
- Low temperature setting for consistent, reliable results

Requirements:
- Azure AI Foundry resource with GPT-4o model deployed
- Python packages: azure-ai-inference, python-dotenv

Usage:
    python plate_reader.py

Configuration:
    Set environment variables in .env file:
    - AZURE_AI_ENDPOINT: Your Azure AI Foundry endpoint URL
    - AZURE_AI_API_KEY: Your Azure AI Foundry API key
    - AZURE_AI_MODEL: Model deployment name (default: gpt-4o)
"""

# =============================================================================
# IMPORTS
# =============================================================================
import os
import io
import csv
import json
import base64
import time
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from PIL import Image
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import SystemMessage, UserMessage, ImageContentItem, ImageUrl, TextContentItem
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import HttpResponseError

# =============================================================================
# CONFIGURATION
# =============================================================================
# Load environment variables from .env file
# This allows secure storage of API keys outside the source code
load_dotenv()


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_image_data_url(image_path: str, max_dimension: int = 1024) -> str:
    """
    Convert an image file to a base64-encoded data URL for the API.
    
    Azure AI Foundry's vision models accept images as data URLs, which embed
    the image data directly in the request. This function:
    1. Opens and optionally resizes the image (for faster API calls)
    2. Determines the correct MIME type based on file extension
    3. Encodes it as base64
    4. Constructs a data URL in the format: data:<mime-type>;base64,<encoded-data>
    
    Args:
        image_path: Full path to the image file
        max_dimension: Maximum width or height (default: 1024px)
        
    Returns:
        A data URL string containing the base64-encoded image
        
    Example:
        >>> url = get_image_data_url("car.jpg")
        >>> url[:30]
        'data:image/jpeg;base64,/9j/4AA'
    """
    # ----- Step 1: Determine MIME type from file extension -----
    extension = Path(image_path).suffix.lower()
    
    # Mapping of file extensions to MIME types
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".webp": "image/webp"
    }
    
    # Default to JPEG if extension not recognized
    mime_type = mime_types.get(extension, "image/jpeg")
    output_format = "JPEG" if mime_type == "image/jpeg" else "PNG"
    
    # ----- Step 2: Open and resize image if needed -----
    with Image.open(image_path) as img:
        # Convert to RGB if necessary (for JPEG output)
        if img.mode in ('RGBA', 'P') and output_format == 'JPEG':
            img = img.convert('RGB')
        elif img.mode != 'RGB' and output_format == 'JPEG':
            img = img.convert('RGB')
        
        # Resize if larger than max_dimension
        width, height = img.size
        if width > max_dimension or height > max_dimension:
            # Calculate new size maintaining aspect ratio
            if width > height:
                new_width = max_dimension
                new_height = int(height * (max_dimension / width))
            else:
                new_height = max_dimension
                new_width = int(width * (max_dimension / height))
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
        
        # ----- Step 3: Encode to base64 -----
        buffer = io.BytesIO()
        img.save(buffer, format=output_format, quality=85)
        image_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
    
    # ----- Step 4: Construct and return the data URL -----
    return f"data:{mime_type};base64,{image_data}"


def retry_with_backoff(func, max_retries: int = 3, base_delay: float = 1.0):
    """
    Retry a function with exponential backoff for transient errors.
    
    Handles common transient errors:
    - 429: Rate limit exceeded (Too Many Requests)
    - 503: Service temporarily unavailable
    - 500: Internal server error
    - Connection errors
    
    Args:
        func: Function to call (should be a lambda or callable)
        max_retries: Maximum number of retry attempts (default: 3)
        base_delay: Initial delay in seconds, doubles each retry (default: 1.0)
        
    Returns:
        The result of the function call
        
    Raises:
        The last exception if all retries fail
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return func()
        except HttpResponseError as e:
            last_exception = e
            # Check if error is retryable
            if e.status_code in (429, 500, 503):
                if attempt < max_retries:
                    # Calculate delay with exponential backoff
                    delay = base_delay * (2 ** attempt)
                    # Check for Retry-After header
                    retry_after = getattr(e, 'retry_after', None)
                    if retry_after:
                        delay = max(delay, float(retry_after))
                    print(f"    Retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...")
                    time.sleep(delay)
                    continue
            raise  # Non-retryable error, raise immediately
        except (ConnectionError, TimeoutError) as e:
            last_exception = e
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                print(f"    Connection error, retrying in {delay:.1f}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                continue
            raise
    
    raise last_exception


# =============================================================================
# PLATE EXTRACTION FUNCTION
# =============================================================================

def extract_plate_number(client: ChatCompletionsClient, image_path: str, model: str) -> dict:
    """
    Extract license plate number(s) from an image using Azure AI Foundry's vision model.
    
    This function sends the image to GPT-4o with a specialized prompt that instructs
    the AI to act as a license plate recognition expert. The model analyzes the image
    and returns only the plate text, without additional explanation.
    
    Workflow:
    1. Convert image to base64 data URL
    2. Send to Azure AI Foundry with system prompt for plate extraction
    3. Parse response and return structured result
    
    Args:
        client: Authenticated ChatCompletionsClient instance
        image_path: Full path to the image file to analyze
        model: Name of the deployed model (e.g., "gpt-4o")
        
    Returns:
        Dictionary containing:
        - 'image': Filename of the processed image
        - 'plate_number': Extracted plate text (or 'NO_PLATE_FOUND')
        - 'status': 'success' or 'error'
        - 'error': Error message (only if status is 'error')
        
    Example:
        >>> result = extract_plate_number(client, "car.jpg", "gpt-4o")
        >>> print(result)
        {'image': 'car.jpg', 'plate_number': 'ABC 1234', 'status': 'success'}
    """
    # Get just the filename for display purposes
    image_name = os.path.basename(image_path)
    
    try:
        # ----- Step 1: Convert image to base64 data URL -----
        # This embeds the image data directly in the API request
        image_data_url = get_image_data_url(image_path)
        
        # ----- Step 2: Send request to Azure AI Foundry with retry logic -----
        # The system message defines the AI's role and behavior
        # The user message contains the instruction and the image
        
        # Optimized system prompt with structured JSON output
        system_prompt = """You are an expert license plate recognition system. Be CRITICAL and CONSERVATIVE with confidence scores.

Your task: Analyze the image and extract ALL visible license plate numbers.

Output Format: Return ONLY valid JSON matching this schema:
{
  "plates": [
    {
      "text": "<plate number with original spacing/formatting>",
      "confidence": <0.0-1.0>,
      "country": "<detected country/region or 'unknown'>"
    }
  ],
  "found": <true/false>
}

STRICT Confidence Scoring Rules (BE HONEST - do NOT default to 1.0):
- 0.95-1.0: ONLY if plate is perfectly clear, well-lit, high resolution, no obstruction, ALL characters 100% certain
- 0.80-0.94: Clear plate but minor issues (slight angle, small size, minor blur)
- 0.60-0.79: Readable but has issues (partial obstruction, moderate blur, poor lighting, some characters uncertain)
- 0.40-0.59: Difficult to read (significant blur, far distance, partial visibility, guessing some characters)
- 0.20-0.39: Very uncertain (heavy obstruction, very blurry, only partial plate visible)
- <0.20: Mostly guessing (barely visible, extreme conditions)

IMPORTANT: Most real-world plates are NOT perfect. Use 0.7-0.9 for typical plates. Reserve 1.0 ONLY for studio-quality images.

Other Rules:
1. Extract plate text EXACTLY as shown (preserve spacing, hyphens, special chars)
2. If NO plate is visible or readable, return: {"plates": [], "found": false}
3. Detect country/region from plate format (e.g., "US-California", "EU-Germany", "UK")
4. Return ONLY the JSON object, no markdown, no explanation
5. If multiple plates in image, score EACH plate independently based on its clarity"""
        
        # Wrap API call in retry logic for transient errors
        def make_api_call():
            return client.complete(
                model=model,
                messages=[
                    SystemMessage(content=system_prompt),
                    UserMessage(content=[
                        TextContentItem(text="Analyze this image and extract all license plate numbers:"),
                        ImageContentItem(image_url=ImageUrl(url=image_data_url))
                    ])
                ],
                max_tokens=200,      # Increased for JSON structure
                temperature=0.0      # Zero temperature for maximum consistency
            )
        
        # Execute with retry logic
        response = retry_with_backoff(make_api_call, max_retries=3, base_delay=1.0)
        
        # ----- Step 3: Parse JSON response -----
        raw_response = response.choices[0].message.content.strip()
        
        # Clean response (remove markdown code blocks if present)
        if raw_response.startswith("```"):
            raw_response = raw_response.split("```")[1]
            if raw_response.startswith("json"):
                raw_response = raw_response[4:]
            raw_response = raw_response.strip()
        
        try:
            parsed = json.loads(raw_response)
            plates = parsed.get("plates", [])
            
            if plates:
                # Format multiple plates with confidence
                plate_texts = []
                confidences = []
                for p in plates:
                    plate_texts.append(p.get("text", "UNKNOWN"))
                    confidences.append(p.get("confidence", 0.0))
                
                plate_number = ", ".join(plate_texts)
                avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            else:
                plate_number = "NO_PLATE_FOUND"
                avg_confidence = 1.0  # Confident no plate exists
                
        except json.JSONDecodeError:
            # Fallback: treat response as plain text (backward compatibility)
            plate_number = raw_response if raw_response else "NO_PLATE_FOUND"
            avg_confidence = 0.5  # Unknown confidence for non-JSON response
        
        # Return successful result with confidence
        return {
            "image": image_name,
            "plate_number": plate_number,
            "confidence": avg_confidence,
            "status": "success"
        }
        
    except Exception as e:
        # Return error result if API call fails
        return {
            "image": image_name,
            "plate_number": None,
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
    3. Discover image files in the pictures folder
    4. Initialize Azure AI Foundry client
    5. Process each image and extract plate numbers
    6. Display results in a formatted summary table
    7. Show statistics (success rate, plates found, errors)
    """
    
    # =========================================================================
    # STEP 1: Load Configuration from Environment Variables
    # =========================================================================
    # These values should be set in the .env file or as system environment variables
    ENDPOINT = os.environ.get("AZURE_AI_ENDPOINT", "https://<your-resource>.services.ai.azure.com/models")
    API_KEY = os.environ.get("AZURE_AI_API_KEY", "<your-api-key>")
    MODEL = os.environ.get("AZURE_AI_MODEL", "gpt-4o")  # GPT-4o has vision capabilities
    
    # =========================================================================
    # STEP 2: Validate Configuration
    # =========================================================================
    # Check if placeholder values are still present (not configured)
    if "<your-" in ENDPOINT or "<your-" in API_KEY:
        print("=" * 60)
        print("CONFIGURATION REQUIRED")
        print("=" * 60)
        print("\nPlease set the following environment variables:")
        print("  - AZURE_AI_ENDPOINT: Your Azure AI Foundry endpoint URL")
        print("  - AZURE_AI_API_KEY: Your Azure AI Foundry API key")
        print("  - AZURE_AI_MODEL: Model deployment name (default: gpt-4o)")
        print("\nExample (PowerShell):")
        print('  $env:AZURE_AI_ENDPOINT = "https://your-resource.services.ai.azure.com/models"')
        print('  $env:AZURE_AI_API_KEY = "your-api-key"')
        print('  $env:AZURE_AI_MODEL = "gpt-4o"')
        print("\nOr modify the values directly in this script.")
        print("=" * 60)
        return
    
    # =========================================================================
    # STEP 3: Set Up Folder Paths and Discover Images
    # =========================================================================
    # Determine the script's directory to find the pictures folder
    script_dir = Path(__file__).parent
    pictures_folder = script_dir / "pictures"
    
    # Verify the pictures folder exists
    if not pictures_folder.exists():
        print(f"Error: Pictures folder not found at {pictures_folder}")
        return
    
    # Define supported image formats (Azure AI vision can process these)
    image_extensions = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
    
    # Get list of all image files in the pictures folder
    image_files = [
        f for f in pictures_folder.iterdir() 
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    
    # Check if any images were found
    if not image_files:
        print(f"No image files found in {pictures_folder}")
        return
    
    print(f"Found {len(image_files)} image(s) to process")
    print("=" * 60)
    
    # =========================================================================
    # STEP 4: Initialize Azure AI Foundry Client
    # =========================================================================
    # Create the client with endpoint URL and API key authentication
    client = ChatCompletionsClient(
        endpoint=ENDPOINT,
        credential=AzureKeyCredential(API_KEY)
    )
    # =========================================================================
    # STEP 5: Process Each Image
    # =========================================================================
    results = []
    for i, image_path in enumerate(sorted(image_files), 1):
        # Display progress indicator
        print(f"\nProcessing [{i}/{len(image_files)}]: {image_path.name}")
        
        # ----- Call Azure AI Foundry to extract plate number -----
        result = extract_plate_number(client, str(image_path), MODEL)
        results.append(result)
        
        # ----- Display result for this image -----
        if result["status"] == "success":
            confidence = result.get('confidence', 0.0)
            print(f"  Plate Number: {result['plate_number']} (confidence: {confidence:.0%})")
        else:
            print(f"  Error: {result.get('error', 'Unknown error')}")
    
    # =========================================================================
    # STEP 6: Display Summary Table
    # =========================================================================
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    # Print table header
    print(f"{'Image':<25} {'Plate Number':<25} {'Confidence':<12} {'Status':<10}")
    print("-" * 72)
    
    # Print each result in the table
    for result in results:
        # Use checkmark for success, X for error
        status = "✓" if result["status"] == "success" else "✗"
        # Handle None or empty plate numbers
        plate = result.get("plate_number", "N/A") or "N/A"
        # Format confidence as percentage
        confidence = result.get("confidence", 0.0)
        conf_str = f"{confidence:.0%}" if result["status"] == "success" else "N/A"
        print(f"{result['image']:<25} {plate:<25} {conf_str:<12} {status:<10}")
    
    # =========================================================================
    # STEP 7: Display Statistics
    # =========================================================================
    # Calculate summary statistics
    successful = sum(1 for r in results if r["status"] == "success")
    plates_found = sum(1 for r in results if r["status"] == "success" and r["plate_number"] != "NO_PLATE_FOUND")
    
    print("-" * 72)
    print(f"Total processed: {len(results)}")     # Total images attempted
    print(f"Successful: {successful}")             # API calls that succeeded
    print(f"Plates found: {plates_found}")         # Images where plates were detected
    print(f"Errors: {len(results) - successful}")  # API calls that failed
    
    # Calculate average confidence for successful detections
    confident_results = [r.get("confidence", 0) for r in results 
                         if r["status"] == "success" and r["plate_number"] != "NO_PLATE_FOUND"]
    if confident_results:
        avg_confidence = sum(confident_results) / len(confident_results)
        print(f"Avg confidence: {avg_confidence:.0%}")
    
    # =========================================================================
    # STEP 8: Save Results to Files (CSV and JSON)
    # =========================================================================
    # Create output folder if it doesn't exist
    output_folder = script_dir / "output"
    output_folder.mkdir(exist_ok=True)
    
    # Generate timestamp for filenames
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # ----- Save to CSV -----
    csv_file = output_folder / f"plate_results_{timestamp}.csv"
    with open(csv_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        # Write header
        writer.writerow(["Image", "Plate_Number", "Confidence", "Status", "Error"])
        # Write data rows
        for result in results:
            writer.writerow([
                result.get("image", ""),
                result.get("plate_number", ""),
                f"{result.get('confidence', 0):.2f}" if result["status"] == "success" else "",
                result.get("status", ""),
                result.get("error", "")
            ])
    
    # ----- Save to JSON -----
    json_file = output_folder / f"plate_results_{timestamp}.json"
    json_output = {
        "timestamp": datetime.now().isoformat(),
        "total_images": len(results),
        "successful": successful,
        "plates_found": plates_found,
        "errors": len(results) - successful,
        "average_confidence": avg_confidence if confident_results else None,
        "results": results
    }
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    
    # ----- Also save a "latest" version for easy access -----
    csv_latest = output_folder / "plate_results_latest.csv"
    json_latest = output_folder / "plate_results_latest.json"
    
    # Copy to latest files
    with open(csv_latest, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Image", "Plate_Number", "Confidence", "Status", "Error"])
        for result in results:
            writer.writerow([
                result.get("image", ""),
                result.get("plate_number", ""),
                f"{result.get('confidence', 0):.2f}" if result["status"] == "success" else "",
                result.get("status", ""),
                result.get("error", "")
            ])
    
    with open(json_latest, "w", encoding="utf-8") as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    
    print("\n" + "=" * 60)
    print("RESULTS SAVED")
    print("=" * 60)
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
    # (not when imported as a module)
    main()
