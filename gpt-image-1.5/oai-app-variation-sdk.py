"""
Image editing using the native OpenAI Python SDK (client.images.edit).

This is the SDK-based counterpart of oai-app-variation-rest.py.
It reads an existing image, applies a structured photorealistic edit prompt,
and saves the result.  The SDK handles auth headers, URL construction,
multipart encoding, and retries automatically.
"""

from openai import AzureOpenAI
import os
import base64
from io import BytesIO
from PIL import Image
import dotenv
import json

# Load environment variables
dotenv.load_dotenv()

# Configure Azure OpenAI client
client = AzureOpenAI(
    api_key=os.environ['AZURE_OPENAI_API_KEY'],
    api_version="2025-04-01-preview",
    azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT'],
)

model = os.environ['AZURE_OPENAI_DEPLOYMENT']

# ---------------------------------------------------------------------------
# Edit prompt — structured into clear sections so the model can parse intent
# ---------------------------------------------------------------------------
EDIT_PROMPT = (
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

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
image_dir = os.path.join(os.curdir, 'images')
input_path = os.path.join(image_dir, 'generated-image.jpg')
output_path = os.path.join(image_dir, 'generated_variation_sdk.jpg')

print(f"Input image : {input_path}")

# Record original dimensions so we can resize back if the API returns a
# different size (the API only accepts 1024x1024, 1024x1536, 1536x1024).
original_image = Image.open(input_path)
original_width, original_height = original_image.size
print(f"Original size: {original_width}x{original_height}")
original_image.close()

# ---------------------------------------------------------------------------
# Call the native SDK images.edit endpoint
# ---------------------------------------------------------------------------
try:
    print(f"Using model : {model}")
    print("Sending edit request via SDK (this may take 30-60 seconds)...")

    with open(input_path, "rb") as img_file:
        result = client.images.edit(
            model=model,
            image=img_file,
            prompt=EDIT_PROMPT,
            n=1,
            size="1024x1024",
        )

    # Parse the response (base64-encoded image)
    generation_response = json.loads(result.model_dump_json())
    image_base64 = generation_response["data"][0]["b64_json"]
    image_data = base64.b64decode(image_base64)

    # Load into PIL, resize to original dimensions if needed, and save
    generated_image = Image.open(BytesIO(image_data))
    print(f"Generated size: {generated_image.size}")

    if generated_image.size != (original_width, original_height):
        print(f"Resizing to original: {original_width}x{original_height}")
        generated_image = generated_image.resize(
            (original_width, original_height), Image.Resampling.LANCZOS
        )

    generated_image.save(output_path, 'JPEG', quality=95)
    print(f"Variation saved to : {output_path}")

    # Display the result
    generated_image.show()

except Exception as err:
    print(f"Error: {err}")

finally:
    print("completed!")
