from openai import AzureOpenAI
import os
import base64
from PIL import Image
import dotenv
import json
from io import BytesIO

# import dotenv
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
    #            high (default for gpt-image-1/1.5; better quality)
    # output_format      - Image format: PNG or JPEG (default: PNG)
    # output_compression - Compression level: 0-100 (default: 100)
    # stream             - Enable streaming: true or false
    # partial_images     - Number of partial images during streaming: 1-3
    # background         - Set to transparent for transparent background (requires PNG format)
    # NOTE: gpt-image-1 returns base64-encoded images only (no URL option)
    # 'A sunlit indoor lounge area with a modern infinity pool, contemporary architecture, natural lighting. some people relaxing by the poolside, enjoying the warm atmosphere.', 
    result = client.images.generate(
        model=model,
        prompt='shafts of natural shining light stream through the window, illuminating the intricate mechanics of the large skeleton wall clock. Sunlight dances across the exposed, brass-toned cogwheels, catching the light. cogwheels shows the internal mechanism of the clock. do not use cartoon style but real picture',    # Enter your prompt text here
        size='1024x1024',
        n=1,
        quality='high',
        output_format='jpeg'
    )
    # The code responds with a JSON object that contains the base64-encoded image.
    # gpt-image-1 returns images in base64 format (no URL option)
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