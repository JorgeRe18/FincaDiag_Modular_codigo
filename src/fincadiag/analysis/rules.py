def build_priority_rules(target_port: int, window_ms: int) -> list[dict]:
    return [
        {
            "prioridad": "Alta",
            "filtro": f"TCP o UDP puerto {target_port}",
            "justificacion": "Canal principal de telemetria entre antena y gateway.",
        },
        {
            "prioridad": "Alta",
            "filtro": "Payload contiene 56 D1 00",
            "justificacion": "Firma candidata de red para eventos relevantes.",
        },
        {
            "prioridad": "Alta",
            "filtro": f"Eventos seriales FC o FE correlacionados en +/- {window_ms} ms",
            "justificacion": "Marcadores temporales observables para sincronizacion.",
        },
        {
            "prioridad": "Media",
            "filtro": "Multicast cercano a eventos correlacionados",
            "justificacion": "Posible causa de aumento del desfase temporal.",
        },
        {
            "prioridad": "Baja",
            "filtro": "Broadcast y ARP fuera de la ventana de interes",
            "justificacion": "Ruido operativo secundario.",
        },
    ]
