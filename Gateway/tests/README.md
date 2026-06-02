# Suite de pruebas del Gateway FincaDiag

Scripts de validacion automatica del gateway perimetral, orientados a garantizar la integridad de datos antes del contraste estadistico del Objetivo 4.

## Pruebas incluidas

| # | Prueba | Windows | Raspberry Pi | Objetivo |
|---|--------|---------|--------------|----------|
| 1 | **Validacion de contrato JSON** | `validate_schema.bat` | `validate_schema_pi.sh` | Verifica que la salida del gateway cumple el contrato minimo (batch_name, message_count, counts_by_event_type, cow_event fields, tipos requeridos). |
| 2 | **TLS handshake** | — | `tls_handshake_pi.sh` | Confirma que el broker rechaza TLS 1.2 y acepta TLS 1.3 con certificados validos. |
| 3 | **Resiliencia (broker caido)** | — | `resilience_spool_pi.sh` | Verifica spooling de mensajes cuando Mosquitto esta detenido y vaciado al recuperarse. |
| 4 | **Suscribirse y validar** | — | `subscribe_validate_pi.sh` | Suscribe al broker, publica desde gateway, valida que los mensajes llegan con topic y JSON correctos. |
| 5 | **Idempotencia** | `idempotency.bat` | `idempotency_pi.sh` | Correr dry-run 2 veces; los checksums MD5 de la salida deben ser identicos. |
| 6 | **Metricas Objetivo 4** | `validate_objective4.bat` | `validate_objective4_pi.sh` | Compara η (eta) del motor (`correlation_summary.json`) contra η reportado por el gateway. Valida que `serial_events > 0`. |

## Uso rapido

### Windows (3 pruebas disponibles)

Con una sesion procesada de ejemplo:

```batch
run_all_tests.bat data\processed\visits\Visita_15_05_2026\sesiones\TOMA_PM__1PM__Captura_20260515_130005
```

O individualmente:

```batch
validate_schema.bat    <sesion>
idempotency.bat        <sesion>
validate_objective4.bat <sesion>
```

### Raspberry Pi (6 pruebas)

```bash
chmod +x *.sh
./run_all_tests_pi.sh /var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005
```

## Notas

- Las pruebas 2, 3 y 4 requieren Mosquitto activo en la Raspberry Pi con TLS en puerto 8883.
- Las pruebas de resiliencia (3) paran y levantan Mosquitto; requieren permisos `sudo`.
- Todas las pruebas limpian `data/gateway/published/` antes y despues.
- **No se han corrido aun** — fueron preparados para ejecutarse como parte de la validacion del Objetivo 4.
