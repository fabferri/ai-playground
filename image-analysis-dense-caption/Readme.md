# AI Vision ImageAnalysis Dense Caption

The Azure AI Vision ImageAnalysis Dense Caption feature generates detailed captions for up to 10 different regions in an image, including one for the whole image. It provides a more comprehensive understanding of the image content without the need to view the image itself. This library offers an easy way to extract dense captions from images using the Azure Computer Vision service.

## <a name="features"></a>Features

This project analyzes images using Azure AI Vision and extracts:

| Feature            | Description                                 | Bounding Box |
|--------------------|---------------------------------------------|--------------|
| **Caption**        | Single sentence describing the entire image | No           |
| **Dense Captions** | Up to 10 detailed descriptions for different regions | Yes |
| **Objects**        | Specific objects detected (~100 types: person, car, dog, etc.) | Yes |
| **Tags**           | Broad image concepts (1000+ categories: outdoor, food, nature, etc.) | No |

### Objects vs Tags

In Azure AI Vision Image Analysis 4.0:

**Objects**: Specific items with exact locations (bounding boxes). Limited to ~100 common object types like person, car, dog, chair, laptop, etc.
- Are the feature type that does return bounding boxes.
- Returned when you call features=[ "objects" ].
- Each object contains:
   - name
   - confidence
   - boundingBox (x, y, w, h)
   - Sometimes additional detail depending on model (e.g., parent categories).

**Tags**: Broader image concepts without locations. Includes 1000+ categories like "indoor", "food", "furniture", "text", "nature", etc.
- Represent high‑level concepts present in the image (e.g., “cat”, “outdoor”, “people”).
- Are image-level annotations only.
- Do NOT include coordinates, regions, bounding boxes, masks, or pixel geometry.
- You're guaranteed only a name and a confidence score.

> [!NOTE] 
>
> Not all items in an image will be detected as objects. Use tags to capture broader concepts that aren't in the object detection list.

In Image Analysis 4.0 explicitly separates:

- Tagging (classification) → no coordinates
- Object detection → coordinates provided
- Dense captions / region captions → bounding regions provided
- People detection → bounding boxes provided
- OCR → text bounding boxes


## <a name="prerequisites"></a>Prerequisites

1. An Azure subscription
2. An Azure AI Vision resource (Computer Vision) in a **supported region**
3. Python 3.8+

### Supported Regions for Dense Captions

Dense Captions and Object Detection features are only available in these regions:
- **Americas**: eastus, westus, westus2
- **Europe**: westeurope, francecentral, northeurope
- **Asia Pacific**: australiaeast, southeastasia, japaneast, koreacentral, centralindia

## <a name="installation"></a>Installation

```bash
pip install -r requirements.txt
```

**Required packages:**
- `azure-ai-vision-imageanalysis` - Azure AI Vision SDK
- `python-dotenv` - Load environment variables from .env file
- `pillow` - Image processing for annotated output

## <a name="configuration"></a>Configuration

### Option 1: Using .env file (Recommended)

Create a `.env` file in the project root:
```
VISION_ENDPOINT=https://<your-resource-name>.cognitiveservices.azure.com/
VISION_KEY=<your-subscription-key>
```

## <a name="deployment"></a>Deployment

Use the included deployment script to create Azure resources:

```powershell
# Deploy to Azure (defaults to northeurope region)
.\deploy.ps1

# Deploy with custom settings
.\deploy.ps1 -ResourceGroupName "my-rg" -Location "westeurope" -Sku "S1"
```

The script will:
   1. Create a Resource Group
   2. Deploy Azure AI Vision service
   3. Update `.env` file with endpoint and key

## <a name="usage"></a>Usage

   1. Place your images in the `.\pictures` folder
   2. Run the analysis script:

```bash
python dense_caption.py
```

The script will:
- Scan all images in `.\pictures` folder (supports .jpg, .jpeg, .png, .gif, .bmp, .webp)
- Analyze each image for captions, dense captions, objects, and tags
- Generate output files in `.\output` folder

## <a name="output-files"></a>Output Files

The script generates the following files in `.\output`:

| File                    | Description |
|-------------------------|-------------|
| `{image}_analysis.json` | Detailed JSON data for each image |
| `{image}_annotated.png` | Image with bounding boxes around objects and tags legend |
| `summary_report.json`   | Machine-readable summary of all analyzed images |
| `summary_report.txt`    | Human-readable summary report |

### Annotated Images

Each annotated image includes:
- **Colored bounding boxes** around detected objects with labels
- **Object labels** showing name and confidence percentage
- **Tags legend** at the bottom listing all identified concepts

### Summary Report Contents

The summary report includes:
- Total images analyzed
- Per-image breakdown: caption, detected objects, tags
- Objects summary: which objects appear in which files

## Example Output

### JSON Analysis (per image)
```json
{
  "timestamp": "2026-01-18T10:30:00",
  "image_source": "pictures/kitchen.jpg",
  "metadata": {
    "width": 1920,
    "height": 1080,
    "model_version": "2024-02-01"
  },
  "caption": {
    "text": "a kitchen table with various items",
    "confidence": 0.85
  },
  "dense_captions": [...],
  "objects": [
    {
      "name": "cup",
      "confidence": 0.92,
      "bounding_box": {"x": 100, "y": 50, "width": 80, "height": 100}
    }
  ],
  "tags": [
    {"name": "indoor", "confidence": 0.99},
    {"name": "kitchen", "confidence": 0.95},
    {"name": "food", "confidence": 0.88}
  ]
}
```


## <a name="cleanup"></a>Cleanup

To delete all Azure resources when done:

```powershell
az group delete --name <resource-group-name> --yes --no-wait
```

##  <a name="troubleshooting"></a>Troubleshooting

### "Feature not supported in this region" Error
Deploy your Azure AI Vision resource to a supported region (eastus, westeurope, etc.)

### Objects Not Detected
- Azure AI Vision detects ~100 common object types
- Small, occluded, or unusual objects may not be detected
- Use **tags** to capture broader concepts not in the object list

## Prompt Engineering used to generate the images

Example prompts for generating images:

- create a realistic image with more than 10 items in a kitchen over a table. add proper shadow and light to keep much realistic as possible the picture
- create a realistic picture with shadow and light with black office desk, 4 computer screens over a desktop, 2 keyboard and 2 laptops, one mouse, two office chairs and code image inside two computer screens all in office room, the light in the room is bright, near the windows there is a gorgeous indoor plant and pot, picture is bright and high resolution
- bright, realistic urban street scene — complete with small houses, four pedestrians, one walking a dog while wearing a dress and hat, two cars (blue and red) with visible licence plates, a large corner tree, and other everyday urban elements like bins, bicycles, greenery, and pavement details
- create on black table 10 objects in iron as a pyramid, a sphere, triangular prism, cone, hexagonal prism all 3D objects reflecting light, add spheres of different radius in a mix composition. The picture is very bright
- realistic room with different musical instruments, piano, guitar, violin, trumpet, xylophone, two lamps, a stool, a large plant in a pot, a table in wood in the back. Picture need to be realistic, in high resolution and bright

## <a name="license"></a>License

This project is licensed under the MIT License - See [LICENSE](../LICENSE) file for details.

`Tag: Azure AI Vision ImageAnalysis` <br>
`date: 18-11-2026`
