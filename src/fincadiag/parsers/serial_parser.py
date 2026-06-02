import re
from collections import Counter
from pathlib import Path

from fincadiag.models import CowBatch, CowEvent, FlowSample, SerialFrame
from fincadiag.utils import read_text, time_str_to_ms


LINE_PATTERN = re.compile(r"^\[(\d{2}:\d{2}:\d{2}\.\d{3})\]\s*(.*?)\s*$")
HEARTBEAT_SEQUENCES = (
    ["A4", "82", "04", "A0"],
    ["A4", "82", "05", "A0"],
)
CONTROL_BYTES = {"A0", "A1", "A4", "A5"}
COW_MARKERS = {"C2", "C3", "E0", "E2", "E3"}
FLOW_MARKER = "E4"
RECONSTRUCTION_WINDOW_MS = 50
HEARTBEAT_EXPECTED_MS = 5000
HEARTBEAT_GAP_THRESHOLD_MS = 15000
RFID_TIMEOUT_MS = 30000
E2_ASSIGNMENT_WINDOW_MS = 30000
FLOW_IDLE_TIMEOUT_MS = 15000
MAX_BATCH_SLOTS = 6
C2_DUPLICATE_WINDOW_MS = 1200
E0_ATTACH_WINDOW_MS = 10000
BATCH_STALE_GAP_MS = 120000
TEMP_PREP_WINDOW_MS = 45000
CADENCE_STEP_MS = 127000
CADENCE_TOLERANCE_MS = 12000
OPERATIONAL_ANCHOR_MIN_STEPS = 4
NOISE_EVENT_MAX_DWELL_MS = 5000
E2_GRACE_AFTER_C3_MS = 15000


def _contains_subsequence(tokens: list[str], subsequence: list[str]) -> bool:
    if len(tokens) < len(subsequence):
        return False
    limit = len(tokens) - len(subsequence) + 1
    for idx in range(limit):
        if tokens[idx : idx + len(subsequence)] == subsequence:
            return True
    return False


def _extract_tokens(payload: str) -> list[str]:
    return [token for token in payload.split() if re.fullmatch(r"[0-9A-F]{2}", token)]


def _attach_monotonic_times(rows: list[dict]) -> None:
    if not rows:
        return
    offset = 0
    previous = rows[0]["ts_ms"]
    for row in rows:
        current = row["ts_ms"]
        if current + offset < previous and previous - (current + offset) > 12 * 3600 * 1000:
            offset += 24 * 3600 * 1000
        row["abs_ts_ms"] = current + offset
        previous = row["abs_ts_ms"]


def _parse_raw_rows(text: str) -> tuple[list[dict], int, int, list[dict]]:
    rows = []
    total_lines = 0
    malformed_lines = 0
    unparsed_rows = []

    for line_index, raw_line in enumerate(text.splitlines(), start=1):
        total_lines += 1
        stripped = raw_line.strip()
        if not stripped:
            continue

        match = LINE_PATTERN.match(stripped)
        if not match:
            malformed_lines += 1
            unparsed_rows.append(
                {
                    "line_index": line_index,
                    "raw_line": stripped,
                    "reason": "linea_fuera_de_formato",
                }
            )
            continue

        ts_str = match.group(1)
        payload_raw = match.group(2).upper().strip()
        tokens = _extract_tokens(payload_raw)
        if not tokens:
            malformed_lines += 1
            unparsed_rows.append(
                {
                    "line_index": line_index,
                    "raw_line": stripped,
                    "reason": "sin_tokens_hex_validos",
                }
            )
            continue

        rows.append(
            {
                "timestamp": ts_str,
                "ts_ms": time_str_to_ms(ts_str),
                "payload_raw": payload_raw,
                "tokens_hex": tokens,
                "line_index": line_index,
            }
        )

    _attach_monotonic_times(rows)
    return rows, total_lines, malformed_lines, unparsed_rows


def _reconstruct_frames(rows: list[dict]) -> list[SerialFrame]:
    frames: list[SerialFrame] = []
    if not rows:
        return frames

    current_group = [rows[0]]
    group_id = 1

    def flush_group(group_rows: list[dict], fragment_group_id: int) -> None:
        tokens = []
        raw_payloads = []
        for row in group_rows:
            tokens.extend(row["tokens_hex"])
            raw_payloads.append(row["payload_raw"])

        markers = [token for token in tokens if token in COW_MARKERS]
        has_control = any(token in CONTROL_BYTES for token in tokens)
        has_flow = FLOW_MARKER in tokens
        has_markers = bool(markers)

        if has_markers and (has_control or has_flow):
            channel = "mixed"
            frame_type = "mixed"
        elif has_markers:
            channel = "evento_vaca"
            frame_type = "cow_marker"
        elif has_flow:
            channel = "sensor_flujo"
            frame_type = "flow_sample" if len(tokens) <= 3 else "flow_burst"
        elif has_control:
            channel = "control_plc"
            frame_type = "heartbeat" if any(_contains_subsequence(tokens, seq) for seq in HEARTBEAT_SEQUENCES) else "control_frame"
        else:
            channel = "desconocido"
            frame_type = "unknown"

        flow_value_raw = None
        flow_value_inverted = None
        if FLOW_MARKER in tokens:
            idx = tokens.index(FLOW_MARKER)
            if idx + 1 < len(tokens) and re.fullmatch(r"[0-9A-F]{2}", tokens[idx + 1]):
                flow_value_raw = int(tokens[idx + 1], 16)
                flow_value_inverted = 255 - flow_value_raw

        frames.append(
            SerialFrame(
                frame_index=len(frames) + 1,
                fragment_group_id=fragment_group_id,
                timestamp=group_rows[0]["timestamp"],
                ts_ms=group_rows[0]["abs_ts_ms"],
                payload_raw=" | ".join(raw_payloads),
                payload_hex=" ".join(tokens),
                line_index_start=group_rows[0]["line_index"],
                line_index_end=group_rows[-1]["line_index"],
                line_count=len(group_rows),
                length=len(tokens),
                first_byte=tokens[0],
                last_byte=tokens[-1],
                channel=channel,
                frame_type=frame_type,
                markers=markers,
                heartbeat_candidate=any(_contains_subsequence(tokens, seq) for seq in HEARTBEAT_SEQUENCES),
                flow_value_raw=flow_value_raw,
                flow_value_inverted=flow_value_inverted,
            )
        )

    for row in rows[1:]:
        first_ts = current_group[0]["abs_ts_ms"]
        previous_ts = current_group[-1]["abs_ts_ms"]
        gap_ms = row["abs_ts_ms"] - previous_ts
        span_ms = row["abs_ts_ms"] - first_ts
        if gap_ms <= RECONSTRUCTION_WINDOW_MS and span_ms <= RECONSTRUCTION_WINDOW_MS:
            current_group.append(row)
        else:
            flush_group(current_group, group_id)
            group_id += 1
            current_group = [row]

    flush_group(current_group, group_id)
    return frames


def _build_marker_rows(frames: list[SerialFrame]) -> list[dict]:
    marker_rows = []
    for frame in frames:
        for marker in frame.markers:
            marker_rows.append(
                {
                    "frame_index": frame.frame_index,
                    "timestamp": frame.timestamp,
                    "ts_ms": frame.ts_ms,
                    "marker": marker,
                    "payload_hex": frame.payload_hex,
                    "channel": frame.channel,
                }
            )
    return marker_rows


def _build_flow_samples(frames: list[SerialFrame]) -> list[FlowSample]:
    samples: list[FlowSample] = []
    for frame in frames:
        if frame.flow_value_raw is None or frame.flow_value_inverted is None:
            continue
        samples.append(
            FlowSample(
                sample_index=len(samples) + 1,
                frame_index=frame.frame_index,
                timestamp=frame.timestamp,
                ts_ms=frame.ts_ms,
                value_raw=frame.flow_value_raw,
                value_inverted=frame.flow_value_inverted,
            )
        )
    return samples


def _create_batch(marker_row: dict, batch_index: int) -> dict:
    batch_id = f"batch_{batch_index:03d}"
    return {
        "batch_id": batch_id,
        "batch_index": batch_index,
        "start_timestamp": marker_row["timestamp"],
        "start_ts_ms": marker_row["ts_ms"],
        "last_marker_timestamp": marker_row["timestamp"],
        "last_marker_ts_ms": marker_row["ts_ms"],
        "slot_counter": 0,
        "events": [],
        "active_slots": [],
    }


def _create_raw_event(batch: dict, marker_row: dict) -> dict:
    batch["slot_counter"] += 1
    raw_event = {
        "batch_id": batch["batch_id"],
        "batch_index": batch["batch_index"],
        "slot_index": batch["slot_counter"],
        "event_id": f"{batch['batch_id']}_slot_{batch['slot_counter']:02d}",
        "c2_timestamp": marker_row["timestamp"],
        "c2_ts_ms": marker_row["ts_ms"],
        "last_c2_timestamp": marker_row["timestamp"],
        "last_c2_ts_ms": marker_row["ts_ms"],
        "c2_count": 1,
        "first_e2_timestamp": "",
        "first_e2_ts_ms": None,
        "c3_timestamp": "",
        "c3_ts_ms": None,
        "first_e0_timestamp": "",
        "first_e0_ts_ms": None,
        "rfid_read_count": 0,
    }
    batch["events"].append(raw_event)
    batch["active_slots"].append(raw_event)
    return raw_event


def _touch_batch(batch: dict | None, marker_row: dict) -> None:
    if batch is None:
        return
    batch["last_marker_timestamp"] = marker_row["timestamp"]
    batch["last_marker_ts_ms"] = marker_row["ts_ms"]


def _should_start_new_batch(batch: dict | None, marker_row: dict) -> bool:
    if batch is None:
        return True
    if not batch["active_slots"] and batch["slot_counter"] > 0:
        return True
    gap_ms = marker_row["ts_ms"] - batch.get("last_marker_ts_ms", batch["start_ts_ms"])
    if gap_ms > BATCH_STALE_GAP_MS:
        return True
    return False


def _select_latest_active_slot(batch: dict) -> dict | None:
    if not batch["active_slots"]:
        return None
    return max(batch["active_slots"], key=lambda item: (item["last_c2_ts_ms"], item["slot_index"]))


def _merge_c2_into_slot(slot: dict, marker_row: dict) -> None:
    slot["c2_count"] += 1
    slot["last_c2_timestamp"] = marker_row["timestamp"]
    slot["last_c2_ts_ms"] = marker_row["ts_ms"]


def _pick_e2_target(batch: dict | None, marker_row: dict) -> dict | None:
    if batch is None:
        return None
    missing_rfid = [
        slot
        for slot in batch["active_slots"]
        if slot.get("first_e2_ts_ms") is None and slot.get("c3_ts_ms") is None
    ]
    recent_missing = [
        slot
        for slot in missing_rfid
        if 0
        <= marker_row["ts_ms"] - slot.get("last_c2_ts_ms", slot["c2_ts_ms"])
        <= E2_ASSIGNMENT_WINDOW_MS
    ]
    if recent_missing:
        return max(
            recent_missing,
            key=lambda item: (item.get("last_c2_ts_ms", item["c2_ts_ms"]), item["slot_index"]),
        )
    if len(missing_rfid) == 1:
        only_slot = missing_rfid[0]
        delay_ms = marker_row["ts_ms"] - only_slot.get("last_c2_ts_ms", only_slot["c2_ts_ms"])
        if 0 <= delay_ms <= RFID_TIMEOUT_MS:
            return only_slot
    reread_candidates = sorted(
        [
            slot
            for slot in batch["active_slots"]
            if slot.get("first_e2_ts_ms") is not None
            and slot.get("c3_ts_ms") is None
            and 0 <= marker_row["ts_ms"] - slot["first_e2_ts_ms"] <= E2_ASSIGNMENT_WINDOW_MS
        ],
        key=lambda item: (item.get("last_c2_ts_ms", item["c2_ts_ms"]), item["slot_index"]),
    )
    if reread_candidates:
        return reread_candidates[-1]
    grace_candidates = sorted(
        [
            slot
            for slot in batch["events"]
            if slot.get("first_e2_ts_ms") is None
            and slot.get("c3_ts_ms") is not None
            and 0 <= marker_row["ts_ms"] - slot["c3_ts_ms"] <= E2_GRACE_AFTER_C3_MS
        ],
        key=lambda item: (item["c3_ts_ms"], item["slot_index"]),
    )
    return grace_candidates[-1] if grace_candidates else None


def _pick_c3_target(batch: dict | None) -> dict | None:
    if batch is None:
        return None
    identified = sorted(
        [slot for slot in batch["active_slots"] if slot.get("first_e2_ts_ms") is not None and slot.get("c3_ts_ms") is None],
        key=lambda item: (item["c2_ts_ms"], item["slot_index"]),
    )
    if identified:
        return identified[0]
    fallback = sorted(
        [slot for slot in batch["active_slots"] if slot.get("c3_ts_ms") is None],
        key=lambda item: (item["c2_ts_ms"], item["slot_index"]),
    )
    return fallback[0] if fallback else None


def _pick_e0_target(batch: dict | None, marker_row: dict) -> dict | None:
    if batch is None:
        return None
    candidates = []
    for slot in reversed(batch["events"]):
        if slot.get("first_e0_ts_ms") is not None:
            continue
        anchor_ts_ms = slot.get("c3_ts_ms") or slot.get("first_e2_ts_ms")
        if anchor_ts_ms is None:
            continue
        if marker_row["ts_ms"] < anchor_ts_ms:
            continue
        if marker_row["ts_ms"] - anchor_ts_ms > E0_ATTACH_WINDOW_MS:
            continue
        candidates.append(slot)
    return candidates[0] if candidates else None


def _compute_event_end(event: dict, batch: dict, next_batch: dict | None) -> tuple[str, int | None]:
    first_e2_ts_ms = event.get("first_e2_ts_ms")
    c3_ts_ms = event.get("c3_ts_ms")
    first_e0_ts_ms = event.get("first_e0_ts_ms")
    next_batch_start_ts_ms = next_batch.get("start_ts_ms") if next_batch else None

    if c3_ts_ms is not None:
        return event.get("c3_timestamp", ""), c3_ts_ms

    if (
        first_e0_ts_ms is not None
        and first_e2_ts_ms is not None
        and first_e0_ts_ms >= first_e2_ts_ms
    ):
        return event.get("first_e0_timestamp", ""), first_e0_ts_ms

    if next_batch_start_ts_ms is not None and next_batch_start_ts_ms >= event["c2_ts_ms"]:
        return next_batch.get("start_timestamp", ""), next_batch_start_ts_ms

    return batch.get("last_marker_timestamp", ""), batch.get("last_marker_ts_ms")


def _build_event_windows(raw_batches: list[dict]) -> list[dict]:
    event_windows = []
    for batch_index, batch in enumerate(raw_batches):
        next_batch = raw_batches[batch_index + 1] if batch_index + 1 < len(raw_batches) else None
        for event in batch["events"]:
            flow_start_ts_ms = event.get("first_e2_ts_ms") or event["c2_ts_ms"]
            event_end_timestamp, event_end_ts_ms = _compute_event_end(event, batch, next_batch)
            event_windows.append(
                {
                    "batch_id": batch["batch_id"],
                    "event_id": event["event_id"],
                    "flow_start_ts_ms": flow_start_ts_ms,
                    "event_end_timestamp": event_end_timestamp,
                    "event_end_ts_ms": event_end_ts_ms,
                }
            )
    return event_windows


def _compute_cadence_metrics(dwell_ms: int | None) -> tuple[int, int | None, bool]:
    if dwell_ms is None or dwell_ms <= 0:
        return 0, None, False
    step_index = max(1, round(dwell_ms / CADENCE_STEP_MS))
    offset_ms = int(dwell_ms - (step_index * CADENCE_STEP_MS))
    cadence_aligned = abs(offset_ms) <= CADENCE_TOLERANCE_MS
    return step_index, offset_ms, cadence_aligned


def _infer_identity_status(first_e2_ts_ms: int | None, rfid_latency_ms: int | None, rfid_read_count: int) -> str:
    if first_e2_ts_ms is None:
        return "unconfirmed"
    if rfid_latency_ms is not None and rfid_latency_ms <= RFID_TIMEOUT_MS:
        return "confirmed"
    if rfid_read_count > 0:
        return "probable"
    return "unconfirmed"


def _is_retained_state_suspected(
    first_e2_ts_ms: int | None,
    rfid_latency_ms: int | None,
    filtered_samples: list[FlowSample],
    ambiguous_flow_sample_count: int,
    cadence_aligned: bool,
    c3_ts_ms: int | None,
) -> bool:
    return (
        first_e2_ts_ms is not None
        and rfid_latency_ms is not None
        and rfid_latency_ms > RFID_TIMEOUT_MS
        and not filtered_samples
        and ambiguous_flow_sample_count == 0
        and c3_ts_ms is not None
        and cadence_aligned
    )


def _infer_parser_confidence(
    first_e2_ts_ms: int | None,
    rfid_latency_ms: int | None,
    filtered_samples: list[FlowSample],
    ambiguous_flow_sample_count: int,
    cadence_aligned: bool,
    c3_ts_ms: int | None,
    retained_state_suspected: bool,
) -> tuple[float, str]:
    score = 0.2
    if first_e2_ts_ms is not None:
        score += 0.25
    if rfid_latency_ms is not None and rfid_latency_ms <= RFID_TIMEOUT_MS:
        score += 0.2
    elif rfid_latency_ms is not None:
        score -= 0.15
    if filtered_samples:
        score += 0.25
    if c3_ts_ms is not None:
        score += 0.1
    if ambiguous_flow_sample_count > 0:
        score -= 0.1
    if retained_state_suspected:
        score -= 0.25
    elif cadence_aligned and not filtered_samples:
        score -= 0.05
    score = max(0.0, min(1.0, round(score, 3)))
    if score >= 0.75:
        return score, "high"
    if score >= 0.45:
        return score, "medium"
    return score, "low"


def _assign_flow_samples(
    event_windows: list[dict], flow_samples: list[FlowSample]
) -> tuple[dict[str, list[FlowSample]], dict[str, int], Counter, Counter]:
    assigned_samples: dict[str, list[FlowSample]] = {window["event_id"]: [] for window in event_windows}
    ambiguous_counts: dict[str, int] = {window["event_id"]: 0 for window in event_windows}
    batch_assigned = Counter()
    batch_ambiguous = Counter()

    for sample in flow_samples:
        owners = []
        for window in event_windows:
            start_ts_ms = window["flow_start_ts_ms"]
            end_ts_ms = window["event_end_ts_ms"]
            if start_ts_ms is None or end_ts_ms is None:
                continue
            if sample.ts_ms < start_ts_ms or sample.ts_ms > end_ts_ms:
                continue
            owners.append(window)

        if len(owners) == 1:
            owner = owners[0]
            assigned_samples[owner["event_id"]].append(sample)
            sample.owner_event_id = owner["event_id"]
            batch_assigned[owner["batch_id"]] += 1
            continue

        if len(owners) > 1:
            batch_ids = {owner["batch_id"] for owner in owners}
            for owner in owners:
                ambiguous_counts[owner["event_id"]] += 1
            for batch_id in batch_ids:
                batch_ambiguous[batch_id] += 1

    return assigned_samples, ambiguous_counts, batch_assigned, batch_ambiguous


def _finalize_cow_event(
    event: dict,
    batch: dict,
    next_batch: dict | None,
    assigned_samples: dict[str, list[FlowSample]],
    ambiguous_counts: dict[str, int],
) -> CowEvent:
    event_end_timestamp, event_end_ts_ms = _compute_event_end(event, batch, next_batch)
    owned_samples = assigned_samples.get(event["event_id"], [])
    ambiguous_flow_sample_count = ambiguous_counts.get(event["event_id"], 0)

    filtered_samples = []
    last_owned_ts_ms = None
    for sample in owned_samples:
        if last_owned_ts_ms is not None and sample.ts_ms - last_owned_ts_ms > FLOW_IDLE_TIMEOUT_MS:
            break
        filtered_samples.append(sample)
        last_owned_ts_ms = sample.ts_ms

    flow_raw_values = [sample.value_raw for sample in filtered_samples]
    flow_inverted_values = [sample.value_inverted for sample in filtered_samples]
    flow_sum_raw = sum(flow_raw_values)
    flow_sum_inverted = sum(flow_inverted_values)

    first_e2_ts_ms = event.get("first_e2_ts_ms")
    c3_ts_ms = event.get("c3_ts_ms")
    rfid_latency_ms = (first_e2_ts_ms - event["c2_ts_ms"]) if first_e2_ts_ms is not None else None
    dwell_ms = (c3_ts_ms - event["c2_ts_ms"]) if c3_ts_ms is not None else None
    cadence_step_index, cadence_offset_ms, cadence_aligned = _compute_cadence_metrics(dwell_ms)
    flow_expectation_anchor_ts_ms = first_e2_ts_ms or event["c2_ts_ms"]
    prep_phase_elapsed_ms = None
    if event_end_ts_ms is not None:
        prep_phase_elapsed_ms = max(0, event_end_ts_ms - flow_expectation_anchor_ts_ms)
    in_prep_phase_without_flow = (
        not filtered_samples
        and ambiguous_flow_sample_count == 0
        and prep_phase_elapsed_ms is not None
        and prep_phase_elapsed_ms <= TEMP_PREP_WINDOW_MS
    )

    notes = []
    if rfid_latency_ms is not None and rfid_latency_ms > RFID_TIMEOUT_MS:
        notes.append("rfid_fuera_de_ventana")
    if event.get("c2_count", 1) > 1:
        notes.append("c2_repetido")
    if event.get("rfid_read_count", 0) > 1:
        notes.append("multiples_e2")
    if not filtered_samples:
        notes.append("sin_flujo_asignado")
    if ambiguous_flow_sample_count > 0:
        notes.append("flujo_ambiguo_en_lote")
    if in_prep_phase_without_flow:
        notes.append("ventana_temporal_preparacion")
    if cadence_aligned:
        notes.append("cadencia_127s")

    retained_state_suspected = _is_retained_state_suspected(
        first_e2_ts_ms,
        rfid_latency_ms,
        filtered_samples,
        ambiguous_flow_sample_count,
        cadence_aligned,
        c3_ts_ms,
    )
    if retained_state_suspected:
        notes.append("estado_retenido_probable")

    identity_status = _infer_identity_status(first_e2_ts_ms, rfid_latency_ms, event.get("rfid_read_count", 0))
    parser_confidence_score, parser_confidence_label = _infer_parser_confidence(
        first_e2_ts_ms,
        rfid_latency_ms,
        filtered_samples,
        ambiguous_flow_sample_count,
        cadence_aligned,
        c3_ts_ms,
        retained_state_suspected,
    )

    if first_e2_ts_ms is None:
        status = "missing_rfid"
    elif rfid_latency_ms is not None and rfid_latency_ms > RFID_TIMEOUT_MS:
        status = "missing_rfid"
    elif not filtered_samples and ambiguous_flow_sample_count > 0:
        status = "partial"
    elif in_prep_phase_without_flow:
        status = "partial"
    elif not filtered_samples and cadence_aligned and c3_ts_ms is not None:
        status = "partial"
    elif not filtered_samples:
        status = "missing_flow"
    elif c3_ts_ms is None:
        status = "partial"
    else:
        status = "success"

    return CowEvent(
        batch_id=event["batch_id"],
        slot_index=event["slot_index"],
        event_id=event["event_id"],
        c2_timestamp=event["c2_timestamp"],
        c2_ts_ms=event["c2_ts_ms"],
        last_c2_timestamp=event.get("last_c2_timestamp", event["c2_timestamp"]),
        last_c2_ts_ms=event.get("last_c2_ts_ms", event["c2_ts_ms"]),
        c2_count=event.get("c2_count", 1),
        first_e2_timestamp=event.get("first_e2_timestamp", ""),
        first_e2_ts_ms=first_e2_ts_ms,
        c3_timestamp=event.get("c3_timestamp", ""),
        c3_ts_ms=c3_ts_ms,
        first_e0_timestamp=event.get("first_e0_timestamp", ""),
        first_e0_ts_ms=event.get("first_e0_ts_ms"),
        event_end_timestamp=event_end_timestamp,
        event_end_ts_ms=event_end_ts_ms,
        status=status,
        rfid_latency_ms=rfid_latency_ms,
        dwell_ms=dwell_ms,
        cadence_step_index=cadence_step_index,
        cadence_offset_ms=cadence_offset_ms,
        cadence_aligned=cadence_aligned,
        flow_sample_count=len(filtered_samples),
        ambiguous_flow_sample_count=ambiguous_flow_sample_count,
        flow_value_sum_raw=flow_sum_raw,
        flow_value_sum_inverted=flow_sum_inverted,
        flow_value_avg_raw=round(flow_sum_raw / len(filtered_samples), 3) if filtered_samples else 0.0,
        flow_value_avg_inverted=round(flow_sum_inverted / len(filtered_samples), 3) if filtered_samples else 0.0,
        flow_peak_raw=max(flow_raw_values) if filtered_samples else 0,
        flow_peak_inverted=max(flow_inverted_values) if filtered_samples else 0,
        flow_start_timestamp=filtered_samples[0].timestamp if filtered_samples else "",
        flow_end_timestamp=filtered_samples[-1].timestamp if filtered_samples else "",
        rfid_read_count=event.get("rfid_read_count", 0),
        identity_status=identity_status,
        parser_confidence_score=parser_confidence_score,
        parser_confidence_label=parser_confidence_label,
        retained_state_suspected=retained_state_suspected,
        notes=notes,
    )


def _is_noise_event(event: CowEvent) -> bool:
    return (
        event.first_e2_ts_ms is None
        and event.flow_sample_count == 0
        and event.ambiguous_flow_sample_count == 0
        and event.c3_ts_ms is not None
        and event.dwell_ms is not None
        and event.dwell_ms <= NOISE_EVENT_MAX_DWELL_MS
        and event.c2_count <= 1
    )


def _is_retained_state_event(event: CowEvent) -> bool:
    return event.retained_state_suspected and event.flow_sample_count == 0 and event.ambiguous_flow_sample_count == 0


def _build_cow_batches(
    raw_batches: list[dict],
    cow_events: list[CowEvent],
    flow_samples: list[FlowSample],
    batch_assigned: Counter,
    batch_ambiguous: Counter,
) -> list[CowBatch]:
    events_by_batch: dict[str, list[CowEvent]] = {}
    for event in cow_events:
        events_by_batch.setdefault(event.batch_id, []).append(event)

    cow_batches = []
    for batch in raw_batches:
        batch_events = sorted(
            events_by_batch.get(batch["batch_id"], []),
            key=lambda item: (item.slot_index, item.c2_ts_ms),
        )
        status_counts = Counter(event.status for event in batch_events)
        cadence_steps = Counter(event.cadence_step_index for event in batch_events if event.cadence_aligned and event.cadence_step_index > 0)
        batch_flow_total = sum(
            1
            for sample in flow_samples
            if batch["start_ts_ms"] <= sample.ts_ms <= batch["last_marker_ts_ms"]
        )
        cow_batches.append(
            CowBatch(
                batch_id=batch["batch_id"],
                batch_index=batch["batch_index"],
                start_timestamp=batch["start_timestamp"],
                start_ts_ms=batch["start_ts_ms"],
                end_timestamp=batch["last_marker_timestamp"],
                end_ts_ms=batch["last_marker_ts_ms"],
                slot_count=len(batch_events),
                completed_count=sum(1 for event in batch_events if event.c3_ts_ms is not None),
                missing_rfid_count=status_counts.get("missing_rfid", 0),
                missing_flow_count=status_counts.get("missing_flow", 0),
                partial_count=status_counts.get("partial", 0),
                success_count=status_counts.get("success", 0),
                cadence_aligned_count=sum(1 for event in batch_events if event.cadence_aligned),
                cadence_dominant_step=cadence_steps.most_common(1)[0][0] if cadence_steps else 0,
                total_flow_samples=batch_flow_total,
                assigned_flow_samples=int(batch_assigned.get(batch["batch_id"], 0)),
                ambiguous_flow_samples=int(batch_ambiguous.get(batch["batch_id"], 0)),
            )
        )

    return cow_batches


def _build_operational_groups(cow_batches: list[CowBatch], cow_events: list[CowEvent]) -> list[dict]:
    if not cow_batches:
        return []

    min_anchor_duration_ms = OPERATIONAL_ANCHOR_MIN_STEPS * CADENCE_STEP_MS
    anchor_indices = [
        idx
        for idx, batch in enumerate(cow_batches)
        if batch.slot_count >= 5 and batch.end_ts_ms is not None and (batch.end_ts_ms - batch.start_ts_ms) >= min_anchor_duration_ms
    ]
    if not anchor_indices:
        anchor_indices = [
            idx
            for idx, batch in enumerate(cow_batches)
            if batch.slot_count >= 5 and batch.end_ts_ms is not None and (batch.end_ts_ms - batch.start_ts_ms) >= 2 * CADENCE_STEP_MS
        ]
    if not anchor_indices:
        anchor_indices = list(range(len(cow_batches)))

    groups = []
    group_members: dict[int, list[int]] = {anchor_idx: [] for anchor_idx in anchor_indices}

    for idx, batch in enumerate(cow_batches):
        batch_mid = batch.start_ts_ms if batch.end_ts_ms is None else (batch.start_ts_ms + batch.end_ts_ms) // 2
        nearest_anchor = min(
            anchor_indices,
            key=lambda anchor_idx: abs(
                batch_mid
                - (
                    cow_batches[anchor_idx].start_ts_ms
                    if cow_batches[anchor_idx].end_ts_ms is None
                    else (cow_batches[anchor_idx].start_ts_ms + cow_batches[anchor_idx].end_ts_ms) // 2
                )
            ),
        )
        group_members[nearest_anchor].append(idx)

    batch_to_group_id = {}
    for group_index, anchor_idx in enumerate(anchor_indices, start=1):
        member_indices = sorted(group_members.get(anchor_idx, []))
        if not member_indices:
            continue
        group_id = f"op_batch_{group_index:03d}"
        anchor_batch = cow_batches[anchor_idx]
        for member_idx in member_indices:
            batch = cow_batches[member_idx]
            batch.operational_group_id = group_id
            batch.operational_group_index = group_index
            batch.is_operational_anchor = member_idx == anchor_idx
            batch_to_group_id[batch.batch_id] = group_id

        member_batches = [cow_batches[member_idx] for member_idx in member_indices]
        member_events = [event for event in cow_events if event.batch_id in {batch.batch_id for batch in member_batches}]
        status_counts = Counter(event.status for event in member_events)
        groups.append(
            {
                "operational_group_id": group_id,
                "operational_group_index": group_index,
                "anchor_batch_id": anchor_batch.batch_id,
                "start_timestamp": member_batches[0].start_timestamp,
                "start_ts_ms": member_batches[0].start_ts_ms,
                "end_timestamp": member_batches[-1].end_timestamp,
                "end_ts_ms": member_batches[-1].end_ts_ms,
                "raw_batch_count": len(member_batches),
                "raw_batch_ids": ",".join(batch.batch_id for batch in member_batches),
                "slot_count_sum": sum(batch.slot_count for batch in member_batches),
                "event_count": len(member_events),
                "success_count": status_counts.get("success", 0),
                "missing_rfid_count": status_counts.get("missing_rfid", 0),
                "missing_flow_count": status_counts.get("missing_flow", 0),
                "partial_count": status_counts.get("partial", 0),
                "cadence_aligned_count": sum(1 for event in member_events if event.cadence_aligned),
            }
        )

    for event in cow_events:
        event.operational_batch_id = batch_to_group_id.get(event.batch_id, "")

    return groups


def _reconstruct_cow_events(
    marker_rows: list[dict], flow_samples: list[FlowSample]
) -> tuple[list[CowEvent], list[CowBatch], dict]:
    raw_batches: list[dict] = []
    current_batch = None
    orphans = {"c3": 0, "e2": 0, "e0": 0, "e3": 0, "suppressed_noise": 0, "suppressed_retained_state": 0}

    for marker_row in marker_rows:
        marker = marker_row["marker"]
        _touch_batch(current_batch, marker_row)

        if marker == "C2":
            if _should_start_new_batch(current_batch, marker_row):
                current_batch = _create_batch(marker_row, len(raw_batches) + 1)
                raw_batches.append(current_batch)

            latest_slot = _select_latest_active_slot(current_batch)
            if (
                latest_slot is not None
                and latest_slot.get("first_e2_ts_ms") is None
                and marker_row["ts_ms"] - latest_slot.get("last_c2_ts_ms", latest_slot["c2_ts_ms"]) <= C2_DUPLICATE_WINDOW_MS
            ):
                _merge_c2_into_slot(latest_slot, marker_row)
                continue

            if current_batch["slot_counter"] < MAX_BATCH_SLOTS:
                _create_raw_event(current_batch, marker_row)
            elif latest_slot is not None:
                _merge_c2_into_slot(latest_slot, marker_row)
            else:
                current_batch = _create_batch(marker_row, len(raw_batches) + 1)
                raw_batches.append(current_batch)
                _create_raw_event(current_batch, marker_row)
            continue

        if marker == "E2":
            target = _pick_e2_target(current_batch, marker_row)
            if target is None:
                orphans["e2"] += 1
                continue
            target["rfid_read_count"] += 1
            if target["first_e2_ts_ms"] is None:
                target["first_e2_timestamp"] = marker_row["timestamp"]
                target["first_e2_ts_ms"] = marker_row["ts_ms"]
            continue

        if marker == "C3":
            target = _pick_c3_target(current_batch)
            if target is None:
                orphans["c3"] += 1
                continue
            if target["c3_ts_ms"] is None:
                target["c3_timestamp"] = marker_row["timestamp"]
                target["c3_ts_ms"] = marker_row["ts_ms"]
            current_batch["active_slots"] = [
                slot for slot in current_batch["active_slots"] if slot["event_id"] != target["event_id"]
            ]
            continue

        if marker == "E0":
            target = _pick_e0_target(current_batch, marker_row)
            if target is None:
                orphans["e0"] += 1
                continue
            if target["first_e0_ts_ms"] is None:
                target["first_e0_timestamp"] = marker_row["timestamp"]
                target["first_e0_ts_ms"] = marker_row["ts_ms"]
            continue

        if marker == "E3":
            orphans["e3"] += 1

    event_windows = _build_event_windows(raw_batches)
    assigned_samples, ambiguous_counts, batch_assigned, batch_ambiguous = _assign_flow_samples(event_windows, flow_samples)

    finalized_events = []
    for batch_index, batch in enumerate(raw_batches):
        next_batch = raw_batches[batch_index + 1] if batch_index + 1 < len(raw_batches) else None
        ordered_raw_events = sorted(batch["events"], key=lambda item: (item["slot_index"], item["c2_ts_ms"]))
        for raw_event in ordered_raw_events:
            finalized_events.append(
                _finalize_cow_event(raw_event, batch, next_batch, assigned_samples, ambiguous_counts)
            )

    cow_events = []
    for event in finalized_events:
        if _is_noise_event(event):
            orphans["suppressed_noise"] += 1
            continue
        if _is_retained_state_event(event):
            orphans["suppressed_retained_state"] += 1
            continue
        cow_events.append(event)

    cow_batches = _build_cow_batches(raw_batches, cow_events, flow_samples, batch_assigned, batch_ambiguous)
    return cow_events, cow_batches, orphans


def _build_coverage_summary(frames: list[SerialFrame]) -> dict:
    if not frames:
        return {
            "capture_start": "",
            "capture_end": "",
            "capture_duration_ms": 0,
            "heartbeat_count": 0,
            "heartbeat_gap_count": 0,
            "heartbeat_coverage_ms": 0,
            "heartbeat_coverage_pct": 0.0,
            "heartbeat_max_gap_ms": 0,
            "heartbeat_avg_gap_ms": 0.0,
        }

    capture_start = frames[0].timestamp
    capture_end = frames[-1].timestamp
    capture_duration_ms = max(0, frames[-1].ts_ms - frames[0].ts_ms)
    heartbeat_times = [frame.ts_ms for frame in frames if frame.heartbeat_candidate]
    heartbeat_gaps = [
        heartbeat_times[idx] - heartbeat_times[idx - 1]
        for idx in range(1, len(heartbeat_times))
        if heartbeat_times[idx] >= heartbeat_times[idx - 1]
    ]
    problematic_gaps = [gap for gap in heartbeat_gaps if gap > HEARTBEAT_GAP_THRESHOLD_MS]
    coverage_ms = 0
    if heartbeat_times:
        coverage_ms += HEARTBEAT_EXPECTED_MS
        for gap in heartbeat_gaps:
            coverage_ms += min(gap, HEARTBEAT_EXPECTED_MS) if gap <= HEARTBEAT_GAP_THRESHOLD_MS else 0
        if capture_duration_ms:
            coverage_ms = min(coverage_ms, capture_duration_ms)

    coverage_pct = 100.0 if capture_duration_ms == 0 and heartbeat_times else 0.0
    if capture_duration_ms > 0:
        coverage_pct = round((coverage_ms / capture_duration_ms) * 100.0, 2)

    return {
        "capture_start": capture_start,
        "capture_end": capture_end,
        "capture_duration_ms": capture_duration_ms,
        "heartbeat_count": len(heartbeat_times),
        "heartbeat_gap_count": len(problematic_gaps),
        "heartbeat_coverage_ms": coverage_ms,
        "heartbeat_coverage_pct": coverage_pct,
        "heartbeat_max_gap_ms": max(heartbeat_gaps) if heartbeat_gaps else 0,
        "heartbeat_avg_gap_ms": round(sum(heartbeat_gaps) / len(heartbeat_gaps), 3) if heartbeat_gaps else 0.0,
    }


def parse_serial_text(text: str) -> dict:
    raw_rows, total_lines, malformed_lines, unparsed_rows = _parse_raw_rows(text)
    frames = _reconstruct_frames(raw_rows)
    marker_rows = _build_marker_rows(frames)
    flow_samples = _build_flow_samples(frames)
    cow_events, cow_batches, orphan_counts = _reconstruct_cow_events(marker_rows, flow_samples)
    operational_groups = _build_operational_groups(cow_batches, cow_events)
    coverage = _build_coverage_summary(frames)

    sorted_frames = sorted(frames, key=lambda frame: frame.ts_ms)
    inter_frame_gaps = [
        sorted_frames[idx].ts_ms - sorted_frames[idx - 1].ts_ms
        for idx in range(1, len(sorted_frames))
        if sorted_frames[idx].ts_ms >= sorted_frames[idx - 1].ts_ms
    ]

    payload_counts = Counter(frame.payload_hex for frame in frames)
    channel_counts = Counter(frame.channel for frame in frames)
    marker_counts = Counter(marker["marker"] for marker in marker_rows)
    status_counts = Counter(event.status for event in cow_events)
    identity_counts = Counter(event.identity_status for event in cow_events)
    confidence_counts = Counter(event.parser_confidence_label for event in cow_events)
    confidence_values = [event.parser_confidence_score for event in cow_events]
    ambiguous_flow_sample_count = sum(event.ambiguous_flow_sample_count for event in cow_events)
    events_with_ambiguous_flow = sum(1 for event in cow_events if event.ambiguous_flow_sample_count > 0)
    prep_phase_event_count = sum(
        1 for event in cow_events if event.notes and "ventana_temporal_preparacion" in event.notes
    )
    cadence_aligned_count = sum(1 for event in cow_events if event.cadence_aligned)
    cadence_steps = Counter(event.cadence_step_index for event in cow_events if event.cadence_aligned and event.cadence_step_index > 0)
    retained_state_suspected_count = sum(1 for event in cow_events if event.retained_state_suspected)

    return {
        "total_events": len(frames),
        "total_lines": total_lines,
        "malformed_lines": malformed_lines,
        "total_frames": len(frames),
        "raw_rows_count": len(raw_rows),
        "fragmented_frame_count": sum(1 for frame in frames if frame.line_count > 1),
        "unique_patterns_count": len(payload_counts),
        "heartbeat_count": coverage["heartbeat_count"],
        "heartbeat_gap_count": coverage["heartbeat_gap_count"],
        "heartbeat_ratio_pct": round((coverage["heartbeat_count"] / len(frames)) * 100.0, 2) if frames else 0.0,
        "heartbeat_coverage_pct": coverage["heartbeat_coverage_pct"],
        "temp_prep_window_ms": TEMP_PREP_WINDOW_MS,
        "cadence_step_ms": CADENCE_STEP_MS,
        "cadence_tolerance_ms": CADENCE_TOLERANCE_MS,
        "capture_duration_ms": coverage["capture_duration_ms"],
        "max_gap_ms": max(inter_frame_gaps) if inter_frame_gaps else 0,
        "avg_gap_ms": round(sum(inter_frame_gaps) / len(inter_frame_gaps), 3) if inter_frame_gaps else 0.0,
        "channel_counts": dict(sorted(channel_counts.items(), key=lambda item: item[0])),
        "marker_counts": dict(sorted(marker_counts.items(), key=lambda item: item[0])),
        "control_frame_count": channel_counts.get("control_plc", 0),
        "flow_frame_count": channel_counts.get("sensor_flujo", 0),
        "cow_marker_frame_count": channel_counts.get("evento_vaca", 0),
        "mixed_frame_count": channel_counts.get("mixed", 0),
        "unknown_frame_count": channel_counts.get("desconocido", 0),
        "total_flow_samples": len(flow_samples),
        "cow_batch_count": len(cow_batches),
        "operational_batch_count": len(operational_groups),
        "cow_event_count": len(cow_events),
        "cow_success_count": status_counts.get("success", 0),
        "cow_partial_count": status_counts.get("partial", 0),
        "cow_missing_rfid_count": status_counts.get("missing_rfid", 0),
        "cow_missing_flow_count": status_counts.get("missing_flow", 0),
        "identity_confirmed_count": identity_counts.get("confirmed", 0),
        "identity_probable_count": identity_counts.get("probable", 0),
        "identity_unconfirmed_count": identity_counts.get("unconfirmed", 0),
        "parser_confidence_average": round(sum(confidence_values) / len(confidence_values), 3) if confidence_values else 0.0,
        "parser_confidence_high_count": confidence_counts.get("high", 0),
        "parser_confidence_medium_count": confidence_counts.get("medium", 0),
        "parser_confidence_low_count": confidence_counts.get("low", 0),
        "cow_ambiguous_flow_sample_count": ambiguous_flow_sample_count,
        "cow_events_with_ambiguous_flow_count": events_with_ambiguous_flow,
        "cow_prep_phase_count": prep_phase_event_count,
        "cow_cadence_aligned_count": cadence_aligned_count,
        "cow_cadence_dominant_step": cadence_steps.most_common(1)[0][0] if cadence_steps else 0,
        "merged_c2_count": sum(max(0, event.c2_count - 1) for event in cow_events),
        "multi_c2_event_count": sum(1 for event in cow_events if event.c2_count > 1),
        "suppressed_noise_event_count": orphan_counts.get("suppressed_noise", 0),
        "suppressed_retained_state_event_count": orphan_counts.get("suppressed_retained_state", 0),
        "retained_state_suspected_count": retained_state_suspected_count,
        "orphans": orphan_counts,
        "coverage": coverage,
        "events": [frame.to_dict() for frame in frames],
        "frames": [frame.to_dict() for frame in frames],
        "marker_events": marker_rows,
        "flow_samples": [sample.to_dict() for sample in flow_samples],
        "cow_batches": [batch.to_dict() for batch in cow_batches],
        "operational_groups": operational_groups,
        "cow_events": [event.to_dict() for event in cow_events],
        "unknown_frames": [frame.to_dict() for frame in frames if frame.channel == "desconocido"],
        "unparsed_lines": unparsed_rows,
        "top_patterns": [
            {"payload_hex": payload, "count": count}
            for payload, count in payload_counts.most_common(20)
        ],
        "legacy_fc_count": sum(1 for marker in marker_rows if marker["marker"] == "E0"),
        "legacy_fe_count": sum(1 for marker in marker_rows if marker["marker"] == "E2"),
    }


def parse_serial_file(path: Path) -> dict:
    return parse_serial_text(read_text(path))
