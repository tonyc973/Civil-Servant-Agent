# src/agent.py — Motor de orchestrare AGENTICĂ (cu tool-use real)
#
# Orchestratorul nu decide prin if-uri hardcodate ce unelte cheamă. În schimb,
# MODELUL decide (function calling), pe baza datelor extrase de la cetățean.
# Uneltele sunt descoperite DINAMIC din serverul MCP (list_tools).
#
# Trei niveluri de siguranță, în ordinea robusteții:
#   1. Calea agentică   — LLM-ul alege uneltele; execuția e reală, prin MCP.
#   2. Safety sweep     — strat determinist: garantează că validările critice
#                         (CNP, VIN, documente) rulează indiferent de model.
#   3. Fallback complet — dacă stratul LLM eșuează, se revine la logica
#                         deterministă clasică.
#
# Contractul de ieșire (dict-ul `enrichments`) este consumat de app.py prin
# cheile: cnp_validation, block_cnp, cnp_error, vin_check, block_vin,
# documents, docs_fetched.

import os
import json
import asyncio
from typing import Optional
from openai import OpenAI
from dotenv import load_dotenv
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

load_dotenv()

THINK_MODEL = "gpt-4o-mini"
MCP_SERVER_PATH = os.path.join(os.path.dirname(__file__), "mcp_server.py")


# ─── Client MCP de bază ───────────────────────────────────────────────────────

class MCPClient:
    """Client MCP async generic. Se conectează, apelează o unealtă, întoarce rezultatul."""

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

    async def _list_tools(self):
        async with stdio_client(self.server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await session.list_tools()

    def list_tools(self):
        try:
            return asyncio.run(self._list_tools())
        except Exception:
            return []


# ─── Instrumente specializate (clienți MCP, pentru calea deterministă / fallback) ───────

class ValidationTool:
    """Validează CNP-uri prin unealta MCP de registru."""

    def __init__(self):
        self.mcp = MCPClient()

    def run(self, cnp: str) -> dict:
        print(f"🔍 [ValidationTool] Verific CNP: {cnp}")
        return json.loads(self.mcp.call("verify_cnp", {"cnp": cnp}))


class VehicleTool:
    """Verifică VIN-uri în registrul național de vehicule."""

    def __init__(self):
        self.mcp = MCPClient()

    def run(self, vin: str) -> dict:
        print(f"🚗 [VehicleTool] Verific VIN: {vin}")
        return json.loads(self.mcp.call("check_vehicle_status", {"vin": vin}))


class DocumentTool:
    """Întoarce lista de documente fizice necesare pentru un serviciu."""

    def __init__(self):
        self.mcp = MCPClient()

    def run(self, service_type: str) -> dict:
        print(f"📋 [DocumentTool] Documente pentru: {service_type}")
        return json.loads(self.mcp.call("check_required_documents", {"service_type": service_type}))


class AppointmentTool:
    """Obține sloturile de programare disponibile pentru serviciul activ."""

    def __init__(self):
        self.mcp = MCPClient()

    def run(self, service_type: str) -> dict:
        print(f"📅 [AppointmentTool] Sloturi pentru: {service_type}")
        return json.loads(self.mcp.call("get_available_appointments", {"service_type": service_type}))


class TimingTool:
    """Estimează timpul de procesare; suportă modul urgent."""

    def __init__(self):
        self.mcp = MCPClient()

    def run(self, service_type: str, urgent: bool = False) -> dict:
        print(f"⏱️ [TimingTool] Estimare timp pentru: {service_type} (urgent={urgent})")
        return json.loads(self.mcp.call("estimate_processing_time", {"service_type": service_type, "is_urgent": urgent}))


# ─── Orchestrator agentic ─────────────────────────────────────────────────────

class Orchestrator:
    """
    Dispecer agentic. MODELUL decide ce unelte MCP să invoce (function calling),
    pe baza datelor extrase de la cetățean. Uneltele sunt descoperite dinamic din
    serverul MCP. Un strat determinist de siguranță garantează validările critice,
    iar un fallback complet acoperă cazul în care stratul LLM eșuează.
    """

    def __init__(self):
        self.mcp = MCPClient()
        # Instrumentele sunt folosite de calea deterministă (fallback).
        self.validation_tool = ValidationTool()
        self.vehicle_tool = VehicleTool()
        self.document_tool = DocumentTool()
        # Urma apelurilor de instrumente din ultimul dispatch (pentru jurnalul UI).
        self._trace: list = []

    # ── Punct de intrare: încearcă agentic, cade pe determinist ──────────────
    def dispatch(self, extracted: dict, service_key: str, client: Optional[OpenAI] = None) -> dict:
        """
        Întoarce un dict de îmbogățiri (enrichments) cu chei canonice consumate
        de restul aplicației: cnp_validation, block_cnp, cnp_error, vin_check,
        block_vin, documents, docs_fetched (+ opțional appointments, timing).
        Cheia `tool_trace` conține urma apelurilor de instrumente, pentru jurnal.
        """
        self._trace = []        # repornim urma la fiecare cerere
        if client is not None:
            try:
                enrichments = self._dispatch_agentic(extracted, service_key, client)
                enrichments["tool_trace"] = self._trace
                return enrichments
            except Exception as e:
                print(f"⚠️ [Orchestrator] Calea agentică a eșuat ({e}); fallback determinist.")
                self._trace = []  # urma parțială nu mai e relevantă pe calea de rezervă
        enrichments = self._dispatch_deterministic(extracted, service_key)
        enrichments["tool_trace"] = self._trace
        return enrichments

    # ── Calea AGENTICĂ: modelul alege uneltele ───────────────────────────────
    def _dispatch_agentic(self, extracted: dict, service_key: str, client: OpenAI) -> dict:
        tools = self._discover_tools()

        sys_prompt = (
            "Ești creierul de orchestrare al unui agent pentru servicii publice. "
            "Pe baza datelor extrase de la cetățean, decide ce unelte de registru/verificare "
            "să apelezi. Apelează verify_cnp pentru orice CNP, check_vehicle_status pentru orice "
            "VIN, check_required_documents pentru serviciul activ. Apelează doar ce e justificat "
            "de datele primite."
        )
        user_prompt = (
            f"Serviciu activ: {service_key}\n"
            f"Date extrase: {json.dumps(extracted, ensure_ascii=False)}"
        )

        resp = client.chat.completions.create(
            model=THINK_MODEL,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tools=tools,
            tool_choice="auto",
            temperature=0,
        )

        enrichments: dict = {}
        tool_calls = resp.choices[0].message.tool_calls or []
        print(f"🧠 [Orchestrator] Modelul a ales {len(tool_calls)} unelte: "
              f"{[tc.function.name for tc in tool_calls]}")

        for tc in tool_calls:
            if tc.type != "function":
                continue  # ignoră tool-call-uri custom; folosim doar function calls
            name = tc.function.name
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            raw = self.mcp.call(name, args)            # execuție REALĂ prin MCP
            result = json.loads(raw)
            self._record(name, result, source="model")  # instrument ales de model
            self._fold(name, result, enrichments)

        # Strat determinist de siguranță: garantează verificările critice.
        self._safety_sweep(extracted, service_key, enrichments)
        return enrichments

    def _safety_sweep(self, extracted: dict, service_key: str, enrichments: dict) -> None:
        """Indiferent ce a decis modelul, CNP/VIN/documente trebuie verificate."""
        cnp_key = next((k for k in extracted if "CNP" in k.upper()), None)
        if cnp_key and "cnp_validation" not in enrichments:
            raw = self.mcp.call("verify_cnp", {"cnp": extracted[cnp_key]})
            result = json.loads(raw)
            self._record("verify_cnp", result, source="safety")
            self._fold("verify_cnp", result, enrichments)

        vin_key = next((k for k in extracted if k.upper() == "VIN"), None)
        if vin_key and "vin_check" not in enrichments:
            raw = self.mcp.call("check_vehicle_status", {"vin": extracted[vin_key]})
            result = json.loads(raw)
            self._record("check_vehicle_status", result, source="safety")
            self._fold("check_vehicle_status", result, enrichments)

        if not enrichments.get("docs_fetched"):
            raw = self.mcp.call("check_required_documents", {"service_type": service_key})
            result = json.loads(raw)
            self._record("check_required_documents", result, source="safety")
            self._fold("check_required_documents", result, enrichments)

    def _record(self, tool_name: str, result: dict, source: str) -> None:
        """Adaugă un apel de instrument în urma de execuție, pentru jurnalul în timp real.

        source: 'model' (ales de LLM), 'safety' (garantat de safety-sweep) sau
        'fallback' (calea deterministă, când stratul LLM a eșuat).
        """
        self._trace.append({"tool": tool_name, "result": result, "source": source})

    def _fold(self, tool_name: str, result: dict, enrichments: dict) -> None:
        """Mapează rezultatul oricărei unelte în cheile canonice citite în aval."""
        if tool_name == "verify_cnp":
            enrichments["cnp_validation"] = result
            if not result.get("valid"):
                enrichments["block_cnp"] = True
                enrichments["cnp_error"] = result.get("error", "Invalid CNP")
        elif tool_name == "check_vehicle_status":
            enrichments["vin_check"] = result
            if result.get("found") and result.get("data", {}).get("status") == "Furat":
                enrichments["block_vin"] = True
        elif tool_name == "check_required_documents":
            enrichments["documents"] = result.get("required_documents", [])
            enrichments["docs_fetched"] = True
        elif tool_name == "get_available_appointments":
            enrichments["appointments"] = result        # cheie nouă, ignorată în aval
        elif tool_name == "estimate_processing_time":
            enrichments["timing"] = result               # cheie nouă, ignorată în aval

    # ── Descoperire dinamică a uneltelor din serverul MCP ─────────────────────
    def _discover_tools(self) -> list:
        """Convertește uneltele MCP în formatul de tools OpenAI. Cade pe schema statică."""
        try:
            listing = self.mcp.list_tools()
            tools = []
            for t in getattr(listing, "tools", []):
                tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": (t.description or "").strip(),
                        "parameters": t.inputSchema or {"type": "object", "properties": {}},
                    },
                })
            if tools:
                return tools
        except Exception as e:
            print(f"⚠️ [Orchestrator] list_tools a eșuat ({e}); folosesc schema statică.")
        return self._STATIC_TOOLS

    # Fallback static (oglindește mcp_server.py) dacă descoperirea dinamică pică.
    _STATIC_TOOLS = [
        {"type": "function", "function": {
            "name": "verify_cnp", "description": "Verifică un CNP în registrul național.",
            "parameters": {"type": "object", "properties": {"cnp": {"type": "string"}},
                           "required": ["cnp"]}}},
        {"type": "function", "function": {
            "name": "check_vehicle_status", "description": "Caută un VIN în registrul de vehicule.",
            "parameters": {"type": "object", "properties": {"vin": {"type": "string"}},
                           "required": ["vin"]}}},
        {"type": "function", "function": {
            "name": "check_required_documents", "description": "Documentele necesare pentru un serviciu.",
            "parameters": {"type": "object", "properties": {"service_type": {"type": "string"}},
                           "required": ["service_type"]}}},
        {"type": "function", "function": {
            "name": "get_available_appointments", "description": "Programări disponibile pentru un serviciu.",
            "parameters": {"type": "object", "properties": {"service_type": {"type": "string"}},
                           "required": ["service_type"]}}},
        {"type": "function", "function": {
            "name": "estimate_processing_time", "description": "Timp estimat de procesare.",
            "parameters": {"type": "object", "properties": {
                "service_type": {"type": "string"}, "is_urgent": {"type": "boolean"}},
                "required": ["service_type"]}}},
    ]

    # ── Calea DETERMINISTĂ ─────────────────────
    def _dispatch_deterministic(self, extracted: dict, service_key: str) -> dict:
        enrichments: dict = {}

        cnp_key = next((k for k in extracted if k.upper() == "CNP" or "CNP" in k.upper()), None)
        if cnp_key:
            val_result = self.validation_tool.run(extracted[cnp_key])
            self._record("verify_cnp", val_result, source="fallback")
            enrichments["cnp_validation"] = val_result
            if not val_result.get("valid"):
                enrichments["block_cnp"] = True
                enrichments["cnp_error"] = val_result.get("error", "Invalid CNP")

        vin_key = next((k for k in extracted if k.upper() == "VIN"), None)
        if vin_key:
            vin_result = self.vehicle_tool.run(extracted[vin_key])
            self._record("check_vehicle_status", vin_result, source="fallback")
            enrichments["vin_check"] = vin_result
            if vin_result.get("found") and vin_result["data"].get("status") == "Furat":
                enrichments["block_vin"] = True

        if not enrichments.get("docs_fetched"):
            doc_result = self.document_tool.run(service_key)
            self._record("check_required_documents", doc_result, source="fallback")
            enrichments["documents"] = doc_result.get("required_documents", [])
            enrichments["docs_fetched"] = True

        return enrichments


# ─── Agentul Universal ─────────────────────────────────────────────────────────

class UniversalAgent:
    """
    Motor principal de raționament. Folosește GPT-4o-mini pentru a extrage date
    structurate din conversație, apoi deleagă orchestratorului agentic decizia de
    a invoca uneltele MCP de îmbogățire/validare.
    """

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY nu este setat în mediu.")
        self.client = OpenAI(api_key=api_key)
        self.orchestrator = Orchestrator()
        self.mcp_client = MCPClient()

    def get_mcp_tools_summary(self) -> str:
        """Întoarce un rezumat al instrumentelor MCP disponibile."""
        tools = self.mcp_client.list_tools()
        if not tools:
            return "Instrumentele MCP nu sunt disponibile."
        return ", ".join([t.name for t in getattr(tools, "tools", [])])

    def think(self, history: list, current_data: dict, service_config: dict, service_key: str = "") -> dict:
        required_fields = service_config["required_fields"]
        service_name = service_config["name"]
        missing_fields = {k: v for k, v in required_fields.items() if not current_data.get(k)}

        sys_prompt = f"""
        Ești un Agent AI expert în Administrație Publică pentru serviciul: "{service_name}".

        OBIECTIV: Colectează exact aceste câmpuri: {json.dumps(required_fields, ensure_ascii=False)}.
        DEJA COLECTATE: {json.dumps(current_data, ensure_ascii=False)}.
        ÎNCĂ LIPSESC: {json.dumps(missing_fields, ensure_ascii=False)}.

        INSTRUCȚIUNI:
        1. **Extragere în bloc**: Analizează textul complet și extrage TOATE câmpurile posibile dintr-o dată.
        2. **Conștientizarea contextului**: Nu întreba niciodată din nou pentru câmpuri deja colectate.
        3. **Întrebări inteligente**: Cere 1-2 câmpuri lipsă natural, într-o singură întrebare.
        4. **Validare**: CNP-ul trebuie să aibă 13 cifre; vei fi informat dacă trece validarea.
        5. **Ton**: Profesional, eficient, cald. Folosește numele cetățeanului odată ce îl cunoști.
        6. **Finalizare**: Când ABSOLUT TOATE câmpurile sunt colectate (STILL MISSING este gol {{}}), confirmă cu un rezumat și spune-i utilizatorului că poate genera PDF-ul.
        7. **IMPORTANT**: Răspunde ÎNTOTDEAUNA în limba ROMÂNĂ.
        8. **REGULĂ CRITICĂ**: Dacă lista ÎNCĂ LIPSESC conține cel puțin un câmp, acțiunea TREBUIE să fie "CONTINUE", NICIODATĂ "DONE". Verifică de două ori lista de câmpuri lipsă înainte de a seta acțiunea. Numără câmpurile: dacă STILL MISSING nu este gol, action = "CONTINUE".
        9. **NU inventa date**: Dacă un câmp nu a fost furnizat explicit de utilizator, NU-l extrage. Nu ghici valori.

        FORMAT DE IEȘIRE (JSON strict):
        {{
            "extracted": {{ "FieldKey": "Value" }},
            "message": "Răspuns în limbaj natural către cetățean, în limba română",
            "action": "CONTINUE" | "DONE",
            "intent": "collect" | "clarify" | "confirm" | "inform"
        }}

        ATENȚIE: action="DONE" este permis DOAR dacă, după extragerea din acest mesaj, TOATE câmpurile din lista de câmpuri obligatorii au valori (STILL MISSING devine gol). Altfel, ÎNTOTDEAUNA action="CONTINUE".
        """

        messages = [{"role": "system", "content": sys_prompt}]
        for r, t in history[-12:]:
            messages.append({"role": r, "content": t})

        try:
            res = self.client.chat.completions.create(
                model=THINK_MODEL,
                messages=messages,
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(res.choices[0].message.content)
        except Exception as e:
            return {"message": f"Eroare de sistem: {e}", "extracted": {}, "action": "CONTINUE", "intent": "inform"}

        extracted = parsed.get("extracted", {})

        # Filtrează câmpurile pe care LLM-ul le-a re-extras din istoric și care
        # coincid cu cele deja colectate — nu mai trebuie re-validate. Evită
        # apeluri MCP redundante și mesaje de tip „CNP verificat" repetate.
        extracted = {k: v for k, v in extracted.items() if current_data.get(k) != v}
        parsed["extracted"] = extracted

        # ── Orchestrare agentică a sub-uneltelor ────────────────────────────
        enrichments = {}
        if extracted:
            enrichments = self.orchestrator.dispatch(extracted, service_key, client=self.client)

        # ── Gestionare blocaje ──────────────────────────────────────────────
        if enrichments.get("block_cnp"):
            extracted = {k: v for k, v in extracted.items() if k.upper() != "CNP" and "CNP" not in k.upper()}
            parsed["extracted"] = extracted
            parsed["action"] = "CONTINUE"
            parsed["message"] = (
                f"⚠️ Am verificat CNP-ul în registrul național și am întâmpinat o problemă: "
                f"**{enrichments['cnp_error']}** "
                f"Puteți verifica și reintroduce Codul Numeric Personal?"
            )

        if enrichments.get("block_vin"):
            extracted = {k: v for k, v in extracted.items() if k.upper() != "VIN"}
            parsed["extracted"] = extracted
            parsed["action"] = "CONTINUE"
            parsed["message"] = (
                "🚨 Acest VIN este marcat ca **furat** în registrul național de vehicule. "
                "Nu pot continua cu înmatricularea. Vă rugăm contactați poliția sau dealerul."
            )

        # ── Auto-completare din registru: numele, adresa returnate de verify_cnp
        # sunt propagate ca și cum ar fi fost extrase de LLM, astfel încât panoul
        # de progres și logica de mesaj să le vadă imediat (cerința CF4).
        cnp_data = enrichments.get("cnp_validation", {}).get("data", {})
        auto_filled = []
        if cnp_data and not enrichments.get("block_cnp"):
            full_name = (cnp_data.get("name") or "").strip()
            if full_name:
                if "FullName" in required_fields and not current_data.get("FullName") \
                        and "FullName" not in extracted:
                    extracted["FullName"] = full_name
                    auto_filled.append("FullName")
                parts = full_name.split(None, 1)
                if len(parts) == 2:
                    first, last = parts[0], parts[1]
                    if "FirstName" in required_fields and not current_data.get("FirstName") \
                            and "FirstName" not in extracted:
                        extracted["FirstName"] = first
                        auto_filled.append("FirstName")
                    if "LastName" in required_fields and not current_data.get("LastName") \
                            and "LastName" not in extracted:
                        extracted["LastName"] = last
                        auto_filled.append("LastName")
            address = (cnp_data.get("address") or "").strip()
            if address and "Address" in required_fields and not current_data.get("Address") \
                    and "Address" not in extracted:
                extracted["Address"] = address
                auto_filled.append("Address")
            parsed["extracted"] = extracted

        # ── Îmbogățește mesajul cu numele de la CNP, dacă e validat ─────────
        if enrichments.get("cnp_validation", {}).get("valid") and not enrichments.get("block_cnp"):
            name = (cnp_data.get("name") or "").strip()

            if auto_filled:
                # Rescriere deterministă a mesajului: nu mai cere câmpurile pe care
                # tocmai le-am pre-completat din registru.
                merged = dict(current_data)
                merged.update(extracted)
                still_missing = {k: v for k, v in required_fields.items() if not merged.get(k)}
                auto_labels = [required_fields[k] for k in auto_filled]
                prefix = (
                    f"✅ CNP verificat pentru **{name}**. "
                    f"Am pre-completat automat din registru: "
                    f"{', '.join(['**' + lbl + '**' for lbl in auto_labels])}. "
                )
                if still_missing:
                    next_ask = list(still_missing.values())[:2]
                    parsed["action"] = "CONTINUE"
                    parsed["message"] = prefix + (
                        "Vă rog să îmi furnizați acum: "
                        + ", ".join(["**" + lbl + "**" for lbl in next_ask]) + "."
                    )
                else:
                    parsed["action"] = "DONE"
                    parsed["message"] = prefix + (
                        "Toate câmpurile sunt complete — puteți genera PDF-ul "
                        "din tab-ul **Dosar în Timp Real**."
                    )
            elif name and name != "Cetățean Necunoscut" and name not in parsed.get("message", ""):
                parsed["message"] = f"✅ CNP verificat pentru **{name}**. " + parsed.get("message", "")

        # ── Verificare server-side: nu permite DONE dacă lipsesc câmpuri ────
        if parsed.get("action") == "DONE":
            merged_data = dict(current_data)
            merged_data.update(extracted)
            still_missing = {k: v for k, v in required_fields.items() if not merged_data.get(k)}
            if still_missing:
                parsed["action"] = "CONTINUE"
                missing_labels = list(still_missing.values())
                parsed["message"] += (
                    f"\n\nÎnsă mai am nevoie de următoarele câmpuri:\n"
                    + "\n".join([f"• **{label}**" for label in missing_labels])
                )

        parsed["enrichments"] = enrichments
        return parsed


# ─── Smoke test (rulează: python -m src.agent) ────────────────────────────────

if __name__ == "__main__":
    print("=== Smoke test agent.py ===\n")
    orch = Orchestrator()

    # 1. Descoperirea dinamică a uneltelor
    discovered = orch._discover_tools()
    print(f"[1] Unelte descoperite din MCP: {[t['function']['name'] for t in discovered]}\n")

    # 2. Calea deterministă (fallback) — VIN furat trebuie blocat
    det = orch._dispatch_deterministic({"VIN": "VF1RFD00X56789012"}, "vehicle_registration")
    print(f"[2] Determinist, VIN furat → block_vin={det.get('block_vin')}\n")

    # 3. Calea agentică — modelul alege uneltele, safety sweep garantează cheile
    if os.getenv("OPENAI_API_KEY"):
        client = OpenAI()
        ag = orch.dispatch(
            {"CNP": "123", "VIN": "VF1RFD00X56789012"},
            "vehicle_registration",
            client=client,
        )
        print(f"[3] Agentic → chei: {sorted(ag.keys())}")
        print(f"    block_cnp={ag.get('block_cnp')} (CNP invalid), "
              f"block_vin={ag.get('block_vin')} (VIN furat)")
    else:
        print("[3] OPENAI_API_KEY absent — sar peste testul agentic.")
