# app.py — Agent Funcționar Public v3 — Ediția Seif Personal de Documente
import time
from pathlib import Path

import streamlit as st

from src.agent import UniversalAgent, TimingTool, AppointmentTool, DocumentTool
from src.services import SERVICES
from src.pdf_handler import PDFHandler
from src.vault_agent import VaultAgent, TYPE_ICONS
from src import database as db
from src import ui

# ─── Configurare Pagină ─────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agent Funcționar Public",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── CSS ─────────────────────────────────────────────────────────────────────
st.markdown(ui.load_css(), unsafe_allow_html=True)


# ─── Starea Sesiunii ─────────────────────────────────────────────────────────
def init_state():
    if "agent" not in st.session_state:
        try:
            st.session_state.agent = UniversalAgent()
            st.session_state.agent_ready = True
        except Exception as e:
            st.session_state.agent_ready = False
            st.session_state.agent_error = str(e)

    if "vault_agent" not in st.session_state:
        try:
            st.session_state.vault_agent = VaultAgent()
            st.session_state.vault_agent_ready = True
        except Exception as e:
            st.session_state.vault_agent_ready = False

    # Încarcă vault din baza de date SQLite
    if "vault" not in st.session_state:
        st.session_state.vault = db.get_vault_fields()

    if "vault_docs" not in st.session_state:
        st.session_state.vault_docs = db.get_vault_documents()

    for key, default in [
        ("pdf_handler", PDFHandler()),
        ("current_service", "identity_card"),
        ("form_data", {}),
        ("chat_history", []),
        ("agent_log", []),
        ("enrichments", {}),
        ("appointment_data", None),
        ("vault_autofill_done", False),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

init_state()


def add_log(msg: str, level: str = "info"):
    ts = time.strftime("%H:%M:%S")
    st.session_state.agent_log.append({"ts": ts, "msg": msg, "level": level})
    if len(st.session_state.agent_log) > 60:
        st.session_state.agent_log = st.session_state.agent_log[-60:]


# Iconițe pentru sursa deciziei de apelare a unui instrument MCP.
_TOOL_SOURCE_ICON = {"model": "🧠", "safety": "🛡️", "fallback": "⚙️"}


def format_tool_log(call: dict) -> tuple[str, str]:
    """Construiește (mesaj, nivel) pentru o intrare de jurnal a unui instrument MCP.

    `call` provine din `enrichments["tool_trace"]`: {tool, result, source}.
    """
    tool = call.get("tool", "?")
    res = call.get("result", {}) or {}
    icon = _TOOL_SOURCE_ICON.get(call.get("source"), "🔧")
    level = "ok"

    if tool == "verify_cnp":
        valid = res.get("valid")
        summary = "CNP valid" if valid else f"CNP invalid ({res.get('error', '')})"
        level = "ok" if valid else "err"
    elif tool == "check_vehicle_status":
        if res.get("found"):
            status = res.get("data", {}).get("status", "")
            summary = f"VIN găsit · {status}"
            level = "err" if status == "Furat" else "ok"
        else:
            summary, level = "VIN negăsit", "warn"
    elif tool == "check_required_documents":
        summary = f"{len(res.get('required_documents', []))} documente"
    elif tool == "get_available_appointments":
        summary = f"{len(res.get('available_slots', []))} sloturi"
    elif tool == "estimate_processing_time":
        summary = res.get("estimated_time", "—")
    else:
        summary = "ok"

    return f"{icon} {tool} → {summary}", level


def switch_service():
    st.session_state.form_data = {}
    st.session_state.chat_history = []
    st.session_state.enrichments = {}
    st.session_state.appointment_data = None
    st.session_state.vault_autofill_done = False
    svc = SERVICES[st.session_state.current_service]
    st.session_state.chat_history.append((
        "assistant",
        f"Bună ziua! Sunt Agentul AI pentru **{svc['icon']} {svc['name']}**.\n\n"
        f"{svc['description']}\n\n"
        f"Timp estimat de procesare: **{svc['estimated_time']}**. "
        + (
            f"Am detectat **{len(st.session_state.vault)} câmpuri de date** în Seiful Personal. "
            f"Scrieți **'completează din seif'** și voi completa formularul automat!"
            if st.session_state.vault
            else "Vă rog să îmi furnizați datele dumneavoastră și voi completa cererea automat."
        )
    ))
    add_log(f"Serviciu → {svc['name']}", "info")


if not st.session_state.chat_history:
    switch_service()

current_config = SERVICES[st.session_state.current_service]


# ─── BARA LATERALĂ ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="padding: 8px 0 16px 0; border-bottom: 1px solid #F1F5F9; margin-bottom: 16px;">
        <div style="font-family:'Source Serif 4',Georgia,serif; font-size:1.3rem; color:#0F172A; letter-spacing:-0.02em;">🏛️ Funcționar Public</div>
        <div style="font-family:'Inter',sans-serif; font-size:0.72rem; color:#94A3B8; margin-top:2px; letter-spacing:0.5px;">PLATFORMĂ AGENTICĂ v3.0</div>
    </div>
    """, unsafe_allow_html=True)

    if st.session_state.get("agent_ready", True):
        st.markdown('<div class="status-pill"><span class="dot-green"></span>Toate sistemele funcționale</div>', unsafe_allow_html=True)
    else:
        st.error(f"⚠️ {st.session_state.get('agent_error', 'Eroare agent')}")

    # Statistici rapide vault în bara laterală
    vault_count = len(st.session_state.vault)
    docs_count = len(st.session_state.vault_docs)
    if vault_count > 0:
        st.markdown(f"""
        <div style="background: linear-gradient(135deg,#EFF6FF,#F5F3FF); border:1px solid #BFDBFE; border-radius:10px; padding:10px 14px; margin-bottom:12px;">
            <div style="font-family:'Inter',sans-serif; font-size:0.72rem; font-weight:700; color:#2563EB; text-transform:uppercase; letter-spacing:1px;">🗄️ Seif Personal</div>
            <div style="font-family:'Source Serif 4',Georgia,serif; font-size:1.1rem; color:#0F172A; margin-top:4px;">{vault_count} câmpuri · {docs_count} doc{"umente" if docs_count!=1 else "ument"}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<span class="sidebar-label">Selectați Procedura</span>', unsafe_allow_html=True)
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

    st.markdown('<span class="sidebar-label">📅 Programări</span>', unsafe_allow_html=True)
    if st.button("Verifică Locuri Disponibile", use_container_width=True, key="appt_btn"):
        with st.spinner("Se obțin datele prin MCP…"):
            add_log("AppointmentTool trimis", "info")
            result = AppointmentTool().run(st.session_state.current_service)
            st.session_state.appointment_data = result
            add_log(f"S-au obținut {len(result.get('available_slots', []))} locuri", "ok")
            st.rerun()

    if st.session_state.appointment_data:
        for s in st.session_state.appointment_data.get("available_slots", [])[:3]:
            st.markdown(f"""
            <div style="background:#EFF6FF;border:1px solid #BFDBFE;border-radius:8px;padding:8px 10px;margin-bottom:6px;">
                <div style="font-family:'Inter',sans-serif;font-size:0.8rem;font-weight:600;color:#1D4ED8;">📅 {s['date']}</div>
                <div style="font-family:'Inter',sans-serif;font-size:0.76rem;color:#3B82F6;">⏰ {s['time']} — {s['office']}</div>
            </div>
            """, unsafe_allow_html=True)


# ─── PRINCIPAL ───────────────────────────────────────────────────────────────
st.markdown(ui.app_header(), unsafe_allow_html=True)

svc_icon = current_config.get("icon", "📋")
st.markdown(ui.service_title(svc_icon, current_config["name"]), unsafe_allow_html=True)

# ─── Tab-uri ─────────────────────────────────────────────────────────────────
tab_chat, tab_vault, tab_case, tab_docs, tab_agents = st.tabs([
    "💬 Conversație",
    "🗄️ Seif Personal",
    "📋 Dosar în Timp Real",
    "📂 Lista Documente",
    "🤖 Activitate Agenți",
])


# ══════════════════════════════════════════════════════════════
# TAB 1 — CONVERSAȚIE
# ══════════════════════════════════════════════════════════════
with tab_chat:
    req_fields = current_config["required_fields"]
    filled = sum(1 for k in req_fields if st.session_state.form_data.get(k))
    total = len(req_fields)
    pct = filled / total if total else 0

    # Banner auto-completare dacă vault-ul are date relevante
    vault = st.session_state.vault
    if vault and not st.session_state.vault_autofill_done:
        autofill_result = st.session_state.vault_agent.auto_fill_form(vault, req_fields) if st.session_state.get("vault_agent_ready") else {"filled": {}, "missing": req_fields}
        prefillable = len(autofill_result.get("filled", {}))
        if prefillable > 0:
            st.markdown(f"""
            <div class="autofill-banner">
                <span style="font-size:1.8rem;">🗄️</span>
                <div style="flex:1;">
                    <div style="font-family:'Inter',sans-serif;font-size:0.9rem;font-weight:600;color:#1E40AF;">Seiful Personal este Pregătit</div>
                    <div style="font-family:'Inter',sans-serif;font-size:0.8rem;color:#3B82F6;margin-top:2px;">
                        {prefillable} din {total} câmpuri pot fi completate automat din documentele încărcate.
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            col_fill, col_skip = st.columns([2, 3])
            with col_fill:
                if st.button(f"⚡ Auto-completează {prefillable} Câmpuri din Seif", type="primary", use_container_width=True, key="vault_autofill_btn"):
                    filled_data = autofill_result["filled"]
                    st.session_state.form_data.update(filled_data)
                    st.session_state.vault_autofill_done = True
                    filled_labels = [req_fields[k] for k in filled_data if k in req_fields]
                    missing_labels = [v for k, v in autofill_result.get("missing", {}).items()]
                    msg = f"✅ **Am completat automat {len(filled_data)} câmpuri** din Seiful Personal:\n"
                    for label in filled_labels:
                        msg += f"\n• {label}"
                    if missing_labels:
                        msg += f"\n\nMai am nevoie de câteva detalii de la dumneavoastră:\n"
                        for label in missing_labels[:3]:
                            msg += f"\n• **{label}**"
                    st.session_state.chat_history.append(("assistant", msg))
                    add_log(f"Seif auto-completat: {len(filled_data)} câmpuri", "ok")
                    st.rerun()

    # Progres
    c1, c2, c3 = st.columns([1, 4, 2])
    with c1:
        st.metric("Câmpuri", f"{filled} / {total}")
    with c2:
        st.markdown("<div style='margin-top:28px;'>", unsafe_allow_html=True)
        st.progress(pct)
        st.markdown("</div>", unsafe_allow_html=True)
    with c3:
        if filled == total:
            st.markdown("""<div style='background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;padding:10px 14px;margin-top:8px;'>
                <span style='font-family:Inter,sans-serif;font-size:0.82rem;font-weight:600;color:#16A34A;'>🎉 Pregătit pentru generare PDF</span>
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div style='background:#FFF7ED;border:1px solid #FED7AA;border-radius:10px;padding:10px 14px;margin-top:8px;'>
                <span style='font-family:Inter,sans-serif;font-size:0.82rem;font-weight:600;color:#EA580C;'>{total - filled} câmp(uri) rămase</span>
            </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)

    chat_container = st.container(height=420)
    with chat_container:
        for role, text in st.session_state.chat_history:
            avatar = "🏛️" if role == "assistant" else "👤"
            st.chat_message(role, avatar=avatar).markdown(text)

    if user_input := st.chat_input("Scrieți datele dumneavoastră, sau 'completează din seif' pentru auto-completare…"):
        # Interceptare intent "completează din seif"
        vault_trigger = any(phrase in user_input.lower() for phrase in [
            "completează din seif", "completez din seif", "folosește seiful",
            "auto completare", "autocompletare", "completare automata",
            "completare automată", "folosește documentele",
            "fill from vault", "use my vault", "auto fill", "autofill",
            "completează formularul", "completeaza formularul",
        ])

        st.session_state.chat_history.append(("user", user_input))
        add_log(f"Input utilizator ({len(user_input)} caractere)", "info")

        if vault_trigger and vault and st.session_state.get("vault_agent_ready"):
            autofill_result = st.session_state.vault_agent.auto_fill_form(vault, req_fields)
            filled_data = autofill_result["filled"]
            missing_data = autofill_result["missing"]

            if filled_data:
                st.session_state.form_data.update(filled_data)
                st.session_state.vault_autofill_done = True
                filled_labels = [req_fields[k] for k in filled_data if k in req_fields]
                msg = f"🗄️ **Auto-completare din Seif finalizată!** Am pre-completat **{len(filled_data)} câmpuri** din documentele încărcate:\n"
                for label in filled_labels:
                    msg += f"\n✅ {label}"
                if missing_data:
                    msg += f"\n\nUrmătoarele **{len(missing_data)} câmp(uri)** nu au fost găsite în seif — le puteți furniza?\n"
                    for label in list(missing_data.values())[:4]:
                        msg += f"\n• **{label}**"
                else:
                    msg += "\n\n🎉 Toate câmpurile sunt completate! Apăsați **Generează PDF** în tab-ul Dosar."
                add_log(f"Auto-completare seif: {len(filled_data)} completate, {len(missing_data)} lipsă", "ok")
            else:
                msg = "🗄️ Am verificat seiful dar nu am găsit date potrivite pentru acest formular. Vă rog completați manual."
                add_log("Auto-completare seif: niciun câmp potrivit", "warn")

            st.session_state.chat_history.append(("assistant", msg))
            st.rerun()

        else:
            # Flux normal agent
            with st.spinner("🤖 Orchestrare agenți…"):
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
                add_log(f"Extras: {list(valid.keys())}", "ok")

            enrichments = response.get("enrichments", {})
            st.session_state.enrichments = enrichments

            # Jurnalizează fiecare instrument MCP invocat de orchestrator, cu
            # sursa deciziei (🧠 model / 🛡️ safety-sweep / ⚙️ fallback determinist).
            for call in enrichments.get("tool_trace", []):
                msg, level = format_tool_log(call)
                add_log(msg, level)

            st.session_state.chat_history.append(("assistant", response.get("message", "Puteți clarifica?")))
            st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 2 — SEIF PERSONAL
# ══════════════════════════════════════════════════════════════
with tab_vault:
    vault = st.session_state.vault
    st.markdown("""
    <div style="margin-bottom:1.5rem;">
        <div style="font-family:'Source Serif 4',Georgia,serif;font-size:1.6rem;color:#0F172A;font-weight:400;letter-spacing:-0.02em;">
            🗄️ Seif Personal de Documente
        </div>
        <div style="font-family:'Inter',sans-serif;font-size:0.82rem;color:#64748B;margin-top:4px;">
            Indicați AI-ului folderul local cu <strong>Documente</strong>. Acesta parcurge fiecare subfolder,
            citește fiecare fișier, identifică tipul documentului și extrage datele —
            gata pentru auto-completarea oricărui formular guvernamental.
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Statistici ────────────────────────────────────────────────────────────
    s1, s2, s3, s4 = st.columns(4)
    # Aceeași sursă de adevăr ca tab-ul Conversație: auto_fill_form aplică
    # logica inteligentă de compoziție/sinonime (ex. FullName din FirstName +
    # LastName), nu doar potrivirea literală a cheilor (k in vault), care
    # subnumăra câmpurile completabile prin compoziție.
    if st.session_state.get("vault_agent_ready"):
        fillable = len(
            st.session_state.vault_agent.auto_fill_form(
                vault, current_config["required_fields"]
            )["filled"]
        )
    else:
        fillable = sum(1 for k in current_config["required_fields"] if k in vault)
    total_needed = len(current_config["required_fields"])
    with s1:
        st.markdown(ui.vault_stat(len(st.session_state.vault_docs), "Fișiere Găsite"), unsafe_allow_html=True)
    with s2:
        st.markdown(ui.vault_stat(len(vault), "Câmpuri Date"), unsafe_allow_html=True)
    with s3:
        color = "#16A34A" if fillable == total_needed and total_needed > 0 else "#2563EB"
        st.markdown(ui.vault_stat(f"{fillable}/{total_needed}", "Formular Curent", color=color), unsafe_allow_html=True)
    with s4:
        doc_types = list({d.get("type","general") for d in st.session_state.vault_docs})
        st.markdown(ui.vault_stat(len(doc_types), "Tipuri Documente"), unsafe_allow_html=True)

    st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════════
    # LAYOUT PRINCIPAL: scanner stânga, rezultate dreapta
    # ═══════════════════════════════════════════════════════════════
    col_scan, col_results = st.columns([5, 7], gap="large")

    with col_scan:

        # ── HERO: Scanner Folder ─────────────────────────────────────────────
        st.markdown("""
        <div style="background:linear-gradient(135deg,#EFF6FF,#F5F3FF);border:1.5px solid #BFDBFE;
                    border-radius:16px;padding:18px 20px;margin-bottom:16px;">
            <div style="font-family:'Inter',sans-serif;font-size:0.72rem;font-weight:700;
                        color:#1D4ED8;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;">
                📂 Scanner Folder
            </div>
            <div style="font-family:'Source Serif 4',Georgia,serif;font-size:1.05rem;color:#0F172A;margin-bottom:6px;">
                Indicați folderul cu Documente
            </div>
            <div style="font-family:'Inter',sans-serif;font-size:0.78rem;color:#64748B;line-height:1.5;">
                AI-ul parcurge recursiv fiecare subfolder, citește fiecare imagine și PDF,
                identifică tipul documentului și extrage toate datele personale.
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Input cale
        folder_path = st.text_input(
            "Calea folderului",
            placeholder="ex.  ~/Documents/Acte   sau   C:/Users/Ion/Documente",
            label_visibility="collapsed",
            key="vault_folder_path",
        )

        # Previzualizare folder dacă este valid
        if folder_path:
            _root = Path(folder_path).expanduser()
            if _root.exists() and _root.is_dir():
                try:
                    _files = st.session_state.vault_agent.walk_folder(folder_path) if st.session_state.get("vault_agent_ready") else []
                    _subdirs = sorted({f["rel"].split("/")[0] for f in _files if "/" in f["rel"]})
                    st.markdown(f"""
                    <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:10px;
                                padding:12px 16px;margin:8px 0;">
                        <div style="font-family:'Inter',sans-serif;font-size:0.8rem;font-weight:600;color:#15803D;">
                            ✅ S-au găsit {len(_files)} fișier{"e" if len(_files)!=1 else ""} de scanat
                        </div>
                        <div style="font-family:'Inter',sans-serif;font-size:0.74rem;color:#64748B;margin-top:4px;">
                            {"Subfoldere: " + ", ".join(_subdirs[:5]) + ("…" if len(_subdirs)>5 else "") if _subdirs else "Doar folderul rădăcină"}
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                except Exception:
                    pass

                already_scanned = db.is_folder_scanned(folder_path)

                if already_scanned:
                    st.info("Acest folder a fost deja scanat.", icon="ℹ️")
                    if st.button("🔄 Re-scanează folderul", use_container_width=True, key="rescan_btn"):
                        db.delete_vault_documents_by_folder(folder_path)
                        db.clear_vault()
                        st.session_state.vault_docs = db.get_vault_documents()
                        st.session_state.vault = db.get_vault_fields()
                        st.session_state.vault_autofill_done = False
                        st.rerun()
                else:
                    if st.button("🧠 Scanează Folderul", type="primary", use_container_width=True, key="scan_folder_btn"):
                        if not st.session_state.get("vault_agent_ready"):
                            st.error("VaultAgent neinițializat. Verificați OPENAI_API_KEY.")
                        else:
                            agent: VaultAgent = st.session_state.vault_agent
                            add_log(f"ScanareFolder: {folder_path}", "info")

                            progress_bar = st.progress(0.0)
                            status_md = st.empty()
                            live_feed = st.empty()
                            feed_items = []

                            def folder_progress(current, total, msg, file_result):
                                pct = current / total if total else 0
                                progress_bar.progress(min(pct, 1.0))
                                status_md.markdown(
                                    f'''<div style="font-family:Inter,sans-serif;font-size:0.8rem;
                                    color:#2563EB;padding:4px 0;">⏳ {msg}</div>''',
                                    unsafe_allow_html=True,
                                )
                                if file_result and file_result.get("fields"):
                                    feed_items.append(file_result)
                                    rows = ""
                                    for fr in feed_items[-5:]:
                                        icon = fr.get("icon", "📄")
                                        doc_type = fr.get("type", "general").replace("_", " ").title()
                                        n_fields = len(fr.get("fields", {}))
                                        field_keys = list(fr.get("fields", {}).keys())[:4]
                                        chips = " ".join([
                                            f'''<span style="background:#F0FDF4;border:1px solid #BBF7D0;
                                            color:#15803D;font-size:0.68rem;font-weight:600;
                                            padding:1px 6px;border-radius:100px;">{k}</span>'''
                                            for k in field_keys
                                        ])
                                        rows += f'''
                                        <div style="display:flex;gap:10px;padding:6px 0;
                                                    border-bottom:1px solid #F1F5F9;align-items:flex-start;">
                                            <span style="font-size:1.1rem;flex-shrink:0;">{icon}</span>
                                            <div style="min-width:0;">
                                                <div style="font-family:Inter,sans-serif;font-size:0.75rem;
                                                            font-weight:600;color:#0F172A;
                                                            white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                                                    {fr["rel"]}
                                                </div>
                                                <div style="font-family:Inter,sans-serif;font-size:0.7rem;
                                                            color:#2563EB;margin:1px 0 4px 0;">
                                                    {doc_type} · {n_fields} câmpuri
                                                </div>
                                                <div>{chips}</div>
                                            </div>
                                        </div>'''
                                    live_feed.markdown(
                                        f'''<div style="background:#FAFBFC;border:1px solid #E2E8F0;
                                        border-radius:10px;padding:10px 14px;">{rows}</div>''',
                                        unsafe_allow_html=True,
                                    )

                            result = agent.scan_folder(folder_path, progress_callback=folder_progress)

                            progress_bar.empty()
                            status_md.empty()
                            live_feed.empty()

                            if result.get("error"):
                                st.error(f"Scanare eșuată: {result['error']}")
                                add_log(f"ScanareFolder eșuată: {result['error']}", "err")
                            else:
                                # Salvează în SQLite și actualizează sesiunea
                                for k, v in result["vault"].items():
                                    if k not in st.session_state.vault:
                                        st.session_state.vault[k] = v
                                db.save_vault_fields(st.session_state.vault)

                                for fr in result["files"]:
                                    if not fr["skipped"] and fr.get("fields"):
                                        doc_entry = {
                                            "name": fr["name"],
                                            "rel":  fr["rel"],
                                            "type": fr.get("type", "general"),
                                            "icon": fr.get("icon", "📄"),
                                            "fields": fr["fields"],
                                            "count": len(fr["fields"]),
                                            "source": "folder",
                                            "folder": folder_path,
                                        }
                                        db.save_vault_document(doc_entry)

                                st.session_state.vault_docs = db.get_vault_documents()
                                st.session_state.vault_autofill_done = False
                                useful = len([f for f in result["files"] if f.get("fields")])
                                add_log(
                                    f"ScanareFolder gata: {useful}/{result['total_files']} fișiere, "
                                    f"{len(st.session_state.vault)} câmpuri", "ok"
                                )
                                st.success(
                                    f"✅ S-au scanat **{result['total_files']} fișiere** din "
                                    f"**{result['total_pages']} pagini** — "
                                    f"**{len(st.session_state.vault)} câmpuri** în seif."
                                )
                                time.sleep(0.5)
                                st.rerun()

            elif folder_path.strip():
                st.markdown("""
                <div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:10px;padding:10px 14px;">
                    <span style="font-family:Inter,sans-serif;font-size:0.8rem;color:#C2410C;">
                        ⚠️ Calea nu a fost găsită sau nu este un director. Verificați și încercați din nou.
                    </span>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:20px'></div>", unsafe_allow_html=True)

        # ── Secundar: Încărcare fișiere individuale ──────────────────────────
        with st.expander("📎 Sau încărcați fișiere individuale", expanded=False):
            st.caption("JPG, PNG sau PDF — documente individuale")
            single_files = st.file_uploader(
                "Documente individuale",
                type=["jpg", "jpeg", "png", "pdf"],
                accept_multiple_files=True,
                label_visibility="collapsed",
                key="vault_uploader",
            )
            if single_files:
                already = {d["name"] for d in st.session_state.vault_docs}
                new_files = [f for f in single_files if f.name not in already]
                if new_files:
                    if st.button(f"Extrage din {len(new_files)} fișier(e)", use_container_width=True, key="single_btn"):
                        if st.session_state.get("vault_agent_ready"):
                            agent: VaultAgent = st.session_state.vault_agent
                            pb = st.progress(0)
                            st_s = st.empty()
                            for i, f in enumerate(new_files):
                                st_s.markdown(f"🔍 **{f.name}**…")
                                add_log(f"Individual: {f.name}", "info")
                                dt = agent.detect_document_type(f)
                                extracted = agent.extract_from_file(f, dt)
                                if "_error" not in extracted and extracted:
                                    st.session_state.vault.update(extracted)
                                    doc_entry = {
                                        "name": f.name, "rel": f.name,
                                        "type": dt,
                                        "icon": TYPE_ICONS.get(dt, "📄"),
                                        "fields": extracted, "count": len(extracted),
                                        "source": "single",
                                    }
                                    st.session_state.vault_docs.append(doc_entry)
                                    db.save_vault_fields(extracted)
                                    db.save_vault_document(doc_entry)
                                    add_log(f"+{len(extracted)} câmpuri", "ok")
                                pb.progress((i + 1) / len(new_files))
                            pb.empty(); st_s.empty()
                            st.session_state.vault_autofill_done = False
                            st.rerun()
                else:
                    st.info("Toate fișierele au fost deja procesate.")

        # ── Ghid tipuri suportate ────────────────────────────────────────────
        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        st.markdown('''<div style="font-family:Inter,sans-serif;font-size:0.72rem;font-weight:700;
            color:#94A3B8;text-transform:uppercase;letter-spacing:1.5px;margin-bottom:8px;">
            Tipuri de Documente Recunoscute</div>''', unsafe_allow_html=True)
        for icon, name, hint in [
            ("🪪", "Carte de Identitate",      "CNP, nume, adresă, data nașterii"),
            ("📘", "Pașaport",                 "Număr pașaport, data expirării, CNP"),
            ("👶", "Certificat de Naștere",     "Date copil, părinți, locul nașterii"),
            ("🚗", "Document Vehicul",          "VIN, marcă, model, an, proprietar"),
            ("🏠", "Factură Utilități",         "Nume complet + dovada adresei"),
            ("💍", "Certificat Căsătorie",      "Ambii soți, data, orașul"),
        ]:
            st.markdown(f"""
            <div style="display:flex;gap:10px;padding:5px 0;border-bottom:1px solid #F8F9FC;align-items:center;">
                <span style="flex-shrink:0;font-size:0.95rem;">{icon}</span>
                <div>
                    <span style="font-family:Inter,sans-serif;font-size:0.78rem;font-weight:600;color:#334155;">{name}</span>
                    <span style="font-family:Inter,sans-serif;font-size:0.72rem;color:#94A3B8;margin-left:6px;">{hint}</span>
                </div>
            </div>""", unsafe_allow_html=True)

    # ── Coloana dreapta: Conținut Seif ───────────────────────────────────────
    with col_results:
        st.markdown('<div class="section-title">Conținut Seif</div>', unsafe_allow_html=True)

        if not st.session_state.vault_docs:
            st.markdown("""
            <div class="vault-empty-state">
                <div style="font-size:2.8rem;margin-bottom:14px;">🗂️</div>
                <div style="font-family:'Source Serif 4',Georgia,serif;font-size:1.25rem;color:#0F172A;">Seiful este gol</div>
                <div style="font-family:'Inter',sans-serif;font-size:0.8rem;color:#94A3B8;margin-top:8px;line-height:1.6;">
                    Introduceți calea către folderul cu Documente în stânga.<br>
                    AI-ul va scana automat fiecare fișier și subfolder.
                </div>
                <div style="margin-top:16px;font-family:'Courier New',monospace;font-size:0.78rem;
                            background:#F1F5F9;color:#475569;padding:8px 14px;border-radius:8px;
                            display:inline-block;">
                    ~/Documents/Acte Personale
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Grupare după sursă
            folder_sources = sorted({d.get("folder", "Încărcat") for d in st.session_state.vault_docs})

            for source in folder_sources:
                docs_in_source = [d for d in st.session_state.vault_docs if d.get("folder", "Încărcat") == source]
                source_label = source if source != "Încărcat" else "📎 Fișiere încărcate"
                st.markdown(f'''
                <div style="font-family:Inter,sans-serif;font-size:0.7rem;font-weight:700;
                            color:#94A3B8;text-transform:uppercase;letter-spacing:1.5px;
                            margin:12px 0 8px 0;">
                    📂 {source_label} · {len(docs_in_source)} fișier{"e" if len(docs_in_source)!=1 else ""}
                </div>''', unsafe_allow_html=True)

                for doc in docs_in_source:
                    st.markdown(ui.vault_doc_card(doc), unsafe_allow_html=True)

            # Tabel complet date vault
            with st.expander("🔍 Vizualizează toate datele extrase", expanded=False):
                rows_html = "".join([
                    f'<div style="display:flex;gap:12px;padding:8px 0;border-bottom:1px solid #F1F5F9;">'
                    f'<span style="font-family:\'Courier New\',monospace;font-size:0.74rem;color:#64748B;width:160px;flex-shrink:0;">{k}</span>'
                    f'<span style="font-family:\'Inter\',sans-serif;font-size:0.82rem;font-weight:500;color:#0F172A;">{v}</span>'
                    f'</div>'
                    for k, v in st.session_state.vault.items()
                ])
                st.markdown(f'<div style="background:#FAFBFC;border-radius:10px;padding:12px 16px;">{rows_html}</div>', unsafe_allow_html=True)

            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            if st.button("🗑️ Golește Seiful", key="clear_vault"):
                db.clear_vault()
                st.session_state.vault = {}
                st.session_state.vault_docs = []
                st.session_state.vault_autofill_done = False
                add_log("Seif golit", "warn")
                st.rerun()


# ══════════════════════════════════════════════════════════════
# TAB 3 — DOSAR ÎN TIMP REAL
# ══════════════════════════════════════════════════════════════
with tab_case:
    st.markdown('<div class="section-title">Date Colectate</div>', unsafe_allow_html=True)

    req_fields = current_config["required_fields"]
    has_any = False
    rows_html = ""
    for key, label in req_fields.items():
        val = st.session_state.form_data.get(key, "")
        if val:
            has_any = True
            source = "🗄️" if key in st.session_state.vault else "💬"
            val_html = f'<span class="field-filled">{source} {val}</span>'
        else:
            val_html = '<span class="field-empty">Se așteaptă introducerea…</span>'
        rows_html += f"""
        <div class="field-row">
            <span style="font-size:8px;color:{'#22C55E' if val else '#CBD5E1'}">{'●' if val else '○'}</span>
            <span class="field-label">{label}</span>
            {val_html}
        </div>"""

    st.markdown(f'<div style="background:#FFFFFF;border:1px solid #E2E8F0;border-radius:14px;padding:16px 20px;">{rows_html}</div>', unsafe_allow_html=True)
    st.caption("🗄️ = completat automat din seif · 💬 = colectat prin conversație")

    enrichments = st.session_state.enrichments
    if enrichments.get("cnp_validation", {}).get("valid"):
        data = enrichments["cnp_validation"].get("data", {})
        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        st.markdown('<div class="section-title">🔒 Verificare Registru</div>', unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        col1.metric("Nume", data.get("name", "—"))
        col2.metric("Status", data.get("status", "—"))
        col3.metric("Data Nașterii", data.get("dob", "—"))

    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    b1, b2 = st.columns(2)

    if b1.button("🔄 Resetează Dosarul", use_container_width=True):
        switch_service()
        add_log("Dosar resetat", "warn")
        st.rerun()

    if has_any:
        if b2.button("🖨️ Generează PDF", type="primary", use_container_width=True):
            with st.spinner("Se generează documentul oficial…"):
                add_log("Generare PDF începută", "info")
                success = st.session_state.pdf_handler.fill_form(
                    data=st.session_state.form_data,
                    service_config=current_config,
                    output_name="Application.pdf",
                )
            if success:
                add_log("PDF generat ✓", "ok")
                st.success("✅ Documentul a fost generat cu succes!")
                with open("Application.pdf", "rb") as f:
                    st.download_button(
                        "⬇️ Descarcă Cererea PDF",
                        f,
                        file_name=current_config["template_file"],
                        mime="application/pdf",
                        use_container_width=True,
                    )
            else:
                add_log("Generare PDF eșuată", "err")
                st.error("Generarea PDF a eșuat. Verificați jurnalul agenților.")


# ══════════════════════════════════════════════════════════════
# TAB 4 — LISTA DOCUMENTE NECESARE
# ══════════════════════════════════════════════════════════════
with tab_docs:
    st.markdown('<div class="section-title">Documente Fizice Necesare</div>', unsafe_allow_html=True)
    st.caption("Aduceți originalele și copiile când depuneți cererea la ghișeu.")

    doc_list = st.session_state.enrichments.get("documents")

    if not doc_list:
        if st.button("🔍 Obține Lista de Documente prin MCP", use_container_width=True):
            with st.spinner("Se contactează instrumentul DocumentChecker prin MCP…"):
                add_log("DocumentTool trimis", "info")
                result = DocumentTool().run(st.session_state.current_service)
                doc_list = result.get("required_documents", [])
                st.session_state.enrichments["documents"] = doc_list
                add_log(f"{len(doc_list)} documente necesare", "ok")
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
    st.markdown('<div class="section-title">⏱️ Timpuri de Procesare</div>', unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown(f"""
        <div style="background:#F0FDF4;border:1px solid #BBF7D0;border-radius:12px;padding:16px;">
            <div style="font-family:'Inter',sans-serif;font-size:0.72rem;font-weight:700;color:#16A34A;text-transform:uppercase;letter-spacing:1px;">Standard</div>
            <div style="font-family:'Source Serif 4',Georgia,serif;font-size:1.3rem;color:#0F172A;margin-top:4px;">{current_config['estimated_time']}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_b:
        if st.button("⚡ Estimare Urgentă prin MCP", use_container_width=True):
            with st.spinner("Se verifică procesarea urgentă…"):
                add_log("TimingTool trimis (urgent)", "info")
                result = TimingTool().run(st.session_state.current_service, urgent=True)
                st.markdown(f"""
                <div style="background:#FFF7ED;border:1px solid #FED7AA;border-radius:12px;padding:16px;">
                    <div style="font-family:'Inter',sans-serif;font-size:0.72rem;font-weight:700;color:#EA580C;text-transform:uppercase;letter-spacing:1px;">Urgent</div>
                    <div style="font-family:'Source Serif 4',Georgia,serif;font-size:1.3rem;color:#0F172A;margin-top:4px;">{result.get('estimated_time','—')}</div>
                    <div style="font-size:0.75rem;color:#94A3B8;margin-top:6px;">{result.get('fee_note','')}</div>
                </div>
                """, unsafe_allow_html=True)
                add_log(f"Urgent: {result.get('estimated_time')}", "ok")


# ══════════════════════════════════════════════════════════════
# TAB 5 — ACTIVITATE AGENȚI
# ══════════════════════════════════════════════════════════════
with tab_agents:
    agents_data = [
        ("🧠", "UniversalAgent", "Motor de Raționament", "GPT-4o · Extragere JSON", "Extrage entități din limbaj natural, conduce fluxul conversației", False),
        ("🗄️", "VaultAgent", "Seif Documente", "GPT-4o Vision · Extragere OCR", "Citește documentele personale, extrage date structurate, alimentează auto-completarea", True),
        ("🔍", "ValidationTool", "Validator CNP", "MCP → verify_cnp", "Validează CNP românesc cu sumă de control mod-11 + căutare în registru", False),
        ("🚗", "VehicleTool", "Verificator VIN", "MCP → check_vehicle_status", "Verifică VIN-uri; semnalează vehiculele furate sau neînregistrate", False),
        ("📅", "AppointmentTool", "Programator", "MCP → get_available_appointments", "Obține programări disponibile la ghișeu în timp real", False),
        ("📋", "DocumentTool", "Verificator Documente", "MCP → check_required_documents", "Returnează lista oficială de documente per serviciu", False),
        ("⏱️", "TimingTool", "Estimator Timp", "MCP → estimate_processing_time", "Estimări timp procesare standard și urgentă", False),
    ]

    st.markdown(ui.agent_cards(agents_data), unsafe_allow_html=True)

    # Jurnal
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)

    st.markdown(ui.agent_log_console(st.session_state.agent_log), unsafe_allow_html=True)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
    if st.button("🗑️ Golește Jurnalul", key="clear_log"):
        st.session_state.agent_log = []
        st.rerun()
