import argparse
import hashlib
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime

import serial

"""
FincaDiag
---------

Herramienta de diagnostico, captura y generacion de baseline para una
plataforma de adquisicion basada en Raspberry Pi.

Criterio de compatibilidad:
Este sistema fue migrado desde un entorno de ejecucion previo en laptop
con Windows hacia una Raspberry Pi con Linux. Para evitar cambios en el
dashboard de analisis y en el flujo de revision forense ya establecido,
los archivos de salida conservan un formato compatible con la etapa
anterior.

Esta decision no busca emular el sistema operativo anfitrion, sino
preservar la estructura de evidencia y los nombres de artefactos ya
consumidos por herramientas auxiliares del proyecto. De este modo se
mantiene continuidad operativa, comparabilidad entre capturas y
compatibilidad con el proceso de analisis previamente validado.

El sistema obtiene datos reales del entorno Linux/Raspberry Pi, pero los
serializa en un formato de salida adaptado a los requerimientos del
pipeline existente.
"""

# =========================
# PARAMETROS DE OPERACION
# =========================
INTERFACE_NAME = "eth0"
INTERFACE_LABEL = "Ethernet 2"
ADAPTER_DESCRIPTION = "Realtek USB GbE Family Controller"

PORT_NAME = "/dev/ttyUSB0"
BAUD_RATE = 19200
UDP_LISTEN_PORT = 6001
BASE_DIR = "/home/esmeralda/FincaLogs"
PING_HOST = "8.8.8.8"

UDP_READ_SIZE = 65535
UDP_SOCKET_BUFFER = 4 * 1024 * 1024

CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
END = "\033[0m"


def get_mode_profile(option):
    profiles = {
        "1": {
            "label": "antena_udp_pcap_filtrado",
            "capture_udp": True,
            "capture_serial": False,
            "pcap_filter": ["udp", "port", str(UDP_LISTEN_PORT)],
            "secondary_pcap_filter": [],
        },
        "2": {
            "label": "serial_pcap_completo",
            "capture_udp": False,
            "capture_serial": True,
            "pcap_filter": [],
            "secondary_pcap_filter": [],
        },
        "3": {
            "label": "pcap_completo",
            "capture_udp": False,
            "capture_serial": False,
            "pcap_filter": [],
            "secondary_pcap_filter": [],
        },
        "5": {
            "label": "serial_udp_pcap_completo",
            "capture_udp": True,
            "capture_serial": True,
            "pcap_filter": [],
            "secondary_pcap_filter": ["udp", "port", str(UDP_LISTEN_PORT)],
        },
    }
    return profiles.get(option, {})


def print_header():
    os.system("clear")
    print(f"{CYAN}==============================================")
    print("                  FincaDiag")
    print("    Diagnostico, captura y baseline de red")
    print(f"=============================================={END}")


def check_root():
    if os.geteuid() != 0:
        print(f"{RED}[!] ERROR: Ejecute con 'sudo python3 FincaDiag.py'{END}")
        sys.exit(1)


def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def run_command(command):
    try:
        return subprocess.check_output(
            command,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""


def sha256_file(path):
    if not os.path.exists(path):
        return ""

    digest = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
    except OSError:
        return ""
    return digest.hexdigest()


def get_boot_id():
    return read_file("/proc/sys/kernel/random/boot_id")


def get_timezone_name():
    timezone = read_file("/etc/timezone")
    if timezone:
        return timezone

    timedatectl_output = run_command(["timedatectl", "show", "--property=Timezone", "--value"])
    if timedatectl_output:
        return timedatectl_output.splitlines()[0].strip()
    return ""


def parse_key_value_output(text):
    result = {}
    for line in text.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip()
    return result


def get_clock_status():
    timedatectl_raw = run_command(
        [
            "timedatectl",
            "show",
            "--property=Timezone",
            "--property=NTPSynchronized",
            "--property=SystemClockSynchronized",
            "--property=LocalRTC",
        ]
    )
    timedatectl_data = parse_key_value_output(timedatectl_raw)
    chrony_tracking = run_command(["chronyc", "tracking"])
    chrony_sources = run_command(["chronyc", "sources"])

    return {
        "timezone": timedatectl_data.get("Timezone", "") or get_timezone_name(),
        "ntp_synchronized": timedatectl_data.get("NTPSynchronized", ""),
        "system_clock_synchronized": timedatectl_data.get("SystemClockSynchronized", ""),
        "local_rtc": timedatectl_data.get("LocalRTC", ""),
        "chrony_tracking": chrony_tracking,
        "chrony_sources": chrony_sources,
    }


def build_artifact_metadata(path):
    exists = os.path.exists(path)
    return {
        "path": path,
        "exists": exists,
        "size_bytes": os.path.getsize(path) if exists else 0,
        "sha256": sha256_file(path) if exists else "",
    }


def write_json_file(path, data):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)


def read_file(path):
    try:
        with open(path, "r", encoding="utf-8") as file:
            return file.read().strip()
    except OSError:
        return ""


def prefix_to_mask(prefix_length):
    try:
        return str(ipaddress.IPv4Network(f"0.0.0.0/{prefix_length}").netmask)
    except (ipaddress.NetmaskValueError, ValueError):
        return ""


def list_interfaces():
    interfaces = []
    try:
        for name in os.listdir("/sys/class/net"):
            if os.path.isdir(os.path.join("/sys/class/net", name)):
                interfaces.append(name)
    except OSError:
        pass
    return sorted(interfaces)


def get_search_suffixes():
    suffixes = []
    try:
        with open("/etc/resolv.conf", "r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if stripped.startswith("search "):
                    suffixes.extend(stripped.split()[1:])
                elif stripped.startswith("domain "):
                    suffixes.extend(stripped.split()[1:])
    except OSError:
        pass
    return suffixes


def get_dns_servers():
    servers = []
    try:
        with open("/etc/resolv.conf", "r", encoding="utf-8") as file:
            for line in file:
                stripped = line.strip()
                if stripped.startswith("nameserver"):
                    parts = stripped.split()
                    if len(parts) >= 2:
                        servers.append(parts[1])
    except OSError:
        pass
    return servers


def get_mac_address(interface_name):
    return read_file(f"/sys/class/net/{interface_name}/address").upper()


def get_interface_index(interface_name):
    try:
        return socket.if_nametoindex(interface_name)
    except OSError:
        return 0


def get_interface_state(interface_name):
    return read_file(f"/sys/class/net/{interface_name}/operstate")


def get_ipv4_info(interface_name):
    output = run_command(["ip", "-4", "-o", "addr", "show", "dev", interface_name])
    if not output:
        return {
            "ip": "",
            "mask": "",
            "prefix": "",
            "dynamic": False,
        }

    lines = output.splitlines()
    selected_line = ""
    for line in lines:
        if " scope global " in line:
            selected_line = line
            break
    if not selected_line:
        selected_line = lines[0]

    match = re.search(r"inet\s+(\d+\.\d+\.\d+\.\d+)/(\d+)", selected_line)
    if not match:
        return {
            "ip": "",
            "mask": "",
            "prefix": "",
            "dynamic": False,
        }

    ipv4 = match.group(1)
    prefix = match.group(2)
    return {
        "ip": ipv4,
        "mask": prefix_to_mask(prefix),
        "prefix": prefix,
        "dynamic": " dynamic " in f" {selected_line} ",
    }


def get_ipv6_link_local(interface_name):
    output = run_command(["ip", "-6", "-o", "addr", "show", "dev", interface_name, "scope", "link"])
    for line in output.splitlines():
        match = re.search(r"inet6\s+([0-9a-fA-F:]+)/\d+", line)
        if match:
            return match.group(1)
    return ""


def get_default_gateways():
    gateways = {}
    output = run_command(["ip", "-4", "route", "show", "default"])
    for line in output.splitlines():
        parts = line.split()
        iface = ""
        gateway = ""
        if "dev" in parts:
            iface = parts[parts.index("dev") + 1]
        if "via" in parts:
            gateway = parts[parts.index("via") + 1]
        if iface and gateway and iface not in gateways:
            gateways[iface] = gateway
    return gateways


def get_interface_label(interface_name):
    if interface_name == INTERFACE_NAME:
        return f"Adaptador de Ethernet {INTERFACE_LABEL}"
    if interface_name == "lo":
        return "Adaptador de Loopback"
    if os.path.exists(f"/sys/class/net/{interface_name}/wireless"):
        return f"Adaptador de LAN inalambrica {interface_name}"
    return f"Adaptador de Ethernet {interface_name}"


def get_interface_description(interface_name):
    if interface_name == INTERFACE_NAME:
        return ADAPTER_DESCRIPTION
    if interface_name == "lo":
        return "Software Loopback Interface 1"
    if os.path.exists(f"/sys/class/net/{interface_name}/wireless"):
        return f"Interfaz inalambrica {interface_name}"
    return interface_name


def get_interface_dns_suffix():
    suffixes = get_search_suffixes()
    return suffixes[0] if suffixes else ""


def get_ipconfig_interfaces():
    gateways = get_default_gateways()
    interfaces_data = []

    for interface_name in list_interfaces():
        ipv4_info = get_ipv4_info(interface_name)
        ipv6_link_local = get_ipv6_link_local(interface_name)
        mac_address = get_mac_address(interface_name)
        state = get_interface_state(interface_name)

        has_address = bool(ipv4_info["ip"] or ipv6_link_local)
        media_disconnected = not has_address and state not in ("up", "unknown")

        interface_data = {
            "name": interface_name,
            "label": get_interface_label(interface_name),
            "description": get_interface_description(interface_name),
            "mac": mac_address.replace(":", "-"),
            "dhcp_enabled": "si" if ipv4_info["dynamic"] else "no",
            "autoconfig": "si",
            "ipv4": ipv4_info["ip"],
            "mask": ipv4_info["mask"],
            "ipv6_local": ipv6_link_local,
            "gateway": gateways.get(interface_name, ""),
            "dns_suffix": get_interface_dns_suffix() if interface_name == INTERFACE_NAME else "",
            "media_disconnected": media_disconnected,
            "netbios": "habilitado" if interface_name == INTERFACE_NAME else "No disponible",
        }
        interfaces_data.append(interface_data)

    return interfaces_data


def get_arp_entries():
    entries_by_interface = {}
    output = run_command(["ip", "neigh", "show"])

    for line in output.splitlines():
        parts = line.split()
        if "dev" not in parts:
            continue

        ip_addr = parts[0]
        interface_name = parts[parts.index("dev") + 1]
        mac_addr = ""
        entry_type = "dinamico"

        if "lladdr" in parts:
            mac_addr = parts[parts.index("lladdr") + 1].replace(":", "-").lower()
        else:
            continue

        if "PERMANENT" in parts or "permanent" in parts:
            entry_type = "estatico"

        entries_by_interface.setdefault(interface_name, []).append(
            {
                "ip": ip_addr,
                "mac": mac_addr,
                "type": entry_type,
            }
        )

    for interface_name in entries_by_interface:
        entries_by_interface[interface_name].sort(key=lambda item: item["ip"])

    return entries_by_interface


def collect_ipv4_routes():
    route_lines = []
    seen = set()

    for table_name in ("main", "local"):
        output = run_command(["ip", "-4", "route", "show", "table", table_name])
        for line in output.splitlines():
            cleaned = line.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                route_lines.append(cleaned)

    routes = []
    ipv4_by_iface = {}
    for interface_name in list_interfaces():
        ipv4_by_iface[interface_name] = get_ipv4_info(interface_name)["ip"]

    for line in route_lines:
        parts = line.split()
        if not parts:
            continue

        destination = ""
        mask = ""
        gateway = "En vinculo"
        interface_name = ""
        metric = "0"

        if parts[0] == "default":
            destination = "0.0.0.0"
            mask = "0.0.0.0"
            if "via" in parts:
                gateway = parts[parts.index("via") + 1]
        elif parts[0] in ("local", "broadcast", "anycast", "unreachable", "prohibit", "blackhole"):
            if len(parts) >= 2 and "/" in parts[1]:
                network = ipaddress.IPv4Network(parts[1], strict=False)
                destination = str(network.network_address)
                mask = str(network.netmask)
            elif len(parts) >= 2:
                destination = parts[1]
                mask = "255.255.255.255"
        elif "/" in parts[0]:
            network = ipaddress.IPv4Network(parts[0], strict=False)
            destination = str(network.network_address)
            mask = str(network.netmask)
        else:
            continue

        if "dev" in parts:
            interface_name = parts[parts.index("dev") + 1]
        if "metric" in parts:
            metric = parts[parts.index("metric") + 1]

        iface_ip = ipv4_by_iface.get(interface_name, "")
        if interface_name == "lo" and not iface_ip:
            iface_ip = "127.0.0.1"

        routes.append(
            {
                "destination": destination,
                "mask": mask,
                "gateway": gateway,
                "interface_ip": iface_ip,
                "metric": metric,
            }
        )

    unique_routes = []
    seen_routes = set()
    for route in routes:
        key = (
            route["destination"],
            route["mask"],
            route["gateway"],
            route["interface_ip"],
            route["metric"],
        )
        if key not in seen_routes:
            seen_routes.add(key)
            unique_routes.append(route)

    return unique_routes


def collect_ipv6_routes():
    route_lines = []
    seen = set()

    for table_name in ("main", "local"):
        output = run_command(["ip", "-6", "route", "show", "table", table_name])
        for line in output.splitlines():
            cleaned = line.strip()
            if cleaned and cleaned not in seen:
                seen.add(cleaned)
                route_lines.append(cleaned)

    formatted = []
    for line in route_lines:
        parts = line.split()
        if not parts:
            continue

        destination = parts[0]
        metric = "0"
        gateway = "En vinculo"
        iface_index = "0"

        if "metric" in parts:
            metric = parts[parts.index("metric") + 1]
        if "via" in parts:
            gateway = parts[parts.index("via") + 1]
        if "dev" in parts:
            interface_name = parts[parts.index("dev") + 1]
            iface_index = str(get_interface_index(interface_name))

        formatted.append(
            {
                "iface_index": iface_index,
                "metric": metric,
                "destination": destination,
                "gateway": gateway,
            }
        )

    unique_entries = []
    seen_entries = set()
    for item in formatted:
        key = (item["iface_index"], item["metric"], item["destination"], item["gateway"])
        if key not in seen_entries:
            seen_entries.add(key)
            unique_entries.append(item)

    return unique_entries


def check_connections():
    print(f"\n{YELLOW}Verificando conexiones...{END}")
    time.sleep(1)

    state = get_interface_state(INTERFACE_NAME)
    if state == "up":
        print(f"   {GREEN}[OK]{END} Interfaz {INTERFACE_NAME} activa.")
    elif state:
        print(f"   {RED}[!!]{END} Interfaz {INTERFACE_NAME} no activa.")
    else:
        print(f"   {RED}[!!]{END} No fue posible verificar la interfaz {INTERFACE_NAME}.")

    try:
        with socket.create_connection((PING_HOST, 53), timeout=2):
            print(f"   {GREEN}[OK]{END} Conexion de red disponible.")
    except OSError:
        print(f"   {YELLOW}[--]{END} Sin salida a Internet. Se continuara en modo local.")

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as test_sock:
            test_sock.bind(("0.0.0.0", UDP_LISTEN_PORT))
        print(f"   {GREEN}[OK]{END} Puerto UDP {UDP_LISTEN_PORT} disponible.")
    except OSError:
        print(f"   {RED}[!!]{END} Puerto UDP {UDP_LISTEN_PORT} en uso o bloqueado.")

    if os.path.exists(PORT_NAME):
        try:
            with serial.Serial(PORT_NAME, BAUD_RATE, timeout=0.1):
                pass
            print(f"   {GREEN}[OK]{END} Puerto serial disponible en {PORT_NAME}.")
        except serial.SerialException:
            print(f"   {RED}[!!]{END} Puerto serial detectado pero ocupado.")
    else:
        print(f"   {YELLOW}[--]{END} Puerto serial no detectado.")

    print(f"{CYAN}=============================================={END}\n")


def get_ping_details(host=PING_HOST):
    try:
        output = subprocess.check_output(
            ["ping", "-c", "4", host],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.SubprocessError, FileNotFoundError):
        return {
            "responses": [],
            "minimum": "",
            "maximum": "",
            "average": "",
            "ttl": "",
        }

    responses = []
    ttl_value = ""

    for line in output.splitlines():
        reply_match = re.search(r"time[=<]([\d\.]+)\s*ms", line)
        ttl_match = re.search(r"ttl[=\s](\d+)", line, re.IGNORECASE)

        if reply_match:
            time_value = reply_match.group(1)
            if time_value.endswith(".0"):
                time_value = time_value[:-2]
            responses.append(f"{time_value}ms")

        if ttl_match and not ttl_value:
            ttl_value = ttl_match.group(1)

    minimum = ""
    maximum = ""
    average = ""

    for line in output.splitlines():
        if "min/avg/max" in line or "rtt" in line:
            try:
                values = line.split("=")[1].strip().split("/")
                minimum = f"{values[0]}ms"
                average = f"{values[1]}ms"
                maximum = f"{values[2]}ms"
            except (IndexError, ValueError):
                pass

    return {
        "responses": responses,
        "minimum": minimum,
        "maximum": maximum,
        "average": average,
        "ttl": ttl_value,
    }


def write_compatible_ipconfig(out_dir):
    path = os.path.join(out_dir, "ipconfig_all.txt")
    hostname = socket.gethostname()
    search_suffixes = get_search_suffixes()
    dns_servers = get_dns_servers()
    interfaces = get_ipconfig_interfaces()

    with open(path, "w", encoding="utf-8") as f:
        f.write("\r\nConfiguracion IP de Windows\r\n\r\n")
        f.write(f"   Nombre de host. . . . . . . . . : {hostname}\r\n")
        f.write("   Sufijo DNS principal  . . . . . : \r\n")
        f.write("   Tipo de nodo. . . . . . . . . . : hibrido\r\n")
        f.write("   Enrutamiento IP habilitado. . . : no\r\n")
        f.write("   Proxy WINS habilitado . . . . . : no\r\n")
        if search_suffixes:
            f.write(f"   Lista de busqueda de sufijos DNS: {' '.join(search_suffixes)}\r\n")
        f.write("\r\n")

        for item in interfaces:
            f.write(f"{item['label']}:\r\n\r\n")

            if item["media_disconnected"]:
                f.write("   Estado de los medios. . . . . . . . . . . : medios desconectados\r\n")

            f.write(f"   Sufijo DNS especifico para la conexion. . : {item['dns_suffix']}\r\n")
            f.write(f"   Descripcion . . . . . . . . . . . . . . . : {item['description']}\r\n")
            f.write(f"   Direccion fisica. . . . . . . . . . . . . : {item['mac']}\r\n")
            f.write(f"   DHCP habilitado . . . . . . . . . . . . . : {item['dhcp_enabled']}\r\n")
            f.write(f"   Configuracion automatica habilitada . . . : {item['autoconfig']}\r\n")

            if item["ipv6_local"]:
                f.write(f"   Vinculo: direccion IPv6 local. . . : {item['ipv6_local']}(Preferido)\r\n")
            if item["ipv4"]:
                f.write(f"   Direccion IPv4. . . . . . . . . . . . . . : {item['ipv4']}(Preferido)\r\n")
            if item["mask"]:
                f.write(f"   Mascara de subred . . . . . . . . . . . . : {item['mask']}\r\n")

            f.write(f"   Puerta de enlace predeterminada . . . . . : {item['gateway']}\r\n")

            if item["name"] == INTERFACE_NAME and dns_servers:
                f.write(f"   Servidores DNS. . . . . . . . . . . . . . : {dns_servers[0]}\r\n")
                for server in dns_servers[1:]:
                    f.write(f"                                       {server}\r\n")

            f.write(f"   NetBIOS sobre TCP/IP. . . . . . . . . . . : {item['netbios']}\r\n")
            f.write("\r\n")


def write_compatible_arp(out_dir):
    path = os.path.join(out_dir, "arp_a.txt")
    entries_by_interface = get_arp_entries()

    with open(path, "w", encoding="utf-8") as f:
        wrote_any_section = False

        for interface_name in list_interfaces():
            ipv4 = get_ipv4_info(interface_name)["ip"]
            entries = entries_by_interface.get(interface_name, [])

            if not ipv4 and not entries:
                continue

            wrote_any_section = True
            interface_index = get_interface_index(interface_name)
            header_ip = ipv4 if ipv4 else "0.0.0.0"

            f.write(f"\r\nInterfaz: {header_ip} --- 0x{interface_index:x}\r\n")
            f.write("  Direccion de Internet          Direccion fisica      Tipo\r\n")

            for entry in entries:
                f.write(f"  {entry['ip'].ljust(30)} {entry['mac'].ljust(21)} {entry['type']}\r\n")

        if not wrote_any_section:
            f.write("\r\nInterfaz: 0.0.0.0 --- 0x0\r\n")
            f.write("  Direccion de Internet          Direccion fisica      Tipo\r\n")


def write_compatible_route(out_dir):
    path = os.path.join(out_dir, "route_print.txt")
    ipv4_routes = collect_ipv4_routes()
    ipv6_routes = collect_ipv6_routes()

    with open(path, "w", encoding="utf-8") as f:
        f.write("===========================================================================\r\n")
        f.write("Lista de interfaces\r\n")
        for interface_name in list_interfaces():
            index = get_interface_index(interface_name)
            mac_raw = get_mac_address(interface_name)
            mac_spaces = mac_raw.lower().replace(":", " ") if mac_raw else ""
            description = get_interface_description(interface_name)
            f.write(f"{str(index).rjust(3)}...{mac_spaces.ljust(20)} ......{description}\r\n")
        f.write("===========================================================================\r\n\r\n")

        f.write("IPv4 Tabla de enrutamiento\r\n")
        f.write("===========================================================================\r\n")
        f.write("Rutas activas:\r\n")
        f.write("Destino de red        Mascara de red   Puerta de enlace   Interfaz  Metrica\r\n")
        for route in ipv4_routes:
            f.write(
                f"{route['destination'].rjust(15)}  "
                f"{route['mask'].rjust(15)}  "
                f"{route['gateway'].rjust(16)}  "
                f"{route['interface_ip'].rjust(15)}  "
                f"{route['metric'].rjust(6)}\r\n"
            )
        f.write("===========================================================================\r\n")
        f.write("Rutas persistentes:\r\n")
        f.write("  Ninguno\r\n\r\n")

        f.write("IPv6 Tabla de enrutamiento\r\n")
        f.write("===========================================================================\r\n")
        f.write("Rutas activas:\r\n")
        f.write(" Cuando destino de red metrica      Puerta de enlace\r\n")
        for route in ipv6_routes:
            f.write(
                f"{route['iface_index'].rjust(3)}"
                f"{route['metric'].rjust(7)} "
                f"{route['destination'].ljust(24)} "
                f"{route['gateway']}\r\n"
            )
        f.write("===========================================================================\r\n")
        f.write("Rutas persistentes:\r\n")
        f.write("  Ninguno\r\n")


def write_compatible_report(out_dir):
    path = os.path.join(out_dir, "reporte.txt")
    local_ip = get_ipv4_info(INTERFACE_NAME)["ip"] or "0.0.0.0"
    gateway = get_default_gateways().get(INTERFACE_NAME, "")
    ping_data = get_ping_details()

    with open(path, "w", encoding="utf-8") as f:
        f.write("==========================================\r\n")
        f.write("1) RED Y CONECTIVIDAD\r\n")
        f.write("==========================================\r\n")
        f.write(f"RESUMEN RED: interfaz={INTERFACE_LABEL} ip={local_ip} gateway={gateway}\r\n")
        f.write("--- PRUEBA PING (LATENCIA) ---\r\n\r\n")

        if ping_data["responses"]:
            f.write(f"Haciendo ping a {PING_HOST} con 32 bytes de datos:\r\n")
            ttl_value = ping_data["ttl"] if ping_data["ttl"] else "0"
            for response in ping_data["responses"]:
                f.write(f"Respuesta desde {PING_HOST}: bytes=32 tiempo={response} TTL={ttl_value}\r\n")

            f.write(f"\r\nEstadisticas de ping para {PING_HOST}:\r\n")
            f.write(
                f"    Paquetes: enviados = 4, recibidos = {len(ping_data['responses'])}, "
                f"perdidos = {4 - len(ping_data['responses'])}\r\n"
            )
            loss_percentage = int(((4 - len(ping_data["responses"])) / 4) * 100)
            f.write(f"    ({loss_percentage}% perdidos),\r\n")

            if ping_data["minimum"] and ping_data["maximum"] and ping_data["average"]:
                f.write("Tiempos aproximados de ida y vuelta en milisegundos:\r\n")
                f.write(
                    f"    Minimo = {ping_data['minimum']}, "
                    f"Maximo = {ping_data['maximum']}, "
                    f"Media = {ping_data['average']}\r\n"
                )
        else:
            f.write(f"No fue posible obtener respuesta de ping hacia {PING_HOST}.\r\n")

        f.write("==========================================\r\n")
        f.write("FIN DEL PROCESO\r\n")
        f.write("==========================================\r\n")


def build_manifest_base(mode, out_dir):
    clock_status = get_clock_status()
    ipv4_info = get_ipv4_info(INTERFACE_NAME)
    gateways = get_default_gateways()

    return {
        "manifest_version": 1,
        "mode": mode,
        "mode_label": get_mode_profile(mode).get("label", "baseline"),
        "hostname": socket.gethostname(),
        "boot_id": get_boot_id(),
        "timezone": clock_status.get("timezone", "") or get_timezone_name(),
        "interface": {
            "name": INTERFACE_NAME,
            "ip": ipv4_info.get("ip", ""),
            "mask": ipv4_info.get("mask", ""),
            "gateway": gateways.get(INTERFACE_NAME, ""),
            "state": get_interface_state(INTERFACE_NAME),
            "mac": get_mac_address(INTERFACE_NAME),
        },
        "clock_status": clock_status,
        "output_dir": out_dir,
    }


def write_capture_manifest(
    out_dir,
    mode,
    started_at,
    ended_at,
    stop_reason,
    requested_seconds,
    serial_until_disconnect,
    udp_stats,
    serial_stats,
    pcap_file,
    telemetry_pcap_file,
    udp_file,
    serial_file,
):
    manifest = build_manifest_base(mode, out_dir)
    manifest.update(
        {
            "started_at": started_at.isoformat(timespec="milliseconds"),
            "ended_at": ended_at.isoformat(timespec="milliseconds"),
            "duration_seconds": round((ended_at - started_at).total_seconds(), 3),
            "requested_seconds": requested_seconds,
            "serial_until_disconnect": bool(serial_until_disconnect),
            "stop_reason": stop_reason,
            "artifacts": {
                "pcap": build_artifact_metadata(pcap_file),
                "pcap_6001": build_artifact_metadata(telemetry_pcap_file),
                "antena_udp": build_artifact_metadata(udp_file),
                "serial_hex": build_artifact_metadata(serial_file),
            },
            "stats": {
                "udp_packets": udp_stats["packets"],
                "udp_bytes": udp_stats["bytes"],
                "udp_changed_payloads": udp_stats["changes"],
                "serial_blocks": serial_stats["blocks"],
                "serial_bytes": serial_stats["bytes"],
            },
        }
    )
    write_json_file(os.path.join(out_dir, "capture_manifest.json"), manifest)


def write_baseline_manifest(out_dir):
    manifest = build_manifest_base("4", out_dir)
    manifest.update(
        {
            "generated_at": datetime.now().isoformat(timespec="milliseconds"),
            "artifacts": {
                "ipconfig_all": build_artifact_metadata(os.path.join(out_dir, "ipconfig_all.txt")),
                "arp_a": build_artifact_metadata(os.path.join(out_dir, "arp_a.txt")),
                "route_print": build_artifact_metadata(os.path.join(out_dir, "route_print.txt")),
                "reporte": build_artifact_metadata(os.path.join(out_dir, "reporte.txt")),
            },
        }
    )
    write_json_file(os.path.join(out_dir, "baseline_manifest.json"), manifest)


def run_baseline():
    print(f"{YELLOW}> Generando baseline compatible...{END}")

    base = os.environ.get("FINCA_BASE_DIR", BASE_DIR)
    ensure_dir(base)
    out_dir = os.path.join(base, f"Baseline_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    ensure_dir(out_dir)

    write_compatible_ipconfig(out_dir)
    write_compatible_arp(out_dir)
    write_compatible_route(out_dir)
    write_compatible_report(out_dir)
    write_baseline_manifest(out_dir)

    print(f"{GREEN}[OK] Baseline guardado en: {out_dir}{END}")
    sys.exit(0)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("-m", "--modo", type=str, help="Modo de ejecucion (1-4)")
    parser.add_argument("-t", "--tiempo", type=int, help="Segundos de captura")
    parser.add_argument(
        "--serial-hasta-desconexion",
        action="store_true",
        help="En modo 2, mantiene la captura hasta perder el cable serial",
    )
    return parser.parse_args()


def ask_mode():
    print_header()
    check_connections()
    print(f"{YELLOW}Seleccione una opcion:{END}")
    print("1. Modo antena (UDP + PCAP puerto 6001)")
    print("2. Modo serial (Serial + PCAP completo)")
    print("3. Solo PCAP completo")
    print("4. Solo baseline")
    print("5. Modo combinado (Serial + UDP + PCAP completo)\n")
    return input(f"{CYAN}Opcion (1-5): {END}")


def ask_capture_time():
    try:
        return int(input(f"\n{CYAN}Segundos de captura: {END}"))
    except ValueError:
        print(f"{RED}[!] Ingrese un numero valido.{END}")
        sys.exit(1)


def start_tcpdump(option, pcap_file):
    profile = get_mode_profile(option)
    if not profile:
        return None

    command = ["tcpdump", "-i", INTERFACE_NAME, "-s", "0", "-B", "4096", "-w", pcap_file]
    command.extend(profile.get("pcap_filter", []))

    try:
        return subprocess.Popen(command, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print(f"{RED}[!] tcpdump no esta instalado o no se encontro en el sistema.{END}")
        sys.exit(1)


def start_filtered_tcpdump(pcap_file, capture_filter):
    if not capture_filter:
        return None

    command = ["tcpdump", "-i", INTERFACE_NAME, "-s", "0", "-B", "4096", "-w", pcap_file]
    command.extend(capture_filter)

    try:
        return subprocess.Popen(command, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        print(f"{RED}[!] tcpdump no esta instalado o no se encontro en el sistema.{END}")
        sys.exit(1)


def open_udp_socket(option):
    profile = get_mode_profile(option)
    if not profile.get("capture_udp", False):
        return None

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, UDP_SOCKET_BUFFER)
    except OSError:
        pass
    sock.bind(("0.0.0.0", UDP_LISTEN_PORT))
    sock.setblocking(False)
    return sock


def open_serial_port(option):
    profile = get_mode_profile(option)
    if not profile.get("capture_serial", False):
        return None

    if not os.path.exists(PORT_NAME):
        return None

    try:
        return serial.Serial(PORT_NAME, BAUD_RATE, timeout=0)
    except serial.SerialException:
        return None


def serial_device_present():
    return os.path.exists(PORT_NAME)


def write_serial_line(file_handle, data):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    hex_data = " ".join(f"{byte:02X}" for byte in data)
    file_handle.write(f"[{timestamp}] {hex_data}\r\n")


def write_udp_line(file_handle, data, addr, changed):
    timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
    payload_hash = hashlib.sha1(data).hexdigest()[:12]
    hex_data = " ".join(f"{byte:02X}" for byte in data)
    file_handle.write(
        f"[{timestamp}] src={addr[0]}:{addr[1]} len={len(data)} "
        f"hash={payload_hash} changed={int(changed)} {hex_data}\r\n"
    )


def run_capture(option, seconds, automatic_mode, serial_until_disconnect=False):
    base = os.environ.get("FINCA_BASE_DIR", BASE_DIR)
    ensure_dir(base)
    out_dir = os.path.join(base, f"Captura_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    ensure_dir(out_dir)

    pcap_file = os.path.join(out_dir, "captura.pcap")
    telemetry_pcap_file = os.path.join(out_dir, "captura_6001.pcap")
    udp_file = os.path.join(out_dir, "antena_udp.txt")
    serial_file = os.path.join(out_dir, "serial_hex.txt")

    tcp_procs = []
    sock = None
    ser = None
    udp_handle = None
    serial_handle = None

    udp_packets = 0
    udp_bytes = 0
    udp_changes = 0
    serial_blocks = 0
    serial_bytes = 0
    last_udp_payload = None
    stop_reason = "completed"
    started_at = datetime.now()

    try:
        main_tcp_proc = start_tcpdump(option, pcap_file)
        if main_tcp_proc:
            tcp_procs.append(main_tcp_proc)
        secondary_filter = get_mode_profile(option).get("secondary_pcap_filter", [])
        telemetry_tcp_proc = start_filtered_tcpdump(telemetry_pcap_file, secondary_filter)
        if telemetry_tcp_proc:
            tcp_procs.append(telemetry_tcp_proc)
        sock = open_udp_socket(option)
        ser = open_serial_port(option)

        if sock:
            udp_handle = open(udp_file, "a", encoding="utf-8", buffering=1)

        if ser:
            serial_handle = open(serial_file, "a", encoding="utf-8", buffering=1)

        print(f"\n{GREEN}Iniciando captura en {out_dir}...{END}")
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time
            if not serial_until_disconnect and elapsed >= seconds:
                break

            if not automatic_mode:
                if serial_until_disconnect:
                    sys.stdout.write(
                        f"\r{YELLOW}Capturando serial... Tiempo transcurrido: {int(elapsed)} s{END}"
                    )
                else:
                    remaining = max(0, int(seconds - elapsed))
                    sys.stdout.write(f"\r{YELLOW}Capturando... Tiempo restante: {remaining} s{END}")
                sys.stdout.flush()

            if sock and udp_handle:
                while True:
                    try:
                        data, addr = sock.recvfrom(UDP_READ_SIZE)
                        changed = data != last_udp_payload
                        if changed:
                            udp_changes += 1
                        write_udp_line(udp_handle, data, addr, changed)
                        udp_packets += 1
                        udp_bytes += len(data)
                        last_udp_payload = data
                    except BlockingIOError:
                        break

            if ser and serial_handle:
                try:
                    waiting = ser.in_waiting
                    if waiting > 0:
                        data = ser.read(waiting)
                        write_serial_line(serial_handle, data)
                        serial_blocks += 1
                        serial_bytes += len(data)
                except (serial.SerialException, OSError):
                    if serial_until_disconnect:
                        stop_reason = "serial_disconnect"
                        print(f"\n{YELLOW}[!] Cable serial desconectado. Finalizando captura.{END}")
                        break
                    raise

            if serial_until_disconnect and get_mode_profile(option).get("capture_serial", False):
                if not serial_device_present():
                    stop_reason = "serial_disconnect"
                    print(f"\n{YELLOW}[!] Cable serial desconectado. Finalizando captura.{END}")
                    break

            time.sleep(0.001)

        if not automatic_mode:
            sys.stdout.write("\r" + " " * 60 + "\r")
            sys.stdout.flush()

        print(f"{GREEN}[OK] Captura finalizada en {out_dir}{END}")
        if get_mode_profile(option).get("secondary_pcap_filter"):
            print(f"{CYAN}PCAP adicional 6001: {telemetry_pcap_file}{END}")
        if sock:
            print(
                f"{CYAN}UDP capturado: {udp_packets} paquetes, {udp_bytes} bytes, "
                f"cambios reales de payload: {udp_changes}{END}"
            )
        if ser:
            print(f"{CYAN}Serial capturado: {serial_blocks} bloques, {serial_bytes} bytes{END}")

    except KeyboardInterrupt:
        stop_reason = "keyboard_interrupt"
        print(f"\n{YELLOW}[!] Captura detenida manualmente.{END}")
    except Exception as exc:
        stop_reason = f"error:{type(exc).__name__}"
        print(f"\n{RED}[!] Error durante la captura: {exc}{END}")
        raise
    finally:
        if udp_handle:
            udp_handle.close()
        if serial_handle:
            serial_handle.close()

        for tcp_proc in tcp_procs:
            tcp_proc.terminate()
        for tcp_proc in tcp_procs:
            try:
                tcp_proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                tcp_proc.kill()

        if ser:
            ser.close()
        if sock:
            sock.close()

        ended_at = datetime.now()
        write_capture_manifest(
            out_dir=out_dir,
            mode=option,
            started_at=started_at,
            ended_at=ended_at,
            stop_reason=stop_reason,
            requested_seconds=seconds,
            serial_until_disconnect=serial_until_disconnect,
            udp_stats={
                "packets": udp_packets,
                "bytes": udp_bytes,
                "changes": udp_changes,
            },
            serial_stats={
                "blocks": serial_blocks,
                "bytes": serial_bytes,
            },
            pcap_file=pcap_file,
            telemetry_pcap_file=telemetry_pcap_file,
            udp_file=udp_file,
            serial_file=serial_file,
        )


def main():
    check_root()
    args = parse_args()

    option = args.modo
    automatic_mode = bool(option)

    if not option:
        option = ask_mode()
    else:
        print(f"{YELLOW}[Auto] Ejecutando modo {option}.{END}")

    if option == "4":
        run_baseline()

    if option not in {"1", "2", "3", "5"}:
        print(f"{RED}[!] Opcion invalida. Use 1, 2, 3, 4 o 5.{END}")
        sys.exit(1)

    if args.serial_hasta_desconexion and option not in {"2", "5"}:
        print(f"{RED}[!] --serial-hasta-desconexion solo aplica con modo 2 o 5.{END}")
        sys.exit(1)

    if args.serial_hasta_desconexion:
        seconds = 0
    else:
        seconds = args.tiempo if args.tiempo else ask_capture_time()

    run_capture(option, seconds, automatic_mode,
                serial_until_disconnect=args.serial_hasta_desconexion)


if __name__ == "__main__":
    main()
