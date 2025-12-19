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

# Set the local directory for the stored images
image_dir = os.path.join(os.curdir, 'images')

# If the directory doesn't exist, create it
if not os.path.isdir(image_dir):
    os.mkdir(image_dir)

# Define multiple prompts for image generation
prompts = [
    'A serene mountain landscape at sunset with snow-capped peaks reflected in a crystal clear lake. do not use cartoon style, but real picture',
    'A futuristic cityscape at night with neon lights and flying vehicles, cyberpunk style. do not use cartoon style, but real picture',
    'A cozy coffee shop interior with warm lighting, wooden furniture, and people reading books. do not use cartoon style, but real picture',
    'A majestic lion standing on a rock overlooking the African savanna at golden hour. do not use cartoon style, but real picture',
    'An underwater coral reef scene with colorful fish and marine life, vibrant and detailed. do not use cartoon style, but real picture'
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
