"""Debug: verificar qué publisher usa drain-only y si conecta al broker."""
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

print("=== Debug: publisher en drain-only ===")
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
    spool_dir=Path('/tmp/spool_dbg'),
    published_dir=Path('/tmp/pub_dbg'),
    dry_run=False
)

runtime = GatewayRuntime(config)
print('Publisher type:', type(runtime.publisher).__name__)
print('Is FileMirrorPublisher?', type(runtime.publisher).__name__ == 'FileMirrorPublisher')
"
""")

print("=== Debug: publicar con drain_spool y verificar ===")
run(c, r"""
rm -rf /tmp/spool_dbg2 /tmp/pub_dbg2 /tmp/mqtt_dbg.txt
mkdir -p /tmp/spool_dbg2 /tmp/pub_dbg2

# Crear spool con mensaje real
cat > /tmp/spool_dbg2/test_batch.jsonl << 'BATCH'
{"topic": "fincadiag/la_esmeralda/session/debug2", "payload": {"batch_id": "dbg2"}, "qos": 1, "retain": false, "source_sample_id": "", "event_type": "session_summary", "event_timestamp": "2026-05-29T00:00:00"}
BATCH

# Iniciar suscriptor
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > /tmp/mqtt_dbg.txt 2>/dev/null &
SUB=$!
sleep 1

# Ejecutar drain-only con mas verbosidad
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
    spool_dir=Path('/tmp/spool_dbg2'),
    published_dir=Path('/tmp/pub_dbg2'),
    dry_run=False
)

runtime = GatewayRuntime(config)
print('Publisher:', type(runtime.publisher).__name__)
result = runtime.drain_spool()
print(f'drained={result.published_count} failed={result.failed_count}')
for note in result.notes:
    print(f'Note: {note}')
"

sleep 2
kill "$SUB" 2>/dev/null || true

echo "--- Mensajes recibidos ---"
cat /tmp/mqtt_dbg.txt
echo "--- Archivos en pub_dbg2 ---"
ls -la /tmp/pub_dbg2/
""")

c.close()
print("=== Terminado ===")
