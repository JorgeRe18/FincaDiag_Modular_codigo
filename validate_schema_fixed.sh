#!/bin/bash
# Prueba 1 (Pi): Validacion de contrato JSON del gateway (schema minimo)
# field_validation_summary ahora es opcional (no todas las sesiones lo generan)
set -euo pipefail

SESSION_DIR="${1:-}"
if [ -z "$SESSION_DIR" ]; then
    echo "Uso: $0 <ruta_sesion_procesada>"
    exit 1
fi

echo "=== Validando sesion: $SESSION_DIR ==="

export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run >/dev/null 2>&1 || {
    echo "[FAIL] Gateway dry-run fallo"
    exit 1
}

JSON_FILE=$(ls data/gateway/published/*.readable.json | tail -1)
if [ -z "$JSON_FILE" ]; then
    echo "[FAIL] No se encontro archivo .readable.json"
    exit 1
fi
echo "Archivo: $JSON_FILE"

python3 - <<PYEOF
import json, sys

with open("$JSON_FILE") as f:
    data = json.load(f)

errors = []

for field in ['batch_name','message_count','counts_by_event_type','messages_by_event_type']:
    if field not in data:
        errors.append(f'Falta campo requerido: {field}')

counts = data.get('counts_by_event_type', {})
if data.get('message_count') != sum(counts.values()):
    errors.append(f"message_count ({data.get('message_count')}) != sum(counts) ({sum(counts.values())})")

# Tipos obligatorios (field_validation_summary es opcional)
required_types = ['session_summary','baseline_snapshot','pcap_summary',
                  'alerts_summary','collar_summary','correlation_summary']
optional_types = ['field_validation_summary']

for t in required_types:
    if t not in counts:
        errors.append(f'Falta tipo requerido: {t}')

for t in optional_types:
    if t in counts:
        print(f'  [INFO] Tipo opcional presente: {t}')

cow_events = data.get('messages_by_event_type', {}).get('cow_event', [])
for idx, ev in enumerate(cow_events):
    payload = ev.get('payload', {})
    for f in ['batch_id','slot_index','event_id','c2_timestamp','status']:
        if f not in payload:
            errors.append(f'cow_event[{idx}] falta campo: {f}')

if errors:
    for e in errors: print(f'  [FAIL] {e}')
    sys.exit(1)
else:
    print(f'  [PASS] Contrato JSON valido')
    print(f'  [INFO] message_count={data.get("message_count")}, cow_events={len(cow_events)}')
PYEOF

echo "[PASS] Validacion completada."
