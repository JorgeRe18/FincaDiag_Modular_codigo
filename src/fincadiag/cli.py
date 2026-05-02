import argparse
import csv
import json
import re
import sqlite3
import time
from datetime import date, datetime
from pathlib import Path

try:
    from rich.progress import (
        BarColumn,
        Progress,
        TaskProgressColumn,
        TextColumn,
        TimeElapsedColumn,
        TimeRemainingColumn,
    )
    _HAS_RICH = True
except Exception:
    _HAS_RICH = False

from fincadiag.analysis.alerts import build_alert_package
from fincadiag.analysis.correlation import correlate_events
from fincadiag.analysis.field_validation import build_field_validation_summary
from fincadiag.analysis.rules import build_priority_rules
from fincadiag.config import (
    DATA_PROCESSED_DIR,
    DEFAULT_SIGNATURE,
    DEFAULT_TARGET_IP,
    DEFAULT_TARGET_PORT,
    DEFAULT_WINDOW_MS,
    REPORTS_DIR,
)
from fincadiag.export.report_builder import generate_reports
from fincadiag.ingest.discover import (
    discover_baseline_only_sessions,
    discover_sessions,
    discover_single_session,
)
from fincadiag.parsers.antenna_udp_parser import parse_antenna_udp_file
from fincadiag.parsers.baseline_parser import has_baseline_files, parse_baseline_dir
from fincadiag.parsers.pcap_parser import SCAPY_OK, parse_pcap_file
from fincadiag.parsers.serial_parser import parse_serial_file
from fincadiag.utils import dump_json, ensure_dir


REQUIRED_VISIT_COLS = [
    "visit_name",
    "total_sessions",
    "sessions_with_pcap",
    "sessions_with_serial",
    "sessions_with_antenna_udp",
    "sessions_with_baseline",
    "total_alertas_altas",
    "total_alertas_criticas",
    "avg_eta_extraccion",
    "avg_desfase_medio_ms",
    "avg_multicast_pct",
    "avg_lat_media",
]

CORRELACION_COLS = {
    "timestamp_serial": "HH:MM:SS.mmm del evento serial",
    "delta_ms": "red_ms - serial_ms, puede ser negativo",
    "serial_event": "tipo de evento (fotocelda_activa, rfid_leido, etc.)",
    "abs_delta_ms": "valor absoluto del delta",
    "matched": "bool - dentro de la ventana de correlacion",
}

REQUIRED_GLOBAL_SUMMARY_KEYS = [
    "total_visits",
    "total_sessions",
    "sessions_with_pcap",
    "sessions_with_serial",
    "sessions_with_antenna_udp",
    "total_alertas_altas",
    "total_alertas_criticas",
    "sample_type_counts",
]

REQUIRED_SAMPLE_TYPE_KEYS = [
    "SERIAL + PCAP",
    "Antena + PCAP",
    "PCAP + ETL",
    "PCAP solo",
    "Baseline",
    "Otros",
]

DB_PATH = DATA_PROCESSED_DIR.parent / "finca_muestras.db"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str] | None = None) -> None:
    if fieldnames is None:
        fieldnames = []
        seen = set()
        for row in rows:
            for key in row.keys():
                if key not in seen:
                    seen.add(key)
                    fieldnames.append(key)
    if not rows and not fieldnames:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def format_metric(value, decimals: int = 3) -> str:
    if value in ("", None):
        return "N/D"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimals == 0:
        return f"{number:.0f}"
    return f"{number:.{decimals}f}"


def format_flag(value: bool) -> str:
    return "Si" if value else "No"


def has_metric(value) -> bool:
    return value not in ("", None)


def clip_text(text: str, width: int) -> str:
    text = str(text)
    if len(text) <= width:
        return text.ljust(width)
    return f"{text[: max(0, width - 3)]}..."


def build_text_table(headers: list[str], rows: list[list[str]], widths: list[int]) -> str:
    header_line = " | ".join(clip_text(header, width) for header, width in zip(headers, widths))
    separator = "-+-".join("-" * width for width in widths)
    body = []
    for row in rows:
        body.append(" | ".join(clip_text(value, width) for value, width in zip(row, widths)))
    return "\n".join([header_line, separator, *body]) if body else "\n".join([header_line, separator, "(sin filas)"])


def sort_session_rows(rows: list[dict]) -> list[dict]:
    return sorted(rows, key=lambda row: (row.get("capture_dir", ""), row.get("sample_id", "")))


def get_operation_mode_label(value: str) -> str:
    mapping = {
        "ordeno_completo": "Ordeno",
        "telemetria_collar": "Collares",
        "baseline": "Baseline",
        "indeterminado": "Indeterm.",
    }
    return mapping.get(str(value or ""), str(value or "N/D"))


def build_operation_mode_counts(rows: list[dict]) -> dict:
    counts = {
        "Ordeno completo": 0,
        "Telemetria de collar": 0,
        "Baseline": 0,
        "Indeterminado": 0,
    }
    for row in rows:
        mode = row.get("operation_mode", "")
        if mode == "ordeno_completo":
            counts["Ordeno completo"] += 1
        elif mode == "telemetria_collar":
            counts["Telemetria de collar"] += 1
        elif mode == "baseline":
            counts["Baseline"] += 1
        else:
            counts["Indeterminado"] += 1
    return counts


def build_session_inventory_table(rows: list[dict], include_visit: bool = False) -> str:
    ordered_rows = sort_session_rows(rows)
    headers = ["Sesion", "Bloque", "Modo", "Origen", "ConBase", "Serial", "AntTXT", "ETL", "PCAP", "Corr", "Lat", "Vacas", "Firmas", "Eta", "Delta", "Crit", "Alta"]
    widths = [38, 7, 10, 8, 7, 6, 6, 4, 4, 4, 8, 5, 7, 8, 8, 4, 4]

    if include_visit:
        headers = ["Visita", *headers]
        widths = [18, *widths]

    table_rows = []
    for row in ordered_rows:
        cells = [
            row["sample_id"],
            row.get("block_label", ""),
            get_operation_mode_label(row.get("operation_mode", "")),
            "BASELINE" if row.get("session_type") == "baseline_only" else "CAPTURA",
            format_flag(row["has_baseline"]),
            format_flag(row["has_serial"]),
            format_flag(row.get("has_antenna_udp", False)),
            format_flag(row.get("has_etl", False)),
            format_flag(row["has_pcap"]),
            format_flag(row["has_correlation"]),
            format_metric(row["lat_media"], 3),
            format_metric(row["eventos_vaca"], 0),
            format_metric(row["firmas_56d100"], 0),
            format_metric(row["eta_extraccion"], 2),
            format_metric(row["desfase_medio_ms"], 3),
            format_metric(row.get("alertas_criticas", 0), 0),
            format_metric(row.get("alertas_altas", 0), 0),
        ]
        if include_visit:
            cells = [row["visit_name"], *cells]
        table_rows.append(cells)

    return build_text_table(headers, table_rows, widths)


def build_visit_aggregate_table(rows: list[dict]) -> str:
    ordered_rows = sorted(rows, key=lambda row: row["visit_name"])
    headers = ["Visita", "Ses", "Baseline", "ConBase", "Serial", "PCAP", "Corr", "Crit", "Alta", "Lat", "Eta", "Delta", "Mcast"]
    widths = [18, 4, 8, 7, 6, 4, 4, 4, 4, 8, 8, 8, 8]
    table_rows = []
    for row in ordered_rows:
        table_rows.append(
            [
                row["visit_name"],
                format_metric(row["total_sessions"], 0),
                format_metric(row.get("sessions_baseline_only", 0), 0),
                format_metric(row["sessions_with_baseline"], 0),
                format_metric(row["sessions_with_serial"], 0),
                format_metric(row["sessions_with_pcap"], 0),
                format_metric(row["sessions_with_correlation"], 0),
                format_metric(row.get("total_alertas_criticas", 0), 0),
                format_metric(row.get("total_alertas_altas", 0), 0),
                format_metric(row["avg_lat_media"], 3),
                format_metric(row["avg_eta_extraccion"], 2),
                format_metric(row["avg_desfase_medio_ms"], 3),
                format_metric(row["avg_multicast_pct"], 2),
            ]
        )
    return build_text_table(headers, table_rows, widths)


def build_highlights_text(rows: list[dict]) -> str:
    if not rows:
        return "No hay datos suficientes para resumir observaciones de apoyo."

    lines = []

    correlated = [row for row in rows if row["has_correlation"]]
    serial_pcap_rows = [row for row in rows if get_capture_topology_type(row) == "SERIAL + PCAP"]
    antenna_rows = [row for row in rows if row.get("has_antenna_udp")]
    collar_mode_rows = [row for row in rows if row.get("operation_mode") == "telemetria_collar"]
    signatures = [row for row in rows if float(row.get("firmas_56d100", 0) or 0) > 0]
    serial_only = [row for row in rows if row["has_serial"] and not row["has_pcap"]]
    pcap_without_serial = [row for row in rows if row["has_pcap"] and not row["has_serial"]]
    pcap_etl = [row for row in rows if row["has_pcap"] and row.get("has_etl")]
    baseline_only = [row for row in rows if row.get("session_type") == "baseline_only"]

    if correlated:
        best_eta = max(correlated, key=lambda row: float(row.get("eta_extraccion", 0) or 0))
        max_delta = max(correlated, key=lambda row: float(row.get("desfase_medio_ms", 0) or 0))
        lines.append(
            f"- Sesion con mejor apoyo de correlacion temporal: {best_eta['sample_id']} | eta={format_metric(best_eta['eta_extraccion'], 2)}% | delta={format_metric(best_eta['desfase_medio_ms'], 3)} ms"
        )
        lines.append(
            f"- Sesion que conviene revisar por mayor desfase medio: {max_delta['sample_id']} | delta={format_metric(max_delta['desfase_medio_ms'], 3)} ms"
        )
    elif serial_pcap_rows:
        lines.append(
            f"- Hay {len(serial_pcap_rows)} sesiones SERIAL + PCAP, pero ninguna produjo correlacion efectiva defendible en esta corrida."
        )
    else:
        lines.append("- En este conjunto no se conto con sesiones serial y PCAP simultaneas para una correlacion directa.")

    if signatures:
        top_signature = max(signatures, key=lambda row: float(row.get("firmas_56d100", 0) or 0))
        lines.append(
            f"- Mayor presencia observada de firma 56 D1 00: {top_signature['sample_id']} | firmas={format_metric(top_signature['firmas_56d100'], 0)}"
        )
    elif collar_mode_rows:
        lines.append(
            f"- Se detectaron {len(collar_mode_rows)} sesiones del dominio de collar, pero sin firmas 56 D1 00 parseadas de forma util en el consolidado actual."
        )
    elif antenna_rows:
        lines.append(
            f"- Se detectaron {len(antenna_rows)} sesiones con evidencia de antena/collar, pero sin firmas 56 D1 00 parseadas de forma util en el consolidado actual."
        )
    else:
        lines.append("- No hubo sesiones del dominio de collar en las muestras revisadas.")

    highest_risk = sorted(
        rows,
        key=lambda row: (
            -int(row.get("alertas_criticas", 0) or 0),
            -int(row.get("alertas_altas", 0) or 0),
            -int(row.get("alertas_totales", 0) or 0),
        ),
    )[0]
    if int(highest_risk.get("alertas_totales", 0) or 0) > 0:
        lines.append(
            f"- Sesion que merece atencion prioritaria: {highest_risk['sample_id']} | criticas={format_metric(highest_risk.get('alertas_criticas', 0), 0)} | altas={format_metric(highest_risk.get('alertas_altas', 0), 0)}"
        )

    lines.append(f"- Sesiones solo serial: {len(serial_only)}")
    lines.append(f"- Sesiones PCAP + ETL: {len(pcap_etl)}")
    lines.append(f"- Sesiones con PCAP sin serial (todas las variantes): {len(pcap_without_serial)}")
    lines.append(f"- Sesiones baseline-only: {len(baseline_only)}")

    return "\n".join(lines)


def _to_float(value, default: float = 0.0) -> float:
    if value in ("", None):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def get_capture_topology_type(row: dict) -> str:
    if row.get("session_type") == "baseline_only":
        return "Baseline"

    has_serial = bool(row.get("has_serial"))
    has_pcap = bool(row.get("has_pcap"))
    has_antenna_udp = bool(row.get("has_antenna_udp"))
    has_etl = bool(row.get("has_etl"))

    if has_serial and has_pcap:
        return "SERIAL + PCAP"
    if has_pcap and has_antenna_udp:
        return "Antena + PCAP"
    if has_pcap and has_etl:
        return "PCAP + ETL"
    if has_pcap:
        return "PCAP solo"
    return "Otros"


def build_sample_type_counts(rows: list[dict]) -> dict:
    counts = {
        "SERIAL + PCAP": 0,
        "Antena + PCAP": 0,
        "PCAP + ETL": 0,
        "PCAP solo": 0,
        "Baseline": 0,
        "Otros": 0,
    }
    for row in rows:
        counts[get_capture_topology_type(row)] += 1
    return counts


def build_artifact_counts(rows: list[dict]) -> dict:
    return {
        "Baseline": sum(1 for row in rows if row.get("has_baseline")),
        "PCAP": sum(1 for row in rows if row.get("has_pcap")),
        "Antena + PCAP": sum(1 for row in rows if get_capture_topology_type(row) == "Antena + PCAP"),
        "ETL de captura": sum(1 for row in rows if row.get("has_etl")),
        "Serial": sum(1 for row in rows if row.get("has_serial")),
        "Correlacion efectiva": sum(1 for row in rows if row.get("has_correlation")),
    }


def build_sample_type_guide_text() -> str:
    return "\n".join(
        [
            "- Ordeno completo: sesion con serial y red del proceso de ordeno; es la base para tiempos, tandas, identificacion del tag de collar y flujo del ordeno.",
            "- Telemetria de collar: sesion orientada al canal de antena/collares; complementa el panorama de red, pero no debe forzarse como ordeno completo.",
            "- SERIAL + PCAP: sesion donde se conto con canal serial de la maquina de ordeno y PCAP al mismo tiempo.",
            "- Antena + PCAP: sesion con PCAP y con evidencia textual complementaria del canal de antena, por ejemplo antena_udp.txt.",
            "- PCAP + ETL: sesion con archivo PCAP acompanado por un .etl de captura del flujo historico de Windows.",
            "- PCAP solo: sesion donde hubo archivo PCAP, pero sin serial y sin evidencia textual complementaria del canal de antena; sigue siendo una captura valida en el esquema actual.",
            "- Baseline: sesion apoyada en artefactos de red (reporte, arp, ipconfig, rutas), sin captura serial ni PCAP.",
            "- Otros: sesiones que no entran en las cuatro clases principales; en la practica suelen corresponder a serial sin PCAP u otras variantes puntuales.",
        ]
    )


def build_sample_type_reconciliation_text(summary: dict, sample_type_counts: dict) -> str:
    serial_total = int(summary.get("sessions_with_serial", 0) or 0)
    pcap_total = int(summary.get("sessions_with_pcap", 0) or 0)
    corr_total = int(summary.get("sessions_with_correlation", 0) or 0)
    serial_pcap = int(sample_type_counts.get("SERIAL + PCAP", 0) or 0)
    antenna_pcap = int(sample_type_counts.get("Antena + PCAP", 0) or 0)
    pcap_etl = int(sample_type_counts.get("PCAP + ETL", 0) or 0)
    pcap_only = int(sample_type_counts.get("PCAP solo", 0) or 0)
    baseline_only = int(sample_type_counts.get("Baseline", 0) or 0)
    others = int(sample_type_counts.get("Otros", 0) or 0)
    serial_only = max(0, serial_total - serial_pcap)
    pcap_reconciled = serial_pcap + antenna_pcap + pcap_etl + pcap_only

    return "\n".join(
        [
            "- Conciliacion de PCAP: (SERIAL + PCAP) + (Antena + PCAP) + (PCAP + ETL) + (PCAP solo) = "
            f"{serial_pcap} + {antenna_pcap} + {pcap_etl} + {pcap_only} = {pcap_reconciled}.",
            "- Conciliacion de serial: sesiones con serial = SERIAL + PCAP + serial sin pcap = "
            f"{serial_pcap} + {serial_only} = {serial_total}.",
            "- Nota: 'Otros' recoge sesiones fuera de las cuatro clases principales; normalmente coinciden con serial sin pcap u otras variantes de captura.",
            f"- Baseline se cuenta aparte y representa {baseline_only} sesiones baseline-only.",
            f"- Sesiones con correlacion efectiva dentro del total SERIAL + PCAP: {corr_total}.",
        ]
    )


def get_plain_alert_type(rule: str) -> str:
    rule_text = str(rule).lower()
    mapping = [
        ("tormenta multicast", "Ruido de red por multidifusion"),
        ("tormenta broadcast", "Ruido de red por broadcast"),
        ("exceso de syn", "Intentos masivos de conexion"),
        ("rafaga de rst", "Conexiones rechazadas o reiniciadas"),
        ("conflicto arp", "Conflicto de identidad en la red"),
        ("una mac responde por varias ip", "Identidad de equipo ambigua"),
        ("salida a ip publica", "Salida fuera de la red local"),
        ("protocolo inseguro", "Uso de protocolo sin cifrado"),
        ("canal de telemetria no observado", "No se observo trafico biotico de antena"),
        ("canal presente pero sin payload", "Canal activo sin datos utiles"),
        ("firma 56 d1 00 no detectada", "No aparecio la firma biotica esperada"),
        ("tcp presente en el canal 6001", "Protocolo inesperado en canal biotico"),
        ("silencio prolongado del canal de telemetria", "Huecos prolongados en el canal biotico"),
    ]
    for needle, plain in mapping:
        if needle in rule_text:
            return plain
    return "Anomalia de trafico a revisar"


def get_row_alerts_path(row: dict) -> Path:
    return DATA_PROCESSED_DIR / "visits" / row["visit_name"] / "sesiones" / row["sample_id"] / "alerts.json"


def aggregate_pcap_alerts(rows: list[dict]) -> list[dict]:
    pcap_rules = {}
    layer_targets = {"pcap_general", "telemetry_6001"}

    for row in rows:
        alert_path = get_row_alerts_path(row)
        if not alert_path.exists():
            continue
        try:
            payload = json.loads(alert_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        for alert in payload.get("all", []):
            layer = alert.get("layer", "")
            if layer not in layer_targets:
                continue
            rule = alert.get("alert_name", alert.get("rule", "Alerta sin nombre"))
            item = pcap_rules.setdefault(
                rule,
                {
                    "rule": rule,
                    "count": 0,
                    "severity_counts": {"Critica": 0, "Alta": 0, "Media": 0, "Baja": 0, "Info": 0},
                    "impact": alert.get("impact", ""),
                    "severity_reason": alert.get("severity_reason", ""),
                },
            )
            severity = alert.get("severity", "Info")
            item["count"] += 1
            item["severity_counts"][severity] = item["severity_counts"].get(severity, 0) + 1

    ordered = []
    severity_rank = {"Critica": 0, "Alta": 1, "Media": 2, "Baja": 3, "Info": 4}
    for data in pcap_rules.values():
        dominant = sorted(
            data["severity_counts"].items(),
            key=lambda pair: (-pair[1], severity_rank.get(pair[0], 99)),
        )[0][0]
        ordered.append(
            {
                "rule": data["rule"],
                "count": data["count"],
                "dominant_severity": dominant,
                "impact": data["impact"],
                "severity_reason": data["severity_reason"],
            }
        )

    ordered.sort(key=lambda item: (-item["count"], severity_rank.get(item["dominant_severity"], 99), item["rule"]))
    return ordered


def build_pcap_alerts_plain_text(rows: list[dict], limit: int = 8) -> str:
    aggregated = aggregate_pcap_alerts(rows)
    if not aggregated:
        return "- En este lote no se registraron alertas provenientes del PCAP."

    lines = []
    for alert in aggregated[:limit]:
        lines.append(f"- Tipo de alerta: {get_plain_alert_type(alert['rule'])}")
        lines.append(f"  Nombre tecnico: {alert['rule']}")
        lines.append(f"  Frecuencia observada en el lote: {alert['count']} apariciones")
        lines.append(f"  Severidad dominante asignada: {alert['dominant_severity']}")
        lines.append(f"  Por que se marca: {alert['severity_reason'] or alert['impact'] or 'Impacto no documentado'}")

    if len(aggregated) > limit:
        lines.append(f"- ... {len(aggregated) - limit} tipos de alerta adicionales no se muestran en este resumen corto.")
    return "\n".join(lines)


def build_security_observations_text(summary: dict, sample_type_counts: dict) -> str:
    total_sessions = int(summary.get("total_sessions", 0) or 0)
    corr_sessions = int(summary.get("sessions_with_correlation", 0) or 0)
    total_alerts = int(summary.get("total_alertas", 0) or 0)
    critical_alerts = int(summary.get("total_alertas_criticas", 0) or 0)
    high_alerts = int(summary.get("total_alertas_altas", 0) or 0)
    antenna_pcap = int(sample_type_counts.get("Antena + PCAP", 0) or 0)
    pcap_etl = int(sample_type_counts.get("PCAP + ETL", 0) or 0)
    pcap_only = int(sample_type_counts.get("PCAP solo", 0) or 0)
    serial_pcap = int(sample_type_counts.get("SERIAL + PCAP", 0) or 0)
    baseline_only = int(sample_type_counts.get("Baseline", 0) or 0)

    corr_pct = (corr_sessions / total_sessions * 100.0) if total_sessions else 0.0
    high_critical_pct = ((critical_alerts + high_alerts) / total_alerts * 100.0) if total_alerts else 0.0

    lines = []
    if corr_sessions == 0:
        lines.append("- Correlacion serial-red: en este lote no hubo sesiones correlacionables; por prudencia no conviene extraer conclusiones causales fuertes.")
    else:
        lines.append(
            f"- Correlacion serial-red: {corr_sessions}/{total_sessions} sesiones ({corr_pct:.2f}%) aportan apoyo temporal util para el analisis."
        )

    if total_alerts == 0:
        lines.append("- Riesgo de red observado: no se registraron alertas en este lote.")
    else:
        lines.append(
            f"- Riesgo de red observado: {critical_alerts} criticas + {high_alerts} altas ({high_critical_pct:.2f}% de las alertas); conviene revisar estas sesiones primero."
        )

    if antenna_pcap == 0 and pcap_etl == 0 and pcap_only == 0:
        lines.append("- Cobertura del dominio PCAP: no se observan sesiones de antena, ni sesiones historicas PCAP + ETL, ni sesiones PCAP solo en este lote.")
    elif antenna_pcap == 0 and pcap_etl == 0 and pcap_only > 0:
        lines.append(
            f"- Cobertura del dominio PCAP: hay {pcap_only} sesiones PCAP solo; esto es compatible con el esquema actual de Linux donde la captura puede venir sin antena_udp.txt ni .etl."
        )
    else:
        lines.append(
            f"- Cobertura del dominio PCAP: {antenna_pcap} sesiones quedaron como Antena + PCAP, {pcap_etl} como PCAP + ETL y {pcap_only} como PCAP solo."
        )

    if serial_pcap == 0:
        lines.append("- Cobertura SERIAL + PCAP: nula; seria conveniente reforzar la captura simultanea para sostener mejor la trazabilidad.")
    else:
        lines.append(f"- Cobertura SERIAL + PCAP: {serial_pcap} sesiones permiten un analisis temporal conjunto mas confiable.")

    lines.append(
        f"- Baseline operacional: {baseline_only} sesiones baseline-only ayudan a documentar el estado de red como apoyo forense."
    )

    return "\n".join(lines)


def build_gateway_implications_text(summary: dict, sample_type_counts: dict) -> str:
    corr_sessions = int(summary.get("sessions_with_correlation", 0) or 0)
    critical_alerts = int(summary.get("total_alertas_criticas", 0) or 0)
    high_alerts = int(summary.get("total_alertas_altas", 0) or 0)
    antenna_pcap = int(sample_type_counts.get("Antena + PCAP", 0) or 0)

    lines = []
    lines.append("- Mantener separados los dominios de trabajo: canal de ordeno (serial) y canal biotico (antena/collares).")
    lines.append("- Definir allowlist de IP, puerto y protocolo para el canal biotico, con bloqueo del trafico lateral no esperado.")
    lines.append("- Organizar la telemetria en topicos MQTT separados por dominio para no mezclar significados de datos.")
    lines.append("- Registrar eventos con sello temporal y hash por sesion para conservar la trazabilidad forense.")

    if critical_alerts + high_alerts > 0:
        lines.append("- Prioridad alta: incluir reglas tempranas de mitigacion para ruido o anomalias de red desde el primer despliegue.")
    else:
        lines.append("- Prioridad media: mantener monitoreo continuo para detectar desviaciones tempranas en produccion.")

    if corr_sessions == 0:
        lines.append("- Antes de cerrar la siguiente etapa, conviene aumentar las sesiones SERIAL + PCAP simultaneas para validar sincronizacion.")

    if antenna_pcap == 0:
        lines.append("- Como verificacion funcional, hace falta confirmar que el gateway capture y preserve evidencia del canal biotico de antena.")

    return "\n".join(lines)


def build_obj1_characterization_summary(rows: list[dict]) -> dict:
    baseline_rows = [row for row in rows if row.get("has_baseline")]
    serial_rows = [row for row in rows if row.get("has_serial")]
    collar_rows = [row for row in rows if row.get("operation_mode") == "telemetria_collar"]
    field_rows = [row for row in rows if row.get("validacion_campo")]
    eta_rows = [row for row in rows if has_metric(row.get("eta_extraccion", ""))]
    latency_values = [float(row["lat_media"]) for row in baseline_rows if has_metric(row.get("lat_media", ""))]
    jitter_values = [float(row["jitter_ms"]) for row in baseline_rows if has_metric(row.get("jitter_ms", ""))]
    heartbeat_values = [float(row["cobertura_heartbeat_pct"]) for row in serial_rows if has_metric(row.get("cobertura_heartbeat_pct", ""))]
    eta_values = [float(row["eta_extraccion"]) for row in eta_rows if has_metric(row.get("eta_extraccion", ""))]
    multicast_values = [float(row["multicast_pct"]) for row in rows if has_metric(row.get("multicast_pct", ""))]

    return {
        "purpose": "caracterizacion_forense_objetivo_1",
        "sessions_useful_for_baseline": len(baseline_rows),
        "sessions_useful_for_serial_signatures": len(serial_rows),
        "sessions_useful_for_collar_telemetry": len(collar_rows),
        "sessions_useful_for_direct_eta": len(eta_rows),
        "sessions_with_field_validation": len(field_rows),
        "avg_latency_baseline_ms": safe_average(latency_values),
        "avg_jitter_baseline_ms": safe_average(jitter_values),
        "avg_heartbeat_coverage_pct": safe_average(heartbeat_values),
        "avg_eta_direct_pct": safe_average(eta_values),
        "avg_multicast_pct": safe_average(multicast_values),
        "supports_latency_jitter_baseline": bool(baseline_rows),
        "supports_serial_signature_characterization": bool(serial_rows),
        "supports_udp_exposure_characterization": any(row.get("has_antenna_udp") or row.get("has_pcap") for row in rows),
        "supports_direct_eta_estimation": bool(eta_rows),
        "supports_field_contrast": bool(field_rows),
        "notes": [
            "El motor modular se usa como instrumento forense de caracterizacion del Objetivo 1.",
            "La estimacion directa de eta solo se considera defendible cuando hubo evidencia simultanea suficiente.",
            "Las sesiones de ordeno completo y las de telemetria de collar se interpretan por separado.",
        ],
    }


def build_obj1_characterization_text(obj1: dict) -> str:
    support_eta = "Si" if obj1.get("supports_direct_eta_estimation") else "No"
    support_field = "Si" if obj1.get("supports_field_contrast") else "No"
    return f"""
- Proposito: caracterizacion forense y linea base del Objetivo 1.
- Sesiones utiles para baseline de red: {obj1.get('sessions_useful_for_baseline', 0)}
- Sesiones utiles para firmas seriales: {obj1.get('sessions_useful_for_serial_signatures', 0)}
- Sesiones utiles para telemetria de collar: {obj1.get('sessions_useful_for_collar_telemetry', 0)}
- Sesiones con validacion de campo: {obj1.get('sessions_with_field_validation', 0)}
- Sesiones con soporte para eta directa: {obj1.get('sessions_useful_for_direct_eta', 0)}
- Latencia baseline promedio: {format_metric(obj1.get('avg_latency_baseline_ms'))}
- Jitter baseline promedio: {format_metric(obj1.get('avg_jitter_baseline_ms'))}
- Cobertura heartbeat promedio: {format_metric(obj1.get('avg_heartbeat_coverage_pct'), 2)}
- Eta directa promedio: {format_metric(obj1.get('avg_eta_direct_pct'), 2)}
- Multicast promedio: {format_metric(obj1.get('avg_multicast_pct'), 2)}
- Hay soporte defendible para eta directa: {support_eta}
- Hay contraste con campo: {support_field}
""".strip()


def build_human_summary_text(scope_name: str, summary: dict, sample_type_counts: dict) -> str:
    total_sessions = int(summary.get("total_sessions", 0) or 0)
    total_visits = summary.get("total_visits")
    total_alerts = int(summary.get("total_alertas", 0) or 0)
    critical_alerts = int(summary.get("total_alertas_criticas", 0) or 0)
    high_alerts = int(summary.get("total_alertas_altas", 0) or 0)
    serial_sessions = int(summary.get("sessions_with_serial", 0) or 0)
    pcap_sessions = int(summary.get("sessions_with_pcap", 0) or 0)
    corr_sessions = int(summary.get("sessions_with_correlation", 0) or 0)
    antenna_pcap = int(sample_type_counts.get("Antena + PCAP", 0) or 0)
    pcap_etl = int(sample_type_counts.get("PCAP + ETL", 0) or 0)
    pcap_only = int(sample_type_counts.get("PCAP solo", 0) or 0)
    baseline_only = int(sample_type_counts.get("Baseline", 0) or 0)
    obj1 = summary.get("objective_1_characterization", {})

    visit_line = ""
    if total_visits is not None:
        visit_line = f"- Visitas incluidas: {total_visits}\n"

    if critical_alerts + high_alerts == 0:
        risk_line = "- No se observaron alertas altas o criticas en este conjunto.\n"
    else:
        risk_line = (
            f"- Se observaron {critical_alerts} alertas criticas y {high_alerts} alertas altas. "
            "Eso sugiere condiciones de red que conviene revisar con prioridad.\n"
        )

    if corr_sessions == 0:
        corr_line = "- No hubo sesiones suficientes con serial y PCAP al mismo tiempo para una correlacion temporal fuerte.\n"
    else:
        corr_line = f"- Hubo {corr_sessions} sesiones con correlacion efectiva entre serial y PCAP.\n"

    return f"""
RESUMEN EN LENGUAJE CLARO
=========================

Conjunto analizado: {scope_name}

1. Que se proceso
{visit_line}- Sesiones totales: {total_sessions}
- Sesiones con PCAP: {pcap_sessions}
- Sesiones con serial: {serial_sessions}
- Sesiones baseline-only: {baseline_only}

2. Como se repartieron las capturas PCAP
- Antena + PCAP: {antenna_pcap}
- PCAP + ETL: {pcap_etl}
- PCAP solo: {pcap_only}

3. Lectura sencilla del resultado
{risk_line}{corr_line}- Se registraron {total_alerts} alertas en total.
- La latencia media promedio fue de {format_metric(summary.get('avg_lat_media'))} ms.

4. Que significa esto en palabras simples
- El lote si aporta evidencia util para documentar el estado de la red y del sistema.
- Sin embargo, no todas las sesiones sirven igual para correlacionar causas entre maquina, antena y red.
- Las sesiones con PCAP permiten revisar trafico, pero las sesiones con serial + PCAP son las mas valiosas para explicar sincronizacion y trazabilidad temporal.
- Las sesiones baseline ayudan a comparar el entorno antes o despues de la captura activa.
- Para el Objetivo 1, este conjunto aporta {obj1.get('sessions_useful_for_baseline', 0)} sesiones utiles para baseline, {obj1.get('sessions_useful_for_serial_signatures', 0)} para firmas seriales y {obj1.get('sessions_useful_for_direct_eta', 0)} con soporte directo para eta.

5. Recomendacion de lectura
- Si la persona que revisa no es tecnica, conviene empezar por las alertas criticas y altas.
- Si el objetivo es explicar el problema del sistema, conviene revisar primero las sesiones con SERIAL + PCAP.
- Si el objetivo es ver evolucion historica del muestreo, conviene distinguir PCAP + ETL del flujo antiguo y PCAP solo del flujo mas reciente.
""".strip()


def build_risk_control_checklist_text(summary: dict, sample_type_counts: dict) -> str:
    headers = ["Riesgo Actual", "Evidencia en Lote", "Control Futuro (Gateway)", "Prioridad"]
    widths = [28, 32, 48, 9]

    total_sessions = int(summary.get("total_sessions", 0) or 0)
    corr_sessions = int(summary.get("sessions_with_correlation", 0) or 0)
    critical_alerts = int(summary.get("total_alertas_criticas", 0) or 0)
    high_alerts = int(summary.get("total_alertas_altas", 0) or 0)
    antenna_pcap = int(sample_type_counts.get("Antena + PCAP", 0) or 0)
    serial_pcap = int(sample_type_counts.get("SERIAL + PCAP", 0) or 0)
    baseline_only = int(sample_type_counts.get("Baseline", 0) or 0)

    rows = [
        [
            "Ruido y anomalia de red",
            f"{critical_alerts} criticas y {high_alerts} altas",
            "ACL/VLAN + reglas de prioridad + bloqueo de trafico no esperado.",
            "Alta",
        ],
        [
            "Baja correlacion temporal",
            f"{corr_sessions}/{total_sessions} sesiones correlacionables",
            "Captura simultanea serial+pcap y sincronizacion temporal obligatoria.",
            "Alta",
        ],
        [
            "Cobertura biotica parcial",
            f"{antenna_pcap} sesiones Antena+PCAP",
            "Pipeline dedicado del canal biotico con validaciones de continuidad.",
            "Media",
        ],
        [
            "Evidencia operativa dispersa",
            f"{baseline_only} sesiones Baseline",
            "Consolidacion automatica por visita y hashes por sesion.",
            "Media",
        ],
        [
            "Interoperabilidad en transicion",
            f"{serial_pcap} sesiones SERIAL+PCAP",
            "Modelo de datos unificado para migracion controlada a MQTT.",
            "Media",
        ],
    ]
    return build_text_table(headers, rows, widths)


def get_visit_processed_sessions_dir(visit_name: str) -> Path:
    return ensure_dir(DATA_PROCESSED_DIR / "visits" / visit_name / "sesiones")


def get_visit_processed_summary_dir(visit_name: str) -> Path:
    return ensure_dir(DATA_PROCESSED_DIR / "visits" / visit_name / "resumen")


def get_visit_report_hourly_dir(visit_name: str) -> Path:
    return ensure_dir(REPORTS_DIR / "visits" / visit_name / "por_hora")


def get_visit_report_summary_dir(visit_name: str) -> Path:
    return ensure_dir(REPORTS_DIR / "visits" / visit_name / "resumen")


def get_global_processed_summary_dir(run_name: str | None = None) -> Path:
    base_dir = ensure_dir(DATA_PROCESSED_DIR / "global" / "resumen_arbol")
    if not run_name:
        return base_dir
    return ensure_dir(base_dir / run_name)


def get_global_report_summary_dir(run_name: str | None = None) -> Path:
    base_dir = ensure_dir(REPORTS_DIR / "global" / "resumen_arbol")
    if not run_name:
        return base_dir
    return ensure_dir(base_dir / run_name)


def get_session_processed_dir(visit_name: str, sample_id: str) -> Path:
    return get_visit_processed_sessions_dir(visit_name) / sample_id


def normalize_run_name(text: str) -> str:
    safe_text = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in str(text).strip())
    safe_text = safe_text.strip("_")
    return safe_text or "lote"


def build_batch_run_name(root_dirs: list[Path], requested_name: str | None = None) -> str:
    if requested_name:
        return normalize_run_name(requested_name)
    if len(root_dirs) == 1:
        return normalize_run_name(root_dirs[0].name)
    return normalize_run_name(f"lote_{len(root_dirs)}_raices")


def build_roots_description(root_dirs: list[Path]) -> str:
    return "\n".join(f"- {root_dir}" for root_dir in root_dirs)


def discover_sessions_from_roots(root_dirs: list[Path]) -> list[dict]:
    deduped_sessions: dict[str, dict] = {}

    for root_dir in root_dirs:
        resolved_root = root_dir.resolve()
        if not resolved_root.exists():
            raise SystemExit(f"No existe la ruta raiz: {resolved_root}")

        capture_sessions = discover_sessions(resolved_root)
        baseline_only_sessions = discover_baseline_only_sessions(resolved_root)

        for session in [*capture_sessions, *baseline_only_sessions]:
            capture_key = str(Path(session["capture_dir"]).resolve()).lower()
            deduped_sessions.setdefault(capture_key, session)

    sessions = list(deduped_sessions.values())
    sessions.sort(key=lambda row: (row.get("visit_name", ""), str(row.get("capture_dir", ""))))
    return sessions


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Herramienta modular de apoyo analitico para FincaDiag")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--sample", help="Ruta a una carpeta Captura_*")
    target.add_argument("--root", help="Ruta raiz para descubrir y procesar varias capturas")
    target.add_argument("--roots", nargs="+", help="Lista de rutas raiz especificas para procesar en un mismo lote")
    parser.add_argument("--target-ip", default=DEFAULT_TARGET_IP, help="IP objetivo de antena o gateway")
    parser.add_argument("--target-port", type=int, default=DEFAULT_TARGET_PORT, help="Puerto de telemetria")
    parser.add_argument("--signature", default=DEFAULT_SIGNATURE, help="Firma de red en hexadecimal")
    parser.add_argument("--window-ms", type=int, default=DEFAULT_WINDOW_MS, help="Ventana de correlacion en ms")
    parser.add_argument("--run-name", help="Nombre opcional para el consolidado global del lote")
    parser.add_argument("--dry-run", action="store_true", help="Solo listar sesiones detectadas y baseline asociado")
    return parser


def safe_average(values: list[float]) -> float:
    if not values:
        return None
    return round(sum(values) / len(values), 3)


def _read_capture_manifest_fields(capture_dir: Path) -> dict:
    manifest_path = capture_dir / "capture_manifest.json"
    if not manifest_path.exists():
        return {
            "capture_started_at": "",
            "capture_ended_at": "",
            "capture_duration_seconds": "",
            "capture_requested_seconds": "",
            "capture_stop_reason": "",
            "capture_mode": "",
        }

    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "capture_started_at": "",
            "capture_ended_at": "",
            "capture_duration_seconds": "",
            "capture_requested_seconds": "",
            "capture_stop_reason": "",
            "capture_mode": "",
        }

    return {
        "capture_started_at": raw.get("started_at", "") or "",
        "capture_ended_at": raw.get("ended_at", "") or "",
        "capture_duration_seconds": raw.get("duration_seconds", ""),
        "capture_requested_seconds": raw.get("requested_seconds", ""),
        "capture_stop_reason": raw.get("stop_reason", "") or "",
        "capture_mode": raw.get("mode", "") or "",
    }


def _safe_dt_from_iso(value: str) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _build_logical_visit_groups(visit_data: list[dict], merge_gap_seconds: int = 300) -> list[list[dict]]:
    baseline_only = [row for row in visit_data if row.get("session_type") == "baseline_only"]
    captures = [row for row in visit_data if row.get("session_type") != "baseline_only"]

    block_dir_pattern = re.compile(r".+_\d{8}_\d{4}$")

    def block_key(row: dict) -> str:
        capture_dir = str(row.get("capture_dir", "") or "")
        if not capture_dir:
            return ""
        try:
            parent = Path(capture_dir).parent
        except Exception:
            return ""

        name = parent.name
        if not name or name.startswith(("Captura_", "Baseline_")):
            return ""
        if not block_dir_pattern.fullmatch(name):
            return ""
        return str(parent)

    def sort_key(row: dict):
        dt = _safe_dt_from_iso(str(row.get("capture_started_at", "")))
        return (dt or datetime.min, str(row.get("capture_dir", "")))

    captures = sorted(captures, key=sort_key)

    groups: list[list[dict]] = [[row] for row in baseline_only]
    current: list[dict] = []

    def should_merge(prev: dict, nxt: dict) -> bool:
        if not prev or not nxt:
            return False

        if str(prev.get("operation_mode", "")) != str(nxt.get("operation_mode", "")):
            return False

        # Raspberry scheduler case:
        # FincaScheduler ejecuta varios intentos dentro de una carpeta de bloque
        # (ej: ordeno_am_YYYYMMDD_HHMM). En ese caso NO hay un gap fijo, y
        # cada intento puede terminar con stop_reason="completed" aunque la fase
        # global del bloque siga pendiente.
        prev_block = block_key(prev)
        nxt_block = block_key(nxt)
        if prev_block and prev_block == nxt_block:
            return True

        prev_end = _safe_dt_from_iso(str(prev.get("capture_ended_at", "")))
        nxt_start = _safe_dt_from_iso(str(nxt.get("capture_started_at", "")))
        if prev_end is None or nxt_start is None:
            return False

        gap = (nxt_start - prev_end).total_seconds()
        if gap < 0 or gap > merge_gap_seconds:
            return False

        prev_stop = str(prev.get("capture_stop_reason", "") or "").strip().lower()
        return prev_stop not in ("completed", "completado")

    for row in captures:
        if not current:
            current = [row]
            continue
        if should_merge(current[-1], row):
            current.append(row)
        else:
            groups.append(current)
            current = [row]

    if current:
        groups.append(current)
    return groups


def build_visit_row(visit_name: str, visit_data: list[dict]) -> dict:
    logical_groups = _build_logical_visit_groups(visit_data)
    def group_any(key: str) -> int:
        return sum(1 for group in logical_groups if any(bool(row.get(key)) for row in group))

    lat_values = [float(row["lat_media"]) for row in visit_data if has_metric(row["lat_media"])]
    eta_values = [float(row["eta_extraccion"]) for row in visit_data if has_metric(row["eta_extraccion"])]
    delta_values = [float(row["desfase_medio_ms"]) for row in visit_data if has_metric(row["desfase_medio_ms"])]
    multicast_values = [float(row["multicast_pct"]) for row in visit_data if has_metric(row["multicast_pct"])]
    return ensure_visit_row_schema(
        {
            "visit_name": visit_name,
            "total_sessions": len(logical_groups),
            "sessions_baseline_only": sum(1 for group in logical_groups if any(row.get("session_type") == "baseline_only" for row in group)),
            "sessions_with_baseline": group_any("has_baseline"),
            "sessions_with_serial": group_any("has_serial"),
            "sessions_with_antenna_udp": group_any("has_antenna_udp"),
            "sessions_with_etl": group_any("has_etl"),
            "sessions_with_pcap": group_any("has_pcap"),
            "sessions_with_correlation": group_any("has_correlation"),
            "total_alertas": sum(int(row.get("alertas_totales", 0) or 0) for row in visit_data),
            "total_alertas_criticas": sum(int(row.get("alertas_criticas", 0) or 0) for row in visit_data),
            "total_alertas_altas": sum(int(row.get("alertas_altas", 0) or 0) for row in visit_data),
            "avg_lat_media": safe_average(lat_values),
            "avg_eta_extraccion": safe_average(eta_values),
            "avg_desfase_medio_ms": safe_average(delta_values),
            "avg_multicast_pct": safe_average(multicast_values),
        }
    )


def ensure_visit_row_schema(row: dict) -> dict:
    normalized = dict(row)
    defaults = {
        "visit_name": "",
        "total_sessions": 0,
        "sessions_with_pcap": 0,
        "sessions_with_serial": 0,
        "sessions_with_antenna_udp": 0,
        "sessions_with_baseline": 0,
        "total_alertas_altas": 0,
        "total_alertas_criticas": 0,
        "avg_eta_extraccion": 0.0,
        "avg_desfase_medio_ms": 0.0,
        "avg_multicast_pct": 0.0,
        "avg_lat_media": 0.0,
    }
    for key, default in defaults.items():
        value = normalized.get(key)
        if value in ("", None):
            normalized[key] = default
    return normalized


def build_correlacion_global_rows(rows: list[dict]) -> list[dict]:
    correlation_rows = []
    for row in sort_session_rows(rows):
        matches_path = get_session_processed_dir(row["visit_name"], row["sample_id"]) / "correlation_matches.csv"
        if not matches_path.exists():
            continue
        with matches_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for match in reader:
                correlation_rows.append(
                    {
                        "timestamp_serial": match.get("timestamp_serial", match.get("serial_timestamp", "")),
                        "delta_ms": match.get("delta_ms", ""),
                        "serial_event": match.get("serial_event", ""),
                        "abs_delta_ms": match.get("abs_delta_ms", ""),
                        "matched": match.get("matched", ""),
                    }
                )
    return correlation_rows


def ensure_registro_muestras_schema(conn: sqlite3.Connection) -> None:
    cursor = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='registro_muestras'"
    )
    exists = bool(cursor.fetchone())
    if not exists:
        return

    table_info = list(conn.execute("PRAGMA table_info(registro_muestras)"))
    current_cols = {row[1] for row in table_info}
    pk_cols = [row[1] for row in table_info if int(row[5] or 0) > 0]
    id_muestra_type = ""
    for row in table_info:
        if row[1] == "id_muestra":
            id_muestra_type = str(row[2] or "")
            break

    needs_rebuild = False
    if pk_cols and pk_cols != ["id_muestra"]:
        needs_rebuild = True
    if id_muestra_type and id_muestra_type.upper() != "TEXT":
        needs_rebuild = True

    if needs_rebuild:
        conn.execute("ALTER TABLE registro_muestras RENAME TO registro_muestras_old")
        conn.execute(
            """
            CREATE TABLE registro_muestras (
                fecha TEXT,
                id_muestra TEXT PRIMARY KEY,
                lat_media REAL,
                jitter_ms REAL,
                packet_loss REAL,
                nodos_dinamicos INTEGER,
                score_ids REAL,
                eventos_fc INTEGER,
                eventos_fe INTEGER,
                firmas_56d100 INTEGER,
                eventos_red INTEGER,
                eventos_correlacionados INTEGER,
                desfase_medio_ms REAL,
                desfase_max_ms REAL,
                multicast_pct REAL,
                eta_extraccion REAL,
                eventos_vaca INTEGER,
                eventos_sin_rfid INTEGER,
                muestras_flujo INTEGER,
                observacion_tecnica TEXT
            )
            """
        )
        old_cols = {row[1] for row in conn.execute("PRAGMA table_info(registro_muestras_old)")}
        common = [
            col
            for col in [
                "fecha",
                "lat_media",
                "jitter_ms",
                "packet_loss",
                "nodos_dinamicos",
                "score_ids",
                "eventos_fc",
                "eventos_fe",
                "firmas_56d100",
                "eventos_red",
                "eventos_correlacionados",
                "desfase_medio_ms",
                "desfase_max_ms",
                "multicast_pct",
                "eta_extraccion",
                "eventos_vaca",
                "eventos_sin_rfid",
                "muestras_flujo",
                "observacion_tecnica",
            ]
            if col in old_cols
        ]
        select_cols = ", ".join(common) if common else ""
        insert_cols = ("id_muestra" + (", " + ", ".join(common) if common else ""))
        select_expr = ("CAST(id_muestra AS TEXT)" + (", " + select_cols if select_cols else ""))
        conn.execute(
            f"INSERT OR IGNORE INTO registro_muestras ({insert_cols}) SELECT {select_expr} FROM registro_muestras_old"
        )
        conn.execute("DROP TABLE registro_muestras_old")
        table_info = list(conn.execute("PRAGMA table_info(registro_muestras)"))
        current_cols = {row[1] for row in table_info}
    desired = {
        "fecha": "TEXT",
        "id_muestra": "TEXT",
        "lat_media": "REAL",
        "jitter_ms": "REAL",
        "packet_loss": "REAL",
        "nodos_dinamicos": "INTEGER",
        "score_ids": "REAL",
        "eventos_fc": "INTEGER",
        "eventos_fe": "INTEGER",
        "firmas_56d100": "INTEGER",
        "eventos_red": "INTEGER",
        "eventos_correlacionados": "INTEGER",
        "desfase_medio_ms": "REAL",
        "desfase_max_ms": "REAL",
        "multicast_pct": "REAL",
        "eta_extraccion": "REAL",
        "eventos_vaca": "INTEGER",
        "eventos_sin_rfid": "INTEGER",
        "muestras_flujo": "INTEGER",
        "observacion_tecnica": "TEXT",
    }
    missing = [name for name in desired.keys() if name not in current_cols]
    for col in missing:
        col_type = desired[col]
        conn.execute(f"ALTER TABLE registro_muestras ADD COLUMN {col} {col_type}")


def auto_save_to_db(session_result: dict, db_path: str) -> None:
    db_file = Path(db_path)
    ensure_dir(db_file.parent)
    values = {
        "lat_media": session_result.get("lat_media", -1),
        "jitter_ms": session_result.get("jitter_ms", -1),
        "packet_loss": session_result.get("packet_loss", -1),
        "eventos_fc": session_result.get("fc_count", -1),
        "eventos_fe": session_result.get("fe_count", -1),
        "firmas_56d100": session_result.get("signature_count", -1),
        "eventos_correlacionados": session_result.get("matched_events", -1),
        "desfase_medio_ms": session_result.get("desfase_medio_ms", -1),
        "desfase_max_ms": session_result.get("desfase_max_ms", -1),
        "multicast_pct": session_result.get("multicast_pct", -1),
        "eta_extraccion": session_result.get("eta_extraccion", -1),
        "eventos_vaca": session_result.get("vaca_count", -1),
        "eventos_sin_rfid": session_result.get("sin_rfid_count", -1),
        "muestras_flujo": session_result.get("flujo_count", -1),
    }
    with sqlite3.connect(db_file) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS registro_muestras (
                fecha TEXT,
                id_muestra TEXT PRIMARY KEY,
                lat_media REAL,
                jitter_ms REAL,
                packet_loss REAL,
                nodos_dinamicos INTEGER,
                score_ids REAL,
                eventos_fc INTEGER,
                eventos_fe INTEGER,
                firmas_56d100 INTEGER,
                eventos_red INTEGER,
                eventos_correlacionados INTEGER,
                desfase_medio_ms REAL,
                desfase_max_ms REAL,
                multicast_pct REAL,
                eta_extraccion REAL,
                eventos_vaca INTEGER,
                eventos_sin_rfid INTEGER,
                muestras_flujo INTEGER,
                observacion_tecnica TEXT
            )
            """
        )
        ensure_registro_muestras_schema(conn)
        conn.execute(
            """
            INSERT INTO registro_muestras (
                fecha, id_muestra, lat_media, jitter_ms, packet_loss, nodos_dinamicos, score_ids,
                eventos_fc, eventos_fe, firmas_56d100, eventos_red, eventos_correlacionados,
                desfase_medio_ms, desfase_max_ms, multicast_pct, eta_extraccion,
                eventos_vaca, eventos_sin_rfid, muestras_flujo, observacion_tecnica
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id_muestra) DO UPDATE SET
                fecha=excluded.fecha,
                lat_media=excluded.lat_media,
                jitter_ms=excluded.jitter_ms,
                packet_loss=excluded.packet_loss,
                nodos_dinamicos=excluded.nodos_dinamicos,
                score_ids=excluded.score_ids,
                eventos_fc=excluded.eventos_fc,
                eventos_fe=excluded.eventos_fe,
                firmas_56d100=excluded.firmas_56d100,
                eventos_red=excluded.eventos_red,
                eventos_correlacionados=excluded.eventos_correlacionados,
                desfase_medio_ms=excluded.desfase_medio_ms,
                desfase_max_ms=excluded.desfase_max_ms,
                multicast_pct=excluded.multicast_pct,
                eta_extraccion=excluded.eta_extraccion,
                eventos_vaca=excluded.eventos_vaca,
                eventos_sin_rfid=excluded.eventos_sin_rfid,
                muestras_flujo=excluded.muestras_flujo,
                observacion_tecnica=excluded.observacion_tecnica
            """,
            (
                datetime.now().isoformat(timespec="seconds"),
                session_result.get("sample_id", ""),
                values["lat_media"],
                values["jitter_ms"],
                values["packet_loss"],
                session_result.get("nodos_dinamicos", -1),
                -1,
                values["eventos_fc"],
                values["eventos_fe"],
                values["firmas_56d100"],
                session_result.get("eventos_red", -1),
                values["eventos_correlacionados"],
                values["desfase_medio_ms"],
                values["desfase_max_ms"],
                values["multicast_pct"],
                values["eta_extraccion"],
                values["eventos_vaca"],
                values["eventos_sin_rfid"],
                values["muestras_flujo"],
                session_result.get("obj1_role", ""),
            ),
        )
        conn.commit()


def validate_outputs(output_dir: Path, label: str) -> list[str]:
    issues = []
    required = [
        f"{label}_summary.json",
        f"{label}_visits.csv",
        f"{label}_sessions.csv",
        f"{label}_correlacion_global.csv",
        f"{label}_obj1_profiles.json",
        f"{label}_gateway_readiness.json",
    ]
    for filename in required:
        if not (output_dir / filename).exists():
            issues.append(f"FALTA ARCHIVO: {filename}")

    visits_path = output_dir / f"{label}_visits.csv"
    if visits_path.exists():
        with visits_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            columns = reader.fieldnames or []
        for column in REQUIRED_VISIT_COLS:
            if column not in columns:
                issues.append(f"COLUMNA FALTANTE en visits.csv: {column}")

    corr_path = output_dir / f"{label}_correlacion_global.csv"
    if corr_path.exists():
        with corr_path.open("r", newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            columns = reader.fieldnames or []
        for column in CORRELACION_COLS.keys():
            if column not in columns:
                issues.append(f"COLUMNA FALTANTE en correlacion_global.csv: {column}")

    summary_path = output_dir / f"{label}_summary.json"
    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(f"JSON INVALIDO en summary.json: {exc}")
            summary = {}
        for key in REQUIRED_GLOBAL_SUMMARY_KEYS:
            if key not in summary:
                issues.append(f"CLAVE FALTANTE en summary.json: {key}")
        sample_type_counts = summary.get("sample_type_counts", {})
        for key in REQUIRED_SAMPLE_TYPE_KEYS:
            if key not in sample_type_counts:
                issues.append(f"CLAVE FALTANTE en sample_type_counts: {key}")

    readiness_path = output_dir / f"{label}_gateway_readiness.json"
    if readiness_path.exists():
        try:
            readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        except Exception as exc:
            issues.append(f"JSON INVALIDO en gateway_readiness.json: {exc}")
            readiness = {}
        if readiness.get("stage") not in {"caracterizacion", "hardware", "gateway", "validacion"}:
            issues.append("VALOR INVALIDO en gateway_readiness.json: stage")
        for key in (
            "baseline_red_definido",
            "firmas_seriales_disponibles",
            "dominio_collar_observable",
            "contraste_campo_disponible",
            "eta_directa_consolidada",
            "pcap_parseado_disponible",
            "linea_base_inicial_defendible",
        ):
            if key not in readiness.get("checks", {}):
                issues.append(f"CHECK FALTANTE en gateway_readiness.json: {key}")

    return issues


OBJ1_PHASES = [
    {
        "key": "fase_inicial_exploratoria",
        "label": "Fase inicial exploratoria",
        "start": date(2026, 2, 23),
        "end": date(2026, 3, 13),
        "recommended_for": "latencia y jitter tempranos; firmas seriales iniciales; evidencia historica PCAP+ETL",
    },
    {
        "key": "fase_transicion_red",
        "label": "Fase de transicion de red",
        "start": date(2026, 3, 14),
        "end": date(2026, 3, 31),
        "recommended_for": "maduracion de baseline, crecimiento de PCAP y exposicion del dominio biotico",
    },
    {
        "key": "fase_madura_operativa",
        "label": "Fase madura operativa",
        "start": date(2026, 4, 1),
        "end": date(2026, 4, 5),
        "recommended_for": "captura simultanea mas estable y ajuste del motor operativo",
    },
    {
        "key": "fase_validada_campo",
        "label": "Fase validada en campo",
        "start": date(2026, 4, 6),
        "end": date(2026, 4, 9),
        "recommended_for": "contraste con observacion presencial y depuracion semantica del motor",
    },
]


def parse_visit_date(visit_name: str) -> date | None:
    try:
        _, dd, mm, yyyy = str(visit_name).split("_")
        return datetime.strptime(f"{dd}_{mm}_{yyyy}", "%d_%m_%Y").date()
    except Exception:
        return None


def build_obj1_phase_profile(rows: list[dict], phase: dict) -> dict:
    phase_rows = []
    phase_visits = set()
    for row in rows:
        visit_dt = parse_visit_date(row.get("visit_name", ""))
        if not visit_dt:
            continue
        if phase["start"] <= visit_dt <= phase["end"]:
            phase_rows.append(row)
            phase_visits.add(row.get("visit_name", ""))

    baseline_rows = [row for row in phase_rows if row.get("has_baseline")]
    serial_rows = [row for row in phase_rows if row.get("has_serial")]
    collar_rows = [row for row in phase_rows if row.get("operation_mode") == "telemetria_collar"]
    parsed_pcap_rows = [row for row in phase_rows if row.get("pcap_parsed")]
    field_rows = [row for row in phase_rows if row.get("validacion_campo")]
    eta_rows = [row for row in phase_rows if has_metric(row.get("eta_extraccion", ""))]

    latency_values = [float(row["lat_media"]) for row in baseline_rows if has_metric(row.get("lat_media", ""))]
    jitter_values = [float(row["jitter_ms"]) for row in baseline_rows if has_metric(row.get("jitter_ms", ""))]
    heartbeat_values = [float(row["cobertura_heartbeat_pct"]) for row in serial_rows if has_metric(row.get("cobertura_heartbeat_pct", ""))]
    eta_values = [float(row["eta_extraccion"]) for row in eta_rows if has_metric(row.get("eta_extraccion", ""))]
    multicast_values = [float(row["multicast_pct"]) for row in phase_rows if has_metric(row.get("multicast_pct", ""))]
    packet_rate_values = [float(row["packet_rate_hz"]) for row in phase_rows if has_metric(row.get("packet_rate_hz", ""))]
    multicast_rate_values = [float(row["multicast_rate_hz"]) for row in phase_rows if has_metric(row.get("multicast_rate_hz", ""))]

    return {
        "key": phase["key"],
        "label": phase["label"],
        "start": phase["start"].isoformat(),
        "end": phase["end"].isoformat(),
        "visit_count": len(phase_visits),
        "session_count": len(phase_rows),
        "baseline_sessions": len(baseline_rows),
        "serial_sessions": len(serial_rows),
        "collar_sessions": len(collar_rows),
        "parsed_pcap_sessions": len(parsed_pcap_rows),
        "field_validation_sessions": len(field_rows),
        "direct_eta_sessions": len(eta_rows),
        "avg_latency_baseline_ms": safe_average(latency_values),
        "avg_jitter_baseline_ms": safe_average(jitter_values),
        "avg_heartbeat_coverage_pct": safe_average(heartbeat_values),
        "avg_eta_direct_pct": safe_average(eta_values),
        "avg_multicast_pct": safe_average(multicast_values),
        "avg_packet_rate_hz": safe_average(packet_rate_values),
        "avg_multicast_rate_hz": safe_average(multicast_rate_values),
        "recommended_for": phase["recommended_for"],
        "supports_latency_jitter": bool(latency_values),
        "supports_serial_semantics": bool(serial_rows),
        "supports_udp_exposure": bool(collar_rows or parsed_pcap_rows),
        "supports_direct_eta": bool(eta_rows),
        "supports_field_contrast": bool(field_rows),
    }


def build_obj1_profiles(rows: list[dict]) -> dict:
    profiles = [build_obj1_phase_profile(rows, phase) for phase in OBJ1_PHASES]
    initial = next((profile for profile in profiles if profile["key"] == "fase_inicial_exploratoria"), {})
    validated = next((profile for profile in profiles if profile["key"] == "fase_validada_campo"), {})
    return {
        "profiles": profiles,
        "cap1_cap2_recommendation": {
            "use_initial_latency_baseline_ms": initial.get("avg_latency_baseline_ms"),
            "use_initial_jitter_baseline_ms": initial.get("avg_jitter_baseline_ms"),
            "use_initial_eta_direct_pct": initial.get("avg_eta_direct_pct"),
            "initial_eta_is_defendable": bool(initial.get("supports_direct_eta")),
            "initial_multicast_rate_hz": initial.get("avg_multicast_rate_hz"),
            "initial_multicast_rate_is_defendable": bool(initial.get("parsed_pcap_sessions")),
            "validated_field_sessions": validated.get("field_validation_sessions", 0),
            "guidance": [
                "Capitulos 1 y 2 deben usar la fase inicial para linea base temprana de latencia y jitter.",
                "Eta directa y frecuencia de inundacion no deben atribuirse al lote inicial si no hubo evidencia simultanea suficiente.",
                "La fase validada en campo es la mejor referencia para semantica de ordeno y contraste presencial.",
            ],
        },
    }


def build_obj1_profiles_text(obj1_profiles: dict) -> str:
    lines = []
    for profile in obj1_profiles.get("profiles", []):
        lines.extend(
            [
                f"- {profile['label']} ({profile['start']} a {profile['end']}):",
                f"  visitas={profile['visit_count']}, sesiones={profile['session_count']}, baseline={profile['baseline_sessions']}, serial={profile['serial_sessions']}, collar={profile['collar_sessions']}, pcap_parseado={profile['parsed_pcap_sessions']}",
                f"  latencia={format_metric(profile.get('avg_latency_baseline_ms'))} ms, jitter={format_metric(profile.get('avg_jitter_baseline_ms'))} ms, heartbeat={format_metric(profile.get('avg_heartbeat_coverage_pct'), 2)}%, eta={format_metric(profile.get('avg_eta_direct_pct'), 2)}, multicast={format_metric(profile.get('avg_multicast_pct'), 2)}%, tasa_multicast={format_metric(profile.get('avg_multicast_rate_hz'), 3)} Hz",
                f"  uso recomendado: {profile['recommended_for']}",
            ]
        )

    recommendation = obj1_profiles.get("cap1_cap2_recommendation", {})
    lines.extend(
        [
            "- Recomendacion para Capitulo 1 y Capitulo 2:",
            f"  latencia inicial defendible = {format_metric(recommendation.get('use_initial_latency_baseline_ms'))} ms",
            f"  jitter inicial defendible = {format_metric(recommendation.get('use_initial_jitter_baseline_ms'))} ms",
            f"  eta inicial defendible = {'Si' if recommendation.get('initial_eta_is_defendable') else 'No'}",
            f"  frecuencia multicast inicial defendible = {'Si' if recommendation.get('initial_multicast_rate_is_defendable') else 'No'}",
        ]
    )
    return "\n".join(lines)


def build_gateway_readiness(summary: dict, obj1_profiles: dict) -> dict:
    obj1 = summary.get("objective_1_characterization", {})
    recommendation = obj1_profiles.get("cap1_cap2_recommendation", {})
    parsed_pcap_sessions = sum(profile.get("parsed_pcap_sessions", 0) for profile in obj1_profiles.get("profiles", []))
    readiness_checks = {
        "baseline_red_definido": bool(obj1.get("supports_latency_jitter_baseline")),
        "firmas_seriales_disponibles": bool(obj1.get("supports_serial_signature_characterization")),
        "dominio_collar_observable": bool(obj1.get("supports_udp_exposure_characterization")),
        "contraste_campo_disponible": bool(obj1.get("supports_field_contrast")),
        "eta_directa_consolidada": bool(obj1.get("supports_direct_eta_estimation")),
        "pcap_parseado_disponible": parsed_pcap_sessions > 0,
        "linea_base_inicial_defendible": bool(
            recommendation.get("use_initial_latency_baseline_ms") is not None
            and recommendation.get("use_initial_jitter_baseline_ms") is not None
        ),
    }
    core_ready = all(
        readiness_checks[key]
        for key in (
            "baseline_red_definido",
            "firmas_seriales_disponibles",
            "dominio_collar_observable",
            "linea_base_inicial_defendible",
        )
    )
    if not core_ready:
        stage = "caracterizacion"
        next_actions = [
            "cerrar linea base de red con latencia y jitter defendibles",
            "consolidar firmas seriales y dominio de collar por separado",
        ]
    elif not readiness_checks["pcap_parseado_disponible"] or not readiness_checks["contraste_campo_disponible"]:
        stage = "hardware"
        next_actions = [
            "estabilizar captura PCAP parseada en todas las sesiones clave",
            "ampliar contraste con campo para validar semantica operativa",
        ]
    elif not readiness_checks["eta_directa_consolidada"]:
        stage = "gateway"
        next_actions = [
            "cerrar regla final de eta directa sobre sesiones serial + red",
            "congelar el contrato JSON y las rutas del pipeline del gateway",
        ]
    else:
        stage = "validacion"
        next_actions = [
            "ejecutar validacion controlada del gateway con sesiones completas",
            "medir no repudio y continuidad con store-and-forward activo",
        ]
    return {
        "stage": stage,
        "checks": readiness_checks,
        "next_actions": next_actions,
    }


def summarize_baseline_metrics(summary: dict | None) -> dict:
    if not summary:
        return {
            "dir": "",
            "ip": "",
            "gateway": "",
            "lat_media": None,
            "jitter_ms": 0.0,
            "packet_loss": 0.0,
            "nodos_totales": 0,
            "nodos_dinamicos": 0,
        }
    return {
        "dir": summary.get("sample_dir", ""),
        "ip": summary.get("ip", ""),
        "gateway": summary.get("gateway", ""),
        "lat_media": summary.get("lat_media"),
        "jitter_ms": summary.get("jitter_ms", 0.0),
        "packet_loss": summary.get("packet_loss", 0.0),
        "nodos_totales": summary.get("nodos_totales", 0),
        "nodos_dinamicos": summary.get("nodos_dinamicos", 0),
    }


def compute_baseline_transition(pre_summary: dict | None, post_summary: dict | None) -> dict:
    if not pre_summary or not post_summary:
        return {
            "available": False,
            "lat_media_delta": None,
            "jitter_delta": None,
            "packet_loss_delta": None,
            "nodos_delta": None,
        }

    def delta(a, b):
        if a is None or b is None:
            return None
        return round(float(b) - float(a), 3)

    return {
        "available": True,
        "lat_media_delta": delta(pre_summary.get("lat_media"), post_summary.get("lat_media")),
        "jitter_delta": delta(pre_summary.get("jitter_ms"), post_summary.get("jitter_ms")),
        "packet_loss_delta": delta(pre_summary.get("packet_loss"), post_summary.get("packet_loss")),
        "nodos_delta": delta(pre_summary.get("nodos_totales"), post_summary.get("nodos_totales")),
    }


def empty_baseline_summary() -> dict:
    return {
        "sample_dir": "",
        "interface": "",
        "ip": "",
        "gateway": "",
        "mac_local": "",
        "latencies": [],
        "lat_min": None,
        "lat_max": None,
        "lat_media": None,
        "packet_loss": 0.0,
        "jitter_ms": 0.0,
        "default_routes": 0,
        "multicast_routes": 0,
        "arp_entries": [],
        "nodos_totales": 0,
        "nodos_dinamicos": 0,
        "gateway_mac": "",
        "gateway_seen_in_arp": False,
        "arp_ip_conflicts": [],
        "arp_mac_conflicts": [],
    }


def empty_serial_summary() -> dict:
    return {
        "available": False,
        "total_events": 0,
        "total_lines": 0,
        "malformed_lines": 0,
        "heartbeat_count": 0,
        "heartbeat_gap_count": 0,
        "heartbeat_coverage_pct": 0.0,
        "control_frame_count": 0,
        "flow_frame_count": 0,
        "cow_marker_frame_count": 0,
        "mixed_frame_count": 0,
        "unknown_frame_count": 0,
        "fragmented_frame_count": 0,
        "unique_patterns_count": 0,
        "heartbeat_ratio_pct": 0.0,
        "temp_prep_window_ms": 0,
        "cadence_step_ms": 0,
        "cadence_tolerance_ms": 0,
        "max_gap_ms": 0,
        "avg_gap_ms": 0.0,
        "capture_duration_ms": 0,
        "total_flow_samples": 0,
        "cow_batch_count": 0,
        "operational_batch_count": 0,
        "cow_event_count": 0,
        "cow_success_count": 0,
        "cow_partial_count": 0,
        "cow_missing_rfid_count": 0,
        "cow_missing_flow_count": 0,
        "cow_ambiguous_flow_sample_count": 0,
        "cow_events_with_ambiguous_flow_count": 0,
        "cow_prep_phase_count": 0,
        "cow_cadence_aligned_count": 0,
        "cow_cadence_dominant_step": 0,
        "merged_c2_count": 0,
        "multi_c2_event_count": 0,
        "channel_counts": {},
        "marker_counts": {},
        "coverage": {},
        "events": [],
        "frames": [],
        "marker_events": [],
        "flow_samples": [],
        "cow_batches": [],
        "operational_groups": [],
        "cow_events": [],
        "unknown_frames": [],
        "unparsed_lines": [],
        "top_patterns": [],
    }


def empty_antenna_udp_summary() -> dict:
    return {
        "available": False,
        "total_events": 0,
        "total_lines": 0,
        "malformed_lines": 0,
        "signature_count": 0,
        "unique_sources_count": 0,
        "sources": [],
        "unique_payloads_count": 0,
        "top_payloads": [],
        "avg_payload_len": 0.0,
        "max_payload_len": 0,
        "max_gap_ms": 0,
        "avg_gap_ms": 0.0,
        "events": [],
    }


def empty_pcap_summary() -> dict:
    return {
        "available": False,
        "scapy_ok": SCAPY_OK,
        "general": {
            "first_packet_timestamp": "",
            "total_packets": 0,
            "total_bytes": 0,
            "broadcast_pct": 0.0,
            "multicast_pct": 0.0,
            "proto_counts": {"TCP": 0, "UDP": 0, "ICMP": 0, "ARP": 0, "Otros": 0},
            "tcp_flags": {"SYN": 0, "RST": 0, "FIN": 0},
            "syn_ratio_pct": 0.0,
            "rst_ratio_pct": 0.0,
            "fin_ratio_pct": 0.0,
            "external_ips": [],
            "top_talkers": [],
            "top_talker_share_pct": 0.0,
            "top_ports": [],
            "insecure_flows": [],
            "arp_ip_conflicts": [],
            "arp_mac_conflicts": [],
        },
        "telemetry": {
            "target_ip": "",
            "target_port": 0,
            "telemetry_packets": 0,
            "telemetry_no_payload_packets": 0,
            "signature_count": 0,
            "udp_event_count": 0,
            "tcp_event_count": 0,
            "multicast_event_count": 0,
            "avg_payload_len": 0.0,
            "max_payload_len": 0,
            "max_interarrival_ms": 0,
            "events": [],
            "udp_events": [],
            "tcp_events": [],
        },
    }


def empty_correlation_summary() -> dict:
    return {
        "network_mode": "sin_datos",
        "serial_events": 0,
        "network_events": 0,
        "matched_events": 0,
        "unmatched_serial_events": 0,
        "eta_extraccion": 0.0,
        "desfase_medio_ms": 0.0,
        "desfase_max_ms": 0.0,
        "desfase_firmado_medio_ms": 0.0,
        "matches": [],
    }


def build_session_summary(
    session: dict,
    baseline: dict,
    serial: dict,
    antenna_udp: dict,
    pcap: dict,
    correlation: dict,
    alerts: dict,
    field_validation: dict,
) -> dict:
    severity_counts = alerts.get("summary", {}).get("by_severity", {})
    operation_mode = session.get("operation_mode", "indeterminado")
    marker_counts = serial.get("marker_counts", {})
    if session.get("session_type") == "baseline_only":
        obj1_role = "linea_base_red"
    elif operation_mode == "ordeno_completo":
        obj1_role = "semantica_ordeno_y_eta_preliminar"
    elif operation_mode == "telemetria_collar":
        obj1_role = "telemetria_collar_y_exposicion_udp"
    else:
        obj1_role = "apoyo_contextual"
    summary = {
        "sample_id": session["sample_id"],
        "visit_name": session.get("visit_name", "Sin_visita"),
        "block_label": session.get("block_label", ""),
        "operation_mode": operation_mode,
        "obj1_role": obj1_role,
        "session_type": session.get("session_type", "capture"),
        "capture_dir": str(session["capture_dir"]),
        "baseline_dir": baseline.get("baseline_dir", ""),
        "baseline_pre": baseline.get("baseline_pre", ""),
        "baseline_post": baseline.get("baseline_post", ""),
        "has_baseline": bool(baseline.get("baseline_dir")),
        "has_serial": bool(serial.get("available", False)),
        "has_antenna_udp": bool(antenna_udp.get("available", False)),
        "has_etl": bool(session.get("etl_path")),
        "has_pcap": bool(session.get("pcap_path")),
        "pcap_parsed": bool(pcap.get("available", False)),
        "has_correlation": bool(serial.get("available", False) and pcap.get("available", False)),
        "has_c2": bool(marker_counts.get("C2", 0) or serial.get("cow_event_count", 0)),
        "has_e2": bool(marker_counts.get("E2", 0)),
        "has_e4": bool(serial.get("total_flow_samples", 0)),
        "lat_media": baseline.get("lat_media") if baseline.get("lat_media") is not None else "",
        "jitter_ms": baseline.get("jitter_ms", 0.0),
        "packet_loss": baseline.get("packet_loss", 0.0),
        "nodos_dinamicos": baseline.get("nodos_dinamicos", 0),
        "tandas_vaca": serial.get("cow_batch_count", 0),
        "tandas_operativas": serial.get("operational_batch_count", 0),
        "eventos_vaca": serial.get("cow_event_count", 0),
        "eventos_con_exito": serial.get("cow_success_count", 0),
        "eventos_sin_rfid": serial.get("cow_missing_rfid_count", 0),
        "eventos_sin_flujo": serial.get("cow_missing_flow_count", 0),
        "eventos_flujo_ambiguo": serial.get("cow_events_with_ambiguous_flow_count", 0),
        "muestras_flujo": serial.get("total_flow_samples", 0),
        "cobertura_heartbeat_pct": serial.get("heartbeat_coverage_pct", 0.0),
        "eventos_antena_udp": antenna_udp.get("total_events", 0) if antenna_udp.get("available", False) else "",
        "firmas_antena_udp": antenna_udp.get("signature_count", 0) if antenna_udp.get("available", False) else "",
        "eventos_red": len(pcap.get("telemetry", {}).get("events", [])) if pcap.get("available", False) else "",
        "firmas_56d100": pcap.get("telemetry", {}).get("signature_count", 0) if pcap.get("available", False) else "",
        "multicast_pct": pcap.get("general", {}).get("multicast_pct", 0.0) if pcap.get("available", False) else "",
        "packet_rate_hz": pcap.get("general", {}).get("packet_rate_hz", 0.0) if pcap.get("available", False) else "",
        "multicast_rate_hz": pcap.get("general", {}).get("multicast_rate_hz", 0.0) if pcap.get("available", False) else "",
        "validacion_campo": bool(field_validation.get("available", False)),
        "vacas_observadas_campo": field_validation.get("observed_cows_count", 0) if field_validation.get("available", False) else "",
        "ids_rapidas_campo": field_validation.get("quick_id_count", 0) if field_validation.get("available", False) else "",
        "ids_dudosas_campo": field_validation.get("id_doubtful_count", 0) if field_validation.get("available", False) else "",
        "issues_fotocelda_campo": field_validation.get("photocell_issue_count", 0) if field_validation.get("available", False) else "",
        "eta_extraccion": correlation.get("eta_extraccion", 0.0) if (serial.get("available", False) and pcap.get("available", False)) else "",
        "desfase_medio_ms": correlation.get("desfase_medio_ms", 0.0) if (serial.get("available", False) and pcap.get("available", False)) else "",
        "desfase_max_ms": correlation.get("desfase_max_ms", 0.0) if (serial.get("available", False) and pcap.get("available", False)) else "",
        "eventos_correlacionados": correlation.get("matched_events", 0) if (serial.get("available", False) and pcap.get("available", False)) else 0,
        "alertas_totales": alerts.get("summary", {}).get("total", 0),
        "alertas_criticas": severity_counts.get("Critica", 0),
        "alertas_altas": severity_counts.get("Alta", 0),
        "alertas_medias": severity_counts.get("Media", 0),
        "alertas_bajas": severity_counts.get("Baja", 0),
        "alertas_info": severity_counts.get("Info", 0),
        "fc_count": serial.get("legacy_fc_count", 0),
        "fe_count": serial.get("legacy_fe_count", 0),
        "signature_count": pcap.get("telemetry", {}).get("signature_count", 0) if pcap.get("available", False) else 0,
        "matched_events": correlation.get("matched_events", 0),
        "vaca_count": serial.get("cow_event_count", 0),
        "sin_rfid_count": serial.get("cow_missing_rfid_count", 0),
        "flujo_count": serial.get("total_flow_samples", 0),
    }

    if session.get("session_type") != "baseline_only":
        capture_dir = Path(session["capture_dir"])
        summary.update(_read_capture_manifest_fields(capture_dir))
    else:
        summary.update(
            {
                "capture_started_at": "",
                "capture_ended_at": "",
                "capture_duration_seconds": "",
                "capture_requested_seconds": "",
                "capture_stop_reason": "",
                "capture_mode": "",
            }
        )

    return summary


def write_visit_summary(visit_name: str, rows: list[dict]) -> None:
    visit_reports_dir = get_visit_report_summary_dir(visit_name)
    visit_processed_dir = get_visit_processed_summary_dir(visit_name)

    artifact_counts = build_artifact_counts(rows)
    sample_type_counts = build_sample_type_counts(rows)
    operation_mode_counts = build_operation_mode_counts(rows)
    obj1_summary = build_obj1_characterization_summary(rows)
    obj1_profiles = build_obj1_profiles(rows)
    visit_row = build_visit_row(visit_name, rows)

    summary = {
        "visit_name": visit_name,
        "total_sessions": visit_row["total_sessions"],
        "sessions_baseline_only": visit_row.get("sessions_baseline_only", 0),
        "sessions_with_baseline": visit_row["sessions_with_baseline"],
        "sessions_with_serial": visit_row["sessions_with_serial"],
        "sessions_with_antenna_udp": visit_row["sessions_with_antenna_udp"],
        "sessions_with_etl": visit_row.get("sessions_with_etl", 0),
        "sessions_with_pcap": visit_row["sessions_with_pcap"],
        "sessions_with_correlation": visit_row.get("sessions_with_correlation", 0),
        "total_alertas": visit_row.get("total_alertas", 0),
        "total_alertas_criticas": visit_row["total_alertas_criticas"],
        "total_alertas_altas": visit_row["total_alertas_altas"],
        "avg_lat_media": visit_row["avg_lat_media"],
        "avg_eta_extraccion": visit_row["avg_eta_extraccion"],
        "avg_desfase_medio_ms": visit_row["avg_desfase_medio_ms"],
        "avg_multicast_pct": visit_row["avg_multicast_pct"],
        "sample_type_counts": sample_type_counts,
        "operation_mode_counts": operation_mode_counts,
        "objective_1_characterization": obj1_summary,
    }

    dump_json(visit_processed_dir / f"{visit_name}_summary.json", summary)
    dump_json(visit_processed_dir / f"{visit_name}_obj1_summary.json", obj1_summary)
    write_csv(visit_processed_dir / f"{visit_name}_sessions.csv", rows)

    report_text = f"""
RESUMEN DE APOYO POR VISITA
===========================

Visita: {visit_name}

1. Cobertura
- Sesiones totales: {summary['total_sessions']}
- Sesiones baseline-only: {summary['sessions_baseline_only']}
- Sesiones con baseline: {summary['sessions_with_baseline']}
- Sesiones con serial: {summary['sessions_with_serial']}
- Sesiones Antena + PCAP: {sample_type_counts['Antena + PCAP']}
- Sesiones PCAP + ETL: {sample_type_counts['PCAP + ETL']}
- Sesiones con pcap: {summary['sessions_with_pcap']}
- Sesiones con correlacion: {summary['sessions_with_correlation']}
- Alertas totales: {summary['total_alertas']}
- Alertas criticas: {summary['total_alertas_criticas']}
- Alertas altas: {summary['total_alertas_altas']}
- Latencia media promedio: {format_metric(summary['avg_lat_media'])}
- Eta promedio: {format_metric(summary['avg_eta_extraccion'], 2)}
- Desfase medio promedio: {format_metric(summary['avg_desfase_medio_ms'])}
- Multicast promedio: {format_metric(summary['avg_multicast_pct'], 2)}

2. Conteo principal de cobertura
- Baseline: {artifact_counts['Baseline']}
- PCAP: {artifact_counts['PCAP']}
- Antena + PCAP: {artifact_counts['Antena + PCAP']}
- ETL de captura: {artifact_counts['ETL de captura']}
- Serial: {artifact_counts['Serial']}
- Correlacion efectiva: {artifact_counts['Correlacion efectiva']}

3. Combinaciones observadas
- Ordeno completo: {operation_mode_counts['Ordeno completo']}
- Telemetria de collar: {operation_mode_counts['Telemetria de collar']}
- SERIAL + PCAP: {sample_type_counts['SERIAL + PCAP']}
- Antena + PCAP: {sample_type_counts['Antena + PCAP']}
- PCAP + ETL: {sample_type_counts['PCAP + ETL']}
- PCAP solo: {sample_type_counts['PCAP solo']}
- Baseline: {sample_type_counts['Baseline']}
- Otros: {sample_type_counts['Otros']}
Guia de interpretacion:
{build_sample_type_guide_text()}
Conciliacion de conteos:
{build_sample_type_reconciliation_text(summary, sample_type_counts)}

4. Puntos observados
{build_highlights_text(rows)}

5. Lectura de caracterizacion para el Objetivo 1
{build_obj1_characterization_text(obj1_summary)}

6. Lectura de apoyo en ciberseguridad (visita)
{build_security_observations_text(summary, sample_type_counts)}

7. Inventario de sesiones revisadas
{build_session_inventory_table(rows)}
""".strip()

    (visit_reports_dir / f"{visit_name}_summary.txt").write_text(report_text, encoding="utf-8")
    (visit_reports_dir / f"{visit_name}_obj1_summary.txt").write_text(build_obj1_characterization_text(obj1_summary), encoding="utf-8")
    human_text = build_human_summary_text(visit_name, summary, sample_type_counts)
    (visit_reports_dir / f"{visit_name}_summary_humano.txt").write_text(human_text, encoding="utf-8")


def write_global_summary(run_name: str, root_dirs: list[Path], rows: list[dict]) -> list[str]:
    if not rows:
        return []

    processed_dir = get_global_processed_summary_dir(run_name)
    reports_dir = get_global_report_summary_dir(run_name)

    visit_groups: dict[str, list[dict]] = {}
    for row in rows:
        visit_groups.setdefault(row["visit_name"], []).append(row)

    visit_rows = []
    for visit_name, visit_data in sorted(visit_groups.items()):
        visit_rows.append(build_visit_row(visit_name, visit_data))

    lat_values = [float(row["lat_media"]) for row in rows if has_metric(row["lat_media"])]
    eta_values = [float(row["eta_extraccion"]) for row in rows if has_metric(row["eta_extraccion"])]
    delta_values = [float(row["desfase_medio_ms"]) for row in rows if has_metric(row["desfase_medio_ms"])]
    multicast_values = [float(row["multicast_pct"]) for row in rows if has_metric(row["multicast_pct"])]

    artifact_counts = build_artifact_counts(rows)
    sample_type_counts = build_sample_type_counts(rows)
    operation_mode_counts = build_operation_mode_counts(rows)
    correlation_rows = build_correlacion_global_rows(rows)

    obj1_summary = build_obj1_characterization_summary(rows)
    obj1_profiles = build_obj1_profiles(rows)

    summary = {
        "root_name": run_name,
        "root_paths": [str(root_dir) for root_dir in root_dirs],
        "total_visits": len(visit_groups),
        "total_sessions": len(rows),
        "sessions_baseline_only": sum(1 for row in rows if row.get("session_type") == "baseline_only"),
        "sessions_with_baseline": sum(1 for row in rows if row["has_baseline"]),
        "sessions_with_serial": sum(1 for row in rows if row["has_serial"]),
        "sessions_with_antenna_udp": sum(1 for row in rows if row.get("has_antenna_udp")),
        "sessions_with_etl": sum(1 for row in rows if row.get("has_etl")),
        "sessions_with_pcap": sum(1 for row in rows if row["has_pcap"]),
        "sessions_with_correlation": sum(1 for row in rows if row["has_correlation"]),
        "total_alertas": sum(int(row.get("alertas_totales", 0) or 0) for row in rows),
        "total_alertas_criticas": sum(int(row.get("alertas_criticas", 0) or 0) for row in rows),
        "total_alertas_altas": sum(int(row.get("alertas_altas", 0) or 0) for row in rows),
        "avg_lat_media": safe_average(lat_values),
        "avg_eta_extraccion": safe_average(eta_values),
        "avg_desfase_medio_ms": safe_average(delta_values),
        "avg_multicast_pct": safe_average(multicast_values),
        "sample_type_counts": {key: int(sample_type_counts.get(key, 0) or 0) for key in REQUIRED_SAMPLE_TYPE_KEYS},
        "operation_mode_counts": operation_mode_counts,
        "objective_1_characterization": obj1_summary,
        "objective_1_profiles": obj1_profiles,
    }
    summary["gateway_readiness"] = build_gateway_readiness(summary, obj1_profiles)

    dump_json(processed_dir / f"{run_name}_summary.json", summary)
    dump_json(processed_dir / f"{run_name}_obj1_summary.json", obj1_summary)
    dump_json(processed_dir / f"{run_name}_obj1_profiles.json", obj1_profiles)
    dump_json(processed_dir / f"{run_name}_gateway_readiness.json", summary["gateway_readiness"])
    write_csv(processed_dir / f"{run_name}_visits.csv", visit_rows, fieldnames=REQUIRED_VISIT_COLS + [
        "sessions_baseline_only",
        "sessions_with_etl",
        "sessions_with_correlation",
        "total_alertas",
    ])
    write_csv(processed_dir / f"{run_name}_sessions.csv", rows)
    write_csv(processed_dir / f"{run_name}_correlacion_global.csv", correlation_rows, fieldnames=list(CORRELACION_COLS.keys()))

    report_text = f"""
RESUMEN GENERAL DE APOYO
========================

Nombre del lote: {run_name}

Raices procesadas:
{build_roots_description(root_dirs)}

1. Cobertura global
- Visitas incluidas: {summary['total_visits']}
- Sesiones totales: {summary['total_sessions']}
- Sesiones baseline-only: {summary['sessions_baseline_only']}
- Sesiones con baseline: {summary['sessions_with_baseline']}
- Sesiones con serial: {summary['sessions_with_serial']}
- Sesiones Antena + PCAP: {sample_type_counts['Antena + PCAP']}
- Sesiones PCAP + ETL: {sample_type_counts['PCAP + ETL']}
- Sesiones con pcap: {summary['sessions_with_pcap']}
- Sesiones con correlacion: {summary['sessions_with_correlation']}
- Alertas totales: {summary['total_alertas']}
- Alertas criticas: {summary['total_alertas_criticas']}
- Alertas altas: {summary['total_alertas_altas']}
- Latencia media promedio: {format_metric(summary['avg_lat_media'])}
- Eta promedio: {format_metric(summary['avg_eta_extraccion'], 2)}
- Desfase medio promedio: {format_metric(summary['avg_desfase_medio_ms'])}
- Multicast promedio: {format_metric(summary['avg_multicast_pct'], 2)}

2. Conteo principal de cobertura
- Baseline: {artifact_counts['Baseline']}
- PCAP: {artifact_counts['PCAP']}
- Antena + PCAP: {artifact_counts['Antena + PCAP']}
- ETL de captura: {artifact_counts['ETL de captura']}
- Serial: {artifact_counts['Serial']}
- Correlacion efectiva: {artifact_counts['Correlacion efectiva']}

3. Combinaciones observadas
- Ordeno completo: {operation_mode_counts['Ordeno completo']}
- Telemetria de collar: {operation_mode_counts['Telemetria de collar']}
- SERIAL + PCAP: {sample_type_counts['SERIAL + PCAP']}
- Antena + PCAP: {sample_type_counts['Antena + PCAP']}
- PCAP + ETL: {sample_type_counts['PCAP + ETL']}
- PCAP solo: {sample_type_counts['PCAP solo']}
- Baseline: {sample_type_counts['Baseline']}
- Otros: {sample_type_counts['Otros']}
Guia de interpretacion:
{build_sample_type_guide_text()}
Conciliacion de conteos:
{build_sample_type_reconciliation_text(summary, sample_type_counts)}

4. Puntos observados a nivel global
{build_highlights_text(rows)}

5. Lectura de caracterizacion para el Objetivo 1
{build_obj1_characterization_text(obj1_summary)}

6. Perfiles por fase para el Objetivo 1
{build_obj1_profiles_text(obj1_profiles)}

7. Lectura de readiness para el gateway
- Etapa actual: {summary['gateway_readiness']['stage']}
- Baseline de red definido: {'Si' if summary['gateway_readiness']['checks']['baseline_red_definido'] else 'No'}
- Firmas seriales disponibles: {'Si' if summary['gateway_readiness']['checks']['firmas_seriales_disponibles'] else 'No'}
- Dominio collar observable: {'Si' if summary['gateway_readiness']['checks']['dominio_collar_observable'] else 'No'}
- Contraste con campo disponible: {'Si' if summary['gateway_readiness']['checks']['contraste_campo_disponible'] else 'No'}
- Eta directa consolidada: {'Si' if summary['gateway_readiness']['checks']['eta_directa_consolidada'] else 'No'}
- PCAP parseado disponible: {'Si' if summary['gateway_readiness']['checks']['pcap_parseado_disponible'] else 'No'}

8. Alertas PCAP explicadas en lenguaje simple
- Como leer severidad:
  Critica: la condicion puede comprometer el segmento o volver poco confiable la lectura de la muestra.
  Alta: merece revision prioritaria porque puede afectar seguridad, continuidad o interpretacion.
  Media: introduce incertidumbre o degradacion relevante, aunque no invalida por si sola la muestra.
  Baja/Info: aporta contexto o seguimiento, con impacto acotado.
{build_pcap_alerts_plain_text(rows)}

9. Lectura ejecutiva de apoyo en ciberseguridad
{build_security_observations_text(summary, sample_type_counts)}

10. Puntos de apoyo para la siguiente etapa del gateway Mosquitto
{build_gateway_implications_text(summary, sample_type_counts)}

11. Guia de seguimiento: riesgo actual vs control futuro
{build_risk_control_checklist_text(summary, sample_type_counts)}

12. Resumen por visita
{build_visit_aggregate_table(visit_rows)}

13. Inventario detallado
- El inventario completo por sesion se exporta aparte en CSV para evitar repeticion visual en este resumen.
- Archivo de apoyo: {processed_dir / f"{run_name}_sessions.csv"}
""".strip()

    (reports_dir / f"{run_name}_summary.txt").write_text(report_text, encoding="utf-8")
    (reports_dir / f"{run_name}_obj1_summary.txt").write_text(build_obj1_characterization_text(obj1_summary), encoding="utf-8")
    (reports_dir / f"{run_name}_obj1_profiles.txt").write_text(build_obj1_profiles_text(obj1_profiles), encoding="utf-8")
    human_text = build_human_summary_text(run_name, summary, sample_type_counts)
    (reports_dir / f"{run_name}_summary_humano.txt").write_text(human_text, encoding="utf-8")
    return validate_outputs(processed_dir, run_name)


def process_session(session: dict, args) -> dict:
    sample_name = session["sample_id"]
    visit_name = session.get("visit_name", "Sin_visita")
    session_type = session.get("session_type", "capture")
    capture_dir = Path(session["capture_dir"])
    baseline_pre = Path(session["baseline_pre"]) if session.get("baseline_pre") else None
    baseline_post = Path(session["baseline_post"]) if session.get("baseline_post") else None
    baseline_dir = Path(session["baseline_dir"]) if session.get("baseline_dir") else None
    serial_path = Path(session["serial_path"])
    antenna_udp_path = Path(session["antenna_udp_path"]) if session.get("antenna_udp_path") else None
    etl_path = Path(session["etl_path"]) if session.get("etl_path") else None
    pcap_path = Path(session["pcap_path"]) if session["pcap_path"] else None

    output_dir = ensure_dir(get_visit_processed_sessions_dir(visit_name) / sample_name)
    report_dir = get_visit_report_hourly_dir(visit_name)
    report_path = report_dir / f"{sample_name}_technical_report.txt"
    human_report_path = report_dir / f"{sample_name}_human_report.txt"

    baseline_capture_summary = parse_baseline_dir(capture_dir) if has_baseline_files(capture_dir) else None
    baseline_pre_summary = parse_baseline_dir(baseline_pre) if baseline_pre and has_baseline_files(baseline_pre) else None
    baseline_post_summary = parse_baseline_dir(baseline_post) if baseline_post and has_baseline_files(baseline_post) else None

    if has_baseline_files(capture_dir):
        baseline_source = capture_dir
    elif baseline_dir and has_baseline_files(baseline_dir):
        baseline_source = baseline_dir
    else:
        baseline_source = None

    if baseline_capture_summary:
        baseline = baseline_capture_summary
    elif baseline_pre_summary:
        baseline = baseline_pre_summary
    elif baseline_post_summary:
        baseline = baseline_post_summary
    else:
        baseline = empty_baseline_summary()

    baseline["capture_dir"] = str(capture_dir)
    baseline["baseline_dir"] = str(baseline_source) if baseline_source else ""
    baseline["baseline_pre"] = str(baseline_pre) if baseline_pre else ""
    baseline["baseline_post"] = str(baseline_post) if baseline_post else ""
    baseline["baseline_capture_summary"] = summarize_baseline_metrics(baseline_capture_summary)
    baseline["baseline_pre_summary"] = summarize_baseline_metrics(baseline_pre_summary)
    baseline["baseline_post_summary"] = summarize_baseline_metrics(baseline_post_summary)
    baseline["baseline_transition"] = compute_baseline_transition(baseline_pre_summary, baseline_post_summary)
    baseline["baseline_strategy"] = "capture" if baseline_capture_summary else ("pre" if baseline_pre_summary else ("post" if baseline_post_summary else "none"))
    if session_type == "baseline_only":
        baseline["baseline_strategy"] = "baseline_only"

    if serial_path.exists():
        serial = parse_serial_file(serial_path)
        serial["available"] = True
        serial["source_path"] = str(serial_path)
    else:
        serial = empty_serial_summary()
        serial["source_path"] = ""

    if antenna_udp_path and antenna_udp_path.exists():
        antenna_udp = parse_antenna_udp_file(antenna_udp_path, args.signature)
        antenna_udp["available"] = True
        antenna_udp["source_path"] = str(antenna_udp_path)
    else:
        antenna_udp = empty_antenna_udp_summary()
        antenna_udp["source_path"] = ""

    if pcap_path:
        if not SCAPY_OK:
            pcap = empty_pcap_summary()
            pcap["available"] = False
            pcap["source_path"] = str(pcap_path)
            pcap["file_detected"] = True
            pcap["parse_error"] = "Scapy no esta instalado; se detecto el archivo PCAP pero no se analizo su contenido."
        else:
            pcap = parse_pcap_file(pcap_path, args.target_ip, args.target_port, args.signature)
            pcap["available"] = True
            pcap["source_path"] = str(pcap_path)
            pcap["file_detected"] = True
            pcap["parse_error"] = ""
    else:
        pcap = empty_pcap_summary()
        pcap["source_path"] = ""
        pcap["file_detected"] = False
        pcap["parse_error"] = ""

    telemetry_events = pcap.get("telemetry", {}).get("events", [])
    if serial["events"] and telemetry_events:
        correlation = correlate_events(serial, telemetry_events, args.window_ms)
    else:
        correlation = empty_correlation_summary()
    operation_mode = session.get("operation_mode", "indeterminado")
    block_label = session.get("block_label", "")
    field_validation = build_field_validation_summary(session, capture_dir, serial)
    alerts = build_alert_package(baseline, serial, pcap, correlation, session_type=session_type, operation_mode=operation_mode)
    rules = build_priority_rules(args.target_port, args.window_ms)

    dump_json(output_dir / "baseline_summary.json", baseline)
    dump_json(output_dir / "serial_summary.json", serial)
    dump_json(output_dir / "antenna_udp_summary.json", antenna_udp)
    dump_json(output_dir / "pcap_summary.json", pcap)
    dump_json(output_dir / "correlation_summary.json", correlation)
    dump_json(output_dir / "field_validation_summary.json", field_validation)
    dump_json(output_dir / "alerts.json", alerts)
    dump_json(output_dir / "priority_rules.json", rules)
    write_csv(output_dir / "serial_events.csv", serial["events"])
    write_csv(output_dir / "serial_frames.csv", serial.get("frames", []))
    write_csv(output_dir / "serial_markers.csv", serial.get("marker_events", []))
    write_csv(output_dir / "serial_unknown.csv", serial.get("unknown_frames", []))
    write_csv(output_dir / "serial_unparsed.csv", serial.get("unparsed_lines", []))
    write_csv(output_dir / "cow_batches.csv", serial.get("cow_batches", []))
    write_csv(output_dir / "cow_operational_groups.csv", serial.get("operational_groups", []))
    write_csv(output_dir / "cow_events.csv", serial.get("cow_events", []))
    write_csv(output_dir / "flow_segments.csv", serial.get("flow_samples", []))
    write_csv(output_dir / "antenna_udp_events.csv", antenna_udp["events"])
    write_csv(output_dir / "pcap_general_top_talkers.csv", pcap.get("general", {}).get("top_talkers", []))
    write_csv(output_dir / "pcap_telemetry_events.csv", pcap.get("telemetry", {}).get("events", []))
    write_csv(output_dir / "pcap_telemetry_udp_events.csv", pcap.get("telemetry", {}).get("udp_events", []))
    write_csv(output_dir / "pcap_telemetry_tcp_events.csv", pcap.get("telemetry", {}).get("tcp_events", []))
    write_csv(output_dir / "correlation_matches.csv", correlation["matches"])
    write_csv(output_dir / "field_validation_records.csv", field_validation.get("records", []))
    write_csv(output_dir / "alerts.csv", alerts["all"])
    technical_path, human_path = generate_reports(
        sample_name,
        baseline,
        serial,
        antenna_udp,
        pcap,
        correlation,
        alerts,
        args.window_ms,
        report_dir,
        etl_path=str(etl_path) if etl_path else "",
        operation_mode=operation_mode,
        block_label=block_label,
        field_validation=field_validation,
    )

    session_result = build_session_summary(session, baseline, serial, antenna_udp, pcap, correlation, alerts, field_validation)
    auto_save_to_db(session_result, str(DB_PATH))

    print(f"[OK] Muestra procesada: {sample_name}")
    print(f"     Captura: {capture_dir}")
    print(f"     Baseline pre: {baseline_pre if baseline_pre else 'No asociado'}")
    print(f"     Baseline post: {baseline_post if baseline_post else 'No asociado'}")
    print(f"     Baseline usado: {baseline_source if baseline_source else 'No asociado'}")
    print(f"     Tipo de sesion: {'Baseline-only' if session_type == 'baseline_only' else 'Captura'}")
    print(f"     Bloque: {block_label or 'Sin bloque'}")
    print(f"     Modo operativo: {get_operation_mode_label(operation_mode)}")
    print(f"     Serial: {'Si' if serial['available'] else 'No'}")
    print(f"     Antena UDP txt: {'Si' if antenna_udp['available'] else 'No'}")
    print(f"     ETL de captura: {'Si' if etl_path and etl_path.exists() else 'No'}")
    print(f"     PCAP archivo: {'Si' if pcap.get('file_detected') else 'No'}")
    print(f"     PCAP analizado: {'Si' if pcap['available'] else 'No'}")
    print(f"     Archivo serial: {serial_path if serial['available'] else 'No detectado'}")
    print(f"     Archivo antena_udp: {antenna_udp_path if antenna_udp['available'] else 'No detectado'}")
    print(f"     Archivo ETL: {etl_path if etl_path and etl_path.exists() else 'No detectado'}")
    print(f"     Archivo pcap: {pcap_path if pcap.get('file_detected') else 'No detectado'}")
    print(f"     Validacion de campo: {'Si' if field_validation.get('available') else 'No'}")
    if field_validation.get("available"):
        print(f"     Vacas observadas en campo: {field_validation.get('observed_cows_count', 0)}")
        print(f"     IDs rapidas observadas: {field_validation.get('quick_id_count', 0)}")
    if pcap.get("parse_error"):
        print(f"     Nota PCAP: {pcap['parse_error']}")
    print(f"     Alertas: {alerts.get('summary', {}).get('total', 0)}")
    print(f"[OK] Salidas en: {output_dir}")
    print(f"[OK] Informe en: {technical_path}")
    print(f"[OK] Informe humano en: {human_path}")
    return session_result


def print_session_preview(session: dict) -> None:
    capture_dir = Path(session["capture_dir"])
    session_type = session.get("session_type", "capture")
    baseline_pre = Path(session["baseline_pre"]) if session.get("baseline_pre") else None
    baseline_post = Path(session["baseline_post"]) if session.get("baseline_post") else None
    baseline_dir = Path(session["baseline_dir"]) if session.get("baseline_dir") else None
    serial_path = Path(session["serial_path"])
    antenna_udp_path = Path(session["antenna_udp_path"]) if session.get("antenna_udp_path") else None
    etl_path = Path(session["etl_path"]) if session.get("etl_path") else None
    pcap_path = Path(session["pcap_path"]) if session["pcap_path"] else None

    baseline_source = ""
    if has_baseline_files(capture_dir):
        baseline_source = str(capture_dir)
    elif baseline_dir and has_baseline_files(baseline_dir):
        baseline_source = str(baseline_dir)

    print("[INFO] Sesion detectada")
    print(f"       sample_id: {session['sample_id']}")
    print(f"       visita: {session.get('visit_name', 'Sin_visita')}")
    print(f"       tipo: {'Baseline-only' if session_type == 'baseline_only' else 'Captura'}")
    print(f"       bloque: {session.get('block_label', 'Sin bloque')}")
    print(f"       modo_operativo: {get_operation_mode_label(session.get('operation_mode', 'indeterminado'))}")
    print(f"       captura: {capture_dir}")
    print(f"       baseline_pre: {baseline_pre if baseline_pre else 'No asociado'}")
    print(f"       baseline_post: {baseline_post if baseline_post else 'No asociado'}")
    print(f"       baseline_asociado: {baseline_source if baseline_source else 'No asociado'}")
    print(f"       serial: {'Si' if serial_path.exists() else 'No'}")
    print(f"       antena_udp: {'Si' if antenna_udp_path and antenna_udp_path.exists() else 'No'}")
    print(f"       etl: {'Si' if etl_path and etl_path.exists() else 'No'}")
    print(f"       pcap_archivo: {'Si' if pcap_path else 'No'}")
    print("")


def main() -> None:
    parser = build_argument_parser()
    args = parser.parse_args()

    if args.sample:
        session = discover_single_session(Path(args.sample))
        if args.dry_run:
            print_session_preview(session)
            return
        process_session(session, args)
        return

    if args.root:
        root_dirs = [Path(args.root).resolve()]
    else:
        root_dirs = [Path(item).resolve() for item in args.roots]

    sessions = discover_sessions_from_roots(root_dirs)
    if not sessions:
        searched = ", ".join(str(root_dir) for root_dir in root_dirs)
        raise SystemExit(f"No se encontraron carpetas Captura_* bajo: {searched}")

    run_name = build_batch_run_name(root_dirs, args.run_name)

    print(f"[INFO] Sesiones detectadas: {len(sessions)}")
    if len(root_dirs) > 1:
        print(f"[INFO] Raices incluidas: {len(root_dirs)}")
        for root_dir in root_dirs:
            print(f"       - {root_dir}")
        print(f"[INFO] Nombre del lote: {run_name}")

    if args.dry_run:
        for session in sessions:
            print_session_preview(session)
        return

    failures = []
    processed_rows = []

    t_batch_start = time.monotonic()
    total = len(sessions)

    def format_duration(seconds: float) -> str:
        seconds = max(0, int(seconds))
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def format_progress_bar(current: int, total_count: int, width: int = 26) -> str:
        if total_count <= 0:
            return "" * width
        ratio = max(0.0, min(1.0, current / total_count))
        filled = int(round(ratio * width))
        return "#" * filled + "-" * (width - filled)

    if _HAS_RICH:
        columns = [
            TextColumn("[bold]Procesando"),
            BarColumn(bar_width=30, complete_style="blue", finished_style="blue"),
            TaskProgressColumn(),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
        ]
        with Progress(*columns, transient=False) as progress:
            task_id = progress.add_task("batch", total=total)
            for session in sessions:
                try:
                    processed_rows.append(process_session(session, args))
                except Exception as exc:
                    failures.append((session["sample_id"], str(exc)))
                    print(f"[ERROR] {session['sample_id']}: {exc}")
                progress.advance(task_id, 1)
    else:
        for idx, session in enumerate(sessions, start=1):
            elapsed = time.monotonic() - t_batch_start
            avg = elapsed / idx if idx else 0.0
            eta = avg * (total - idx)

            bar = format_progress_bar(idx, total)
            line = (
                f"[INFO] [{bar}] {idx}/{total} | transcurrido={format_duration(elapsed)} | ETA={format_duration(eta)}"
            )

            # Actualizacion tipo "barra" en una sola linea.
            # Para no saturar la consola, solo se imprime con salto de linea cada 10 sesiones (y al final).
            if idx % 10 == 0 or idx == total:
                print(line, flush=True)
            else:
                print(line, end="\r", flush=True)
            try:
                processed_rows.append(process_session(session, args))
            except Exception as exc:
                failures.append((session["sample_id"], str(exc)))
                print(f"[ERROR] {session['sample_id']}: {exc}")

    visit_groups: dict[str, list[dict]] = {}
    for row in processed_rows:
        visit_groups.setdefault(row["visit_name"], []).append(row)

    for visit_name, rows in visit_groups.items():
        write_visit_summary(visit_name, rows)
        print(f"[OK] Resumen de visita generado: {visit_name}")

    should_write_global_summary = len(visit_groups) > 1 or len(root_dirs) > 1 or bool(args.run_name)
    if should_write_global_summary:
        output_issues = write_global_summary(run_name, root_dirs, processed_rows)
        print(f"[OK] Resumen general del lote generado: {run_name}")
        if output_issues:
            print(f"[WARN] Validacion de salida detecto {len(output_issues)} problema(s).")
            for issue in output_issues:
                print(f"       - {issue}")
        else:
            print("[OK] Validacion de salida completada sin problemas.")

    if failures:
        print(f"[WARN] Fallaron {len(failures)} sesiones.")
        for sample_id, message in failures:
            print(f"       - {sample_id}: {message}")
    else:
        print("[OK] Procesamiento por lote completado sin errores.")

    total_elapsed = time.monotonic() - t_batch_start
    print(f"[INFO] Duracion total del lote: {format_duration(total_elapsed)}")
