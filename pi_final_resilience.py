"""Ejecutar prueba de resiliencia corregida en Pi via SSH."""
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

# Crear script resilience_sub2.sh en Pi usando Python remoto
remote_script = r"""#!/bin/bash
set -euo pipefail
SESSION_DIR="${1:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"
SPOOL_DIR="/tmp/test_spool_resilience2"
PUB_DIR="/tmp/test_published_resilience2"
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
OUTPUT="/tmp/mqtt_resilience_test2.jsonl"

echo "=== Resiliencia (suscriptor reiniciado post-recovery) ==="
rm -rf "$SPOOL_DIR"/* "$PUB_DIR"/* "$OUTPUT" 2>/dev/null || true
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# Parar mosquitto
sudo systemctl stop mosquitto
echo "--- Mosquitto detenido ---"

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

# Levantar mosquitto
sudo systemctl start mosquitto
echo "--- Mosquitto iniciado ---"
sleep 2

# Iniciar suscriptor AHORA (broker ya activo)
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > "$OUTPUT" 2>/dev/null &
SUB_PID=$!
sleep 1

# Drenar spool
python3 -m fincadiag.gateway.runtime \
    --spool-dir "$SPOOL_DIR" \
    --published-dir "$PUB_DIR" \
    --drain-only >/dev/null 2>&1

# Esperar recepcion
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
"""

# Escribir script remoto usando sftp (BytesIO para formato Unix)
import io
bio = io.BytesIO(remote_script.encode("utf-8"))
sftp = c.open_sftp()
sftp.putfo(bio, "/tmp/resilience_sub2.sh")
sftp.close()

run(c, "chmod +x /tmp/resilience_sub2.sh")

print("=== Ejecutando resiliencia corregida ===")
run(c, f"bash /tmp/resilience_sub2.sh {SESSION}", timeout=180)

c.close()
print("=== Terminado ===")
