"""Verificar si PahoPublisher realmente publica al broker con mosquitto_sub."""
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

print("=== Test: mosquitto_sub + PahoPublisher directo ===")
run(c, r"""
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
rm -f /tmp/mqtt_verify.txt

# Iniciar suscriptor
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/test/#" -v > /tmp/mqtt_verify.txt 2>/dev/null &
SUB=$!
sleep 2

# Publicar con PahoPublisher via Python
export PYTHONPATH=/opt/fincadiag
python3 -c "
from fincadiag.gateway.publisher import PahoPublisher
from fincadiag.gateway.config import GatewayConfig
from fincadiag.gateway.models import GatewayMessage
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
    spool_dir=Path('/tmp/spool_v'),
    published_dir=Path('/tmp/pub_v'),
    dry_run=False
)

msg = GatewayMessage(
    topic='fincadiag/la_esmeralda/test/verify',
    payload={'test': 'paho_direct'},
    qos=1,
    retain=False,
    event_type='test',
    event_timestamp='2026-05-29T00:00:00'
)

publisher = PahoPublisher(config)
published = publisher.publish_batch('verify_batch', [msg])
print(f'Published: {published}')
"

# Esperar y verificar
sleep 2
kill "$SUB" 2>/dev/null || true

echo "--- Mensajes recibidos ---"
cat /tmp/mqtt_verify.txt
echo "--- Fin ---"
""")

print("=== Test: drain-only con spool real y suscriptor ===")
run(c, r"""
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
rm -rf /tmp/spool_d /tmp/pub_d /tmp/mqtt_d.txt
mkdir -p /tmp/spool_d /tmp/pub_d

# Crear spool con mensaje real
cat > /tmp/spool_d/test.jsonl << 'BATCH'
{"topic": "fincadiag/la_esmeralda/session/drain_test", "payload": {"batch_id": "drain", "status": "ok"}, "qos": 1, "retain": false, "source_sample_id": "", "event_type": "session_summary", "event_timestamp": "2026-05-29T00:00:00"}
BATCH

# Iniciar suscriptor
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > /tmp/mqtt_d.txt 2>/dev/null &
SUB=$!
sleep 1

# Drenar
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --spool-dir /tmp/spool_d --published-dir /tmp/pub_d --drain-only

# Esperar
sleep 2
kill "$SUB" 2>/dev/null || true

echo "--- Mensajes recibidos ---"
cat /tmp/mqtt_d.txt
echo "--- Spool despues ---"
ls -la /tmp/spool_d/
""")

c.close()
print("=== Terminado ===")
