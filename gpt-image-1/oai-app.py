"""
Single photorealistic image generation with Azure OpenAI gpt-image-1.5.

This script generates one high-quality image from a detailed scene
description using a structured prompt template with per-scene camera
and lighting parameters.

Prompt hierarchy:
  Subject & Setting -> Mood & Lighting -> Style -> Technical -> Camera & Lens

Output: images/generated-image.jpg
"""

from openai import AzureOpenAI
import os
import base64
from PIL import Image
import dotenv
import json
from io import BytesIO

# load the environment variables from the .env file.
dotenv.load_dotenv()

 
# configure Azure OpenAI service client
# Assign the API version 
client = AzureOpenAI(
  api_key=os.environ['AZURE_OPENAI_API_KEY'],  # this is also the default, it can be omitted
        api_version = "2025-04-01-preview",
  azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT'] 
  )

model = os.environ['AZURE_OPENAI_DEPLOYMENT']

# ---------------------------------------------------------------------------
# Prompt-engineering building blocks (structured hierarchy)
# ---------------------------------------------------------------------------
# Order matters: Subject → Setting → Mood → Style → Materials → Negative
# Each block is kept short so the total prompt stays well under the 4 000-char
# limit while remaining information-dense.

STYLE_BLOCK = """\
Photorealistic image indistinguishable from a professional photograph.
- True-to-life materials with correct light interaction:
  subsurface scattering on skin and wax, Fresnel reflections on glass and water,
  anisotropic highlights on brushed metal, diffuse scatter on fabric and matte wood.
- Physically plausible lighting: correct shadow hardness for source size,
  realistic falloff (inverse-square), and believable ambient / bounce fill.
- Cinematic yet natural color grading; no over-saturated or neon tones.
- Rich micro-detail and tactile imperfections (dust motes, hairline scratches,
  fabric pilling, patina, fingerprints on polished surfaces).
- Three-layer depth separation: sharp foreground → mid-ground subject → softer background
  with aerial perspective (slight desaturation and haze at distance)."""

TECHNICAL_BLOCK = """\
Technical constraints:
- Preserve highlight roll-off and shadow detail (no clipped whites or crushed blacks).
- Maintain natural white balance; state explicit color temperature when relevant.
- Avoid over-sharpening halos, plastic skin, banding, or posterization.
- Keep straight lines straight; use only optically plausible barrel/pincushion distortion.
- No illustration, cartoon, CGI, 3D render, painting, text overlay, or watermark."""


def build_photoreal_prompt(
    scene: str,
    *,
    lens: str = "85 mm",
    aperture: str = "f/2.0",
    color_temp: str = "~4500 K (warm daylight)",
    lighting_style: str = "soft Rembrandt key light with warm bounced fill",
    palette: str = "warm amber highlights, cool blue-grey shadows",
) -> str:
    """Assemble a structured prompt with per-scene camera & mood parameters."""
    return f"""\
Subject & Setting:
{scene}

Mood & Lighting:
Lighting style: {lighting_style}.
Color temperature: {color_temp}. Palette: {palette}.

Style:
{STYLE_BLOCK}

{TECHNICAL_BLOCK}

Camera & Lens:
Full-frame sensor, {lens} prime, {aperture}, ISO 100.
Natural bokeh in out-of-focus regions, subtle vignette, fine film-like grain.
Shoot as if captured on Kodak Portra 400 for color rendition reference."""

try:
    # Create an image by using the image generation API
    # prompt - it is the text prompt that is used to generate the image. 
    #           (max 4,000 characters)
    # size    - it is the size of the image that is generated. 
    #           1024x1024 (square - fastest)
    #           1024x1536 (portrait)
    #           1536x1024 (landscape)
    # n       - it is the number of images that are generated. 
    #           Number of images per request: 1-10 (default: 1)
    # quality - it is a parameter that controls the quality of the generated image. (it is optional) 
    #            low (fastest)
    #            medium
    #            high (default for gpt-image-1.5; better quality)
    # output_format      - Image format: PNG or JPEG (default: PNG)
    # output_compression - Compression level: 0-100 (default: 100)
    # stream             - Enable streaming: true or false
    # partial_images     - Number of partial images during streaming: 1-3
    # background         - Set to transparent for transparent background (requires PNG format)
    # NOTE: gpt-image-1.5 returns base64-encoded images only (no URL option)
    # 'A sunlit indoor lounge area with a modern infinity pool, contemporary architecture, natural lighting. some people relaxing by the poolside, enjoying the warm atmosphere.', 
    prompt = build_photoreal_prompt(
        'A vintage skeleton wall clock mounted on an aged textured plaster wall '
        'in a softly sunlit European living room. '
        'Angled late-afternoon sunbeams enter from a tall side window, '
        'catching airborne dust particles and projecting long warm shadows. '
        'Brass and steel gears show patina, hairline scratches, and tiny '
        'specular highlights that shift with the curved surfaces. '
        'Below the clock a weathered oak sideboard displays a ceramic vase '
        'with dried lavender; the wood grain catches soft reflected light '
        'and shows decades of gentle wear.',
        lens="85 mm",
        aperture="f/2.0",
        color_temp="~4000 K (late-afternoon warm)",
        lighting_style="directional key light from a side window, "
                        "warm bounced fill off the plaster wall opposite",
        palette="golden amber key, cool steel-blue accents in shadow areas",
    )

    result = client.images.generate(
        model=model,
        prompt=prompt,
        size='1024x1024',
        n=1,
        quality='high',
        output_format='jpeg'
    )
    # The code responds with a JSON object that contains the base64-encoded image.
    # gpt-image-1.5 returns images in base64 format (no URL option)
    generation_response = json.loads(result.model_dump_json())

    # Set the local directory for the stored image
    image_dir = os.path.join(os.curdir, 'images')

    # If the directory doesn't exist, create it
    if not os.path.isdir(image_dir):
        os.mkdir(image_dir)

    # Initialize the image path (match extension to output_format)
    image_path = os.path.join(image_dir, 'generated-image.jpg')

    # Retrieve the generated image from base64 data
    image_base64 = generation_response["data"][0]["b64_json"]  # extract base64 image from response
    image_data = base64.b64decode(image_base64)  # decode base64 to bytes
    
    # Save the image to file
    with open(image_path, "wb") as image_file:
        image_file.write(image_data)

    # Display the image in the default image viewer
    image = Image.open(image_path)
    image.show()

except Exception as err:
    print(f"Error: {err}")

finally:
    print("completed!")