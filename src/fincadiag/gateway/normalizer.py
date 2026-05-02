import csv
import json
from pathlib import Path

from fincadiag.gateway.models import GatewayMessage


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _load_csv_rows(path: Path) -> list[dict]:
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _infer_visit_and_sample(session_dir: Path) -> tuple[str, str]:
    return session_dir.parent.parent.name, session_dir.name


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
                },
                source_sample_id=sample_name,
                event_type="collar_summary",
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
                    "matches": len(correlation.get("matches", [])),
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
        messages.append(
            GatewayMessage(
                topic=f"{topic_prefix}/ordeno/cow_event",
                payload=row,
                source_sample_id=sample_name,
                event_type="cow_event",
                event_timestamp=row.get("c2_timestamp", ""),
            )
        )

    return messages
