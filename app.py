# app.py — Civil Servant Agent v2 — Premium Light UI
import streamlit as st
import time
import json
from src.agent import UniversalAgent, TimingAgent, AppointmentAgent, DocumentCheckerAgent
from src.services import SERVICES
from src.pdf_handler import PDFHandler
from src.vision import extract_data_from_image

# ─── Page Config ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Civil Servant Agent",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS — Light Theme, Premium Design ───────────────────────────────────────
st.markdown("""
<style>
/* ── Google Fonts ─────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@300;400;500;600;700&display=swap');

/* ── Global Reset ─────────────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    background-color: #F8F9FC !important;
    color: #0F172A !important;
}

/* ── Hide Streamlit chrome ────────────────────────────────────────────────── */
#MainMenu, footer, header { visibility: hidden !important; }
.stDeployButton, [data-testid="stToolbar"] { display: none !important; }
.block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; max-width: 1400px !important; }

/* ── Sidebar ──────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: #FFFFFF !important;
    border-right: 1px solid #E2E8F0 !important;
    padding-top: 0 !important;
}
[data-testid="stSidebar"] > div { padding: 1.5rem 1rem !important; }

/* ── App Header ───────────────────────────────────────────────────────────── */
.app-header {
    padding: 0 0 1.5rem 0;
    border-bottom: 2px solid #E2E8F0;
    margin-bottom: 1.75rem;
}
.app-title {
    font-family: 'Instrument Serif', Georgia, serif !important;
    font-size: 2.4rem !important;
    font-weight: 400 !important;
    color: #0F172A !important;
    letter-spacing: -0.03em;
    line-height: 1 !important;
    margin: 0 !important;
    padding: 0 !important;
    display: inline;
}
.app-title-icon {
    font-size: 2rem;
    margin-right: 10px;
    vertical-align: middle;
}
.badge-v2 {
    display: inline-block;
    background: linear-gradient(135deg, #2563EB, #7C3AED);
    color: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    padding: 4px 12px;
    border-radius: 100px;
    vertical-align: middle;
    margin-left: 12px;
}
.app-sub {
    font-family: 'Inter', sans-serif !important;
    font-size: 0.82rem !important;
    color: #64748B !important;
    margin-top: 6px !important;
    font-weight: 400 !important;
}

/* ── Status Pill ──────────────────────────────────────────────────────────── */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: #F0FDF4;
    border: 1px solid #BBF7D0;
    color: #16A34A;
    font-size: 11px;
    font-weight: 600;
    padding: 5px 14px;
    border-radius: 100px;
    font-family: 'Inter', sans-serif;
    margin-bottom: 1.5rem;
}
.dot-green {
    width: 7px; height: 7px;
    background: #22C55E;
    border-radius: 50%;
    animation: blink 2s infinite;
}
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:.3} }

/* ── Sidebar Section Label ────────────────────────────────────────────────── */
.sidebar-label {
    font-family: 'Inter', sans-serif !important;
    font-size: 10px !important;
    font-weight: 700 !important;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #94A3B8 !important;
    margin: 1.25rem 0 0.6rem 0;
    display: block;
}

/* ── Service Buttons ──────────────────────────────────────────────────────── */
.stButton > button {
    width: 100% !important;
    text-align: left !important;
    padding: 10px 14px !important;
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    transition: all 0.15s ease !important;
    background: #F8F9FC !important;
    border: 1px solid #E2E8F0 !important;
    color: #334155 !important;
}
.stButton > button:hover {
    background: #EFF6FF !important;
    border-color: #BFDBFE !important;
    color: #2563EB !important;
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #2563EB, #1D4ED8) !important;
    border-color: transparent !important;
    color: #FFFFFF !important;
    font-weight: 600 !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.25) !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1D4ED8, #1E40AF) !important;
    box-shadow: 0 4px 12px rgba(37,99,235,0.35) !important;
    color: #FFFFFF !important;
}

/* ── Tabs ─────────────────────────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] {
    background: #F1F5F9 !important;
    border-radius: 12px !important;
    padding: 4px !important;
    gap: 2px !important;
    border: none !important;
}
.stTabs [data-baseweb="tab"] {
    background: transparent !important;
    color: #64748B !important;
    border-radius: 9px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.83rem !important;
    font-weight: 500 !important;
    padding: 7px 16px !important;
    border: none !important;
}
.stTabs [data-baseweb="tab"]:hover {
    color: #0F172A !important;
    background: rgba(255,255,255,0.7) !important;
}
.stTabs [aria-selected="true"] {
    background: #FFFFFF !important;
    color: #2563EB !important;
    font-weight: 600 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1) !important;
}

/* ── Chat Messages ────────────────────────────────────────────────────────── */
[data-testid="stChatMessage"] {
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 14px !important;
    padding: 14px 16px !important;
    margin-bottom: 10px !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
[data-testid="stChatMessage"] p {
    color: #0F172A !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.9rem !important;
    line-height: 1.6 !important;
}
[data-testid="stChatMessage"] strong {
    color: #2563EB !important;
}

/* ── Chat Input ───────────────────────────────────────────────────────────── */
[data-testid="stChatInput"] {
    border: 2px solid #E2E8F0 !important;
    border-radius: 14px !important;
    background: #FFFFFF !important;
    font-family: 'Inter', sans-serif !important;
    transition: border-color 0.2s !important;
}
[data-testid="stChatInput"]:focus-within {
    border-color: #2563EB !important;
    box-shadow: 0 0 0 3px rgba(37,99,235,0.1) !important;
}

/* ── Progress Bar ─────────────────────────────────────────────────────────── */
.stProgress > div > div {
    background: #EFF6FF !important;
    border-radius: 100px !important;
    height: 8px !important;
}
.stProgress > div > div > div {
    background: linear-gradient(90deg, #2563EB, #7C3AED) !important;
    border-radius: 100px !important;
}

/* ── Metric ───────────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
[data-testid="stMetricLabel"] p {
    color: #64748B !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.5px !important;
}
[data-testid="stMetricValue"] {
    color: #0F172A !important;
    font-size: 1.5rem !important;
    font-weight: 700 !important;
}

/* ── Field Cards ──────────────────────────────────────────────────────────── */
.field-row {
    display: flex;
    align-items: center;
    padding: 11px 0;
    border-bottom: 1px solid #F1F5F9;
    gap: 12px;
}
.field-label {
    font-family: 'Inter', sans-serif;
    font-size: 0.8rem;
    font-weight: 500;
    color: #64748B;
    width: 180px;
    flex-shrink: 0;
}
.field-filled {
    font-family: 'Inter', sans-serif;
    font-size: 0.88rem;
    font-weight: 600;
    color: #16A34A;
    background: #F0FDF4;
    border: 1px solid #BBF7D0;
    padding: 3px 10px;
    border-radius: 6px;
}
.field-empty {
    font-family: 'Inter', sans-serif;
    font-size: 0.82rem;
    color: #CBD5E1;
    font-style: italic;
}

/* ── Agent Card ───────────────────────────────────────────────────────────── */
.agent-card {
    background: #FFFFFF;
    border: 1px solid #E2E8F0;
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 12px;
    transition: box-shadow 0.2s;
}
.agent-card:hover { box-shadow: 0 4px 12px rgba(0,0,0,0.08); }
.agent-name {
    font-family: 'Inter', sans-serif;
    font-size: 0.92rem;
    font-weight: 600;
    color: #0F172A;
}
.agent-role {
    font-size: 0.75rem;
    color: #2563EB;
    font-weight: 500;
    margin: 3px 0;
}
.agent-tool {
    font-family: 'Courier New', monospace;
    font-size: 0.72rem;
    background: #F1F5F9;
    color: #475569;
    padding: 2px 7px;
    border-radius: 4px;
    display: inline-block;
    margin: 4px 0;
}
.agent-desc {
    font-size: 0.76rem;
    color: #94A3B8;
    margin-top: 4px;
}

/* ── Log Console ──────────────────────────────────────────────────────────── */
.log-console {
    background: #0F172A;
    border-radius: 12px;
    padding: 14px 16px;
    font-family: 'Courier New', monospace;
    font-size: 0.73rem;
    max-height: 180px;
    overflow-y: auto;
    border: 1px solid #1E293B;
}
.log-ok    { color: #4ADE80; display: block; margin: 2px 0; }
.log-info  { color: #60A5FA; display: block; margin: 2px 0; }
.log-warn  { color: #FCD34D; display: block; margin: 2px 0; }
.log-err   { color: #F87171; display: block; margin: 2px 0; }

/* ── Success / Info Boxes ─────────────────────────────────────────────────── */
.stSuccess, .stInfo {
    border-radius: 10px !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.85rem !important;
}

/* ── Expander ─────────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
    border: 1px solid #E2E8F0 !important;
    border-radius: 10px !important;
    background: #FFFFFF !important;
}

/* ── Divider ──────────────────────────────────────────────────────────────── */
hr { border-color: #F1F5F9 !important; }

/* ── Section title ────────────────────────────────────────────────────────── */
.section-title {
    font-family: 'Instrument Serif', Georgia, serif;
    font-size: 1.25rem;
    color: #0F172A;
    font-weight: 400;
    letter-spacing: -0.02em;
    margin-bottom: 1rem;
}

/* ── Download button ──────────────────────────────────────────────────────── */
[data-testid="stDownloadButton"] > button {
    background: linear-gradient(135deg, #2563EB, #1D4ED8) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    padding: 10px 20px !important;
    box-shadow: 0 2px 8px rgba(37,99,235,0.3) !important;
}
</style>
""", unsafe_allow_html=True)


# ─── Session State ────────────────────────────────────────────────────────────
def init_state():
    if "agent" not in st.session_state:
        try:
            st.session_state.agent = UniversalAgent()
            st.session_state.agent_ready = True
        except Exception as e:
            st.session_state.agent_ready = False
            st.session_state.agent_error = str(e)
    for key, default in [
        ("pdf_handler", PDFHandler()),
        ("current_service", "identity_card"),
        ("form_data", {}),
        ("chat_history", []),
        ("agent_log", []),
        ("enrichments", {}),
        ("appointment_data", None),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

init_state()


def add_log(msg: str, level: str = "info"):
    ts = time.strftime("%H:%M:%S")
    st.session_state.agent_log.append({"ts": ts, "msg": msg, "level": level})
    if len(st.session_state.agent_log) > 60:
        st.session_state.agent_log = st.session_state.agent_log[-60:]


def switch_service():
    st.session_state.form_data = {}
    st.session_state.chat_history = []
    st.session_state.enrichments = {}
    st.session_state.appointment_data = None
    svc = SERVICES[st.session_state.current_service]
    st.session_state.chat_history.append((
        "assistant",
        f"Hello! I'm the AI Agent for **{svc['icon']} {svc['name']}**.\n\n"
        f"{svc['description']}\n\n"
        f"Estimated processing time: **{svc['estimated_time']}**. "
        f"Please share your details and I'll fill in your application automatically."
    ))
    add_log(f"Service → {svc['name']}", "info")


if not st.session_state.chat_history:
    switch_service()

current_config = SERVICES[st.session_state.current_service]


# ─── SIDEBAR ──────────────────────────────────────────────────────────────────
with st.sidebar:
    # Logo area
    st.markdown("""
    <div style="padding: 8px 0 16px 0; border-bottom: 1px solid #F1F5F9; margin-bottom: 16px;">
        <div style="font-family:'Instrument Serif',serif; font-size:1.3rem; color:#0F172A; letter-spacing:-0.02em;">🏛️ Civil Servant</div>
        <div style="font-family:'Inter',sans-serif; font-size:0.72rem; color:#94A3B8; margin-top:2px; letter-spacing:0.5px;">AGENTIC PLATFORM v2.0</div>
    </div>
    """, unsafe_allow_html=True)

    # Status
    if st.session_state.get("agent_ready", True):
        st.markdown('<div class="status-pill"><span class="dot-green"></span>All systems operational</div>', unsafe_allow_html=True)
    else:
        st.error(f"⚠️ {st.session_state.get('agent_error', 'Agent error')}")

    # Services
    st.markdown('<span class="sidebar-label">Select Procedure</span>', unsafe_allow_html=True)
    for key, svc in SERVICES.items():
        is_active = key == st.session_state.current_service
        if st.button(
            f"{svc['icon']}  {svc['name']}",
            key=f"svc_{key}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            if key != st.session_state.current_service:
                st.session_state.current_service = key
                switch_service()
                st.rerun()

    st.divider()

    # Vision scanner
    st.markdown('<span class="sidebar-label">📷 Document Scanner</span>', unsafe_allow_html=True)
    with st.expander("Scan ID / Passport", expanded=False):
        st.caption("Upload a document image to auto-fill fields using AI Vision.")
        uploaded = st.file_uploader("Upload image", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
        if uploaded:
            if st.button("✨ Auto-Extract Fields", use_container_width=True, key="vision_btn"):
                with st.spinner("Scanning with GPT-4o Vision…"):
                    add_log("Vision scan initiated", "info")
                    raw = extract_data_from_image(uploaded, current_config["required_fields"])
                    clean = {k: v for k, v in raw.items() if k in current_config["required_fields"] and v}
                    if clean:
                        st.session_state.form_data.update(clean)
                        labels = [current_config["required_fields"][k] for k in clean]
                        st.session_state.chat_history.append((
                            "assistant",
                            f"📷 Document scanned! Auto-filled: **{', '.join(labels)}**."
                        ))
                        add_log(f"Vision extracted {len(clean)} fields", "ok")
                        st.success(f"✅ Extracted {len(clean)} fields!")
                        time.sleep(0.8)
                        st.rerun()
                    else:
                        add_log("Vision: no matching fields found", "warn")
                        st.warning("No matching fields found in image.")

    st.divider()

    # Appointments
    st.markdown('<span class="sidebar-label">📅 Appointments</span>', unsafe_allow_html=True)
    if st.button("Check Available Slots", use_container_width=True, key="appt_btn"):
        with st.spinner("Fetching via MCP…"):
            add_log("AppointmentAgent dispatched", "info")
            result = AppointmentAgent().run(st.session_state.current_service)
            st.session_state.appointment_data = result
            add_log(f"Got {len(result.get('available_slots', []))} slots", "ok")
            st.rerun()

    if st.session_state.appointment_data:
        for s in st.session_state.appointment_data.get("available_slots", [])[:3]:
            st.markdown(f"""
            <div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:8px 10px;margin-bottom:6px;">
                <div style="font-family:'Inter',sans-serif;font-size:0.8rem;font-weight:600;color:#1D4ED8;">📅 {s['date']}</div>
                <div style="font-family:'Inter',sans-serif;font-size:0.76rem;color:#3B82F6;">⏰ {s['time']} — {s['office']}</div>
            </div>
            """, unsafe_allow_html=True)


# ─── MAIN ─────────────────────────────────────────────────────────────────────

# Header
st.markdown(f"""
<div class="app-header">
    <div style="display:flex; align-items:center; gap:0; flex-wrap:wrap;">
        <span class="app-title-icon">🏛️</span>
        <span class="app-title">Civil Servant Agent</span>
        <span class="badge-v2">v2.0 — Multi-Agent</span>
    </div>
    <div class="app-sub">Powered by GPT-4o &nbsp;·&nbsp; MCP Registry &nbsp;·&nbsp; 5 Specialist Sub-Agents &nbsp;·&nbsp; Agentic Orchestration</div>
</div>
""", unsafe_allow_html=True)

# Active service header
svc_icon = current_config.get("icon", "📋")
st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:1.25rem;">
    <span style="font-size:1.5rem;">{svc_icon}</span>
    <span style="font-family:'Instrument Serif',serif;font-size:1.5rem;color:#0F172A;font-weight:400;letter-spacing:-0.02em;">{current_config['name']}</span>
</div>
""", unsafe_allow_html=True)

# ─── Tabs ─────────────────────────────────────────────────────────────────────
tab_chat, tab_case, tab_docs, tab_agents = st.tabs([
    "💬 Conversation",
    "📋 Live Case File",
    "📂 Document Checklist",
    "🤖 Agent Activity",
])

# ══════════════════════════════════════════════════════════════
# TAB 1 — CONVERSATION
# ══════════════════════════════════════════════════════════════
with tab_chat:
    req_fields = current_config["required_fields"]
    filled = sum(1 for k in req_fields if st.session_state.form_data.get(k))
    total = len(req_fields)
    pct = filled / total if total else 0

    # Progress row
    c1, c2, c3 = st.columns([1, 4, 2])
    with c1:
        st.metric("Fields", f"{filled} / {total}")
    with c2:
        st.markdown("<div style='margin-top:28px;'>", unsafe_allow_html=True)
        st.progress(pct)
        st.markdown("</div>", unsafe_allow_html=True)
    with c3:
        if filled == total:
            st.markdown("""
            <div style='background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;padding:10px 14px;margin-top:8px;'>
                <span style='font-family:Inter,sans-serif;font-size:0.82rem;font-weight:600;color:#16A34A;'>🎉 Ready to generate PDF</span>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style='background:#FFF7ED;border:1px solid #FED7AA;border-radius:10px;padding:10px 14px;margin-top:8px;'>
                <span style='font-family:Inter,sans-serif;font-size:0.82rem;font-weight:600;color:#EA580C;'>{total - filled} field(s) remaining</span>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    # Chat container
    chat_container = st.container(height=450)
    with chat_container:
        for role, text in st.session_state.chat_history:
            avatar = "🏛️" if role == "assistant" else "👤"
            st.chat_message(role, avatar=avatar).markdown(text)

    # Input
    if user_input := st.chat_input("Describe yourself or answer the question above…"):
        st.session_state.chat_history.append(("user", user_input))
        add_log(f"User input ({len(user_input)} chars)", "info")

        with st.spinner("🤖 Orchestrating agents…"):
            response = st.session_state.agent.think(
                st.session_state.chat_history,
                st.session_state.form_data,
                current_config,
                service_key=st.session_state.current_service,
            )

        extracted = response.get("extracted", {})
        if extracted:
            valid = {k: v for k, v in extracted.items() if k in req_fields}
            st.session_state.form_data.update(valid)
            add_log(f"Extracted: {list(valid.keys())}", "ok")

        enrichments = response.get("enrichments", {})
        st.session_state.enrichments = enrichments

        if enrichments.get("cnp_validation"):
            v = enrichments["cnp_validation"]
            add_log(f"ValidationAgent → valid={v.get('valid')}", "ok" if v.get("valid") else "err")
        if enrichments.get("vin_check"):
            add_log(f"VehicleAgent → found={enrichments['vin_check'].get('found')}", "info")
        if enrichments.get("documents"):
            add_log(f"DocumentAgent → {len(enrichments['documents'])} docs", "info")

        st.session_state.chat_history.append(("assistant", response.get("message", "Could you clarify?")))
        st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 2 — LIVE CASE FILE
# ══════════════════════════════════════════════════════════════
with tab_case:
    st.markdown('<div class="section-title">Collected Data</div>', unsafe_allow_html=True)

    req_fields = current_config["required_fields"]
    has_any = False
    rows_html = ""
    for key, label in req_fields.items():
        val = st.session_state.form_data.get(key, "")
        if val:
            has_any = True
            val_html = f'<span class="field-filled">{val}</span>'
            dot = "🟢"
        else:
            val_html = '<span class="field-empty">Awaiting input…</span>'
            dot = "⚪"
        rows_html += f"""
        <div class="field-row">
            <span style="font-size:8px;color:{'#22C55E' if val else '#CBD5E1'}">{'●' if val else '○'}</span>
            <span class="field-label">{label}</span>
            {val_html}
        </div>"""

    st.markdown(f'<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;padding:16px 20px;">{rows_html}</div>', unsafe_allow_html=True)

    # Registry result
    enrichments = st.session_state.enrichments
    if enrichments.get("cnp_validation", {}).get("valid"):
        data = enrichments["cnp_validation"].get("data", {})
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">🔒 Registry Verification</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("Name", data.get("name", "—"))
        col2.metric("Status", data.get("status", "—"))
        col3.metric("Date of Birth", data.get("dob", "—"))

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    b1, b2 = st.columns(2)

    if b1.button("🔄 Reset Case", use_container_width=True):
        switch_service()
        add_log("Case reset", "warn")
        st.rerun()

    if has_any:
        if b2.button("🖨️ Generate PDF", type="primary", use_container_width=True):
            with st.spinner("Generating official document…"):
                add_log("PDF generation started", "info")
                success = st.session_state.pdf_handler.fill_form(
                    data=st.session_state.form_data,
                    service_config=current_config,
                    output_name="Application.pdf",
                )
            if success:
                add_log("PDF generated ✓", "ok")
                st.success("✅ Document generated successfully!")
                with open("Application.pdf", "rb") as f:
                    st.download_button(
                        "⬇️ Download Application PDF",
                        f,
                        file_name=current_config["template_file"],
                        mime="application/pdf",
                        use_container_width=True,
                    )
            else:
                add_log("PDF generation failed", "err")
                st.error("PDF generation failed. Check the agent log.")


# ══════════════════════════════════════════════════════════════
# TAB 3 — DOCUMENT CHECKLIST
# ══════════════════════════════════════════════════════════════
with tab_docs:
    st.markdown('<div class="section-title">Required Physical Documents</div>', unsafe_allow_html=True)
    st.caption("Bring these originals and copies when submitting at the government office.")

    doc_list = st.session_state.enrichments.get("documents")

    if not doc_list:
        if st.button("🔍 Fetch Document Checklist via MCP", use_container_width=True):
            with st.spinner("Contacting DocumentChecker sub-agent via MCP…"):
                add_log("DocumentCheckerAgent dispatched", "info")
                result = DocumentCheckerAgent().run(st.session_state.current_service)
                doc_list = result.get("required_documents", [])
                st.session_state.enrichments["documents"] = doc_list
                add_log(f"{len(doc_list)} docs required", "ok")
                st.rerun()
    else:
        for i, doc in enumerate(doc_list, 1):
            st.markdown(f"""
            <div style="display:flex;gap:12px;align-items:flex-start;padding:10px 0;border-bottom:1px solid #F1F5F9;">
                <span style="background:#EFF6FF;color:#2563EB;font-weight:700;font-size:0.72rem;padding:2px 8px;border-radius:100px;margin-top:1px;flex-shrink:0;">{i}</span>
                <span style="font-family:'Inter',sans-serif;font-size:0.87rem;color:#334155;">{doc}</span>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">⏱️ Processing Times</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"""
        <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:16px;">
            <div style="font-family:'Inter',sans-serif;font-size:0.72rem;font-weight:700;color:#16A34A;text-transform:uppercase;letter-spacing:1px;">Standard</div>
            <div style="font-family:'Instrument Serif',serif;font-size:1.3rem;color:#0F172A;margin-top:4px;">{current_config['estimated_time']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_b:
        if st.button("⚡ Get Urgent Estimate via MCP", use_container_width=True):
            with st.spinner("Checking urgent processing…"):
                add_log("TimingAgent dispatched (urgent)", "info")
                result = TimingAgent().run(st.session_state.current_service, urgent=True)
                st.markdown(f"""
                <div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:16px;">
                    <div style="font-family:'Inter',sans-serif;font-size:0.72rem;font-weight:700;color:#EA580C;text-transform:uppercase;letter-spacing:1px;">Urgent</div>
                    <div style="font-family:'Instrument Serif',serif;font-size:1.3rem;color:#0F172A;margin-top:4px;">{result.get('estimated_time','—')}</div>
                    <div style="font-size:0.75rem;color:#94A3B8;margin-top:6px;">{result.get('fee_note','')}</div>
                </div>
                """, unsafe_allow_html=True)
                add_log(f"Urgent: {result.get('estimated_time')}", "ok")


# ══════════════════════════════════════════════════════════════
# TAB 4 — AGENT ACTIVITY
# ══════════════════════════════════════════════════════════════
with tab_agents:
    st.markdown('<div class="section-title">Multi-Agent Orchestration Monitor</div>', unsafe_allow_html=True)

    agents_data = [
        ("🧠", "UniversalAgent", "Reasoning Engine", "GPT-4o-mini · JSON extraction", "Extracts entities from natural language, drives conversation flow"),
        ("🔍", "ValidationAgent", "CNP Validator", "MCP → verify_cnp", "Validates Romanian CNP with mod-11 checksum + registry lookup"),
        ("🚗", "VehicleAgent", "VIN Checker", "MCP → check_vehicle_status", "Cross-checks VINs; flags stolen or unregistered vehicles"),
        ("📅", "AppointmentAgent", "Scheduler", "MCP → get_available_appointments", "Fetches real-time office appointment slots"),
        ("📋", "DocumentAgent", "Document Checker", "MCP → check_required_documents", "Returns the official per-service document checklist"),
        ("⏱️", "TimingAgent", "Processing Timer", "MCP → estimate_processing_time", "Standard and urgent processing time estimates"),
    ]

    cols = st.columns(3)
    for i, (icon, name, role, tool, desc) in enumerate(agents_data):
        with cols[i % 3]:
            st.markdown(f"""
            <div class="agent-card">
                <div style="font-size:1.4rem;margin-bottom:6px;">{icon}</div>
                <div class="agent-name">{name}</div>
                <div class="agent-role">{role}</div>
                <div class="agent-tool">{tool}</div>
                <div class="agent-desc">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">🖥️ Live Agent Log</div>', unsafe_allow_html=True)

    if st.session_state.agent_log:
        lines = ""
        for entry in reversed(st.session_state.agent_log[-25:]):
            css = entry["level"]
            lines += f'<span class="log-{css}">[{entry["ts"]}]  {entry["msg"]}</span>'
        st.markdown(f'<div class="log-console">{lines}</div>', unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="log-console">
            <span class="log-info">[system]  Waiting for agent activity…</span>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("🗑️ Clear Log", key="clear_log"):
        st.session_state.agent_log = []
        st.rerun()