# Diseno del motor serial operativo

Este documento fija el rediseño minimo del analisis serial para FincaDiag.
La idea central es simple: el archivo `serial_hex.txt` no debe tratarse como
un flujo uniforme. Antes de calcular metricas, el motor debe separar canales,
reconstruir fragmentos y recien despues identificar eventos operativos.

## Objetivo

Convertir `serial_hex.txt` en una fuente de eventos operativos trazables:

- cobertura real del bus durante la captura
- eventos de vaca reconstruidos
- segmentos de flujo asociados a cada vaca
- bytes o tramas desconocidas preservadas como evidencia

## Principios

1. Separar antes de medir.
2. Reagrupar antes de clasificar.
3. Marcar inferencias como inferencias, no como verdad cerrada.
4. Conservar siempre el raw y la trazabilidad temporal.

## Flujo propuesto

```text
serial_hex.txt
  -> parseo de lineas raw
  -> reconstruccion de fragmentos cercanos
  -> demultiplexado por canal
  -> deteccion de eventos de vaca
  -> asignacion de flujo por ventana temporal
  -> metricas operativas
  -> correlacion con red
```

## Fase 1. Parseo raw

Cada linea valida del archivo debe producir un registro base con:

- `timestamp`
- `ts_ms`
- `payload_raw`
- `tokens_hex`
- `line_index`
- `source_path`

Las lineas vacias o no interpretables no se eliminan sin rastro:

- se cuentan en `malformed_lines`
- si hace falta, se exportan en `serial_unparsed.csv`

## Fase 2. Reconstruccion de fragmentos

El adaptador USB puede cortar una misma trama en varias lineas. Por eso el
parser nuevo debe introducir una ventana de reconstruccion.

### Regla base

- si dos lineas consecutivas estan separadas por `<= 50 ms`
- y la primera luce truncada o demasiado corta
- se permite intentar fusionarlas en una sola trama candidata

### Señales de fragmentacion

- payload de 1 a 3 bytes seguido casi de inmediato por otra linea
- secuencias parciales que terminan o continúan patrones conocidos
- prefijos `A4`, `82`, `E4`, `C2`, `C3`, `E2`, `E3`, `E0` aislados

### Salida de esta fase

`serial_frames.csv` y `serial_frames.json` con:

- `frame_id`
- `start_ts`
- `end_ts`
- `duration_ms`
- `line_count`
- `payload_hex`
- `reconstructed`
- `source_line_indexes`

## Fase 3. Demultiplexado por canal

La clasificacion debe trabajar sobre `frames`, no sobre lineas sueltas.

### Categorias iniciales

- `control_plc`
  - tramas tipo `A4 ... A0`
- `sensor_flujo`
  - secuencias `E4 XX`
- `evento_vaca`
  - tokens o subtramas `C2`, `C3`, `E2`, `E3`, `E0`
- `desconocido`
  - cualquier byte o grupo no clasificado

### Regla de prioridad

1. `evento_vaca`
2. `sensor_flujo`
3. `control_plc`
4. `desconocido`

Un mismo `frame` puede producir subeventos en mas de una categoria. Por eso
conviene separar:

- `frame_type`: tipo dominante del frame
- `subevents`: tokens operativos extraidos del frame

## Fase 4. Cobertura del bus

La cobertura no debe basarse en "hubo cualquier byte", sino en actividad valida
del canal de control.

### Heartbeats o control de presencia

Patrones candidatos de cobertura:

- `A4 82 04 A0`
- `A4 82 05 A0`
- variantes equivalentes reconstruidas dentro del canal `control_plc`

### Metricas

- `capture_start_ts`
- `capture_end_ts`
- `capture_duration_s`
- `heartbeat_count`
- `heartbeat_avg_gap_s`
- `heartbeat_max_gap_s`
- `coverage_gap_count`
- `coverage_gap_seconds_total`
- `effective_coverage_pct`

### Regla de hueco

Si el intervalo entre heartbeats consecutivos supera `15 s`, se registra un
`coverage_gap`.

## Fase 5. Eventos de vaca

Los eventos de vaca deben reconstruirse con una maquina de estados sencilla.

### Secuencia operativa candidata

- `C2`: entrada o activacion de fotocelda
- `E2`: lectura RFID
- `C3`: salida o cierre del cruce

### Estados

- `idle`
- `waiting_rfid`
- `active_milking`
- `closing`
- `closed`
- `incomplete`

### Reglas base

- `C2` abre un evento nuevo
- `E2` dentro de `<= 5 s` desde el `C2` se asocia al evento actual
- `C3` cierra el evento actual
- si aparece un nuevo `C2` antes del `C3`, el evento anterior se marca como
  `interrumpido` o `incompleto`

### Metricas por evento

- `dwell_ms`
  - tiempo entre `C2` y `C3`
- `rfid_latency_ms`
  - tiempo entre `C2` y `E2`
- `next_cow_gap_ms`
  - tiempo entre `C2` actual y el siguiente `C2`

## Fase 6. Flujo por vaca

Todos los `E4 XX` entre el `C2` de la vaca `N` y el `C2` de la vaca `N+1`
pertenecen, por defecto, a la vaca `N`.

### Campos derivados

- `flow_sample_count`
- `flow_first_ts`
- `flow_last_ts`
- `flow_duration_ms`
- `flow_raw_min`
- `flow_raw_max`
- `flow_raw_avg`
- `flow_value_transform`

### Transformacion a probar

Como los valores observados suelen concentrarse entre `FC` y `FF`, conviene
guardar ambas lecturas:

- `flow_raw_value`
- `flow_inverted_value = 255 - flow_raw_value`

No se debe fijar una interpretacion fisica definitiva del byte sin validacion
de campo.

## Fase 7. Calidad del protocolo

Cada evento de vaca debe clasificarse como:

- `success`
  - `C2 + E2` en `<= 5 s` y flujo asociado
- `missing_rfid`
  - `C2` sin `E2` en ventana
- `missing_flow`
  - `C2 + E2` pero sin `E4 XX` posterior
- `partial`
  - secuencia incompleta o interrumpida

Esto alimenta la metrica operacional principal:

- `eta_operativa = eventos_success / eventos_totales`

## Archivos de salida nuevos

- `serial_frames.csv`
- `serial_unknown.csv`
- `cow_events.csv`
- `flow_segments.csv`
- `serial_operational_summary.json`

## Contrato de `cow_events.csv`

Cada fila representa un cruce de vaca reconstruido.

### Columnas minimas

- `event_id`
- `visit_name`
- `sample_id`
- `source_path`
- `event_status`
- `start_ts`
- `start_ts_ms`
- `c2_ts`
- `e2_ts`
- `c3_ts`
- `end_ts`
- `dwell_ms`
- `rfid_latency_ms`
- `next_cow_gap_ms`
- `has_c2`
- `has_e2`
- `has_c3`
- `has_flow`
- `flow_sample_count`
- `flow_first_ts`
- `flow_last_ts`
- `flow_duration_ms`
- `flow_raw_min`
- `flow_raw_max`
- `flow_raw_avg`
- `flow_inverted_min`
- `flow_inverted_max`
- `flow_inverted_avg`
- `unknown_token_count`
- `reconstructed_fragment_count`
- `notes`

### Valores esperados de `event_status`

- `success`
- `missing_rfid`
- `missing_flow`
- `partial`
- `interrupted`
- `unknown`

## Relacion con seguridad

Este motor operativo debe existir antes del motor de seguridad. La capa de
seguridad usara `cow_events.csv` como base para:

- eventos sin confirmacion de red
- descarte silencioso
- cadena de custodia
- tiempo de exposicion de datos en claro

## Implementacion por etapas

### Etapa 1

- parser raw
- reconstruccion de fragmentos
- demultiplexado basico
- export de `serial_frames.csv`

### Etapa 2

- maquina de estados de vaca
- export de `cow_events.csv`

### Etapa 3

- asignacion de flujo por vaca
- `eta_operativa`

### Etapa 4

- correlacion con UDP y PCAP
- metricas de seguridad y no repudio

