# src/agent.py — Multi-Agent Orchestration Engine
import os
import json
import re
import asyncio
from openai import OpenAI
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

MCP_SERVER_PATH = os.path.join(os.path.dirname(__file__), "mcp_server.py")


# ─── Base MCP Client ────────────────────────────────────────────────────────

class MCPClient:
    """Generic async MCP client. Connects, calls a tool, returns result."""

    def __init__(self, server_script: str = MCP_SERVER_PATH):
        self.server_params = StdioServerParameters(command="python", args=[server_script])

    async def _call(self, tool_name: str, arguments: dict) -> str:
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments=arguments)
                return result.content[0].text

    def call(self, tool_name: str, arguments: dict) -> str:
        try:
            return asyncio.run(self._call(tool_name, arguments))
        except Exception as e:
            return json.dumps({"error": f"MCP connection failed: {e}"})

    async def list_tools_async(self):
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.list_tools()

    def list_tools(self):
        try:
            return asyncio.run(self.list_tools_async())
        except Exception as e:
            return []


# ─── Specialist Sub-Agents ──────────────────────────────────────────────────

class ValidationAgent:
    """Validates Romanian CNP numbers via MCP registry tool."""

    def __init__(self):
        self.mcp = MCPClient()

    def run(self, cnp: str) -> dict:
        print(f"🔍 [ValidationAgent] Verifying CNP: {cnp}")
        raw = self.mcp.call("verify_cnp", {"cnp": cnp})
        result = json.loads(raw)
        print(f"   → Result: {result}")
        return result


class VehicleAgent:
    """Cross-checks VIN numbers against the national vehicle registry."""

    def __init__(self):
        self.mcp = MCPClient()

    def run(self, vin: str) -> dict:
        print(f"🚗 [VehicleAgent] Checking VIN: {vin}")
        raw = self.mcp.call("check_vehicle_status", {"vin": vin})
        result = json.loads(raw)
        print(f"   → Result: {result}")
        return result


class AppointmentAgent:
    """Fetches available appointment slots for the active service."""

    def __init__(self):
        self.mcp = MCPClient()

    def run(self, service_type: str) -> dict:
        print(f"📅 [AppointmentAgent] Fetching slots for: {service_type}")
        raw = self.mcp.call("get_available_appointments", {"service_type": service_type})
        return json.loads(raw)


class DocumentCheckerAgent:
    """Returns the physical document checklist for a service."""

    def __init__(self):
        self.mcp = MCPClient()

    def run(self, service_type: str) -> dict:
        print(f"📋 [DocumentCheckerAgent] Getting docs for: {service_type}")
        raw = self.mcp.call("check_required_documents", {"service_type": service_type})
        return json.loads(raw)


class TimingAgent:
    """Estimates processing time, supports urgent mode."""

    def __init__(self):
        self.mcp = MCPClient()

    def run(self, service_type: str, urgent: bool = False) -> dict:
        print(f"⏱️ [TimingAgent] Estimating time for: {service_type} (urgent={urgent})")
        raw = self.mcp.call("estimate_processing_time", {"service_type": service_type, "is_urgent": urgent})
        return json.loads(raw)


# ─── Orchestrator ───────────────────────────────────────────────────────────

class Orchestrator:
    """
    Central dispatcher. Decides which specialist agents to invoke
    based on what data the UniversalAgent just extracted.
    """

    def __init__(self):
        self.validation_agent = ValidationAgent()
        self.vehicle_agent = VehicleAgent()
        self.appointment_agent = AppointmentAgent()
        self.document_agent = DocumentCheckerAgent()
        self.timing_agent = TimingAgent()

    def dispatch(self, extracted: dict, service_key: str) -> dict:
        """
        Runs relevant sub-agents in parallel (simulated) based on extracted fields.
        Returns a dict of enrichment results to fold back into the main response.
        """
        enrichments = {}

        # ── CNP Validation ──────────────────────────────────────────────────
        cnp_key = next((k for k in extracted if k.upper() == "CNP" or "CNP" in k.upper()), None)
        if cnp_key:
            cnp_val = extracted[cnp_key]
            val_result = self.validation_agent.run(cnp_val)
            enrichments["cnp_validation"] = val_result
            if not val_result.get("valid"):
                enrichments["block_cnp"] = True
                enrichments["cnp_error"] = val_result.get("error", "Invalid CNP")

        # ── VIN Validation ──────────────────────────────────────────────────
        vin_key = next((k for k in extracted if k.upper() == "VIN"), None)
        if vin_key:
            vin_result = self.vehicle_agent.run(extracted[vin_key])
            enrichments["vin_check"] = vin_result
            if vin_result.get("found") and vin_result["data"].get("status") == "Stolen":
                enrichments["block_vin"] = True

        # ── Document Checklist (on first interaction or when asked) ─────────
        if not enrichments.get("docs_fetched"):
            doc_result = self.document_agent.run(service_key)
            enrichments["documents"] = doc_result.get("required_documents", [])
            enrichments["docs_fetched"] = True

        return enrichments


# ─── Universal Agent ────────────────────────────────────────────────────────

class UniversalAgent:
    """
    Primary reasoning engine.
    Uses GPT-4o-mini to extract structured form data from conversation,
    then dispatches enrichment tasks to the Orchestrator's sub-agents.
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not set in environment.")
        self.client = OpenAI(api_key=api_key)
        self.orchestrator = Orchestrator()
        self.mcp_client = MCPClient()

    def get_mcp_tools_summary(self) -> str:
        """Returns a human-readable summary of available MCP tools."""
        tools = self.mcp_client.list_tools()
        if not tools:
            return "MCP tools unavailable."
        return ", ".join([t.name for t in getattr(tools, "tools", [])])

    def think(self, history: list, current_data: dict, service_config: dict, service_key: str = "") -> dict:
        required_fields = service_config["required_fields"]
        service_name = service_config["name"]
        missing_fields = {k: v for k, v in required_fields.items() if not current_data.get(k)}

        sys_prompt = f"""
You are an expert Public Administration AI Agent for: "{service_name}".

GOAL: Collect these exact fields: {json.dumps(required_fields)}.
ALREADY COLLECTED: {json.dumps(current_data)}.
STILL MISSING: {json.dumps(missing_fields)}.

INSTRUCTIONS:
1. **Bulk Extraction**: Parse full narratives and extract ALL possible fields at once.
2. **Context Awareness**: Never re-ask for already collected fields.
3. **Smart Prompting**: Ask for 1-2 missing fields naturally in one question.
4. **Validation Awareness**: CNP must be 13 digits; you will be told if it passes validation.
5. **Tone**: Professional, efficient, warm. Use the citizen's name once you know it.
6. **Completion**: When all fields are collected, confirm with a summary and tell the user they can generate their PDF.

OUTPUT FORMAT (strict JSON):
{{
    "extracted": {{ "FieldKey": "Value" }},
    "message": "Natural language response to citizen",
    "action": "CONTINUE" | "DONE",
    "intent": "collect" | "clarify" | "confirm" | "inform"
}}
"""

        messages = [{"role": "system", "content": sys_prompt}]
        for r, t in history[-12:]:
            messages.append({"role": r, "content": t})

        try:
            res = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(res.choices[0].message.content)
        except Exception as e:
            return {"message": f"System error: {e}", "extracted": {}, "action": "CONTINUE", "intent": "inform"}

        extracted = parsed.get("extracted", {})

        # ── Orchestrate Sub-Agents ──────────────────────────────────────────
        enrichments = {}
        if extracted:
            enrichments = self.orchestrator.dispatch(extracted, service_key)

        # ── Handle Blocks ───────────────────────────────────────────────────
        if enrichments.get("block_cnp"):
            extracted = {k: v for k, v in extracted.items() if k.upper() != "CNP" and "CNP" not in k.upper()}
            parsed["extracted"] = extracted
            parsed["action"] = "CONTINUE"
            parsed["message"] = (
                f"⚠️ I ran your CNP through the national registry but encountered an issue: "
                f"**{enrichments['cnp_error']}** "
                f"Could you please double-check and re-enter your Personal Numerical Code?"
            )

        if enrichments.get("block_vin"):
            extracted = {k: v for k, v in extracted.items() if k.upper() != "VIN"}
            parsed["extracted"] = extracted
            parsed["action"] = "CONTINUE"
            parsed["message"] = (
                "🚨 This VIN is flagged as **stolen** in the national vehicle registry. "
                "I cannot proceed with registration. Please contact the police or your dealer."
            )

        # ── Enrich message with CNP name if validated ───────────────────────
        if enrichments.get("cnp_validation", {}).get("valid") and not enrichments.get("block_cnp"):
            name = enrichments["cnp_validation"].get("data", {}).get("name", "")
            if name and name != "Unknown Citizen" and name not in parsed.get("message", ""):
                parsed["message"] = f"✅ CNP verified for **{name}**. " + parsed.get("message", "")

        parsed["enrichments"] = enrichments
        return parsed