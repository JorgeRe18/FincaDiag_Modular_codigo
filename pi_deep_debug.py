"""Debug profundo: verificar PahoPublisher y diferencias de idempotencia."""
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

print("=== Debug 1: Verificar PAHO_OK y publisher ===")
run(c, r"""
export PYTHONPATH=/opt/fincadiag
python3 -c "
from fincadiag.gateway.publisher import PAHO_OK, PahoPublisher
print('PAHO_OK:', PAHO_OK)
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
    spool_dir=Path('/tmp/spool_debug'),
    published_dir=Path('/tmp/pub_debug'),
    dry_run=False
)
p = PahoPublisher(config)
print('PahoPublisher creado OK')
"
""")

print("=== Debug 2: Publicar un mensaje simple con PahoPublisher ===")
run(c, r"""
export PYTHONPATH=/opt/fincadiag
python3 -c "
import time, json
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
    spool_dir=Path('/tmp/spool_debug'),
    published_dir=Path('/tmp/pub_debug'),
    dry_run=False
)

msg = GatewayMessage(
    topic='fincadiag/la_esmeralda/test/debug',
    payload={'test': True, 'ts': '2026-05-29T00:00:00'},
    qos=1,
    retain=False,
    event_type='test',
    event_timestamp='2026-05-29T00:00:00'
)

publisher = PahoPublisher(config)
published = publisher.publish_batch('debug_batch', [msg])
print(f'Publicados: {published}')
"
""", timeout=60)

print("=== Debug 3: Ver mosquitto_sub recibio ===")
run(c, "cat /tmp/mqtt_test_basic.txt 2>/dev/null | head -5 || echo '(no hay archivo)'")

print("=== Debug 4: Comparar jsonl de idempotencia ===")
run(c, r"""
export PYTHONPATH=/opt/fincadiag
TMPDIR=$(mktemp -d)
mkdir -p "$TMPDIR/run1" "$TMPDIR/run2"

python3 -m fincadiag.gateway.runtime \
  --session-dir /var/lib/fincadiag/processed/visits/Visita_18_05_2026/sesiones/TOMA_PM__1PM__Captura_20260518_130005 \
  --topic-root "fincadiag/la_esmeralda" --dry-run \
  --spool-dir "$TMPDIR/spool1" --published-dir "$TMPDIR/run1" >/dev/null 2>&1

python3 -m fincadiag.gateway.runtime \
  --session-dir /var/lib/fincadiag/processed/visits/Visita_18_05_2026/sesiones/TOMA_PM__1PM__Captura_20260518_130005 \
  --topic-root "fincadiag/la_esmeralda" --dry-run \
  --spool-dir "$TMPDIR/spool2" --published-dir "$TMPDIR/run2" >/dev/null 2>&1

for f1 in "$TMPDIR/run1"/*.jsonl; do
  [ -f "$f1" ] || continue
  name=$(basename "$f1")
  f2="$TMPDIR/run2/$name"
  if [ -f "$f2" ]; then
    echo "=== Comparando $name ==="
    python3 - <<PYEOF
import json
with open("$f1") as fh: lines1 = [json.loads(l) for l in fh]
with open("$f2") as fh: lines2 = [json.loads(l) for l in fh]
for i, (a, b) in enumerate(zip(lines1, lines2)):
    if a != b:
        print(f"Linea {i} difiere")
        for k in set(a.keys()) | set(b.keys()):
            if a.get(k) != b.get(k):
                print(f"  {k}: {repr(a.get(k))[:60]} vs {repr(b.get(k))[:60]}")
        break
PYEOF
  fi
done
rm -rf "$TMPDIR"
""")

c.close()
print("=== Terminado ===")
