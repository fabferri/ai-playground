"""
Child-safe photorealistic image generation with metaprompts.

This script demonstrates how to combine content-safety boundaries (disallow
lists, role instructions) with a structured photorealistic prompt template.
The result is high-quality imagery that is guaranteed to be appropriate for
children.

Uses:
  - AzureOpenAI client with gpt-image-1.5 (images.generate)
  - A disallow list to exclude unsafe themes
  - Structured prompt hierarchy: Role -> Safety -> Subject & Setting ->
    Mood & Lighting -> Style -> Technical -> Camera & Lens

Output: images/sol-generated-image.jpg
"""

from openai import AzureOpenAI
import os
import base64
from PIL import Image
import dotenv
import json

dotenv.load_dotenv()

# Assign the API version for gpt-image-1.5 model
client = AzureOpenAI(
  api_key=os.environ['AZURE_OPENAI_API_KEY'],  # this is also the default, it can be omitted
    api_version = "2025-04-01-preview",
  azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT'] 
  )

model = os.environ['AZURE_OPENAI_DEPLOYMENT']

# ---------------------------------------------------------------------------
# Content-safety boundaries (metaprompts)
# ---------------------------------------------------------------------------
# Metaprompts are text prompts used to steer output away from unsafe content.
# Keep the disallow list short and high-signal; the style block handles the
# rest through positive framing ("include THIS") rather than negative framing.
disallow_list = (
    "swords, weapons, violence, blood, gore, nudity, sexual content, "
    "adult content, adult themes, adult language, adult humor, frightening imagery"
)

# ---------------------------------------------------------------------------
# Prompt-engineering building blocks
# ---------------------------------------------------------------------------
STYLE_BLOCK = """\
Photorealistic image indistinguishable from a professional photograph.
- True-to-life materials with correct light interaction:
  subsurface scattering on skin, Fresnel reflections on glass and wet pavement,
  diffuse scatter on limestone and fabric, anisotropic highlights on brushed metal.
- Physically plausible lighting: correct shadow hardness, realistic falloff,
  believable ambient / bounce fill.
- Cinematic yet natural color grading; no over-saturated or neon tones.
- Rich micro-detail (texture grain in stone, stitching on clothing seams,
  individual leaves on trees, subtle cracks in pavement).
- Three-layer depth separation with aerial perspective at distance."""

TECHNICAL_BLOCK = """\
Technical constraints:
- Preserve highlight roll-off and shadow detail; no clipped whites or crushed blacks.
- Natural white balance.
- Avoid over-sharpening halos, plastic skin, banding, or posterization.
- Keep straight architectural lines straight.
- No illustration, cartoon, CGI, 3D render, painting, text overlay, or watermark."""


def build_child_safe_photoreal_prompt(
    scene: str,
    *,
    lens: str = "35 mm",
    aperture: str = "f/4",
    color_temp: str = "~4000 K (golden hour)",
    lighting_style: str = "warm golden-hour sun with soft bounced fill",
    palette: str = "warm amber highlights, cool lavender shadows",
) -> str:
    """Build a visually rich but child-safe photorealistic prompt."""
    return f"""\
Role: You are a creative photographer producing beautiful, child-friendly images.

Content safety rules:
- Image must be safe for work and appropriate for children.
- Use color, landscape orientation, 16:9 framing.
- Exclude any items from this disallow list: {disallow_list}

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
Natural depth of field, subtle vignette, fine film-like grain.
Color rendition reference: Kodak Portra 160 (gentle skin tones, soft contrast)."""


prompt = build_child_safe_photoreal_prompt(
    "The Arc de Triomphe in Paris during warm evening golden hour. "
    "A woman in a light summer dress walks elegantly along the wide "
    "Champs-Élysées boulevard carrying a leather handbag; subtle motion "
    "blur in the hem of her dress conveys gentle movement. "
    "The monument's Haussmann-era limestone shows carved bas-relief detail, "
    "chisel marks, and warm rim light on its edges. "
    "Foreground cobblestones with realistic joint lines; middle distance "
    "features manicured plane trees, a few strolling pedestrians, and "
    "a classic Parisian lamppost casting a long shadow. "
    "Sky transitions from soft apricot near the horizon to pale lavender above, "
    "balanced exposure with no blown highlights.",
    lens="35 mm",
    aperture="f/5.6",
    color_temp="~3800 K (late golden-hour, Parisian warmth)",
    lighting_style="low-angle golden-hour key from the west, soft fill bounce off warm limestone façades",
    palette="warm apricot and champagne-gold highlights, soft lavender and slate-blue shadows",
)


try:
    # Create an image by using the image generation API
    # NOTE: gpt-image-1.5 returns base64-encoded images only (no URL option)

    result = client.images.generate(
        model=model,
        prompt=prompt,    # Enter your prompt text here
        size='1024x1024',
        n=1,
        quality='high',         # gpt-image-1.5 supports: low, medium, high (default)
        output_format='jpeg'    # gpt-image-1.5 supports: jpeg or png
    )

    generation_response = json.loads(result.model_dump_json())
    # Set the directory for the stored image
    image_dir = os.path.join(os.curdir, 'images')

    # If the directory doesn't exist, create it
    if not os.path.isdir(image_dir):
        os.mkdir(image_dir)

    # Initialize the image path (match extension to output_format)
    image_path = os.path.join(image_dir, 'sol-generated-image.jpg')

    # Retrieve the generated image from base64 data
    # gpt-image-1.5 returns base64-encoded images, not URLs
    image_base64 = generation_response["data"][0]["b64_json"]  # extract base64 image from response
    image_data = base64.b64decode(image_base64)  # decode base64 to bytes
    with open(image_path, "wb") as image_file:
        image_file.write(image_data)

    # Display the image in the default image viewer
    image = Image.open(image_path)
    image.show()

except Exception as err:
    print(f"Error: {err}")

finally:
    print("completed!")
