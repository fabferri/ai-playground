"""
Image editing using the REST API directly (multipart/form-data).

This script calls the Azure OpenAI images/edits endpoint with raw HTTP
requests via the 'requests' library.  It is useful for understanding the
underlying API structure or when you need full control over the HTTP
request (custom headers, timeouts, retries, etc.).

For the simpler SDK-based approach, see oai-app-variation-sdk.py.

Input : images/generated-image.jpg
Output: images/generated_variation_rest.jpg
"""

import os
import base64
from PIL import Image
import dotenv
import requests

# Load environment variables
dotenv.load_dotenv()

# Configuration
endpoint_raw = os.environ['AZURE_OPENAI_ENDPOINT']
api_key = os.environ['AZURE_OPENAI_API_KEY']
model = os.environ['AZURE_OPENAI_DEPLOYMENT']
api_version = "2025-04-01-preview"

# Extract base endpoint (handle cases where endpoint includes full path)
# Example: https://swedencentral.api.cognitive.microsoft.com/openai/deployments/...
# Should become: https://swedencentral.api.cognitive.microsoft.com
if '/openai/' in endpoint_raw:
    endpoint = endpoint_raw.split('/openai/')[0]
else:
    endpoint = endpoint_raw.rstrip('/')

image_dir = os.path.join(os.curdir, 'images')

# Initialize the image path
image_path = os.path.join(image_dir, 'generated-image.jpg')
print(f"Input image: {image_path}")

# Get original image dimensions
original_image = Image.open(image_path)
original_width, original_height = original_image.size
print(f"Original image size: {original_width}x{original_height}")
original_image.close()

# ---Creating variation using REST API---
try:
    print("LOG creating variation using REST API")
    print(f"Using model: {model}")
    
    # Read the image bytes
    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()
    
    # Prepare REST API request with multipart/form-data
    url = f"{endpoint}/openai/deployments/{model}/images/edits?api-version={api_version}"
    
    print(f"LOG URL: {url}")
    
    headers = {
        "api-key": api_key
        # Don't set Content-Type - requests will set it automatically with boundary
    }
    
    # Prepare multipart form data
    files = {
        'image': ('image.jpg', image_bytes, 'image/jpeg')
    }
    
    # Azure OpenAI only supports: 1024x1024, 1024x1536, 1536x1024
    # Use 1024x1024 as default, will resize back to original later
    edit_prompt = (
        "Photorealistic edit of the input photograph. "
        "Keep every original object but rearrange their positions — "
        "shift furniture, decorative items, and smaller objects to new "
        "locations within the room for a fresh, asymmetric layout that "
        "feels naturally lived-in. Preserve subject identity and all "
        "original elements; do NOT add or remove anything.\n\n"

        "Lighting — change to intense noon sunlight (~5500 K, high-key). "
        "Bright, direct sun rays pour through the windows at a steep angle, "
        "casting hard-edged geometric light patches and strong parallel "
        "shadows across the floor and walls. Flood the room with abundant "
        "natural light; overall exposure should feel +1.0 to +1.5 EV brighter "
        "than the original. Visible dust motes float in the sunbeams.\n\n"

        "Exposure & Color — raise overall luminance significantly, keep "
        "highlights just below clipping, open shadows completely. "
        "White balance neutral daylight (~5500 K). "
        "Boost vibrance +10-12% for sun-drenched warmth while keeping "
        "skin and natural materials true-to-life.\n\n"

        "Material fidelity — preserve micro-textures: brass patina, "
        "steel gear teeth, wood grain, plaster pores, fabric weave. "
        "Under the brighter light, surface detail and Fresnel reflections "
        "should be more visible, not washed out.\n\n"

        "Constraints — no over-sharpening halos, no plastic or painted look, "
        "no noise/banding artifacts, no added text/watermarks, "
        "no cartoon/illustration/CGI style shift."
    )

    data = {
        'prompt': edit_prompt,
        'n': '1',
        'size': '1024x1024'
    }
    
    print("LOG sending request to Azure OpenAI...")
    print("LOG this may take 30-60 seconds...")
    response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
    response.raise_for_status()
    
    result = response.json()
    
    # Save the generated variation
    variation_path = os.path.join(image_dir, 'generated_variation_rest.jpg')
    
    # gpt-image-1.5 returns base64-encoded images
    image_base64_output = result['data'][0]['b64_json']
    
    print("LOG decoding base64 image")
    image_data = base64.b64decode(image_base64_output)
    
    # Load the generated image and resize to original dimensions
    from io import BytesIO
    generated_image = Image.open(BytesIO(image_data))
    print(f"Generated image size: {generated_image.size}")
    
    # Resize back to original dimensions if different
    if generated_image.size != (original_width, original_height):
        print(f"Resizing to original size: {original_width}x{original_height}")
        generated_image = generated_image.resize((original_width, original_height), Image.Resampling.LANCZOS)
    
    # Save the resized image
    variation_path = os.path.join(image_dir, 'generated_variation_rest.jpg')
    generated_image.save(variation_path, 'JPEG', quality=95)
    
    print(f"LOG variation saved to: {variation_path}")

except requests.exceptions.Timeout:
    print("Error: Request timed out after 120 seconds")
except requests.exceptions.HTTPError as http_err:
    print(f"HTTP Error: {http_err}")
    print(f"Response: {response.text}")
except Exception as err:
    print(f"Error: {err}")
    
finally:
    print("completed!")

# Display the generated variation
if os.path.exists(os.path.join(image_dir, 'generated_variation_rest.jpg')):
    variation_image = Image.open(os.path.join(image_dir, 'generated_variation_rest.jpg'))
    variation_image.show()
