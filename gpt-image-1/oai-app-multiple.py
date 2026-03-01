"""
Batch photorealistic image generation with per-scene camera parameters.

This script generates five images sequentially, each with its own lens,
aperture, colour temperature, lighting style, palette, and film-stock
reference.  Scenes range from an alpine landscape to an underwater reef.

Prompt hierarchy (shared with oai-app.py):
  Subject & Setting -> Mood & Lighting -> Style -> Technical -> Camera & Lens

Output: images/generated-image-1.jpg through generated-image-5.jpg
"""

from openai import AzureOpenAI
import os
import base64
from PIL import Image
import dotenv
import json

# Load environment variables from the .env file
dotenv.load_dotenv()

# Configure Azure OpenAI service client
client = AzureOpenAI(
    api_key=os.environ['AZURE_OPENAI_API_KEY'],
    api_version="2025-04-01-preview",
    azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT']
)

model = os.environ['AZURE_OPENAI_DEPLOYMENT']

# ---------------------------------------------------------------------------
# Prompt-engineering building blocks (structured hierarchy)
# ---------------------------------------------------------------------------
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
    lens: str = "50 mm",
    aperture: str = "f/2.8",
    color_temp: str = "~5500 K (daylight)",
    lighting_style: str = "natural ambient light",
    palette: str = "neutral true-to-life tones",
    film_stock: str = "Kodak Portra 400",
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
Color rendition reference: {film_stock}."""

# Set the local directory for the stored images
image_dir = os.path.join(os.curdir, 'images')

# If the directory doesn't exist, create it
if not os.path.isdir(image_dir):
    os.mkdir(image_dir)

# ---------------------------------------------------------------------------
# Per-scene prompts — each scene gets its own lens, lighting & palette
# ---------------------------------------------------------------------------
scene_configs = [
    {   # 1 — Epic landscape
        "scene": (
            "A tranquil alpine valley at sunset: snow-capped granite peaks "
            "reflected in a glassy lake, foreground of wild grass with tiny "
            "water droplets on blades, light mist drifting above the waterline, "
            "aerial perspective haze deepening toward distant ridges, "
            "and high-altitude cirrus clouds catching warm rim light."
        ),
        "lens": "24 mm",
        "aperture": "f/8",
        "color_temp": "~3500 K (golden-hour warm)",
        "lighting_style": "low-angle golden-hour sun with long shadows and warm rim light on peaks",
        "palette": "burnt orange and rose-gold highlights, cool teal shadows on snow",
        "film_stock": "Fujifilm Velvia 50 (vivid landscape rendition)",
    },
    {   # 2 — Cyberpunk / night city
        "scene": (
            "A futuristic downtown avenue at night after rain: wet asphalt with "
            "elongated puddle reflections of neon signage, modern glass-and-steel "
            "architecture, subtle ground-level fog, autonomous electric vehicles "
            "with natural headlight bloom and red taillight streaks, a lone "
            "pedestrian reflected in a shop window."
        ),
        "lens": "35 mm",
        "aperture": "f/1.8",
        "color_temp": "~6500 K (cool artificial mix)",
        "lighting_style": "mixed neon key lights with cyan and magenta spill, sodium-vapor orange street lamps as practicals",
        "palette": "electric cyan, magenta, and warm sodium-orange against deep charcoal darks",
        "film_stock": "Kodak Vision3 500T (cinema tungsten stock)",
    },
    {   # 3 — Intimate interior
        "scene": (
            "A cozy independent coffee shop interior mid-morning: exposed-brick wall, "
            "worn oak tables with cup rings and visible grain, ceramic mugs with "
            "wisps of steam, soft window daylight mixing with warm tungsten pendants, "
            "a barista in a linen apron pouring a latte with micro-foam detail, "
            "shallow depth of field isolating the pour, surrounding patrons "
            "softly blurred."
        ),
        "lens": "50 mm",
        "aperture": "f/1.4",
        "color_temp": "~3800 K (warm tungsten mixed with cool window light)",
        "lighting_style": "Rembrandt key from side window, warm fill from overhead tungsten pendants",
        "palette": "warm caramels and creams in highlights, cool slate-blue window-light shadows",
        "film_stock": "Kodak Portra 400",
    },
    {   # 4 — Wildlife telephoto
        "scene": (
            "A majestic male lion standing on a weathered sandstone outcrop in "
            "the East African savanna at golden hour: individual strands of mane "
            "backlit by the low sun, dry tawny grass with seed heads in the wind, "
            "distant acacia silhouettes, visible heat shimmer near the horizon, "
            "a faint line of wildebeest in the far background."
        ),
        "lens": "200 mm",
        "aperture": "f/2.8",
        "color_temp": "~3200 K (deep golden hour)",
        "lighting_style": "strong backlit rim light with warm bounced fill from sunlit ground",
        "palette": "burnished gold and sienna, dusty ochre midtones, blue-grey distant haze",
        "film_stock": "Kodak Ektar 100 (saturated fine-grain)",
    },
    {   # 5 — Underwater macro
        "scene": (
            "An underwater coral reef at 10 m depth: branching staghorn coral "
            "and soft fan coral in the mid-ground, a pair of clownfish near an "
            "anemone in the foreground, volumetric god-rays from the surface, "
            "suspended plankton particles catching the light, subtle caustic "
            "patterns on the sandy bottom, natural blue-green water-column "
            "color attenuation increasing with distance."
        ),
        "lens": "16 mm (behind dome port, rectilinear)",
        "aperture": "f/8",
        "color_temp": "~6000 K (white-balanced for depth with mild blue tint)",
        "lighting_style": "dual underwater strobes at 45° providing warm fill, natural downwelling ambient light as key",
        "palette": "vivid coral orange and clownfish orange against deep cerulean and teal water",
        "film_stock": "Fujifilm Provia 100F (neutral-accurate)",
    },
]

prompts = [
    build_photoreal_prompt(
        cfg["scene"],
        lens=cfg["lens"],
        aperture=cfg["aperture"],
        color_temp=cfg["color_temp"],
        lighting_style=cfg["lighting_style"],
        palette=cfg["palette"],
        film_stock=cfg["film_stock"],
    )
    for cfg in scene_configs
]

print(f"Generating {len(prompts)} images using Azure OpenAI...")
print(f"Using model: {model}\n")

generated_images = []

try:
    # Generate images for each prompt
    for idx, prompt in enumerate(prompts, start=1):
        print(f"[{idx}/{len(prompts)}] Generating image...")
        print(f"Prompt: {prompt[:80]}{'...' if len(prompt) > 80 else ''}")
        
        result = client.images.generate(
            model=model,
            prompt=prompt,
            size='1024x1024',
            n=1,
            quality='high',
            output_format='jpeg'
        )
        
        # Parse the response
        generation_response = json.loads(result.model_dump_json())
        
        # Create filename with index
        image_path = os.path.join(image_dir, f'generated-image-{idx}.jpg')
        
        # Retrieve and decode the generated image
        image_base64 = generation_response["data"][0]["b64_json"]
        image_data = base64.b64decode(image_base64)
        
        # Save the image to file
        with open(image_path, "wb") as image_file:
            image_file.write(image_data)
        
        print(f"✓ Saved: {image_path}\n")
        generated_images.append(image_path)

    print(f"\nSuccessfully generated {len(generated_images)} images!")
    print("\nGenerated images:")
    for img_path in generated_images:
        print(f"  - {img_path}")
    
    # Display all generated images
    print("\nDisplaying all images...")
    for img_path in generated_images:
        image = Image.open(img_path)
        image.show()

except Exception as err:
    print(f"Error: {err}")

finally:
    print("\nCompleted!")
