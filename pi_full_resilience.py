"""Prueba completa de resiliencia con spool real y mosquitto_sub."""
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

print("=== Resiliencia completa ===")
run(c, r"""
SESSION_DIR=""" + f'"{SESSION}"' + r"""
SPOOL_DIR="/tmp/spool_full"
PUB_DIR="/tmp/pub_full"
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
OUTPUT="/tmp/mqtt_full.txt"

echo "=== Resiliencia completa ==="
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
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > "$OUTPUT" 2>/tmp/mqtt_full.err &
SUB_PID=$!
sleep 2

# 5. Drenar spool
python3 -m fincadiag.gateway.runtime \
    --spool-dir "$SPOOL_DIR" \
    --published-dir "$PUB_DIR" \
    --drain-only

# 6. Esperar
sleep 5
kill "$SUB_PID" 2>/dev/null || true

LINE_COUNT=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
echo "--- Resultados ---"
echo "Mensajes recibidos: $LINE_COUNT"
echo "Errores mosquitto_sub:"
cat /tmp/mqtt_full.err | head -5

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
