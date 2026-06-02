import json
import unicodedata
from datetime import datetime
from pathlib import Path


def decode_best(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "utf-8", "latin1", "cp850"):
        try:
            return raw.decode(encoding)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def read_text(path: Path) -> str:
    return decode_best(path.read_bytes())


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    return normalized.lower()


def time_str_to_ms(time_str: str) -> int:
    dt = datetime.strptime(time_str, "%H:%M:%S.%f")
    return ((dt.hour * 3600) + (dt.minute * 60) + dt.second) * 1000 + int(dt.microsecond / 1000)


def epoch_to_day_ms(epoch_seconds: float) -> int:
    dt = datetime.fromtimestamp(float(epoch_seconds))
    return ((dt.hour * 3600) + (dt.minute * 60) + dt.second) * 1000 + int(dt.microsecond / 1000)


def percent(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return (numerator / denominator) * 100.0


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def dump_json(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
