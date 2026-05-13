import json
import re
import sqlite3
from datetime import date, datetime, timedelta
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from pathlib import Path

# ── Dependencias opcionales ───────────────────────────────────────────────────
try:
    import statsmodels
    _HAS_STATSMODELS = True
except ImportError:
    _HAS_STATSMODELS = False

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG Y TEMA
# ─────────────────────────────────────────────────────────────────────────────
# El dashboard esta pensado como vista ejecutiva del lote procesado, no como reemplazo del reporte tecnico.
st.set_page_config(page_title="FincaDiag", layout="wide")

GREEN  = "#27AE60"
YELLOW = "#F4D03F"
ORANGE = "#E67E22"
RED    = "#E74C3C"
BLUE   = "#2980B9"
BG     = "#0d1a0d"

st.markdown(f"""
<style>
.stApp {{ background-color:{BG}; color:#e2f1ec; }}
[data-testid="stSidebar"] {{ background-color:#09120e !important; border-right:1px solid #1c3b2b; }}
.stTabs [aria-selected="true"] {{ color:{GREEN} !important; border-bottom-color:{GREEN} !important; }}

/* KPI banner */
.kpi-box {{
    background:#1a2b1a; border-radius:10px; padding:14px 10px;
    text-align:center; border-top:3px solid {GREEN}; height:100px;
    display:flex; flex-direction:column; justify-content:center;
    margin-bottom: 15px;
}}
.kpi-val  {{ font-size:1.7em; font-weight:800; color:#fff; line-height:1.1; }}
.kpi-lbl  {{ font-size:0.65rem; color:#8dae9d; text-transform:uppercase; letter-spacing:0.8px; margin-top:4px; }}
.kpi-sub  {{ font-size:0.7rem; color:{GREEN}; margin-top:2px; }}

/* KPI alertas */
.kpi-red   {{ border-top-color:{RED}; }}
.kpi-yellow{{ border-top-color:{YELLOW}; }}
.kpi-blue  {{ border-top-color:{BLUE}; }}

/* Assessment grid */
.grid-cell {{
    display:inline-block; padding:5px 10px; border-radius:6px;
    font-size:0.72rem; font-weight:700; margin:2px; min-width:68px; text-align:center;
}}
.cell-green  {{ background:{GREEN}; color:#fff; }}
.cell-yellow {{ background:{YELLOW}; color:#333; }}
.cell-orange {{ background:{ORANGE}; color:#fff; }}
.cell-red    {{ background:{RED}; color:#fff; }}

/* Section header */
.sec-hdr {{
    background:#1a2b1a; border-left:4px solid {GREEN};
    padding:7px 14px; border-radius:0 8px 8px 0;
    font-weight:700; font-size:0.85rem; margin:18px 0 10px;
    text-transform:uppercase; letter-spacing:0.5px; color:{GREEN};
}}

/* Visit card */
.vcard {{
    background:#1a2b1a; padding:14px; border-radius:10px;
    border-left:5px solid {GREEN}; margin-bottom:8px; height:185px;
    display:flex; flex-direction:column; justify-content:space-between;
    align-items:center; text-align:center;
}}
.vname {{ font-size:0.7rem; color:#8dae9d; font-weight:700; text-transform:uppercase; }}
.vval  {{ font-size:2em; font-weight:800; color:#fff; }}
.vlbl  {{ font-size:0.6rem; letter-spacing:1px; text-transform:uppercase; }}
.vsub  {{ font-size:0.65rem; color:#8dae9d; }}

/* Legend */
.leg-item {{ display:flex; align-items:center; gap:8px; font-size:0.78rem; color:#c2d9c8; margin-bottom:5px; }}
.leg-dot  {{ width:11px; height:11px; border-radius:50%; flex-shrink:0; }}

.stButton>button {{
    background:#1a2b1a; color:#fff; border:1px solid {GREEN};
    width:100%; font-size:0.72rem;
}}
.stButton>button:hover {{ background:{GREEN}; }}
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# RUTAS
# ─────────────────────────────────────────────────────────────────────────────
_ROOT = Path(__file__).resolve().parents[3]
BASE_DIR      = _ROOT if (_ROOT / "data").exists() else Path(__file__).resolve().parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
DB_PATH       = BASE_DIR / "data" / "finca_muestras.db"

# ─────────────────────────────────────────────────────────────────────────────
# DATOS
# ─────────────────────────────────────────────────────────────────────────────
def get_db() -> pd.DataFrame:
    # La base consolidada sirve para metricas transversales que no siempre estan en los CSV por visita.
    if not DB_PATH.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            if not conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='registro_muestras'"
            ).fetchone():
                return pd.DataFrame()
            return pd.read_sql_query(
                "SELECT * FROM registro_muestras ORDER BY fecha DESC, id_muestra ASC", conn
            )
    except Exception:
        return pd.DataFrame()

def load_visits(path: Path, label: str) -> pd.DataFrame:
    p = path.with_name(f"{label}_visits.csv")
    if not p.exists():
        return pd.DataFrame()
    df = pd.read_csv(p)
    if "visit_name" in df.columns:
        visit_dt = pd.to_datetime(
            df["visit_name"]
            .astype(str)
            .str.replace("Visita_", "", regex=False),
            format="%d_%m_%Y",
            errors="coerce",
        )
        df = df.assign(_visit_dt=visit_dt).sort_values(
            by=["_visit_dt", "visit_name"],
            ascending=[True, True],
            na_position="last",
            kind="mergesort",
        )
        df = df.drop(columns=["_visit_dt"], errors="ignore").reset_index(drop=True)
    return df

def load_sessions(path: Path, label: str) -> pd.DataFrame:
    p = path.with_name(f"{label}_sessions.csv")
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)

def load_corr(path: Path, label: str) -> pd.DataFrame:
    p = path.with_name(f"{label}_correlacion_global.csv")
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)

def num(val) -> float:
    try:
        v = float(val)
        return 0.0 if pd.isna(v) else v
    except Exception:
        return 0.0


def format_visit_label(value: str, prefix: str = "V") -> str:
    raw = str(value or "?")
    raw = raw.replace("Visita_", "")
    raw = re.sub(r"_\d{4}$", "", raw)
    if prefix == "V":
        return f"V{raw}" if raw else "V?"
    if prefix == "Visita ":
        return f"Visita {raw}" if raw else "Visita ?"
    return raw if raw else "?"

# ─────────────────────────────────────────────────────────────────────────────
# CLASIFICACIÓN
# ─────────────────────────────────────────────────────────────────────────────
def classify(eta: float) -> str:
    if eta >= 85:   return "cubierto"
    elif eta >= 60: return "parcial_ok"
    elif eta > 0:   return "parcial"
    else:           return "no_cubierto"

CAT_CSS   = {"cubierto":"cell-green","parcial_ok":"cell-yellow","parcial":"cell-orange","no_cubierto":"cell-red"}
CAT_COLOR = {"cubierto":GREEN,"parcial_ok":YELLOW,"parcial":ORANGE,"no_cubierto":RED}

# ─────────────────────────────────────────────────────────────────────────────
# CHART HELPERS
# ─────────────────────────────────────────────────────────────────────────────
DARK = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font_color="#fff")

def dark(fig, h=240):
    fig.update_layout(**DARK, height=h, margin=dict(l=0,r=0,t=30,b=0))
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# BANNER DE KPIs (Distribuido para evitar apuñamiento)
# ─────────────────────────────────────────────────────────────────────────────
def render_kpi_banner(visits_df: pd.DataFrame, db_df: pd.DataFrame, summary: dict):
    st.markdown('<div class="sec-hdr">Indicadores clave del diagnóstico forense</div>', unsafe_allow_html=True)

    # Aqui se priorizan indicadores de lectura rapida para saber como viene el lote sin abrir cada visita.
    eta_global  = num(pd.to_numeric(visits_df.get("avg_eta_extraccion", pd.Series()), errors="coerce").mean()) if not visits_df.empty else 0.0
    jitter_max  = num(pd.to_numeric(db_df.get("jitter_ms", pd.Series()), errors="coerce").max()) if not db_df.empty else 71.3
    plr_med     = num(pd.to_numeric(db_df.get("packet_loss", pd.Series()), errors="coerce").mean()) if not db_df.empty else 0.0
    desfase_max = num(pd.to_numeric(db_df.get("desfase_max_ms", pd.Series()), errors="coerce").max()) if not db_df.empty else 87.95
    multicast   = num(pd.to_numeric(visits_df.get("avg_multicast_pct", pd.Series()), errors="coerce").mean()) if not visits_df.empty else 0.0
    total_sess  = int(summary.get("total_sessions", 0) or 0)
    total_vis   = int(summary.get("total_visits", 0) or 0)
    alertas_al  = int(summary.get("total_alertas_altas", 0) or 0)
    alertas_cr  = int(summary.get("total_alertas_criticas", 0) or 0)

    # Definir todos los KPIs
    kpis = [
        ("η línea base",     "0.55%",          "sin gateway",       ""),
        ("η actual",         f"{eta_global:.1f}%", "promedio visitas", "" if eta_global >= 85 else "kpi-red"),
        ("Meta η",           "95%",             "objetivo TFG",      "kpi-blue"),
        ("Jitter máx.",      f"{jitter_max:.1f} ms", "documentado",  "kpi-yellow" if jitter_max > 50 else ""),
        ("Desfase máx.",     f"{desfase_max:.1f} ms", "serial↔red",  "kpi-yellow"),
        ("Ruido UDP",        "43.29 Hz",        "sin filtrar",       "kpi-red"),
        ("PLR medio",        f"{plr_med:.2f}%", "pérdida paquetes",  ""),
        ("Multicast",        f"{multicast:.1f}%", "del tráfico",     "kpi-yellow" if multicast > 15 else ""),
        ("Alertas altas",    str(alertas_al),   f"{alertas_cr} críticas", "kpi-red" if alertas_cr > 0 else ""),
    ]

    # Fila 1: 5 columnas
    cols_top = st.columns(5)
    for col, (lbl, val, sub, extra) in zip(cols_top, kpis[:5]):
        with col:
            st.markdown(f"""
            <div class="kpi-box {extra}">
                <div class="kpi-val">{val}</div>
                <div class="kpi-lbl">{lbl}</div>
                <div class="kpi-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

    # Fila 2: 4 columnas
    cols_bot = st.columns(4)
    for col, (lbl, val, sub, extra) in zip(cols_bot, kpis[5:]):
        with col:
            st.markdown(f"""
            <div class="kpi-box {extra}">
                <div class="kpi-val">{val}</div>
                <div class="kpi-lbl">{lbl}</div>
                <div class="kpi-sub">{sub}</div>
            </div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# ASSESSMENT DONUT + GRID
# ─────────────────────────────────────────────────────────────────────────────
def render_assessment(visits_df: pd.DataFrame):
    st.markdown('<div class="sec-hdr">Cobertura η por visita</div>', unsafe_allow_html=True)

    if visits_df.empty:
        st.info("No hay visitas para mostrar.")
        return

    # Contar por categoría
    cats = {"cubierto": 0, "parcial_ok": 0, "parcial": 0, "no_cubierto": 0}
    for _, r in visits_df.iterrows():
        cats[classify(num(r.get("avg_eta_extraccion", 0)))] += 1

    total  = sum(cats.values()) or 1
    pct_ok = round(cats["cubierto"] / total * 100)

    left, right = st.columns([1, 2.8])

    with left:
        # Donut
        fig_d = go.Figure(go.Pie(
            labels=["Cubierto","Con obs.","Parcial","No cubierto"],
            values=[cats["cubierto"], cats["parcial_ok"], cats["parcial"], cats["no_cubierto"]],
            hole=0.62, marker_colors=[GREEN, YELLOW, ORANGE, RED],
            textinfo="none",
            hovertemplate="%{label}: %{value}<extra></extra>",
        ))
        fig_d.update_layout(
            annotations=[dict(text=f"<b>{pct_ok}%</b>", x=0.5, y=0.5,
                              font_size=26, font_color="#fff", showarrow=False)],
            showlegend=False, **DARK, height=200,
            margin=dict(l=0, r=0, t=0, b=0),
        )
        st.plotly_chart(fig_d, use_container_width=True)

        # Leyenda
        for color, n_val, lbl in [
            (GREEN,  cats["cubierto"],    "Cubierto (η ≥ 85%)"),
            (YELLOW, cats["parcial_ok"],  "Con observaciones"),
            (ORANGE, cats["parcial"],     "Parcial (η > 0%)"),
            (RED,    cats["no_cubierto"], "No cubierto"),
        ]:
            st.markdown(f"""
            <div class="leg-item">
                <div class="leg-dot" style="background:{color}"></div>
                <b style="color:{color}; min-width:18px">{n_val}</b> {lbl}
            </div>""", unsafe_allow_html=True)

    with right:
        # Grilla de celdas
        cells = []
        for _, r in visits_df.iterrows():
            eta    = num(r.get("avg_eta_extraccion", 0))
            cat    = classify(eta)
            css    = CAT_CSS[cat]
            nombre = format_visit_label(r.get("visit_name", "?"), prefix="V")
            tip    = f"η={eta:.1f}%"
            cells.append(f'<span class="grid-cell {css}" title="{tip}">{nombre}</span>')

        rows_html = []
        for i in range(0, len(cells), 6):
            rows_html.append('<div style="margin-bottom:4px;">' + "".join(cells[i:i+6]) + '</div>')
        st.markdown("\n".join(rows_html), unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# MODAL EMERGENTE DE VISITA
# ─────────────────────────────────────────────────────────────────────────────
@st.dialog("Análisis Detallado del Nodo", width="large")
def show_visit_details(r):
    nombre = format_visit_label(r.get("visit_name", "?"), prefix="Visita ")
    eta    = num(r.get("avg_eta_extraccion", 0))
    alts   = int(r.get("total_alertas_altas", 0) or 0)
    crit   = int(r.get("total_alertas_criticas", 0) or 0)
    mc_v   = num(r.get("avg_multicast_pct", 0))
    def_v  = num(r.get("avg_desfase_medio_ms", 0))
    
    st.markdown(f"### 📍 {nombre}")
    st.markdown("---")
    
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Eficiencia η", f"{eta:.1f}%", "-Crítico" if eta < 85 else "Óptimo", delta_color="inverse" if eta < 85 else "normal")
    m2.metric("Tasa Multicast", f"{mc_v:.1f}%", f"+{mc_v - 15:.1f}% sobre límite" if mc_v > 15 else "Normal", delta_color="inverse")
    m3.metric("Desfase Medio", f"{def_v:.1f} ms", f"+{def_v - 50:.1f} ms riesgo" if def_v > 50 else "Estable", delta_color="inverse")
    m4.metric("Alertas Críticas", crit, f"{alts} Alertas Altas", delta_color="inverse" if crit > 0 or alts > 0 else "normal")

    st.markdown("---")
    st.markdown("**Composición de sesiones**")
    
    sess = int(r.get("total_sessions", 0) or 0)
    pcaps = int(r.get("sessions_with_pcap", 0) or 0)
    ser = int(r.get("sessions_with_serial", 0) or 0)
    ant = int(r.get("sessions_with_antenna_udp", 0) or 0)
    
    # Un pequeño DataFrame renderizado para que sea claro el contexto sin llenar de texto
    df_detalle = pd.DataFrame(
        {
            "Métrica": [
                "Sesiones totales",
                "Capturas PCAP",
                "Sesiones con serial (DB9)",
                "Sesiones con antena UDP",
            ],
            "Valor": [sess, pcaps, ser, ant],
        }
    )
    st.dataframe(df_detalle, hide_index=True, use_container_width=True)

    st.markdown("---")
    st.markdown("**Distribución**")
    df_vis = pd.DataFrame({
        "Tipo": ["PCAP", "Serial", "Collar"],
        "Sesiones": [pcaps, ser, ant]
    })
    fig_m = px.bar(df_vis, x="Tipo", y="Sesiones",
                   color="Tipo",
                   color_discrete_sequence=[BLUE, GREEN, YELLOW])
    fig_m.update_layout(**DARK, height=200, margin=dict(l=0,r=0,t=10,b=0), showlegend=False)
    st.plotly_chart(fig_m, use_container_width=True)

    # Evaluación rápida
    st.markdown("**Evaluación**")
    if eta >= 95:
        st.success(f"η={eta:.1f}% cumple la meta del TFG (≥95%)")
    elif eta >= 85:
        st.warning(f"η={eta:.1f}% es aceptable, pero no alcanza el 95%")
    else:
        st.error(f"η={eta:.1f}% está por debajo del umbral mínimo de 85%")
    if mc_v > 15:
        st.warning(f"Multicast {mc_v:.1f}% supera el umbral del 15% y puede estar afectando η")
    if def_v > 71.3:
        st.error(f"Desfase {def_v:.1f} ms supera el jitter máximo documentado (71.3 ms)")

# ─────────────────────────────────────────────────────────────────────────────
# VISITA CARDS
# ─────────────────────────────────────────────────────────────────────────────
def render_visit_cards(visits_df: pd.DataFrame):
    if visits_df.empty:
        return
    st.markdown('<div class="sec-hdr">Nodos de captura</div>', unsafe_allow_html=True)
    n_cols = min(len(visits_df), 4)
    cols   = st.columns(n_cols)
    for i, (_, r) in enumerate(visits_df.iterrows()):
        with cols[i % n_cols]:
            eta   = num(r.get("avg_eta_extraccion", 0))
            sess  = int(r.get("total_sessions", 0) or 0)
            alts  = int(r.get("total_alertas_altas", 0) or 0)
            pcaps = int(r.get("sessions_with_pcap", 0) or 0)
            ser   = int(r.get("sessions_with_serial", 0) or 0)
            bc    = CAT_COLOR[classify(eta)]
            nombre= format_visit_label(r.get("visit_name", "?"), prefix="")
            
            st.markdown(f"""
            <div class="vcard" style="border-left-color:{bc};">
                <div class="vname">{nombre}</div>
                <div class="vval" style="color:{bc};">{eta:.1f}%</div>
                <div class="vlbl" style="color:{bc};">Eficiencia η</div>
                <div class="vsub">{sess} ses. · {pcaps} PCAP · {ser} serial</div>
                <div class="vsub" style="color:{'#E74C3C' if alts>0 else '#8dae9d'};">
                    {'⚠ ' + str(alts) + ' alertas' if alts > 0 else '✓ Sin alertas'}
                </div>
            </div>""", unsafe_allow_html=True)
            
            if st.button("Ver detalle", key=f"btn_{r.get('visit_name',i)}"):
                show_visit_details(r)

# ─────────────────────────────────────────────────────────────────────────────
# TENDENCIA TEMPORAL DE η
# ─────────────────────────────────────────────────────────────────────────────
def render_eta_trend(visits_df: pd.DataFrame):
    if visits_df.empty or "avg_eta_extraccion" not in visits_df.columns:
        return
    st.markdown('<div class="sec-hdr">Tendencia de eficiencia η por visita</div>', unsafe_allow_html=True)
    df = visits_df.copy()
    df["eta"]    = pd.to_numeric(df["avg_eta_extraccion"], errors="coerce")
    df["visita"] = df["visit_name"].astype(str).map(lambda x: format_visit_label(x, prefix="V"))
    df["desfase"]= pd.to_numeric(df.get("avg_desfase_medio_ms", pd.Series(0)), errors="coerce").fillna(0)

    c1, c2 = st.columns(2)

    with c1:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["visita"], y=df["eta"], mode="lines+markers",
            line=dict(color=GREEN, width=2.5),
            marker=dict(size=9, color=[CAT_COLOR[classify(e)] for e in df["eta"].fillna(0)]),
            name="η (%)",
        ))
        fig.add_hline(y=95, line_dash="dash", line_color=YELLOW,
                      annotation_text="Meta 95%", annotation_font_color=YELLOW)
        fig.add_hline(y=0.55, line_dash="dot", line_color=RED,
                      annotation_text="Línea base 0.55%", annotation_font_color=RED)
        fig.update_layout(**DARK, height=240, margin=dict(l=0,r=0,t=30,b=0),
                          xaxis=dict(tickangle=-30), yaxis=dict(title="η (%)"),
                          title="η por visita vs meta TFG")
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        # Desfase temporal por visita
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(
            x=df["visita"], y=df["desfase"],
            marker_color=[RED if d > 71.3 else YELLOW if d > 30 else GREEN for d in df["desfase"].fillna(0)],
            name="Desfase medio (ms)",
        ))
        fig2.add_hline(y=71.3, line_dash="dash", line_color=RED,
                       annotation_text="Jitter máx. documentado", annotation_font_color=RED)
        fig2.update_layout(**DARK, height=240, margin=dict(l=0,r=0,t=30,b=0),
                           xaxis=dict(tickangle=-30), yaxis=dict(title="ms"),
                           title="Desfase serial↔red por visita")
        st.plotly_chart(fig2, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# GAUGE η ACTUAL VS META
# ─────────────────────────────────────────────────────────────────────────────
def render_eta_gauge(visits_df: pd.DataFrame):
    if visits_df.empty:
        return
    eta_global = num(pd.to_numeric(visits_df.get("avg_eta_extraccion", pd.Series()), errors="coerce").mean())
    eta_max    = num(pd.to_numeric(visits_df.get("avg_eta_extraccion", pd.Series()), errors="coerce").max())
    eta_min    = num(pd.to_numeric(visits_df.get("avg_eta_extraccion", pd.Series()), errors="coerce").min())

    c1, c2, c3 = st.columns(3)

    with c1:
        fig_g = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=eta_global,
            delta={"reference": 0.55, "increasing": {"color": GREEN},
                   "decreasing": {"color": RED}, "suffix": "%"},
            title={"text": "η promedio actual", "font": {"color": "#fff", "size": 13}},
            number={"suffix": "%", "font": {"color": "#fff", "size": 28}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#8dae9d", "tickfont": {"color": "#8dae9d"}},
                "bar": {"color": GREEN},
                "bgcolor": "#1a2b1a",
                "bordercolor": "#1a2b1a",
                "steps": [
                    {"range": [0, 30],  "color": "#2d1010"},
                    {"range": [30, 60], "color": "#2d2010"},
                    {"range": [60, 85], "color": "#2d2d10"},
                    {"range": [85, 100],"color": "#102d10"},
                ],
                "threshold": {
                    "line": {"color": YELLOW, "width": 3},
                    "thickness": 0.85,
                    "value": 95,
                },
            },
        ))
        fig_g.update_layout(**DARK, height=220, margin=dict(l=20,r=20,t=40,b=10))
        st.plotly_chart(fig_g, use_container_width=True)

    with c2:
        fig_g2 = go.Figure(go.Indicator(
            mode="gauge+number",
            value=eta_max,
            title={"text": "η máximo alcanzado", "font": {"color": "#fff", "size": 13}},
            number={"suffix": "%", "font": {"color": "#fff", "size": 28}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#8dae9d", "tickfont": {"color": "#8dae9d"}},
                "bar": {"color": BLUE},
                "bgcolor": "#1a2b1a",
                "bordercolor": "#1a2b1a",
                "steps": [
                    {"range": [0, 85],  "color": "#101a2d"},
                    {"range": [85, 100],"color": "#102d10"},
                ],
                "threshold": {"line": {"color": YELLOW, "width": 3}, "thickness": 0.85, "value": 95},
            },
        ))
        fig_g2.update_layout(**DARK, height=220, margin=dict(l=20,r=20,t=40,b=10))
        st.plotly_chart(fig_g2, use_container_width=True)

    with c3:
        # Mini tabla de resumen estadístico
        st.markdown("**Estadísticas de η**")
        etas = pd.to_numeric(visits_df.get("avg_eta_extraccion", pd.Series()), errors="coerce").dropna()
        if not etas.empty:
            stats = pd.DataFrame({
                "Métrica": ["Mínimo", "Media", "Mediana", "Máximo", "Desv. estándar", "Vs meta 95%"],
                "Valor": [
                    f"{etas.min():.2f}%",
                    f"{etas.mean():.2f}%",
                    f"{etas.median():.2f}%",
                    f"{etas.max():.2f}%",
                    f"±{etas.std():.2f}%",
                    f"{etas.mean() - 95:.2f}pp",
                ]
            })
            st.dataframe(stats, hide_index=True, use_container_width=True, height=240)

# ─────────────────────────────────────────────────────────────────────────────
# THREAT PANEL
# ─────────────────────────────────────────────────────────────────────────────
def render_threat_panel(visits_df: pd.DataFrame, db_df: pd.DataFrame):
    st.markdown('<div class="sec-hdr">Panel de amenazas y riesgos de red</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    # ── Alertas por visita (stacked bar) ─────────────────────────────────────
    with c1:
        st.markdown("**Estado de alertas por visita**")
        if not visits_df.empty:
            df  = visits_df.copy()
            nom = df["visit_name"].astype(str).map(lambda x: format_visit_label(x, prefix="V"))
            fig = go.Figure()
            for col, color, lbl in [
                ("total_alertas_criticas", RED,    "Críticas"),
                ("total_alertas_altas",    ORANGE, "Altas"),
            ]:
                vals = pd.to_numeric(df.get(col, pd.Series(0)), errors="coerce").fillna(0)
                fig.add_trace(go.Bar(name=lbl, x=nom, y=vals, marker_color=color))
            fig.update_layout(**DARK, barmode="stack", height=230,
                              margin=dict(l=0,r=0,t=10,b=0),
                              legend=dict(orientation="h", y=1.1, font_size=9),
                              xaxis=dict(tickangle=-35, tickfont_size=9))
            st.plotly_chart(fig, use_container_width=True)

    # ── Distribución de riesgo (donut) ────────────────────────────────────────
    with c2:
        st.markdown("**Distribución de riesgo actual**")
        if not visits_df.empty:
            etas = pd.to_numeric(visits_df.get("avg_eta_extraccion", pd.Series(0)), errors="coerce").fillna(0)
            rk   = {
                "No cubierto (η<30%)":  int((etas < 30).sum()),
                "Parcial (30-60%)":     int(((etas >= 30) & (etas < 60)).sum()),
                "Elevado (60-85%)":     int(((etas >= 60) & (etas < 85)).sum()),
                "Cubierto (≥85%)":      int((etas >= 85).sum()),
            }
            total  = sum(rk.values()) or 1
            pct_ok = round(rk["Cubierto (≥85%)"] / total * 100)
            fig_p  = go.Figure(go.Pie(
                labels=list(rk.keys()), values=list(rk.values()),
                hole=0.6, marker_colors=[RED, ORANGE, YELLOW, GREEN],
                textinfo="none",
                hovertemplate="%{label}: %{value}<extra></extra>",
            ))
            fig_p.update_layout(
                annotations=[dict(text=f"<b>{pct_ok}%</b>", x=0.5, y=0.5,
                                  font_size=22, font_color="#fff", showarrow=False)],
                **DARK, height=230, showlegend=True,
                legend=dict(orientation="v", font_size=9, x=1),
                margin=dict(l=0, r=80, t=10, b=0),
            )
            st.plotly_chart(fig_p, use_container_width=True)

    # ── Exposición por categoría de amenaza ────────────────────────────────────
    with c3:
        st.markdown("**Exposición por vector de amenaza**")
        if not visits_df.empty:
            mc_alto = int((pd.to_numeric(visits_df.get("avg_multicast_pct", pd.Series(0)), errors="coerce") > 15).sum())
            def_alto= int((pd.to_numeric(visits_df.get("avg_desfase_medio_ms", pd.Series(0)), errors="coerce") > 50).sum())
            crit    = int(pd.to_numeric(visits_df.get("total_alertas_criticas", pd.Series(0)), errors="coerce").sum())
            alts    = int(pd.to_numeric(visits_df.get("total_alertas_altas", pd.Series(0)), errors="coerce").sum())
            sin_ser = int((pd.to_numeric(visits_df.get("sessions_with_serial", pd.Series(0)), errors="coerce") == 0).sum())
            cats    = {
                "Sin cifrado UDP": len(visits_df),
                "Broadcast/multicast alto": mc_alto,
                "Jitter > 50 ms":  def_alto,
                "Alertas críticas": crit,
                "Alertas altas":    alts,
                "Sin captura serial": sin_ser,
            }
            fig_h = go.Figure(go.Bar(
                x=list(cats.values()), y=list(cats.keys()),
                orientation="h",
                marker_color=[RED, ORANGE, YELLOW, RED, ORANGE, YELLOW],
                text=list(cats.values()), textposition="auto",
            ))
            fig_h.update_layout(**DARK, height=230, margin=dict(l=0,r=0,t=10,b=0),
                                xaxis=dict(title=""))
            st.plotly_chart(fig_h, use_container_width=True)

    # ── Fila 2: scatter multicast vs η + tabla de riesgo ──────────────────────
    c4, c5 = st.columns([1.3, 1])

    with c4:
        st.markdown("**Impacto multicast vs η extracción (trendline)**")
        if not visits_df.empty:
            mc  = pd.to_numeric(visits_df.get("avg_multicast_pct",  pd.Series()), errors="coerce")
            eta = pd.to_numeric(visits_df.get("avg_eta_extraccion", pd.Series()), errors="coerce")
            nom = visits_df["visit_name"].astype(str).map(lambda x: format_visit_label(x, prefix="V"))
            if mc.notna().any() and eta.notna().any():
                df_sc = pd.DataFrame({"Multicast %": mc.fillna(0), "η (%)": eta.fillna(0), "Visita": nom})
                fig_s = px.scatter(df_sc, x="Multicast %", y="η (%)", text="Visita",
                                   trendline="ols" if _HAS_STATSMODELS else None, color_discrete_sequence=[GREEN])
                fig_s.update_traces(marker_size=10, textfont_color="#fff", textposition="top center")
                fig_s.add_hline(y=95, line_dash="dash", line_color=YELLOW,
                                annotation_text="Meta 95%", annotation_font_color=YELLOW)
                dark(fig_s, 260)
                st.plotly_chart(fig_s, use_container_width=True)

    with c5:
        st.markdown("**Tabla de riesgo por visita**")
        if not visits_df.empty:
            rows = []
            for _, r in visits_df.iterrows():
                eta   = num(r.get("avg_eta_extraccion", 0))
                alts  = int(r.get("total_alertas_altas", 0) or 0)
                crit  = int(r.get("total_alertas_criticas", 0) or 0)
                mc_v  = num(r.get("avg_multicast_pct", 0))
                def_v = num(r.get("avg_desfase_medio_ms", 0))
                if crit > 0 or eta < 30:
                    nivel = "Alto"
                elif alts > 2 or eta < 60:
                    nivel = "Elevado"
                elif alts > 0 or eta < 85:
                    nivel = "Guarded"
                else:
                    nivel = "Bajo"
                nombre = format_visit_label(r.get("visit_name", "?"), prefix="V")
                rows.append({
                    "Visita": nombre, "η (%)": f"{eta:.1f}",
                    "Alertas": alts, "Críticas": crit,
                    "Multicast %": f"{mc_v:.1f}", "Desfase (ms)": f"{def_v:.1f}",
                    "Riesgo": nivel,
                })
            df_r = pd.DataFrame(rows)
            color_map = {"Alto": RED, "Elevado": ORANGE, "Guarded": BLUE, "Bajo": GREEN}

            def color_riesgo(val):
                c = color_map.get(val, "#fff")
                return f"color:{c}; font-weight:bold"

            st.dataframe(
                df_r.style.map(color_riesgo, subset=["Riesgo"]),
                use_container_width=True, height=260, hide_index=True,
            )

# ─────────────────────────────────────────────────────────────────────────────
# DISTRIBUCIÓN DE MUESTREO
# ─────────────────────────────────────────────────────────────────────────────
def render_sample_dist(summary: dict, visits_df: pd.DataFrame):
    st.markdown('<div class="sec-hdr">Distribución de muestreo y cobertura</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**Tipos de sesión**")
        counts = summary.get("sample_type_counts", {})
        if counts:
            order  = ["SERIAL + PCAP","Antena + PCAP","PCAP + ETL","PCAP solo","Baseline","Otros"]
            df_t   = pd.DataFrame([{"tipo": k, "cantidad": int(counts.get(k,0) or 0)} for k in order])
            fig_b  = px.bar(df_t, x="tipo", y="cantidad", color_discrete_sequence=[GREEN])
            dark(fig_b, 230)
            fig_b.update_layout(xaxis_title="", yaxis_title="Sesiones")
            st.plotly_chart(fig_b, use_container_width=True)

    with c2:
        st.markdown("**Cobertura PCAP vs Serial por visita**")
        if not visits_df.empty:
            nom   = visits_df["visit_name"].astype(str).map(lambda x: format_visit_label(x, prefix="V"))
            pcap  = pd.to_numeric(visits_df.get("sessions_with_pcap",   pd.Series(0)), errors="coerce").fillna(0)
            ser   = pd.to_numeric(visits_df.get("sessions_with_serial",  pd.Series(0)), errors="coerce").fillna(0)
            collar= pd.to_numeric(visits_df.get("sessions_with_antenna_udp", pd.Series(0)), errors="coerce").fillna(0)
            fig_l = go.Figure()
            fig_l.add_trace(go.Bar(name="PCAP",   x=nom, y=pcap,   marker_color=BLUE))
            fig_l.add_trace(go.Bar(name="Serial",  x=nom, y=ser,    marker_color=GREEN))
            fig_l.add_trace(go.Bar(name="Collar",  x=nom, y=collar, marker_color=YELLOW))
            fig_l.update_layout(**DARK, barmode="group", height=230,
                                margin=dict(l=0,r=0,t=10,b=0),
                                xaxis=dict(tickangle=-30, tickfont_size=9),
                                legend=dict(orientation="h", y=1.1, font_size=9))
            st.plotly_chart(fig_l, use_container_width=True)

    with c3:
        st.markdown("**Cobertura de ordeño AM vs PM**")
        if not visits_df.empty:
            # Estimar sesiones de ordeño vs normales desde los datos disponibles
            total_s = pd.to_numeric(visits_df.get("total_sessions", pd.Series(0)), errors="coerce").fillna(0).sum()
            serial_s= pd.to_numeric(visits_df.get("sessions_with_serial", pd.Series(0)), errors="coerce").fillna(0).sum()
            normal_s= max(0, total_s - serial_s)
            fig_pie = go.Figure(go.Pie(
                labels=["Ordeño (con serial)", "Normal (sin serial)", "Baseline"],
                values=[serial_s, normal_s,
                        int(summary.get("total_sessions", 0) or 0) - int(total_s)],
                hole=0.55, marker_colors=[GREEN, BLUE, "#555"],
                textinfo="percent+label", textfont_size=9,
            ))
            fig_pie.update_layout(**DARK, height=230,
                                  margin=dict(l=0,r=0,t=10,b=0),
                                  showlegend=False)
            st.plotly_chart(fig_pie, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB GENERAL COMPLETO
# ─────────────────────────────────────────────────────────────────────────────
def tab_general(label: str, path: Path, summary: dict):
    visits_df = load_visits(path, label)
    db_df     = get_db()

    render_kpi_banner(visits_df, db_df, summary)
    st.markdown("---")
    render_assessment(visits_df)
    st.markdown("---")
    render_visit_cards(visits_df)
    st.markdown("---")
    render_eta_trend(visits_df)
    st.markdown("---")
    render_eta_gauge(visits_df)
    st.markdown("---")
    render_sample_dist(summary, visits_df)
    st.markdown("---")
    render_threat_panel(visits_df, db_df)

# ─────────────────────────────────────────────────────────────────────────────
# TAB SINCRONÍA
# ─────────────────────────────────────────────────────────────────────────────
def tab_sincronia(label: str, path: Path):
    st.subheader("Sincronía (Edge)")
    df_s = load_corr(path, label)

    if df_s.empty:
        st.info("No hay datos de correlación para este lote.")
        return

    x_col = "timestamp_serial" if "timestamp_serial" in df_s.columns else df_s.columns[0]
    delta  = df_s["delta_ms"].abs() if "delta_ms" in df_s.columns else pd.Series()

    # KPIs
    dentro_50  = int((delta <= 50).sum()) if not delta.empty else 0
    pct_dentro = round(dentro_50 / len(delta) * 100) if len(delta) > 0 else 0

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Eventos correlacionados", len(df_s))
    m2.metric("Desfase medio (ms)",  f"{delta.mean():.2f}" if not delta.empty else "N/D")
    m3.metric("Desfase máximo (ms)", f"{delta.max():.2f}"  if not delta.empty else "N/D")
    m4.metric("Dentro de ±50 ms",   f"{dentro_50} / {len(delta)}" if not delta.empty else "N/D")
    m5.metric("Estabilidad temporal", f"{pct_dentro}%", "dentro de ventana")

    # Gauge de estabilidad
    fig_gs = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct_dentro,
        title={"text": "% eventos dentro de ±50 ms", "font":{"color":"#fff","size":12}},
        number={"suffix":"%","font":{"color":"#fff","size":28}},
        gauge={
            "axis":{"range":[0,100],"tickcolor":"#8dae9d","tickfont":{"color":"#8dae9d"}},
            "bar":{"color": GREEN if pct_dentro >= 80 else YELLOW if pct_dentro >= 50 else RED},
            "bgcolor":"#1a2b1a","bordercolor":"#1a2b1a",
            "steps":[{"range":[0,50],"color":"#2d1010"},{"range":[50,80],"color":"#2d2d10"},{"range":[80,100],"color":"#102d10"}],
            "threshold":{"line":{"color":YELLOW,"width":3},"thickness":0.85,"value":80},
        },
    ))
    fig_gs.update_layout(**DARK, height=200, margin=dict(l=20,r=20,t=40,b=10))
    st.plotly_chart(fig_gs, use_container_width=True)

    c1, c2 = st.columns(2)
    upd = dict(**DARK, height=250, margin=dict(l=0,r=0,t=30,b=0))

    with c1:
        st.markdown("**Dispersión de desfase temporal**")
        fig2 = px.scatter(df_s, x=x_col, y="delta_ms", color_discrete_sequence=[GREEN])
        fig2.add_hline(y=0, line_dash="dash", line_color="#fff", opacity=0.3)
        fig2.add_hrect(y0=-50, y1=50, fillcolor=GREEN, opacity=0.05,
                       annotation_text="Ventana ±50 ms", annotation_font_color=GREEN)
        st.plotly_chart(fig2.update_layout(**upd), use_container_width=True)

    with c2:
        st.markdown("**Histograma de estabilidad**")
        fig3 = px.histogram(df_s, x="delta_ms", nbins=30, color_discrete_sequence=[GREEN])
        fig3.add_vline(x=0, line_dash="dash", line_color="#fff", opacity=0.4)
        st.plotly_chart(fig3.update_layout(**upd), use_container_width=True)

    st.markdown("**Tendencia temporal de desfase**")
    fig4 = px.line(df_s, x=x_col, y="delta_ms", color_discrete_sequence=[GREEN])
    fig4.add_hline(y=71.3, line_dash="dot", line_color=RED,
                   annotation_text="Jitter máx. 71.3 ms", annotation_font_color=RED)
    fig4.add_hline(y=-71.3, line_dash="dot", line_color=RED)
    st.plotly_chart(fig4.update_layout(**upd), use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# TAB TRAZABILIDAD SQL
# ─────────────────────────────────────────────────────────────────────────────
def tab_trazabilidad():
    st.subheader("Trazabilidad (SQL)")
    df = get_db()

    if df.empty:
        st.info("Todavía no hay registros guardados.")
        return

    c_filter, _ = st.columns([1, 3])
    with c_filter:
        filter_mode = st.selectbox(
            "Ventana de registros",
            ["Todo", "Últimas 24h", "Últimos 7 días", "Últimos 30 días"],
        )

    if "fecha" in df.columns:
        fecha_dt = pd.to_datetime(df["fecha"], errors="coerce")
        now = datetime.now()
        min_ts: datetime | None = None
        if filter_mode == "Últimas 24h":
            min_ts = now - timedelta(hours=24)
        elif filter_mode == "Últimos 7 días":
            min_ts = now - timedelta(days=7)
        elif filter_mode == "Últimos 30 días":
            min_ts = now - timedelta(days=30)
        if min_ts is not None:
            df = df.loc[fecha_dt.notna() & (fecha_dt >= min_ts)].copy()
        else:
            df = df.loc[fecha_dt.notna()].copy()

    numeric_cols = [
        "eta_extraccion",
        "desfase_medio_ms",
        "jitter_ms",
        "packet_loss",
        "lat_media",
        "desfase_max_ms",
        "multicast_pct",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # KPIs
    eta_v  = df[df["eta_extraccion"]    != -1]["eta_extraccion"]
    def_v  = df[df["desfase_medio_ms"]  != -1]["desfase_medio_ms"]
    jit_v  = df[df["jitter_ms"]         != -1]["jitter_ms"]
    plr_v  = df[df["packet_loss"]       != -1]["packet_loss"]
    comp   = df[(df["lat_media"] != -1) & (df["eta_extraccion"] != -1)]

    k1,k2,k3,k4,k5 = st.columns(5)
    k1.metric("Registros totales",    len(df))
    k2.metric("Muestras completas",   len(comp))
    k3.metric("η promedio",           f"{eta_v.mean():.2f}%" if not eta_v.empty else "N/D")
    k4.metric("Desfase medio prom.",  f"{def_v.mean():.2f} ms" if not def_v.empty else "N/D")
    k5.metric("Jitter máx. registrado", f"{jit_v.max():.2f} ms" if not jit_v.empty else "N/D")

    upd = dict(**DARK, height=250, margin=dict(l=0,r=0,t=30,b=0))

    c1, c2, c3 = st.columns(3)

    with c1:
        st.markdown("**η extracción por muestra**")
        if not eta_v.empty:
            valid = df[df["eta_extraccion"] != -1]
            fig   = px.bar(valid, x="id_muestra", y="eta_extraccion",
                           color="fecha", color_discrete_sequence=[GREEN, BLUE, YELLOW])
            fig.add_hline(y=95, line_dash="dash", line_color=YELLOW,
                          annotation_text="Meta 95%", annotation_font_color=YELLOW)
            fig.add_hline(y=0.55, line_dash="dot", line_color=RED,
                          annotation_text="Línea base", annotation_font_color=RED)
            st.plotly_chart(fig.update_layout(**upd), use_container_width=True)

    with c2:
        st.markdown("**Latencia media por muestra**")
        valid = df[df["lat_media"] != -1]
        if not valid.empty:
            fig2 = px.line(valid, x="id_muestra", y="lat_media",
                           color="fecha", markers=True)
            st.plotly_chart(fig2.update_layout(**upd), use_container_width=True)

    with c3:
        st.markdown("**Desfase medio vs multicast**")
        valid = df[(df["desfase_medio_ms"] != -1) & (df["multicast_pct"] != -1)]
        if not valid.empty:
            fig3 = px.bar(valid, x="id_muestra", y="desfase_medio_ms",
                          color="multicast_pct",
                          color_continuous_scale=["green","yellow","red"])
            fig3.add_hline(y=71.3, line_dash="dot", line_color=RED)
            st.plotly_chart(fig3.update_layout(**upd), use_container_width=True)

    # Scatter latencia vs η — clave para prueba t
    st.markdown("**Correlación latencia vs η — evidencia para prueba t de Student**")
    if not comp.empty:
        size_col = None
        if "desfase_medio_ms" in comp.columns:
            comp = comp.copy()
            comp["desfase_medio_ms"] = pd.to_numeric(comp["desfase_medio_ms"], errors="coerce").fillna(0)
            size_col = "desfase_medio_ms"
        fig_t = px.scatter(
            comp,
            x="lat_media",
            y="eta_extraccion",
            size=size_col,
            color="fecha",
            trendline="ols" if _HAS_STATSMODELS else None,
            labels={"lat_media": "Latencia media (ms)", "eta_extraccion": "η (%)"},
            color_discrete_sequence=[GREEN, BLUE, YELLOW],
        )
        fig_t.add_hline(y=95, line_dash="dash", line_color=YELLOW,
                        annotation_text="Meta η 95%", annotation_font_color=YELLOW)
        dark(fig_t, 300)
        st.plotly_chart(fig_t, use_container_width=True)

    # Histograma de jitter — distribución para Shapiro-Wilk
    if not jit_v.empty:
        st.markdown("**Distribución de jitter — base para prueba de normalidad Shapiro-Wilk**")
        valid_j = df[df["jitter_ms"] != -1]
        fig_j   = px.histogram(valid_j, x="jitter_ms", nbins=20,
                               color_discrete_sequence=[GREEN],
                               labels={"jitter_ms": "Jitter (ms)"})
        fig_j.add_vline(x=jit_v.mean(), line_dash="dash", line_color=YELLOW,
                        annotation_text=f"Media {jit_v.mean():.1f} ms",
                        annotation_font_color=YELLOW)
        dark(fig_j, 240)
        st.plotly_chart(fig_j, use_container_width=True)

    # Tabla completa
    st.markdown("**Registro completo**")
    display = df.rename(columns={
        "fecha":"Fecha","id_muestra":"Muestra","lat_media":"Latencia (ms)",
        "jitter_ms":"Jitter (ms)","packet_loss":"PLR (%)","nodos_dinamicos":"Nodos din.",
        "score_ids":"Score IDS","eventos_fc":"FC","eventos_fe":"FE",
        "firmas_56d100":"Firmas 56D1","eventos_red":"Eventos red",
        "eventos_correlacionados":"Correlacionados","desfase_medio_ms":"Desfase medio",
        "desfase_max_ms":"Desfase máx.","multicast_pct":"Multicast %",
        "eta_extraccion":"η (%)","observacion_tecnica":"Observación",
    })
    st.dataframe(display, use_container_width=True, height=300)
    csv = display.to_csv(index=False).encode("utf-8")
    st.download_button("Descargar CSV", data=csv,
                       file_name=f"trazabilidad_fincadiag.csv", mime="text/csv")


# ─────────────────────────────────────────────────────────────────────────────
# TAB POR VISITA
# ─────────────────────────────────────────────────────────────────────────────
def tab_por_visita(label: str, path: Path):
    visits_df = load_visits(path, label)
    if visits_df.empty:
        st.info("No hay visitas para mostrar en este lote.")
        return

    nombres = visits_df["visit_name"].tolist()
    sel     = st.selectbox("Seleccionar visita", nombres,
                           format_func=lambda x: format_visit_label(x, prefix="Visita "))
    row     = visits_df[visits_df["visit_name"] == sel].iloc[0]

    eta   = num(row.get("avg_eta_extraccion", 0))
    mc_v  = num(row.get("avg_multicast_pct", 0))
    def_v = num(row.get("avg_desfase_medio_ms", 0))
    alts  = int(row.get("total_alertas_altas", 0) or 0)
    crit  = int(row.get("total_alertas_criticas", 0) or 0)
    sess  = int(row.get("total_sessions", 0) or 0)
    pcaps = int(row.get("sessions_with_pcap", 0) or 0)
    ser   = int(row.get("sessions_with_serial", 0) or 0)
    collar= int(row.get("sessions_with_antenna_udp", 0) or 0)
    bc    = CAT_COLOR[classify(eta)]

    # Métricas principales
    m1, m2, m3, m4, m5, m6 = st.columns(6)
    m1.metric("η extracción",    f"{eta:.1f}%",   "vs meta 95%" )
    m2.metric("Multicast",       f"{mc_v:.1f}%",  "umbral 15%"  )
    m3.metric("Desfase medio",   f"{def_v:.1f} ms","umbral 50 ms")
    m4.metric("Alertas altas",   alts)
    m5.metric("Alertas críticas",crit)
    m6.metric("Sesiones totales",sess)

    st.markdown("---")
    c1, c2 = st.columns(2)

    with c1:
        # Gauge de η de esta visita
        fig_g = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=eta,
            delta={"reference": 95, "suffix": "%",
                   "increasing": {"color": GREEN}, "decreasing": {"color": RED}},
            title={"text": f"η — {format_visit_label(sel, prefix='Visita ')}", "font":{"color":"#fff","size":12}},
            number={"suffix": "%", "font":{"color":"#fff","size":32}},
            gauge={
                "axis": {"range": [0,100], "tickcolor":"#8dae9d","tickfont":{"color":"#8dae9d"}},
                "bar": {"color": bc},
                "bgcolor": "#1a2b1a","bordercolor":"#1a2b1a",
                "steps": [
                    {"range":[0,30],"color":"#2d1010"},{"range":[30,60],"color":"#2d2010"},
                    {"range":[60,85],"color":"#2d2d10"},{"range":[85,100],"color":"#102d10"},
                ],
                "threshold":{"line":{"color":YELLOW,"width":3},"thickness":0.85,"value":95},
            },
        ))
        fig_g.update_layout(**DARK, height=280, margin=dict(l=20,r=20,t=50,b=10))
        st.plotly_chart(fig_g, use_container_width=True)

    with c2:
        # Composición de sesiones
        st.markdown("**Composición de sesiones**")
        df_comp = pd.DataFrame({
            "Tipo": ["PCAP", "Serial", "Collar/Antena", "Solo baseline"],
            "Sesiones": [
                pcaps, ser, collar,
                max(0, sess - max(pcaps, ser, collar))
            ]
        })
        fig_comp = px.bar(df_comp, x="Sesiones", y="Tipo", orientation="h",
                          color="Tipo",
                          color_discrete_sequence=[BLUE, GREEN, YELLOW, "#555"])
        fig_comp.update_layout(**DARK, height=280, margin=dict(l=0,r=0,t=10,b=0),
                               showlegend=False)
        st.plotly_chart(fig_comp, use_container_width=True)

    # Tabla de contexto
    st.markdown("**Detalle técnico de la visita**")
    detalle = pd.DataFrame({
        "Parámetro": [
            "η extracción", "Multicast %", "Desfase medio (ms)",
            "Alertas altas", "Alertas críticas",
            "Sesiones PCAP", "Sesiones Serial", "Sesiones Collar",
            "Clasificación de riesgo",
        ],
        "Valor": [
            f"{eta:.2f}%", f"{mc_v:.2f}%", f"{def_v:.2f} ms",
            alts, crit, pcaps, ser, collar,
            "Alto" if (crit>0 or eta<30) else "Elevado" if (alts>2 or eta<60) else "Guarded" if eta<85 else "Bajo",
        ],
        "Referencia TFG": [
            "Meta: 95% | Línea base: 0.55%", "Umbral: 15%", "Jitter máx.: 71.3 ms",
            "—", "—", "—", "—", "—", "IEC 62443",
        ],
    })
    st.dataframe(detalle, hide_index=True, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    st.sidebar.title("🐄 FincaDiag")

    resumen_path = PROCESSED_DIR / "global" / "resumen_arbol"
    if not resumen_path.exists():
        st.error(f"Carpeta no encontrada: {resumen_path}")
        st.info("Revisa que la carpeta 'data' esté en el nivel correcto del proyecto.")
        return

    runs = sorted(
        [
            (p.stem.replace("_summary", ""), p)
            for p in resumen_path.rglob("*_summary.json")
            if "old" not in {part.lower() for part in p.relative_to(resumen_path).parts}
        ],
        reverse=True,
    )
    if not runs:
        st.warning("No se encontraron lotes con el filtro actual.")
        return

    sel_label = st.sidebar.selectbox("Lote", [r[0] for r in runs])
    sel_path  = dict(runs)[sel_label]

    with open(sel_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    # Info de lote en sidebar
    st.sidebar.markdown("---")
    total_vis = int(summary.get("total_visits", 0) or 0)
    total_ses = int(summary.get("total_sessions", 0) or 0)
    altas_s   = int(summary.get("total_alertas_altas", 0) or 0)
    crit_s    = int(summary.get("total_alertas_criticas", 0) or 0)

    st.sidebar.markdown("**Resumen del lote**")
    st.sidebar.markdown(f"🗂 Visitas: **{total_vis}**")
    st.sidebar.markdown(f"📋 Sesiones: **{total_ses}**")
    st.sidebar.markdown(f"Alertas altas: **{altas_s}**")
    if crit_s > 0:
        st.sidebar.markdown(f"🔴 Alertas críticas: **{crit_s}**")

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Referencias TFG**")
    st.sidebar.markdown(f"η línea base: **0.55%**")
    st.sidebar.markdown(f"η meta: **95%**")
    st.sidebar.markdown(f"Jitter máx.: **71.3 ms**")
    st.sidebar.markdown(f"Ruido UDP: **43.29 Hz**")

    st.sidebar.markdown("---")
    st.sidebar.caption("FincaDiag")

    tab_gen, tab_vis, tab_sync, tab_trace = st.tabs([
        "📊 Panel General",
        "🔍 Por visita",
        "🎯 Sincronía Edge",
        "📚 Trazabilidad SQL",
    ])

    with tab_gen:
        tab_general(sel_label, sel_path, summary)
    with tab_vis:
        tab_por_visita(sel_label, sel_path)
    with tab_sync:
        tab_sincronia(sel_label, sel_path)
    with tab_trace:
        tab_trazabilidad()


if __name__ == "__main__":
    main()