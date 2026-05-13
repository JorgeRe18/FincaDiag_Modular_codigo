import re
from pathlib import Path

from fincadiag.parsers.baseline_parser import has_baseline_files


CAPTURE_PREFIX = "Captura_"
BASELINE_PREFIX = "Baseline_"
TIMESTAMP_RE = re.compile(r"(\d{8}_\d{6})")


def is_capture_dir(path: Path) -> bool:
    return (
        path.is_dir()
        and path.name.startswith(CAPTURE_PREFIX)
    )


def is_baseline_dir(path: Path) -> bool:
    return path.is_dir() and path.name.startswith(BASELINE_PREFIX)


def extract_named_timestamp(path: Path) -> str:
    match = TIMESTAMP_RE.search(path.name)
    return match.group(1) if match else ""


def timestamp_key_from_path(path: Path) -> int | None:
    timestamp_text = extract_named_timestamp(path)
    if not timestamp_text:
        return None
    return int(timestamp_text.replace("_", ""))


def has_capture_payload(path: Path) -> bool:
    serial_exists = (path / "serial_hex.txt").exists()
    antenna_udp_exists = (path / "antena_udp.txt").exists()
    etl_exists = any(path.glob("*.etl"))
    pcap_exists = (path / "captura.pcap").exists() or (path / "captura.pcapng").exists()
    return serial_exists or antenna_udp_exists or etl_exists or pcap_exists


def resolve_pcap_path(capture_dir: Path) -> Path | None:
    for name in ("captura.pcap", "captura.pcapng"):
        candidate = capture_dir / name
        if candidate.exists():
            return candidate
    return None


def resolve_antenna_udp_path(capture_dir: Path) -> Path | None:
    candidate = capture_dir / "antena_udp.txt"
    return candidate if candidate.exists() else None


def resolve_etl_path(capture_dir: Path) -> Path | None:
    etl_files = sorted(capture_dir.glob("*.etl"))
    return etl_files[0] if etl_files else None


def _collect_candidate_baselines(capture_dir: Path, search_root: Path) -> list[tuple[Path, int]]:
    candidates: list[tuple[Path, int]] = []
    current = capture_dir.parent
    depth = 0

    # Se sube por el arbol para buscar baselines cercanos sin salirse de la raiz analizada.
    while True:
        if current.exists():
            for child in current.iterdir():
                if is_baseline_dir(child):
                    candidates.append((child, depth))

        if current == search_root or current.parent == current:
            break

        if search_root not in current.parents and current != search_root:
            break

        current = current.parent
        depth += 1

    return candidates


def find_nearest_baseline(capture_dir: Path, search_root: Path) -> Path | None:
    candidates = _collect_candidate_baselines(capture_dir, search_root)
    if not candidates:
        return None

    capture_ts = timestamp_key_from_path(capture_dir)

    def sort_key(item: tuple[Path, int]):
        baseline_dir, depth = item
        baseline_ts = timestamp_key_from_path(baseline_dir)
        if capture_ts is not None and baseline_ts is not None:
            delta = abs(capture_ts - baseline_ts)
        else:
            delta = 99999999999999
        return (depth, delta, baseline_dir.name)

    candidates.sort(key=sort_key)
    return candidates[0][0]


def find_neighbor_baselines(capture_dir: Path, search_root: Path) -> tuple[Path | None, Path | None]:
    candidates = _collect_candidate_baselines(capture_dir, search_root)
    if not candidates:
        return None, None

    capture_ts = timestamp_key_from_path(capture_dir)
    if capture_ts is None:
        nearest = find_nearest_baseline(capture_dir, search_root)
        return nearest, None

    baseline_rows = []
    for baseline_dir, depth in candidates:
        baseline_ts = timestamp_key_from_path(baseline_dir)
        if baseline_ts is None:
            continue
        baseline_rows.append(
            {
                "path": baseline_dir,
                "depth": depth,
                "timestamp": baseline_ts,
            }
        )

    if not baseline_rows:
        nearest = find_nearest_baseline(capture_dir, search_root)
        return nearest, None

    pre_candidates = [row for row in baseline_rows if row["timestamp"] <= capture_ts]
    post_candidates = [row for row in baseline_rows if row["timestamp"] > capture_ts]

    baseline_pre = None
    baseline_post = None

    if pre_candidates:
        pre_candidates.sort(key=lambda row: (row["depth"], capture_ts - row["timestamp"], row["path"].name))
        baseline_pre = pre_candidates[0]["path"]

    if post_candidates:
        post_candidates.sort(key=lambda row: (row["depth"], row["timestamp"] - capture_ts, row["path"].name))
        baseline_post = post_candidates[0]["path"]

    return baseline_pre, baseline_post


def build_session_id(search_root: Path, capture_dir: Path) -> str:
    relative = capture_dir.relative_to(search_root)
    safe_parts = []
    for part in relative.parts:
        safe_parts.append(re.sub(r"[^A-Za-z0-9_-]+", "_", part))
    return "__".join(safe_parts)


def extract_visit_name(path: Path) -> str:
    for part in path.parts:
        if part.startswith("Visita_"):
            return part

    # Scheduler blocks (PI_5): e.g. ordeno_am_20260402_0215
    parent_name = (path.parent.name or "").strip()
    match = re.fullmatch(r"(?P<label>.+)_(?P<date>\d{8})_\d{4}", parent_name)
    if match:
        date_text = match.group("date")
        dd, mm, yyyy = date_text[6:8], date_text[4:6], date_text[0:4]
        return f"Visita_{dd}_{mm}_{yyyy}"

    return path.parent.name if path.parent.name else "Sin_visita"


def extract_block_label(path: Path) -> str:
    parent_name = path.parent.name.strip()
    return parent_name or "Sin_bloque"


def infer_operation_mode(capture_dir: Path) -> str:
    serial_exists = (capture_dir / "serial_hex.txt").exists()
    antenna_udp_exists = (capture_dir / "antena_udp.txt").exists()
    etl_exists = any(capture_dir.glob("*.etl"))
    pcap_exists = resolve_pcap_path(capture_dir) is not None

    # La presencia de serial suele marcar escenarios de ordeno; si no, se interpreta como telemetria biótica.
    if serial_exists:
        return "ordeno_completo"
    if antenna_udp_exists or etl_exists or pcap_exists:
        return "telemetria_collar"
    return "indeterminado"


def build_session(search_root: Path, capture_dir: Path) -> dict:
    baseline_pre, baseline_post = find_neighbor_baselines(capture_dir, search_root)
    baseline_selected = baseline_pre if baseline_pre else baseline_post
    # Aqui se concentra la foto minima de una sesion: identidad, bloque, evidencias y baseline asociado.
    return {
        "sample_id": build_session_id(search_root, capture_dir),
        "visit_name": extract_visit_name(capture_dir),
        "block_label": extract_block_label(capture_dir),
        "operation_mode": infer_operation_mode(capture_dir),
        "capture_dir": capture_dir,
        "capture_is_short": capture_dir.name.endswith("_corta"),
        "baseline_pre": baseline_pre,
        "baseline_post": baseline_post,
        "baseline_dir": baseline_selected,
        "serial_path": capture_dir / "serial_hex.txt",
        "antenna_udp_path": resolve_antenna_udp_path(capture_dir),
        "etl_path": resolve_etl_path(capture_dir),
        "pcap_path": resolve_pcap_path(capture_dir),
        "session_type": "capture",
    }


def build_baseline_only_session(search_root: Path, baseline_dir: Path) -> dict:
    return {
        "sample_id": f"BASELINE_ONLY__{build_session_id(search_root, baseline_dir)}",
        "visit_name": extract_visit_name(baseline_dir),
        "block_label": extract_block_label(baseline_dir),
        "operation_mode": "baseline",
        "capture_dir": baseline_dir,
        "baseline_pre": None,
        "baseline_post": None,
        "baseline_dir": baseline_dir,
        "serial_path": baseline_dir / "serial_hex.txt",
        "antenna_udp_path": None,
        "etl_path": None,
        "pcap_path": None,
        "session_type": "baseline_only",
    }


def discover_sessions(root_dir: Path) -> list[dict]:
    root_dir = root_dir.resolve()
    sessions = []

    # El descubrimiento es intencionalmente simple: recorrer todo y quedarse solo con capturas utiles.
    for path in sorted(root_dir.rglob("*")):
        if not is_capture_dir(path):
            continue
        if not has_capture_payload(path):
            continue
        sessions.append(build_session(root_dir, path))

    return sessions


def discover_baseline_only_sessions(root_dir: Path, excluded_visit_names: set[str] | None = None) -> list[dict]:
    root_dir = root_dir.resolve()
    excluded_visit_names = excluded_visit_names or set()
    sessions = []

    for path in sorted(root_dir.rglob("*")):
        if not is_baseline_dir(path):
            continue
        if not has_baseline_files(path):
            continue
        if extract_visit_name(path) in excluded_visit_names:
            continue
        sessions.append(build_baseline_only_session(root_dir, path))

    return sessions


def discover_single_session(sample_path: Path) -> dict:
    sample_path = sample_path.resolve()
    if not sample_path.exists():
        raise FileNotFoundError(f"No existe la ruta: {sample_path}")
    if not sample_path.is_dir():
        raise ValueError(f"La ruta no es un directorio: {sample_path}")
    if not is_capture_dir(sample_path):
        raise ValueError(f"La ruta no corresponde a una carpeta Captura_*: {sample_path}")
    if not has_capture_payload(sample_path):
        raise ValueError(f"La carpeta no contiene serial_hex.txt, antena_udp.txt, .etl ni captura.pcap/pcapng: {sample_path}")

    search_root = sample_path.parent
    return build_session(search_root, sample_path)
