from openai import AzureOpenAI
import os
import requests
from PIL import Image
import dotenv
import json

# import dotenv
# load the environment variables from the .env file.
dotenv.load_dotenv()

 
# configure Azure OpenAI service client
# Assign the API version 
client = AzureOpenAI(
  api_key=os.environ['AZURE_OPENAI_API_KEY'],  # this is also the default, it can be omitted
  api_version = "2024-10-21",
  azure_endpoint=os.environ['AZURE_OPENAI_ENDPOINT'] 
  )

model = os.environ['AZURE_OPENAI_DEPLOYMENT']


try:
    # Create an image by using the image generation API
    # - prompt: it is the text prompt that is used to generate the image. 
    #           In this case, we're using the prompt "Bunny on horse, holding a lollipop, on a foggy meadow where it grows daffodils".
    #- size:    it is the size of the image that is generated. 
    #           In this case, we're generating an image that is 1024x1024 pixels.
    #- n:       it is the number of images that are generated. 
    #           In this case, we're generating 1 image.
    #           NOTE: DALL·E-3 only support n=1
    # - quality: it is a parameter that controls the quality of the generated image. (it is optional) 
    #            'standard' or 'hd' (DALL-E 3 only)
    # - style: 'vivid' or 'natural' (DALL-E 3 only)
    result = client.images.generate(
        model=model,
        prompt='shafts of natural shining light stream through the window, illuminating the intricate mechanics of the large skeleton wall clock. Sunlight dances across the exposed, brass-toned cogwheels, catching the light. cogwheels shows the internal mechanism of the clock. do not use cartoon style but real picture',    # Enter your prompt text here
        size='1024x1024',
        n=1,
        quality='standard',
        style='vivid'
    )
    # The code responds with a JSON object that contains the URL of the generated image. 
    # We can use the URL to download the image and save it to a file.
    generation_response = json.loads(result.model_dump_json())

    # Set the local directory for the stored image
    image_dir = os.path.join(os.curdir, 'images')

    # If the directory doesn't exist, create it
    if not os.path.isdir(image_dir):
        os.mkdir(image_dir)

    # Initialize the image path (note the filetype should be png)
    image_path = os.path.join(image_dir, 'generated-image.png')

    # Retrieve the generated image
    image_url = generation_response["data"][0]["url"]  # extract image URL from response
    generated_image = requests.get(image_url).content  # download the image
    with open(image_path, "wb") as image_file:
        image_file.write(generated_image)

    # Display the image in the default image viewer
    image = Image.open(image_path)
    image.show()

except Exception as err:
    print(f"Error: {err}")

finally:
    print("completed!")