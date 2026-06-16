# src/ui.py — Funcții de prezentare pentru interfața Streamlit.
#
# Fiecare funcție întoarce un șir HTML identic cu markup-ul folosit anterior
# inline în app.py. Nu există logică de aplicație aici, doar randare — scopul
# este să păstreze app.py concentrat pe fluxul Streamlit, nu pe HTML brut.

from pathlib import Path

_CSS_PATH = Path(__file__).resolve().parent.parent / "assets" / "styles.css"


def load_css() -> str:
    """Întoarce foaia de stil din assets/styles.css împachetată într-un tag <style>."""
    return f"<style>{_CSS_PATH.read_text(encoding='utf-8')}</style>"


def app_header() -> str:
    """Antetul principal al aplicației (titlu + badge versiune + subtitlu)."""
    return """
<div class="app-header">
    <div style="display:flex; align-items:center; gap:0; flex-wrap:wrap;">
        <span class="app-title-icon">🏛️</span>
        <span class="app-title">Agent Funcționar Public</span>
        <span class="badge-v2">v3.0 — Ediția Seif</span>
    </div>
    <div class="app-sub">Alimentat de GPT-4o &nbsp;·&nbsp; Seif Personal de Documente &nbsp;·&nbsp; Orchestrare Agentică &nbsp;·&nbsp; 5 Instrumente MCP</div>
</div>
"""


def service_title(icon: str, name: str) -> str:
    """Rândul cu iconița și numele serviciului activ."""
    return f"""
<div style="display:flex;align-items:center;gap:10px;margin-bottom:1.25rem;">
    <span style="font-size:1.5rem;">{icon}</span>
    <span style="font-family:'Source Serif 4',Georgia,serif;font-size:1.5rem;color:#0F172A;font-weight:400;letter-spacing:-0.02em;">{name}</span>
</div>
"""


def vault_stat(num, label: str, color: str | None = None) -> str:
    """Un card de statistică din tab-ul Seif (număr mare + etichetă)."""
    style = f' style="color:{color};"' if color else ""
    return f'''<div class="vault-stat"><div class="vault-stat-num"{style}>{num}</div><div class="vault-stat-label">{label}</div></div>'''


def vault_doc_card(doc: dict) -> str:
    """Cardul unui document din seif, cu primele câmpuri afișate drept chips."""
    icon = doc.get("icon", "📄")
    chips_html = "".join([
        f'''<span class="vault-field-chip">
            <span class="vault-field-chip-key">{k}:</span>
            {str(v)[:16]}{"…" if len(str(v))>16 else ""}
        </span>'''
        for k, v in list(doc["fields"].items())[:6]
    ])
    return f'''
    <div class="vault-doc-card">
        <div style="font-size:1.5rem;flex-shrink:0;padding-top:2px;">{icon}</div>
        <div style="flex:1;min-width:0;">
            <div style="font-family:Inter,sans-serif;font-size:0.83rem;
                        font-weight:600;color:#0F172A;
                        white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
                {doc.get("rel", doc["name"])}
            </div>
            <div style="font-family:Inter,sans-serif;font-size:0.71rem;
                        color:#2563EB;font-weight:500;margin:2px 0 6px 0;">
                {doc.get("type","general").replace("_"," ").title()} · {doc["count"]} câmpuri
            </div>
            <div>{chips_html}</div>
        </div>
    </div>
    '''


def agent_cards(agents_data: list) -> str:
    """Grila de carduri din tab-ul Activitate Agenți (Monitor Orchestrare)."""
    cards_html = ""
    for icon, name, role, tool, desc, is_new in agents_data:
        bg = "background:linear-gradient(135deg,#EFF6FF,#FAFBFF);border-color:#BFDBFE;" if is_new else "background:#FFFFFF;border-color:#E2E8F0;"
        badge = '<span style="background:#DBEAFE;color:#1D4ED8;font-size:0.65rem;font-weight:700;padding:2px 7px;border-radius:100px;letter-spacing:0.5px;">NOU</span>' if is_new else ""
        cards_html += f'''<div style="{bg}border:1px solid;border-radius:14px;padding:16px;transition:box-shadow 0.2s;">
<div style="display:flex;justify-content:space-between;align-items:flex-start;">
<div style="font-size:1.4rem;margin-bottom:6px;">{icon}</div>{badge}
</div>
<div style="font-family:Inter,sans-serif;font-size:0.92rem;font-weight:600;color:#0F172A;">{name}</div>
<div style="font-size:0.75rem;color:#2563EB;font-weight:500;margin:3px 0;">{role}</div>
<div style="font-family:Courier New,monospace;font-size:0.72rem;background:#F1F5F9;color:#475569;padding:2px 7px;border-radius:4px;display:inline-block;margin:4px 0;">{tool}</div>
<div style="font-size:0.76rem;color:#94A3B8;margin-top:4px;">{desc}</div>
</div>'''

    return f'''<div style="font-family:'Source Serif 4',Georgia,serif;font-size:1.25rem;color:#0F172A;font-weight:400;letter-spacing:-0.02em;margin-bottom:1rem;">Monitor Orchestrare Agentică</div>
<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;">{cards_html}</div>'''


def agent_log_console(agent_log: list) -> str:
    """Consola de jurnal a agenților (ultimele 25 de intrări, cele mai noi sus)."""
    title = ('<div style="font-family:\'Source Serif 4\',Georgia,serif;font-size:1.25rem;'
             'color:#0F172A;font-weight:400;letter-spacing:-0.02em;margin-bottom:1rem;">'
             '🖥️ Jurnal Agenți în Timp Real</div>')
    if agent_log:
        log_lines = ""
        color_map = {"ok": "#4ADE80", "info": "#60A5FA", "warn": "#FCD34D", "err": "#F87171"}
        for entry in reversed(agent_log[-25:]):
            c = color_map.get(entry["level"], "#60A5FA")
            log_lines += f'<span style="color:{c};display:block;margin:2px 0;">[{entry["ts"]}]  {entry["msg"]}</span>'
        body = log_lines
    else:
        body = '<span style="color:#60A5FA;display:block;margin:2px 0;">[sistem]  Se așteaptă activitate agenți…</span>'
    return (f'{title}\n'
            f'<div style="background:#0F172A;border-radius:12px;padding:14px 16px;'
            f'font-family:Courier New,monospace;font-size:0.73rem;max-height:180px;'
            f'overflow-y:auto;border:1px solid #1E293B;">{body}</div>')
