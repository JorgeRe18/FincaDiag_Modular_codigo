#!/bin/bash
# Prueba de resiliencia con spool aislado
set -euo pipefail
SESSION_DIR="${1:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"
SPOOL_DIR="/tmp/test_spool_resilience"
PUB_DIR="/tmp/test_published_resilience"

echo "=== Prueba de resiliencia (broker caido) ==="
sudo rm -rf "$SPOOL_DIR"/* "$PUB_DIR"/* 2>/dev/null || true
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# Parar mosquitto
sudo systemctl stop mosquitto
echo "--- Mosquitto detenido ---"

export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime \
    --session-dir "$SESSION_DIR" \
    --topic-root "fincadiag/la_esmeralda" \
    --mqtt-host localhost --mqtt-port 8883 \
    --tls-enabled \
    --ca-path /etc/fincadiag/certs/ca.crt \
    --cert-path /etc/fincadiag/certs/client.crt \
    --key-path /etc/fincadiag/certs/client.key \
    --tls-min-version 1.3 \
    --spool-dir "$SPOOL_DIR" \
    --published-dir "$PUB_DIR" >/dev/null 2>&1

SPOOL_COUNT=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
if [ "$SPOOL_COUNT" -eq 0 ]; then
    echo "  [FAIL] No se spoolo nada (broker caido)"
    sudo systemctl start mosquitto
    exit 1
fi
echo "  [INFO] Archivos en spool: $SPOOL_COUNT"

# Levantar mosquitto
sudo systemctl start mosquitto
echo "--- Mosquitto iniciado ---"
sleep 2

# Drenar spool con --drain-only
python3 -m fincadiag.gateway.runtime \
    --spool-dir "$SPOOL_DIR" \
    --published-dir "$PUB_DIR" \
    --drain-only \
    >/dev/null 2>&1

SPOOL_COUNT_AFTER=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
if [ "$SPOOL_COUNT_AFTER" -gt 0 ]; then
    echo "  [WARN] Spool no vacio despues de recovery ($SPOOL_COUNT_AFTER archivos)"
else
    echo "  [PASS] Spool vacio despues de recovery"
fi

PUB_COUNT=$(find "$PUB_DIR" -name "*.jsonl" 2>/dev/null | wc -l)
if [ "$PUB_COUNT" -gt 0 ]; then
    echo "  [PASS] Archivos publicados generados: $PUB_COUNT"
else
    echo "  [FAIL] No hay archivos publicados"
    exit 1
fi

echo "[PASS] Prueba de resiliencia completada."
