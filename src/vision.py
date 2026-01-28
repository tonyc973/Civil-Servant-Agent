import base64
from openai import OpenAI
import streamlit as st
import json

# Initialize Client (Make sure OPENAI_API_KEY is in your environment or .streamlit/secrets.toml)
client = OpenAI()

def encode_image(uploaded_file):
    """Converts Streamlit file buffer to base64 string."""
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

def extract_data_from_image(uploaded_file, required_fields):
    """
    Sends image to GPT-4o-mini to extract specific fields.
    """
    base64_image = encode_image(uploaded_file)
    
    # Create a precise prompt based on the service requirements
    fields_str = ", ".join(required_fields.keys())
    
    prompt = f"""
    You are a government document OCR specialist. 
    Analyze this image. Extract the following fields: {fields_str}.
    
    Return ONLY a JSON object. Keys must match the requested fields exactly.
    If a field is not visible, use null.
    Do not add markdown formatting (like ```json). Just the raw JSON.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            },
                        },
                    ],
                }
            ],
            max_tokens=300,
        )
        
        # Parse the result
        content = response.choices[0].message.content
        return json.loads(content)
        
    except Exception as e:
        st.error(f"Vision Error: {e}")
        return {}