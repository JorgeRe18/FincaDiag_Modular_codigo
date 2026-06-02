"""Contar mensajes en el spool y verificar por qué drain-only publica solo 1."""
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

print("=== Crear spool y contar mensajes ===")
run(c, r"""
SESSION_DIR=""" + f'"{SESSION}"' + r"""
SPOOL_DIR="/tmp/spool_count"
PUB_DIR="/tmp/pub_count"
rm -rf "$SPOOL_DIR" "$PUB_DIR"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# Detener mosquitto
sudo systemctl stop mosquitto

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

# Contar mensajes en spool
echo "--- Lineas en spool ---"
wc -l "$SPOOL_DIR"/*.jsonl

# Levantar mosquitto
sudo systemctl start mosquitto
""", timeout=120)

print("=== Ejecutar drain-only con output verboso ===")
run(c, r"""
SPOOL_DIR="/tmp/spool_count"
PUB_DIR="/tmp/pub_count2"
mkdir -p "$PUB_DIR"

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
    spool_dir=Path('/tmp/spool_count'),
    published_dir=Path('/tmp/pub_count2'),
    dry_run=False
)

runtime = GatewayRuntime(config)
print('Publisher:', type(runtime.publisher).__name__)

# Verificar spool
from fincadiag.gateway.store import JsonlSpoolStore
spool = JsonlSpoolStore(Path('/tmp/spool_count'))
files = list(spool.root.glob('*.jsonl'))
print(f'Archivos en spool: {len(files)}')
for f in files:
    msgs = spool.load_batch(f)
    print(f'  {f.name}: {len(msgs)} mensajes')

# Drenar
result = runtime.drain_spool()
print(f'drained={result.published_count} failed={result.failed_count}')
for note in result.notes:
    print(f'Note: {note}')
"
""")

c.close()
print("=== Terminado ===")
