import os
import re
import json
import openai

class MetadataGenerator:
    def __init__(self, api_key=None):
        if api_key is None:
            api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise ValueError("OpenAI API key not found in environment variables")
        openai.api_key = api_key

    def generate(self, product_names, filename):
        prompt = f"Based on the following list of product names from a STEP file named '{filename}', generate a JSON metadata that includes:\n"
        prompt += "If none of the component names make sense, or too generic, ignore everything and return an empty JSON object.\n"
        prompt += "1. A brief description of what this assembly might be (json key description)\n"
        prompt += "2. Potential categories or tags for the assembly (json key categories)\n"
        prompt += "3. Estimated complexity (low, medium, high) (json key complexity)\n"
        prompt += "4. Possible industry or application (json key industry)\n"
        prompt += "5. Simplified names of components, for example if 'shaft_holder001' is a component, the name should be 'shaft_holder' or if it does not make sense do not include it (json key components)\n"
        prompt += "Product names: " + ", ".join(product_names)
        prompt += "\nProvide the response as a JSON object."

        try:
            response = openai.ChatCompletion.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system",
                        "content": "You are a helpful assistant that generates metadata for CAD assemblies."},
                    {"role": "user", "content": prompt}
                ]
            )

            content = response.choices[0].message.content.strip()
            content = re.sub(r'^```json\n|\n```$', '', content, flags=re.MULTILINE)

            metadata = json.loads(content)
            if metadata == {}:
                return None
            return metadata

        except Exception as e:
            print(f"Error generating metadata: {str(e)}")
            return None
