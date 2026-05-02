import re
from collections import Counter
from pathlib import Path

from fincadiag.utils import read_text, time_str_to_ms


LINE_PATTERN = re.compile(
    r"^\[(?P<ts>\d{2}:\d{2}:\d{2}\.\d{3})\]\s+src=(?P<src_ip>\d+\.\d+\.\d+\.\d+):(?P<src_port>\d+)\s+len=(?P<len>\d+)\s+(?P<payload>.+?)\s*$"
)


def parse_antenna_udp_text(text: str, signature_hex: str = "56 D1 00") -> dict:
    signature_tokens = tuple(part.upper() for part in signature_hex.split() if part.strip())
    rows = []
    total_lines = 0
    malformed_lines = 0

    for raw_line in text.splitlines():
        total_lines += 1
        line = raw_line.strip()
        if not line:
            continue

        match = LINE_PATTERN.match(line)
        if not match:
            malformed_lines += 1
            continue

        payload_tokens = [token for token in match.group("payload").upper().split() if re.fullmatch(r"[0-9A-F]{2}", token)]
        if not payload_tokens:
            malformed_lines += 1
            continue

        rows.append(
            {
                "timestamp": match.group("ts"),
                "ts_ms": time_str_to_ms(match.group("ts")),
                "src_ip": match.group("src_ip"),
                "src_port": int(match.group("src_port")),
                "declared_len": int(match.group("len")),
                "payload_len": len(payload_tokens),
                "payload_hex": " ".join(payload_tokens),
                "has_signature": tuple(payload_tokens[: len(signature_tokens)]) == signature_tokens
                or (" ".join(signature_tokens) in " ".join(payload_tokens)),
            }
        )

    rows.sort(key=lambda item: item["ts_ms"])
    gaps = [
        rows[idx]["ts_ms"] - rows[idx - 1]["ts_ms"]
        for idx in range(1, len(rows))
        if rows[idx]["ts_ms"] >= rows[idx - 1]["ts_ms"]
    ]
    source_counts = Counter(row["src_ip"] for row in rows)
    payload_counts = Counter(row["payload_hex"] for row in rows)

    return {
        "total_events": len(rows),
        "total_lines": total_lines,
        "malformed_lines": malformed_lines,
        "signature_count": sum(1 for row in rows if row["has_signature"]),
        "unique_sources_count": len(source_counts),
        "sources": [{"src_ip": src_ip, "count": count} for src_ip, count in source_counts.most_common(10)],
        "unique_payloads_count": len(payload_counts),
        "top_payloads": [{"payload_hex": payload, "count": count} for payload, count in payload_counts.most_common(10)],
        "avg_payload_len": round(sum(row["payload_len"] for row in rows) / len(rows), 3) if rows else 0.0,
        "max_payload_len": max((row["payload_len"] for row in rows), default=0),
        "max_gap_ms": max(gaps) if gaps else 0,
        "avg_gap_ms": round(sum(gaps) / len(gaps), 3) if gaps else 0.0,
        "events": rows,
    }


def parse_antenna_udp_file(path: Path, signature_hex: str = "56 D1 00") -> dict:
    return parse_antenna_udp_text(read_text(path), signature_hex=signature_hex)
