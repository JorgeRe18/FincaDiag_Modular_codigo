"""Re-ejecutar pruebas Pi con publisher corregido y aislamiento completo."""
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

# Verificar que publisher.py tiene el fix
print("=== Verificando publisher.py corregido ===")
run(c, "grep -n 'loop_start' /opt/fincadiag/fincadiag/gateway/publisher.py")

# Script de resiliencia con mosquitto_sub post-recovery + aislamiento
print("=== Resiliencia corregida (suscriptor post-recovery) ===")
resilience_cmd = r"""cat > /tmp/resilience_final.sh << 'EOF'
#!/bin/bash
set -euo pipefail
SESSION_DIR="${1:-}"
SPOOL_DIR="/tmp/test_spool_final"
PUB_DIR="/tmp/test_pub_final"
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
OUTPUT="/tmp/mqtt_final.txt"

echo "=== Resiliencia final ==="
rm -rf "$SPOOL_DIR"/* "$PUB_DIR"/* "$OUTPUT" 2>/dev/null || true
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# 1. Detener mosquitto
sudo systemctl stop mosquitto
echo "--- Mosquitto detenido ---"

# 2. Gateway spoola (broker caido)
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime \
    --session-dir "$SESSION_DIR" \
    --topic-root "fincadiag/la_esmeralda" \
    --mqtt-host localhost --mqtt-port 8883 --tls-enabled \
    --ca-path "$CA" --cert-path "$CERT" --key-path "$KEY" \
    --tls-min-version 1.3 \
    --spool-dir "$SPOOL_DIR" \
    --published-dir "$PUB_DIR" >/dev/null 2>&1

SPOOL_COUNT=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
if [ "$SPOOL_COUNT" -eq 0 ]; then
    echo "  [FAIL] No spoolo"
    sudo systemctl start mosquitto
    exit 1
fi
echo "  [INFO] Spool: $SPOOL_COUNT"

# 3. Levantar mosquitto
sudo systemctl start mosquitto
echo "--- Mosquitto iniciado ---"
sleep 2

# 4. Iniciar suscriptor (broker ya activo)
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > "$OUTPUT" 2>/dev/null &
SUB_PID=$!
sleep 1

# 5. Drenar spool
python3 -m fincadiag.gateway.runtime \
    --spool-dir "$SPOOL_DIR" \
    --published-dir "$PUB_DIR" \
    --drain-only >/dev/null 2>&1

# 6. Esperar y verificar
sleep 3
kill "$SUB_PID" 2>/dev/null || true

LINE_COUNT=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
echo "  [INFO] Mensajes recibidos: $LINE_COUNT"

SPOOL_AFTER=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
if [ "$SPOOL_AFTER" -gt 0 ]; then echo "  [WARN] Spool residual: $SPOOL_AFTER"; else echo "  [PASS] Spool vacio"; fi

if [ "$LINE_COUNT" -gt 0 ]; then
    echo "  [PASS] Mensajes publicados y recibidos: $LINE_COUNT"
else
    echo "  [FAIL] No se recibieron mensajes"
    exit 1
fi

echo "[PASS] Resiliencia OK."
EOF
chmod +x /tmp/resilience_final.sh
bash /tmp/resilience_final.sh """ + f'"{SESSION}"'

run(c, resilience_cmd, timeout=180)

# Idempotencia aislada
print("=== Idempotencia aislada ===")
run(c, f"bash /tmp/idempotency_isolated.sh {SESSION}", timeout=180)

# Objetivo 4
print("=== Objetivo 4 ===")
run(c, f"bash /opt/fincadiag/Gateway/tests/validate_objective4_pi.sh {SESSION}")

c.close()
print("=== Terminado ===")
