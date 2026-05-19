from collections import Counter
import json
from pathlib import Path

from fincadiag.config import PROJECT_ROOT


def _load_known_hosts() -> dict:
    candidate = PROJECT_ROOT / "data" / "network" / "known_hosts.json"
    if not candidate.exists():
        candidate = Path("data/network/known_hosts.json")
    if candidate.exists():
        try:
            with open(candidate, encoding="utf-8") as f:
                data = json.load(f)
            by_mac = {h["mac"].upper(): h for h in data.get("hosts", []) if h.get("mac")}
            by_ip  = {h["ip"]: h for h in data.get("hosts", []) if h.get("ip")}
            oui    = {o["prefix"].upper(): o for o in data.get("known_oui_prefixes", [])}
            return {"by_mac": by_mac, "by_ip": by_ip, "oui": oui}
        except Exception:
            pass
    return {"by_mac": {}, "by_ip": {}, "oui": {}}


_KNOWN_HOSTS = _load_known_hosts()


def _label(mac: str = "", ip: str = "") -> str:
    mac_up = mac.upper() if mac else ""
    entry = _KNOWN_HOSTS["by_mac"].get(mac_up)
    if not entry and ip:
        entry = _KNOWN_HOSTS["by_ip"].get(ip)
    if not entry and mac_up:
        prefix = mac_up[:8]
        entry = _KNOWN_HOSTS["oui"].get(prefix)
    if entry:
        return f" [{entry['label']}]"
    return ""


def _is_known_pc_captura(ip: str) -> bool:
    entry = _KNOWN_HOSTS["by_ip"].get(ip, {})
    return entry.get("role") == "pc_captura"


SEVERITY_ORDER = {
    "Critica": 0,
    "Alta": 1,
    "Media": 2,
    "Baja": 3,
    "Info": 4,
}

SEVERITY_REASON_DEFAULTS = {
    "Critica": "Se clasifica como Critica porque compromete de forma directa la seguridad del segmento o invalida fuertemente la interpretacion tecnica de la muestra.",
    "Alta": "Se clasifica como Alta porque afecta de forma directa la calidad analitica, la seguridad del entorno o la sincronizacion de la telemetria y requiere revision prioritaria.",
    "Media": "Se clasifica como Media porque introduce degradacion o incertidumbre relevante, aunque no invalida por si sola toda la muestra.",
    "Baja": "Se clasifica como Baja porque describe una condicion secundaria o de contexto que conviene vigilar, pero con impacto acotado.",
    "Info": "Se clasifica como Info porque es un hallazgo descriptivo o de apoyo y no representa por si mismo una falla o incidente.",
}


def make_alert(
    severity: str,
    layer: str,
    rule: str,
    evidence: str,
    impact: str,
    recommendation: str,
    severity_reason: str = "",
    timestamp: str = "",
    src_ip: str = "",
    dst_ip: str = "",
    port: str = "",
    protocol: str = "",
) -> dict:
    return {
        "alert_name": rule,
        "severity": severity,
        "layer": layer,
        "rule": rule,
        "evidence": evidence,
        "impact": impact,
        "recommendation": recommendation,
        "severity_reason": severity_reason or SEVERITY_REASON_DEFAULTS.get(severity, ""),
        "timestamp": timestamp,
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "port": str(port) if port else "",
        "protocol": protocol,
    }


def summarize_alerts(alerts: list[dict]) -> dict:
    severity_counts = Counter(alert["severity"] for alert in alerts)
    layer_counts = Counter(alert["layer"] for alert in alerts)
    return {
        "total": len(alerts),
        "by_severity": {severity: severity_counts.get(severity, 0) for severity in SEVERITY_ORDER},
        "by_layer": dict(sorted(layer_counts.items(), key=lambda item: item[0])),
    }


def sort_alerts(alerts: list[dict]) -> list[dict]:
    return sorted(
        alerts,
        key=lambda alert: (
            SEVERITY_ORDER.get(alert["severity"], 99),
            alert.get("layer", ""),
            alert.get("timestamp", ""),
            alert.get("rule", ""),
        ),
    )


def _tag_alert_rules(alerts: list[dict], tag: str) -> list[dict]:
    tagged = []
    prefix = f"{tag}: "
    for alert in alerts:
        row = dict(alert)
        rule = row.get("rule", "")
        if rule and not str(rule).startswith(prefix):
            row["rule"] = f"{prefix}{rule}"
        alert_name = row.get("alert_name", "")
        if alert_name and not str(alert_name).startswith(prefix):
            row["alert_name"] = f"{prefix}{alert_name}"
        tagged.append(row)
    return tagged


def _build_baseline_point_alerts(baseline: dict) -> list[dict]:
    alerts = []

    lat_media = baseline.get("lat_media")
    jitter = float(baseline.get("jitter_ms", 0.0) or 0.0)
    packet_loss = float(baseline.get("packet_loss", 0.0) or 0.0)
    default_routes = int(baseline.get("default_routes", 0) or 0)
    nodos_dinamicos = int(baseline.get("nodos_dinamicos", 0) or 0)
    nodos_totales = int(baseline.get("nodos_totales", 0) or 0)

    if baseline.get("arp_ip_conflicts"):
        for conflict in baseline["arp_ip_conflicts"]:
            alerts.append(
                make_alert(
                    "Critica",
                    "baseline",
                    "Conflicto ARP IP-MAC",
                    f"La IP {conflict['ip']} aparece asociada a varias MAC: {', '.join(conflict['macs'])}.",
                    "Posible ARP spoofing o incoherencia de cache ARP.",
                    "Verificar la identidad del gateway y limpiar/renovar cache ARP antes de nuevas capturas.",
                )
            )

    if baseline.get("arp_mac_conflicts"):
        for conflict in baseline["arp_mac_conflicts"]:
            alerts.append(
                make_alert(
                    "Alta",
                    "baseline",
                    "Una MAC anuncia multiples IP",
                    f"La MAC {conflict['mac']} aparece en varias IP: {', '.join(conflict['ips'])}.",
                    "Puede indicar proxy ARP, virtualizacion o una condicion anomala en el segmento.",
                    "Confirmar si se trata de un comportamiento esperado del gateway o de un host no autorizado.",
                )
            )

    if default_routes > 1:
        alerts.append(
            make_alert(
                "Alta",
                "baseline",
                "Multiples rutas por defecto",
                f"Se detectaron {default_routes} rutas 0.0.0.0/0.",
                "Puede desviar trafico y alterar la telemetria o la salida WAN.",
                "Revisar tabla de ruteo y dejar una ruta principal coherente para la sesion de medicion.",
            )
        )

    if packet_loss >= 5:
        alerts.append(
            make_alert(
                "Alta",
                "baseline",
                "Perdida de paquetes elevada",
                f"La perdida de paquetes fue {packet_loss:.2f}%.",
                "Reduce la calidad de captura y puede explicar desfases o sesiones sin telemetria util.",
                "Revisar cableado, calidad del enlace y saturacion del switch antes de correlacionar.",
            )
        )
    elif packet_loss > 0:
        alerts.append(
            make_alert(
                "Media",
                "baseline",
                "Perdida de paquetes observada",
                f"La perdida de paquetes fue {packet_loss:.2f}%.",
                "Puede degradar la sincronizacion entre red y serial.",
                "Mantener registro de perdida y contrastarla con eta y desfase.",
            )
        )

    if lat_media is not None and float(lat_media) >= 100:
        alerts.append(
            make_alert(
                "Alta",
                "baseline",
                "Latencia local alta",
                f"La latencia media fue {float(lat_media):.3f} ms.",
                "La red local presenta retardo por encima de lo esperable para una LAN de adquisicion.",
                "Corroborar congestion, calidad del medio y trafico simultaneo en el segmento.",
            )
        )
    elif lat_media is not None and float(lat_media) >= 50:
        alerts.append(
            make_alert(
                "Media",
                "baseline",
                "Latencia local moderada",
                f"La latencia media fue {float(lat_media):.3f} ms.",
                "Puede elevar el desfase observado en sesiones sensibles.",
                "Comparar con baselines previos y posteriores de la misma visita.",
            )
        )

    if jitter >= 20:
        alerts.append(
            make_alert(
                "Alta",
                "baseline",
                "Jitter elevado",
                f"El jitter fue {jitter:.3f} ms.",
                "La variabilidad temporal del enlace puede comprometer la sincronizacion de telemetria.",
                "Correlacionar con porcentaje de multicast y picos de trafico del PCAP general.",
            )
        )
    elif jitter >= 5:
        alerts.append(
            make_alert(
                "Media",
                "baseline",
                "Jitter apreciable",
                f"El jitter fue {jitter:.3f} ms.",
                "Indica inestabilidad temporal en la capa de red.",
                "Vigilar su relacion con las ventanas donde cae eta.",
            )
        )

    if baseline.get("gateway") and not baseline.get("gateway_seen_in_arp", False):
        alerts.append(
            make_alert(
                "Media",
                "baseline",
                "Gateway no visible en ARP",
                f"El gateway {baseline.get('gateway')} no aparece en la tabla ARP de la sesion.",
                "Puede indicar aislamiento, falta de trafico reciente o un problema de resolucion local.",
                "Forzar trafico al gateway antes de medir o validar el estado de la interfaz local.",
            )
        )

    if nodos_dinamicos >= 10:
        alerts.append(
            make_alert(
                "Media",
                "baseline",
                "Cantidad alta de nodos dinamicos",
                f"Se observaron {nodos_dinamicos} nodos dinamicos sobre {nodos_totales} entradas ARP.",
                "Un numero alto de vecinos activos puede introducir ruido y variabilidad en la LAN.",
                "Segregar la red o medir en ventanas con menor actividad lateral.",
            )
        )
    return alerts


def _build_baseline_transition_alerts(baseline: dict) -> list[dict]:
    alerts = []
    transition = baseline.get("baseline_transition", {})
    if not transition.get("available"):
        return alerts

    lat_delta = transition.get("lat_media_delta")
    jitter_delta = transition.get("jitter_delta")
    nodos_delta = transition.get("nodos_delta")

    if lat_delta is not None and abs(float(lat_delta)) >= 20:
        alerts.append(
            make_alert(
                "Media",
                "baseline",
                "Cambio fuerte de latencia entre baseline previo y posterior",
                f"El delta pre-post de latencia fue {float(lat_delta):.3f} ms.",
                "Sugiere que la condicion de red cambio durante la ventana de medicion.",
                "Interpretar la muestra junto al baseline previo y posterior, no como un estado fijo.",
            )
        )

    if jitter_delta is not None and abs(float(jitter_delta)) >= 10:
        alerts.append(
            make_alert(
                "Media",
                "baseline",
                "Cambio fuerte de jitter entre baseline previo y posterior",
                f"El delta pre-post de jitter fue {float(jitter_delta):.3f} ms.",
                "La estabilidad temporal del enlace vario a lo largo de la toma.",
                "Cruzar este cambio con el comportamiento del PCAP general y el desfase de correlacion.",
            )
        )

    if nodos_delta is not None and abs(float(nodos_delta)) >= 5:
        alerts.append(
            make_alert(
                "Baja",
                "baseline",
                "Cambio de vecinos ARP entre baseline previo y posterior",
                f"El delta pre-post de nodos ARP fue {float(nodos_delta):.0f}.",
                "Puede reflejar renovacion normal de cache o actividad nueva en la red.",
                "Registrar el cambio como contexto operativo de la sesion.",
            )
        )

    return alerts


def build_baseline_alerts(baseline: dict) -> list[dict]:
    return _build_baseline_point_alerts(baseline) + _build_baseline_transition_alerts(baseline)


def build_baseline_pre_post_alerts(baseline: dict) -> list[dict]:
    pre = baseline.get("baseline_pre_summary") or {}
    post = baseline.get("baseline_post_summary") or {}
    alerts = []
    if pre:
        alerts.extend(_tag_alert_rules(_build_baseline_point_alerts(pre), "PRE"))
    if post:
        alerts.extend(_tag_alert_rules(_build_baseline_point_alerts(post), "POST"))
    alerts.extend(_build_baseline_transition_alerts(baseline))
    return alerts


def build_serial_alerts(serial: dict, session_type: str = "capture", operation_mode: str = "indeterminado") -> list[dict]:
    alerts = []
    if not serial.get("available", False):
        if session_type == "baseline_only":
            return []
        if operation_mode == "telemetria_collar":
            return []
        return [
            make_alert(
                "Info",
                "serial",
                "Canal serial no disponible",
                "La sesion no incluye serial_hex.txt.",
                "No es posible reconstruir eventos operativos ni correlacion serial directa.",
                "Si la visita requiere correlacion, capture serial y PCAP en la misma ventana temporal.",
            )
        ]

    total_frames = int(serial.get("total_frames", serial.get("total_events", 0)) or 0)
    heartbeat_ratio = float(serial.get("heartbeat_ratio_pct", 0.0) or 0.0)
    malformed = int(serial.get("malformed_lines", 0) or 0)
    max_gap = int(serial.get("max_gap_ms", 0) or 0)
    coverage_pct = float(serial.get("heartbeat_coverage_pct", 0.0) or 0.0)
    heartbeat_count = int(serial.get("heartbeat_count", 0) or 0)
    heartbeat_gap_count = int(serial.get("heartbeat_gap_count", 0) or 0)
    unknown_frames = int(serial.get("unknown_frame_count", 0) or 0)
    cow_events = int(serial.get("cow_event_count", 0) or 0)
    success_events = int(serial.get("cow_success_count", 0) or 0)
    missing_rfid = int(serial.get("cow_missing_rfid_count", 0) or 0)
    missing_flow = int(serial.get("cow_missing_flow_count", 0) or 0)
    ambiguous_flow_events = int(serial.get("cow_events_with_ambiguous_flow_count", 0) or 0)
    partial_events = int(serial.get("cow_partial_count", 0) or 0)
    fragmented_frames = int(serial.get("fragmented_frame_count", 0) or 0)

    if total_frames == 0:
        alerts.append(
            make_alert(
                "Media",
                "serial",
                "Sesion serial vacia",
                "El archivo serial existe, pero no se reconstruyeron frames validos.",
                "No hay eventos operativos utiles para correlacionar con telemetria de red.",
                "Revisar formato del archivo o integridad de la captura serial.",
            )
        )
        return alerts

    if malformed > 0:
        alerts.append(
            make_alert(
                "Baja",
                "serial",
                "Lineas seriales no parseables",
                f"Se descartaron {malformed} lineas por formato no interpretable.",
                "Una fraccion del flujo no pudo normalizarse para el analisis.",
                "Conservar el raw original y revisar si existe otra variante de formato en FincaDiag.",
            )
        )

    if fragmented_frames > 0:
        alerts.append(
            make_alert(
                "Info",
                "serial",
                "Fragmentacion serial reconstruida",
                f"Se reagruparon {fragmented_frames} frames a partir de multiples lineas cercanas.",
                "La captura presenta fragmentacion del adaptador y requirio reconstruccion previa.",
                "Usar estos frames reconstruidos como base del analisis, no las lineas crudas aisladas.",
            )
        )

    if heartbeat_count == 0:
        alerts.append(
            make_alert(
                "Alta",
                "serial",
                "Sin heartbeat de control observable",
                "No se detectaron heartbeats A4 82 04/05 A0 en la captura.",
                "No hay una referencia fuerte para medir cobertura efectiva del bus.",
                "Validar si la sesion corresponde a otra fase operativa o si el canal de control se perdio en la captura.",
            )
        )

    if heartbeat_ratio >= 70:
        alerts.append(
            make_alert(
                "Media",
                "serial",
                "Dominancia de control serial",
                f"El {heartbeat_ratio:.2f}% de los frames luce repetitivo y compatible con control/heartbeat.",
                "La captura contiene mucho trafico de control y poca variabilidad operativa visible.",
                "Separar control, flujo y eventos de vaca antes de sacar conclusiones de negocio.",
            )
        )

    if coverage_pct < 60 and heartbeat_count > 0:
        alerts.append(
            make_alert(
                "Alta" if coverage_pct < 30 else "Media",
                "serial",
                "Cobertura efectiva baja del bus",
                f"La cobertura estimada por heartbeat fue {coverage_pct:.2f}%.",
                "Hay huecos importantes en el canal de control o una captura parcial del periodo esperado.",
                "Revisar ventanas sin heartbeat antes de usar la sesion como evidencia completa del ordeño.",
            )
        )

    if heartbeat_gap_count > 0:
        alerts.append(
            make_alert(
                "Alta" if max_gap >= 30000 else "Media",
                "serial",
                "Huecos en la cobertura del bus",
                f"Se detectaron {heartbeat_gap_count} brechas de cobertura; el mayor hueco fue {max_gap} ms.",
                "Puede representar perdida de captura, pausa operativa o desconexion temporal del canal.",
                "Contrastar estos huecos con baseline, PCAP y eventos de vaca incompletos.",
            )
        )

    if unknown_frames > 0:
        alerts.append(
            make_alert(
                "Media" if (unknown_frames / total_frames) >= 0.15 else "Baja",
                "serial",
                "Frames seriales desconocidos",
                f"Se observaron {unknown_frames} frames que no encajan en control, flujo ni eventos de vaca.",
                "Pueden corresponder a ruido, variaciones del protocolo o bytes anomales con valor forense.",
                "Conservarlos y revisar su distribucion temporal antes de descartarlos como ruido.",
            )
        )

    if cow_events == 0:
        alerts.append(
            make_alert(
                "Media",
                "serial",
                "Sin eventos de vaca reconstruidos",
                "El serial fue parseado, pero no aparecieron secuencias con C2 como inicio de evento.",
                "La sesion no permite medir permanencia, flujo por vaca ni fallos de identificacion del tag de collar.",
                "Validar si el turno estaba activo o si esta captura pertenece a otra fase del sistema.",
            )
        )
        return alerts

    if missing_rfid > 0:
        alerts.append(
            make_alert(
                "Alta",
                "serial",
                "Eventos de vaca sin tag de collar asociado",
                f"Se reconstruyeron {missing_rfid} eventos con C2 pero sin identificacion valida de tag de collar en la ventana esperada.",
                "Es consistente con fallos de identificacion del collar o descarte silencioso del cruce.",
                "Priorizar estas ventanas porque conectan directamente con el problema central del TFG.",
            )
        )

    if missing_flow > 0:
        alerts.append(
            make_alert(
                "Alta" if success_events == 0 else "Media",
                "serial",
                "Eventos de vaca sin flujo asociado",
                f"Se reconstruyeron {missing_flow} eventos con identificacion de tag pero sin muestras E4 asignadas.",
                "La cadena fotocelda-tag-flujo queda incompleta para parte del turno.",
                "Revisar si el sensor de flujo estuvo activo o si existe desacople temporal entre canales seriales.",
            )
        )

    if ambiguous_flow_events > 0:
        alerts.append(
            make_alert(
                "Media",
                "serial",
                "Flujo ambiguo por concurrencia",
                f"Se detectaron {ambiguous_flow_events} eventos cuya ventana coincide con otras vacas activas del mismo lote.",
                "En una sala con varias jaulas en paralelo no siempre es posible atribuir cada muestra E4 a una sola vaca sin una senal adicional por puesto.",
                "Interpretar el flujo por vaca con cautela y priorizar validacion de campo para afinar asignacion por jaula.",
            )
        )

    if partial_events > 0:
        alerts.append(
            make_alert(
                "Media",
                "serial",
                "Eventos de vaca parciales",
                f"Se cerraron {partial_events} eventos sin secuencia completa C2-E2-C3.",
                "La reconstruccion de permanencia o cierre de ordeño queda incompleta en parte de la muestra.",
                "Usar estos casos como evidencia de incertidumbre operativa y revisar la ventana circundante.",
            )
        )

    return alerts


def build_pcap_alerts(pcap: dict, session_type: str = "capture") -> tuple[list[dict], list[dict]]:
    general_alerts = []
    telemetry_alerts = []

    if not pcap.get("available", False):
        if session_type == "baseline_only":
            return general_alerts, telemetry_alerts
        general_alerts.append(
            make_alert(
                "Info",
                "pcap_general",
                "PCAP no disponible",
                "La sesion no incluye captura de red.",
                "No es posible analizar ruido de LAN ni telemetria de antena en esta muestra.",
                "Capturar PCAP general y de telemetria cuando la visita requiera analisis de red.",
            )
        )
        return general_alerts, telemetry_alerts

    general = pcap.get("general", {})
    telemetry = pcap.get("telemetry", {})
    first_ts = general.get("first_packet_timestamp", "")

    multicast_pct = float(general.get("multicast_pct", 0.0) or 0.0)
    broadcast_pct = float(general.get("broadcast_pct", 0.0) or 0.0)
    syn_ratio = float(general.get("syn_ratio_pct", 0.0) or 0.0)
    rst_ratio = float(general.get("rst_ratio_pct", 0.0) or 0.0)
    external_ips = general.get("external_ips", [])
    insecure_flows = general.get("insecure_flows", [])
    arp_ip_conflicts = general.get("arp_ip_conflicts", [])
    arp_mac_conflicts = general.get("arp_mac_conflicts", [])
    top_talker_share = float(general.get("top_talker_share_pct", 0.0) or 0.0)

    if arp_ip_conflicts:
        for conflict in arp_ip_conflicts:
            mac_labels = ", ".join(m + _label(mac=m) for m in conflict["macs"])
            general_alerts.append(
                make_alert(
                    "Critica",
                    "pcap_general",
                    "Conflicto ARP en captura",
                    f"La IP {conflict['ip']} fue anunciada por varias MAC: {mac_labels}.",
                    "Es una firma compatible con ARP spoofing o inestabilidad de resolucion local.",
                    "Revisar respuestas ARP del gateway y aislar el segmento si la condicion persiste.",
                    timestamp=first_ts,
                    protocol="ARP",
                )
            )

    if arp_mac_conflicts:
        for conflict in arp_mac_conflicts:
            device_label = _label(mac=conflict["mac"])
            ip_labels = ", ".join(ip + _label(ip=ip) for ip in conflict["ips"])
            general_alerts.append(
                make_alert(
                    "Alta",
                    "pcap_general",
                    "Una MAC responde por varias IP",
                    f"La MAC {conflict['mac']}{device_label} anuncio varias IP: {ip_labels}.",
                    "Puede reflejar proxy ARP esperado o una condicion anomala de red.",
                    "Confirmar si corresponde al gateway o a un host no autorizado.",
                    timestamp=first_ts,
                    protocol="ARP",
                )
            )

    if multicast_pct >= 15:
        general_alerts.append(
            make_alert(
                "Alta",
                "pcap_general",
                "Tormenta multicast",
                f"El trafico multicast representa {multicast_pct:.2f}% del PCAP general.",
                "Puede aumentar latencia local y afectar la sincronizacion de telemetria.",
                "Segmentar la red o filtrar multidifusion no esencial durante la captura.",
                timestamp=first_ts,
            )
        )
    elif multicast_pct >= 5:
        general_alerts.append(
            make_alert(
                "Media",
                "pcap_general",
                "Multicast apreciable",
                f"El trafico multicast representa {multicast_pct:.2f}% del PCAP general.",
                "Introduce carga lateral relevante para un entorno IoT sensible al tiempo.",
                "Correlacionar este valor con el desfase medio y la variacion de eta.",
                timestamp=first_ts,
            )
        )

    if broadcast_pct >= 10:
        general_alerts.append(
            make_alert(
                "Alta",
                "pcap_general",
                "Tormenta broadcast",
                f"El trafico broadcast representa {broadcast_pct:.2f}% del PCAP general.",
                "Afecta el switch y eleva el ruido de fondo del segmento.",
                "Revisar protocolos de descubrimiento y dominios broadcast innecesarios.",
                timestamp=first_ts,
            )
        )
    elif broadcast_pct >= 3:
        general_alerts.append(
            make_alert(
                "Media",
                "pcap_general",
                "Broadcast por encima de lo deseado",
                f"El trafico broadcast representa {broadcast_pct:.2f}% del PCAP general.",
                "Puede contribuir a variaciones de retardo en ventanas de adquisicion.",
                "Reducir descubrimiento lateral y revisar hosts ruidosos.",
                timestamp=first_ts,
            )
        )

    if syn_ratio >= 40:
        general_alerts.append(
            make_alert(
                "Alta",
                "pcap_general",
                "Exceso de SYN",
                f"Las banderas SYN representan {syn_ratio:.2f}% del trafico TCP.",
                "Sugiere escaneo, conexiones incompletas o intentos masivos de inicio de sesion.",
                "Revisar los emisores principales y validar si son herramientas de mantenimiento autorizadas.",
                timestamp=first_ts,
                protocol="TCP",
            )
        )

    if rst_ratio >= 20:
        general_alerts.append(
            make_alert(
                "Media",
                "pcap_general",
                "Rafaga de RST",
                f"Las banderas RST representan {rst_ratio:.2f}% del trafico TCP.",
                "Sugiere rechazos repetidos, puertos cerrados o conexiones reseteadas.",
                "Inspeccionar destinos y puertos mas afectados para descartar escaneo o configuracion errada.",
                timestamp=first_ts,
                protocol="TCP",
            )
        )

    if external_ips:
        general_alerts.append(
            make_alert(
                "Alta",
                "pcap_general",
                "Salida a IP publica desde la LAN",
                f"Se observaron {len(external_ips)} destinos publicos: {', '.join(external_ips[:6])}.",
                "Puede indicar telemetria externa, actualizaciones no controladas o fuga de datos.",
                "Validar politica de salida WAN del gateway y aplicar deny-all si el segmento debe permanecer aislado.",
                timestamp=first_ts,
            )
        )

    if len(insecure_flows) > 2:
        src_ips = set(f["src_ip"] for f in insecure_flows)
        total_pkts = sum(f["packets"] for f in insecure_flows)
        all_known_pc = all(_is_known_pc_captura(ip) for ip in src_ips)
        severity_ins = "Media" if all_known_pc else "Alta"
        src_labels = ", ".join(ip + _label(ip=ip) for ip in sorted(src_ips))
        note = " Origen identificado como nodo de captura del experimento." if all_known_pc else ""
        general_alerts.append(
            make_alert(
                severity_ins,
                "pcap_general",
                "Protocolo inseguro observado",
                f"Se detectaron {len(insecure_flows)} flujos inseguros desde {src_labels} ({total_pkts} paquetes totales). Destinos: {', '.join(f['dst_ip'] for f in insecure_flows[:3])}{'...' if len(insecure_flows) > 3 else ''}.{note}",
                "Protocolos en texto claro o sensibles pueden exponer credenciales y metadatos.",
                "Eliminar servicios inseguros del segmento o encapsularlos en un entorno controlado.",
                timestamp=first_ts,
                protocol=insecure_flows[0]["protocol"],
            )
        )
    else:
        for flow in insecure_flows:
            is_pc = _is_known_pc_captura(flow["src_ip"])
            severity_ins = "Media" if is_pc else "Alta"
            src_label = flow["src_ip"] + _label(ip=flow["src_ip"])
            note = " Origen identificado como nodo de captura del experimento." if is_pc else ""
            general_alerts.append(
                make_alert(
                    severity_ins,
                    "pcap_general",
                    "Protocolo inseguro observado",
                    f"Se detecto trafico {flow['protocol']} hacia puerto {flow['dst_port']} entre {src_label} y {flow['dst_ip']} ({flow['packets']} paquetes).{note}",
                    "Protocolos en texto claro o sensibles pueden exponer credenciales y metadatos.",
                    "Eliminar servicios inseguros del segmento o encapsularlos en un entorno controlado.",
                    timestamp=first_ts,
                    src_ip=flow["src_ip"],
                    dst_ip=flow["dst_ip"],
                    port=flow["dst_port"],
                    protocol=flow["protocol"],
                )
            )

    if top_talker_share >= 50:
        top_talker = general.get("top_talkers", [{}])[0]
        general_alerts.append(
            make_alert(
                "Media",
                "pcap_general",
                "Top talker dominante",
                f"La IP {top_talker.get('ip', '')} genera {top_talker_share:.2f}% de los paquetes observados.",
                "Una sola fuente domina el trafico y puede sesgar el comportamiento de la red.",
                "Revisar si corresponde a la antena, al gateway o a un host ruidoso inesperado.",
                timestamp=first_ts,
                src_ip=top_talker.get("ip", ""),
            )
        )

    telemetry_packets = int(telemetry.get("telemetry_packets", 0) or 0)
    signature_count = int(telemetry.get("signature_count", 0) or 0)
    udp_count = int(telemetry.get("udp_event_count", 0) or 0)
    tcp_count = int(telemetry.get("tcp_event_count", 0) or 0)
    no_payload = int(telemetry.get("telemetry_no_payload_packets", 0) or 0)
    max_gap = int(telemetry.get("max_interarrival_ms", 0) or 0)
    multicast_events = int(telemetry.get("multicast_event_count", 0) or 0)
    target_port = telemetry.get("target_port", "")
    target_ip = telemetry.get("target_ip", "")

    if telemetry_packets == 0:
        telemetry_alerts.append(
            make_alert(
                "Alta",
                "telemetry_6001",
                "Canal de telemetria no observado",
                f"No se detecto trafico en el puerto objetivo {target_port} para la IP {target_ip or 'configurada'}.",
                "No existe evidencia de canal de antena en esta muestra.",
                "Verificar punto de captura, direccion IP objetivo y presencia real de trafico de la antena.",
            )
        )
        return general_alerts, telemetry_alerts

    if no_payload > 0 and no_payload == telemetry_packets:
        telemetry_alerts.append(
            make_alert(
                "Alta",
                "telemetry_6001",
                "Canal presente pero sin payload",
                f"Se observaron {telemetry_packets} paquetes del canal, pero todos sin carga util.",
                "La sesion ve control del canal pero no datos extraibles del collar.",
                "Confirmar si la antena estaba transmitiendo datos utiles o si la captura fue parcial.",
                port=target_port,
            )
        )
    elif no_payload > 0:
        telemetry_alerts.append(
            make_alert(
                "Baja",
                "telemetry_6001",
                "Paquetes del canal sin carga util",
                f"{no_payload} paquetes del canal objetivo no contenian payload.",
                "Parte del flujo corresponde a control o mantenimiento de sesion.",
                "Distinguir estos paquetes de los payloads utiles al analizar la eficiencia de extraccion.",
                port=target_port,
            )
        )

    if signature_count == 0:
        telemetry_alerts.append(
            make_alert(
                "Media",
                "telemetry_6001",
                "Firma 56 D1 00 no detectada",
                "Se detecto trafico del canal, pero no aparecio la firma candidata 56 D1 00.",
                "La correlacion de red debe basarse en payload generico del canal y no en la firma esperada.",
                "Revisar si la sesion corresponde al tipo de telemetria esperada o si la firma debe refinarse.",
                port=target_port,
            )
        )
    else:
        telemetry_alerts.append(
            make_alert(
                "Info",
                "telemetry_6001",
                "Firma 56 D1 00 presente",
                f"Se detectaron {signature_count} payloads con la firma 56 D1 00.",
                "Existe evidencia fuerte de trafico candidato a telemetria relevante.",
                "Usar estas ocurrencias como ancla principal de correlacion temporal.",
                port=target_port,
            )
        )

    if tcp_count > 0 and udp_count == 0:
        telemetry_alerts.append(
            make_alert(
                "Alta",
                "telemetry_6001",
                "Canal 6001 dominado por TCP",
                f"Se observaron {tcp_count} eventos TCP y 0 eventos UDP en el canal objetivo.",
                "Esto contradice la expectativa de telemetria UDP de la antena y puede indicar una sesion distinta.",
                "Verificar si la antena realmente estaba activa o si la IP/puerto objetivo corresponde a otro servicio.",
                port=target_port,
            )
        )
    elif tcp_count > 0:
        telemetry_alerts.append(
            make_alert(
                "Media",
                "telemetry_6001",
                "TCP presente en el canal 6001",
                f"Se observaron {tcp_count} eventos TCP junto a {udp_count} eventos UDP.",
                "Puede representar control de sesion, encapsulado alterno o mezcla de trafico inesperada.",
                "Distinguir TCP de UDP en el analisis de telemetria de la antena.",
                port=target_port,
            )
        )

    if max_gap >= 5000:
        telemetry_alerts.append(
            make_alert(
                "Media",
                "telemetry_6001",
                "Silencio prolongado del canal de telemetria",
                f"El mayor hueco entre eventos del canal fue {max_gap} ms.",
                "Sugiere pausas operativas, perdida de captura o baja actividad real de la antena.",
                "Comparar este hueco con silencios seriales y con variaciones del baseline.",
                port=target_port,
            )
        )

    if multicast_events > 0:
        telemetry_alerts.append(
            make_alert(
                "Baja",
                "telemetry_6001",
                "Eventos de telemetria marcados como multicast",
                f"Se observaron {multicast_events} eventos de telemetria en contexto multicast.",
                "Puede sesgar la interpretacion del canal si la antena comparte medio con trafico de multidifusion.",
                "Cruzar esta condicion con el porcentaje de multicast del PCAP general.",
                port=target_port,
            )
        )

    return general_alerts, telemetry_alerts


def build_correlation_alerts(correlation: dict, serial: dict, pcap: dict, baseline: dict, session_type: str = "capture", operation_mode: str = "indeterminado") -> list[dict]:
    alerts = []
    general = pcap.get("general", {})

    if session_type == "baseline_only":
        return alerts
    if operation_mode == "telemetria_collar":
        return alerts

    if not serial.get("available", False):
        alerts.append(
            make_alert(
                "Info",
                "correlation",
                "Sin canal serial para correlacion",
                "La sesion no incluye serial_hex.txt.",
                "No puede estimarse la cadena de custodia entre eventos operativos y red para esta muestra.",
                "Tomar serial y PCAP en la misma ventana si la muestra se destinara a correlacion.",
            )
        )
        return alerts

    if not pcap.get("available", False):
        alerts.append(
            make_alert(
                "Info",
                "correlation",
                "Sin PCAP para correlacion",
                "La sesion no incluye captura de red.",
                "No puede estimarse la confirmacion en red de los eventos operativos seriales.",
                "Agregar PCAP general y telemetria del canal 6001 en futuras sesiones.",
            )
        )
        return alerts

    if correlation.get("matched_events", 0) == 0:
        alerts.append(
            make_alert(
                "Alta",
                "correlation",
                "Sin eventos operativos correlacionados",
                "Se detectaron serial y PCAP, pero no hubo pareos dentro de la ventana configurada.",
                "La cadena de custodia serial-red queda vacia para esta sesion.",
                "Revisar ventana temporal, firma de red y simultaneidad real de las capturas.",
            )
        )
        return alerts

    eta = float(correlation.get("eta_extraccion", 0.0) or 0.0)
    delta = float(correlation.get("desfase_medio_ms", 0.0) or 0.0)
    delta_max = float(correlation.get("desfase_max_ms", 0.0) or 0.0)
    unmatched = int(correlation.get("unmatched_serial_events", 0) or 0)
    multicast_pct = float(general.get("multicast_pct", 0.0) or 0.0)
    packet_loss = float(baseline.get("packet_loss", 0.0) or 0.0)

    if eta < 1:
        alerts.append(
            make_alert(
                "Critica",
                "correlation",
                "Cadena de custodia extremadamente baja",
                f"La eficiencia de extraccion fue {eta:.2f}%.",
                "La mayoria de eventos operativos seriales no encuentra reflejo en la telemetria observada.",
                "Usar esta sesion como evidencia de degradacion fuerte y revisar canal, sincronizacion y punto de captura.",
            )
        )
    elif eta < 10:
        alerts.append(
            make_alert(
                "Alta",
                "correlation",
                "Cadena de custodia baja",
                f"La eficiencia de extraccion fue {eta:.2f}%.",
                "La correlacion existe, pero solo cubre una fraccion reducida de los eventos operativos.",
                "Comparar con las sesiones de mejor desempeno y con la carga multicast del segmento.",
            )
        )

    if delta >= 100:
        alerts.append(
            make_alert(
                "Alta",
                "correlation",
                "Desfase medio alto",
                f"El desfase medio absoluto fue {delta:.3f} ms.",
                "El desacople temporal entre serial y red puede comprometer la sincronizacion de telemetria.",
                "Analizar si coincide con jitter alto, perdida o multidifusion elevada.",
            )
        )
    elif delta >= 30:
        alerts.append(
            make_alert(
                "Media",
                "correlation",
                "Desfase medio apreciable",
                f"El desfase medio absoluto fue {delta:.3f} ms.",
                "Hay retraso observable entre ambos canales.",
                "Mantener esta muestra como referencia de degradacion moderada.",
            )
        )

    if delta_max >= 250:
        alerts.append(
            make_alert(
                "Alta",
                "correlation",
                "Desfase maximo critico",
                f"El desfase maximo absoluto fue {delta_max:.3f} ms.",
                "Existen eventos con desacople temporal severo.",
                "Revisar los pareos extremos y sus condiciones de red asociadas.",
            )
        )

    if correlation.get("network_mode") != "firma_56d100":
        alerts.append(
            make_alert(
                "Baja",
                "correlation",
                "Correlacion sin firma de red ancla",
                "La correlacion se hizo sobre payload generico del canal 6001 y no sobre 56 D1 00.",
                "La confianza semantica del pareo es menor que en sesiones con firma de red bien identificada.",
                "Marcar esta correlacion como funcional pero no tan fuerte como una basada en firma conocida.",
            )
        )

    if unmatched > 0:
        alerts.append(
            make_alert(
                "Media",
                "correlation",
                "Eventos operativos sin correspondencia en red",
                f"Quedaron {unmatched} eventos operativos relevantes sin pareo.",
                "Parte del flujo serial no se refleja en el canal de telemetria observado.",
                "Inspeccionar si se trata de descarte silencioso o de un offset temporal entre relojes.",
            )
        )

    if multicast_pct >= 10 and delta >= 30:
        alerts.append(
            make_alert(
                "Alta",
                "correlation",
                "Desfase elevado coincidente con multicast alto",
                f"Multicast={multicast_pct:.2f}% y desfase medio={delta:.3f} ms.",
                "La multidifusion aparece como factor plausible de degradacion temporal.",
                "Usar esta sesion como evidencia para reglas de prioridad y filtrado en el motor perimetral.",
            )
        )

    if packet_loss > 0 and eta < 10:
        alerts.append(
            make_alert(
                "Media",
                "correlation",
                "Eta baja coincidente con perdida de paquetes",
                f"Perdida={packet_loss:.2f}% y eta={eta:.2f}%.",
                "La degradacion del enlace puede estar contribuyendo a la baja extraccion efectiva.",
                "Documentar esta sesion como caso de acoplamiento entre QoS y rendimiento de telemetria.",
            )
        )

    return alerts


def build_alert_package(baseline: dict, serial: dict, pcap: dict, correlation: dict, session_type: str = "capture", operation_mode: str = "indeterminado") -> dict:
    baseline_alerts = build_baseline_pre_post_alerts(baseline)
    serial_alerts = build_serial_alerts(serial, session_type=session_type, operation_mode=operation_mode)
    pcap_general_alerts, telemetry_alerts = build_pcap_alerts(pcap, session_type=session_type)
    correlation_alerts = build_correlation_alerts(correlation, serial, pcap, baseline, session_type=session_type, operation_mode=operation_mode)

    combined = sort_alerts(
        baseline_alerts
        + serial_alerts
        + pcap_general_alerts
        + telemetry_alerts
        + correlation_alerts
    )

    return {
        "baseline": sort_alerts(baseline_alerts),
        "serial": sort_alerts(serial_alerts),
        "pcap_general": sort_alerts(pcap_general_alerts),
        "telemetry_6001": sort_alerts(telemetry_alerts),
        "correlation": sort_alerts(correlation_alerts),
        "all": combined,
        "summary": summarize_alerts(combined),
    }
