"""Re-ejecutar suite completa de pruebas Pi con python3 -c para drain-only."""
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

# Helper script para drain-only confiable
DRAIN_SCRIPT = r"""
cat > /tmp/drain_spool.py << 'EOF'
#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, '/opt/fincadiag')
from fincadiag.gateway.runtime import GatewayRuntime
from fincadiag.gateway.config import GatewayConfig

config = GatewayConfig(
    topic_root='fincadiag/la_esmeralda',
    mqtt_host='localhost',
    mqtt_port=8883,
    tls_enabled=True,
    ca_path='/etc/fincadiag/certs/ca.crt',
    cert_path='/etc/fincadiag/certs/client.crt',
    key_path='/etc/fincadiag/certs/client.key',
    tls_min_version='1.3',
    spool_dir=Path(sys.argv[1]),
    published_dir=Path(sys.argv[2]),
    dry_run=False
)
runtime = GatewayRuntime(config)
result = runtime.drain_spool()
print(f'drained={result.published_count} failed={result.failed_count}')
EOF
chmod +x /tmp/drain_spool.py
"""
run(c, DRAIN_SCRIPT)

print("\n=== [1/4] Resiliencia ===")
run(c, r"""
SESSION_DIR=""" + f'"{SESSION}"' + r"""
SPOOL_DIR="/tmp/spool_suite"
PUB_DIR="/tmp/pub_suite"
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
OUTPUT="/tmp/mqtt_suite.txt"

rm -rf "$SPOOL_DIR" "$PUB_DIR" "$OUTPUT"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

sudo systemctl stop mosquitto
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
echo "  [INFO] Spool: $SPOOL_COUNT"

sudo systemctl start mosquitto
sleep 3

mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > "$OUTPUT" 2>/dev/null &
SUB=$!
sleep 2

python3 /tmp/drain_spool.py "$SPOOL_DIR" "$PUB_DIR"

sleep 3
kill "$SUB" 2>/dev/null || true

LINE_COUNT=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
SPOOL_AFTER=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)

if [ "$SPOOL_AFTER" -eq 0 ] && [ "$LINE_COUNT" -gt 0 ]; then
    echo "  [PASS] Resiliencia OK (recibidos=$LINE_COUNT)"
else
    echo "  [FAIL] Spool=$SPOOL_AFTER recibidos=$LINE_COUNT"
fi
""", timeout=180)

print("\n=== [2/4] Idempotencia ===")
run(c, r"""
SESSION_DIR=""" + f'"{SESSION}"' + r"""
SPOOL1="/tmp/spool_idem1"
PUB1="/tmp/pub_idem1"
SPOOL2="/tmp/spool_idem2"
PUB2="/tmp/pub_idem2"
rm -rf "$SPOOL1" "$PUB1" "$SPOOL2" "$PUB2"
mkdir -p "$SPOOL1" "$PUB1" "$SPOOL2" "$PUB2"

export PYTHONPATH=/opt/fincadiag
# Run 1
python3 -m fincadiag.gateway.runtime \
    --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run \
    --spool-dir "$SPOOL1" --published-dir "$PUB1" >/dev/null 2>&1
# Run 2
python3 -m fincadiag.gateway.runtime \
    --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run \
    --spool-dir "$SPOOL2" --published-dir "$PUB2" >/dev/null 2>&1

echo "--- Comparando MD5 ---"
MATCH=0
DIFF=0
for f1 in "$PUB1"/*.jsonl; do
  [ -f "$f1" ] || continue
  name=$(basename "$f1")
  f2="$PUB2/$name"
  if [ -f "$f2" ]; then
    md5_1=$(md5sum "$f1" | awk '{print $1}')
    md5_2=$(md5sum "$f2" | awk '{print $1}')
    if [ "$md5_1" = "$md5_2" ]; then
      echo "  [MATCH] $name"
      MATCH=$((MATCH+1))
    else
      echo "  [MISMATCH] $name"
      DIFF=$((DIFF+1))
    fi
  fi
done
echo "Coinciden: $MATCH, Difieren: $DIFF"
if [ "$DIFF" -eq 0 ]; then
    echo "  [PASS] Idempotencia OK"
else
    echo "  [FAIL] Idempotencia fallida"
fi
""", timeout=120)

print("\n=== [3/4] Objetivo 4 ===")
run(c, f"bash /opt/fincadiag/Gateway/tests/validate_objective4_pi.sh {SESSION}")

print("\n=== [4/4] TLS Handshake ===")
run(c, "bash /opt/fincadiag/Gateway/tests/tls_handshake_pi.sh")

c.close()
print("\n=== Suite terminada ===")
