#!/bin/bash
# Prueba 6 (Pi): Validacion de metricas Objetivo 4
# Compara η del motor (correlation_summary.json) contra η reportado por el gateway.
# Tambien valida que serial_events > 0 para sesiones incluidas en el contraste.

set -euo pipefail

SESSION_DIR="${1:-}"
if [ -z "$SESSION_DIR" ]; then
    echo "Uso: $0 <ruta_sesion_procesada>"
    exit 1
fi

CORR_FILE="$SESSION_DIR/correlation_summary.json"

echo "=== Validacion Objetivo 4: $SESSION_DIR ==="

# 1. Verificar que correlation_summary.json existe
if [ ! -f "$CORR_FILE" ]; then
    echo "[FAIL] No existe correlation_summary.json"
    exit 1
fi

# 2. Correr gateway dry-run
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run >/dev/null 2>&1 || {
    echo "[FAIL] Gateway dry-run fallo"
    exit 1
}

# 3. Extraer metricas del motor
READABLE=$(ls data/gateway/published/*.readable.json | tail -1)

python3 - <<PYEOF
import json, sys

with open("$CORR_FILE") as f:
    motor = json.load(f)

with open("$READABLE") as f:
    gw = json.load(f)

gw_corr = None
for msg in gw.get('messages_by_event_type', {}).get('correlation_summary', []):
    gw_corr = msg.get('payload', {})
    break

if not gw_corr:
    print('[FAIL] correlation_summary no encontrado en salida del gateway')
    sys.exit(1)

motor_eta = motor.get('eta_extraccion')
gw_eta = gw_corr.get('eta_extraccion_pct')
motor_matches = motor.get('matched_events', -1)
gw_matches = gw_corr.get('matches', -1)
serial_events = motor.get('serial_events', 0)

print(f'  Motor:   eta={motor_eta}, matched={motor_matches}, serial_events={serial_events}')
print(f'  Gateway: eta={gw_eta}, matches={gw_matches}')

errors = []
if serial_events == 0:
    errors.append('serial_events=0 (sesion no apta para contraste Objetivo 4)')
if motor_eta is None:
    errors.append('Motor no reporta eta')
if gw_eta is None:
    errors.append('Gateway no reporta eta')
if motor_eta is not None and gw_eta is not None:
    if abs(float(motor_eta) - float(gw_eta)) > 0.01:
        errors.append(f'Divergencia eta: motor={motor_eta} vs gateway={gw_eta}')
if motor_matches >= 0 and gw_matches >= 0:
    if motor_matches != gw_matches:
        errors.append(f'Divergencia matches: motor={motor_matches} vs gateway={gw_matches}')

if errors:
    for e in errors: print(f'  [FAIL] {e}')
    sys.exit(1)
else:
    print('  [PASS] Metricas consistentes')
PYEOF

echo "[PASS] Validacion Objetivo 4 completada."
