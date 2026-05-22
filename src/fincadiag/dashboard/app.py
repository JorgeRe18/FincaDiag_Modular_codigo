import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

_DASHBOARD_CODENAME = "Aletheia Board"

st.set_page_config(page_title=_DASHBOARD_CODENAME, layout="wide")

GREEN = "#27AE60"
YELLOW = "#F4D03F"
ORANGE = "#E67E22"
RED = "#E74C3C"
BLUE = "#2980B9"
BG = "#0D1A0D"
PANEL = "#16261B"

ETA_STRONG_THRESHOLD = 85.0
ETA_PARTIAL_THRESHOLD = 60.0
MULTICAST_ATTENTION_THRESHOLD = 15.0
TIMING_ATTENTION_THRESHOLD_MS = 50.0

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
.grid-cell {{
    display: inline-block;
    padding: 5px 10px;
    border-radius: 7px;
    font-size: 0.72rem;
    font-weight: 700;
    margin: 3px;
    min-width: 74px;
    text-align: center;
}}
.cell-green {{ background: {GREEN}; color: white; }}
.cell-yellow {{ background: {YELLOW}; color: #1A1A1A; }}
.cell-orange {{ background: {ORANGE}; color: white; }}
.cell-red {{ background: {RED}; color: white; }}
.leg-item {{ display: flex; align-items: center; gap: 8px; font-size: 0.80rem; color: #D6E7DD; margin-bottom: 6px; }}
.leg-dot {{ width: 11px; height: 11px; border-radius: 50%; flex-shrink: 0; }}
</style>
""",
    unsafe_allow_html=True,
)

ROOT = Path(__file__).resolve().parents[3]
BASE_DIR = ROOT if (ROOT / "data").exists() else Path(__file__).resolve().parent
PROCESSED_DIR = BASE_DIR / "data" / "processed"
DB_PATH = BASE_DIR / "data" / "finca_muestras.db"


def num(value) -> float:
    try:
        parsed = float(value)
        return 0.0 if pd.isna(parsed) else parsed
    except Exception:
        return 0.0


def dark(fig, height=280):
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color="#E9F5EE",
        height=height,
        margin=dict(l=0, r=0, t=40, b=0),
    )
    return fig


def classify_eta(eta: float) -> str:
    if eta >= ETA_STRONG_THRESHOLD:
        return "Fuerte"
    if eta >= ETA_PARTIAL_THRESHOLD:
        return "Parcial"
    if eta > 0:
        return "Débil"
    return "Sin cobertura"


def eta_color(eta: float) -> str:
    if eta >= ETA_STRONG_THRESHOLD:
        return GREEN
    if eta >= ETA_PARTIAL_THRESHOLD:
        return YELLOW
    if eta > 0:
        return ORANGE
    return RED


def format_visit_label(value: str, prefix: str = "V") -> str:
    raw = str(value or "?").replace("Visita_", "")
    if prefix == "V":
        return f"V{raw}"
    if prefix:
        return f"{prefix}{raw}"
    return raw


def visit_date_from_name(value: str) -> str:
    raw = str(value or "").replace("Visita_", "")
    parts = raw.split("_")
    if len(parts) >= 3:
        return f"{parts[0]}/{parts[1]}/{parts[2]}"
    return ""


def get_db() -> pd.DataFrame:
    if not DB_PATH.exists():
        return pd.DataFrame()
    try:
        with sqlite3.connect(DB_PATH) as conn:
            found = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='registro_muestras'"
            ).fetchone()
            if not found:
                return pd.DataFrame()
            return pd.read_sql_query(
                "SELECT * FROM registro_muestras ORDER BY fecha DESC, id_muestra ASC",
                conn,
            )
    except Exception:
        return pd.DataFrame()


def load_visits(run_path: Path, label: str) -> pd.DataFrame:
    csv_path = run_path.with_name(f"{label}_visits.csv")
    if not csv_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(csv_path)
    if "visit_name" in df.columns:
        visit_dt = pd.to_datetime(
            df["visit_name"].astype(str).str.replace("Visita_", "", regex=False),
            format="%d_%m_%Y",
            errors="coerce",
        )
        df = (
            df.assign(_visit_dt=visit_dt)
            .sort_values(["_visit_dt", "visit_name"], na_position="last")
            .drop(columns="_visit_dt")
            .reset_index(drop=True)
        )
    return df


@st.cache_data(show_spinner=False)
def load_parsing_data(summary_path: Path, label: str) -> pd.DataFrame:
    """Carga datos de calidad de parsing de todas las sesiones del lote.

    Retorna DataFrame con métricas de parsing por sesión:
    - sample_name: nombre de la sesión
    - visit_name: nombre de la visita
    - serial_available: si hay serial parseado
    - serial_malformed_lines: líneas malformadas del serial
    - serial_unparsed_lines: líneas no parseadas del serial
    - serial_cow_event_count: eventos de vaca reconstruidos
    - serial_cow_success_count: eventos exitosos
    - pcap_available: si hay PCAP parseado
    - pcap_parse_error: error de parseo de PCAP
    - antenna_udp_available: si hay antena UDP parseado
    - antenna_udp_malformed_lines: líneas malformadas de antena
    - field_validation_available: si hay validación de campo
    - parser_event_count: eventos de parser vs campo
    - parser_coverage_rate_vs_field: cobertura del parser vs campo
    - parser_missing_count_vs_field: eventos faltantes
    - parser_excess_count_vs_field: eventos excesivos
    - parser_event_delta_vs_field: delta parser vs campo
    """
    rows = []
    visits_dir = BASE_DIR / "data" / "processed" / "visits"
    if not visits_dir.exists():
        return pd.DataFrame()

    for visit_dir in visits_dir.iterdir():
        if not visit_dir.is_dir() or not visit_dir.name.startswith("Visita_"):
            continue
        visit_name = visit_dir.name
        sesiones_dir = visit_dir / "sesiones"
        if not sesiones_dir.exists():
            continue

        for session_dir in sesiones_dir.iterdir():
            if not session_dir.is_dir():
                continue
            sample_name = session_dir.name

            row = {
                "sample_name": sample_name,
                "visit_name": visit_name,
                "serial_available": False,
                "serial_malformed_lines": 0,
                "serial_unparsed_lines": 0,
                "serial_cow_event_count": 0,
                "serial_cow_success_count": 0,
                "pcap_available": False,
                "pcap_parse_error": "",
                "antenna_udp_available": False,
                "antenna_udp_malformed_lines": 0,
                "field_validation_available": False,
                "parser_event_count": 0,
                "parser_coverage_rate_vs_field": 0.0,
                "parser_missing_count_vs_field": 0,
                "parser_excess_count_vs_field": 0,
                "parser_event_delta_vs_field": 0,
            }

            # Cargar serial_summary.json
            serial_path = session_dir / "serial_summary.json"
            if serial_path.exists():
                try:
                    serial_data = json.loads(serial_path.read_text(encoding="utf-8"))
                    row["serial_available"] = serial_data.get("available", False)
                    row["serial_malformed_lines"] = serial_data.get("malformed_lines", 0)
                    row["serial_unparsed_lines"] = len(serial_data.get("unparsed_lines", []))
                    row["serial_cow_event_count"] = serial_data.get("cow_event_count", 0)
                    row["serial_cow_success_count"] = serial_data.get("cow_success_count", 0)
                except Exception:
                    pass

            # Cargar pcap_summary.json
            pcap_path = session_dir / "pcap_summary.json"
            if pcap_path.exists():
                try:
                    pcap_data = json.loads(pcap_path.read_text(encoding="utf-8"))
                    row["pcap_available"] = pcap_data.get("available", False)
                    row["pcap_parse_error"] = pcap_data.get("parse_error", "")
                except Exception:
                    pass

            # Cargar antenna_udp_summary.json
            antenna_path = session_dir / "antenna_udp_summary.json"
            if antenna_path.exists():
                try:
                    antenna_data = json.loads(antenna_path.read_text(encoding="utf-8"))
                    row["antenna_udp_available"] = antenna_data.get("available", False)
                    row["antenna_udp_malformed_lines"] = antenna_data.get("malformed_lines", 0)
                except Exception:
                    pass

            # Cargar field_validation_summary.json
            field_path = session_dir / "field_validation_summary.json"
            if field_path.exists():
                try:
                    field_data = json.loads(field_path.read_text(encoding="utf-8"))
                    row["field_validation_available"] = field_data.get("available", False)
                    row["parser_event_count"] = field_data.get("parser_event_count", 0)
                    row["parser_coverage_rate_vs_field"] = field_data.get("parser_coverage_rate_vs_field", 0.0)
                    row["parser_missing_count_vs_field"] = field_data.get("parser_missing_count_vs_field", 0)
                    row["parser_excess_count_vs_field"] = field_data.get("parser_excess_count_vs_field", 0)
                    row["parser_event_delta_vs_field"] = field_data.get("parser_event_delta_vs_field", 0)
                except Exception:
                    pass

            rows.append(row)

    return pd.DataFrame(rows) if rows else pd.DataFrame()


@st.cache_data(show_spinner=False)
def load_visit_alerts(visit_name: str) -> pd.DataFrame:
    """Carga todas las alertas detalladas (alerts.json) de las sesiones de una visita.

    Usa la misma ruta canónica que el motor (cli.py:get_row_alerts_path):
    data/processed/visits/{visit_name}/sesiones/{sample_id}/alerts.json
    Retorna DataFrame con columnas: sample_name, alert_name, severity, layer,
    evidence, impact, recommendation, timestamp, src_ip, dst_ip, port, protocol.
    """
    rows = []
    sesiones = BASE_DIR / "data" / "processed" / "visits" / visit_name / "sesiones"
    if not sesiones.exists():
        return pd.DataFrame()
    for session_dir in sesiones.iterdir():
        if not session_dir.is_dir():
            continue
        alerts_path = session_dir / "alerts.json"
        if not alerts_path.exists():
            continue
        try:
            data = json.loads(alerts_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for alert in data.get("all", []):
            rows.append({
                "sample_name": session_dir.name,
                "alert_name": alert.get("alert_name", ""),
                "severity": alert.get("severity", ""),
                "layer": alert.get("layer", ""),
                "evidence": alert.get("evidence", ""),
                "impact": alert.get("impact", ""),
                "recommendation": alert.get("recommendation", ""),
                "timestamp": alert.get("timestamp", ""),
                "src_ip": alert.get("src_ip", ""),
                "dst_ip": alert.get("dst_ip", ""),
                "port": alert.get("port", ""),
                "protocol": alert.get("protocol", ""),
            })
    return pd.DataFrame(rows)


def load_corr(run_path: Path, label: str) -> pd.DataFrame:
    csv_path = run_path.with_name(f"{label}_correlacion_global.csv")
    if not csv_path.exists():
        return pd.DataFrame()
    return pd.read_csv(csv_path)


def available_runs() -> list[tuple[str, Path]]:
    root = PROCESSED_DIR / "global" / "resumen_arbol"
    if not root.exists():
        return []
    runs = []
    for path in root.rglob("*_summary.json"):
        rel_parts = {part.lower() for part in path.relative_to(root).parts}
        if "old" in rel_parts:
            continue
        runs.append((path.stem.replace("_summary", ""), path))
    return sorted(runs, reverse=True)


def risk_level(row: pd.Series) -> str:
    eta = num(row.get("avg_eta_extraccion", 0))
    alerts_high = int(row.get("total_alertas_altas", 0) or 0)
    alerts_crit = int(row.get("total_alertas_criticas", 0) or 0)
    multicast = num(row.get("avg_multicast_pct", 0))
    offset = num(row.get("avg_desfase_medio_ms", 0))
    if alerts_crit > 0 or eta < ETA_PARTIAL_THRESHOLD:
        return "Alto"
    if alerts_high > 0 or multicast > MULTICAST_ATTENTION_THRESHOLD or offset > TIMING_ATTENTION_THRESHOLD_MS:
        return "Medio"
    return "Bajo"


def eta_bucket_key(eta: float) -> str:
    if eta >= ETA_STRONG_THRESHOLD:
        return "strong"
    if eta >= ETA_PARTIAL_THRESHOLD:
        return "partial"
    if eta > 0:
        return "weak"
    return "none"


def eta_bucket_label(bucket: str) -> str:
    return {
        "strong": "Fuerte (η ≥ 85%)",
        "partial": "Parcial (60-84.9%)",
        "weak": "Débil (0-59.9%)",
        "none": "Sin cobertura",
    }.get(bucket, bucket)


def eta_bucket_css(bucket: str) -> str:
    return {
        "strong": "cell-green",
        "partial": "cell-yellow",
        "weak": "cell-orange",
        "none": "cell-red",
    }.get(bucket, "cell-red")


def eta_bucket_color(bucket: str) -> str:
    return {
        "strong": GREEN,
        "partial": YELLOW,
        "weak": ORANGE,
        "none": RED,
    }.get(bucket, RED)


def parse_bool_series(values, length: int) -> pd.Series:
    if isinstance(values, pd.Series):
        lowered = values.astype(str).str.strip().str.lower()
        return lowered.isin(["1", "true", "t", "yes", "si", "sí", "match", "matched"])
    return pd.Series([bool(values)] * length, dtype=bool)


def render_kpi(label: str, value: str, subtitle: str, tone: str = ""):
    css = "kpi"
    if tone:
        css += f" {tone}"
    st.markdown(
        f"""
<div class="{css}">
  <div class="kpi-value">{value}</div>
  <div class="kpi-label">{label}</div>
  <div class="kpi-sub">{subtitle}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def render_header(summary: dict, visits_df: pd.DataFrame, db_df: pd.DataFrame, critical_alerts: int, high_alerts: int):
    st.markdown('<div class="sec">Resumen del lote</div>', unsafe_allow_html=True)
    eta_avg = num(pd.to_numeric(visits_df.get("avg_eta_extraccion", pd.Series(dtype=float)), errors="coerce").mean())
    jitter_max = num(pd.to_numeric(db_df.get("jitter_ms", pd.Series(dtype=float)), errors="coerce").max()) if not db_df.empty else 0.0
    offset_max = num(pd.to_numeric(db_df.get("desfase_max_ms", pd.Series(dtype=float)), errors="coerce").max()) if not db_df.empty else 0.0
    multicast_avg = num(pd.to_numeric(visits_df.get("avg_multicast_pct", pd.Series(dtype=float)), errors="coerce").mean())
    field_sessions = int(summary.get("objective_1_characterization", {}).get("sessions_with_field_validation", 0) or 0)

    cols = st.columns(5)
    with cols[0]:
        render_kpi("Visitas", str(int(summary.get("total_visits", 0) or 0)), "procesadas", "info")
    with cols[1]:
        render_kpi("Sesiones", str(int(summary.get("total_sessions", 0) or 0)), "en el lote", "info")
    with cols[2]:
        render_kpi("Eficiencia", f"{eta_avg:.1f}%", "correlación promedio", "" if eta_avg >= ETA_STRONG_THRESHOLD else "alert")
    with cols[3]:
        render_kpi("Jitter máx.", f"{jitter_max:.1f} ms", "SQL consolidado", "warn" if jitter_max > TIMING_ATTENTION_THRESHOLD_MS else "")
    with cols[4]:
        render_kpi("Val. campo", str(field_sessions), "sesiones con contraste", "info")

    cols2 = st.columns(4)
    with cols2[0]:
        render_kpi("Desfase máx.", f"{offset_max:.1f} ms", "serial-red", "warn" if offset_max > TIMING_ATTENTION_THRESHOLD_MS else "")
    with cols2[1]:
        render_kpi("Multicast", f"{multicast_avg:.1f}%", "promedio del tráfico", "warn" if multicast_avg > MULTICAST_ATTENTION_THRESHOLD else "")
    with cols2[2]:
        render_kpi("Alertas altas", str(high_alerts), "conteo consolidado", "alert")
    with cols2[3]:
        render_kpi("Alertas críticas", str(critical_alerts), "conteo consolidado", "alert")


def render_assessment(visits_df: pd.DataFrame):
    st.markdown('<div class="sec">Cobertura η por visita</div>', unsafe_allow_html=True)
    if visits_df.empty:
        st.info("No hay visitas para mostrar.")
        return

    df = visits_df.copy()
    df["eta"] = pd.to_numeric(df.get("avg_eta_extraccion", 0), errors="coerce").fillna(0)
    buckets = df["eta"].map(eta_bucket_key)
    counts = {
        "strong": int((buckets == "strong").sum()),
        "partial": int((buckets == "partial").sum()),
        "weak": int((buckets == "weak").sum()),
        "none": int((buckets == "none").sum()),
    }
    total = max(1, len(df))
    pct_strong = round(100.0 * counts["strong"] / total)

    c1, c2 = st.columns([1, 2.4])
    with c1:
        fig = go.Figure(
            go.Pie(
                labels=[eta_bucket_label(key) for key in ["strong", "partial", "weak", "none"]],
                values=[counts[key] for key in ["strong", "partial", "weak", "none"]],
                hole=0.62,
                marker_colors=[GREEN, YELLOW, ORANGE, RED],
                textinfo="none",
                hovertemplate="%{label}: %{value}<extra></extra>",
            )
        )
        fig.update_layout(
            annotations=[dict(text=f"<b>{pct_strong}%</b>", x=0.5, y=0.5, font_size=24, font_color="#E9F5EE", showarrow=False)],
            showlegend=False,
            margin=dict(l=0, r=0, t=0, b=0),
            height=220,
            paper_bgcolor="rgba(0,0,0,0)",
        )
        st.plotly_chart(fig, use_container_width=True)
        for key in ["strong", "partial", "weak", "none"]:
            st.markdown(
                f'<div class="leg-item"><div class="leg-dot" style="background:{eta_bucket_color(key)}"></div><b>{counts[key]}</b> {eta_bucket_label(key)}</div>',
                unsafe_allow_html=True,
            )

    with c2:
        cells = []
        for _, row in df.iterrows():
            eta = num(row.get("eta", 0))
            bucket = eta_bucket_key(eta)
            visit_label = format_visit_label(row.get("visit_name", "?"), "V")
            cells.append(
                f'<span class="grid-cell {eta_bucket_css(bucket)}" title="η={eta:.1f}%">{visit_label}</span>'
            )
        rows = []
        for index in range(0, len(cells), 6):
            rows.append("<div>" + "".join(cells[index:index + 6]) + "</div>")
        st.markdown("".join(rows), unsafe_allow_html=True)


def render_sampling(summary: dict, visits_df: pd.DataFrame):
    st.markdown('<div class="sec">Distribución de muestreo y cobertura</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3)

    with c1:
        sample_counts = summary.get("sample_type_counts", {})
        if sample_counts:
            df = pd.DataFrame({"Tipo": list(sample_counts.keys()), "Sesiones": list(sample_counts.values())})
            fig = px.bar(df, x="Tipo", y="Sesiones", color_discrete_sequence=[GREEN], title="Tipos de sesión")
            fig.update_layout(xaxis_title="", yaxis_title="Sesiones")
            st.plotly_chart(dark(fig, 260), use_container_width=True)

    with c2:
        if not visits_df.empty:
            df = pd.DataFrame(
                {
                    "Tipo": ["PCAP", "Serial", "Collar/Antena"],
                    "Sesiones": [
                        int(pd.to_numeric(visits_df.get("sessions_with_pcap", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
                        int(pd.to_numeric(visits_df.get("sessions_with_serial", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
                        int(pd.to_numeric(visits_df.get("sessions_with_antenna_udp", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()),
                    ],
                }
            )
            fig = px.pie(df, names="Tipo", values="Sesiones", hole=0.55, color="Tipo", color_discrete_map={"PCAP": BLUE, "Serial": GREEN, "Collar/Antena": YELLOW}, title="Cobertura por dominio")
            st.plotly_chart(dark(fig, 260), use_container_width=True)

    with c3:
        if not visits_df.empty:
            field_visits = 0
            if "sessions_with_field_validation" in visits_df.columns:
                field_visits = int((pd.to_numeric(visits_df["sessions_with_field_validation"], errors="coerce").fillna(0) > 0).sum())
            corr_visits = int((pd.to_numeric(visits_df.get("avg_eta_extraccion", pd.Series(dtype=float)), errors="coerce").fillna(0) > 0).sum())
            baseline_only = max(0, len(visits_df) - max(field_visits, corr_visits))
            df = pd.DataFrame(
                {
                    "Cobertura": ["Correlación", "Validación de campo", "Resto del lote"],
                    "Visitas": [corr_visits, field_visits, baseline_only],
                }
            )
            fig = px.bar(df, x="Cobertura", y="Visitas", color="Cobertura", color_discrete_sequence=[GREEN, BLUE, ORANGE], title="Contraste analítico disponible")
            fig.update_layout(xaxis_title="", yaxis_title="Visitas")
            st.plotly_chart(dark(fig, 260), use_container_width=True)


def render_executive_panel(summary: dict, visits_df: pd.DataFrame, db_df: pd.DataFrame, critical_alerts: int, high_alerts: int):
    """Panel ejecutivo consolidado - Estado de la Finca"""
    st.markdown('<div class="sec">Panel Ejecutivo - Estado de la Finca</div>', unsafe_allow_html=True)

    if not summary:
        st.info("No hay datos de resumen disponibles.")
        return

    # Extraer métricas clave del summary
    total_visits = summary.get('total_visits', 0)
    total_sessions = summary.get('total_sessions', 0)
    sessions_with_pcap = summary.get('sessions_with_pcap', 0)
    sessions_with_serial = summary.get('sessions_with_serial', 0)
    sessions_with_correlation = summary.get('sessions_with_correlation', 0)

    # Calcular total_sessions desde visits_df para consistencia (si está disponible)
    if not visits_df.empty and "total_sessions" in visits_df.columns:
        total_sessions_from_df = int(pd.to_numeric(visits_df["total_sessions"], errors="coerce").sum())
        # Usar el valor del visits_df si es diferente del summary para consistencia
        if total_sessions_from_df != total_sessions:
            total_sessions = total_sessions_from_df

    # Calcular métricas técnicas de visits_df y db_df
    eta_avg = num(pd.to_numeric(visits_df.get("avg_eta_extraccion", pd.Series(dtype=float)), errors="coerce").mean()) if not visits_df.empty else 0.0
    jitter_max = num(pd.to_numeric(db_df.get("jitter_ms", pd.Series(dtype=float)), errors="coerce").max()) if not db_df.empty else 0.0
    offset_max = num(pd.to_numeric(db_df.get("desfase_max_ms", pd.Series(dtype=float)), errors="coerce").max()) if not db_df.empty else 0.0
    multicast_avg = num(pd.to_numeric(visits_df.get("avg_multicast_pct", pd.Series(dtype=float)), errors="coerce").mean()) if not visits_df.empty else 0.0
    field_sessions = int(summary.get("objective_1_characterization", {}).get("sessions_with_field_validation", 0) or 0)

    # Cargar alertas reales del lote para análisis detallado
    all_alerts_frames = []
    if not visits_df.empty and "visit_name" in visits_df.columns:
        for vname in visits_df["visit_name"].dropna().unique():
            df_v = load_visit_alerts(vname)
            if not df_v.empty:
                df_v = df_v.copy()
                df_v["visit_name"] = vname
                all_alerts_frames.append(df_v)

    all_alerts_df = pd.concat(all_alerts_frames, ignore_index=True) if all_alerts_frames else pd.DataFrame()

    # KPIs principales - Línea 1 (Negocio)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        severity_class = "alert" if critical_alerts > 0 else ""
        render_kpi("Problemas Urgentes", str(critical_alerts), "Requieren atención inmediata", severity_class)
    with c2:
        severity_class = "warn" if high_alerts > 50 else ""
        render_kpi("Problemas Importantes", str(high_alerts), "Deben revisarse pronto", severity_class)
    with c3:
        efficiency_class = "alert" if eta_avg < 5 else "warn" if eta_avg < 10 else ""
        render_kpi("Eficiencia", f"{eta_avg:.1f}%", "correlación promedio", efficiency_class)
    with c4:
        render_kpi("Mediciones Totales", str(total_sessions), "Momentos analizados", "info")
    
    # KPIs técnicos - Línea 2 (Técnico)
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        render_kpi("Visitas", str(int(total_visits or 0)), "procesadas", "info")
    with c2:
        jitter_class = "warn" if jitter_max > TIMING_ATTENTION_THRESHOLD_MS else ""
        render_kpi("Jitter máx.", f"{jitter_max:.1f} ms", "SQL consolidado", jitter_class)
    with c3:
        offset_class = "warn" if offset_max > TIMING_ATTENTION_THRESHOLD_MS else ""
        render_kpi("Desfase máx.", f"{offset_max:.1f} ms", "serial-red", offset_class)
    with c4:
        multicast_class = "warn" if multicast_avg > MULTICAST_ATTENTION_THRESHOLD else ""
        render_kpi("Multicast", f"{multicast_avg:.1f}%", "promedio del tráfico", multicast_class)
    with c5:
        render_kpi("Val. campo", str(field_sessions), "sesiones con contraste", "info")
    
    # Panel de problemas detallados con alertas REALES agregadas del lote
    st.markdown('<div class="sec">Análisis Detallado de Problemas</div>', unsafe_allow_html=True)
    
    if all_alerts_df.empty:
        st.info("No se encontraron archivos de alertas detalladas (alerts.json) en las sesiones de este lote.")
        critical_problems = []
    else:
        focus_df = all_alerts_df[all_alerts_df["severity"].isin(["Critica", "Alta"])].copy()
        
        # Resumen ejecutivo (sin detalles, esos están en "Por visita")
        # Usar los mismos valores calculados para los KPIs para consistencia
        st.markdown(
            f"<div style='color:#AFCDBB; margin-bottom:10px;'>"
            f"<strong style='color:{RED};'>{critical_alerts}</strong> críticas · "
            f"<strong style='color:{ORANGE};'>{high_alerts}</strong> altas · "
            f"detectadas en {focus_df['visit_name'].nunique()} visita(s) con alertas y "
            f"{focus_df['sample_name'].nunique()} sesión(es) con alertas"
            f"</div>"
            f"<div style='color:#8FC6A1; font-size:0.85rem; margin-bottom:14px;'>"
            f"Para ver la evidencia específica de cada alerta, ir a la pestaña <strong>Por visita</strong>."
            f"</div>",
            unsafe_allow_html=True,
        )
        
        # Top tipos de alerta con desglose por visita (colapsado por defecto)
        all_types = (
            focus_df.groupby(["severity", "alert_name"])
            .size()
            .reset_index(name="n_cases")
            .sort_values(["severity", "n_cases"], ascending=[True, False])
        )
        all_types = pd.concat([
            all_types[all_types["severity"] == "Critica"],
            all_types[all_types["severity"] == "Alta"],
        ])
        
        # Construir tabla con visitas afectadas por alerta
        types_with_visits = []
        for _, t in all_types.iterrows():
            n_visits = focus_df[
                (focus_df["severity"] == t["severity"]) & (focus_df["alert_name"] == t["alert_name"])
            ]["visit_name"].nunique()
            types_with_visits.append({
                "Severidad": "🔴 Crítica" if t["severity"] == "Critica" else "🟠 Alta",
                "Tipo de alerta": t["alert_name"],
                "Casos": int(t["n_cases"]),
                "Visitas afectadas": int(n_visits),
            })
        types_table = pd.DataFrame(types_with_visits)
        
        with st.expander(f"Ver listado de tipos de alerta ({len(all_types)} tipos)", expanded=False):
            st.caption("Tabla resumen ordenada por severidad y casos. Selecciona una alerta abajo para ver el desglose por visita.")
            
            # Tabla limpia, ordenada
            st.dataframe(
                types_table,
                use_container_width=True,
                hide_index=True,
                height=min(420, 45 + 35 * len(types_table)),
                column_config={
                    "Severidad": st.column_config.TextColumn(width="small"),
                    "Tipo de alerta": st.column_config.TextColumn(width="large"),
                    "Casos": st.column_config.NumberColumn(format="%d", width="small"),
                    "Visitas afectadas": st.column_config.NumberColumn(format="%d", width="small"),
                },
            )
            
            # Selector + desglose por visita debajo
            st.markdown("##### Desglose por visita")
            alert_options = types_table["Tipo de alerta"].tolist()
            selected_alert = st.selectbox(
                "Selecciona una alerta para ver en qué visitas aparece:",
                alert_options,
                key="exec_alert_selector",
            )
            if selected_alert:
                sel_row = types_table[types_table["Tipo de alerta"] == selected_alert].iloc[0]
                sev_norm = "Critica" if "Crítica" in sel_row["Severidad"] else "Alta"
                by_visit = (
                    focus_df[(focus_df["severity"] == sev_norm) & (focus_df["alert_name"] == selected_alert)]
                    .groupby("visit_name")
                    .size()
                    .reset_index(name="Casos")
                    .sort_values("Casos", ascending=False)
                )
                by_visit["Visita"] = by_visit["visit_name"].str.replace("Visita_", "", regex=False)
                st.dataframe(
                    by_visit[["Visita", "Casos"]],
                    use_container_width=True,
                    hide_index=True,
                    height=min(300, 45 + 35 * len(by_visit)),
                )
                st.caption("Para ver la evidencia específica de cada caso, ir a la pestaña **Por visita** y seleccionar la visita correspondiente.")
        
        # Construir critical_problems desde datos reales para gráficas
        critical_problems = []
        for severity_label, sev_norm in [("Critica", "crítica"), ("Alta", "alta")]:
            sev_df = focus_df[focus_df["severity"] == severity_label]
            for alert_name, group in sev_df.groupby("alert_name"):
                critical_problems.append({
                    "tipo": alert_name,
                    "cantidad": len(group),
                    "severidad": sev_norm,
                })
    
    # Gráficas de análisis
    c1, c2 = st.columns(2)
    
    with c1:
        # Gráfica de barras horizontal por tipo de problema
        problem_types = [p["tipo"] for p in critical_problems]
        problem_counts = [p["cantidad"] for p in critical_problems]
        problem_colors = [RED if p["severidad"] == "crítica" else ORANGE for p in critical_problems]
        
        fig = go.Figure(data=[
            go.Bar(y=problem_types, x=problem_counts, orientation='h', 
                  marker_color=problem_colors, text=problem_counts, textposition='auto')
        ])
        fig.update_layout(
            title='Problemas por Tipo',
            xaxis_title='Cantidad de Casos',
            yaxis_title='',
            height=350,
            yaxis={'categoryorder': 'total ascending'}
        )
        st.plotly_chart(dark(fig), use_container_width=True)
    
    with c2:
        # Cobertura de monitoreo
        coverage_df = pd.DataFrame({
            'Componente': ['Monitoreo de Red', 'Datos de Ordeño', 'Sincronización', 'Otros'],
            'Sesiones': [sessions_with_pcap, sessions_with_serial, sessions_with_correlation, 
                        total_sessions - sessions_with_pcap - sessions_with_serial - sessions_with_correlation],
            'Color': [GREEN, BLUE, YELLOW, ORANGE]
        })
        
        fig = px.bar(
            coverage_df, 
            x='Componente', 
            y='Sesiones', 
            title='Cobertura de Monitoreo',
            color='Componente',
            color_discrete_map={'Monitoreo de Red': GREEN, 'Datos de Ordeño': BLUE, 
                             'Sincronización': YELLOW, 'Otros': ORANGE}
        )
        fig.update_layout(xaxis_title='', yaxis_title='Sesiones')
        st.plotly_chart(dark(fig, 300), use_container_width=True)
    
    # Impacto en la finca
    st.markdown('<div class="sec">Impacto en la Operación de la Finca</div>', unsafe_allow_html=True)
    
    # Análisis de impacto
    impact_critical = critical_alerts * 3  # Ponderación: crítico = 3x impacto
    impact_high = high_alerts * 2         # Ponderación: importante = 2x impacto
    total_impact = impact_critical + impact_high
    
    c1, c2, c3 = st.columns(3)
    
    with c1:
        # Impacto por severidad
        impact_df = pd.DataFrame({
            'Severidad': ['Urgentes', 'Importantes'],
            'Impacto': [impact_critical, impact_high],
            'Problemas': [critical_alerts, high_alerts]
        })
        
        fig = px.bar(
            impact_df, 
            x='Severidad', 
            y='Impacto', 
            title='Impacto Operativo (Ponderado)',
            color='Severidad',
            color_discrete_map={'Urgentes': RED, 'Importantes': ORANGE}
        )
        fig.update_layout(xaxis_title='', yaxis_title='Puntos de Impacto')
        st.plotly_chart(dark(fig, 280), use_container_width=True)
    
    with c2:
        # Estado del sistema
        system_status = "Crítico" if critical_alerts > 5 else "Preocupante" if critical_alerts > 0 or high_alerts > 50 else "Estable"
        status_color = RED if system_status == "Crítico" else ORANGE if system_status == "Preocupante" else GREEN
        
        st.markdown(f"""
        <div class="card">
            <h4 style="color: {status_color}; margin: 0 0 10px 0;">Estado del Sistema: {system_status}</h4>
            <div style="font-size: 0.9rem; color: #D6E7DD;">
                <p><strong>⚠️ Riesgos identificados:</strong></p>
                <ul style="margin: 5px 0; padding-left: 20px;">
                    <li>Conflicto de identidad en red: {critical_alerts} casos</li>
                    <li>Conexiones externas no autorizadas: {critical_alerts} casos</li>
                    <li>Ruido de red excesivo: {high_alerts} casos</li>
                    <li>Equipos con identidad ambigua: {high_alerts} casos</li>
                </ul>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with c3:
        # Recomendaciones automáticas
        recommendations = []
        if critical_alerts > 0:
            recommendations.append(f"1. Atender {critical_alerts} problemas urgentes")
        if high_alerts > 20:
            recommendations.append(f"2. Revisar {high_alerts} problemas importantes")
        if eta_avg < 10:
            recommendations.append(f"3. Mejorar eficiencia (actual: {eta_avg:.1f}%)")
        
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


def render_threat_panel(visits_df: pd.DataFrame):
    st.markdown('<div class="sec">Panel de amenazas y riesgo operativo</div>', unsafe_allow_html=True)
    if visits_df.empty:
        st.info("No hay visitas disponibles para evaluar riesgo.")
        return

    df = visits_df.copy()
    if "visit_name" in df.columns:
        df["Visita"] = df["visit_name"].astype(str).map(lambda value: format_visit_label(value, "V"))
    else:
        df["Visita"] = "N/D"
    df["η (%)"] = pd.to_numeric(df.get("avg_eta_extraccion", 0), errors="coerce").fillna(0)
    df["Multicast %"] = pd.to_numeric(df.get("avg_multicast_pct", 0), errors="coerce").fillna(0)
    df["Desfase (ms)"] = pd.to_numeric(df.get("avg_desfase_medio_ms", 0), errors="coerce").fillna(0)

    # Usar valores de alertas ya actualizados en visits_df desde archivos alerts.json reales
    df["Alertas altas"] = pd.to_numeric(df.get("total_alertas_altas", 0), errors="coerce").fillna(0)
    df["Alertas críticas"] = pd.to_numeric(df.get("total_alertas_criticas", 0), errors="coerce").fillna(0)

    c1, c2, c3 = st.columns(3)
    with c1:
        fig = go.Figure()
        fig.add_trace(go.Bar(name="Críticas", x=df["Visita"], y=df["Alertas críticas"], marker_color=RED))
        fig.add_trace(go.Bar(name="Altas", x=df["Visita"], y=df["Alertas altas"], marker_color=ORANGE))
        fig.update_layout(barmode="stack", title="Alertas por visita", legend=dict(orientation="h"))
        st.plotly_chart(dark(fig, 260), use_container_width=True)

    with c2:
        risk_counts = df.apply(risk_level, axis=1).value_counts()
        fig = px.pie(
            names=["Alto", "Medio", "Bajo"],
            values=[int(risk_counts.get("Alto", 0)), int(risk_counts.get("Medio", 0)), int(risk_counts.get("Bajo", 0))],
            hole=0.58,
            color=["Alto", "Medio", "Bajo"],
            color_discrete_map={"Alto": RED, "Medio": YELLOW, "Bajo": GREEN},
            title="Distribución de riesgo",
        )
        st.plotly_chart(dark(fig, 260), use_container_width=True)

    with c3:
        serial_counts = pd.to_numeric(df["sessions_with_serial"], errors="coerce").fillna(0) if "sessions_with_serial" in df.columns else pd.Series([0] * len(df), index=df.index, dtype=float)
        exposure = pd.DataFrame(
            {
                "Vector": ["Multicast alto", "Desfase alto", "Sin serial", "Alerta crítica"],
                "Visitas": [
                    int((df["Multicast %"] > MULTICAST_ATTENTION_THRESHOLD).sum()),
                    int((df["Desfase (ms)"] > TIMING_ATTENTION_THRESHOLD_MS).sum()),
                    int((serial_counts == 0).sum()),
                    int((df["Alertas críticas"] > 0).sum()),
                ],
            }
        )
        fig = px.bar(exposure, x="Visitas", y="Vector", orientation="h", color="Vector", color_discrete_sequence=[ORANGE, YELLOW, BLUE, RED], title="Exposición por vector")
        st.plotly_chart(dark(fig, 260), use_container_width=True)

    scatter = px.scatter(
        df,
        x="Multicast %",
        y="η (%)",
        text="Visita",
        color="Alertas críticas",
        color_continuous_scale=[GREEN, ORANGE, RED],
        title="Impacto de multicast sobre η",
    )
    scatter.update_traces(textposition="top center", marker_size=11)
    scatter.add_hline(y=ETA_STRONG_THRESHOLD, line_dash="dash", line_color=YELLOW)
    st.plotly_chart(dark(scatter, 300), use_container_width=True)


def render_general(summary: dict, visits_df: pd.DataFrame, corr_df: pd.DataFrame, db_df: pd.DataFrame, critical_alerts: int, high_alerts: int):
    render_executive_panel(summary, visits_df, db_df, critical_alerts, high_alerts)
    render_assessment(visits_df)

    st.markdown('<div class="sec">Tendencia y estructura</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if not visits_df.empty:
            df = visits_df.copy()
            df["eta"] = pd.to_numeric(df.get("avg_eta_extraccion", 0), errors="coerce").fillna(0)
            if "visit_name" in df.columns:
                df["visita"] = df["visit_name"].astype(str).map(lambda x: format_visit_label(x, "V"))
            else:
                df["visita"] = "N/D"
            fig = go.Figure()
            fig.add_trace(
                go.Scatter(
                    x=df["visita"],
                    y=df["eta"],
                    mode="lines+markers",
                    marker=dict(size=9, color=[eta_color(v) for v in df["eta"]]),
                    line=dict(color=GREEN, width=2.5),
                    name="η por visita",
                )
            )
            fig.add_hline(y=ETA_STRONG_THRESHOLD, line_dash="dash", line_color=YELLOW, annotation_text=f"Cobertura fuerte {ETA_STRONG_THRESHOLD:.0f}%")
            fig.add_hline(y=ETA_PARTIAL_THRESHOLD, line_dash="dot", line_color=ORANGE, annotation_text=f"Cobertura parcial {ETA_PARTIAL_THRESHOLD:.0f}%")
            fig.update_layout(xaxis=dict(tickangle=-30), yaxis=dict(title="η (%)"), title="Cobertura η por visita")
            st.plotly_chart(dark(fig, 300), use_container_width=True)
    with c2:
        op_counts = summary.get("operation_mode_counts", {})
        if op_counts:
            df_modes = pd.DataFrame(
                {"Modo": list(op_counts.keys()), "Sesiones": list(op_counts.values())}
            )
            fig = px.bar(
                df_modes,
                x="Modo",
                y="Sesiones",
                color="Modo",
                color_discrete_sequence=[GREEN, BLUE, YELLOW, ORANGE],
                title="Composición operativa del lote",
            )
            st.plotly_chart(dark(fig, 300), use_container_width=True)

    render_sampling(summary, visits_df)

    st.markdown('<div class="sec">Lectura rápida de riesgo</div>', unsafe_allow_html=True)
    if not visits_df.empty:
        table = visits_df.copy()
        table["η (%)"] = pd.to_numeric(table.get("avg_eta_extraccion", 0), errors="coerce").fillna(0).round(2)
        table["Multicast %"] = pd.to_numeric(table.get("avg_multicast_pct", 0), errors="coerce").fillna(0).round(2)
        table["Desfase (ms)"] = pd.to_numeric(table.get("avg_desfase_medio_ms", 0), errors="coerce").fillna(0).round(2)
        table["Riesgo"] = table.apply(risk_level, axis=1)
        if "visit_name" in table.columns:
            table["Visita"] = table["visit_name"].astype(str).map(lambda x: format_visit_label(x, "Visita "))
        else:
            table["Visita"] = "N/D"
        display = table[
            [
                "Visita",
                "η (%)",
                "Multicast %",
                "Desfase (ms)",
                "total_alertas_altas",
                "total_alertas_criticas",
                "Riesgo",
            ]
        ].rename(
            columns={
                "total_alertas_altas": "Alertas altas",
                "total_alertas_criticas": "Alertas críticas",
            }
        )
        st.dataframe(display, use_container_width=True, hide_index=True, height=320)

    render_threat_panel(visits_df)

    if not corr_df.empty:
        st.markdown('<div class="sec">Correlación serial-red</div>', unsafe_allow_html=True)
        corr = corr_df.copy()
        corr["abs_delta_ms"] = pd.to_numeric(corr.get("abs_delta_ms", 0), errors="coerce").fillna(0)
        matched = parse_bool_series(corr["matched"] if "matched" in corr.columns else False, len(corr))
        matched_rate = 100.0 * matched.mean()
        m1, m2, m3 = st.columns(3)
        m1.metric("Eventos correlados", len(corr))
        m2.metric("Tasa de match", f"{matched_rate:.1f}%")
        m3.metric("Delta abs. medio", f"{corr['abs_delta_ms'].mean():.1f} ms")


def render_visit_detail(visits_df: pd.DataFrame):
    st.markdown('<div class="sec">Detalle por visita</div>', unsafe_allow_html=True)
    if visits_df.empty:
        st.info("No hay visitas disponibles en este lote.")
        return

    if "visit_name" not in visits_df.columns:
        st.info("No hay información de visitas disponible en este lote.")
        return

    options = visits_df["visit_name"].tolist()
    selected = st.selectbox("Visita", options, format_func=lambda x: format_visit_label(x, "Visita "))
    row = visits_df[visits_df["visit_name"] == selected].iloc[0]

    eta = num(row.get("avg_eta_extraccion", 0))
    multicast = num(row.get("avg_multicast_pct", 0))
    offset = num(row.get("avg_desfase_medio_ms", 0))
    alerts_high = int(row.get("total_alertas_altas", 0) or 0)
    alerts_crit = int(row.get("total_alertas_criticas", 0) or 0)
    total_sessions = int(row.get("total_sessions", 0) or 0)
    sessions_pcap = int(row.get("sessions_with_pcap", 0) or 0)
    sessions_serial = int(row.get("sessions_with_serial", 0) or 0)
    sessions_collar = int(row.get("sessions_with_antenna_udp", 0) or 0)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("η", f"{eta:.1f}%", classify_eta(eta))
    c2.metric("Multicast", f"{multicast:.1f}%", "atención" if multicast > MULTICAST_ATTENTION_THRESHOLD else "normal")
    c3.metric("Desfase medio", f"{offset:.1f} ms", "atención" if offset > TIMING_ATTENTION_THRESHOLD_MS else "normal")
    c4.metric("Alertas", f"{alerts_high} / {alerts_crit}", "altas / críticas")

    # Sección de problemas encontrados en esta visita - alertas reales con evidencia
    st.markdown('<div class="sec">Problemas Encontrados en esta Visita</div>', unsafe_allow_html=True)
    
    alerts_df = load_visit_alerts(selected)
    
    if alerts_df.empty:
        st.success("✅ No se detectaron problemas en esta visita")
    else:
        # Filtrar solo Críticas y Altas (los "problemas" reales)
        focus_df = alerts_df[alerts_df["severity"].isin(["Critica", "Alta"])].copy()
        
        if focus_df.empty:
            st.success("✅ No se detectaron problemas críticos ni altos en esta visita")
        else:
            # Resumen por severidad
            sev_counts = focus_df["severity"].value_counts()
            crit_n = int(sev_counts.get("Critica", 0))
            high_n = int(sev_counts.get("Alta", 0))
            st.markdown(
                f"<div style='color:#AFCDBB; margin-bottom:10px;'>"
                f"<strong style='color:{RED};'>{crit_n}</strong> críticas · "
                f"<strong style='color:{ORANGE};'>{high_n}</strong> altas · "
                f"agrupadas por tipo en {focus_df['sample_name'].nunique()} sesión(es)"
                f"</div>",
                unsafe_allow_html=True,
            )
            
            # Tabla resumen + selector de detalle (mismo formato que Panel General)
            visit_types_rows = []
            for (severity_label, alert_name), group in focus_df.groupby(["severity", "alert_name"]):
                visit_types_rows.append({
                    "Severidad": "🔴 Crítica" if severity_label == "Critica" else "🟠 Alta",
                    "Tipo de alerta": alert_name,
                    "Casos": len(group),
                    "Sesiones afectadas": group["sample_name"].nunique(),
                    "Capa": ", ".join(sorted(group["layer"].unique())),
                    "_sev_rank": 0 if severity_label == "Critica" else 1,
                })
            visit_types_df = (
                pd.DataFrame(visit_types_rows)
                .sort_values(["_sev_rank", "Casos"], ascending=[True, False])
                .drop(columns="_sev_rank")
                .reset_index(drop=True)
            )
            
            st.caption("Tabla resumen ordenada por severidad y casos. Selecciona una alerta abajo para ver la evidencia específica.")
            st.dataframe(
                visit_types_df,
                use_container_width=True,
                hide_index=True,
                height=min(420, 45 + 35 * len(visit_types_df)),
                column_config={
                    "Severidad": st.column_config.TextColumn(width="small"),
                    "Tipo de alerta": st.column_config.TextColumn(width="large"),
                    "Casos": st.column_config.NumberColumn(format="%d", width="small"),
                    "Sesiones afectadas": st.column_config.NumberColumn(format="%d", width="small"),
                    "Capa": st.column_config.TextColumn(width="medium"),
                },
            )
            
            # Selector + evidencia debajo
            st.markdown("##### Evidencia detallada")
            alert_options = visit_types_df["Tipo de alerta"].tolist()
            selected_alert = st.selectbox(
                "Selecciona una alerta para ver la evidencia específica:",
                alert_options,
                key=f"visit_alert_selector_{selected}",
            )
            if selected_alert:
                sel_row = visit_types_df[visit_types_df["Tipo de alerta"] == selected_alert].iloc[0]
                sev_norm = "Critica" if "Crítica" in sel_row["Severidad"] else "Alta"
                group = focus_df[(focus_df["severity"] == sev_norm) & (focus_df["alert_name"] == selected_alert)]
                first = group.iloc[0]
                
                # Metadatos colapsados (solo visibles bajo demanda)
                with st.expander("ℹ️ Ver impacto y recomendación", expanded=False):
                    st.markdown(
                        f"**Severidad:** {sel_row['Severidad']}  ·  **Capa:** {sel_row['Capa']}  ·  "
                        f"**Casos:** {sel_row['Casos']}  ·  **Sesiones:** {sel_row['Sesiones afectadas']}"
                    )
                    st.markdown(f"**Impacto:** {first['impact']}")
                    st.markdown(f"**Recomendación:** {first['recommendation']}")
                
                evidence_cols = ["sample_name", "evidence", "protocol", "timestamp"]
                display_df = group[[c for c in evidence_cols if c in group.columns]].reset_index(drop=True)
                display_df.columns = [c.replace("_", " ").title() for c in display_df.columns]
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    height=min(360, 45 + 35 * len(display_df)),
                )

    d1, d2 = st.columns(2)
    with d1:
        fig = go.Figure(
            go.Indicator(
                mode="gauge+number",
                value=eta,
                number={"suffix": "%"},
                title={"text": format_visit_label(selected, "Visita ")},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": eta_color(eta)},
                    "steps": [
                        {"range": [0, ETA_PARTIAL_THRESHOLD], "color": "#341414"},
                        {"range": [ETA_PARTIAL_THRESHOLD, ETA_STRONG_THRESHOLD], "color": "#433813"},
                        {"range": [ETA_STRONG_THRESHOLD, 100], "color": "#17331E"},
                    ],
                    "threshold": {"line": {"color": YELLOW, "width": 3}, "value": ETA_STRONG_THRESHOLD},
                },
            )
        )
        st.plotly_chart(dark(fig, 280), use_container_width=True)
    with d2:
        comp = pd.DataFrame(
            {
                "Tipo": ["PCAP", "Serial", "Collar/Antena", "Baseline"],
                "Sesiones": [
                    sessions_pcap,
                    sessions_serial,
                    sessions_collar,
                    max(0, total_sessions - max(sessions_pcap, sessions_serial, sessions_collar)),
                ],
            }
        )
        fig = px.bar(comp, x="Sesiones", y="Tipo", orientation="h", color="Tipo", color_discrete_sequence=[BLUE, GREEN, YELLOW, ORANGE])
        st.plotly_chart(dark(fig, 280), use_container_width=True)

    detail = pd.DataFrame(
        {
            "Parámetro": [
                "Sesiones totales",
                "Sesiones con PCAP",
                "Sesiones con serial",
                "Sesiones de collar",
                "Riesgo operativo",
            ],
            "Valor": [
                total_sessions,
                sessions_pcap,
                sessions_serial,
                sessions_collar,
                risk_level(row),
            ],
        }
    )
    st.dataframe(detail, use_container_width=True, hide_index=True)


def render_sync(corr_df: pd.DataFrame):
    st.markdown('<div class="sec">Sincronía serial-red</div>', unsafe_allow_html=True)
    if corr_df.empty:
        st.info("Este lote no trae correlación global serial-red.")
        return

    df = corr_df.copy()
    df["abs_delta_ms"] = pd.to_numeric(df.get("abs_delta_ms", 0), errors="coerce").fillna(0)
    df["matched"] = parse_bool_series(df["matched"] if "matched" in df.columns else False, len(df))
    if "visit_name" in df.columns:
        df["visit_name"] = df["visit_name"].astype(str)
        df["visit_date"] = df["visit_name"].map(visit_date_from_name)
    if "sample_id" in df.columns:
        df["sample_id"] = df["sample_id"].astype(str)
    if "serial_event" in df.columns:
        df["serial_event"] = df["serial_event"].astype(str)

    has_visit_scope = "visit_name" in df.columns and df["visit_name"].str.strip().ne("").any()
    has_session_scope = "sample_id" in df.columns and df["sample_id"].str.strip().ne("").any()
    has_date_scope = "visit_date" in df.columns and df["visit_date"].str.strip().ne("").any()
    has_event_scope = "serial_event" in df.columns and df["serial_event"].str.strip().ne("").any()

    if not has_visit_scope and not has_session_scope:
        st.caption("Este archivo de correlación es de formato antiguo: la sincronía sigue filtrable por evento/estado, pero no por visita o sesión hasta regenerar el lote.")

    filter_cols = st.columns(4)
    filtered = df.copy()

    with filter_cols[0]:
        if has_visit_scope:
            visit_options = ["Todas"] + sorted({value for value in df["visit_name"].tolist() if str(value).strip()})
            selected_visit = st.selectbox("Visita", visit_options, format_func=lambda value: value if value == "Todas" else format_visit_label(value, "Visita "))
            if selected_visit != "Todas":
                filtered = filtered[filtered["visit_name"] == selected_visit]
        else:
            st.selectbox("Visita", ["No disponible"], disabled=True)

    with filter_cols[1]:
        if has_date_scope:
            date_options = ["Todas"] + sorted({value for value in filtered["visit_date"].tolist() if str(value).strip()})
            selected_date = st.selectbox("Fecha", date_options)
            if selected_date != "Todas":
                filtered = filtered[filtered["visit_date"] == selected_date]
        else:
            st.selectbox("Fecha", ["No disponible"], disabled=True)

    with filter_cols[2]:
        if has_session_scope:
            session_options = ["Todas"] + sorted({value for value in filtered["sample_id"].tolist() if str(value).strip()})
            selected_session = st.selectbox("Sesión", session_options)
            if selected_session != "Todas":
                filtered = filtered[filtered["sample_id"] == selected_session]
        else:
            st.selectbox("Sesión", ["No disponible"], disabled=True)

    with filter_cols[3]:
        if has_event_scope:
            event_options = ["Todos"] + sorted({value for value in filtered["serial_event"].tolist() if str(value).strip()})
            selected_event = st.selectbox("Evento serial", event_options)
            if selected_event != "Todos":
                filtered = filtered[filtered["serial_event"] == selected_event]
        else:
            st.selectbox("Evento serial", ["No disponible"], disabled=True)

    match_scope = st.radio("Estado de correlación", ["Todos", "Solo match", "Solo sin match"], horizontal=True)
    if match_scope == "Solo match":
        filtered = filtered[filtered["matched"]]
    elif match_scope == "Solo sin match":
        filtered = filtered[~filtered["matched"]]

    if filtered.empty:
        st.warning("No hay eventos de sincronía para el filtro seleccionado.")
        return

    df = filtered
    matched_rate = 100.0 * df["matched"].mean()
    raw_delta_col = "delta_ms" if "delta_ms" in df.columns else "abs_delta_ms"
    x_col = None
    for candidate in ["timestamp_serial", "timestamp_red", "timestamp", "event_timestamp"]:
        if candidate in df.columns:
            x_col = candidate
            break

    c1, c2, c3 = st.columns(3)
    c1.metric("Eventos", len(df))
    c2.metric("Match", f"{matched_rate:.1f}%")
    c3.metric("P95 abs. delta", f"{df['abs_delta_ms'].quantile(0.95):.1f} ms")

    scope_parts = []
    if has_visit_scope and len(df["visit_name"].dropna().unique()) == 1:
        scope_parts.append(f"visita {format_visit_label(df['visit_name'].dropna().iloc[0], 'Visita ')}")
    if has_session_scope and len(df["sample_id"].dropna().unique()) == 1:
        scope_parts.append(f"sesión {df['sample_id'].dropna().iloc[0]}")
    if has_event_scope and len(df["serial_event"].dropna().unique()) == 1:
        scope_parts.append(f"evento {df['serial_event'].dropna().iloc[0]}")
    if scope_parts:
        st.caption("Vista actual: " + " | ".join(scope_parts))

    p1, p2 = st.columns(2)
    with p1:
        fig = px.histogram(df, x="abs_delta_ms", nbins=30, color_discrete_sequence=[GREEN], title="Distribución de |delta|")
        st.plotly_chart(dark(fig, 280), use_container_width=True)
    with p2:
        pie = pd.DataFrame(
            {
                "Estado": ["Match", "Sin match"],
                "Cantidad": [int(df["matched"].sum()), int((~df["matched"]).sum())],
            }
        )
        fig = px.pie(pie, values="Cantidad", names="Estado", color="Estado", color_discrete_map={"Match": GREEN, "Sin match": RED}, title="Estado de correlación")
        st.plotly_chart(dark(fig, 280), use_container_width=True)

    if x_col is not None:
        series = df.copy()
        series[x_col] = pd.to_datetime(series[x_col], errors="coerce")
        series = series.dropna(subset=[x_col]).sort_values(x_col)
        if not series.empty:
            fig = px.line(series, x=x_col, y=raw_delta_col, markers=True, color_discrete_sequence=[GREEN], title="Tendencia temporal del desfase")
            fig.add_hline(y=TIMING_ATTENTION_THRESHOLD_MS, line_dash="dash", line_color=YELLOW)
            fig.add_hline(y=-TIMING_ATTENTION_THRESHOLD_MS, line_dash="dash", line_color=YELLOW)
            st.plotly_chart(dark(fig, 300), use_container_width=True)

    display_cols = [col for col in ["visit_name", "visit_date", "sample_id", "serial_event", "timestamp_serial", raw_delta_col, "abs_delta_ms", "matched"] if col in df.columns]
    st.dataframe(df[display_cols], use_container_width=True, hide_index=True, height=260)


def render_trazabilidad(db_df: pd.DataFrame):
    st.markdown('<div class="sec">Trazabilidad SQL</div>', unsafe_allow_html=True)
    if db_df.empty:
        st.info("No hay base SQL consolidada disponible.")
        return

    df = db_df.copy()
    for col in ["eta_extraccion", "desfase_medio_ms", "jitter_ms", "packet_loss", "lat_media"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    eta = df["eta_extraccion"].dropna() if "eta_extraccion" in df.columns else pd.Series(dtype=float)
    jitter = df["jitter_ms"].dropna() if "jitter_ms" in df.columns else pd.Series(dtype=float)

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Registros", len(df))
    k2.metric("η promedio", f"{eta.mean():.2f}%" if not eta.empty else "N/D")
    k3.metric("Jitter máx.", f"{jitter.max():.2f} ms" if not jitter.empty else "N/D")
    k4.metric("PLR medio", f"{df['packet_loss'].dropna().mean():.2f}%" if "packet_loss" in df.columns and not df["packet_loss"].dropna().empty else "N/D")

    c1, c2 = st.columns(2)
    with c1:
        if not jitter.empty:
            fig = px.histogram(df.dropna(subset=["jitter_ms"]), x="jitter_ms", nbins=30, color_discrete_sequence=[GREEN], title="Distribución de jitter")
            st.plotly_chart(dark(fig, 280), use_container_width=True)
    with c2:
        if {"lat_media", "eta_extraccion"}.issubset(df.columns):
            valid = df.dropna(subset=["lat_media", "eta_extraccion"])
            fig = px.scatter(valid, x="lat_media", y="eta_extraccion", color="fecha" if "fecha" in valid.columns else None, title="Latencia vs η")
            st.plotly_chart(dark(fig, 280), use_container_width=True)

    display_cols = [col for col in ["fecha", "id_muestra", "lat_media", "jitter_ms", "packet_loss", "desfase_medio_ms", "eta_extraccion"] if col in df.columns]
    st.dataframe(df[display_cols], use_container_width=True, height=320)
    st.download_button(
        "Descargar CSV",
        data=df.to_csv(index=False).encode("utf-8"),
        file_name="fincadiag_trazabilidad.csv",
        mime="text/csv",
    )


def render_parsing_quality(parsing_df: pd.DataFrame):
    """Panel de calidad de parsing - Ingeniería inversa de datos"""
    st.markdown('<div class="sec">Calidad de Parsing</div>', unsafe_allow_html=True)

    if parsing_df.empty:
        st.info("No hay datos de parsing disponibles en este lote.")
        return

    # KPIs principales de parsing
    total_sessions = len(parsing_df)
    serial_available = int(parsing_df["serial_available"].sum())
    pcap_available = int(parsing_df["pcap_available"].sum())
    field_validation_available = int(parsing_df["field_validation_available"].sum())

    total_malformed_lines = int(parsing_df["serial_malformed_lines"].sum() + parsing_df["antenna_udp_malformed_lines"].sum())
    total_unparsed_lines = int(parsing_df["serial_unparsed_lines"].sum())

    # Métricas de parser vs campo (solo sesiones con validación)
    field_sessions = parsing_df[parsing_df["field_validation_available"]]
    if not field_sessions.empty:
        avg_coverage = float(field_sessions["parser_coverage_rate_vs_field"].mean())
        total_parser_events = int(field_sessions["parser_event_count"].sum())
        total_missing = int(field_sessions["parser_missing_count_vs_field"].sum())
        total_excess = int(field_sessions["parser_excess_count_vs_field"].sum())
    else:
        avg_coverage = 0.0
        total_parser_events = 0
        total_missing = 0
        total_excess = 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        render_kpi("Serial parseado", f"{serial_available}/{total_sessions}", "sesiones con serial", "info")
    with c2:
        render_kpi("PCAP parseado", f"{pcap_available}/{total_sessions}", "sesiones con PCAP", "info")
    with c3:
        render_kpi("Validación campo", f"{field_validation_available}/{total_sessions}", "sesiones con contraste", "info")
    with c4:
        severity_class = "warn" if total_malformed_lines > 0 else ""
        render_kpi("Líneas malformadas", str(total_malformed_lines), "serial + antena", severity_class)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        severity_class = "warn" if total_unparsed_lines > 0 else ""
        render_kpi("Líneas no parseadas", str(total_unparsed_lines), "serial no procesadas", severity_class)
    with c2:
        coverage_class = "alert" if avg_coverage < 0.8 else "warn" if avg_coverage < 0.9 else ""
        render_kpi("Cobertura parser", f"{avg_coverage:.1%}", "promedio vs campo", coverage_class)
    with c3:
        render_kpi("Eventos parser", str(total_parser_events), "reconstruidos", "info")
    with c4:
        severity_class = "warn" if total_missing > 0 else ""
        render_kpi("Eventos faltantes", str(total_missing), "parser vs campo", severity_class)

    # Gráficas de distribución
    st.markdown('<div class="sec">Distribución de calidad</div>', unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        # Distribución de líneas malformadas
        serial_malformed = parsing_df[parsing_df["serial_available"]]["serial_malformed_lines"]
        if not serial_malformed.empty:
            fig = px.histogram(
                serial_malformed,
                nbins=20,
                title="Distribución de líneas malformadas (Serial)",
                color_discrete_sequence=[ORANGE],
            )
            st.plotly_chart(dark(fig, 280), use_container_width=True)

    with c2:
        # Distribución de cobertura del parser
        if not field_sessions.empty:
            fig = px.histogram(
                field_sessions["parser_coverage_rate_vs_field"],
                nbins=20,
                title="Distribución de cobertura parser vs campo",
                color_discrete_sequence=[GREEN],
            )
            fig.add_vline(x=0.9, line_dash="dash", line_color=YELLOW, annotation_text="90%")
            fig.add_vline(x=0.8, line_dash="dot", line_color=ORANGE, annotation_text="80%")
            st.plotly_chart(dark(fig, 280), use_container_width=True)

    # Tabla resumen por sesión
    st.markdown('<div class="sec">Detalle por sesión</div>', unsafe_allow_html=True)

    display_df = parsing_df.copy()
    display_df["Visita"] = display_df["visit_name"].astype(str).map(lambda x: format_visit_label(x, "V"))
    display_df["Serial"] = display_df["serial_available"].map(lambda x: "✓" if x else "✗")
    display_df["PCAP"] = display_df["pcap_available"].map(lambda x: "✓" if x else "✗")
    display_df["Campo"] = display_df["field_validation_available"].map(lambda x: "✓" if x else "✗")
    display_df["Malformadas"] = display_df["serial_malformed_lines"] + display_df["antenna_udp_malformed_lines"]
    display_df["No parseadas"] = display_df["serial_unparsed_lines"]
    display_df["Eventos parser"] = display_df["parser_event_count"]
    display_df["Cobertura %"] = (display_df["parser_coverage_rate_vs_field"] * 100).round(1)
    display_df["Delta"] = display_df["parser_event_delta_vs_field"]

    cols_to_show = ["Visita", "Serial", "PCAP", "Campo", "Malformadas", "No parseadas", "Eventos parser", "Cobertura %", "Delta"]
    st.dataframe(
        display_df[cols_to_show],
        use_container_width=True,
        height=400,
        hide_index=True,
        column_config={
            "Malformadas": st.column_config.NumberColumn(format="%d", width="small"),
            "No parseadas": st.column_config.NumberColumn(format="%d", width="small"),
            "Eventos parser": st.column_config.NumberColumn(format="%d", width="small"),
            "Cobertura %": st.column_config.NumberColumn(format="%.1f", width="small"),
            "Delta": st.column_config.NumberColumn(format="%d", width="small"),
        },
    )


def main():
    st.sidebar.title(f"FincaDiag — {_DASHBOARD_CODENAME}")
    runs = available_runs()
    if not runs:
        st.error(f"No se encontraron lotes en {PROCESSED_DIR / 'global' / 'resumen_arbol'}")
        return

    selected_label = st.sidebar.selectbox("Lote", [label for label, _ in runs])
    run_map = dict(runs)
    summary_path = run_map[selected_label]

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    visits_df = load_visits(summary_path, selected_label)
    corr_df = load_corr(summary_path, selected_label)
    db_df = get_db()

    # Actualizar visits_df con contadores reales de alertas por visita desde archivos alerts.json
    alert_counts = {}
    if "visit_name" in visits_df.columns:
        for vname in visits_df["visit_name"].dropna().unique():
            alerts_df = load_visit_alerts(vname)
            if not alerts_df.empty:
                focus_df = alerts_df[alerts_df["severity"].isin(["Critica", "Alta"])]
                alert_counts[vname] = {
                    "altas": int((focus_df["severity"] == "Alta").sum()),
                    "criticas": int((focus_df["severity"] == "Critica").sum()),
                }
            else:
                alert_counts[vname] = {"altas": 0, "criticas": 0}

        visits_df["total_alertas_altas"] = visits_df["visit_name"].map(lambda x: alert_counts.get(x, {}).get("altas", 0))
        visits_df["total_alertas_criticas"] = visits_df["visit_name"].map(lambda x: alert_counts.get(x, {}).get("criticas", 0))
    else:
        # Si no hay columna visit_name, inicializar con 0
        visits_df["total_alertas_altas"] = 0
        visits_df["total_alertas_criticas"] = 0

    # Calcular totales del lote desde datos reales para el sidebar
    total_high = sum(v["altas"] for v in alert_counts.values())
    total_critical = sum(v["criticas"] for v in alert_counts.values())

    st.sidebar.markdown("---")
    st.sidebar.markdown("**Resumen del lote**")
    st.sidebar.markdown(f"Visitas: **{int(summary.get('total_visits', 0) or 0)}**")
    st.sidebar.markdown(f"Sesiones: **{int(summary.get('total_sessions', 0) or 0)}**")
    st.sidebar.markdown(f"Alertas altas: **{total_high}**")
    st.sidebar.markdown(f"Alertas críticas: **{total_critical}**")
    st.sidebar.markdown("---")
    st.sidebar.markdown("**Criterios operativos**")
    st.sidebar.markdown(f"Cobertura fuerte η: **≥{ETA_STRONG_THRESHOLD:.0f}%**")
    st.sidebar.markdown(f"Cobertura parcial η: **≥{ETA_PARTIAL_THRESHOLD:.0f}%**")
    st.sidebar.markdown(f"Multicast de atención: **>{MULTICAST_ATTENTION_THRESHOLD:.0f}%**")
    st.sidebar.markdown(f"Desfase de atención: **>{TIMING_ATTENTION_THRESHOLD_MS:.0f} ms**")
    st.sidebar.markdown("---")
    st.sidebar.caption(
        "<div style='line-height:1.4; color:#6B8E6B; font-size:0.75rem;'>"
        "<strong>TFG</strong><br>"
        "Instrumentación perimetral, caracterización y evaluación del flujo de telemetría IoT en el borde<br>"
        "<em>Caso SenseHub Dairy en la Finca La Esmeralda</em><br><br>"
        "<strong>Elaborado:</strong> Jorge Rodríguez E.<br>"
        "<strong>Curso:</strong> IS-2026"
        "</div>",
        unsafe_allow_html=True,
    )

    # Cargar datos de parsing para la nueva pestaña
    parsing_df = load_parsing_data(summary_path, selected_label)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        ["Panel general", "Por visita", "Sincronía", "Calidad de Parsing", "Trazabilidad SQL"]
    )
    with tab1:
        render_general(summary, visits_df, corr_df, db_df, total_critical, total_high)
    with tab2:
        render_visit_detail(visits_df)
    with tab3:
        render_sync(corr_df)
    with tab4:
        render_parsing_quality(parsing_df)
    with tab5:
        render_trazabilidad(db_df)


if __name__ == "__main__":
    main()
