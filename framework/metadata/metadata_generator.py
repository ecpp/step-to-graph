import os
import re
import json
import openai
import logging
from typing import List, Optional
import base64
from PIL import Image
import io

class MetadataGenerator:
    def __init__(self, api_key=None):
        if api_key is None:
            api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key not found in environment variables")
        self.client = openai.OpenAI(api_key=api_key)

    def generate(self, product_names: List[str], filename: str, images_folder: Optional[str] = None):
        if product_names:
            prompt = (
                f"Based on the following list of product names from a STEP file named '{filename}', generate a JSON metadata that includes:\n"
                "If none of the component names make sense, or too generic, ignore everything and return an empty JSON object.\n"
                "For potential categories consider at most 2 categories that are most likely.\n"
                "1. A very brief description (but not too generic) of what this assembly might be (json key description)\n"
                "2. Potential categories (not too generic) or tags for the assembly (json key categories)\n"
                "3. Estimated complexity (low, medium, high) (json key complexity)\n"
                "4. Possible industry or application (json key industry)\n"
                "5. Simplified names of components, for example if 'shaft_holder001' is a component, the name should be 'shaft_holder' or if it does not make sense do not include it (json key components)\n"
                f"Product names: {', '.join(product_names)}\n"
                "Provide the response as a JSON object."
            )

            try:
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates metadata for CAD assemblies."},
                        {"role": "user", "content": prompt}
                    ]
                )

                content = response.choices[0].message.content.strip()
                content = re.sub(r'^```json\n|\n```$', '', content, flags=re.MULTILINE)

                metadata = json.loads(content)

                if metadata == {} and images_folder:
                    logging.warning(f"No metadata generated using part names for {filename}, trying with images")
                    return self.generate_from_images(images_folder, filename)
                logging.info(f"Metadata generated for {filename}")
                return metadata

            except Exception as e:
                logging.error(f"Error generating metadata with product names: {str(e)}")
                if images_folder:
                    return self.generate_from_images(images_folder, filename)
                return None
        elif images_folder:
            return self.generate_from_images(images_folder, filename)
        else:
            logging.warning("No product names or images provided for metadata generation.")
            return None

    def generate_from_images(self, images_folder: str, filename: str):
        try:
            encoded_images = []
            image_files = [f for f in os.listdir(images_folder) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
            
            for image_file in image_files:
                image_path = os.path.join(images_folder, image_file)
                with Image.open(image_path) as img:
                    # Convert to grayscale
                    img = img.convert('L')
                    # Resize image (adjust dimensions as needed)
                    img.thumbnail((300, 300))
                    # Compress image
                    buffer = io.BytesIO()
                    img.save(buffer, format="JPEG", optimize=True, quality=75)
                    #also save to local
                    #img.save(os.path.join(images_folder, image_file), format="JPEG", optimize=True, quality=75)
                    compressed_image = buffer.getvalue()
                    encoded_string = base64.b64encode(compressed_image).decode('utf-8')
                    encoded_images.append(encoded_string)

            prompt = (
                f"Based on the following images of a STEP file named '{filename}', generate a JSON metadata that includes:\n"
                "For potential categories consider at most 2 categories that are most likely.\n"
                "1. A very brief description (but not too generic) of what this assembly might be (json key description)\n"
                "2. Potential categories (not too generic) or tags for the assembly (json key categories)\n"
                "3. Estimated complexity (low, medium, high) (json key complexity)\n"
                "4. Possible industry or application (json key industry)\n"
                "5. Simplified names of components present in the images (json key components)\n"
                "Provide the response as a JSON object."
            )

            messages = [
                {"role": "system", "content": "You are a helpful assistant that generates metadata for CAD assemblies based on images."},
                {"role": "user", "content": prompt}
            ]

            for img in encoded_images:
                messages.append({"role": "user", "content": f"![image](data:image/png;base64,{img})"})

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages
            )

            content = response.choices[0].message.content.strip()
            content = re.sub(r'^```json\n|\n```$', '', content, flags=re.MULTILINE)

            metadata = json.loads(content)
            logging.info(f"Metadata generated for {filename}. Using images.")
            return metadata

        except Exception as e:
            logging.error(f"Error generating metadata with images: {str(e)}")
            return None
