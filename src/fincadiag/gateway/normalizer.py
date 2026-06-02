import csv
import json
from pathlib import Path

from fincadiag.gateway.models import GatewayMessage


def _load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    # Los JSONs pueden venir de Windows (cp1252); se prueba utf-8 primero y fallback a cp1252.
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="cp1252")
    return json.loads(text)


def _load_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    # Mismo fallback de encoding que _load_json para archivos generados en Windows.
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="cp1252")
    if not text.strip():
        return []
    with path.open("r", encoding="utf-8", newline="", errors="replace") as handle:
        return list(csv.DictReader(handle))


def _infer_visit_and_sample(session_dir: Path) -> tuple[str, str]:
    return session_dir.parent.parent.name, session_dir.name


def _normalize_identity_status(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"confirmed", "rfid_confirmed", "identity_assigned"}:
        return "confirmed"
    if normalized in {"probable", "rfid_uncertain", "identity_uncertain"}:
        return "probable"
    return "unconfirmed"


def normalize_processed_session(session_dir: Path, topic_root: str) -> list[GatewayMessage]:
    visit_name, sample_name = _infer_visit_and_sample(session_dir)
    topic_prefix = f"{topic_root}/{visit_name}/{sample_name}"

    baseline = _load_json(session_dir / "baseline_summary.json")
    serial = _load_json(session_dir / "serial_summary.json")
    antenna = _load_json(session_dir / "antenna_udp_summary.json")
    pcap = _load_json(session_dir / "pcap_summary.json")
    correlation = _load_json(session_dir / "correlation_summary.json")
    field_validation = _load_json(session_dir / "field_validation_summary.json")
    alerts = _load_json(session_dir / "alerts.json")
    cow_events = _load_csv_rows(session_dir / "cow_events.csv")

    operation_mode = "baseline"
    if serial.get("available"):
        operation_mode = "ordeno_completo"
    elif antenna.get("available") or pcap.get("file_detected"):
        operation_mode = "telemetria_collar"

    messages = [
        GatewayMessage(
            topic=f"{topic_prefix}/session/summary",
            payload={
                "visit_name": visit_name,
                "sample_name": sample_name,
                "operation_mode": operation_mode,
                "has_baseline": bool(baseline.get("baseline_dir")),
                "has_serial": bool(serial.get("available")),
                "has_antenna_udp": bool(antenna.get("available")),
                "has_pcap": bool(pcap.get("file_detected")),
                "pcap_parsed": bool(pcap.get("available")),
                "parser_confidence_average": serial.get("parser_confidence_average", field_validation.get("semantic_confidence_average", 0.0)),
                "suppressed_microevent_count": serial.get("suppressed_noise_event_count", 0),
                "suppressed_retained_state_count": serial.get("suppressed_retained_state_event_count", 0),
            },
            source_sample_id=sample_name,
            event_type="session_summary",
        ),
        GatewayMessage(
            topic=f"{topic_prefix}/network/baseline",
            payload={
                "lat_media_ms": baseline.get("lat_media"),
                "jitter_ms": baseline.get("jitter_ms"),
                "packet_loss_pct": baseline.get("packet_loss"),
                "gateway": baseline.get("gateway"),
            },
            source_sample_id=sample_name,
            event_type="baseline_snapshot",
        ),
        GatewayMessage(
            topic=f"{topic_prefix}/network/pcap_summary",
            payload={
                "available": bool(pcap.get("available")),
                "telemetry_packets": pcap.get("telemetry", {}).get("telemetry_packets", 0),
                "signature_count": pcap.get("telemetry", {}).get("signature_count", 0),
                "multicast_pct": pcap.get("general", {}).get("multicast_pct", 0.0),
                "packet_rate_hz": pcap.get("general", {}).get("packet_rate_hz", 0.0),
                "multicast_rate_hz": pcap.get("general", {}).get("multicast_rate_hz", 0.0),
            },
            source_sample_id=sample_name,
            event_type="pcap_summary",
        ),
        GatewayMessage(
            topic=f"{topic_prefix}/security/alerts",
            payload=alerts.get("summary", {}),
            source_sample_id=sample_name,
            event_type="alerts_summary",
        ),
    ]

    if antenna.get("available"):
        messages.append(
            GatewayMessage(
                topic=f"{topic_prefix}/collar/summary",
                payload={
                    "events": antenna.get("total_events", 0),
                    "signature_count": antenna.get("signature_count", 0),
                    "avg_interval_ms": antenna.get("avg_interval_ms", 0.0),
                    "source_ip": antenna.get("source_ip", ""),
                    "source_port": antenna.get("source_port", 0),
                    "identity_confirmed_count": serial.get("identity_confirmed_count", 0),
                    "identity_probable_count": serial.get("identity_probable_count", 0),
                    "identity_unconfirmed_count": serial.get("identity_unconfirmed_count", 0),
                },
                source_sample_id=sample_name,
                event_type="collar_summary",
            )
        )

    if serial.get("available"):
        messages.append(
            GatewayMessage(
                topic=f"{topic_prefix}/ordeno/parser_summary",
                payload={
                    "cow_event_count": serial.get("cow_event_count", 0),
                    "parser_confidence_average": serial.get("parser_confidence_average", 0.0),
                    "parser_confidence_high_count": serial.get("parser_confidence_high_count", 0),
                    "parser_confidence_medium_count": serial.get("parser_confidence_medium_count", 0),
                    "parser_confidence_low_count": serial.get("parser_confidence_low_count", 0),
                    "suppressed_microevent_count": serial.get("suppressed_noise_event_count", 0),
                    "suppressed_retained_state_count": serial.get("suppressed_retained_state_event_count", 0),
                    "retained_state_suspected_count": serial.get("retained_state_suspected_count", 0),
                    "identity_confirmed_count": serial.get("identity_confirmed_count", 0),
                    "identity_probable_count": serial.get("identity_probable_count", 0),
                    "identity_unconfirmed_count": serial.get("identity_unconfirmed_count", 0),
                },
                source_sample_id=sample_name,
                event_type="parser_summary",
            )
        )

    if correlation:
        messages.append(
            GatewayMessage(
                topic=f"{topic_prefix}/ordeno/correlation",
                payload={
                    "eta_extraccion_pct": correlation.get("eta_extraccion"),
                    "desfase_medio_ms": correlation.get("desfase_medio_ms"),
                    "desfase_max_ms": correlation.get("desfase_max_ms"),
                    "matches": correlation.get("matched_events", len(correlation.get("matches", []))),
                },
                source_sample_id=sample_name,
                event_type="correlation_summary",
            )
        )

    if field_validation.get("available"):
        messages.append(
            GatewayMessage(
                topic=f"{topic_prefix}/ordeno/field_validation",
                payload={
                    "observed_cows_count": field_validation.get("observed_cows_count", 0),
                    "quick_id_count": field_validation.get("quick_id_count", 0),
                    "photocell_issue_count": field_validation.get("photocell_issue_count", 0),
                },
                source_sample_id=sample_name,
                event_type="field_validation_summary",
            )
        )

    for row in cow_events:
        payload = dict(row)
        payload["identity_status"] = _normalize_identity_status(payload.get("identity_status", ""))
        payload["parser_confidence_score"] = payload.get("parser_confidence_score", serial.get("parser_confidence_average", 0.0))
        payload["parser_confidence_label"] = payload.get("parser_confidence_label", "low")
        payload["suppressed_microevent_count"] = serial.get("suppressed_noise_event_count", 0)
        payload["suppressed_retained_state_count"] = serial.get("suppressed_retained_state_event_count", 0)
        payload["identity_confirmed"] = payload["identity_status"] == "confirmed"
        messages.append(
            GatewayMessage(
                topic=f"{topic_prefix}/ordeno/cow_event",
                payload=payload,
                source_sample_id=sample_name,
                event_type="cow_event",
                event_timestamp=row.get("c2_timestamp", ""),
            )
        )

    return messages
