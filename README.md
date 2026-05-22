# FincaDiag Modular

Base modular para analizar:

- baseline de red
- telemetria serial
- trafico PCAP
- correlacion temporal serial <-> red
- alertas de ciberseguridad por capa
- reglas de prioridad para un motor perimetral

## Estructura

```text
FincaDiag_Modular/
├─ data/
│  ├─ raw/
│  └─ processed/
├─ reports/
├─ src/
│  └─ fincadiag/
│     ├─ analysis/
│     ├─ dashboard/
│     ├─ export/
│     ├─ parsers/
│     ├─ cli.py
│     ├─ config.py
│     ├─ models.py
│     └─ utils.py
├─ main.py
└─ requirements.txt
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
