import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class UniversalAgent:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API Key missing. Set OPENAI_API_KEY in .env")
        self.client = OpenAI(api_key=self.api_key)

    def think(self, history, current_data, service_config):
        """
        Generic Reasoning Engine.
        """
        required_fields = service_config["required_fields"]
        service_name = service_config["name"]

        # IMPROVED "MANTIX" PROMPT
        sys_prompt = f"""
        You are an intelligent Public Administration Agent handling: "{service_name}".
        
        GOAL: Collect these exact fields: {json.dumps(required_fields)}.
        
        INSTRUCTIONS:
        1. **Bulk Extraction:** Users may provide full narratives (e.g., "I am Ion from Bucharest..."). Extract EVERYTHING possible at once.
        2. **Validation:** 'CNP' must be 13 digits.
        3. **Context:** Only ask for fields that are missing in the 'KNOWN DATA'.
        4. **Tone:** Professional, efficient, helpful. Avoid repeating questions.
        
        OUTPUT FORMAT (JSON):
        {{
            "extracted": {{ "Field": "Value" }},
            "message": "Text to user",
            "action": "CONTINUE" or "DONE"
        }}
        """
        
        messages = [
            {"role": "system", "content": sys_prompt}, 
            {"role": "system", "content": f"KNOWN DATA: {json.dumps(current_data)}"}
        ]
        
        for r, t in history[-10:]:
            messages.append({"role": r, "content": t})

        try:
            res = self.client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=messages, 
                temperature=0.0, # Robotic precision
                response_format={"type": "json_object"}
            )
            return json.loads(res.choices[0].message.content)
        except Exception as e:
            return {"message": f"Error: {e}", "extracted": {}, "action": "CONTINUE"}