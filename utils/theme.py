"""utils/theme.py — Color tokens and CSS injection."""

import streamlit as st

# ── Color palettes ──────────────────────────────────────
DARK = {
    "BG":     "#13151e",
    "CARD":   "#1c1f2e",
    "CARD2":  "#232638",
    "BORDER": "#2d3149",
    "TEXT":   "#e2e8f8",
    "SUB":    "#7b83a6",
    "GREEN":  "#4ade80",
    "YELLOW": "#fbbf24",
    "RED":    "#f87171",
    "BLUE":   "#60a5fa",
    "PURPLE": "#a78bfa",
    "ACCENT": "#4361ee",
    "ACCENT2":"#3a56e8",
}

LIGHT = {
    "BG":     "#f1f4fc",
    "CARD":   "#ffffff",
    "CARD2":  "#f8f9fe",
    "BORDER": "#dde2f0",
    "TEXT":   "#1a1d2e",
    "SUB":    "#6470a0",
    "GREEN":  "#16a34a",
    "YELLOW": "#d97706",
    "RED":    "#dc2626",
    "BLUE":   "#2563eb",
    "PURPLE": "#7c3aed",
    "ACCENT": "#4361ee",
    "ACCENT2":"#3a56e8",
}

def get_colors():
    dark = st.session_state.get("dark_mode", False)
    return DARK if dark else LIGHT

def inject_css():
    C = get_colors()
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

/* ── Base ── */
.stApp {{ background: {C['BG']}; }}
.block-container {{ padding: 1.5rem 2rem 4rem; max-width: 100% !important; }}
html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; color: {C['TEXT']}; }}

/* ── Typography ── */
h1 {{ font-weight: 800; font-size: 1.75rem; letter-spacing: -0.03em; color: {C['TEXT']}; margin-bottom: 0.2rem; }}
h2, h3 {{ font-weight: 700; letter-spacing: -0.02em; color: {C['TEXT']}; }}
h4 {{ font-weight: 600; color: {C['TEXT']}; }}

/* ── Sidebar ── */
[data-testid="stSidebar"] {{
    background: {C['CARD']} !important;
    border-right: 1px solid {C['BORDER']};
}}
[data-testid="stSidebarNav"] a {{
    border-radius: 8px; padding: 6px 12px; margin: 2px 0;
    font-weight: 500; color: {C['SUB']};
    transition: all 0.15s;
}}
[data-testid="stSidebarNav"] a:hover {{
    background: {C['CARD2']}; color: {C['TEXT']};
}}
[data-testid="stSidebarNav"] a[aria-selected="true"] {{
    background: {C['ACCENT']}22; color: {C['ACCENT']};
    font-weight: 600;
}}

/* ── Metrics ── */
div[data-testid="metric-container"] {{
    background: {C['CARD']}; border: 1px solid {C['BORDER']};
    border-radius: 12px; padding: 1rem 1.2rem;
    transition: transform 0.15s, box-shadow 0.15s;
}}
div[data-testid="metric-container"]:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 16px rgba(67,97,238,0.12);
}}
div[data-testid="metric-container"] label {{
    color: {C['SUB']} !important; font-size: 0.78rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.06em;
}}
div[data-testid="metric-container"] [data-testid="metric-value"] {{
    font-weight: 700; font-size: 1.6rem; letter-spacing: -0.02em;
}}

/* ── DataFrames ── */
.stDataFrame {{
    border: 1px solid {C['BORDER']}; border-radius: 12px;
    overflow: hidden;
}}
.stDataFrame th {{
    background: {C['CARD2']} !important;
    color: {C['SUB']} !important;
    font-size: 0.72rem !important; font-weight: 600 !important;
    text-transform: uppercase; letter-spacing: 0.06em;
    padding: 10px 12px !important;
}}
.stDataFrame td {{
    font-size: 0.82rem !important; padding: 8px 12px !important;
    border-bottom: 1px solid {C['BORDER']}44;
}}

/* ── Buttons ── */
.stButton > button {{
    background: {C['ACCENT']}; color: white; border: none;
    border-radius: 8px; font-weight: 600; font-size: 0.875rem;
    padding: 0.5rem 1.25rem;
    transition: all 0.15s;
    box-shadow: 0 2px 8px {C['ACCENT']}40;
}}
.stButton > button:hover {{
    background: {C['ACCENT2']}; transform: translateY(-1px);
    box-shadow: 0 4px 14px {C['ACCENT']}50;
}}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input,
.stSelectbox > div > div,
.stMultiSelect > div > div {{
    background: {C['CARD']} !important; color: {C['TEXT']} !important;
    border: 1px solid {C['BORDER']} !important; border-radius: 8px !important;
    font-size: 0.875rem !important;
}}
.stTextInput > div > div > input:focus {{
    border-color: {C['ACCENT']} !important;
    box-shadow: 0 0 0 3px {C['ACCENT']}20 !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    background: {C['CARD']}; border-radius: 12px;
    padding: 5px; border: 1px solid {C['BORDER']}; gap: 3px;
}}
.stTabs [data-baseweb="tab"] {{
    background: transparent; color: {C['SUB']};
    border-radius: 9px; font-weight: 600; font-size: 0.875rem;
    padding: 8px 20px; transition: all 0.15s;
}}
.stTabs [aria-selected="true"] {{
    background: {C['ACCENT']}; color: white;
    box-shadow: 0 2px 10px {C['ACCENT']}40;
}}

/* ── Expander ── */
details summary {{
    background: {C['CARD']}; border: 1px solid {C['BORDER']};
    border-radius: 8px; padding: 10px 16px;
    font-weight: 600; cursor: pointer;
}}

/* ── Cards ── */
.wcard {{
    background: {C['CARD']}; border: 1px solid {C['BORDER']};
    border-radius: 12px; padding: 16px 20px; margin: 6px 0;
    transition: box-shadow 0.15s;
}}
.wcard:hover {{ box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
.wcard-premium {{
    background: linear-gradient(135deg, {C['GREEN']}0d, {C['CARD']});
    border: 1px solid {C['GREEN']}44; border-left: 3px solid {C['GREEN']};
    border-radius: 12px; padding: 14px 18px; margin: 5px 0;
    font-family: 'JetBrains Mono', monospace; font-size: 0.82rem;
}}
.wcard-early {{
    background: linear-gradient(135deg, {C['YELLOW']}0d, {C['CARD']});
    border: 1px solid {C['YELLOW']}44; border-left: 3px solid {C['YELLOW']};
    border-radius: 12px; padding: 14px 18px; margin: 5px 0;
    font-family: 'JetBrains Mono', monospace; font-size: 0.82rem;
}}
.wcard-warn {{
    background: linear-gradient(135deg, {C['RED']}0d, {C['CARD']});
    border: 1px solid {C['RED']}44; border-left: 3px solid {C['RED']};
    border-radius: 12px; padding: 14px 18px; margin: 5px 0;
}}
.wcard-info {{
    background: linear-gradient(135deg, {C['BLUE']}0d, {C['CARD']});
    border: 1px solid {C['BLUE']}33;
    border-radius: 12px; padding: 14px 18px; margin: 5px 0;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 5px; height: 5px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: {C['BORDER']}; border-radius: 3px; }}

/* ── Misc ── */
hr {{ border: none; border-top: 1px solid {C['BORDER']}; margin: 1.5rem 0; opacity: 0.6; }}
.subtext {{ color: {C['SUB']}; font-size: 0.82rem; }}
.mono {{ font-family: 'JetBrains Mono', monospace; }}
.pill {{
    display: inline-block; padding: 2px 10px; border-radius: 20px;
    font-size: 0.72rem; font-weight: 700; letter-spacing: 0.04em;
}}
.pill-green  {{ background: {C['GREEN']}22;  color: {C['GREEN']};  }}
.pill-yellow {{ background: {C['YELLOW']}22; color: {C['YELLOW']}; }}
.pill-red    {{ background: {C['RED']}22;    color: {C['RED']};    }}
.pill-blue   {{ background: {C['BLUE']}22;   color: {C['BLUE']};   }}
.pill-purple {{ background: {C['PURPLE']}22; color: {C['PURPLE']}; }}

/* ── Stage badges ── */
.stage-2 {{ color: {C['GREEN']};  font-weight: 700; }}
.stage-3 {{ color: {C['YELLOW']}; font-weight: 700; }}
.stage-4 {{ color: {C['RED']};    font-weight: 700; }}
.stage-1 {{ color: {C['BLUE']};   font-weight: 700; }}
</style>
""", unsafe_allow_html=True)

def page_config(title="Weinstein Screener"):
    st.set_page_config(
        page_title=title,
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

def header(title: str, subtitle: str = ""):
    C = get_colors()
    st.markdown(f"# {title}")
    if subtitle:
        st.markdown(f"<p class='subtext'>{subtitle}</p>", unsafe_allow_html=True)

def metric_row(items: list):
    """items = list of (label, value, delta?) tuples"""
    cols = st.columns(len(items))
    for col, item in zip(cols, items):
        if len(item) == 3:
            col.metric(item[0], item[1], item[2])
        else:
            col.metric(item[0], item[1])

def signal_pill(r: dict) -> str:
    if r.get("premium"):   return '<span class="pill pill-green">PREMIUM</span>'
    if r.get("early_sig"): return '<span class="pill pill-yellow">EARLY</span>'
    if r.get("score",0) >= 4: return '<span class="pill pill-blue">S2</span>'
    return ""

def stage_pill(stage: str) -> str:
    if not stage: return ""
    if "Stage 2" in stage: return '<span class="pill pill-green">● S2</span>'
    if "Stage 3" in stage: return '<span class="pill pill-yellow">● S3</span>'
    if "Stage 4" in stage: return '<span class="pill pill-red">● S4</span>'
    return '<span class="pill pill-blue">● S1</span>'

def rs_color(score) -> str:
    C = get_colors()
    if score is None: return C["SUB"]
    try: score = float(score)
    except: return C["SUB"]
    if score >= 15:  return C["GREEN"]
    if score >= 5:   return "#86efac"
    if score >= -3:  return C["SUB"]
    if score >= -15: return "#fca5a5"
    return C["RED"]
