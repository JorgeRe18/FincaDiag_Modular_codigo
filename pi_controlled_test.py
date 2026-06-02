"""Prueba controlada: drain-only sin mosquitto_sub para aislar el problema."""
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

print("=== Test controlado ===")
run(c, r"""
SESSION_DIR=""" + f'"{SESSION}"' + r"""
SPOOL_DIR="/tmp/spool_ctrl"
PUB_DIR="/tmp/pub_ctrl"
rm -rf "$SPOOL_DIR" "$PUB_DIR"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# 1. Crear spool con broker caido
sudo systemctl stop mosquitto
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime \
    --session-dir "$SESSION_DIR" \
    --topic-root "fincadiag/la_esmeralda" \
    --mqtt-host localhost --mqtt-port 8883 --tls-enabled \
    --ca-path /etc/fincadiag/certs/ca.crt \
    --cert-path /etc/fincadiag/certs/client.crt \
    --key-path /etc/fincadiag/certs/client.key \
    --tls-min-version 1.3 \
    --spool-dir "$SPOOL_DIR" \
    --published-dir "$PUB_DIR" >/dev/null 2>&1

sudo systemctl start mosquitto
sleep 2

echo "--- Spool antes del drain ---"
wc -l "$SPOOL_DIR"/*.jsonl

# 2. Drain-only SIN suscriptor
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --spool-dir "$SPOOL_DIR" --published-dir "$PUB_DIR" --drain-only

echo "--- Spool despues del drain ---"
ls -la "$SPOOL_DIR/"
""", timeout=120)

print("=== Verificar publicacion con mosquitto_sub posterior ===")
run(c, r"""
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"

# Verificar si hay mensajes en mosquitto (usando mosquitto_sub por 2 segundos)
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v -C 100 > /tmp/mqtt_ctrl.txt 2>/dev/null &
SUB=$!
sleep 2
kill "$SUB" 2>/dev/null || true

echo "--- Mensajes capturados ---"
wc -l /tmp/mqtt_ctrl.txt
echo "--- Primeros 3 mensajes ---"
head -3 /tmp/mqtt_ctrl.txt
""")

c.close()
print("=== Terminado ===")
