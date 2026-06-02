# FincaDiag Modular

Motor de análisis modular para el sistema FincaDiag (TFG). Procesa capturas de campo de una finca ganadera y genera informes técnicos y ejecutivos por sesión y por lote de visitas.

Capacidades principales:

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
├─ src/fincadiag/        ← motor analítico (parsers, analysis, export, gateway, dashboard)
├─ Gateway/             ← código del gateway MQTT/TLS y pruebas de resiliencia Obj4
│  └─ tests/
│     └─ obj4_resilience_staged.py
├─ scripts/             ← utilidades de análisis y generación de reportes
├─ docs/                ← documentación interna
├─ data/                ← capturas raw y datos procesados (no versionados)
├─ reports/             ← informes generados (no versionados)
├─ main.py              ← punto de entrada del motor
├─ requirements.txt
├─ install_obj4_cron.py ← gestión del cron de Obj4 en la Raspberry Pi
├─ run_obj4_all_now.py  ← ejecución manual de Obj4 vía SSH
└─ diag_obj4_pi.py      ← diagnóstico remoto de la Pi
```

## Flujo recomendado

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

El sistema tratara cada `Captura_*` como una sesion analitica y buscara el `Baseline_*`
mas cercano dentro de la misma rama de carpetas.

Si existen dos baselines alrededor de una captura, el sistema detecta:

- `baseline_pre`: el baseline inmediatamente anterior por timestamp
- `baseline_post`: el baseline inmediatamente posterior por timestamp
- `baseline_usado`: por defecto el `baseline_pre`; si no existe, usa el `baseline_post`

Si la propia `Captura_*` ya contiene los archivos de baseline, esa carpeta se usa como
baseline principal de la sesion.

Si la raiz que pasas corresponde a una visita, por ejemplo:

```powershell
python .\main.py --root "C:\PROYECTO_TFG\Prueba_Finca\Visita_24_03_2026"
```

se procesaran todas las tomas de esa visita y ademas se generara un resumen consolidado por visita.

Tambien soporta estos casos reales:

- `Captura_*` con solo `serial_hex.txt`
- `Captura_*` con solo `captura.pcap` o `captura.pcapng`
- `Captura_*` con ambos archivos
- cualquier carpeta `Baseline_*`, incluso dentro de visitas mixtas, se registra tambien como sesion `baseline-only`
- `Captura_*` que ya trae `reporte.txt`, `arp_a.txt`, `ipconfig_all.txt` y `route_print.txt`
  dentro de la propia carpeta

La correlacion solo se ejecuta cuando una sesion tiene serial y PCAP al mismo tiempo.

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
- cada visita tiene una carpeta `por_hora` con los informes por sesion
- cada visita tiene una carpeta `resumen` con el consolidado de la visita
- si procesas un arbol grande con varias visitas, tambien se genera un resumen global del arbol
- si procesas varias visitas especificas con `--roots`, se genera un consolidado global propio del lote
- cada sesion guarda `alerts.json` y `alerts.csv` con alertas de `baseline`, `serial`, `pcap_general`, `telemetry_6001` y `correlation`
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

## Ejecutar dashboard (Aletheia Board)

```powershell
python -m streamlit run .\src\fincadiag\dashboard\app.py
```

> El dashboard interno se identifica como **Aletheia Board**. El título visible de la página sigue siendo **FincaDiag**.

## Instalar dependencias

```powershell
pip install -r .\requirements.txt
```

## Filosofia

- El motor analitico vive fuera del dashboard.
- El dashboard solo visualiza resultados.
- Cada modulo puede cambiarse sin reescribir el resto.

## Distincion de capas de red

El motor separa explicitamente dos tipos de analisis sobre PCAP:

1. `general`
   - trafico LAN completo
   - multicast
   - broadcast
   - volumen total
   - top talkers

2. `telemetry`
   - trafico del canal de antena/telemetria
   - filtrado por IP objetivo y puerto objetivo
   - firma `56 D1 00`
   - eventos UDP y TCP del canal

La correlacion serial <-> red se realiza contra la capa `telemetry`, no contra todo el
PCAP general.

---

## Pruebas de Resiliencia - Objetivo 4 (Raspberry Pi)

El sistema ejecuta pruebas automaticas de resiliencia del gateway en la Raspberry Pi,
programadas en el crontab de `root`. Esto garantiza que las metricas MTTR, PLR y
estabilidad de memoria/CPU se miden **bajo carga real** (durante los bloques de captura
activa del FincaScheduler).

### Cronograma diario automatico

| Hora | Evento | Tipo | Duracion |
|------|--------|------|----------|
| 02:50, 05:00, 07:50, 10:38, 13:28, 15:36, 18:14, 21:03, 23:52 | `--all --cycles 7` | **Resiliencia** (broker, network, kill) | ~25 min |
| 08:15, 16:05 | `--scenario soak` | **Soak** (RSS/CPU del gateway) | 60 min |

**`--cycles 7`** ejecuta 7 ciclos consecutivos de cada escenario por corrida, lo que
produce **189 filas de resiliencia al dia** (27 escenarios × 7 ciclos).

**Soak test** muestrea la memoria RSS y el uso de CPU del proceso `fincadiag-gateway`
cada 30 segundos. Falla si el crecimiento de memoria supera 20% o el promedio de CPU
supera 80%.

### Resultados

Los resultados se organizan en subcarpetas por dia dentro de la Pi:

```text
/home/esmeralda/resultados_obj4/
  20260601/
    obj4_resilience_results_20260601.csv   # broker/network/kill PASS/FAIL
    obj4_soak_results_20260601.csv         # muestras RSS/CPU cada 30s
    obj4_resilience_20260601.log
    obj4_soak_20260601.log
```

### Gestion desde Windows (repo local)

Scripts en la raiz del repo para administrar las pruebas sin entrar a la Pi:

| Script | Funcion |
|--------|---------|
| `install_obj4_cron.py` | Sube `obj4_resilience_staged.py` e instala/actualiza el crontab de root en la Pi |
| `run_obj4_all_now.py` | Corre `--all` manualmente en la Pi y muestra el CSV del dia |
| `diag_obj4_pi.py` | Diagnostico read-only: verifica cron, procesos activos y ultimos resultados |

Requiere la variable de entorno `PI_PASSWORD` para conexion SSH via paramiko.

### Argumentos del script de resiliencia (en la Pi)

```bash
sudo python3 /home/esmeralda/obj4_resilience_staged.py --dry-run        # verificacion sin tocar nada
sudo python3 /home/esmeralda/obj4_resilience_staged.py --all --cycles 5   # broker+network+kill, 5 ciclos
sudo python3 /home/esmeralda/obj4_resilience_staged.py --scenario broker  # solo broker, 1 ciclo
sudo python3 /home/esmeralda/obj4_resilience_staged.py --scenario soak --soak-minutes 60
```

---

## Generacion de informes por Objetivo

El motor soporta generar informes orientados al objetivo del TFG seleccionado:

```powershell
# Objetivo 1 (default): baseline, serial, pcap, correlacion, alertas
python .\main.py --root "C:\ruta\a\visitas" --objetivo 1

# Objetivo 3: gateway, publicacion MQTT, spool, metricas de cadena
python .\main.py --root "C:\ruta\a\visitas" --objetivo 3

# Objetivo 4: resiliencia, MTTR, PLR, estabilidad del gateway
python .\main.py --root "C:\ruta\a\visitas" --objetivo 4
```

El parametro `--objetivo` afecta:
- El texto de los informes tecnicos y human-readable (framing, titulos, secciones)
- El resumen ejecutivo global (etiquetas y hallazgos priorizados)
- El nombre del directorio del lote (ej. `Etapa_Obj3`, `Etapa_Obj4`)

### Regenerar informes sin reprocesar datos

Si ya existen los `summary.json` procesados, se pueden regenerar los informes
sin volver a ejecutar el motor completo:

```powershell
python .\scripts\regenerar_informes_obj.py --objetivo 4 --run-name "Etapa_Obj4"
```

Esto reescribe los `.txt` de sesion y actualiza el resumen ejecutivo global
para reflejar el objetivo seleccionado.

---

## Analisis estadistico de resultados Objetivo 4

Una vez que las pruebas automaticas han acumulado datos suficientes (n ≥ 30 por escenario),
`normality_tests.py` aplica **Shapiro-Wilk** sobre las tres metricas de resiliencia para
determinar si usar test parametrico (t-Student) o no parametrico (Mann-Whitney U) en el
analisis comparativo del Capitulo 6.

### Uso

```powershell
python .\normality_tests.py
```

### Que analiza

| Metrica | Descripcion |
|---------|-------------|
| **η (eta)** | Eficiencia de extraccion — sesiones PRE vs POST intervencion |
| **PLR** | Packet Loss Rate por escenario (broker / network / kill) |
| **MTTR** | Mean Time To Recovery — distribucion de la muestra unica |

### Salida

```
PRUEBAS DE NORMALIDAD (Shapiro-Wilk) - OBJETIVO 4
--- 1. Eficiencia de extraccion (eta) ---
  eta PRE : W=0.94 p=0.312 -> NORMAL
  eta POST: W=0.89 p=0.041 -> NO NORMAL
  RECOMENDACION: Mann-Whitney U (al menos una distribucion no normal)

--- 2. Packet Loss Rate (PLR) ---
  ...

--- 3. Mean Time To Recovery (MTTR) ---
  ...

Resultados guardados en normality_results.json
```

Lee los CSV de la Pi desde `resultados_obj4/YYYYMMDD/obj4_resilience_results_*.csv`
y guarda el resumen en `normality_results.json` para incluir en el informe.
