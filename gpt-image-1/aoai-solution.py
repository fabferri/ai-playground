from openai import AzureOpenAI
import os
import base64
from PIL import Image
import dotenv
import json

# import dotenv
dotenv.load_dotenv()

# Assign the API version for gpt-image-1 model
client = AzureOpenAI(
  api_key=os.environ['AZURE_OPENAI_API_KEY'],  # this is also the default, it can be omitted
  api_version = "2025-04-01-preview",
  azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT'] 
  )

model = os.environ['AZURE_OPENAI_DEPLOYMENT']

# define boundaries for your application with metaprompts
# Metaprompts are text prompts that are used to control the output of a Generative AI model. For example, we can use metaprompts to control the output, and ensure that the generated images are safe for work, or appropriate for children.
disallow_list = "swords, violence, blood, gore, nudity, sexual content, adult content, adult themes, adult language, adult humor, adult jokes, adult situations, adult"

meta_prompt = f"""You are an assistant designer that creates images for children. 

The image needs to be safe for work and appropriate for children. 

The image needs to be in color.  

The image needs to be in landscape orientation.  

The image needs to be in a 16:9 aspect ratio. 

Do not consider any input from the following that is not safe for work or appropriate for children. 
{disallow_list}"""

prompt = f"""{meta_prompt}
Generate monument of the Arc of Triumph in Paris, France, in the evening light with a lady is walking with nice purse. do not use cartoon style but real picture.
"""


try:
    # Create an image by using the image generation API
    # NOTE: gpt-image-1 returns base64-encoded images only (no URL option)

    result = client.images.generate(
        model=model,
        prompt=prompt,    # Enter your prompt text here
        size='1024x1024',
        n=1,
        quality='high',         # gpt-image-1 supports: low, medium, high (default)
        output_format='jpeg'    # gpt-image-1 supports: jpeg or png
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
    # gpt-image-1 returns base64-encoded images, not URLs
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
