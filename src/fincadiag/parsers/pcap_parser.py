import os
from pathlib import Path
from tempfile import gettempdir

from fincadiag.models import NetworkEvent
from fincadiag.utils import epoch_to_day_ms, percent


_SCAPY_CACHE_ROOT = Path(os.environ.get("XDG_CACHE_HOME") or (Path(gettempdir()) / "fincadiag_scapy_cache"))
_SCAPY_CACHE_ROOT.mkdir(parents=True, exist_ok=True)
os.environ["XDG_CACHE_HOME"] = str(_SCAPY_CACHE_ROOT)

try:
    from scapy.all import ARP, Ether, ICMP, IP, PcapReader, Raw, TCP, UDP
    SCAPY_OK = True
except Exception:
    SCAPY_OK = False


def _is_multicast_ip(ip_text: str) -> bool:
    first_octet = ip_text.split(".")[0]
    return first_octet.isdigit() and 224 <= int(first_octet) <= 239


def is_multicast_packet(packet) -> bool:
    try:
        if packet.haslayer(IP) and _is_multicast_ip(packet[IP].dst):
            return True
        if packet.haslayer(Ether):
            dst_mac = packet[Ether].dst.lower()
            return dst_mac.startswith("01:00:5e") or dst_mac.startswith("33:33")
    except Exception:
        return False
    return False


def is_broadcast_packet(packet) -> bool:
    try:
        return packet.haslayer(Ether) and packet[Ether].dst.lower() == "ff:ff:ff:ff:ff:ff"
    except Exception:
        return False


def parse_pcap_file(path: Path, target_ip: str, target_port: int, signature_hex: str) -> dict:
    if not SCAPY_OK:
        raise RuntimeError("Scapy no esta instalado.")

    signature_bytes = bytes.fromhex(signature_hex)
    proto_counts = {"TCP": 0, "UDP": 0, "ICMP": 0, "ARP": 0, "Otros": 0}
    tcp_flags = {"SYN": 0, "RST": 0, "FIN": 0}
    top_talkers = {}
    total_packets = 0
    total_bytes = 0
    broadcast_packets = 0
    multicast_packets = 0
    telemetry_packets = 0
    telemetry_no_payload_packets = 0
    signature_count = 0
    external_ips = set()
    event_rows: list[NetworkEvent] = []
    top_ports = {}
    insecure_flows = {}
    arp_ip_to_macs = {}
    arp_mac_to_ips = {}
    first_packet_ts = ""
    last_packet_ts = ""

    with PcapReader(str(path)) as pcap_reader:
        for packet in pcap_reader:
            total_packets += 1
            total_bytes += len(packet)
            packet_time = float(packet.time)
            if not first_packet_ts:
                first_packet_ts = packet_time.__format__(".6f")
            last_packet_ts = packet_time.__format__(".6f")

            if is_broadcast_packet(packet):
                broadcast_packets += 1
            if is_multicast_packet(packet):
                multicast_packets += 1

            if packet.haslayer(TCP):
                proto_counts["TCP"] += 1
                flags = str(packet[TCP].flags)
                if "S" in flags:
                    tcp_flags["SYN"] += 1
                if "R" in flags:
                    tcp_flags["RST"] += 1
                if "F" in flags:
                    tcp_flags["FIN"] += 1
            elif packet.haslayer(UDP):
                proto_counts["UDP"] += 1
            elif packet.haslayer(ICMP):
                proto_counts["ICMP"] += 1
            elif packet.haslayer(ARP):
                proto_counts["ARP"] += 1
                arp_ip = getattr(packet[ARP], "psrc", "")
                arp_mac = getattr(packet[ARP], "hwsrc", "").upper()
                if arp_ip and arp_mac:
                    arp_ip_to_macs.setdefault(arp_ip, set()).add(arp_mac)
                    arp_mac_to_ips.setdefault(arp_mac, set()).add(arp_ip)
            else:
                proto_counts["Otros"] += 1

            if not packet.haslayer(IP):
                continue

            src_ip = packet[IP].src
            dst_ip = packet[IP].dst
            top_talkers[src_ip] = top_talkers.get(src_ip, 0) + 1

            if not (
                dst_ip.startswith("10.")
                or dst_ip.startswith("192.168.")
                or dst_ip.startswith("172.")
                or dst_ip.startswith("169.254.")
                or dst_ip.startswith("224.")
                or dst_ip.startswith("239.")
                or dst_ip == "255.255.255.255"
            ):
                external_ips.add(dst_ip)

            protocol = ""
            sport = 0
            dport = 0
            if packet.haslayer(TCP):
                protocol = "TCP"
                sport = int(packet[TCP].sport)
                dport = int(packet[TCP].dport)
            elif packet.haslayer(UDP):
                protocol = "UDP"
                sport = int(packet[UDP].sport)
                dport = int(packet[UDP].dport)

            if not protocol:
                continue

            top_ports[(protocol, dport)] = top_ports.get((protocol, dport), 0) + 1
            if dport in {21, 23, 80, 445}:
                insecure_flows[(src_ip, dst_ip, protocol, dport)] = insecure_flows.get((src_ip, dst_ip, protocol, dport), 0) + 1

            port_match = sport == target_port or dport == target_port
            ip_match = True if not target_ip else (src_ip == target_ip or dst_ip == target_ip)

            if port_match and ip_match:
                telemetry_packets += 1
                payload_bytes = bytes(packet[Raw].load) if packet.haslayer(Raw) else b""
                if not payload_bytes:
                    telemetry_no_payload_packets += 1
                    continue

                has_signature = signature_bytes in payload_bytes
                if has_signature:
                    signature_count += 1

                event_rows.append(
                    NetworkEvent(
                        timestamp=float(packet.time).__format__(".6f"),
                        day_ms=epoch_to_day_ms(float(packet.time)),
                        protocol=protocol,
                        src_ip=src_ip,
                        dst_ip=dst_ip,
                        src_port=sport,
                        dst_port=dport,
                        payload_len=len(payload_bytes),
                        event_kind="firma_56d100" if has_signature else "payload_port_6001",
                        has_signature=has_signature,
                        is_multicast=is_multicast_packet(packet),
                        payload_hex=payload_bytes.hex(" ").upper()[:180],
                    )
                )

    telemetry_udp_events = [event.to_dict() for event in event_rows if event.protocol == "UDP"]
    telemetry_tcp_events = [event.to_dict() for event in event_rows if event.protocol == "TCP"]
    telemetry_day_ms = [event.day_ms for event in event_rows]
    telemetry_gaps = [
        telemetry_day_ms[idx] - telemetry_day_ms[idx - 1]
        for idx in range(1, len(telemetry_day_ms))
        if telemetry_day_ms[idx] >= telemetry_day_ms[idx - 1]
    ]

    syn_ratio = percent(tcp_flags["SYN"], proto_counts["TCP"]) if proto_counts["TCP"] else 0.0
    rst_ratio = percent(tcp_flags["RST"], proto_counts["TCP"]) if proto_counts["TCP"] else 0.0
    fin_ratio = percent(tcp_flags["FIN"], proto_counts["TCP"]) if proto_counts["TCP"] else 0.0
    duration_s = max(0.0, float(last_packet_ts) - float(first_packet_ts)) if first_packet_ts and last_packet_ts else 0.0
    packet_rate_hz = (total_packets / duration_s) if duration_s > 0 else 0.0
    multicast_rate_hz = (multicast_packets / duration_s) if duration_s > 0 else 0.0
    broadcast_rate_hz = (broadcast_packets / duration_s) if duration_s > 0 else 0.0
    telemetry_rate_hz = (telemetry_packets / duration_s) if duration_s > 0 else 0.0

    top_talkers_rows = [
        {"ip": ip, "packets": count}
        for ip, count in sorted(top_talkers.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    top_talker_packets = top_talkers_rows[0]["packets"] if top_talkers_rows else 0
    top_talker_share_pct = percent(top_talker_packets, total_packets)

    top_ports_rows = [
        {"protocol": protocol, "dst_port": dport, "packets": count}
        for (protocol, dport), count in sorted(top_ports.items(), key=lambda x: x[1], reverse=True)[:10]
    ]
    insecure_flow_rows = [
        {
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "protocol": protocol,
            "dst_port": dport,
            "packets": count,
        }
        for (src_ip, dst_ip, protocol, dport), count in sorted(insecure_flows.items(), key=lambda x: x[1], reverse=True)
    ]
    arp_ip_conflicts = [
        {"ip": ip, "macs": sorted(list(macs))}
        for ip, macs in arp_ip_to_macs.items()
        if len(macs) > 1
    ]
    arp_mac_conflicts = [
        {"mac": mac, "ips": sorted(list(ips))}
        for mac, ips in arp_mac_to_ips.items()
        if len(ips) > 1
    ]

    return {
        "scapy_ok": True,
        "general": {
            "first_packet_timestamp": first_packet_ts,
            "last_packet_timestamp": last_packet_ts,
            "total_duration_s": round(duration_s, 3),
            "packet_rate_hz": round(packet_rate_hz, 3),
            "multicast_rate_hz": round(multicast_rate_hz, 3),
            "broadcast_rate_hz": round(broadcast_rate_hz, 3),
            "total_packets": total_packets,
            "total_bytes": total_bytes,
            "broadcast_pct": percent(broadcast_packets, total_packets),
            "multicast_pct": percent(multicast_packets, total_packets),
            "proto_counts": proto_counts,
            "tcp_flags": tcp_flags,
            "syn_ratio_pct": round(syn_ratio, 2),
            "rst_ratio_pct": round(rst_ratio, 2),
            "fin_ratio_pct": round(fin_ratio, 2),
            "external_ips": sorted(external_ips),
            "top_talkers": top_talkers_rows,
            "top_talker_share_pct": round(top_talker_share_pct, 2),
            "top_ports": top_ports_rows,
            "insecure_flows": insecure_flow_rows,
            "arp_ip_conflicts": arp_ip_conflicts,
            "arp_mac_conflicts": arp_mac_conflicts,
        },
        "telemetry": {
            "target_ip": target_ip,
            "target_port": target_port,
            "telemetry_packets": telemetry_packets,
            "telemetry_rate_hz": round(telemetry_rate_hz, 3),
            "telemetry_no_payload_packets": telemetry_no_payload_packets,
            "signature_count": signature_count,
            "udp_event_count": len(telemetry_udp_events),
            "tcp_event_count": len(telemetry_tcp_events),
            "multicast_event_count": sum(1 for event in event_rows if event.is_multicast),
            "avg_payload_len": round(sum(event.payload_len for event in event_rows) / len(event_rows), 3) if event_rows else 0.0,
            "max_payload_len": max((event.payload_len for event in event_rows), default=0),
            "max_interarrival_ms": max(telemetry_gaps) if telemetry_gaps else 0,
            "events": [event.to_dict() for event in event_rows],
            "udp_events": telemetry_udp_events,
            "tcp_events": telemetry_tcp_events,
        },
    }
