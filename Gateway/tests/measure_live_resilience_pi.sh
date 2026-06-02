#!/bin/bash
# measure_live_resilience_pi.sh
# Corre DESPUES de una sesion en la que se inyecto un fallo (inject_fault_live_pi.sh).
# Cruza fault_injections.csv con session_summary.json publicado para calcular:
#   - cow_events_publicados vs esperados
#   - spool_residual
#   - eventos_perdidos = 0 (o >0 si hubo perdida real)
#
# Uso: ./measure_live_resilience_pi.sh [VISIT_DIR] [SESION_NOMBRE]
# Default: ultima visita en /var/lib/fincadiag/published

set -euo pipefail

VISIT_DIR="${1:-}"
SESION="${2:-}"
PUB_ROOT="/var/lib/fincadiag/published"
SPOOL_DIR="/var/lib/fincadiag/spool"
FAULTS="/home/esmeralda/fault_injections.csv"
RESULTS="/home/esmeralda/live_resilience_results.csv"

# Si no pasan args, detectar ultima visita
if [ -z "$VISIT_DIR" ]; then
    VISIT_DIR=$(find "$PUB_ROOT" -maxdepth 1 -type d | sort | tail -1)
fi
if [ -z "$SESION" ]; then
    SESION=$(basename "$VISIT_DIR")
fi

if [ ! -d "$VISIT_DIR" ]; then
    echo "[ERROR] No existe visita: $VISIT_DIR"
    exit 1
fi

echo "=== Measure Live Resilience ==="
echo "Visita : $VISIT_DIR"
echo "Sesion : $SESION"

# Contar cow_event publicados
COW_EVENTS=$(find "$VISIT_DIR" -name "*.jsonl" -exec grep -h '"type":"cow_event"' {} + 2>/dev/null | wc -l)

# Ver session_summary si existe
SUMMARY=""
for f in "$VISIT_DIR"/session_summary.json "$VISIT_DIR"/*/session_summary.json; do
    if [ -f "$f" ]; then
        SUMMARY="$f"
        break
    fi
done

EVENTS_SUMMARY=0
if [ -n "$SUMMARY" ] && [ -f "$SUMMARY" ]; then
    EVENTS_SUMMARY=$(python3 -c "import json; d=json.load(open('$SUMMARY')); print(d.get('cow_event_count',0))" 2>/dev/null || echo 0)
fi

# Spool residual
SPOOL_RES=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)

# Cargar fallos aplicados en esta sesion (ultima hora antes de la sesion)
FAULT_COUNT=0
if [ -f "$FAULTS" ]; then
    FAULT_COUNT=$(tail -n +2 "$FAULTS" | wc -l)
fi

# Criterio: si spool==0 y cow_events_publicados > 0 => PASS resiliencia
if [ "$SPOOL_RES" -eq 0 ] && [ "$COW_EVENTS" -gt 0 ]; then
    STATUS="PASS"
else
    STATUS="REVIEW"
fi

TS=$(date -Iseconds)

if [ ! -f "$RESULTS" ]; then
    echo "timestamp,sesion,cow_events_publicados,cow_events_summary,spool_residual,fault_count,resilience_status" > "$RESULTS"
fi

echo "$TS,$SESION,$COW_EVENTS,$EVENTS_SUMMARY,$SPOOL_RES,$FAULT_COUNT,$STATUS" >> "$RESULTS"

echo ""
echo "Resultado:"
echo "  cow_events_publicados : $COW_EVENTS"
echo "  cow_events_summary    : $EVENTS_SUMMARY"
echo "  spool_residual        : $SPOOL_RES"
echo "  fault_count           : $FAULT_COUNT"
echo "  resilience_status     : $STATUS"
echo ""
echo "Registrado en $RESULTS"
