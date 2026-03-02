import os
import json
import re
from openai import OpenAI
from dotenv import load_dotenv
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

class ValidationAgent:
    """Connects to the standalone MCP Server to validate data."""
    def __init__(self, server_script_path=r"/home/george/Civil-Servant-Agent/src/mcp_server.py"):
        # Tell the client how to launch the MCP server
        self.server_params = StdioServerParameters(
            command="python",
            args=[server_script_path]
        )

    async def _async_validate(self, cnp: str) -> str:
        """The actual async connection to the MCP Server."""
        # Open a secure stdio connection to the server process
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # Execute the tool on the remote server
                result = await session.call_tool("verify_cnp", arguments={"cnp": cnp})
                
                # MCP returns a list of content blocks. We want the text of the first one.
                return result.content[0].text

    def validate_cnp(self, cnp: str) -> str:
        """Synchronous wrapper so UniversalAgent doesn't need to await."""
        print(f"🔒 [ValidationAgent] Calling external MCP Server for CNP: {cnp}")
        try:
            return asyncio.run(self._async_validate(cnp))
        except Exception as e:
            print(f"❌ [ValidationAgent] MCP Connection Error: {e}")
            return json.dumps({"valid": False, "error": "Validation service offline."})


class UniversalAgent:
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("API Key missing. Set OPENAI_API_KEY in .env")
        self.client = OpenAI(api_key=self.api_key)
        self.validation_agent = ValidationAgent()

    def think(self, history, current_data, service_config):
        """
        Generic Reasoning Engine with A2A Interception for MCP Validation.
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
            # 1. Standard LLM Extraction
            res = self.client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=messages, 
                temperature=0.0, # Robotic precision
                response_format={"type": "json_object"}
            )
            parsed_response = json.loads(res.choices[0].message.content)

            # =========================================================
            # 2. A2A INTERCEPT: Validate Extracted Data via Peer Agent
            # =========================================================
            extracted_data = parsed_response.get("extracted", {})
            
            # Look for the CNP key (case-insensitive search just in case the LLM outputs "cnp")
            cnp_key = next((k for k in extracted_data.keys() if k.upper() == "CNP"), None)

            if cnp_key:
                candidate_cnp = extracted_data[cnp_key]
                
                # Delegate to the ValidationAgent (which hits the MCP server)
                validation_json = self.validation_agent.validate_cnp(candidate_cnp)
                validation_result = json.loads(validation_json)

                # If the MCP Server rejects the CNP, override the LLM's planned response
                if not validation_result.get("valid"):
                    print(f"❌ [System] Invalid CNP detected. Overriding LLM.")
                    
                    # Remove the bad data so your main app loop doesn't save it
                    parsed_response["extracted"].pop(cnp_key, None)
                    
                    # Force the agent to ask the user again
                    parsed_response["action"] = "CONTINUE"
                    error_msg = validation_result.get("error", "CNP not found.")
                    parsed_response["message"] = f"I checked the national registry, but there was an issue: {error_msg} Could you please double-check your CNP and provide it again?"
                else:
                    citizen_name = validation_result.get("data", {}).get("name", "Citizen")
                    print(f"✅ [System] CNP Validated successfully for: {citizen_name}")

            return parsed_response

        except Exception as e:
            return {"message": f"Error: {e}", "extracted": {}, "action": "CONTINUE"}