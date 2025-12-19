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
    data = {
        'prompt': 'Increase brightness by approximately 15%. Increase color saturation slightly (~10%). Do not change composition. Center the clock exactly on the wall. Change the angle of the light in opposite direction.',
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
    
    # gpt-image-1 returns base64-encoded images
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
