import base64
import os
from openai import OpenAI

def encode_image(image_path):
    """Encodes an image to base64."""
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def describe_image(client: OpenAI, image_path: str) -> str:
    """
    Sends an image to OpenAI's GPT-4o-mini to get a detailed technical description
    suitable for RAG retrieval.
    """
    base64_image = encode_image(image_path)
    
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Describe this technical image detailedly for retrieval purposes. "
                            "Include any visible text, error codes, component names, and the state of LEDs or displays. "
                            "Be concise."
                        )
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        max_tokens=300
    )
    
    return response.choices[0].message.content
