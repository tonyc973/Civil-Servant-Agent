import base64
from openai import OpenAI
import streamlit as st
import json
import os

def encode_image(uploaded_file):
    return base64.b64encode(uploaded_file.getvalue()).decode('utf-8')

def extract_data_from_image(uploaded_file, required_fields):
    # 1. SETUP API KEY
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        try:
            api_key = st.secrets["OPENAI_API_KEY"]
        except:
            pass
            
    if not api_key:
        st.error("Missing OpenAI API Key.")
        return {}

    client = OpenAI(api_key=api_key)
    base64_image = encode_image(uploaded_file)
    
    # 2. CREATE A STRICT PROMPT
    # We list the fields but add specific rules to stop guessing.
    fields_list = list(required_fields.keys())
    
    prompt = f"""
    Analyze this Romanian Identity document. Extract the following fields: {json.dumps(fields_list)}.

    CRITICAL RULES:
    1. **Strict Extraction:** Only extract text that is EXPLICITLY visible on the card.
    2. **No Hallucinations:** Romanian IDs usually DO NOT contain Parents' Names (Father/Mother). If these are not written on the card, return null.
    3. **Do NOT use placeholders:** Do not return "Not provided", "N/A", or "Unknown". Return null (None) for missing fields.
    4. **Name Logic:** The "Prenume" on the card is the Person's First Name. Do NOT mistakenly use it for "Father's Name".
    
    Return the result as a raw JSON object.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o", # gpt-4o is better at reading text than mini
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ],
                }
            ],
            max_tokens=500,
            response_format={"type": "json_object"}
        )
        
        # 3. PARSE AND CLEAN
        content = response.choices[0].message.content
        data = json.loads(content)
        
        # Final Safety Filter: Remove any nulls or "N/A" strings that slipped through
        clean_data = {}
        for k, v in data.items():
            if v and str(v).lower() not in ["null", "none", "n/a", "not provided"]:
                clean_data[k] = v
                
        return clean_data

    except Exception as e:
        st.error(f"Vision Error: {e}")
        return {}