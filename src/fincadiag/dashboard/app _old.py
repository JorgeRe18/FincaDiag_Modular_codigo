import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
REPORTS_DIR = PROJECT_ROOT / "reports"
DOCS_DIR = PROJECT_ROOT / "docs"


def load_json(path: Path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return pd.DataFrame()
    return pd.read_csv(path)


def resolve_text_report(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else "Reporte no disponible."


def format_metric(value, decimals: int = 2) -> str:
    if value in ("", None) or pd.isna(value):
        return "N/D"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return f"{number:.{decimals}f}"


def build_count_df(sample_type_counts: dict) -> pd.DataFrame:
    ordered = [
        "SERIAL + PCAP",
        "Antena + PCAP",
        "PCAP + ETL",
        "PCAP solo",
        "Baseline",
        "Otros",
    ]
    rows = [{"tipo": key, "cantidad": int(sample_type_counts.get(key, 0) or 0)} for key in ordered]
    return pd.DataFrame(rows)


def list_global_runs() -> list[tuple[str, Path]]:
    root = PROCESSED_DIR / "global" / "resumen_arbol"
    if not root.exists():
        return []
    return sorted((path.stem.replace("_summary", ""), path) for path in root.rglob("*_summary.json"))


def list_visits() -> list[tuple[str, Path]]:
    root = PROCESSED_DIR / "visits"
    if not root.exists():
        return []
    return sorted((path.stem.replace("_summary", ""), path) for path in root.glob("*/resumen/*_summary.json"))


def resolve_session_report_path(visit_name: str, sample_name: str, suffix: str) -> Path | None:
    candidate = REPORTS_DIR / "visits" / visit_name / "por_hora" / f"{sample_name}_{suffix}"
    return candidate if candidate.exists() else None


def build_profiles_df(obj1_profiles: dict) -> pd.DataFrame:
    profiles = obj1_profiles.get("profiles", [])
    if not profiles:
        return pd.DataFrame()
    df = pd.DataFrame(profiles)
    rename_map = {
        "label": "Fase",
        "start": "Inicio",
        "end": "Fin",
        "visit_count": "Visitas",
        "session_count": "Sesiones",
        "baseline_sessions": "Baseline",
        "serial_sessions": "Serial",
        "collar_sessions": "Collar",
        "parsed_pcap_sessions": "PCAP parseado",
        "field_validation_sessions": "Campo",
        "avg_latency_baseline_ms": "Latencia",
        "avg_jitter_baseline_ms": "Jitter",
        "avg_heartbeat_coverage_pct": "Heartbeat",
        "avg_eta_direct_pct": "Eta",
        "avg_multicast_pct": "Multicast %",
        "avg_multicast_rate_hz": "Multicast Hz",
        "recommended_for": "Uso recomendado",
    }
    return df.rename(columns=rename_map)


def build_readiness_df(readiness: dict) -> pd.DataFrame:
    checks = readiness.get("checks", {})
    if not checks:
        return pd.DataFrame()
    labels = {
        "baseline_red_definido": "Baseline de red",
        "firmas_seriales_disponibles": "Firmas seriales",
        "dominio_collar_observable": "Dominio collar",
        "contraste_campo_disponible": "Contraste campo",
        "eta_directa_consolidada": "Eta directa",
        "pcap_parseado_disponible": "PCAP parseado",
        "linea_base_inicial_defendible": "Linea base inicial",
    }
    rows = [{"Chequeo": labels.get(key, key), "Estado": "Si" if value else "No"} for key, value in checks.items()]
    return pd.DataFrame(rows)


def render_obj1_view(selected_label: str, selected_path: Path):
    summary = load_json(selected_path)
    profiles = load_json(selected_path.with_name(f"{selected_label}_obj1_profiles.json"))
    readiness = load_json(selected_path.with_name(f"{selected_label}_gateway_readiness.json"))
    recommendation = profiles.get("cap1_cap2_recommendation", {})

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Latencia inicial", f"{format_metric(recommendation.get('use_initial_latency_baseline_ms'))} ms")
    c2.metric("Jitter inicial", f"{format_metric(recommendation.get('use_initial_jitter_baseline_ms'))} ms")
    c3.metric("Eta inicial defendible", "Si" if recommendation.get("initial_eta_is_defendable") else "No")
    c4.metric("Etapa gateway", readiness.get("stage", "N/D"))

    left, right = st.columns([2, 1])
    with left:
        st.markdown("**Perfiles por fase**")
        profiles_df = build_profiles_df(profiles)
        if not profiles_df.empty:
            st.dataframe(profiles_df, use_container_width=True, height=280)
        else:
            st.info("No hay perfiles por fase disponibles.")
    with right:
        st.markdown("**Readiness del gateway**")
        readiness_df = build_readiness_df(readiness)
        if not readiness_df.empty:
            st.dataframe(readiness_df, use_container_width=True, height=280)
        else:
            st.info("No hay chequeos de readiness.")

    if not profiles_df.empty:
        fig = px.bar(
            profiles_df,
            x="Fase",
            y="Latencia",
            color="Fase",
            title="Latencia baseline promedio por fase",
        )
        fig.update_layout(showlegend=False, xaxis_tickangle=-20)
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("**Texto de apoyo para Obj. 1**")
    obj1_profiles_report = REPORTS_DIR / "global" / "resumen_arbol" / selected_label / f"{selected_label}_obj1_profiles.txt"
    st.text_area("Perfiles Obj. 1", resolve_text_report(obj1_profiles_report), height=240)


def render_global_view(view_mode: str, selected_label: str, selected_path: Path):
    summary = load_json(selected_path)
    sample_type_counts = summary.get("sample_type_counts", {})
    visits_csv = selected_path.with_name(f"{selected_label}_visits.csv")
    visits_df = load_csv(visits_csv)
    report_suffix = "summary.txt" if view_mode == "Vista tecnica" else "summary_humano.txt"
    report_path = REPORTS_DIR / "global" / "resumen_arbol" / selected_label / f"{selected_label}_{report_suffix}"

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Visitas", int(summary.get("total_visits", 0) or 0))
    c2.metric("Sesiones", int(summary.get("total_sessions", 0) or 0))
    c3.metric("PCAP", int(summary.get("sessions_with_pcap", 0) or 0))
    c4.metric("Serial", int(summary.get("sessions_with_serial", 0) or 0))
    c5.metric("Collar", int(summary.get("sessions_with_antenna_udp", 0) or 0))
    c6.metric("Altas", int(summary.get("total_alertas_altas", 0) or 0))

    left, right = st.columns(2)
    with left:
        st.markdown("**Topologia de muestra**")
        df_types = build_count_df(sample_type_counts)
        fig = px.bar(df_types, x="tipo", y="cantidad", color="tipo")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Cantidad")
        st.plotly_chart(fig, use_container_width=True)

    with right:
        st.markdown("**Cobertura por visita**")
        if not visits_df.empty:
            numeric_cols = ["sessions_with_pcap", "sessions_with_serial", "total_alertas_altas"]
            for col in numeric_cols:
                if col in visits_df.columns:
                    visits_df[col] = pd.to_numeric(visits_df[col], errors="coerce")
            fig = px.line(
                visits_df,
                x="visit_name",
                y=["sessions_with_pcap", "sessions_with_serial"],
                labels={"visit_name": "Visita", "value": "Sesiones", "variable": "Cobertura"},
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay tabla consolidada de visitas.")

    if not visits_df.empty:
        display_df = visits_df.rename(
            columns={
                "visit_name": "Visita",
                "total_sessions": "Sesiones",
                "sessions_with_baseline": "Con baseline",
                "sessions_with_serial": "Con serial",
                "sessions_with_antenna_udp": "Con collar",
                "sessions_with_etl": "Con ETL",
                "sessions_with_pcap": "Con PCAP",
                "sessions_with_correlation": "Con correlacion",
                "total_alertas_criticas": "Criticas",
                "total_alertas_altas": "Altas",
                "avg_lat_media": "Latencia media",
                "avg_eta_extraccion": "Eta",
                "avg_desfase_medio_ms": "Desfase medio",
                "avg_multicast_pct": "Multicast",
            }
        )
        st.markdown("**Resumen por visita**")
        st.dataframe(display_df, use_container_width=True, height=320)

    heading = "**Resumen global tecnico**" if view_mode == "Vista tecnica" else "**Resumen global claro**"
    st.markdown(heading)
    st.text_area("Reporte global", resolve_text_report(report_path), height=320)


def render_visit_view(view_mode: str):
    visits = list_visits()
    if not visits:
        st.info("Aun no hay visitas procesadas.")
        return

    labels = [label for label, _ in visits]
    default_index = labels.index("Visita_09_04_2026") if "Visita_09_04_2026" in labels else len(labels) - 1
    selected_visit = st.selectbox("Visita", labels, index=max(default_index, 0))
    selected_path = dict(visits)[selected_visit]

    summary = load_json(selected_path)
    sample_type_counts = summary.get("sample_type_counts", {})
    sessions_csv = selected_path.with_name(f"{selected_visit}_sessions.csv")
    sessions_df = load_csv(sessions_csv)
    report_suffix = "summary.txt" if view_mode == "Vista tecnica" else "summary_humano.txt"
    report_path = REPORTS_DIR / "visits" / selected_visit / "resumen" / f"{selected_visit}_{report_suffix}"

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Sesiones", int(summary.get("total_sessions", 0) or 0))
    c2.metric("Baseline", int(summary.get("sessions_baseline_only", 0) or 0))
    c3.metric("Serial", int(summary.get("sessions_with_serial", 0) or 0))
    c4.metric("Collar", int(summary.get("sessions_with_antenna_udp", 0) or 0))
    c5.metric("PCAP", int(summary.get("sessions_with_pcap", 0) or 0))
    c6.metric("Altas", int(summary.get("total_alertas_altas", 0) or 0))

    left, right = st.columns(2)
    with left:
        st.markdown("**Distribucion interna**")
        df_types = build_count_df(sample_type_counts)
        fig = px.bar(df_types, x="tipo", y="cantidad", color="tipo")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Cantidad")
        st.plotly_chart(fig, use_container_width=True)
    with right:
        st.markdown("**Alertas por sesion**")
        if not sessions_df.empty:
            for col in ["alertas_criticas", "alertas_altas", "alertas_totales"]:
                if col in sessions_df.columns:
                    sessions_df[col] = pd.to_numeric(sessions_df[col], errors="coerce")
            fig = px.bar(
                sessions_df.sort_values(by="alertas_totales", ascending=False).head(20),
                x="sample_id",
                y="alertas_totales",
                color="operation_mode" if "operation_mode" in sessions_df.columns else None,
                labels={"sample_id": "Sesion", "alertas_totales": "Alertas"},
            )
            fig.update_layout(xaxis_tickangle=-45)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No hay sesiones para esta visita.")

    if not sessions_df.empty:
        mode_filter = st.selectbox("Filtrar por modo", ["todos", "baseline", "telemetria_collar", "ordeno_completo"])
        filtered_df = sessions_df if mode_filter == "todos" else sessions_df[sessions_df["operation_mode"] == mode_filter]
        display_df = filtered_df.rename(
            columns={
                "sample_id": "Sesion",
                "block_label": "Bloque",
                "operation_mode": "Modo",
                "obj1_role": "Rol Obj1",
                "has_baseline": "Baseline",
                "has_serial": "Serial",
                "has_antenna_udp": "Antena txt",
                "has_etl": "ETL",
                "has_pcap": "PCAP",
                "pcap_parsed": "PCAP parseado",
                "lat_media": "Latencia",
                "jitter_ms": "Jitter",
                "eventos_vaca": "Vacas",
                "eventos_sin_rfid": "Sin tag",
                "muestras_flujo": "Flujo E4",
                "multicast_pct": "Multicast %",
                "packet_rate_hz": "Pkt Hz",
                "multicast_rate_hz": "Mcast Hz",
                "validacion_campo": "Campo",
            }
        )
        st.markdown("**Sesiones de la visita**")
        st.dataframe(display_df, use_container_width=True, height=320)

        with st.expander("Detalle opcional por sesion"):
            sample_names = filtered_df["sample_id"].dropna().astype(str).tolist()
            if sample_names:
                selected_sample = st.selectbox("Sesion puntual", sample_names)
                tech_path = resolve_session_report_path(selected_visit, selected_sample, "technical_report.txt")
                human_path = resolve_session_report_path(selected_visit, selected_sample, "human_report.txt")
                report_to_show = tech_path if view_mode == "Vista tecnica" else human_path
                st.text_area("Reporte de sesion", resolve_text_report(report_to_show) if report_to_show else "Reporte no disponible.", height=260)

    heading = "**Resumen de visita tecnico**" if view_mode == "Vista tecnica" else "**Resumen de visita claro**"
    st.markdown(heading)
    st.text_area("Reporte de visita", resolve_text_report(report_path), height=260)


def render_gateway_view(selected_label: str, selected_path: Path):
    readiness = load_json(selected_path.with_name(f"{selected_label}_gateway_readiness.json"))
    stage = readiness.get("stage", "N/D")
    next_actions = readiness.get("next_actions", [])
    docs_path = DOCS_DIR / "diagrama_gateway_perimetral.md"

    c1, c2 = st.columns(2)
    c1.metric("Etapa actual", stage)
    c2.metric("Acciones siguientes", len(next_actions))

    checks_df = build_readiness_df(readiness)
    if not checks_df.empty:
        st.markdown("**Checklist de readiness**")
        st.dataframe(checks_df, use_container_width=True, height=260)

    if next_actions:
        st.markdown("**Siguiente paso recomendado**")
        for item in next_actions:
            st.write(f"- {item}")

    st.markdown("**Diagrama / esqueleto del gateway**")
    st.text_area("Documento gateway", resolve_text_report(docs_path), height=320)


st.set_page_config(page_title="FincaDiag | Panel integral", layout="wide")
st.title("FincaDiag | Panel integral")
st.caption("Panel para Objetivo 1, verificacion de fases y preparacion del gateway perimetral.")

global_runs = list_global_runs()
if not global_runs:
    st.info("Aun no hay lotes globales procesados.")
    st.stop()

labels = [label for label, _ in global_runs]
default_index = labels.index("Prueba_Finca") if "Prueba_Finca" in labels else 0
selected_label = st.selectbox("Lote global", labels, index=default_index)
selected_path = dict(global_runs)[selected_label]
view_mode = st.radio("Modo de visualizacion", ["Vista tecnica", "Vista en lenguaje claro"], horizontal=True)

tab_obj1, tab_general, tab_visitas, tab_gateway = st.tabs(["Obj.1", "General", "Por visita", "Gateway"])

with tab_obj1:
    render_obj1_view(selected_label, selected_path)

with tab_general:
    render_global_view(view_mode, selected_label, selected_path)

with tab_visitas:
    render_visit_view(view_mode)

with tab_gateway:
    render_gateway_view(selected_label, selected_path)
