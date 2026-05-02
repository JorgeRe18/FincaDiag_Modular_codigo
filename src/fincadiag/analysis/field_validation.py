import csv
import json
from collections import Counter
import re
import zipfile
from datetime import date, datetime, time, timedelta
from html import unescape
from pathlib import Path
import unicodedata

from fincadiag.config import DATA_FIELD_VALIDATION_DIR, PROJECT_ROOT


VALIDATION_PM_PATH = DATA_FIELD_VALIDATION_DIR / "pm_validations_2026_04_06_2026_04_09.csv"
ALLFLEX_REGISTRY_PATH = DATA_FIELD_VALIDATION_DIR / "allflex_tag_registry.csv"
VALIDATION_DOCX_DIR = PROJECT_ROOT / "vali_presencial"
VISIT_NAME_RE = re.compile(r"Visita_(\d{2})_(\d{2})_(\d{4})")
CAPTURE_NAME_RE = re.compile(r"Captura_(\d{8})_(\d{6})")
DOCX_VISIT_NAME_RE = re.compile(r"validacion_visita_(\d{1,2})_(\d{1,2})_(\d{4})\.docx$", re.IGNORECASE)
QUICK_ID_THRESHOLD_SECONDS = 3.0
SEMANTIC_CONFIDENCE_HIGH_THRESHOLD = 0.75
SEMANTIC_CONFIDENCE_MEDIUM_THRESHOLD = 0.45
_VALIDATION_ROWS_CACHE = None
_ALLFLEX_REGISTRY_CACHE = None


def empty_field_validation_summary() -> dict:
    return {
        "available": False,
        "source_path": str(VALIDATION_PM_PATH),
        "reason": "",
        "visit_date": "",
        "block": "",
        "identity_basis": "tag_allflex",
        "capture_started_at": "",
        "capture_ended_at": "",
        "milking_started_at": "",
        "milking_ended_at": "",
        "capture_overlap_seconds": 0.0,
        "records_total": 0,
        "records_in_capture_window": 0,
        "observed_cows_count": 0,
        "known_tag_count": 0,
        "missing_tag_count": 0,
        "id_success_count": 0,
        "id_doubtful_count": 0,
        "flow_visible_count": 0,
        "flow_doubtful_count": 0,
        "quick_id_count": 0,
        "delayed_id_count": 0,
        "missing_id_latency_count": 0,
        "photocell_issue_count": 0,
        "controller_intervention_count": 0,
        "controller_stale_read_count": 0,
        "mastitis_count": 0,
        "controller_celo_count": 0,
        "controller_e56_count": 0,
        "controller_e59_count": 0,
        "controller_error_count": 0,
        "controller_error_codes_present": [],
        "stale_milk_measurement_count": 0,
        "low_production_suspected_count": 0,
        "semantic_identity_confirmed_count": 0,
        "semantic_identity_uncertain_count": 0,
        "semantic_identity_stale_count": 0,
        "semantic_flow_confirmed_count": 0,
        "semantic_flow_uncertain_count": 0,
        "semantic_flow_stale_count": 0,
        "semantic_manual_override_suspected_count": 0,
        "semantic_photocell_failure_suspected_count": 0,
        "semantic_controller_alarm_count": 0,
        "semantic_normal_milking_flow_count": 0,
        "semantic_case_counts": {},
        "semantic_primary_case": "",
        "semantic_reconstruction_ready": False,
        "semantic_confidence_average": 0.0,
        "semantic_confidence_high_count": 0,
        "semantic_confidence_medium_count": 0,
        "semantic_confidence_low_count": 0,
        "field_id_success_rate": 0.0,
        "field_flow_visible_rate": 0.0,
        "parser_coverage_rate_vs_field": 0.0,
        "parser_missing_count_vs_field": 0,
        "parser_excess_count_vs_field": 0,
        "parser_event_count": 0,
        "parser_batch_count": 0,
        "parser_operational_batch_count": 0,
        "parser_success_count": 0,
        "parser_missing_tag_count": 0,
        "parser_missing_flow_count": 0,
        "parser_event_delta_vs_field": 0,
        "parser_event_ratio_vs_field": 0.0,
        "records": [],
    }


def _parse_visit_date(visit_name: str) -> date | None:
    match = VISIT_NAME_RE.search(str(visit_name or ""))
    if not match:
        return None
    day, month, year = match.groups()
    return date(int(year), int(month), int(day))


def _parse_time_flexible(value: str) -> time | None:
    text = str(value or "").strip()
    if not text:
        return None
    for pattern in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(text, pattern).time()
        except ValueError:
            continue
    return None


def _parse_capture_manifest_window(capture_dir: Path) -> tuple[datetime | None, datetime | None]:
    manifest_path = capture_dir / "capture_manifest.json"
    if not manifest_path.exists():
        return None, None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return None, None

    start_text = str(payload.get("started_at", "")).strip()
    end_text = str(payload.get("ended_at", "")).strip()
    try:
        start_dt = datetime.fromisoformat(start_text) if start_text else None
    except ValueError:
        start_dt = None
    try:
        end_dt = datetime.fromisoformat(end_text) if end_text else None
    except ValueError:
        end_dt = None
    return start_dt, end_dt


def _parse_capture_name_window(capture_dir: Path, serial: dict) -> tuple[datetime | None, datetime | None]:
    match = CAPTURE_NAME_RE.search(capture_dir.name)
    if not match:
        return None, None
    start_dt = datetime.strptime("".join(match.groups()), "%Y%m%d%H%M%S")
    duration_ms = int(serial.get("capture_duration_ms", 0) or 0)
    if duration_ms > 0:
        end_dt = start_dt + timedelta(milliseconds=duration_ms)
    else:
        end_dt = start_dt + timedelta(hours=2)
    return start_dt, end_dt


def _load_capture_window(capture_dir: Path, serial: dict) -> tuple[datetime | None, datetime | None]:
    start_dt, end_dt = _parse_capture_manifest_window(capture_dir)
    if start_dt and end_dt:
        return start_dt, end_dt
    return _parse_capture_name_window(capture_dir, serial)


def _get_block_period(block_label: str) -> str:
    text = str(block_label or "").upper()
    if text.endswith("AM"):
        return "AM"
    if text.endswith("PM"):
        return "PM"
    return ""


def _strip_accents(value: str) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _normalize_text_for_matching(value: str) -> str:
    text = _strip_accents(value).lower()
    text = text.replace("\u00a0", " ")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_docx_text(value: str) -> str:
    text = unescape(str(value or ""))
    text = text.replace("\u00a0", " ")
    text = text.replace("–", "-").replace("—", "-")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = re.sub(r"\bVac\s+a\b", "Vaca", text, flags=re.IGNORECASE)
    text = re.sub(r"\bS\s+i\b", "Si", text, flags=re.IGNORECASE)
    text = re.sub(r"\bD\s+udoso\b", "Dudoso", text, flags=re.IGNORECASE)
    text = re.sub(r"\bP\s+M\b", "PM", text, flags=re.IGNORECASE)
    text = re.sub(r"\bA\s+M\b", "AM", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*:\s*", ":", text)
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _normalize_status(value: str) -> str:
    token = _normalize_text_for_matching(value).replace(" ", "")
    if token.startswith("si"):
        return "si"
    if token.startswith("no"):
        return "no"
    if "dudoso" in token:
        return "dudoso"
    return str(value or "").strip().lower()


def _normalize_time_value(value: str, default_period: str = "") -> str:
    text = _normalize_docx_text(value)
    if not text:
        return ""
    marker_match = re.search(r"\b(am|pm)\b", text, flags=re.IGNORECASE)
    marker = marker_match.group(1).upper() if marker_match else str(default_period or "").upper()
    match = re.search(r"(\d{1,2}:\d{1,2}(?::\d{1,2})?)", text)
    if not match:
        return ""
    parts = [int(part) for part in match.group(1).split(":")]
    if len(parts) == 2:
        hour, minute = parts
        second = None
    else:
        hour, minute, second = parts
    if marker == "PM" and hour < 12:
        hour += 12
    elif marker == "AM" and hour == 12:
        hour = 0
    if second is None:
        return f"{hour:02d}:{minute:02d}"
    return f"{hour:02d}:{minute:02d}:{second:02d}"


def _normalize_decimal(value: str) -> float | None:
    text = _normalize_docx_text(value).replace(",", ".")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _load_allflex_registry() -> dict[str, str]:
    global _ALLFLEX_REGISTRY_CACHE
    if _ALLFLEX_REGISTRY_CACHE is not None:
        return _ALLFLEX_REGISTRY_CACHE
    registry = {}
    if ALLFLEX_REGISTRY_PATH.exists():
        with ALLFLEX_REGISTRY_PATH.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                animal_number = str(row.get("animal_number", "") or "").strip()
                tag_allflex = str(row.get("tag_allflex", "") or "").strip()
                if animal_number:
                    registry[animal_number] = tag_allflex
    _ALLFLEX_REGISTRY_CACHE = registry
    return registry


def _read_docx_text(path: Path) -> str:
    try:
        with zipfile.ZipFile(path) as archive:
            xml_text = archive.read("word/document.xml").decode("utf-8", errors="ignore")
    except Exception:
        return ""
    pieces = re.findall(r"<w:t[^>]*>(.*?)</w:t>", xml_text, flags=re.DOTALL)
    return _normalize_docx_text(" ".join(pieces))


def _parse_docx_visit_date(path: Path, text: str) -> str:
    match = re.search(r"Fecha:\s*(\d{1,2})/(\d{1,2})/(\d{4})", text, flags=re.IGNORECASE)
    if not match:
        match = DOCX_VISIT_NAME_RE.search(path.name)
    if not match:
        return ""
    day, month, year = match.groups()
    return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"


def _parse_docx_milking_window(text: str, block: str) -> tuple[str, str]:
    match = re.search(
        r"Tiempo total de orde[ñn]o\s*:\s*(.*?)\s*-\s*(.*?)\s*(?:Observador:|Instrucciones breves|Vaca\s+\d+)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return "", ""
    milking_start = _normalize_time_value(match.group(1), block)
    milking_end = _normalize_time_value(match.group(2), block)
    return milking_start, milking_end


def _parse_docx_rows(path: Path, known_tags: dict[str, str]) -> list[dict]:
    text = _read_docx_text(path)
    if not text:
        return []
    visit_date = _parse_docx_visit_date(path, text)
    block_match = re.search(r"Bloque:\s*(AM|PM)", text, flags=re.IGNORECASE)
    block = block_match.group(1).upper() if block_match else ""
    milking_start, milking_end = _parse_docx_milking_window(text, block)
    if not visit_date or not block:
        return []

    rows = []
    pattern = re.compile(
        r"Vaca\s+(?P<cow_number>\d+)\s*-+\s*hora_entrada:\s*(?P<entry_time>.*?)\s*hora_rfid:\s*(?P<id_time>.*?)\s*hora_salida:\s*(?P<exit_time>.*?)\s*rfid_leido:\s*(?P<id_read_status>.*?)\s*flujo_visible:\s*(?P<flow_visible_status>.*?)\s*observacion:\s*(?P<observation>.*?)(?=\s*Vaca\s+\d+\s*-+\s*hora_entrada:|$)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(text):
        cow_number = str(match.group("cow_number") or "").strip()
        tag_allflex = known_tags.get(cow_number, "")
        rows.append(
            {
                "visit_date": visit_date,
                "block": block,
                "milking_start": milking_start,
                "milking_end": milking_end,
                "cow_number": cow_number,
                "tag_allflex": tag_allflex,
                "tag_lookup_status": "matched" if tag_allflex else "not_found",
                "entry_time": _normalize_time_value(match.group("entry_time"), block),
                "id_time": _normalize_time_value(match.group("id_time"), block),
                "exit_time": _normalize_time_value(match.group("exit_time"), block),
                "id_read_status": _normalize_status(match.group("id_read_status")),
                "flow_visible_status": _normalize_status(match.group("flow_visible_status")),
                "observation": str(match.group("observation") or "").strip(),
                "source_doc": path.name,
            }
        )
    return rows


def _dedupe_validation_rows(rows: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for row in rows:
        key = (
            str(row.get("visit_date", "") or "").strip(),
            str(row.get("block", "") or "").strip().upper(),
            str(row.get("cow_number", "") or "").strip(),
            str(row.get("entry_time", "") or "").strip(),
            str(row.get("id_time", "") or "").strip(),
            str(row.get("exit_time", "") or "").strip(),
            str(row.get("source_doc", "") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def _load_validation_rows() -> list[dict]:
    global _VALIDATION_ROWS_CACHE
    if _VALIDATION_ROWS_CACHE is not None:
        return _VALIDATION_ROWS_CACHE

    rows = []
    if VALIDATION_PM_PATH.exists():
        with VALIDATION_PM_PATH.open("r", encoding="utf-8", newline="") as handle:
            for raw_row in csv.DictReader(handle):
                row = dict(raw_row)
                extras = [item for item in (row.pop(None, []) or []) if str(item).strip()]
                observation = str(row.get("observation", "") or "").strip()
                source_doc = str(row.get("source_doc", "") or "").strip()

                recovered_doc = ""
                recovered_observation_parts = []

                if source_doc and not source_doc.lower().endswith((".docx", ".txt", ".md", ".pdf")):
                    recovered_observation_parts.append(source_doc)
                    source_doc = ""

                for extra in extras:
                    cleaned = str(extra).strip()
                    if not cleaned:
                        continue
                    if cleaned.lower().endswith((".docx", ".txt", ".md", ".pdf")):
                        recovered_doc = cleaned
                    else:
                        recovered_observation_parts.append(cleaned)

                if recovered_observation_parts:
                    joined = ", ".join(recovered_observation_parts)
                    observation = f"{observation}, {joined}".strip(", ") if observation else joined

                if recovered_doc:
                    source_doc = recovered_doc

                row["observation"] = observation
                row["source_doc"] = source_doc
                rows.append(row)

    known_tags = _load_allflex_registry()
    existing_docs = {str(row.get("source_doc", "") or "").strip().lower() for row in rows}
    if VALIDATION_DOCX_DIR.exists():
        for docx_path in sorted(VALIDATION_DOCX_DIR.glob("validacion_visita_*.docx")):
            if docx_path.name.lower() in existing_docs:
                continue
            rows.extend(_parse_docx_rows(docx_path, known_tags))

    _VALIDATION_ROWS_CACHE = _dedupe_validation_rows(rows)
    return _VALIDATION_ROWS_CACHE


def _to_datetime(visit_date: date, value: str) -> datetime | None:
    parsed_time = _parse_time_flexible(value)
    if parsed_time is None:
        return None
    return datetime.combine(visit_date, parsed_time)


def _seconds_between(start_dt: datetime | None, end_dt: datetime | None) -> float | None:
    if start_dt is None or end_dt is None:
        return None
    return round((end_dt - start_dt).total_seconds(), 3)


def _record_overlaps_capture(record: dict, capture_start_dt: datetime, capture_end_dt: datetime) -> bool:
    candidate_times = [
        record.get("entry_dt"),
        record.get("id_dt"),
        record.get("exit_dt"),
    ]
    for candidate in candidate_times:
        if candidate is None:
            continue
        if capture_start_dt <= candidate <= capture_end_dt:
            return True

    start_dt = record.get("entry_dt") or record.get("id_dt")
    end_dt = record.get("exit_dt") or record.get("id_dt") or start_dt
    if start_dt is None or end_dt is None:
        return False
    return start_dt <= capture_end_dt and end_dt >= capture_start_dt


def _build_enriched_records(rows: list[dict], visit_date: date, capture_start_dt: datetime, capture_end_dt: datetime) -> list[dict]:
    enriched = []
    for row in rows:
        entry_dt = _to_datetime(visit_date, row.get("entry_time", ""))
        id_dt = _to_datetime(visit_date, row.get("id_time", ""))
        exit_dt = _to_datetime(visit_date, row.get("exit_time", ""))
        observation = str(row.get("observation", "") or "")
        observation_normalized = _normalize_text_for_matching(observation)
        entry_to_id_seconds = _seconds_between(entry_dt, id_dt)
        entry_to_exit_seconds = _seconds_between(entry_dt, exit_dt)
        milk_liters_observed = _normalize_decimal(observation)
        controller_error_codes = sorted(
            {
                f"E{match}"
                for match in re.findall(r"\be\s*(\d{2})\b", observation_normalized, flags=re.IGNORECASE)
            }
        )
        enriched_row = dict(row)
        enriched_row["entry_dt"] = entry_dt
        enriched_row["id_dt"] = id_dt
        enriched_row["exit_dt"] = exit_dt
        enriched_row["entry_to_id_seconds"] = entry_to_id_seconds
        enriched_row["entry_to_exit_seconds"] = entry_to_exit_seconds
        enriched_row["milk_liters_observed"] = milk_liters_observed
        enriched_row["controller_error_codes"] = controller_error_codes
        enriched_row["overlaps_capture_window"] = _record_overlaps_capture(
            {
                "entry_dt": entry_dt,
                "id_dt": id_dt,
                "exit_dt": exit_dt,
            },
            capture_start_dt,
            capture_end_dt,
        )
        enriched_row["photocell_issue"] = "fotocelda" in observation_normalized
        enriched_row["controller_intervention"] = (
            "presionar el boton" in observation_normalized
            or "presiono el boton" in observation_normalized
            or "controller" in observation_normalized
        )
        enriched_row["controller_stale_read"] = (
            "seguia manteniendo la lectura" in observation_normalized
            or "mantuvo la lectura de la vaca" in observation_normalized
            or "mantuvo el dato de la vaca" in observation_normalized
            or "no sostiene el numero de la vaca" in observation_normalized
        )
        enriched_row["stale_milk_measurement"] = (
            "mantuvo la cantidad de leche" in observation_normalized
            or "no mantuvo la cantidad de leche" in observation_normalized
            or "no mantuvo la cantidad del ordeno" in observation_normalized
            or "cantidad de leche generada" in observation_normalized
            or "registra el flujo de la leche ordenada" in observation_normalized
        )
        enriched_row["low_production_suspected"] = "baja produccion" in observation_normalized
        enriched_row["mastitis_flag"] = "mastitis" in observation_normalized
        enriched_row["controller_celo_flag"] = "celo" in observation_normalized
        enriched_row["controller_e56_flag"] = "E56" in controller_error_codes
        enriched_row["controller_e59_flag"] = "E59" in controller_error_codes
        enriched.append(enriched_row)
    return enriched


def _semantic_confidence_label(value: float) -> str:
    if value >= SEMANTIC_CONFIDENCE_HIGH_THRESHOLD:
        return "high"
    if value >= SEMANTIC_CONFIDENCE_MEDIUM_THRESHOLD:
        return "medium"
    return "low"


def _infer_semantic_record(row: dict) -> dict:
    id_status = str(row.get("id_read_status", "") or "").lower()
    flow_status = str(row.get("flow_visible_status", "") or "").lower()
    controller_error_codes = [str(code).strip() for code in row.get("controller_error_codes", []) if str(code).strip()]

    if row.get("controller_stale_read"):
        identity_state = "identity_stale_suspected"
    elif id_status == "si":
        identity_state = "rfid_confirmed"
    elif id_status == "dudoso":
        identity_state = "rfid_uncertain"
    else:
        identity_state = "identity_missing"

    if row.get("stale_milk_measurement"):
        flow_state = "milk_state_stale_suspected"
    elif flow_status == "si":
        flow_state = "flow_confirmed"
    elif flow_status == "dudoso":
        flow_state = "flow_uncertain"
    else:
        flow_state = "flow_missing"

    if row.get("controller_stale_read") and row.get("stale_milk_measurement"):
        semantic_case_type = "controller_state_stale"
    elif row.get("controller_stale_read"):
        semantic_case_type = "identity_stale"
    elif row.get("stale_milk_measurement"):
        semantic_case_type = "milk_state_stale"
    elif row.get("photocell_issue") and row.get("controller_intervention"):
        semantic_case_type = "photocell_manual_override"
    elif row.get("photocell_issue"):
        semantic_case_type = "photocell_issue"
    elif row.get("controller_intervention"):
        semantic_case_type = "manual_intervention"
    elif id_status == "dudoso" and flow_status == "dudoso":
        semantic_case_type = "identity_and_flow_uncertain"
    elif id_status == "dudoso":
        semantic_case_type = "identity_uncertain"
    elif flow_status == "dudoso":
        semantic_case_type = "flow_uncertain"
    elif row.get("low_production_suspected"):
        semantic_case_type = "low_production_suspected"
    elif row.get("mastitis_flag"):
        semantic_case_type = "mastitis_observed"
    elif row.get("controller_celo_flag"):
        semantic_case_type = "celo_observed"
    elif id_status == "si" and flow_status == "si":
        semantic_case_type = "normal_milking_flow"
    else:
        semantic_case_type = "review_required"

    inferred_state_sequence = []
    if row.get("entry_dt") is not None or row.get("id_dt") is not None or row.get("exit_dt") is not None:
        inferred_state_sequence.append("animal_present")
    if identity_state == "rfid_confirmed":
        inferred_state_sequence.append("identity_assigned")
    elif identity_state == "rfid_uncertain":
        inferred_state_sequence.append("identity_uncertain")
    elif identity_state == "identity_stale_suspected":
        inferred_state_sequence.append("identity_stale")
    if flow_state == "flow_confirmed":
        inferred_state_sequence.append("flow_started")
        inferred_state_sequence.append("flow_stable")
    elif flow_state == "flow_uncertain":
        inferred_state_sequence.append("flow_uncertain")
    elif flow_state == "milk_state_stale_suspected":
        inferred_state_sequence.append("flow_stale")
    if row.get("photocell_issue"):
        inferred_state_sequence.append("photocell_failure_suspected")
    if row.get("controller_intervention"):
        inferred_state_sequence.append("manual_override_suspected")
    if controller_error_codes:
        inferred_state_sequence.append("controller_alarm_present")
    if row.get("low_production_suspected"):
        inferred_state_sequence.append("low_production_suspected")
    if row.get("mastitis_flag"):
        inferred_state_sequence.append("mastitis_observed")
    if row.get("controller_celo_flag"):
        inferred_state_sequence.append("celo_observed")
    if row.get("exit_dt") is not None:
        inferred_state_sequence.append("animal_exited")

    confidence = 0.35
    if id_status == "si":
        confidence += 0.25
    elif id_status == "dudoso":
        confidence -= 0.1
    if flow_status == "si":
        confidence += 0.25
    elif flow_status == "dudoso":
        confidence -= 0.1
    if row.get("entry_dt") is not None and row.get("exit_dt") is not None:
        confidence += 0.1
    if row.get("entry_to_id_seconds") is not None and row.get("entry_to_id_seconds") <= QUICK_ID_THRESHOLD_SECONDS:
        confidence += 0.05
    if row.get("controller_stale_read"):
        confidence -= 0.2
    if row.get("stale_milk_measurement"):
        confidence -= 0.2
    if row.get("photocell_issue"):
        confidence -= 0.05
    if row.get("controller_intervention"):
        confidence -= 0.05
    if controller_error_codes:
        confidence -= min(0.15, 0.05 * len(controller_error_codes))
    confidence = max(0.0, min(1.0, round(confidence, 3)))

    return {
        "identity_state": identity_state,
        "flow_state": flow_state,
        "semantic_case_type": semantic_case_type,
        "inferred_state_sequence": inferred_state_sequence,
        "semantic_confidence": confidence,
        "semantic_confidence_label": _semantic_confidence_label(confidence),
        "manual_override_suspected": row.get("controller_intervention", False),
        "photocell_failure_suspected": row.get("photocell_issue", False),
        "controller_alarm_present": bool(controller_error_codes),
    }


def _summarize_semantic_records(records: list[dict]) -> dict:
    case_counter = Counter(str(row.get("semantic_case_type", "") or "") for row in records if str(row.get("semantic_case_type", "") or ""))
    confidence_counter = Counter(str(row.get("semantic_confidence_label", "") or "") for row in records if str(row.get("semantic_confidence_label", "") or ""))
    confidence_values = [float(row.get("semantic_confidence", 0.0) or 0.0) for row in records]
    return {
        "semantic_identity_confirmed_count": sum(1 for row in records if row.get("identity_state") == "rfid_confirmed"),
        "semantic_identity_uncertain_count": sum(1 for row in records if row.get("identity_state") == "rfid_uncertain"),
        "semantic_identity_stale_count": sum(1 for row in records if row.get("identity_state") == "identity_stale_suspected"),
        "semantic_flow_confirmed_count": sum(1 for row in records if row.get("flow_state") == "flow_confirmed"),
        "semantic_flow_uncertain_count": sum(1 for row in records if row.get("flow_state") == "flow_uncertain"),
        "semantic_flow_stale_count": sum(1 for row in records if row.get("flow_state") == "milk_state_stale_suspected"),
        "semantic_manual_override_suspected_count": sum(1 for row in records if row.get("manual_override_suspected")),
        "semantic_photocell_failure_suspected_count": sum(1 for row in records if row.get("photocell_failure_suspected")),
        "semantic_controller_alarm_count": sum(1 for row in records if row.get("controller_alarm_present")),
        "semantic_normal_milking_flow_count": sum(1 for row in records if row.get("semantic_case_type") == "normal_milking_flow"),
        "semantic_case_counts": dict(sorted(case_counter.items())),
        "semantic_primary_case": case_counter.most_common(1)[0][0] if case_counter else "",
        "semantic_reconstruction_ready": bool(records) and sum(1 for row in records if row.get("identity_state") != "identity_missing") >= max(1, len(records) // 2),
        "semantic_confidence_average": round(sum(confidence_values) / len(confidence_values), 3) if confidence_values else 0.0,
        "semantic_confidence_high_count": confidence_counter.get("high", 0),
        "semantic_confidence_medium_count": confidence_counter.get("medium", 0),
        "semantic_confidence_low_count": confidence_counter.get("low", 0),
    }


def build_field_validation_summary(session: dict, capture_dir: Path, serial: dict) -> dict:
    summary = empty_field_validation_summary()

    if session.get("operation_mode") != "ordeno_completo":
        summary["reason"] = "modo_operativo_sin_validacion_de_ordeno"
        return summary

    visit_date = _parse_visit_date(session.get("visit_name", ""))
    block_period = _get_block_period(session.get("block_label", ""))
    if visit_date is None or not block_period:
        summary["reason"] = "visita_o_bloque_no_parseable"
        return summary

    capture_start_dt, capture_end_dt = _load_capture_window(capture_dir, serial)
    if capture_start_dt is None or capture_end_dt is None:
        summary["reason"] = "sin_ventana_temporal_de_captura"
        return summary

    rows = _load_validation_rows()
    candidate_rows = [
        row
        for row in rows
        if row.get("visit_date") == visit_date.isoformat() and str(row.get("block", "")).upper() == block_period
    ]
    if not candidate_rows:
        summary["reason"] = "sin_validacion_de_campo_para_la_sesion"
        summary["visit_date"] = visit_date.isoformat()
        summary["block"] = block_period
        summary["capture_started_at"] = capture_start_dt.isoformat(timespec="seconds")
        summary["capture_ended_at"] = capture_end_dt.isoformat(timespec="seconds")
        return summary

    milking_start_dt = _to_datetime(visit_date, candidate_rows[0].get("milking_start", ""))
    milking_end_dt = _to_datetime(visit_date, candidate_rows[0].get("milking_end", ""))
    if milking_start_dt is None or milking_end_dt is None:
        summary["reason"] = "sin_ventana_temporal_de_ordeno"
        return summary

    overlap_start = max(capture_start_dt, milking_start_dt)
    overlap_end = min(capture_end_dt, milking_end_dt)
    overlap_seconds = max(0.0, round((overlap_end - overlap_start).total_seconds(), 3))
    if overlap_seconds <= 0:
        summary["reason"] = "sin_solapamiento_con_ventana_de_ordeno"
        summary["visit_date"] = visit_date.isoformat()
        summary["block"] = block_period
        summary["capture_started_at"] = capture_start_dt.isoformat(timespec="seconds")
        summary["capture_ended_at"] = capture_end_dt.isoformat(timespec="seconds")
        summary["milking_started_at"] = milking_start_dt.isoformat(timespec="seconds")
        summary["milking_ended_at"] = milking_end_dt.isoformat(timespec="seconds")
        return summary

    enriched_records = _build_enriched_records(candidate_rows, visit_date, capture_start_dt, capture_end_dt)
    records_in_window = [row for row in enriched_records if row["overlaps_capture_window"]]
    semantic_records = []
    for row in records_in_window:
        semantic_row = dict(row)
        semantic_row.update(_infer_semantic_record(row))
        semantic_records.append(semantic_row)
    semantic_summary = _summarize_semantic_records(semantic_records)

    def format_record(row: dict) -> dict:
        return {
            "visit_date": row.get("visit_date", ""),
            "block": row.get("block", ""),
            "cow_number": row.get("cow_number", ""),
            "tag_allflex": row.get("tag_allflex", ""),
            "tag_lookup_status": row.get("tag_lookup_status", ""),
            "entry_time": row.get("entry_time", ""),
            "id_time": row.get("id_time", ""),
            "exit_time": row.get("exit_time", ""),
            "entry_to_id_seconds": row.get("entry_to_id_seconds", ""),
            "entry_to_exit_seconds": row.get("entry_to_exit_seconds", ""),
            "id_read_status": row.get("id_read_status", ""),
            "flow_visible_status": row.get("flow_visible_status", ""),
            "overlaps_capture_window": row.get("overlaps_capture_window", False),
            "photocell_issue": row.get("photocell_issue", False),
            "controller_intervention": row.get("controller_intervention", False),
            "controller_stale_read": row.get("controller_stale_read", False),
            "stale_milk_measurement": row.get("stale_milk_measurement", False),
            "low_production_suspected": row.get("low_production_suspected", False),
            "mastitis_flag": row.get("mastitis_flag", False),
            "controller_celo_flag": row.get("controller_celo_flag", False),
            "controller_e56_flag": row.get("controller_e56_flag", False),
            "controller_e59_flag": row.get("controller_e59_flag", False),
            "controller_error_codes": row.get("controller_error_codes", []),
            "milk_liters_observed": row.get("milk_liters_observed", ""),
            "identity_state": row.get("identity_state", ""),
            "flow_state": row.get("flow_state", ""),
            "semantic_case_type": row.get("semantic_case_type", ""),
            "inferred_state_sequence": row.get("inferred_state_sequence", []),
            "semantic_confidence": row.get("semantic_confidence", 0.0),
            "semantic_confidence_label": row.get("semantic_confidence_label", ""),
            "manual_override_suspected": row.get("manual_override_suspected", False),
            "photocell_failure_suspected": row.get("photocell_failure_suspected", False),
            "controller_alarm_present": row.get("controller_alarm_present", False),
            "observation": row.get("observation", ""),
            "source_doc": row.get("source_doc", ""),
        }

    quick_id_count = sum(
        1
        for row in records_in_window
        if row.get("entry_to_id_seconds") is not None and row["entry_to_id_seconds"] <= QUICK_ID_THRESHOLD_SECONDS
    )
    delayed_id_count = sum(
        1
        for row in records_in_window
        if row.get("entry_to_id_seconds") is not None and row["entry_to_id_seconds"] > QUICK_ID_THRESHOLD_SECONDS
    )
    missing_id_latency_count = sum(1 for row in records_in_window if row.get("entry_to_id_seconds") is None)

    observed_cows_count = len({str(row.get("cow_number", "")).strip() for row in records_in_window if str(row.get("cow_number", "")).strip()})
    parser_event_count = int(serial.get("cow_event_count", 0) or 0)
    controller_error_codes_present = sorted(
        {
            code
            for row in records_in_window
            for code in row.get("controller_error_codes", [])
            if str(code).strip()
        }
    )
    id_success_count = sum(1 for row in records_in_window if str(row.get("id_read_status", "")).lower() == "si")
    flow_visible_count = sum(1 for row in records_in_window if str(row.get("flow_visible_status", "")).lower() == "si")

    summary.update(
        {
            "available": True,
            "source_path": "; ".join(sorted({str(row.get("source_doc", "")).strip() for row in candidate_rows if str(row.get("source_doc", "")).strip()})) or str(VALIDATION_PM_PATH),
            "visit_date": visit_date.isoformat(),
            "block": block_period,
            "capture_started_at": capture_start_dt.isoformat(timespec="seconds"),
            "capture_ended_at": capture_end_dt.isoformat(timespec="seconds"),
            "milking_started_at": milking_start_dt.isoformat(timespec="seconds"),
            "milking_ended_at": milking_end_dt.isoformat(timespec="seconds"),
            "capture_overlap_seconds": overlap_seconds,
            "records_total": len(enriched_records),
            "records_in_capture_window": len(records_in_window),
            "observed_cows_count": observed_cows_count,
            "known_tag_count": sum(1 for row in records_in_window if str(row.get("tag_lookup_status", "")).lower() == "matched"),
            "missing_tag_count": sum(1 for row in records_in_window if str(row.get("tag_lookup_status", "")).lower() != "matched"),
            "id_success_count": id_success_count,
            "id_doubtful_count": sum(1 for row in records_in_window if str(row.get("id_read_status", "")).lower() == "dudoso"),
            "flow_visible_count": flow_visible_count,
            "flow_doubtful_count": sum(1 for row in records_in_window if str(row.get("flow_visible_status", "")).lower() == "dudoso"),
            "quick_id_count": quick_id_count,
            "delayed_id_count": delayed_id_count,
            "missing_id_latency_count": missing_id_latency_count,
            "photocell_issue_count": sum(1 for row in records_in_window if row.get("photocell_issue")),
            "controller_intervention_count": sum(1 for row in records_in_window if row.get("controller_intervention")),
            "controller_stale_read_count": sum(1 for row in records_in_window if row.get("controller_stale_read")),
            "stale_milk_measurement_count": sum(1 for row in records_in_window if row.get("stale_milk_measurement")),
            "low_production_suspected_count": sum(1 for row in records_in_window if row.get("low_production_suspected")),
            "mastitis_count": sum(1 for row in records_in_window if row.get("mastitis_flag")),
            "controller_celo_count": sum(1 for row in records_in_window if row.get("controller_celo_flag")),
            "controller_e56_count": sum(1 for row in records_in_window if row.get("controller_e56_flag")),
            "controller_e59_count": sum(1 for row in records_in_window if row.get("controller_e59_flag")),
            "controller_error_count": sum(len(row.get("controller_error_codes", [])) for row in records_in_window),
            "controller_error_codes_present": controller_error_codes_present,
            "field_id_success_rate": round(id_success_count / observed_cows_count, 3) if observed_cows_count else 0.0,
            "field_flow_visible_rate": round(flow_visible_count / observed_cows_count, 3) if observed_cows_count else 0.0,
            "parser_coverage_rate_vs_field": round(parser_event_count / observed_cows_count, 3) if observed_cows_count else 0.0,
            "parser_missing_count_vs_field": max(0, observed_cows_count - parser_event_count),
            "parser_excess_count_vs_field": max(0, parser_event_count - observed_cows_count),
            "parser_event_count": parser_event_count,
            "parser_batch_count": int(serial.get("cow_batch_count", 0) or 0),
            "parser_operational_batch_count": int(serial.get("operational_batch_count", 0) or 0),
            "parser_success_count": int(serial.get("cow_success_count", 0) or 0),
            "parser_missing_tag_count": int(serial.get("cow_missing_rfid_count", 0) or 0),
            "parser_missing_flow_count": int(serial.get("cow_missing_flow_count", 0) or 0),
            "parser_event_delta_vs_field": parser_event_count - observed_cows_count,
            "parser_event_ratio_vs_field": round(parser_event_count / observed_cows_count, 3) if observed_cows_count else 0.0,
            "records": [format_record(row) for row in semantic_records],
        }
    )
    summary.update(semantic_summary)
    return summary
