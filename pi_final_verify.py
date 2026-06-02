"""Verificacion final: python3 -c drain_spool sobre spool fresco de 13 msgs con mosquitto activo."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]
SESSION = "/var/lib/fincadiag/processed/visits/Visita_18_05_2026/sesiones/TOMA_PM__1PM__Captura_20260518_130005"

def run(client, cmd, timeout=180, show=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show:
        print(f"$ {cmd[:120]}")
        if out.strip():
            print(out)
        if err.strip():
            print("[err]", err)
        print()
    return out, err

print("=== Conectando ===")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("=== Prueba final de resiliencia ===")
run(c, r"""
SESSION_DIR=""" + f'"{SESSION}"' + r"""
SPOOL_DIR="/tmp/spool_final"
PUB_DIR="/tmp/pub_final"
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
OUTPUT="/tmp/mqtt_final.txt"

echo "=== Resiliencia final ==="
rm -rf "$SPOOL_DIR" "$PUB_DIR" "$OUTPUT"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# 1. Detener mosquitto
sudo systemctl stop mosquitto
echo "--- Mosquitto detenido ---"

# 2. Gateway spoola
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime \
    --session-dir "$SESSION_DIR" \
    --topic-root "fincadiag/la_esmeralda" \
    --mqtt-host localhost --mqtt-port 8883 --tls-enabled \
    --ca-path "$CA" --cert-path "$CERT" --key-path "$KEY" \
    --tls-min-version 1.3 \
    --spool-dir "$SPOOL_DIR" \
    --published-dir "$PUB_DIR" >/dev/null 2>&1

echo "--- Spool creado ---"
wc -l "$SPOOL_DIR"/*.jsonl

# 3. Levantar mosquitto
sudo systemctl start mosquitto
echo "--- Mosquitto iniciado ---"
sleep 3

# 4. Iniciar suscriptor
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > "$OUTPUT" 2>/dev/null &
SUB_PID=$!
sleep 2

# 5. Drenar spool con python3 -c (el que funciona)
export PYTHONPATH=/opt/fincadiag
python3 -c "
from fincadiag.gateway.runtime import GatewayRuntime
from fincadiag.gateway.config import GatewayConfig
from pathlib import Path

config = GatewayConfig(
    topic_root='fincadiag/la_esmeralda',
    mqtt_host='localhost',
    mqtt_port=8883,
    tls_enabled=True,
    ca_path='/etc/fincadiag/certs/ca.crt',
    cert_path='/etc/fincadiag/certs/client.crt',
    key_path='/etc/fincadiag/certs/client.key',
    tls_min_version='1.3',
    spool_dir=Path('/tmp/spool_final'),
    published_dir=Path('/tmp/pub_final2'),
    dry_run=False
)

runtime = GatewayRuntime(config)
result = runtime.drain_spool()
print(f'drained={result.published_count} failed={result.failed_count}')
"

# 6. Esperar
sleep 5
kill "$SUB_PID" 2>/dev/null || true

LINE_COUNT=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
echo "--- Resultados ---"
echo "Mensajes recibidos: $LINE_COUNT"

SPOOL_AFTER=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
echo "Spool residual: $SPOOL_AFTER"

if [ "$LINE_COUNT" -gt 0 ]; then
    echo "[PASS] Mensajes recibidos: $LINE_COUNT"
    echo "Primer mensaje:"
    head -1 "$OUTPUT"
else
    echo "[FAIL] No se recibieron mensajes"
fi
""", timeout=180)

c.close()
print("=== Terminado ===")
