# Aletheia — Motor de Análisis Forense FincaDiag

Motor de análisis forense de telemetría operativa para el ecosistema SenseHub Dairy
en Finca La Esmeralda. Desarrollado como instrumento de medicion para un proyecto de
investigacion sobre pasarelas perimetrales en entornos ganaderos con controladores
propietarios sin documentacion publica.

Una **Raspberry Pi 5** instalada en la finca captura trafico serial, PCAP y UDP del
controlador de ordeño de forma pasiva. Los datos se transfieren a una estacion Windows
donde el motor los analiza. Los resultados normalizados se publican al broker MQTT/TLS
local (tambien en la Raspberry Pi 5) mediante la pasarela perimetral incluida aqui.
El motor analitico vive fuera del dashboard — cada modulo puede cambiarse sin reescribir
el resto.

Capacidades principales:

- análisis de baseline de red (latencia, jitter, PLR, ARP)
- parseo de telemetría serial propietaria (protocolo SenseHub)
- correlación temporal serial ↔ red para calculo de eficiencia (η)
- deteccion de alertas por capa (baseline, serial, pcap, correlación)
- publicación normalizada de eventos de ordeño via MQTT/TLS (store-and-forward)

## Estructura

```text
FincaDiag_Modular/
├─ data/
│  ├─ raw/
│  ├─ processed/
│  └─ gateway/
│     ├─ published/   ← JSONL y readable.json generados por el gateway
│     └─ spool/       ← mensajes pendientes de publicar (store-and-forward)
├─ reports/
├─ src/
│  └─ fincadiag/
│     ├─ analysis/
│     ├─ dashboard/
│     ├─ export/
│     ├─ gateway/     ← modulo de pasarela perimetral MQTT/TLS
│     ├─ ingest/      ← descubrimiento y construccion de sesiónes
│     ├─ parsers/
│     ├─ cli.py
│     ├─ config.py
│     ├─ models.py
│     └─ utils.py
├─ probe_forense/  ← scripts del instrumento forense (corren en la Raspberry Pi 5)
│  ├─ FincaDiag.py
│  └─ FincaScheduler.py
├─ main.py
└─ requirements.txt
```

## Requisitos de entorno

- Python 3.12 o superior
- Instalar dependencias: `pip install -r requirements.txt`
- El proyecto usa un layout `src/`, por lo que se requiere `PYTHONPATH=src`:

```powershell
$env:PYTHONPATH = "src"
```

---

## Pipeline completo (end-to-end)

Este es el flujo operativo completo del sistema, desde la captura en campo hasta la
publicación de telemetría normalizada al broker:

```
[Raspberry Pi en finca]          [Windows / estacion de análisis]        [Raspberry Pi - broker]
        |                                      |                                    |
 Captura automatica                            |                                    |
 serial_hex.txt                                |                                    |
 captura.pcap                                  |                                    |
 antena_udp.txt                                |                                    |
        |                                      |                                    |
        |--- SCP / WinSCP transfer ----------->|                                    |
        |                              python main.py --root <visita>               |
        |                              (motor: parser + correlación + alertas)      |
        |                                      |                                    |
        |                              data/processed/visits/                       |
        |                              Visita_DD_MM_YYYY/sesiones/...               |
        |                                      |                                    |
        |<-- SCP / WinSCP transfer ------------|                                    |
        |  /var/lib/fincadiag/processed/       |                                    |
        |                                      |                                    |
 run_gateway.sh                                |                                    |
 python -m fincadiag.gateway.runtime           |                                    |
        |                                      |                                    |
        |--- MQTT/TLS publish ----------------------------------------------->|      |
                                                                     broker:8883    |
```

### Pasos detallados

1. **Captura en campo (Raspberry Pi)**
   La Raspberry captura automaticamente por cron en `/home/esmeralda/FincaLogs/`.
   Cada sesión genera una carpeta `Captura_YYYYMMDD_HHMMSS/` con los archivos de evidencia.

2. **Transferencia a Windows**
   ```powershell
   scp -r esmeralda@<ip>:/home/esmeralda/FincaLogs/Visita_* C:\PROYECTO_TFG\Prueba_Finca\
   ```

3. **Procesamiento con el motor**
   ```powershell
   $env:PYTHONPATH = "src"
   python main.py --root "C:\PROYECTO_TFG\Prueba_Finca\Visita_DD_MM_YYYY"
   ```
   Salida: `data/processed/visits/Visita_DD_MM_YYYY/`

4. **Transferencia de sesión procesada a Raspberry**
   ```powershell
   scp -r "data\processed\visits\Visita_DD_MM_YYYY" esmeralda@<ip>:/var/lib/fincadiag/processed/
   ```

5. **Publicacion al broker MQTT/TLS**
   ```bash
   /home/esmeralda/run_gateway.sh
   ```
   Resultado esperado: `published=N spooled=0 failed=0`

---

## Probe Forense — Instrumento de captura en Raspberry Pi 5

La carpeta `probe_forense/` contiene los dos scripts que corren de forma autónoma en la
Raspberry Pi 5 instalada en la finca. No requieren intervención manual una vez configurados.

### Scripts

| Script | Rol |
|--------|-----|
| `FincaScheduler.py` | Orquestador: detecta el bloque activo del timeline y lanza `FincaDiag.py` en el modo correcto |
| `FincaDiag.py` | Ejecutor: captura serial, PCAP, Antena UDP o baseline según el modo recibido |

### Timeline diario (9 bloques)

El scheduler conoce el horario real de la finca y opera sin configuración adicional:

```
02:15  ORDEÑO AM  → Baseline + Serial + Antena UDP + PCAP (1h20) + Baseline
04:34  NORMAL 1   → Baseline + Antena UDP (1h) + PCAP (1h) + Baseline
07:23  NORMAL 2   → ...
10:12  NORMAL 3   → ...
13:00  ORDEÑO PM  → Baseline + Serial + Antena UDP + PCAP (1h20) + Baseline
15:10  NORMAL 4   → ...
17:48  NORMAL 5   → ...
20:37  NORMAL 6   → ...
23:26  NORMAL 7   → ...
```

Bloques **ORDEÑO**: captura serial + red completa — son las sesiónes de análisis principal.
Bloques **NORMAL**: solo telemetría de red — monitoreo continuo entre ordeños.

### Modos de FincaDiag.py

| Modo | Descripcion |
|------|-------------|
| `-m 1` | Antena UDP + PCAP filtrado puerto 6001 |
| `-m 2` | Serial + PCAP completo (bloques ordeño) |
| `-m 3` | Solo PCAP completo (bloques normales) |
| `-m 4` | Baseline de red |
| `-m 5` | Serial + Antena UDP + PCAP en paralelo |

### Ejecución en Raspberry Pi

El scheduler se invoca via cron cada minuto. Si el minuto actual cae dentro de un bloque
activo, ejecuta las fases pendientes; si cae en período de descanso, no hace nada.

```bash
# Entrada en crontab (crontab -e)
* * * * * /usr/bin/python3 /home/esmeralda/probe_forense/FincaScheduler.py
```

El scheduler es resiliente a reinicios: guarda el estado del bloque en
`/home/esmeralda/FincaLogs/fincadiag_scheduler_state.json` y retoma desde donde se
interrumpió si detecta que el bloque todavía está activo.

Salidas generadas en `/home/esmeralda/FincaLogs/`:

```
ordeño_pm_20260512_1300/
  Baseline_20260512_130000/
  Captura_20260512_130500/
    serial_hex.txt
    captura.pcap
    antena_udp.txt
  Baseline_20260512_145500/
```

## Motor — Flujo recomendado

No necesitas copiar tus logs a mano si ya los tienes organizados por visita, toma y hora.

El motor puede trabajar de dos formas:

1. `--sample`
   Procesa una sola carpeta `Captura_*` y le asocia el `Baseline_*` mas cercano.

2. `--root`
   Recorre una raiz completa y procesa todas las carpetas `Captura_*` encontradas.

3. `--roots`
   Procesa varias raices especificas en un mismo lote y genera un consolidado global
   solo para ese conjunto de visitas o carpetas seleccionadas.

Ejemplo de estructura soportada:

```text
Visita_21_03_2026/
├─ TOMA_AM/
│  ├─ 1AM/
│  │  ├─ Baseline_20260321_010004/
│  │  ├─ Captura_20260321_010500/
│  │  └─ Captura_20260321_011500/
│  └─ 3AM/
│     ├─ Baseline_...
│     └─ Captura_...
└─ TOMA_PM/
   └─ 1PM/
      ├─ Baseline_...
      └─ Captura_...
```

### Procesar una sola captura

```powershell
python .\main.py --sample "C:\PROYECTO_TFG\Prueba_Finca\Visita_21_03_2026\TOMA_PM\1PM\Captura_20260321_134708"
```

### Procesar un arbol completo

```powershell
python .\main.py --root "C:\PROYECTO_TFG\Prueba_Finca"
```

### Procesar varias visitas especificas en un mismo lote

```powershell
python .\main.py --roots `
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_20_03_2026" `
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_21_03_2026" `
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_23_03_2026" `
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_24_03_2026" `
  --run-name "Lote_4_visitas"
```

Si prefieres, tambien puedes armar la lista en PowerShell:

```powershell
$visitas = @(
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_20_03_2026",
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_21_03_2026",
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_23_03_2026",
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_24_03_2026"
)

python .\main.py --roots $visitas --run-name "Lote_4_visitas"
```

El sistema tratara cada `Captura_*` como una sesión analitica y buscara el `Baseline_*`
mas cercano dentro de la misma rama de carpetas.

Si existen dos baselines alrededor de una captura, el sistema detecta:

- `baseline_pre`: el baseline inmediatamente anterior por timestamp
- `baseline_post`: el baseline inmediatamente posterior por timestamp
- `baseline_usado`: por defecto el `baseline_pre`; si no existe, usa el `baseline_post`

Cuando existen **ambos** (`baseline_pre` y `baseline_post`), el motor calcula ademas un
análisis de transicion de red (`baseline_transition`) que compara el estado de la red
antes y despues de la captura:

| Campo | Descripcion |
|-------|-------------|
| `lat_media_delta` | Cambio de latencia media pre→post (ms) |
| `jitter_delta` | Cambio de jitter pre→post (ms) |
| `packet_loss_delta` | Cambio de pérdida de paquetes pre→post (%) |
| `nodos_delta` | Cambio en cantidad de nodos detectados en red |

Si solo existe uno de los dos baselines, `baseline_transition.available = false` y
los deltas quedan en `null`.

Si la propia `Captura_*` ya contiene los archivos de baseline, esa carpeta se usa como
baseline principal de la sesión.

Si la raiz que pasas corresponde a una visita, por ejemplo:

```powershell
python .\main.py --root "C:\PROYECTO_TFG\Prueba_Finca\Visita_24_03_2026"
```

se procesaran todas las tomas de esa visita y ademas se generara un resumen consolidado por visita.

Tambien soporta estos casos reales:

- `Captura_*` con solo `serial_hex.txt`
- `Captura_*` con solo `captura.pcap` o `captura.pcapng`
- `Captura_*` con ambos archivos
- cualquier carpeta `Baseline_*`, incluso dentro de visitas mixtas, se registra tambien como sesión `baseline-only`
- `Captura_*` que ya trae `reporte.txt`, `arp_a.txt`, `ipconfig_all.txt` y `route_print.txt`
  dentro de la propia carpeta

La correlación solo se ejecuta cuando una sesión tiene serial y PCAP al mismo tiempo.

### Distincion de capas de red

El motor separa explicitamente dos tipos de análisis sobre PCAP:

1. `general` — trafico LAN completo: multicast, broadcast, volumen total, top talkers
2. `telemetry` — trafico del canal de antena: filtrado por IP/puerto objetivo, firma `56 D1 00`, eventos UDP/TCP del canal

La correlación serial ↔ red se realiza contra la capa `telemetry`, no contra el PCAP general.

### Salidas

Las salidas ya no quedan mezcladas en una sola carpeta plana.

Ahora se organizan asi:

```text
data/
  processed/
    visits/
      Visita_23_03_2026/
        sesiones/
          TOMA_AM__12AM__Captura_20260323_000005/
          TOMA_AM__12AM__Captura_20260323_010005/
        resumen/
          Visita_23_03_2026_summary.json
          Visita_23_03_2026_sessions.csv
    global/
      resumen_arbol/
        Prueba_Finca_summary.json
        Prueba_Finca_visits.csv

reports/
  visits/
    Visita_23_03_2026/
      por_hora/
        TOMA_AM__12AM__Captura_20260323_000005_technical_report.txt
        TOMA_AM__12AM__Captura_20260323_010005_technical_report.txt
      resumen/
        Visita_23_03_2026_summary.txt
  global/
    resumen_arbol/
      Prueba_Finca_summary.txt
```

En resumen:

- cada visita tiene su propia carpeta
- cada visita tiene una carpeta `por_hora` con los informes por sesión
- cada visita tiene una carpeta `resumen` con el consolidado de la visita
- si procesas un arbol grande con varias visitas, tambien se genera un resumen global del arbol
- si procesas varias visitas especificas con `--roots`, se genera un consolidado global propio del lote
- cada sesión guarda `alerts.json` y `alerts.csv` con alertas de `baseline`, `serial`, `pcap_general`, `telemetry_6001` y `correlation`
- el resumen global y el resumen por visita incluyen control por tipo de muestra:
  `SERIAL + PCAP`, `Antena + PCAP`, `PCAP`, `Baseline`
- el resumen global incluye un bloque de alertas PCAP en lenguaje simple para lector no tecnico

Cuando usas `--roots` con `--run-name`, el consolidado del lote queda separado asi:

```text
data/
  processed/
    global/
      resumen_arbol/
        Lote_4_visitas/
          Lote_4_visitas_summary.json
          Lote_4_visitas_visits.csv
          Lote_4_visitas_sessions.csv

reports/
  global/
    resumen_arbol/
      Lote_4_visitas/
        Lote_4_visitas_summary.txt
```

## Gateway perimetral

El modulo `gateway` toma una sesión ya procesada por el motor y publica sus mensajes
normalizados a un broker MQTT/TLS. Soporta modo dry-run (escribe localmente) y modo
produccion (publica al broker).

### Dry-run (sin broker)

```powershell
$env:PYTHONPATH="src"
python -m fincadiag.gateway.runtime `
  --session-dir "data\processed\visits\Visita_11_05_2026\sesiones\TOMA_PM__1PM__Captura_20260511_130005" `
  --dry-run
```

Genera los archivos `.jsonl` y `.readable.json` en `data/gateway/published/` sin
necesitar broker activo.

### Publicacion real (broker MQTT/TLS)

```powershell
$env:PYTHONPATH="src"
$env:MQTT_HOST="<ip_broker>"
$env:MQTT_PORT="8883"
$env:TOPIC_ROOT="fincadiag/la_esmeralda"
$env:CA_PATH="<ruta>/ca.crt"
$env:CERT_PATH="<ruta>/client.crt"
$env:KEY_PATH="<ruta>/client.key"
python -m fincadiag.gateway.runtime `
  --session-dir "data\processed\visits\Visita_11_05_2026\sesiones\TOMA_PM__1PM__Captura_20260511_130005"
```

### Salidas del gateway

Cada sesión publicada genera dos archivos en `data/gateway/published/`:

- `<session_id>.jsonl` — un mensaje JSON por linea, formato de ingesta
- `<session_id>.readable.json` — version legible con metadatos y conteos

El motor tambien genera un archivo `gateway_expectations.json` por sesión procesada
(junto a `correlation_summary.json`, `pcap_summary.json`, etc.) que sirve como
oraculo/checklist: describe los tipos de mensajes esperados y las métricas que el
gateway deberia reflejar para esa sesión.

### Tipos de mensaje publicados

| Tipo | Descripcion |
|------|-------------|
| `session_summary` | Resumen general de la sesión |
| `baseline_snapshot` | Estado de red al momento de la captura |
| `pcap_summary` | Estadisticas de trafico PCAP |
| `alerts_summary` | Conteo y severidad de alertas por capa |
| `collar_summary` | Telemetria de collares SCR |
| `correlation_summary` | η, desfase_medio, matches |
| `cow_event` | Un mensaje por evento de vaca (status, RFID, confianza, dwell) |

## Dashboard — Aletheia Board

### Ejecutar

```powershell
python -m streamlit run .\src\fincadiag\dashboard\app.py
```

El dashboard solo visualiza resultados ya procesados por el motor — no ejecuta análisis.

---

## Generación de informes por objetivo

El motor puede generar informes orientados al objetivo del TFG que se esté documentando.
Esto no cambia la evidencia procesada; cambia el enfoque del reporte, los títulos y la
lectura ejecutiva de los hallazgos.

```powershell
# Objetivo 1: caracterización, baseline, serial, PCAP, correlación y alertas
python .\main.py --root "C:\ruta\a\visitas" --objetivo 1

# Objetivo 3: gateway perimetral, publicación MQTT/TLS y cadena de datos
python .\main.py --root "C:\ruta\a\visitas" --objetivo 3

# Objetivo 4: resiliencia, MTTR, PLR y estabilidad operativa del gateway
python .\main.py --root "C:\ruta\a\visitas" --objetivo 4
```

El parámetro `--objetivo` afecta:

- el texto de los informes técnicos y human-readable
- el resumen ejecutivo global
- las etiquetas de hallazgos priorizados
- el nombre del directorio del lote, por ejemplo `Etapa_Obj3` o `Etapa_Obj4`

Si ya existen los `summary.json` procesados, se pueden regenerar informes sin repetir
todo el análisis:

```powershell
python .\main.py --root "C:\ruta\a\visitas" --objetivo 4 --run-name "Etapa_Obj4"
```

## Pruebas de resiliencia — Objetivo 4

El Objetivo 4 se evalúa sobre el gateway perimetral en la Raspberry Pi. Las pruebas
miden recuperación y estabilidad bajo condiciones controladas: caída de broker, pérdida
de red, terminación del proceso y ejecución prolongada.

### Cronograma automático en Raspberry Pi

| Hora | Evento | Tipo | Duración |
|------|--------|------|----------|
| 02:50, 05:00, 07:50, 10:38, 13:28, 15:36, 18:14, 21:03, 23:52 | `--all --cycles 7` | Resiliencia: broker, network, kill | ~25 min |
| 08:15, 16:05 | `--scenario soak` | Soak: memoria RSS y CPU del gateway | 60 min |

`--cycles 7` ejecuta siete ciclos consecutivos por escenario. En una jornada completa
produce 189 filas de resiliencia, útiles para calcular PLR, MTTR y estabilidad de
recuperación.

### Scripts de gestión desde Windows

| Script | Función |
|--------|---------|
| `install_obj4_cron.py` | Sube el experimento a la Raspberry Pi e instala/actualiza el cron de pruebas |
| `run_obj4_all_now.py` | Ejecuta manualmente una corrida `--all` en la Raspberry Pi y muestra el CSV del día |
| `diag_obj4_pi.py` | Diagnóstico remoto read-only: cron, procesos activos y últimos resultados |
| `normality_tests.py` | Aplica Shapiro-Wilk sobre métricas acumuladas para apoyar el análisis estadístico |


### Resultados esperados en la Raspberry Pi

```text
/home/esmeralda/resultados_obj4/
  20260601/
    obj4_resilience_results_20260601.csv
    obj4_soak_results_20260601.csv
    obj4_resilience_20260601.log
    obj4_soak_20260601.log
```

### Ejecución manual de referencia

```bash
sudo python3 /home/esmeralda/obj4_resilience_staged.py --dry-run
sudo python3 /home/esmeralda/obj4_resilience_staged.py --all --cycles 5
sudo python3 /home/esmeralda/obj4_resilience_staged.py --scenario broker
sudo python3 /home/esmeralda/obj4_resilience_staged.py --scenario soak --soak-minutes 60
```

## Análisis estadístico del Objetivo 4

Cuando las pruebas automáticas acumulan suficientes datos, `normality_tests.py` aplica
Shapiro-Wilk sobre las métricas principales para decidir si el análisis comparativo debe
usar una prueba paramétrica o no paramétrica.

```powershell
python .\normality_tests.py
```

Métricas consideradas:

| Métrica | Descripción |
|---------|-------------|
| `eta` | Eficiencia de extracción antes y después de la intervención |
| `PLR` | Packet Loss Rate por escenario de resiliencia |
| `MTTR` | Mean Time To Recovery del gateway |

El resultado se guarda en `normality_results.json` y sirve como respaldo para el
capítulo de validación.
