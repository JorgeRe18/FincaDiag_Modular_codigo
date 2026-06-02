"""Ejecutar exactamente el mismo codigo que funciona (python3 -c) sobre spool de 13 mensajes."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

def run(client, cmd, timeout=60, show=True):
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

print("=== Recrear spool de 13 mensajes ===")
run(c, r"""
SESSION_DIR="/var/lib/fincadiag/processed/visits/Visita_18_05_2026/sesiones/TOMA_PM__1PM__Captura_20260518_130005"
SPOOL_DIR="/tmp/spool_same"
PUB_DIR="/tmp/pub_same"
rm -rf "$SPOOL_DIR" "$PUB_DIR"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

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

echo "Lineas en spool:"
wc -l "$SPOOL_DIR"/*.jsonl
""", timeout=120)

print("=== Ejecutar python3 -c (el que funciona) ===")
run(c, r"""
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
    spool_dir=Path('/tmp/spool_same'),
    published_dir=Path('/tmp/pub_same2'),
    dry_run=False
)

runtime = GatewayRuntime(config)
result = runtime.drain_spool()
print(f'RESULT python3-c: drained={result.published_count} failed={result.failed_count}')
"
""")

print("=== Ejecutar python3 -m (el que falla) ===")
run(c, r"""
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --spool-dir /tmp/spool_same --published-dir /tmp/pub_same3 --drain-only
""")

c.close()
print("=== Terminado ===")
