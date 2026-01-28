import streamlit as st
import time
from src.agent import UniversalAgent
from src.services import SERVICES
from src.pdf_handler import PDFHandler

# --- PAGE CONFIG ---
st.set_page_config(page_title="Agentic Gov", page_icon="🟢", layout="wide")

# --- LOAD CSS ---
try:
    with open("assets/styles.css") as f:
        st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)
except: pass

# --- STATE INITIALIZATION ---
if "agent" not in st.session_state:
    st.session_state.agent = UniversalAgent()
    st.session_state.pdf_handler = PDFHandler()
if "current_service" not in st.session_state:
    st.session_state.current_service = "identity_card"
if "form_data" not in st.session_state:
    st.session_state.form_data = {}
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

def switch_service():
    """Clears history and sets new context greeting."""
    st.session_state.form_data = {}
    st.session_state.chat_history = []
    srv_name = SERVICES[st.session_state.current_service]["name"]
    # Add initial greeting
    st.session_state.chat_history.append(("assistant", f"Hello. I am the AI Agent for **{srv_name}**. Please provide the details to begin."))

# Ensure greeting exists on first load
if not st.session_state.chat_history:
    switch_service()

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("### ⚙️ Procedure Selector")
    
    # Get list of keys
    service_keys = list(SERVICES.keys())
    
    # Robust index finding
    try:
        current_index = service_keys.index(st.session_state.current_service)
    except ValueError:
        current_index = 0

    selected_key = st.selectbox(
        "Active Service",
        options=service_keys,
        format_func=lambda x: SERVICES[x]["name"],
        index=current_index
    )

    if selected_key != st.session_state.current_service:
        st.session_state.current_service = selected_key
        switch_service()
        st.rerun()

    st.divider()
    st.info("System Status: Online 🟢")

# --- MAIN HEADER ---
current_config = SERVICES[st.session_state.current_service]
st.markdown(f"## 🟢 Agentic Core | {current_config['name']}")

# --- DUAL VIEW LAYOUT ---
col_chat, col_dash = st.columns([1, 1], gap="large")

# === LEFT PANEL: CHAT ===
with col_chat:
    chat_box = st.container(height=500)
    with chat_box:
        for r, t in st.session_state.chat_history:
            st.chat_message(r, avatar="🟢" if r=="assistant" else "👤").markdown(t)

    # Input Field
    if user_input := st.chat_input("Type here..."):
        # 1. User Message (Display immediately)
        st.session_state.chat_history.append(("user", user_input))
        chat_box.chat_message("user", avatar="👤").markdown(user_input)
        
        # 2. Agent Thinking
        with st.spinner("Agentic Core processing..."):
            response = st.session_state.agent.think(
                st.session_state.chat_history, 
                st.session_state.form_data, 
                current_config
            )
            time.sleep(0.3) 
            
        # 3. HANDLE RESPONSE (The Logic Fix)
        
        # A. Update Data first (if any)
        if response.get("extracted"):
            st.session_state.form_data.update(response["extracted"])
            
        # B. Save Agent Message to History
        msg = response.get("message", "I didn't understand.")
        st.session_state.chat_history.append(("assistant", msg))
        
        # C. Force Rerun (NOW it is safe, because history is saved)
        st.rerun()

# === RIGHT PANEL: DASHBOARD ===
with col_dash:
    st.subheader("📋 Live Case File")
    
    # Progress Bar
    req_fields = current_config["required_fields"]
    filled = len(st.session_state.form_data)
    total = len(req_fields)
    progress = min(filled/total, 1.0)
    
    c1, c2 = st.columns([1, 3])
    c1.metric("Fields", f"{filled}/{total}")
    c2.progress(progress)
    
    # Live Form Visualization
    with st.container(border=True):
        for key, label in req_fields.items():
            val = st.session_state.form_data.get(key, "")
            
            row = st.columns([1, 2])
            row[0].markdown(f"**{label}**")
            
            if val:
                row[1].success(val)
            else:
                row[1].caption("Waiting for input...")
                
    # Actions
    st.markdown("---")
    b1, b2 = st.columns(2)
    
    if b1.button("🔄 Reset Case"):
        switch_service()
        st.rerun()
        
    # Generate PDF Logic
    if filled > 0:
        if b2.button("🖨️ Generate PDF", type="primary"):
            success = st.session_state.pdf_handler.fill_form(
                data=st.session_state.form_data, 
                service_config=current_config, 
                output_name="Application.pdf"
            )
            if success:
                st.success("Document Generated!")
                with open("Application.pdf", "rb") as f:
                    st.download_button("⬇️ Download PDF", f, f"{current_config['template_file']}", "application/pdf")
            else:
                st.error("Error generating PDF. Check console.")