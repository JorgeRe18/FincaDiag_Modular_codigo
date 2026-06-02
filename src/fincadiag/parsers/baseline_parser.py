import re
import ipaddress
from pathlib import Path

from fincadiag.utils import normalize_text, read_text


BASELINE_FILENAMES = {"reporte.txt", "arp_a.txt", "ipconfig_all.txt", "route_print.txt"}


def _is_special_mac(mac: str) -> bool:
    mac_upper = str(mac).upper()
    return (
        mac_upper == "FF-FF-FF-FF-FF-FF"
        or mac_upper.startswith("01-00-5E")
        or mac_upper.startswith("33-33")
    )


def _is_special_ip(ip_text: str) -> bool:
    try:
        ip_obj = ipaddress.ip_address(ip_text)
        return ip_obj.is_multicast or str(ip_obj) == "255.255.255.255"
    except ValueError:
        return False


def has_baseline_files(path: Path) -> bool:
    return any((path / filename).exists() for filename in BASELINE_FILENAMES)


def parse_report_text(text: str) -> dict:
    norm = normalize_text(text)
    result = {
        "interface": "",
        "ip": "",
        "gateway": "",
        "latencies": [],
        "lat_min": None,
        "lat_max": None,
        "lat_media": None,
        "packet_loss": 0.0,
    }

    match_summary = re.search(
        r"resumen red:\s*interfaz=(.*?)\s+ip=([\d\.]+)\s+gateway=([\d\.]+)",
        norm,
    )
    if match_summary:
        result["interface"] = match_summary.group(1).strip()
        result["ip"] = match_summary.group(2).strip()
        result["gateway"] = match_summary.group(3).strip()

    lat_matches = re.findall(r"tiempo\s*[=<]\s*(\d+(?:\.\d+)?)ms", norm)
    result["latencies"] = [float(x) for x in lat_matches]

    match_ping = re.search(
        r"minimo\s*=\s*(\d+(?:\.\d+)?)ms,\s*maximo\s*=\s*(\d+(?:\.\d+)?)ms,\s*media\s*=\s*(\d+(?:\.\d+)?)ms",
        norm,
    )
    if match_ping:
        result["lat_min"] = float(match_ping.group(1))
        result["lat_max"] = float(match_ping.group(2))
        result["lat_media"] = float(match_ping.group(3))
    elif result["latencies"]:
        result["lat_min"] = min(result["latencies"])
        result["lat_max"] = max(result["latencies"])
        result["lat_media"] = round(sum(result["latencies"]) / len(result["latencies"]), 3)

    match_loss = re.search(r"\((\d+(?:\.\d+)?)%\s+perdidos\)", norm)
    if match_loss:
        result["packet_loss"] = float(match_loss.group(1))

    return result


def parse_arp_text(text: str) -> list[dict]:
    rows = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match_full = re.search(
            r"(\d{1,3}(?:\.\d{1,3}){3})\s+([0-9A-Fa-f:-]{17})\s+([A-Za-záéíóúÁÉÍÓÚ]+)",
            line,
        )
        if match_full:
            rows.append(
                {
                    "ip": match_full.group(1),
                    "mac": match_full.group(2).upper().replace(":", "-"),
                    "tipo": normalize_text(match_full.group(3)),
                }
            )
            continue

        match_partial = re.search(
            r"(\d{1,3}(?:\.\d{1,3}){3}).*?\b(estatico|estático|dinamico|dinámico)\b",
            line,
            re.IGNORECASE,
        )
        if match_partial:
            rows.append(
                {
                    "ip": match_partial.group(1),
                    "mac": "No visible",
                    "tipo": normalize_text(match_partial.group(2)),
                }
            )

    return rows


def parse_ipconfig_text(text: str) -> dict:
    norm = normalize_text(text)
    macs = re.findall(r"direccion fisica[^:]*:\s*([0-9a-f-]{17})", norm)
    ipv4s = re.findall(r"direccion ipv4[^:]*:\s*([\d\.]+)", norm)
    gateways = re.findall(r"puerta de enlace predeterminada[^:]*:\s*([\d\.]+)", norm)

    ip_local = ""
    for ip in ipv4s:
        if not ip.startswith("169.254."):
            ip_local = ip
            break
    if not ip_local and ipv4s:
        ip_local = ipv4s[0]

    return {
        "mac_local": macs[0].upper() if macs else "",
        "ip_local": ip_local,
        "gateway": gateways[0] if gateways else "",
    }


def parse_route_text(text: str) -> dict:
    norm = normalize_text(text)
    return {
        "default_routes": len(re.findall(r"0\.0\.0\.0\s+0\.0\.0\.0", norm)),
        "multicast_routes": len(re.findall(r"224\.0\.0\.0", norm)),
    }


def parse_baseline_dir(sample_dir: Path) -> dict:
    report_path = sample_dir / "reporte.txt"
    arp_path = sample_dir / "arp_a.txt"
    ipconfig_path = sample_dir / "ipconfig_all.txt"
    route_path = sample_dir / "route_print.txt"

    summary = {
        "sample_dir": str(sample_dir),
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

    if report_path.exists():
        data = parse_report_text(read_text(report_path))
        summary.update({k: v for k, v in data.items() if k in summary})
    if arp_path.exists():
        arp_entries = parse_arp_text(read_text(arp_path))
        summary["arp_entries"] = arp_entries
        summary["nodos_totales"] = len(arp_entries)
        summary["nodos_dinamicos"] = sum(1 for row in arp_entries if row["tipo"] == "dinamico")
    if ipconfig_path.exists():
        data = parse_ipconfig_text(read_text(ipconfig_path))
        if not summary["ip"]:
            summary["ip"] = data["ip_local"]
        if not summary["gateway"]:
            summary["gateway"] = data["gateway"]
        if data["mac_local"]:
            summary["mac_local"] = data["mac_local"]
    if route_path.exists():
        data = parse_route_text(read_text(route_path))
        summary.update(data)

    if summary["lat_min"] is not None and summary["lat_max"] is not None:
        summary["jitter_ms"] = round(summary["lat_max"] - summary["lat_min"], 3)

    if summary["gateway"]:
        gateway_entries = [row for row in summary["arp_entries"] if row["ip"] == summary["gateway"]]
        if gateway_entries:
            summary["gateway_seen_in_arp"] = True
            visible_macs = [row["mac"] for row in gateway_entries if row["mac"] != "No visible"]
            summary["gateway_mac"] = visible_macs[0] if visible_macs else gateway_entries[0]["mac"]

    ip_to_macs = {}
    mac_to_ips = {}
    for row in summary["arp_entries"]:
        if not _is_special_ip(row["ip"]) and not _is_special_mac(row["mac"]):
            ip_to_macs.setdefault(row["ip"], set()).add(row["mac"])
        if row["mac"] != "No visible" and not _is_special_mac(row["mac"]) and not _is_special_ip(row["ip"]):
            mac_to_ips.setdefault(row["mac"], set()).add(row["ip"])

    summary["arp_ip_conflicts"] = [
        {"ip": ip, "macs": sorted(list(macs))}
        for ip, macs in ip_to_macs.items()
        if len([mac for mac in macs if mac != "No visible"]) > 1
    ]
    summary["arp_mac_conflicts"] = [
        {"mac": mac, "ips": sorted(list(ips))}
        for mac, ips in mac_to_ips.items()
        if len(ips) > 1
    ]

    return summary
