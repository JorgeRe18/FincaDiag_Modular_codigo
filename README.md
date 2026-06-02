# FincaDiag Modular

Motor de análisis modular desarrollado como parte de un TFG de ingeniería en ciberseguridad. Procesa capturas de campo de una finca ganadera y genera informes técnicos y ejecutivos por sesión y por lote de visitas, cubriendo los tres objetivos del proyecto.

**Capacidades principales:**

- Baseline de red (ARP, topología, top talkers)
- Telemetría serial (collares SCR, eventos por vaca, confianza del parser)
- Tráfico PCAP (análisis general + canal de telemetría filtrado)
- Correlación temporal serial ↔ red (η de extracción, desfase medio)
- Alertas de ciberseguridad por capa (baseline, serial, PCAP, telemetría, correlación)
- Publicación normalizada vía gateway MQTT/TLS (Objetivo 3)
- Pruebas de resiliencia del gateway en producción (Objetivo 4)

## Estructura

```text
FincaDiag_Modular/
├─ src/fincadiag/        ← motor analítico
│  ├─ parsers/          ← serial, PCAP, baseline, antena UDP
│  ├─ analysis/         ← correlación, alertas, métricas, validación de campo
│  ├─ export/           ← generador de informes (report_builder)
│  ├─ gateway/          ← publicador MQTT/TLS, runtime, normalizer
│  ├─ dashboard/        ← Aletheia Board (Streamlit)
│  ├─ ingest/           ← descubrimiento de sesiones
│  └─ cli.py            ← interfaz de línea de comandos
├─ Gateway/             ← código operativo del gateway en la Raspberry Pi
│  ├─ run_gateway.sh / run_gateway.bat  ← arranque del daemon en la Pi
│  └─ tests/
│     └─ obj4_resilience_staged.py  ← experimento de resiliencia Obj4
├─ data/                ← capturas raw y datos procesados  [no versionado]
├─ reports/             ← informes generados               [no versionado]
├─ main.py              ← punto de entrada del motor
├─ requirements.txt
├─ normality_tests.py   ← pruebas Shapiro-Wilk sobre resultados Obj4 (Cap 6)
├─ install_obj4_cron.py ← sube script a Pi e instala cron de 9 ventanas diarias
├─ run_obj4_all_now.py  ← corre --all manualmente en Pi y muestra CSV del día
└─ diag_obj4_pi.py      ← diagnóstico remoto read-only de la Pi
```

## Flujo de uso

No es necesario copiar los archivos a mano si ya están organizados por visita, toma y hora. El motor detecta la estructura automáticamente.

Hay tres modos de operación:

1. `--sample`
   Procesa una sola carpeta `Captura_*` y le asocia el `Baseline_*` más cercano.

2. `--root`
   Recorre una raíz completa y procesa todas las carpetas `Captura_*` encontradas.

3. `--roots`
   Procesa varias raíces específicas en un mismo lote y genera un consolidado global
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

### Procesar un árbol completo

```powershell
python .\main.py --root "C:\PROYECTO_TFG\Prueba_Finca"
```

### Procesar varias visitas específicas en un mismo lote

```powershell
python .\main.py --roots `
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_20_03_2026" `
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_21_03_2026" `
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_23_03_2026" `
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_24_03_2026" `
  --run-name "Lote_4_visitas"
```

También puedes armar la lista en PowerShell:

```powershell
$visitas = @(
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_20_03_2026",
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_21_03_2026",
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_23_03_2026",
  "C:\PROYECTO_TFG\Prueba_Finca\Visita_24_03_2026"
)

python .\main.py --roots $visitas --run-name "Lote_4_visitas"
```

El motor trata cada `Captura_*` como una sesión analítica y busca el `Baseline_*`
más cercano dentro de la misma rama de carpetas.

Si existen dos baselines alrededor de una captura, el sistema detecta:

- `baseline_pre`: el baseline inmediatamente anterior por timestamp
- `baseline_post`: el baseline inmediatamente posterior por timestamp
- `baseline_usado`: por defecto el `baseline_pre`; si no existe, usa el `baseline_post`

Si la propia `Captura_*` ya contiene los archivos de baseline, esa carpeta se usa como
baseline principal de la sesión.

Si la raíz que pasas corresponde a una visita, por ejemplo:

```powershell
python .\main.py --root "C:\PROYECTO_TFG\Prueba_Finca\Visita_24_03_2026"
```

Se procesarán todas las tomas de esa visita y además se generará un resumen consolidado.

Casos de campo soportados:

- `Captura_*` con solo `serial_hex.txt`
- `Captura_*` con solo `captura.pcap` o `captura.pcapng`
- `Captura_*` con ambos archivos
- Cualquier carpeta `Baseline_*`, incluso dentro de visitas mixtas, se registra como sesión `baseline-only`
- `Captura_*` que ya incluye `reporte.txt`, `arp_a.txt`, `ipconfig_all.txt` y `route_print.txt`

La correlación solo se ejecuta cuando una sesión tiene datos serial y PCAP al mismo tiempo.

### Salidas

Los resultados se organizan por visita y por sesión, sin mezclar todo en una sola carpeta:

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

- Cada visita tiene su propia carpeta con informes por sesión (`por_hora`) y un consolidado (`resumen`)
- Al procesar un árbol grande, se genera además un resumen global del árbol completo
- Al usar `--roots`, se genera un consolidado global exclusivo del lote seleccionado
- Cada sesión guarda `alerts.json` y `alerts.csv` con alertas por capa: `baseline`, `serial`, `pcap_general`, `telemetry_6001` y `correlation`
- El resumen global distingue entre tipos de muestra: `SERIAL + PCAP`, `Antena + PCAP`, `PCAP`, `Baseline`
- El resumen global incluye un bloque de alertas en lenguaje accesible para lectores no técnicos

Cuando usas `--roots` con `--run-name`, el consolidado del lote queda separado así:

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

## Ejecutar dashboard (Aletheia Board)

```powershell
python -m streamlit run .\src\fincadiag\dashboard\app.py
```

> El dashboard interno se identifica como **Aletheia Board**. El título visible de la página sigue siendo **FincaDiag**.

## Instalar dependencias

```powershell
pip install -r .\requirements.txt
```

## Filosofía de diseño

- El motor analítico vive separado del dashboard: puede usarse sin interfaz gráfica.
- El dashboard solo visualiza resultados ya procesados, no ejecuta análisis.
- Cada módulo es reemplazable sin afectar el resto.

## Distinción de capas de red

El motor diferencia dos tipos de análisis sobre el PCAP:

1. `general` — tráfico LAN completo: multicast, broadcast, volumen total, top talkers
2. `telemetry` — canal de telemetría filtrado por IP, puerto y firma `56 D1 00`

La correlación serial ↔ red se ejecuta contra la capa `telemetry`, no contra el PCAP general.

---

## Pruebas de Resiliencia — Objetivo 4 (Raspberry Pi)

Las pruebas de resiliencia corren automáticamente en la Raspberry Pi mediante cron, sincronizadas con los bloques de captura activa del FincaScheduler. Esto garantiza que las métricas MTTR, PLR y estabilidad de memoria/CPU se miden **bajo carga real**.

### Cronograma diario

| Hora | Evento | Tipo | Duracion |
|------|--------|------|----------|
| 02:50, 05:00, 07:50, 10:38, 13:28, 15:36, 18:14, 21:03, 23:52 | `--all --cycles 7` | **Resiliencia** (broker, network, kill) | ~25 min |
| 08:15, 16:05 | `--scenario soak` | **Soak** (RSS/CPU del gateway) | 60 min |

Cada corrida de `--all` ejecuta 7 ciclos de los tres escenarios, generando **189 filas por día**.

El soak test muestrea la memoria RSS y el CPU del proceso `fincadiag-gateway` cada 30 segundos. Falla si el crecimiento de memoria supera el 20% o el CPU promedio supera el 80%.

### Resultados

Los resultados se almacenan en subcarpetas por día en la Pi:

```text
/home/esmeralda/resultados_obj4/
  20260601/
    obj4_resilience_results_20260601.csv   # broker/network/kill PASS/FAIL
    obj4_soak_results_20260601.csv         # muestras RSS/CPU cada 30s
    obj4_resilience_20260601.log
    obj4_soak_20260601.log
```

### Gestión desde Windows

Desde la raíz del repositorio se puede administrar la Pi sin conectarse manualmente:

| Script | Función |
|--------|---------|
| `install_obj4_cron.py` | Sube el script a la Pi e instala o actualiza el crontab |
| `run_obj4_all_now.py` | Lanza `--all` manualmente en la Pi y muestra el CSV del día |
| `diag_obj4_pi.py` | Diagnóstico remoto: verifica cron, procesos activos y últimos resultados |

### Uso directo del script en la Pi

```bash
sudo python3 /home/esmeralda/obj4_resilience_staged.py --dry-run
sudo python3 /home/esmeralda/obj4_resilience_staged.py --all --cycles 7
sudo python3 /home/esmeralda/obj4_resilience_staged.py --scenario broker
sudo python3 /home/esmeralda/obj4_resilience_staged.py --scenario soak --soak-minutes 60
```

---

## Generación de informes por objetivo

El motor puede orientar el contenido de los informes según el objetivo del TFG:

```powershell
# Objetivo 1 (por defecto): baseline, serial, PCAP, correlación, alertas
python .\main.py --root "C:\ruta\a\visitas" --objetivo 1

# Objetivo 3: gateway, publicación MQTT, spool, métricas de cadena
python .\main.py --root "C:\ruta\a\visitas" --objetivo 3

# Objetivo 4: resiliencia, MTTR, PLR, estabilidad del gateway
python .\main.py --root "C:\ruta\a\visitas" --objetivo 4
```

El parámetro `--objetivo` ajusta el framing de los informes técnicos, el resumen ejecutivo y el nombre del directorio de salida (por ejemplo, `Etapa_Obj4`).

---

## Análisis estadístico de resultados — Objetivo 4

Cuando las pruebas automáticas han acumulado suficientes datos (n ≥ 30 por escenario), `normality_tests.py` aplica **Shapiro-Wilk** sobre las tres métricas de resiliencia para determinar si corresponde usar una prueba paramétrica (t de Student) o no paramétrica (Mann-Whitney U) en el análisis comparativo.

```powershell
python .\normality_tests.py
```

| Métrica | Descripción |
|---------|-------------|
| **η (eta)** | Eficiencia de extracción — sesiones PRE vs POST intervención |
| **PLR** | Packet Loss Rate por escenario (broker / network / kill) |
| **MTTR** | Mean Time To Recovery — distribución de la muestra |

El script lee los CSV desde `resultados_obj4/YYYYMMDD/` en la Pi y guarda el resumen en `normality_results.json`.
