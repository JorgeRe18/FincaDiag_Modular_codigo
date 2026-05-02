from pathlib import Path


def _format_value(value, decimals: int = 3) -> str:
    if value in ("", None):
        return "N/D"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if decimals == 0:
        return f"{number:.0f}"
    return f"{number:.{decimals}f}"


def _format_alert_lines(alerts: list[dict], limit: int = 8) -> str:
    if not alerts:
        return "- Sin alertas registradas en esta seccion."

    lines = []
    for alert in alerts[:limit]:
        context = []
        if alert.get("timestamp"):
            context.append(f"ts={alert['timestamp']}")
        if alert.get("src_ip"):
            context.append(f"src={alert['src_ip']}")
        if alert.get("dst_ip"):
            context.append(f"dst={alert['dst_ip']}")
        if alert.get("port"):
            context.append(f"port={alert['port']}")
        if alert.get("protocol"):
            context.append(f"proto={alert['protocol']}")
        context_text = f" [{' | '.join(context)}]" if context else ""
        lines.append(f"- Nombre de la alerta: {alert.get('alert_name', alert['rule'])}")
        lines.append(f"  Severidad: {alert['severity']}")
        lines.append(f"  Capa: {alert.get('layer', 'N/D')}{context_text}")
        lines.append(f"  Evidencia: {alert['evidence']}")
        lines.append(f"  Por que se marca esta severidad: {alert.get('severity_reason', 'N/D')}")
        lines.append(f"  Impacto: {alert['impact']}")
        lines.append(f"  Sugerencia de revision: {alert['recommendation']}")

    if len(alerts) > limit:
        lines.append(f"- ... {len(alerts) - limit} alertas adicionales no se muestran en este resumen corto.")
    return "\n".join(lines)


def _format_human_alert_lines(alerts: list[dict], limit: int = 6) -> str:
    if not alerts:
        return "- No se observaron alertas relevantes en esta parte de la muestra."

    lines = []
    for alert in alerts[:limit]:
        alert_name = alert.get("alert_name", alert.get("rule", "Alerta sin nombre"))
        plain_type = alert.get("plain_type", "") or alert_name
        lines.append(f"- Alerta observada: {plain_type}")
        lines.append(f"  Nombre tecnico: {alert_name}")
        lines.append(f"  Severidad: {alert.get('severity', 'N/D')}")
        lines.append(f"  Que significa: {alert.get('impact', 'Sin descripcion disponible')}")
        lines.append(f"  Que conviene revisar: {alert.get('recommendation', 'Sin sugerencia disponible')}")

    if len(alerts) > limit:
        lines.append(f"- Hay {len(alerts) - limit} alertas adicionales que no se muestran en este resumen breve.")
    return "\n".join(lines)


def _build_obj1_role_text(
    operation_mode: str,
    serial: dict,
    antenna_udp: dict,
    pcap: dict,
    correlation: dict,
    field_validation: dict,
) -> tuple[str, str]:
    if operation_mode == "baseline":
        role = "linea base de red y contraste pre/post de latencia, jitter y nodos."
    elif operation_mode == "telemetria_collar":
        role = "caracterizacion del canal de collar, exposicion UDP/6001 y cobertura del dominio biotico."
    else:
        role = "caracterizacion de firmas seriales del ordeno, semantica operativa y estimacion preliminar de eta."

    if correlation.get("matched_events", 0) > 0:
        confidence = "alto para desfase y eta preliminar"
    elif field_validation.get("available", False):
        confidence = "medio, con apoyo de validacion de campo"
    elif serial.get("available", False) or antenna_udp.get("available", False) or pcap.get("file_detected", False):
        confidence = "medio, util para linea base y firmas"
    else:
        confidence = "bajo, muestra de apoyo contextual"

    return role, confidence


def build_technical_report(
    sample_name: str,
    baseline: dict,
    serial: dict,
    antenna_udp: dict,
    pcap: dict,
    correlation: dict,
    alerts: dict,
    window_ms: int,
    etl_path: str = "",
    operation_mode: str = "indeterminado",
    block_label: str = "",
    field_validation: dict | None = None,
) -> str:
    pre = baseline.get("baseline_pre_summary", {})
    post = baseline.get("baseline_post_summary", {})
    transition = baseline.get("baseline_transition", {})
    general = pcap.get("general", {})
    telemetry = pcap.get("telemetry", {})
    alert_summary = alerts.get("summary", {})
    severity_counts = alert_summary.get("by_severity", {})
    is_baseline_only = baseline.get("baseline_strategy") == "baseline_only"
    field_validation = field_validation or {}
    obj1_role, obj1_confidence = _build_obj1_role_text(operation_mode, serial, antenna_udp, pcap, correlation, field_validation)
    operation_mode_label = {
        "ordeno_completo": "Ordeño completo",
        "telemetria_collar": "Telemetría de collar",
        "baseline": "Baseline",
    }.get(operation_mode, operation_mode or "Indeterminado")
    files_block = f"""- Carpeta de captura: {baseline.get('capture_dir', '') or 'N/D'}
- Baseline pre: {baseline.get('baseline_pre', '') or 'No asociado'}
- Baseline post: {baseline.get('baseline_post', '') or 'No asociado'}
- Baseline usado: {baseline.get('baseline_dir', '') or 'No asociado'}
- Serial hex: {serial.get('source_path', 'No detectado') or 'No detectado'}
- Antena UDP txt: {antenna_udp.get('source_path', 'No detectado') or 'No detectado'}
- ETL de captura: {etl_path or 'No detectado'}
- PCAP: {pcap.get('source_path', 'No detectado') or 'No detectado'}"""

    if is_baseline_only:
        serial_block = """- En esta sesion baseline-only no se conto con flujo serial.
- Esta seccion se conserva solo como referencia de lectura."""
        antenna_udp_block = """- En esta sesion baseline-only no se conto con registro antena_udp.txt.
- Esta seccion se conserva solo como referencia de lectura."""
        pcap_general_block = """- En esta sesion baseline-only no se conto con PCAP general.
- Esta seccion se conserva solo como referencia de lectura."""
        telemetry_block = """- En esta sesion baseline-only no se conto con el canal de telemetria/antena.
- Esta seccion se conserva solo como referencia de lectura."""
        correlation_block = f"""- En esta sesion baseline-only no fue posible evaluar correlacion directa.
- Ventana de correlacion configurada: +/- {window_ms} ms
- No hubo canales serial y PCAP simultaneos que permitieran correlacion."""
    elif operation_mode == "telemetria_collar":
        serial_block = """- Este bloque se clasifica como telemetria de collar.
- No se espera reconstruccion completa del ordeño si no hubo serial_hex.txt."""
        antenna_udp_block = f"""- Disponible: {"Si" if antenna_udp.get('available', False) else "No"}
- Eventos de antena en texto: {antenna_udp.get('total_events', 0)}
- Firmas 56 D1 00 observadas: {antenna_udp.get('signature_count', 0)}
- Fuentes unicas: {antenna_udp.get('unique_sources_count', 0)}
- Payload promedio: {_format_value(antenna_udp.get('avg_payload_len'))} bytes
- Payload maximo: {_format_value(antenna_udp.get('max_payload_len'), 0)} bytes
- Lineas no parseables: {antenna_udp.get('malformed_lines', 0)}
- Maximo hueco entre eventos: {_format_value(antenna_udp.get('max_gap_ms'), 0)} ms"""
        pcap_general_block = f"""- Disponible: {"Si" if pcap.get('available', False) else "No"}
- Archivo PCAP detectado: {"Si" if pcap.get('file_detected', bool(pcap.get('source_path'))) else "No"}
- Paquetes totales: {general.get('total_packets', 0)}
- Volumen total: {_format_value(general.get('total_bytes'), 0)} bytes
- Multicast general: {_format_value(general.get('multicast_pct'), 2)}%
- Broadcast general: {_format_value(general.get('broadcast_pct'), 2)}%
- Ratio SYN: {_format_value(general.get('syn_ratio_pct'), 2)}%
- Ratio RST: {_format_value(general.get('rst_ratio_pct'), 2)}%
- Top talker dominante: {_format_value(general.get('top_talker_share_pct'), 2)}%
- Destinos publicos: {len(general.get('external_ips', []))}
- Nota de parseo: {pcap.get('parse_error', 'Sin novedades') or 'Sin novedades'}"""
        telemetry_block = f"""- IP objetivo: {telemetry.get('target_ip', '') or 'N/D'}
- Puerto objetivo: {telemetry.get('target_port', 0)}
- Paquetes del canal: {telemetry.get('telemetry_packets', 0)}
- Paquetes sin payload: {telemetry.get('telemetry_no_payload_packets', 0)}
- Eventos UDP: {telemetry.get('udp_event_count', 0)}
- Eventos TCP: {telemetry.get('tcp_event_count', 0)}
- Firmas 56 D1 00: {telemetry.get('signature_count', 0)}
- Payload promedio: {_format_value(telemetry.get('avg_payload_len'))} bytes
- Payload maximo: {_format_value(telemetry.get('max_payload_len'), 0)} bytes
- Maximo hueco de telemetria: {_format_value(telemetry.get('max_interarrival_ms'), 0)} ms"""
        correlation_block = f"""- Este bloque se clasifica como telemetria de collar.
- La correlacion serial-red del ordeño no se evalua aqui.
- Ventana de correlacion configurada: +/- {window_ms} ms"""
    else:
        serial_block = f"""- Disponible: {"Si" if serial.get('available', False) else "No"}
- Frames reconstruidos: {serial.get('total_frames', serial.get('total_events', 0))}
- Tandas reconstruidas: {serial.get('cow_batch_count', 0)}
- Tandas operativas estimadas por cadencia: {serial.get('operational_batch_count', 0)}
- Eventos de vaca: {serial.get('cow_event_count', 0)}
- Eventos exitosos: {serial.get('cow_success_count', 0)}
- Eventos sin tag de collar: {serial.get('cow_missing_rfid_count', 0)}
- Eventos sin flujo: {serial.get('cow_missing_flow_count', 0)}
- Eventos con flujo ambiguo por concurrencia: {serial.get('cow_events_with_ambiguous_flow_count', 0)}
- Eventos en ventana temporal de preparacion: {serial.get('cow_prep_phase_count', 0)}
- Eventos alineados con cadencia observada: {serial.get('cow_cadence_aligned_count', 0)}
- Escalon de cadencia dominante: {serial.get('cow_cadence_dominant_step', 0)} x {_format_value(serial.get('cadence_step_ms'), 0)} ms
- Muestras de flujo E4: {serial.get('total_flow_samples', 0)}
- Heartbeat de control: {serial.get('heartbeat_count', 0)} frames ({_format_value(serial.get('heartbeat_ratio_pct'), 2)}%)
- Cobertura por heartbeat: {_format_value(serial.get('heartbeat_coverage_pct'), 2)}%
- Heuristica temporal de preparacion: {serial.get('temp_prep_window_ms', 0)} ms
- Tolerancia de alineamiento de cadencia: {serial.get('cadence_tolerance_ms', 0)} ms
- Frames desconocidos: {serial.get('unknown_frame_count', 0)}
- Lineas no parseables: {serial.get('malformed_lines', 0)}
- Maximo hueco serial: {_format_value(serial.get('max_gap_ms'), 0)} ms"""
        antenna_udp_block = f"""- Disponible: {"Si" if antenna_udp.get('available', False) else "No"}
- Eventos de antena en texto: {antenna_udp.get('total_events', 0)}
- Firmas 56 D1 00 observadas: {antenna_udp.get('signature_count', 0)}
- Fuentes unicas: {antenna_udp.get('unique_sources_count', 0)}
- Payload promedio: {_format_value(antenna_udp.get('avg_payload_len'))} bytes
- Payload maximo: {_format_value(antenna_udp.get('max_payload_len'), 0)} bytes
- Lineas no parseables: {antenna_udp.get('malformed_lines', 0)}
- Maximo hueco entre eventos: {_format_value(antenna_udp.get('max_gap_ms'), 0)} ms"""
        pcap_general_block = f"""- Disponible: {"Si" if pcap.get('available', False) else "No"}
- Archivo PCAP detectado: {"Si" if pcap.get('file_detected', bool(pcap.get('source_path'))) else "No"}
- Paquetes totales: {general.get('total_packets', 0)}
- Volumen total: {_format_value(general.get('total_bytes'), 0)} bytes
- Multicast general: {_format_value(general.get('multicast_pct'), 2)}%
- Broadcast general: {_format_value(general.get('broadcast_pct'), 2)}%
- Ratio SYN: {_format_value(general.get('syn_ratio_pct'), 2)}%
- Ratio RST: {_format_value(general.get('rst_ratio_pct'), 2)}%
- Top talker dominante: {_format_value(general.get('top_talker_share_pct'), 2)}%
- Destinos publicos: {len(general.get('external_ips', []))}
- Nota de parseo: {pcap.get('parse_error', 'Sin novedades') or 'Sin novedades'}"""
        telemetry_block = f"""- IP objetivo: {telemetry.get('target_ip', '') or 'N/D'}
- Puerto objetivo: {telemetry.get('target_port', 0)}
- Paquetes del canal: {telemetry.get('telemetry_packets', 0)}
- Paquetes sin payload: {telemetry.get('telemetry_no_payload_packets', 0)}
- Eventos UDP: {telemetry.get('udp_event_count', 0)}
- Eventos TCP: {telemetry.get('tcp_event_count', 0)}
- Firmas 56 D1 00: {telemetry.get('signature_count', 0)}
- Payload promedio: {_format_value(telemetry.get('avg_payload_len'))} bytes
- Payload maximo: {_format_value(telemetry.get('max_payload_len'), 0)} bytes
- Maximo hueco de telemetria: {_format_value(telemetry.get('max_interarrival_ms'), 0)} ms"""
        correlation_block = f"""- Ventana de correlacion: +/- {window_ms} ms
- Modo de red usado: {correlation.get('network_mode', 'sin_datos')}
- Eventos seriales relevantes: {correlation.get('serial_events', 0)}
- Eventos de red usados: {correlation.get('network_events', 0)}
- Eventos correlacionados: {correlation.get('matched_events', 0)}
- Eventos seriales sin pareo: {correlation.get('unmatched_serial_events', 0)}
- Eta de extraccion: {_format_value(correlation.get('eta_extraccion'), 2)}%
- Desfase medio absoluto: {_format_value(correlation.get('desfase_medio_ms'))} ms
- Desfase maximo absoluto: {_format_value(correlation.get('desfase_max_ms'))} ms
- Desfase firmado medio: {_format_value(correlation.get('desfase_firmado_medio_ms'))} ms"""

    if field_validation.get("available", False):
        field_validation_block = f"""- Base de validacion: {field_validation.get('source_path', 'N/D')}
- Identidad observada en campo: tag Allflex del collar
- Ventana observada del ordeño: {field_validation.get('milking_started_at', 'N/D')} -> {field_validation.get('milking_ended_at', 'N/D')}
- Solapamiento con la captura: {_format_value(field_validation.get('capture_overlap_seconds'))} s
- Vacas observadas dentro de la captura: {field_validation.get('observed_cows_count', 0)}
- Tags conocidos en el registro: {field_validation.get('known_tag_count', 0)}
- Identificaciones rapidas (<= 3 s): {field_validation.get('quick_id_count', 0)}
- Identificaciones tardias (> 3 s): {field_validation.get('delayed_id_count', 0)}
- Identificaciones dudosas: {field_validation.get('id_doubtful_count', 0)}
- Flujo dudoso observado en campo: {field_validation.get('flow_doubtful_count', 0)}
- Casos con problema de fotocelda: {field_validation.get('photocell_issue_count', 0)}
- Casos con intervencion de controller/boton: {field_validation.get('controller_intervention_count', 0)}
- Casos con lectura retenida en controller: {field_validation.get('controller_stale_read_count', 0)}
- Vacas con mastitis anotadas: {field_validation.get('mastitis_count', 0)}
- Eventos del controller CELO/E56/E59: {field_validation.get('controller_celo_count', 0)} / {field_validation.get('controller_e56_count', 0)} / {field_validation.get('controller_e59_count', 0)}
- Eventos de vaca reconstruidos por el parser: {field_validation.get('parser_event_count', 0)}
- Delta parser - campo: {field_validation.get('parser_event_delta_vs_field', 0)}
- Ratio parser/campo: {_format_value(field_validation.get('parser_event_ratio_vs_field'), 3)}"""
    else:
        field_validation_block = (
            "- No hay validacion de campo asociada a esta sesion.\n"
            f"- Motivo: {field_validation.get('reason', 'sin_validacion_de_campo_para_la_sesion') or 'sin_validacion_de_campo_para_la_sesion'}"
        )

    return f"""
INFORME TECNICO DE APOYO POR SESION
==================================

Muestra: {sample_name}
Tipo de sesion: {"Baseline-only" if baseline.get('baseline_strategy') == 'baseline_only' else "Captura"}
Bloque operativo: {block_label or 'Sin bloque'}
Modo operativo: {operation_mode_label}
Rol analitico en Objetivo 1: {obj1_role}
Confianza de uso para Objetivo 1: {obj1_confidence}

1. Archivos de entrada detectados
{files_block}

2. Baseline de red
- IP local: {baseline.get('ip', '') or 'N/D'}
- Gateway: {baseline.get('gateway', '') or 'N/D'}
- Latencia media: {_format_value(baseline.get('lat_media'))} ms
- Jitter: {_format_value(baseline.get('jitter_ms'))} ms
- Perdida: {_format_value(baseline.get('packet_loss'), 2)}%
- Nodos ARP: {baseline.get('nodos_totales', 0)}
- Nodos dinamicos: {baseline.get('nodos_dinamicos', 0)}
- Estrategia de baseline usada: {baseline.get('baseline_strategy', 'none')}
- Baseline previo: {pre.get('dir', 'No asociado')}
- Baseline posterior: {post.get('dir', 'No asociado')}
- Delta latencia pre-post: {_format_value(transition.get('lat_media_delta'))} ms
- Delta jitter pre-post: {_format_value(transition.get('jitter_delta'))} ms
- Delta nodos pre-post: {_format_value(transition.get('nodos_delta'), 0)}

3. Serial
{serial_block}

4. Registro de antena en texto (antena_udp.txt)
{antenna_udp_block}

5. PCAP general
{pcap_general_block}

6. Telemetria de antena / puerto objetivo
{telemetry_block}

7. Correlacion serial <-> telemetria
{correlation_block}

8. Validacion de campo
{field_validation_block}

9. Resumen de alertas para seguimiento
- Alertas totales: {alert_summary.get('total', 0)}
- Criticas: {severity_counts.get('Critica', 0)}
- Altas: {severity_counts.get('Alta', 0)}
- Medias: {severity_counts.get('Media', 0)}
- Bajas: {severity_counts.get('Baja', 0)}
- Info: {severity_counts.get('Info', 0)}

10. Guia breve para leer la severidad
- Critica: la condicion puede comprometer de forma directa la seguridad del segmento o volver poco confiable la interpretacion tecnica de la muestra.
- Alta: afecta la calidad analitica, la seguridad del entorno o la sincronizacion de la telemetria y conviene revisarla con prioridad.
- Media: introduce degradacion o incertidumbre relevante, aunque por si sola no invalida toda la muestra.
- Baja: describe una condicion secundaria o de contexto con impacto acotado.
- Info: es un hallazgo descriptivo o de apoyo y no representa por si mismo una falla o incidente.

11. Alertas baseline
{_format_alert_lines(alerts.get('baseline', []))}

12. Alertas serial
{_format_alert_lines(alerts.get('serial', []))}

13. Alertas PCAP general
{_format_alert_lines(alerts.get('pcap_general', []))}

14. Alertas telemetria 6001
{_format_alert_lines(alerts.get('telemetry_6001', []))}

15. Alertas de correlacion
{_format_alert_lines(alerts.get('correlation', []))}

16. Notas de lectura e interpretacion
- El serial ya no se interpreta como un flujo uniforme; primero se reconstruyen frames y se separan control, flujo y eventos de vaca.
- El archivo antena_udp.txt se usa como evidencia textual complementaria del canal biotico cuando esta disponible.
- El archivo .etl se interpreta como artefacto historico de captura del flujo previo en Windows; se reporta como acompanamiento de algunas sesiones PCAP, no como evidencia del canal de antena.
- La firma 56 D1 00 se usa como firma de interes para la capa de telemetria cuando esta presente.
- La correlacion temporal se realiza a partir de eventos operativos seriales reconstruidos y no contra bytes sueltos del serial.
- La lectura de flujo por vaca usa una heuristica temporal provisoria de preparacion antes de marcar ausencia de flujo.
- La lectura operativa tambien marca eventos cuya permanencia se alinea con una cadencia observada cercana a 127 s.
- Las alertas del PCAP general describen condiciones de red que pueden influir en la sincronizacion, pero no se confunden con la telemetria de collares.
- Cuando hay validacion de campo, la identidad de referencia se interpreta como tag Allflex del collar; el bolo queda como capa aparte hasta contar con evidencia directa.
- Este informe se plantea como apoyo tecnico-forense para interpretacion y seguimiento, no como reemplazo de la revision experta del contexto operativo.
""".strip()


def build_human_report(
    sample_name: str,
    baseline: dict,
    serial: dict,
    antenna_udp: dict,
    pcap: dict,
    correlation: dict,
    alerts: dict,
    window_ms: int,
    etl_path: str = "",
    operation_mode: str = "indeterminado",
    block_label: str = "",
    field_validation: dict | None = None,
) -> str:
    general = pcap.get("general", {})
    telemetry = pcap.get("telemetry", {})
    alert_summary = alerts.get("summary", {})
    is_baseline_only = baseline.get("baseline_strategy") == "baseline_only"
    field_validation = field_validation or {}
    obj1_role, obj1_confidence = _build_obj1_role_text(operation_mode, serial, antenna_udp, pcap, correlation, field_validation)
    operation_mode_label = {
        "ordeno_completo": "Ordeño completo",
        "telemetria_collar": "Telemetría de collar",
        "baseline": "Baseline",
    }.get(operation_mode, operation_mode or "Indeterminado")

    if is_baseline_only:
        situation_text = (
            "Esta carpeta corresponde a una muestra de baseline. Sirve para describir el estado de la red "
            "como referencia, pero no incluye una captura activa de serial ni de trafico PCAP."
        )
    else:
        pieces = []
        if operation_mode == "telemetria_collar":
            pieces.append("el bloque corresponde a telemetria de collar")
        elif operation_mode == "ordeno_completo":
            pieces.append("el bloque corresponde a ordeño completo")
        if serial.get("available", False):
            pieces.append("hubo lectura del canal serial de la maquina de ordeno")
        if antenna_udp.get("available", False):
            pieces.append("hubo registro textual del canal de antena")
        if pcap.get("file_detected", False):
            pieces.append("hubo captura de trafico PCAP")
        if etl_path:
            pieces.append("la captura vino acompanada por un archivo ETL historico")
        if not pieces:
            pieces.append("no se detectaron artefactos activos aparte del baseline")
        situation_text = "En esta muestra " + ", ".join(pieces) + "."

    baseline_text = (
        f"La red base se observo con latencia media de {_format_value(baseline.get('lat_media'))} ms, "
        f"jitter de {_format_value(baseline.get('jitter_ms'))} ms y "
        f"{baseline.get('nodos_totales', 0)} nodos ARP detectados."
    )

    serial_text = (
        "No hubo datos seriales en esta muestra."
        if not serial.get("available", False)
        else
        f"El canal serial aporto {serial.get('total_frames', serial.get('total_events', 0))} frames reconstruidos. "
        f"Se detectaron {serial.get('cow_batch_count', 0)} tandas crudas, {serial.get('operational_batch_count', 0)} tandas operativas estimadas y {serial.get('cow_event_count', 0)} eventos de vaca, "
        f"{serial.get('cow_missing_rfid_count', 0)} sin identificacion valida de tag de collar y "
        f"{serial.get('total_flow_samples', 0)} muestras de flujo E4."
    )
    if operation_mode == "telemetria_collar" and not serial.get("available", False):
        serial_text = "En este bloque no se esperaba serial de ordeño completo; la lectura principal es la de antena/collar."

    antenna_text = (
        "No hubo archivo antena_udp.txt en esta muestra."
        if not antenna_udp.get("available", False)
        else
        f"El archivo antena_udp.txt aporto {antenna_udp.get('total_events', 0)} eventos y "
        f"{antenna_udp.get('signature_count', 0)} firmas 56 D1 00."
    )

    pcap_text = (
        "No hubo archivo PCAP en esta muestra."
        if not pcap.get("file_detected", False)
        else
        f"Se detecto un archivo PCAP con {general.get('total_packets', 0)} paquetes observados. "
        f"El trafico presento {_format_value(general.get('multicast_pct'), 2)}% de multicast y "
        f"{_format_value(general.get('broadcast_pct'), 2)}% de broadcast. "
        f"Nota de parseo: {pcap.get('parse_error', 'Sin novedades') or 'Sin novedades'}"
    )

    telemetry_text = (
        "No hubo telemetria de antena observable en el puerto objetivo."
        if not pcap.get("available", False)
        else
        f"En el puerto objetivo se observaron {telemetry.get('telemetry_packets', 0)} paquetes, "
        f"{telemetry.get('udp_event_count', 0)} eventos UDP y "
        f"{telemetry.get('signature_count', 0)} firmas 56 D1 00."
    )

    if operation_mode == "telemetria_collar":
        correlation_text = (
            "Este bloque corresponde a telemetria de collar. Se usa para estudiar antena, collares y red, "
            "no para reconstruir tiempos completos de ordeño."
        )
    else:
        correlation_text = (
            f"No fue posible hacer correlacion temporal directa; para ello se requiere evidencia serial y PCAP simultanea en una ventana de +/- {window_ms} ms."
            if not (serial.get("available", False) and pcap.get("available", False))
            else
            f"Se intento correlacion temporal con ventana de +/- {window_ms} ms y se lograron "
            f"{correlation.get('matched_events', 0)} coincidencias entre serial y red. "
            f"El desfase medio observado fue de {_format_value(correlation.get('desfase_medio_ms'))} ms."
        )

    if field_validation.get("available", False):
        field_validation_text = (
            f"Se cuenta con validacion de campo para este bloque. En la ventana observada se anotaron "
            f"{field_validation.get('observed_cows_count', 0)} vacas, "
            f"{field_validation.get('quick_id_count', 0)} identificaciones rapidas del tag Allflex y "
            f"{field_validation.get('photocell_issue_count', 0)} casos con problema de fotocelda."
        )
        field_validation_text_2 = (
            f"El parser reconstruyo {field_validation.get('parser_event_count', 0)} eventos de vaca; "
            f"la diferencia frente al conteo de campo fue {field_validation.get('parser_event_delta_vs_field', 0)}. "
            f"Tambien se observaron {field_validation.get('controller_stale_read_count', 0)} casos donde el controller retuvo la lectura, "
            f"y {field_validation.get('controller_celo_count', 0)}/{field_validation.get('controller_e56_count', 0)}/{field_validation.get('controller_e59_count', 0)} avisos CELO/E56/E59."
        )
    else:
        field_validation_text = "No hay validacion de campo asociada a esta sesion."
        field_validation_text_2 = (
            f"Motivo registrado: {field_validation.get('reason', 'sin_validacion_de_campo_para_la_sesion') or 'sin_validacion_de_campo_para_la_sesion'}."
        )

    return f"""
INFORME EN LENGUAJE CLARO
=========================

Muestra: {sample_name}
Tipo de sesion: {"Baseline-only" if is_baseline_only else "Captura"}
Bloque operativo: {block_label or 'Sin bloque'}
Modo operativo: {operation_mode_label}
Rol analitico en Objetivo 1: {obj1_role}
Confianza de uso para Objetivo 1: {obj1_confidence}

1. Que se encontro en esta muestra
- {situation_text}
- Baseline asociado: {baseline.get('baseline_dir', '') or 'No asociado'}
- Archivo serial: {serial.get('source_path', 'No detectado') or 'No detectado'}
- Archivo antena_udp: {antenna_udp.get('source_path', 'No detectado') or 'No detectado'}
- Archivo ETL: {etl_path or 'No detectado'}
- Archivo PCAP: {pcap.get('source_path', 'No detectado') or 'No detectado'}

2. Lectura simple del estado de red
- {baseline_text}

3. Lectura simple del canal serial
- {serial_text}

4. Lectura simple del canal de antena
- {antenna_text}

5. Lectura simple del trafico capturado
- {pcap_text}
- {telemetry_text}

6. Correlacion entre serial y red
- {correlation_text}

7. Validacion de campo
- {field_validation_text}
- {field_validation_text_2}

8. Resumen de alertas en lenguaje claro
- Alertas totales: {alert_summary.get('total', 0)}
- Criticas: {alert_summary.get('by_severity', {}).get('Critica', 0)}
- Altas: {alert_summary.get('by_severity', {}).get('Alta', 0)}
- Medias: {alert_summary.get('by_severity', {}).get('Media', 0)}
- Bajas: {alert_summary.get('by_severity', {}).get('Baja', 0)}
- Info: {alert_summary.get('by_severity', {}).get('Info', 0)}

9. Alertas mas importantes para una persona no tecnica
Alertas de red general:
{_format_human_alert_lines(alerts.get('pcap_general', []))}

Alertas del canal de telemetria:
{_format_human_alert_lines(alerts.get('telemetry_6001', []))}

Alertas del canal serial:
{_format_human_alert_lines(alerts.get('serial', []))}

10. Conclusiones rapidas
- Este informe esta pensado para que una persona no tecnica pueda entender que se observo en la muestra.
- Las alertas no siempre significan ataque; a veces describen ruido, inestabilidad o condiciones que afectan la calidad de lectura.
- Si una alerta aparece como critica o alta, conviene revisarla primero porque puede afectar seguridad, continuidad o interpretacion de la evidencia.
""".strip()


def generate_reports(
    sample_name: str,
    baseline: dict,
    serial: dict,
    antenna_udp: dict,
    pcap: dict,
    correlation: dict,
    alerts: dict,
    window_ms: int,
    output_dir: Path,
    etl_path: str = "",
    operation_mode: str = "indeterminado",
    block_label: str = "",
    field_validation: dict | None = None,
) -> tuple[Path, Path]:
    technical_text = build_technical_report(
        sample_name,
        baseline,
        serial,
        antenna_udp,
        pcap,
        correlation,
        alerts,
        window_ms,
        etl_path=etl_path,
        operation_mode=operation_mode,
        block_label=block_label,
        field_validation=field_validation,
    )
    human_text = build_human_report(
        sample_name,
        baseline,
        serial,
        antenna_udp,
        pcap,
        correlation,
        alerts,
        window_ms,
        etl_path=etl_path,
        operation_mode=operation_mode,
        block_label=block_label,
        field_validation=field_validation,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    technical_path = output_dir / f"{sample_name}_technical_report.txt"
    human_path = output_dir / f"{sample_name}_human_report.txt"
    technical_path.write_text(technical_text, encoding="utf-8")
    human_path.write_text(human_text, encoding="utf-8")
    return technical_path, human_path
