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


def _build_obj1_evidence_text(
    operation_mode: str,
    serial: dict,
    pcap: dict,
    correlation: dict,
    field_validation: dict,
) -> str:
    if operation_mode == "baseline":
        return "La muestra sirve principalmente para fijar o contrastar la linea base de red del Objetivo 1 mediante latencia, jitter y nodos observados."
    if operation_mode == "telemetria_collar":
        return "La muestra sirve principalmente para caracterizar el dominio biotico, la exposicion UDP/6001 y la continuidad observable del canal de collar dentro del Objetivo 1."
    matched_events = int(correlation.get("matched_events", 0) or 0)
    if matched_events > 0:
        return "La muestra aporta evidencia fuerte para el Objetivo 1 porque combina semantica serial y correlacion temporal serial-red con soporte para eta preliminar."
    if field_validation.get("available", False):
        return "La muestra aporta evidencia media para el Objetivo 1 porque permite contrastar la reconstruccion del motor contra observacion de campo aunque la correlacion serial-red siga siendo parcial."
    if serial.get("available", False) and pcap.get("available", False):
        return "La muestra aporta evidencia util para el Objetivo 1 porque combina serial y PCAP, aunque todavia no cierre una correlacion temporal defendible."
    return "La muestra aporta evidencia contextual para el Objetivo 1, pero su fuerza probatoria es limitada frente a sesiones con simultaneidad mas completa."


def _build_defendibility_text(
    serial: dict,
    pcap: dict,
    correlation: dict,
    field_validation: dict,
) -> str:
    matched_events = int(correlation.get("matched_events", 0) or 0)
    parser_conf = float(serial.get("parser_confidence_average", 0.0) or 0.0)
    if matched_events > 0 and field_validation.get("available", False):
        return "Defendibilidad alta: existe soporte cruzado entre reconstruccion operativa, red y validacion de campo."
    if matched_events > 0:
        return "Defendibilidad media-alta: existe correlacion serial-red, aunque la validacion de campo no acompana o no esta disponible."
    if field_validation.get("available", False) and parser_conf >= 0.45:
        return "Defendibilidad media: la muestra es util para contraste con campo y lectura semantica, aunque no cierre todavia la cadena serial-red completa."
    if serial.get("available", False) or pcap.get("available", False):
        return "Defendibilidad media-baja: la muestra sirve para caracterizacion forense, firmas y contexto operativo, pero no para una conclusion fuerte por si sola."
    return "Defendibilidad baja: la muestra funciona solo como apoyo contextual o de linea base."


def _build_limitations_text(
    operation_mode: str,
    serial: dict,
    pcap: dict,
    correlation: dict,
    field_validation: dict,
) -> str:
    limitations = []
    if operation_mode == "telemetria_collar":
        limitations.append("No corresponde usar esta muestra para reconstruir el ordeño completo ni para reclamar eta directa.")
    if not serial.get("available", False) and operation_mode != "baseline":
        limitations.append("No hubo evidencia serial util para reconstruir semantica completa del ordeño.")
    if not pcap.get("available", False) and not pcap.get("file_detected", False):
        limitations.append("No hubo PCAP parseado suficiente para sostener cadena de custodia de red.")
    if int(correlation.get("matched_events", 0) or 0) == 0 and operation_mode == "ordeno_completo":
        limitations.append("No se lograron coincidencias serial-red defendibles dentro de la ventana temporal configurada.")
    if not field_validation.get("available", False):
        limitations.append("No hay contraste de campo asociado para reforzar la interpretacion semantica de esta sesion.")
    if int(serial.get("suppressed_retained_state_event_count", 0) or 0) > 0:
        limitations.append(
            f"El parser detecto y suprimio {int(serial.get('suppressed_retained_state_event_count', 0) or 0)} eventos compatibles con estado retenido del controller."
        )
    if not limitations:
        limitations.append("No se observan limitaciones dominantes fuera de las propias del muestreo instrumental de esta sesion.")
    return "\n".join(f"- {line}" for line in limitations)


def _build_obj3_bridge_text(
    operation_mode: str,
    serial: dict,
    pcap: dict,
    correlation: dict,
    field_validation: dict,
) -> str:
    lines = []
    if serial.get("available", False):
        lines.append(
            f"La muestra deja listo para Objetivo 3 un resumen de parser con confianza promedio {_format_value(serial.get('parser_confidence_average'), 3)}, {serial.get('suppressed_noise_event_count', 0)} microeventos suprimidos y {serial.get('suppressed_retained_state_event_count', 0)} eventos retenidos depurados."
        )
        lines.append(
            f"Tambien permite publicar identidad operativa en tres estados: confirmada={serial.get('identity_confirmed_count', 0)}, probable={serial.get('identity_probable_count', 0)} y no confirmada={serial.get('identity_unconfirmed_count', 0)}."
        )
    if pcap.get("available", False):
        lines.append("La presencia de PCAP parseado ayuda a sostener una politica minima de red y a justificar sincronizacion/control de publicacion en la pasarela.")
    if int(correlation.get("matched_events", 0) or 0) > 0:
        lines.append("La correlacion serial-red observada en esta muestra sirve como base para congelar mensajes de sincronia del gateway con mejor soporte temporal.")
    if field_validation.get("available", False):
        lines.append("El contraste con campo abre la puerta a que la pasarela exponga no solo eventos, sino tambien confianza semantica y estado de identidad operativa.")
    if operation_mode == "baseline":
        lines.append("Como baseline, esta muestra no empuja semantica fina del gateway, pero si fija el estado de red contra el cual luego se comparara la instrumentacion perimetral.")
    if not lines:
        lines.append("La muestra todavia no deja insumos fuertes para Objetivo 3; conviene priorizar sesiones con serial, PCAP y contraste adicional.")
    return "\n".join(f"- {line}" for line in lines)


def _build_executive_takeaway(
    operation_mode: str,
    serial: dict,
    pcap: dict,
    correlation: dict,
    field_validation: dict,
) -> str:
    if operation_mode == "baseline":
        return "Muestra util como referencia de linea base, pero no como evidencia fuerte de sincronia operativa."
    if operation_mode == "telemetria_collar":
        return "Muestra util para caracterizar el canal de collar y su exposicion de red, no para cerrar por si sola el fenomeno de ordeño completo."
    if int(correlation.get("matched_events", 0) or 0) > 0 and field_validation.get("available", False):
        return "Muestra prioritaria: combina lectura operativa, soporte temporal y contraste con campo."
    if int(correlation.get("matched_events", 0) or 0) > 0:
        return "Muestra fuerte para sincronia serial-red, aunque todavia no quede reforzada con contraste de campo."
    if serial.get("available", False) and pcap.get("available", False):
        return "Muestra de transicion: ya permite explicar el problema, pero aun no cierra toda la defendibilidad esperada."
    return "Muestra auxiliar: sirve mas para caracterizacion o contexto que para una conclusion central."


def build_gateway_expectations(
    sample_name: str,
    baseline: dict,
    serial: dict,
    antenna_udp: dict,
    pcap: dict,
    correlation: dict,
    alerts: dict,
    window_ms: int,
    operation_mode: str = "indeterminado",
    block_label: str = "",
    field_validation: dict | None = None,
) -> dict:
    field_validation = field_validation or {}
    obj1_role, obj1_confidence = _build_obj1_role_text(operation_mode, serial, antenna_udp, pcap, correlation, field_validation)
    obj1_evidence = _build_obj1_evidence_text(operation_mode, serial, pcap, correlation, field_validation)
    defendibility_text = _build_defendibility_text(serial, pcap, correlation, field_validation)
    executive_takeaway = _build_executive_takeaway(operation_mode, serial, pcap, correlation, field_validation)

    matched_events = int(correlation.get("matched_events", 0) or 0)
    parser_confidence_average = float(serial.get("parser_confidence_average", 0.0) or 0.0)
    expected_event_types = ["session_summary", "baseline_snapshot", "alerts_summary"]
    if serial.get("available", False):
        expected_event_types.extend(["parser_summary", "cow_event"])
    if antenna_udp.get("available", False):
        expected_event_types.append("collar_summary")
    if correlation.get("serial_events", 0) or correlation.get("network_events", 0) or matched_events:
        expected_event_types.append("correlation_summary")
    if field_validation.get("available", False):
        expected_event_types.append("field_validation_summary")

    if matched_events > 0 and field_validation.get("available", False):
        offline_readiness = "strong"
    elif serial.get("available", False) and pcap.get("available", False):
        offline_readiness = "transitional"
    elif serial.get("available", False) or antenna_udp.get("available", False) or pcap.get("file_detected", False):
        offline_readiness = "contextual"
    else:
        offline_readiness = "weak"

    return {
        "sample_name": sample_name,
        "block_label": block_label,
        "operation_mode": operation_mode,
        "objective_1": {
            "role": obj1_role,
            "confidence": obj1_confidence,
            "evidence_statement": obj1_evidence,
            "defendibility": defendibility_text,
            "executive_takeaway": executive_takeaway,
        },
        "offline_gateway_validation": {
            "readiness": offline_readiness,
            "window_ms": window_ms,
            "should_preserve_operation_mode": True,
            "should_preserve_identity_semantics": bool(serial.get("available", False)),
            "should_preserve_parser_confidence": bool(serial.get("available", False)),
            "should_preserve_suppressed_microevents": bool(serial.get("available", False)),
            "should_preserve_field_context": bool(field_validation.get("available", False)),
            "should_claim_eta_direct": matched_events > 0,
            "should_claim_full_milking_reconstruction": operation_mode == "ordeno_completo" and serial.get("available", False),
            "expected_event_types": expected_event_types,
        },
        "expected_metrics": {
            "parser_confidence_average": round(parser_confidence_average, 3),
            "suppressed_microevent_count": int(serial.get("suppressed_noise_event_count", 0) or 0),
            "suppressed_retained_state_count": int(serial.get("suppressed_retained_state_event_count", 0) or 0),
            "identity_confirmed_count": int(serial.get("identity_confirmed_count", 0) or 0),
            "identity_probable_count": int(serial.get("identity_probable_count", 0) or 0),
            "identity_unconfirmed_count": int(serial.get("identity_unconfirmed_count", 0) or 0),
            "matched_events": matched_events,
            "field_observed_cows_count": int(field_validation.get("observed_cows_count", 0) or 0),
            "alerts_total": int(alerts.get("summary", {}).get("total", 0) or 0),
        },
        "expected_gateway_semantics": {
            "identity_states_expected": [
                state
                for state, count in (
                    ("confirmed", int(serial.get("identity_confirmed_count", 0) or 0)),
                    ("probable", int(serial.get("identity_probable_count", 0) or 0)),
                    ("unconfirmed", int(serial.get("identity_unconfirmed_count", 0) or 0)),
                )
                if count > 0
            ],
            "correlation_support": "direct" if matched_events > 0 else "contextual",
            "field_validation_available": bool(field_validation.get("available", False)),
            "network_policy_evidence_available": bool(pcap.get("available", False)),
        },
        "notes": [
            "Este archivo no reemplaza el informe tecnico; resume expectativas estructuradas para validar el gateway offline.",
            "La validacion offline debe comparar estas expectativas contra los mensajes normalizados producidos por la misma sesion procesada.",
        ],
    }


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
    baseline_pre_label = "No aplica (muestra baseline)" if is_baseline_only else "No asociado"
    baseline_post_label = "No aplica (muestra baseline)" if is_baseline_only else "No asociado"
    field_validation = field_validation or {}
    obj1_role, obj1_confidence = _build_obj1_role_text(operation_mode, serial, antenna_udp, pcap, correlation, field_validation)
    obj1_evidence = _build_obj1_evidence_text(operation_mode, serial, pcap, correlation, field_validation)
    defendibility_text = _build_defendibility_text(serial, pcap, correlation, field_validation)
    limitations_text = _build_limitations_text(operation_mode, serial, pcap, correlation, field_validation)
    obj3_bridge_text = _build_obj3_bridge_text(operation_mode, serial, pcap, correlation, field_validation)
    executive_takeaway = _build_executive_takeaway(operation_mode, serial, pcap, correlation, field_validation)
    operation_mode_label = {
        "ordeno_completo": "Ordeño completo",
        "telemetria_collar": "Telemetría de collar",
        "baseline": "Baseline",
    }.get(operation_mode, operation_mode or "Indeterminado")
    files_block = f"""- Carpeta de captura: {baseline.get('capture_dir', '') or 'N/D'}
- Baseline pre: {baseline.get('baseline_pre', '') or baseline_pre_label}
- Baseline post: {baseline.get('baseline_post', '') or baseline_post_label}
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
- Microeventos suprimidos como ruido: {serial.get('suppressed_noise_event_count', 0)}
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
- Casos de calostro / "Prob CALO": {field_validation.get('calostrum_count', 0)}
- Eventos del controller CELO/E56/E59: {field_validation.get('controller_celo_count', 0)} / {field_validation.get('controller_e56_count', 0)} / {field_validation.get('controller_e59_count', 0)}
- Codigos observados del controller: {", ".join(field_validation.get('controller_error_codes_present', [])) or 'Ninguno'}
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

1. Lectura ejecutiva de la muestra
- Sintesis rapida: {executive_takeaway}
- Aporte principal al indicador del Objetivo 1: {obj1_evidence}
- Defendibilidad actual: {defendibility_text}

2. Limitaciones que conviene declarar
{limitations_text}

3. Apertura hacia Objetivo 3 / gateway
{obj3_bridge_text}

4. Archivos de entrada detectados
{files_block}

5. Baseline de red
- IP local: {baseline.get('ip', '') or 'N/D'}
- Gateway: {baseline.get('gateway', '') or 'N/D'}
- Latencia media: {_format_value(baseline.get('lat_media'))} ms
- Jitter: {_format_value(baseline.get('jitter_ms'))} ms
- Perdida: {_format_value(baseline.get('packet_loss'), 2)}%
- Nodos ARP: {baseline.get('nodos_totales', 0)}
- Nodos dinamicos: {baseline.get('nodos_dinamicos', 0)}
- Estrategia de baseline usada: {baseline.get('baseline_strategy', 'none')}
- Baseline previo: {pre.get('dir') or baseline_pre_label}
- Baseline posterior: {post.get('dir') or baseline_post_label}
- Delta latencia pre-post: {_format_value(transition.get('lat_media_delta'))} ms
- Delta jitter pre-post: {_format_value(transition.get('jitter_delta'))} ms
- Delta nodos pre-post: {_format_value(transition.get('nodos_delta'), 0)}

6. Serial
{serial_block}

7. Registro de antena en texto (antena_udp.txt)
{antenna_udp_block}

8. PCAP general
{pcap_general_block}

9. Telemetria de antena / puerto objetivo
{telemetry_block}

10. Correlacion serial <-> telemetria
{correlation_block}

11. Validacion de campo
{field_validation_block}

12. Resumen de alertas para seguimiento
- Alertas totales: {alert_summary.get('total', 0)}
- Criticas: {severity_counts.get('Critica', 0)}
- Altas: {severity_counts.get('Alta', 0)}
- Medias: {severity_counts.get('Media', 0)}
- Bajas: {severity_counts.get('Baja', 0)}
- Info: {severity_counts.get('Info', 0)}

13. Guia breve para leer la severidad
- Critica: la condicion puede comprometer de forma directa la seguridad del segmento o volver poco confiable la interpretacion tecnica de la muestra.
- Alta: afecta la calidad analitica, la seguridad del entorno o la sincronizacion de la telemetria y conviene revisarla con prioridad.
- Media: introduce degradacion o incertidumbre relevante, aunque por si sola no invalida toda la muestra.
- Baja: describe una condicion secundaria o de contexto con impacto acotado.
- Info: es un hallazgo descriptivo o de apoyo y no representa por si mismo una falla o incidente.

14. Alertas baseline
{_format_alert_lines(alerts.get('baseline', []))}

15. Alertas serial
{_format_alert_lines(alerts.get('serial', []))}

16. Alertas PCAP general
{_format_alert_lines(alerts.get('pcap_general', []))}

17. Alertas telemetria 6001
{_format_alert_lines(alerts.get('telemetry_6001', []))}

18. Alertas de correlacion
{_format_alert_lines(alerts.get('correlation', []))}

19. Notas de lectura e interpretacion
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
    obj1_evidence = _build_obj1_evidence_text(operation_mode, serial, pcap, correlation, field_validation)
    defendibility_text = _build_defendibility_text(serial, pcap, correlation, field_validation)
    limitations_text = _build_limitations_text(operation_mode, serial, pcap, correlation, field_validation)
    obj3_bridge_text = _build_obj3_bridge_text(operation_mode, serial, pcap, correlation, field_validation)
    executive_takeaway = _build_executive_takeaway(operation_mode, serial, pcap, correlation, field_validation)
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
        f"{serial.get('total_flow_samples', 0)} muestras de flujo E4. "
        f"El parser suprimio {serial.get('suppressed_noise_event_count', 0)} microeventos de ruido."
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
            f", {field_validation.get('calostrum_count', 0)} casos de calostro/Prob CALO "
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

1. Lectura ejecutiva
- {executive_takeaway}
- Aporte al indicador del Objetivo 1: {obj1_evidence}
- Nivel de defendibilidad: {defendibility_text}

2. Que se encontro en esta muestra
- {situation_text}
- Baseline asociado: {baseline.get('baseline_dir', '') or 'No asociado'}
- Archivo serial: {serial.get('source_path', 'No detectado') or 'No detectado'}
- Archivo antena_udp: {antenna_udp.get('source_path', 'No detectado') or 'No detectado'}
- Archivo ETL: {etl_path or 'No detectado'}
- Archivo PCAP: {pcap.get('source_path', 'No detectado') or 'No detectado'}

3. Lectura simple del estado de red
- {baseline_text}

4. Lectura simple del canal serial
- {serial_text}

5. Lectura simple del canal de antena
- {antenna_text}

6. Lectura simple del trafico capturado
- {pcap_text}
- {telemetry_text}

7. Correlacion entre serial y red
- {correlation_text}

8. Validacion de campo
- {field_validation_text}
- {field_validation_text_2}

9. Limitaciones de esta muestra
{limitations_text}

10. Lo que esta muestra abre hacia Objetivo 3
{obj3_bridge_text}

11. Resumen de alertas en lenguaje claro
- Alertas totales: {alert_summary.get('total', 0)}
- Criticas: {alert_summary.get('by_severity', {}).get('Critica', 0)}
- Altas: {alert_summary.get('by_severity', {}).get('Alta', 0)}
- Medias: {alert_summary.get('by_severity', {}).get('Media', 0)}
- Bajas: {alert_summary.get('by_severity', {}).get('Baja', 0)}
- Info: {alert_summary.get('by_severity', {}).get('Info', 0)}

12. Alertas mas importantes para una persona no tecnica
Alertas de red general:
{_format_human_alert_lines(alerts.get('pcap_general', []))}

Alertas del canal de telemetria:
{_format_human_alert_lines(alerts.get('telemetry_6001', []))}

Alertas del canal serial:
{_format_human_alert_lines(alerts.get('serial', []))}

13. Conclusiones rapidas
- Este informe esta pensado para que una persona no tecnica pueda entender que se observo en la muestra.
- Las alertas no siempre significan ataque; a veces describen ruido, inestabilidad o condiciones que afectan la calidad de lectura.
- Si una alerta aparece como critica o alta, conviene revisarla primero porque puede afectar seguridad, continuidad o interpretacion de la evidencia.
""".strip()


def _format_top_alerts_section(top_alerts_detail: list[dict] | None) -> str:
    """Construye la sección textual de alertas detalladas con evidencia.

    Cada item de top_alerts_detail debe tener:
        alert_name, severity, layer, n_cases, n_visits, n_sessions,
        impact, recommendation, sample_evidence (list[dict] con keys
        visit_name, sample_name, evidence).
    """
    if not top_alerts_detail:
        return "(No se recopilaron detalles individuales de alertas para este lote.)"
    lines = []
    for idx, item in enumerate(top_alerts_detail, start=1):
        lines.append(
            f"{idx}. [{item.get('severity', '?')}] {item.get('alert_name', '?')} "
            f"({item.get('n_cases', 0)} caso(s) en "
            f"{item.get('n_visits', 0)} visita(s) y "
            f"{item.get('n_sessions', 0)} sesión(es) — capa {item.get('layer', '?')})"
        )
        if item.get("impact"):
            lines.append(f"   Impacto: {item['impact']}")
        if item.get("recommendation"):
            lines.append(f"   Recomendación: {item['recommendation']}")
        sample_evidence = item.get("sample_evidence") or []
        if sample_evidence:
            lines.append("   Casos específicos (evidencia):")
            for ev in sample_evidence[:5]:
                visit = ev.get("visit_name", "")
                sample = ev.get("sample_name", "")
                evidence = ev.get("evidence", "")
                lines.append(f"     - {visit} / {sample}: {evidence}")
            if len(sample_evidence) > 5:
                lines.append(f"     ... y {len(sample_evidence) - 5} caso(s) adicional(es).")
        lines.append("")
    return "\n".join(lines).rstrip()


def build_executive_summary(
    batch_name: str,
    total_visits: int,
    total_sessions: int,
    sessions_with_pcap: int,
    sessions_with_serial: int,
    sessions_with_correlation: int,
    critical_alerts: int,
    high_alerts: int,
    total_alerts: int,
    avg_latency: float,
    avg_eta: float,
    sessions_with_field_validation: int,
    processing_duration: str,
    failed_sessions: int = 0,
    top_alerts_detail: list[dict] | None = None,
    total_input_size: str = "N/D",
    avg_multicast: float = 0.0,
    avg_offset: float = 0.0,
    avg_jitter_baseline: float = 0.0,
    avg_heartbeat_coverage: float = 0.0,
    sessions_useful_for_baseline: int = 0,
    sessions_useful_for_serial: int = 0,
    sessions_useful_for_collar: int = 0,
    sessions_useful_for_direct_eta: int = 0,
    obj1_supports: dict | None = None,
    gateway_ready: bool = False,
    visit_rows: list[dict] | None = None,
) -> str:
    """Informe ejecutivo orientado al Objetivo 1 (caracterizacion forense).
    Estructura: 8 secciones (mapa, resumen, Obj.1, hallazgos, metricas, distribucion, limitaciones, conclusiones).
    """
    from datetime import datetime as _dt
    
    obj1_supports = obj1_supports or {}
    visit_rows = visit_rows or []
    top_alerts_detail = top_alerts_detail or []
    generated_at = _dt.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Sección 3: top alertas con referencia al dashboard
    def _top_alerts_block() -> str:
        if not top_alerts_detail:
            return "  (sin alertas registradas en este lote)"
        out = []
        for i, t in enumerate(top_alerts_detail[:10], 1):
            out.append(f"{i}. [{t['severity']}] {t['alert_name']}")
            out.append(
                f"   {t['n_cases']} caso(s) en {t['n_visits']} visita(s) y "
                f"{t['n_sessions']} sesion(es)  ·  capa {t['layer']}"
            )
            out.append(f"   Impacto: {t['impact']}")
            out.append(f"   Recomendacion: {t['recommendation']}")
            if t.get("sample_evidence"):
                ev = (t["sample_evidence"][0].get("evidence", "") or "")[:200]
                if ev:
                    out.append(f"   Ejemplo de evidencia: {ev}")
            out.append(f"   >> Dashboard: Por visita -> {t['alert_name']!r}")
            out.append("")
        return "\n".join(out)
    
    # Sección 5: top visitas con más problemas
    def _visit_distribution_block() -> str:
        if not visit_rows:
            return "  (sin datos de visitas)"
        scored = []
        for r in visit_rows:
            try:
                crit = int(r.get("total_alertas_criticas", 0) or 0)
                high = int(r.get("total_alertas_altas", 0) or 0)
                eta = float(r.get("avg_eta_extraccion") or 0.0)
                scored.append((r.get("visit_name", ""), crit, high, eta, crit + high))
            except (ValueError, TypeError):
                continue
        scored.sort(key=lambda x: x[4], reverse=True)
        top = scored[:8]
        lines = [f"{'Visita':<25} {'Crit':>6} {'Alta':>6} {'Eta %':>8}"]
        for name, crit, high, eta, _ in top:
            short = str(name).replace("Visita_", "")
            lines.append(f"{short:<25} {crit:>6} {high:>6} {eta:>8.2f}")
        return "\n".join(lines)
    
    # Sección 2: capacidades validadas
    def _capability(label: str, key: str) -> str:
        flag = "si" if obj1_supports.get(key) else "no"
        return f"  - {label:<35} {flag}"
    
    success_rate = ((total_sessions - failed_sessions) / total_sessions * 100) if total_sessions > 0 else 0
    
    return f"""
================================================================================
INFORME EJECUTIVO - OBJETIVO 1: CARACTERIZACION FORENSE DEL SISTEMA
Sistema actual de monitoreo IoT - Finca La Esmeralda
================================================================================

Lote analizado:              {batch_name}
Generado:                    {generated_at}
Duracion del procesamiento:  {processing_duration}
Datos fuente procesados:     {total_input_size}
Visitas: {total_visits}  ·  Sesiones: {total_sessions}  ·  Tasa de exito: {success_rate:.1f}%

--------------------------------------------------------------------------------
1. RESUMEN EJECUTIVO
--------------------------------------------------------------------------------
Durante {total_visits} visitas se procesaron {total_sessions} sesiones de operacion.
El motor detecto {total_alerts} alertas en total: {critical_alerts} criticas y {high_alerts} altas.
La eficiencia de correlacion serial-red promedio fue {avg_eta:.1f}%.
Solo {sessions_with_field_validation} sesion(es) cuentan con validacion presencial directa.

Hallazgo central: el segmento de red presenta condiciones recurrentes
compatibles con ARP spoofing/inestabilidad ARP y trafico broadcast/multicast
elevado, factores que degradan la sincronia entre el bus serial y la red.

--------------------------------------------------------------------------------
2. CARACTERIZACION FORENSE (OBJETIVO 1)
--------------------------------------------------------------------------------
Cobertura del instrumento:
  - Sesiones utiles para baseline de red:          {sessions_useful_for_baseline}
  - Sesiones utiles para firmas seriales:          {sessions_useful_for_serial}
  - Sesiones utiles para telemetria de collar:     {sessions_useful_for_collar}
  - Sesiones con eta directa estimable:            {sessions_useful_for_direct_eta}
  - Sesiones con validacion de campo (presencial): {sessions_with_field_validation}

Capacidades validadas del Objetivo 1:
{_capability("Latencia/jitter baseline",        "supports_latency_jitter_baseline")}
{_capability("Caracterizacion firmas seriales", "supports_serial_signature_characterization")}
{_capability("Exposicion UDP de collar",        "supports_udp_exposure_characterization")}
{_capability("Estimacion directa de eta",       "supports_direct_eta_estimation")}
{_capability("Contraste con campo presencial",  "supports_field_contrast")}

Listo para gateway offline: {"si" if gateway_ready else "parcial"}

--------------------------------------------------------------------------------
3. HALLAZGOS CLAVE - TOP ALERTAS CON EVIDENCIA
--------------------------------------------------------------------------------
{_top_alerts_block()}

--------------------------------------------------------------------------------
4. METRICAS TECNICAS DEL LOTE
--------------------------------------------------------------------------------
  - Eficiencia de correlacion (eta promedio): {avg_eta:.2f} %
  - Latencia baseline promedio:               {avg_latency:.2f} ms
  - Multicast promedio:                       {avg_multicast:.2f} %
  - Desfase medio promedio:                   {avg_offset:.2f} ms
  - Jitter baseline promedio (Obj.1):         {avg_jitter_baseline:.2f} ms
  - Cobertura de heartbeat (Obj.1):           {avg_heartbeat_coverage:.2f} %

--------------------------------------------------------------------------------
5. DISTRIBUCION POR VISITA - VISITAS CON MAS PROBLEMAS
--------------------------------------------------------------------------------
{_visit_distribution_block()}

>> Ver desglose completo por visita en dashboard: Por visita.

--------------------------------------------------------------------------------
6. LIMITACIONES DEL INSTRUMENTO
--------------------------------------------------------------------------------
- Solo {sessions_useful_for_direct_eta}/{total_sessions} sesiones tienen evidencia simultanea para eta directa.
- Solo {sessions_with_field_validation} sesion(es) tienen validacion presencial; el resto se interpreta sin contraste.
- El motor caracteriza condiciones de red pero no decide; la atribucion de causalidad
  requiere lectura cruzada con baseline, PCAP y eventos seriales.
- Las firmas detectadas (ARP, broadcast, multicast) son indicios; no constituyen prueba
  de incidente activo de seguridad.

--------------------------------------------------------------------------------
7. CONCLUSIONES OBJETIVO 1
--------------------------------------------------------------------------------
- El sistema actual de monitoreo IoT presenta degradacion temporal recurrente
  (eta promedio {avg_eta:.1f}%, multicast {avg_multicast:.1f}%, desfase {avg_offset:.1f} ms).
- Hay condiciones de red repetidas (ARP, broadcast/multicast, salida a IP publica)
  que constituyen un perfil forense reproducible y caracterizable.
- La validacion de campo aun es escasa ({sessions_with_field_validation} sesion(es)); ampliarla refuerza el contraste.
- El instrumento esta listo para alimentar el gateway offline en las sesiones de referencia.

--------------------------------------------------------------------------------
8. ANEXOS
--------------------------------------------------------------------------------
- Inventario completo de visitas:  {batch_name}_visits.csv
- Inventario completo de sesiones: {batch_name}_sessions.csv
- Resumen Obj.1 detallado:         {batch_name}_obj1_summary.txt
- Perfiles Obj.1 por sesion:       {batch_name}_obj1_profiles.txt
- Informe tecnico completo:        {batch_name}_summary.txt
- Dashboard interactivo:           streamlit run src/fincadiag/dashboard/app.py
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
