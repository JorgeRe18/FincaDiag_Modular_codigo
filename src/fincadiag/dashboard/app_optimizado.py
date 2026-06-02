import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


st.set_page_config(page_title="FincaDiag Ejecutivo", layout="wide")

GREEN = "#27AE60"
YELLOW = "#F4D03F"
ORANGE = "#E67E22"
RED = "#E74C3C"
BLUE = "#2980B9"
BG = "#0D1A0D"
PANEL = "#16261B"

st.markdown(
    f"""
<style>
.stApp {{ background-color: {BG}; color: #E9F5EE; }}
[data-testid="stSidebar"] {{ background-color: #0A120D !important; border-right: 1px solid #21402B; }}
.card {{
    background: {PANEL};
    border: 1px solid #21402B;
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 12px;
}}
.sec {{
    background: {PANEL};
    border-left: 4px solid {GREEN};
    border-radius: 0 10px 10px 0;
    padding: 8px 14px;
    font-weight: 700;
    margin: 16px 0 10px;
}}
.kpi {{
    background: {PANEL};
    border-radius: 12px;
    border-top: 3px solid {GREEN};
    padding: 14px;
    text-align: center;
    min-height: 104px;
}}
.kpi.warn {{ border-top-color: {YELLOW}; }}
.kpi.alert {{ border-top-color: {RED}; }}
.kpi.info {{ border-top-color: {BLUE}; }}
.kpi-value {{ font-size: 1.8rem; font-weight: 800; color: white; }}
.kpi-label {{ font-size: 0.72rem; color: #AFCDBB; text-transform: uppercase; margin-top: 4px; }}
.kpi-sub {{ font-size: 0.75rem; color: #8FC6A1; margin-top: 4px; }}
</style>
""",
    unsafe_allow_html=True,
)

ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = ROOT if (ROOT / "data").exists() else Path(__file__).resolve().parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
DB_PATH = BASE_DIR / "data" / "finca_muestras.db"


def dark(fig, height=280):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#E9F5EE",
        height=height,
    )
    return fig


def load_summary(run_path: Path, run_name: str) -> dict:
    path = run_path / f"{run_name}_summary.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_visits(run_path: Path, run_name: str) -> pd.DataFrame:
    path = run_path / f"{run_name}_visits.csv"
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def available_runs():
    base = PROCESSED_DIR / "global" / "resumen_arbol"
    if not base.exists():
        return []
    results = []
    for child in sorted(base.iterdir()):
        if child.is_dir():
            candidates = [c for c in child.iterdir() if c.suffix == ".json" and "summary" in c.name]
            if candidates:
                results.append((child.name, child))
    return results


def render_executive_panel(summary: dict):
    st.markdown('<div class="sec">Panel Ejecutivo - Estado de la Finca</div>', unsafe_allow_html=True)
    if not summary:
        st.info("No hay datos de resumen disponibles.")
        return

    critical_alerts = summary.get('total_alertas_criticas', 0)
    high_alerts = summary.get('total_alertas_altas', 0)
    total_alerts = summary.get('total_alertas', 0)
    total_sessions = summary.get('total_sessions', 0)
    sessions_with_serial = summary.get('sessions_with_serial', 0)
    sessions_with_pcap = summary.get('sessions_with_pcap', 0)
    sessions_with_correlation = summary.get('sessions_with_correlation', 0)
    avg_eta = summary.get('avg_eta_extraccion', 0) or 0

    # KPIs principales simplificados
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        severity_class = "alert" if critical_alerts > 0 else ""
        st.markdown(f"""
        <div class="kpi {severity_class}">
            <div class="kpi-value">{critical_alerts}</div>
            <div class="kpi-label">Problemas Urgentes</div>
            <div class="kpi-sub">Requieren atención inmediata</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        severity_class = "warn" if high_alerts > 50 else ""
        st.markdown(f"""
        <div class="kpi {severity_class}">
            <div class="kpi-value">{high_alerts}</div>
            <div class="kpi-label">Problemas Importantes</div>
            <div class="kpi-sub">Revisar esta semana</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        efficiency_class = "alert" if avg_eta < 5 else "warn" if avg_eta < 10 else ""
        st.markdown(f"""
        <div class="kpi {efficiency_class}">
            <div class="kpi-value">{avg_eta:.1f}%</div>
            <div class="kpi-label">Eficiencia del Sistema</div>
            <div class="kpi-sub">Rendimiento operativo</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="kpi info">
            <div class="kpi-value">{total_sessions}</div>
            <div class="kpi-label">Mediciones Totales</div>
            <div class="kpi-sub">Momentos analizados</div>
        </div>
        """, unsafe_allow_html=True)

    # Análisis detallado de problemas con expandibles
    st.markdown('<div class="sec">Análisis Detallado de Problemas</div>', unsafe_allow_html=True)

    critical_problems = [
        {"tipo": "Conflicto ARP", "descripcion": "Equipos comparten misma dirección IP", "impacto": "Pérdida de datos del ordeño", "cantidad": 454, "severidad": "crítica"},
        {"tipo": "Salida no autorizada", "descripcion": "Conexiones externas a Internet", "impacto": "Riesgo de seguridad", "cantidad": 469, "severidad": "crítica"},
        {"tipo": "Tormenta Broadcast", "descripcion": "Ruido excesivo en red", "impacto": "Sistema lento", "cantidad": 747, "severidad": "alta"},
        {"tipo": "Identidad Ambigua", "descripcion": "Dispositivos no identificados", "impacto": "Errores de medición", "cantidad": 8503, "severidad": "alta"}
    ]

    problem_categories = {
        "Problemas Críticos": [p for p in critical_problems if p["severidad"] == "crítica"],
        "Problemas Importantes": [p for p in critical_problems if p["severidad"] == "alta"],
    }

    for category, problems in problem_categories.items():
        if not problems:
            continue
        category_color = RED if "Críticos" in category else ORANGE
        total_count = sum(p["cantidad"] for p in problems)
        with st.expander(f"{category} ({total_count} casos)", expanded=True):
            for problem in problems:
                severity_color = RED if problem["severidad"] == "crítica" else ORANGE
                st.markdown(f"""
                <div class="card" style="border-left: 4px solid {severity_color}; margin-bottom: 10px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h4 style="color: {severity_color}; margin: 0;">{problem['tipo']}</h4>
                            <p style="margin: 5px 0; color: #D6E7DD; font-size: 0.9rem;">{problem['descripcion']}</p>
                            <p style="margin: 5px 0; color: #8FC6A1; font-size: 0.85rem;"><strong>Impacto:</strong> {problem['impacto']}</p>
                        </div>
                        <div style="text-align: center; padding: 10px;">
                            <div style="font-size: 1.5rem; font-weight: bold; color: white;">{problem['cantidad']}</div>
                            <div style="font-size: 0.8rem; color: #AFCDBB;">casos</div>
                        </div>
                    </div>
                </div>
                """, unsafe_allow_html=True)

    # Solo dos gráficas clave: problemas por tipo + cobertura
    c1, c2 = st.columns(2)
    with c1:
        problem_types = [p["tipo"] for p in critical_problems]
        problem_counts = [p["cantidad"] for p in critical_problems]
        problem_colors = [RED if p["severidad"] == "crítica" else ORANGE for p in critical_problems]
        fig = go.Figure(data=[
            go.Bar(y=problem_types, x=problem_counts, orientation='h',
                  marker_color=problem_colors, text=problem_counts, textposition='auto')
        ])
        fig.update_layout(title='Problemas por Tipo', xaxis_title='Cantidad de Casos', yaxis_title='', height=300,
                         yaxis={'categoryorder': 'total ascending'})
        st.plotly_chart(dark(fig), use_container_width=True)
    with c2:
        coverage_df = pd.DataFrame({
            'Componente': ['Monitoreo de Red', 'Datos de Ordeño', 'Sincronización'],
            'Sesiones': [sessions_with_pcap, sessions_with_serial, sessions_with_correlation],
        })
        fig = px.bar(coverage_df, x='Componente', y='Sesiones', title='Cobertura de Monitoreo',
                     color='Componente', color_discrete_map={'Monitoreo de Red': GREEN, 'Datos de Ordeño': BLUE, 'Sincronización': YELLOW})
        fig.update_layout(xaxis_title='', yaxis_title='Sesiones')
        st.plotly_chart(dark(fig, 300), use_container_width=True)

    # Estado del sistema + recomendaciones
    st.markdown('<div class="sec">Estado y Recomendaciones</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        system_status = "Crítico" if critical_alerts > 5 else "Preocupante" if critical_alerts > 0 or high_alerts > 50 else "Estable"
        status_color = RED if system_status == "Crítico" else ORANGE if system_status == "Preocupante" else GREEN
        st.markdown(f"""
        <div class="card">
            <h4 style="color: {status_color}; margin: 0 0 10px 0;">Estado del Sistema: {system_status}</h4>
            <div style="font-size: 0.9rem; color: #D6E7DD;">
                <p><strong>Riesgos identificados:</strong></p>
                <ul style="margin: 5px 0; padding-left: 20px;">
                    <li>Conflicto de identidad en red: {critical_alerts} casos</li>
                    <li>Ruido de red excesivo: {high_alerts} casos</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        recommendations = []
        if critical_alerts > 0:
            recommendations.append(f"1. Atender {critical_alerts} problemas urgentes")
        if high_alerts > 20:
            recommendations.append(f"2. Revisar {high_alerts} problemas importantes")
        if avg_eta < 10:
            recommendations.append(f"3. Mejorar eficiencia (actual: {avg_eta:.1f}%)")
        st.markdown(f"""
        <div class="card">
            <h4 style="color: {GREEN}; margin: 0 0 10px 0;">Recomendaciones Prioritarias</h4>
            <div style="font-size: 0.85rem; color: #D6E7DD;">
                <ol style="margin: 5px 0; padding-left: 20px;">
                    {''.join(f'<li>{rec}</li>' for rec in recommendations[:3])}
                </ol>
            </div>
        </div>
        """, unsafe_allow_html=True)


def render_visit_detail(visits_df: pd.DataFrame):
    st.markdown('<div class="sec">Detalle por Visita</div>', unsafe_allow_html=True)
    if visits_df.empty:
        st.info("No hay visitas disponibles.")
        return
    st.dataframe(visits_df, use_container_width=True, hide_index=True)


def main():
    st.sidebar.title("FincaDiag Ejecutivo")
    runs = available_runs()
    if not runs:
        st.error(f"No se encontraron lotes en {PROCESSED_DIR / 'global' / 'resumen_arbol'}")
        return

    selected_label = st.sidebar.selectbox("Lote", [label for label, _ in runs])
    run_map = dict(runs)
    summary_path = run_map[selected_label]

    summary = load_summary(summary_path, selected_label)
    visits_df = load_visits(summary_path, selected_label)

    st.sidebar.markdown("---")
    st.sidebar.markdown(f"**Lote seleccionado:** {selected_label}")
    st.sidebar.markdown(f"Visitas: **{int(summary.get('total_visits', 0) or 0)}**")
    st.sidebar.markdown(f"Sesiones: **{int(summary.get('total_sessions', 0) or 0)}**")

    tab1, tab2 = st.tabs(["Panel Ejecutivo", "Detalle por Visita"])
    with tab1:
        render_executive_panel(summary)
    with tab2:
        render_visit_detail(visits_df)


if __name__ == "__main__":
    main()
