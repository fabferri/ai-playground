# Azure OpenAI GPT-Image-1.5 -- Image Generation and Editing

This repository contains Python scripts that demonstrate image generation and editing with
Azure OpenAI's **GPT-Image-1.5** model, using structured prompt-engineering techniques
designed for high photorealism.

## Prerequisites

- Python 3.9+
- An Azure AI Foundry (AIServices) resource with a **GPT-Image-1.5** deployment
  (GlobalStandard SKU, model version `2025-12-16`)
- Required packages: `openai`, `pillow`, `requests`, `python-dotenv`

Run scripts inside a Python virtual environment:
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Environment setup

Create a `.env` file (or let the deployment script generate one):
```
AZURE_OPENAI_ENDPOINT=https://<account>.cognitiveservices.azure.com/
AZURE_OPENAI_API_KEY=<your_key>
AZURE_OPENAI_DEPLOYMENT=gpt-image-1.5
```

## Automated deployment (PowerShell)

The PowerShell script creates the Azure resource, deploys the model, and optionally
writes the `.env` file:

```powershell
.\create-oai-image-deployment.ps1
```

At the end you are prompted:
`Update .env automatically with endpoint, api key, and deployment? (y/N)`

---

## Prompt-engineering approach

All scripts share a **structured prompt template** organised in a fixed hierarchy
that research shows works well with diffusion-based image models:

```
Subject & Setting   --  what to depict, with tactile scene detail
Mood & Lighting     --  named lighting style, colour temperature (Kelvin), palette
Style               --  material-light interaction rules (Fresnel, SSS, anisotropic)
Technical           --  negative constraints (no halos, no clipping, no CGI ...)
Camera & Lens       --  focal length, aperture, ISO, film-stock colour reference
```

Key techniques used:

| Technique | Purpose |
|-----------|---------|
| **Per-scene camera parameters** | Lens, aperture, and film stock matched to the subject (wide-angle for landscapes, telephoto for wildlife, macro for underwater) |
| **Named lighting styles** | Rembrandt key, golden-hour rim, neon spill, dual strobes -- gives the model a concrete visual anchor |
| **Material physics language** | Subsurface scattering, Fresnel reflections, anisotropic highlights, caustics -- steers away from flat/plastic output |
| **Explicit colour temperature** | Kelvin values (3200 K -- 6500 K) plus split-tone direction for highlights and shadows |
| **Film-stock reference** | Portra 400, Velvia 50, Ektar 100, Vision3 500T, Provia 100F -- provides a shorthand for the model's colour rendition |
| **Constraint block (negatives last)** | "No illustration, no cartoon, no CGI ..." placed after positives so the model weighs desired traits higher |

---

## Scripts

### oai-app.py -- Single image generation
Generates one photorealistic image from a richly described scene prompt.

- Uses `build_photoreal_prompt()` with keyword arguments for lens, aperture,
  colour temperature, lighting style, palette, and film stock.
- Default scene: a vintage skeleton wall clock on a sunlit plaster wall with an
  oak sideboard below (85 mm, f/2.0, ~4000 K late-afternoon light).
- Saves `images/generated-image.jpg` and opens the system image viewer.

### oai-app-multiple.py -- Batch generation (five scenes)
Generates five images sequentially, each with scene-specific camera and lighting
parameters.

| Scene | Lens | Film stock |
|-------|------|------------|
| Alpine valley at sunset | 24 mm f/8 | Fujifilm Velvia 50 |
| Futuristic city at night | 35 mm f/1.8 | Kodak Vision3 500T |
| Coffee shop interior | 50 mm f/1.4 | Kodak Portra 400 |
| Lion on the savanna | 200 mm f/2.8 | Kodak Ektar 100 |
| Underwater coral reef | 16 mm f/8 | Fujifilm Provia 100F |

- Saves `images/generated-image-1.jpg` through `generated-image-5.jpg`.
- Progress is printed to the console as each image completes.

### oai-solution.py -- Child-safe generation with metaprompts
Demonstrates content-safety boundaries combined with photorealistic quality.

- Uses `build_child_safe_photoreal_prompt()` that prepends a role instruction
  ("creative photographer producing child-friendly images") and a disallow list.
- Default scene: the Arc de Triomphe in Paris at golden hour with a woman on the
  Champs-Elysees (35 mm, f/5.6, ~3800 K, Kodak Portra 160).
- Saves `images/sol-generated-image.jpg`.

### oai-app-variation-sdk.py -- Image editing via native SDK
Edits an existing image using the native `client.images.edit()` method from the
`openai` Python SDK. This is the recommended approach -- the SDK handles auth,
URL construction, multipart encoding, and retries automatically.

- Reads `images/generated-image.jpg` as input.
- Edit prompt is structured into sections:
  - **Object rearrangement** -- repositions furniture and decorative items into a
    fresh asymmetric layout while keeping every original element.
  - **Lighting** -- switches to intense noon sunlight (~5500 K, high-key) with
    steep-angle sun rays, hard-edged geometric light patches, strong parallel
    shadows, and visible dust motes (+1.0 to +1.5 EV brighter).
  - **Exposure & Color** -- raises overall luminance, neutral daylight white
    balance, vibrance +10-12%.
  - **Material fidelity** -- preserves micro-textures under brighter light.
  - **Constraints** -- no halos, no artifacts, no style shift.
- Resizes output back to original dimensions if the API returns a different size.
- Saves `images/generated_variation_sdk.jpg`.

### oai-app-variation-rest.py -- Image editing via REST API
Edits an existing image using the `images/edits` REST endpoint directly
(multipart/form-data). Useful for understanding the raw API structure or when
you need full control over the HTTP request.

- Reads `images/generated-image.jpg` as input.
- Same structured edit prompt as the SDK version (noon sunlight, object
  rearrangement).
- Resizes output back to original dimensions if the API returns a different size.
- Saves `images/generated_variation_rest.jpg`.

## GPT-Image-1.5 model reference

| Parameter | Values |
|-----------|--------|
| **Sizes** | 1024x1024 (square), 1024x1536 (portrait), 1536x1024 (landscape) |
| **Quality** | `low` (fastest), `medium`, `high` (default, best quality) |
| **Output format** | JPEG, PNG |
| **Images per request** | 1--10 |
| **Encoding** | Base64 only (no URL option) |
| **API version** | `2025-04-01-preview` |
| **Deployment SKU** | GlobalStandard |
| **Available regions** | westus3, eastus2, uaenorth, polandcentral, swedencentral |

## Output files

| File | Source script |
|------|---------------|
| `images/generated-image.jpg` | oai-app.py |
| `images/generated-image-N.jpg` | oai-app-multiple.py |
| `images/generated_variation_sdk.jpg` | oai-app-variation-sdk.py |
| `images/generated_variation_rest.jpg` | oai-app-variation-rest.py |
| `images/sol-generated-image.jpg` | oai-solution.py |

## Notes

- GPT-Image-1.5 returns base64-encoded images only (no URL option unlike DALL-E 3).
- Two image-editing scripts are provided:
  - `oai-app-variation-sdk.py` -- uses the native `client.images.edit()` SDK method (recommended).
  - `oai-app-variation-rest.py` -- calls the REST endpoint directly with `requests`,
    useful for learning the raw API or when you need full HTTP control.
- All scripts open generated images in the system's default viewer after saving.

---

`Tags: Azure OpenAI, gpt-image-1.5, prompt engineering, photorealism` <br>
`date: 01-03-2026` <br>
