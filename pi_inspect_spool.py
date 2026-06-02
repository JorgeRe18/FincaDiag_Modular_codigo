"""Inspeccionar el contenido del spool creado en la prueba de resiliencia."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]
SESSION = "/var/lib/fincadiag/processed/visits/Visita_18_05_2026/sesiones/TOMA_PM__1PM__Captura_20260518_130005"

def run(client, cmd, timeout=120, show=True):
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

print("=== Crear spool con broker caido y verificar formato ===")
run(c, r"""
SESSION_DIR=""" + f'"{SESSION}"' + r"""
SPOOL_DIR="/tmp/spool_inspect"
PUB_DIR="/tmp/pub_inspect"
rm -rf "$SPOOL_DIR" "$PUB_DIR"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# Detener mosquitto
sudo systemctl stop mosquitto
echo "--- Mosquitto detenido ---"

# Ejecutar gateway
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

# Verificar spool
echo "--- Archivos en spool ---"
ls -la "$SPOOL_DIR/"

echo "--- Contenido del spool ---"
for f in "$SPOOL_DIR"/*.jsonl; do
  [ -f "$f" ] || continue
  echo "File: $f"
  head -3 "$f"
  echo "---"
done

# Verificar mosquitto logs
echo "--- Mosquitto logs ---"
sudo journalctl -u mosquitto --since '2 minutes ago' --no-pager | tail -10

# Levantar mosquitto
sudo systemctl start mosquitto
""", timeout=120)

print("=== Probar drain-only manual del spool ===")
run(c, r"""
SPOOL_DIR="/tmp/spool_inspect"
PUB_DIR="/tmp/pub_inspect2"
mkdir -p "$PUB_DIR"

# Iniciar suscriptor
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
rm -f /tmp/mqtt_inspect.txt
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > /tmp/mqtt_inspect.txt 2>/dev/null &
SUB=$!
sleep 1

# Drenar
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --spool-dir "$SPOOL_DIR" --published-dir "$PUB_DIR" --drain-only

sleep 2
kill "$SUB" 2>/dev/null || true

echo "--- Mensajes recibidos ---"
cat /tmp/mqtt_inspect.txt
echo "---"
""")

c.close()
print("=== Terminado ===")
