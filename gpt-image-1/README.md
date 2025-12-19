# Azure OpenAI GPT-Image-1 Sample Scripts

This repository contains Python scripts demonstrating various image generation and editing capabilities using Azure OpenAI's GPT-Image-1 model.

## Prerequisites

- Python 3.7+
- Azure OpenAI service with GPT-Image-1 deployment
- Required packages: `openai`, `pillow`, `requests`, `python-dotenv`

Run the explae in python virtuak environment. <br>
Inside the python virtual enviroment, install the dependencies:
```bash
pip install -r requirements.txt
```

## Environment Setup

Create a `.env` file with the following variables:
```
AZURE_OPENAI_ENDPOINT=your_endpoint_here
AZURE_OPENAI_API_KEY=your_api_key_here
AZURE_OPENAI_DEPLOYMENT=your_deployment_name_here
```

## Scripts

### aoai-app.py
Basic image generation using Azure OpenAI GPT-Image-1 model.
- Generates a single image from a text prompt
- Saves image in JPEG format
- Displays the generated image
- Demonstrates model parameters (size, quality, output format)

### aoai-app-multiple.py
Batch image generation from multiple prompts.
- Generates multiple images sequentially
- Uses different prompts for variety
- Saves each image with an index (generated-image-1.jpg, generated-image-2.jpg, etc.)
- Displays all generated images at completion


### aoai-app-variation-rest.py
Creates image edits using the REST API directly.
- Demonstrates REST API usage with multipart/form-data
- Edits an existing image with a prompt
- The script preserves original image dimensions by resizing output
- Shows how to handle base64-encoded responses
- Useful for understanding the underlying API structure


### aoai-solution.py
Complete example with metaprompts and content safety.
- Demonstrates using metaprompts to control output
- Implements content filtering for safe-for-work images
- Generates child-appropriate content
- Shows best practices for prompt engineering

## GPT-Image-1 Model Features

The scripts demonstrate these GPT-Image-1 capabilities:

- **Supported sizes**: 1024x1024 (square), 1024x1536 (portrait), 1536x1024 (landscape)
- **Quality levels**: low (fastest), medium, high (best quality)
- **Output formats**: JPEG or PNG
- **Base64 encoding**: All images returned as base64-encoded data (no URL option)
- **Image editing**: Modify existing images with text prompts
- **Batch generation**: Generate 1-10 images per request

## Output

Generated images are saved in the `images/` directory with the following naming conventions:
- `generated-image.jpg` - Single image output
- `generated-image-N.jpg` - Multiple image outputs (where N is the index)
- `generated_variation_rest.jpg` - REST API variation output
- `sol-generated-image.jpg` - Solution script output

## Notes

- GPT-Image-1 returns base64-encoded images only (no URL option like DALL-E)
- API version used: `2025-04-01-preview`
- All scripts display generated images using the system's default image viewer


## License

This is a sample project for educational purposes.
