from bisect import bisect_left

from fincadiag.analysis.metrics import compute_eta


def _map_serial_event(anchor_kind: str) -> str:
    mapping = {
        "C2": "fotocelda_activa",
        "E2": "rfid_leido",
        "E4": "muestra_flujo",
        "C3": "salida_vaca",
        "E0": "fin_evento",
    }
    return mapping.get(anchor_kind, str(anchor_kind or "").lower())


def correlate_events(serial: dict, network_events: list[dict], window_ms: int) -> dict:
    serial_candidates = []
    for event in serial.get("cow_events", []):
        # Se prefiere E2 (tag leído) como ancla porque marca la lectura del collar; C2 (fotocelda) es el fallback.
        anchor_ts_ms = event.get("first_e2_ts_ms")
        anchor_timestamp = event.get("first_e2_timestamp", "")
        anchor_kind = "E2"
        if anchor_ts_ms is None:
            anchor_ts_ms = event.get("c2_ts_ms")
            anchor_timestamp = event.get("c2_timestamp", "")
            anchor_kind = "C2"
        if anchor_ts_ms is None:
            continue
        serial_candidates.append(
            {
                "event_id": event.get("event_id", ""),
                "timestamp": anchor_timestamp,
                "ts_ms": anchor_ts_ms,
                "anchor_kind": anchor_kind,
                "status": event.get("status", "incomplete"),
            }
        )

    if not serial_candidates or not network_events:
        return {
            "network_mode": "sin_datos",
            "serial_events": len(serial_candidates),
            "network_events": 0,
            "matched_events": 0,
            "unmatched_serial_events": len(serial_candidates),
            "eta_extraccion": 0.0,
            "desfase_medio_ms": 0.0,
            "desfase_max_ms": 0.0,
            "desfase_firmado_medio_ms": 0.0,
            "matches": [],
        }

    # Si hay firmas 56 D1 00 se usan como ancla de red de alta confianza; si no, se usa todo el canal 6001.
    signature_candidates = [row for row in network_events if row["event_kind"] == "firma_56d100"]
    if signature_candidates:
        candidate_events = sorted(signature_candidates, key=lambda row: row["day_ms"])
        network_mode = "firma_56d100"
    else:
        candidate_events = sorted(network_events, key=lambda row: row["day_ms"])
        network_mode = "payload_port_6001"

    network_times = [row["day_ms"] for row in candidate_events]
    matches = []

    for serial_row in sorted(serial_candidates, key=lambda row: row["ts_ms"]):
        # bisect ubica el punto de inserción; los dos vecinos inmediatos son los únicos candidatos válidos de mínimo delta.
        pos = bisect_left(network_times, serial_row["ts_ms"])
        best = None
        for idx in (pos - 1, pos):
            if 0 <= idx < len(candidate_events):
                net_row = candidate_events[idx]
                delta_ms = int(net_row["day_ms"]) - int(serial_row["ts_ms"])
                abs_delta = abs(delta_ms)
                if best is None or abs_delta < best["abs_delta_ms"]:
                    best = {
                        "event_id": serial_row["event_id"],
                        "timestamp_serial": serial_row["timestamp"],
                        "serial_timestamp": serial_row["timestamp"],
                        "serial_event": _map_serial_event(serial_row["anchor_kind"]),
                        "serial_status": serial_row["status"],
                        "network_timestamp": net_row["timestamp"],
                        "network_event": net_row["event_kind"],
                        "network_payload": net_row["payload_hex"],
                        "delta_ms": delta_ms,
                        "abs_delta_ms": abs_delta,
                        "matched": abs_delta <= window_ms,
                    }
        if best:
            matches.append(best)

    matched = [row for row in matches if row["matched"]]
    abs_deltas = [row["abs_delta_ms"] for row in matched]
    signed_deltas = [row["delta_ms"] for row in matched]
    return {
        "network_mode": network_mode,
        "serial_events": len(serial_candidates),
        "network_events": len(candidate_events),
        "matched_events": len(matched),
        "unmatched_serial_events": len(serial_candidates) - len(matched),
        "eta_extraccion": compute_eta(len(matched), len(serial_candidates)),
        "desfase_medio_ms": round(sum(abs_deltas) / len(abs_deltas), 3) if abs_deltas else 0.0,
        "desfase_max_ms": max(abs_deltas) if abs_deltas else 0.0,
        "desfase_firmado_medio_ms": round(sum(signed_deltas) / len(signed_deltas), 3) if signed_deltas else 0.0,
        "matches": matches,
    }
