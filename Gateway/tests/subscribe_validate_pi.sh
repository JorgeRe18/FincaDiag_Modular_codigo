#!/bin/bash
# Prueba 5 (Pi): Validacion semantica con mosquitto_sub
# Objetivo: suscribirse al broker y validar que los mensajes llegan legibles.
# Requiere mosquitto_sub instalado.
# Sirve para Objetivo 4: confirma que el pipeline end-to-end funciona.

set -euo pipefail

SESSION_DIR="${1:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
TOPIC="fincadiag/la_esmeralda/#"
OUTPUT_FILE="/tmp/gateway_subscribe_test.jsonl"

echo "=== Prueba de suscripcion MQTT ==="

# Limpiar archivo previo
rm -f "$OUTPUT_FILE"

# Iniciar suscripcion en segundo plano
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" \
    -h localhost -p 8883 -t "$TOPIC" -v > "$OUTPUT_FILE" 2>/dev/null &
SUB_PID=$!
sleep 2

# Correr gateway en vivo (publica al broker)
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime \
    --session-dir "$SESSION_DIR" \
    --topic-root "fincadiag/la_esmeralda" \
    --mqtt-host localhost --mqtt-port 8883 \
    --tls-enabled \
    --ca-path "$CA" --cert-path "$CERT" --key-path "$KEY" \
    --tls-min-version 1.3 \
    >/dev/null 2>&1

sleep 2
kill "$SUB_PID" 2>/dev/null || true

# Validar resultados
LINE_COUNT=$(wc -l < "$OUTPUT_FILE" 2>/dev/null || echo 0)
echo "  [INFO] Lineas recibidas: $LINE_COUNT"

if [ "$LINE_COUNT" -eq 0 ]; then
    echo "  [FAIL] No se recibieron mensajes"
    exit 1
fi

# Validar que cada linea tiene formato topic + payload JSON
python3 - <<PYEOF
import sys
errors = 0
with open("$OUTPUT_FILE") as f:
    for i, line in enumerate(f, 1):
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) != 2:
            print(f"  [FAIL] Linea {i}: formato invalido")
            errors += 1
            continue
        topic, payload = parts
        if not topic.startswith("fincadiag/la_esmeralda/"):
            print(f"  [FAIL] Linea {i}: topic invalido: {topic}")
            errors += 1
            continue
        try:
            import json
            data = json.loads(payload)
        except json.JSONDecodeError:
            print(f"  [FAIL] Linea {i}: payload no es JSON valido")
            errors += 1

if errors:
    print(f"  [FAIL] {errors} errores encontrados")
    sys.exit(1)
else:
    print(f"  [PASS] {i} mensajes validados correctamente")
PYEOF

echo "[PASS] Prueba de suscripcion completada."
