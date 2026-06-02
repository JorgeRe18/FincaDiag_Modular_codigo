#!/bin/bash
# measure_live_resilience_pi_v3.sh
# Corre DESPUES de una sesion en la que se inyecto un fallo.
# v3-hot: Calcula PLR real contra baseline historico, evalua spooling como resiliencia activa.
#
# Uso: ./measure_live_resilience_pi_v3.sh [HORAS_ATRAS] [BASELINE_COW_EVENTS]
# Default: HORAS_ATRAS=2, BASELINE_COW_EVENTS=30 (promedio historico sesiones ordeño)

set -euo pipefail

HORAS_ATRAS="${1:-2}"
BASELINE="${2:-30}"   # Baseline historico: 30 cow_events/sesion tipica
PUB_DIR="/var/lib/fincadiag/published"
SPOOL_DIR="/var/lib/fincadiag/spool"
FAULTS="/home/esmeralda/fault_injections.csv"
RESULTS="/home/esmeralda/live_resilience_results.csv"

# Detectar archivos .jsonl publicados en las ultimas HORAS_ATRAS horas
JSONL_FILES=$(find "$PUB_DIR" -name "*.jsonl" -mmin -$((HORAS_ATRAS * 60)) 2>/dev/null || true)
if [ -z "$JSONL_FILES" ]; then
    JSONL_FILES=$(find "$PUB_DIR" -name "*.jsonl" 2>/dev/null || true)
    SCOPE="todos"
else
    SCOPE="ultimas_${HORAS_ATRAS}h"
fi

# Contar cow_event publicados
COW_EVENTS=0
if [ -n "$JSONL_FILES" ]; then
    COW_EVENTS=$(echo "$JSONL_FILES" | xargs grep -h '"event_type":"cow_event"' 2>/dev/null | wc -l)
fi

# Spool residual (mensajes que el gateway guardo localmente durante el fallo)
SPOOL_RES=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)

# Cargar fallos aplicados
FAULT_COUNT=0
if [ -f "$FAULTS" ]; then
    FAULT_COUNT=$(tail -n +2 "$FAULTS" | wc -l)
fi

# Calcular PLR real vs baseline historico
if [ "$COW_EVENTS" -ge "$BASELINE" ]; then
    PLR="0.00"
    PERDIDOS=0
else
    PERDIDOS=$((BASELINE - COW_EVENTS))
    PLR=$(awk "BEGIN {printf \"%.2f\", ($PERDIDOS / $BASELINE) * 100}")
fi

# Criterio de resiliencia v3-hot:
# - Si hay spool > 0: gateway activo con resiliencia (spooling = bueno, no perdida definitiva)
# - Si PLR <= 10% y spool drena: RECOVERY
# - Si PLR > 10%: DATA_LOSS (pero documentado para tesis)
if [ "$SPOOL_RES" -gt 0 ]; then
    # Gateway spoolo mensajes -> resiliencia activa. Verificar si luego los drena.
    STATUS="SPOOL_ACTIVE"
elif [ "$COW_EVENTS" -eq 0 ]; then
    STATUS="CRITICAL_NO_DATA"
else
    PLR_VAL=$(echo "$PLR" | awk '{print $1 + 0}')
    if awk "BEGIN {exit !($PLR_VAL <= 10.0)}"; then
        STATUS="PASS"
    else
        STATUS="DATA_LOSS"
    fi
fi

TS=$(date -Iseconds)
SESION=$(echo "$JSONL_FILES" | head -1 | xargs basename 2>/dev/null || echo "N/A")

if [ ! -f "$RESULTS" ]; then
    echo "timestamp,sesion,scope,cow_events_publicados,cow_events_baseline,cow_events_perdidos,plr_pct,spool_residual,fault_count_total,resilience_status" > "$RESULTS"
fi

echo "$TS,$SESION,$SCOPE,$COW_EVENTS,$BASELINE,$PERDIDOS,$PLR,$SPOOL_RES,$FAULT_COUNT,$STATUS" >> "$RESULTS"

echo "=== Measure Live Resilience v3-hot ==="
echo "Archivos analizados : $SCOPE"
echo "cow_events_publicados: $COW_EVENTS"
echo "cow_events_baseline  : $BASELINE"
echo "cow_events_perdidos  : $PERDIDOS"
echo "PLR (%)              : $PLR"
echo "spool_residual       : $SPOOL_RES"
echo "fault_count_total    : $FAULT_COUNT"
echo "resilience_status    : $STATUS"
echo ""
echo "Registrado en $RESULTS"
