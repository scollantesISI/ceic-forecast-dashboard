"""
theme.py — Proyección PIB Colombia (ISI | CEIC)
-------------------------------------------------
Mismo patrón que theme.py del proyecto EMIS Benchmark Dashboard (mismas
funciones: apply_custom_theme, render_badge, truncate_label,
render_metric_card).

CONFIRMADO: ISI unificó su marca en marzo de 2026 (CEIC, EMIS, EPFR,
REDD, iMoneyNet bajo "ISI"). Extrayendo el color dominante del logo real
de ISI (logo2.png) por conteo de píxeles, el naranja #FF5315 cubre el
98.7% de los píxeles no blancos del logo — es decir, la marca unificada
adoptó el mismo naranja que ya usaba EMIS (el morado viejo de CEIC, usado
en el proyecto de trade data, quedó obsoleto). Por eso este BRAND es
idéntico al de theme.py del proyecto EMIS Benchmark Dashboard.
"""

import streamlit as st

# ---------------------------------------------------------------------------
# Brand Theme — confirmado contra el logo real de ISI (2026)
# ---------------------------------------------------------------------------
BRAND = {
    "primary": "#FF5315",
    "primary_hover": "#E64510",
    "primary_dark": "#B33A0F",
    "primary_light": "#FFEEE8",
    "primary_soft": "#FFDDD0",
    "text": "#1A1A1A",
    "text_secondary": "#6B7280",
    "border": "#E8E5E3",
    "bg_page": "#FAF9F8",
    "bg_card": "#FFFFFF",
}
CHART_PALETTE = ["#FF5315", "#FFA36B", "#B33A0F", "#4A4A4A", "#FF8B4D", "#7A2E0A", "#D8430D", "#FFD1B3"]


def apply_custom_theme() -> None:
    """Inyecta CSS para alinear la interfaz con la identidad de marca corporativa."""
    st.markdown(f"""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        html, body, [class*="css"] {{ font-family: 'Inter', -apple-system, sans-serif; }}

        .stApp {{ background-color: {BRAND["bg_page"]}; }}

        /* ---------- Headings ---------- */
        h1, h2, h3 {{ color: {BRAND["text"]} !important; font-weight: 800 !important; letter-spacing: -0.02em; }}
        h1 {{ border-bottom: 3px solid {BRAND["primary"]}; padding-bottom: 0.5rem; display: inline-block; }}

        /* ---------- Sidebar ---------- */
        [data-testid="stSidebar"] {{
            background-color: {BRAND["bg_card"]};
            border-right: 1px solid {BRAND["border"]};
        }}
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
            color: {BRAND["primary_dark"]} !important; border-bottom: none;
        }}

        /* ---------- Buttons ---------- */
        .stButton>button, [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {{
            border-radius: 8px !important;
            font-weight: 600 !important;
            transition: all 0.15s ease-in-out;
        }}
        .stButton>button[kind="primary"], [data-testid="stBaseButton-primary"] {{
            background-color: {BRAND["primary"]} !important;
            border-color: {BRAND["primary"]} !important;
            box-shadow: 0 2px 6px rgba(255, 83, 21, 0.25);
        }}
        .stButton>button[kind="primary"]:hover, [data-testid="stBaseButton-primary"]:hover {{
            background-color: {BRAND["primary_hover"]} !important;
            border-color: {BRAND["primary_hover"]} !important;
            box-shadow: 0 4px 10px rgba(255, 83, 21, 0.35);
        }}

        /* ---------- Bordered containers -> tarjetas estilo dashboard ---------- */
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border-radius: 14px !important;
            border-color: {BRAND["border"]} !important;
            background-color: {BRAND["bg_card"]};
            box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.04);
            transition: box-shadow 0.2s ease;
        }}
        [data-testid="stVerticalBlockBorderWrapper"]:hover {{
            box-shadow: 0 6px 16px rgba(255, 83, 21, 0.10);
        }}

        /* ---------- Native metrics ---------- */
        [data-testid="stMetric"] {{
            background-color: {BRAND["bg_card"]};
            border: 1px solid {BRAND["border"]};
            border-radius: 12px;
            padding: 0.9rem 1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        }}
        [data-testid="stMetricLabel"] {{ color: {BRAND["text_secondary"]} !important; text-transform: uppercase; font-size: 0.72rem !important; letter-spacing: 0.04em; }}
        [data-testid="stMetricValue"] {{ color: {BRAND["text"]} !important; font-weight: 800 !important; }}

        /* ---------- Custom metric cards ---------- */
        .isi-metric-card {{
            background-color: {BRAND["bg_card"]};
            border: 1px solid {BRAND["border"]};
            border-radius: 12px;
            padding: 0.9rem 1.1rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            margin-bottom: 0.6rem;
        }}
        .isi-metric-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.35rem; }}
        .isi-metric-label {{ font-size: 0.72rem; color: {BRAND["text_secondary"]}; text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600; }}
        .isi-metric-value {{ font-size: 1.6rem; font-weight: 800; color: {BRAND["text"]}; }}

        /* ---------- Hero metric card (número principal, estilo "Total Sales") ---------- */
        .isi-hero-card {{
            background-color: {BRAND["bg_card"]};
            border: 1px solid {BRAND["border"]};
            border-radius: 16px;
            padding: 1.9rem 1.5rem;
            text-align: center;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05), 0 1px 2px rgba(0,0,0,0.04);
        }}
        .isi-hero-icon {{ font-size: 2.1rem; margin-bottom: 0.4rem; }}
        .isi-hero-value {{ font-size: 2.6rem; font-weight: 800; color: {BRAND["primary"]}; line-height: 1.05; }}
        .isi-hero-label {{ font-size: 0.95rem; color: {BRAND["text"]}; margin-top: 0.4rem; font-weight: 700; }}
        .isi-hero-caption {{ font-size: 0.8rem; color: {BRAND["text_secondary"]}; margin-top: 0.5rem; }}

        /* ---------- Badge "ISI | CEIC API" ---------- */
        .isi-badge {{
            display: inline-flex; align-items: center; gap: 5px;
            background-color: {BRAND["primary_light"]};
            color: {BRAND["primary_dark"]};
            font-size: 0.65rem; font-weight: 700;
            text-transform: uppercase; letter-spacing: 0.04em;
            padding: 3px 9px; border-radius: 999px;
            white-space: nowrap;
        }}
        .isi-badge::before {{
            content: ''; width: 6px; height: 6px; border-radius: 50%;
            background-color: {BRAND["primary"]}; display: inline-block;
        }}

        /* ---------- Tabs ---------- */
        [data-testid="stTabs"] button[aria-selected="true"] {{
            color: {BRAND["primary"]} !important;
            border-bottom-color: {BRAND["primary"]} !important;
            font-weight: 700 !important;
        }}
        [data-testid="stTabs"] button p {{ font-weight: 600; }}

        /* ---------- Progress bar ---------- */
        [data-testid="stProgress"] > div > div > div {{ background-color: {BRAND["primary"]} !important; }}

        /* ---------- Text inputs ---------- */
        .stTextInput input:focus {{ border-color: {BRAND["primary"]} !important; box-shadow: 0 0 0 1px {BRAND["primary"]} !important; }}

        /* ---------- Dividers ---------- */
        hr {{ border-color: {BRAND["border"]} !important; }}

        /* ---------- Imágenes centradas dentro de su contenedor ---------- */
        [data-testid="stImageContainer"] {{ display: flex; justify-content: center; }}

        /* ---------- Login card helpers ---------- */
        .isi-login-logo {{ display: block; margin: 0 auto 0.4rem auto; width: 160px; }}
        .isi-login-title {{ text-align: center; margin: 0.6rem 0 0.1rem 0; }}
        .isi-login-subtitle {{ text-align: center; color: {BRAND["text_secondary"]}; margin-bottom: 1.2rem; font-size: 0.9rem; }}
    </style>
    """, unsafe_allow_html=True)


def render_badge(text: str = "ISI | CEIC API") -> str:
    return f"<span class='isi-badge'>{text}</span>"


def truncate_label(name: str, max_len: int = 30) -> str:
    """Acorta nombres largos para ejes de gráficos, conservando el original para el hover."""
    name = str(name).strip()
    return name if len(name) <= max_len else name[:max_len - 1].rstrip() + "…"


def render_metric_card(label: str, value: str, badge: bool = False) -> None:
    """
    OJO: el HTML se construye en UNA sola línea a propósito. Si se separa
    en varias líneas indentadas (como estaba antes), Markdown interpreta
    4+ espacios de indentación al inicio de línea como bloque de código
    literal — el resultado era que las tarjetas mostraban las etiquetas
    </div> como texto visible en vez de renderizar el HTML.
    """
    badge_html = render_badge() if badge else ""
    html = (
        f'<div class="isi-metric-card">'
        f'<div class="isi-metric-header">'
        f'<span class="isi-metric-label">{label}</span>{badge_html}'
        f'</div>'
        f'<div class="isi-metric-value">{value}</div>'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def render_hero_metric(label: str, value: str, icon: str = "", caption: str = None) -> None:
    """
    Tarjeta grande centrada (icono + número grande + etiqueta), estilo
    "Total Sales" de un dashboard ejecutivo. HTML en una sola línea por
    la misma razón que render_metric_card (ver su docstring).
    """
    caption_html = f'<div class="isi-hero-caption">{caption}</div>' if caption else ""
    html = (
        f'<div class="isi-hero-card">'
        f'<div class="isi-hero-icon">{icon}</div>'
        f'<div class="isi-hero-value">{value}</div>'
        f'<div class="isi-hero-label">{label}</div>'
        f'{caption_html}'
        f'</div>'
    )
    st.markdown(html, unsafe_allow_html=True)
