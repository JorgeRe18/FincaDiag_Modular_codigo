"""Arreglar ambos problemas: investigar idempotencia + resiliencia con mosquitto_sub."""
import paramiko, os, io

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

# === PARTE 1: Investigar idempotencia ===
print("=== PARTE 1: Investigando no-idempotencia ===")

# Crear script directamente en la Pi via heredoc
investigate_cmd = r"""cat > /tmp/investigate_idemp.sh << 'EOF'
#!/bin/bash
set -euo pipefail
SESSION_DIR="$1"
export PYTHONPATH=/opt/fincadiag
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT
mkdir -p "$TMPDIR/run1" "$TMPDIR/run2"

python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run --spool-dir "$TMPDIR/spool1" --published-dir "$TMPDIR/run1" >/dev/null 2>&1
python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run --spool-dir "$TMPDIR/spool2" --published-dir "$TMPDIR/run2" >/dev/null 2>&1

for f1 in "$TMPDIR/run1"/*.jsonl; do
  [ -f "$f1" ] || continue
  name=$(basename "$f1")
  f2="$TMPDIR/run2/$name"
  if [ ! -f "$f2" ]; then echo "MISSING: $name"; continue; fi
  if diff -q "$f1" "$f2" >/dev/null 2>&1; then
    echo "IDENTICO: $name"
  else
    echo "DIFERENTE: $name"
    python3 - <<PYEOF
import json
with open("$f1") as fh: lines1 = [json.loads(l) for l in fh]
with open("$f2") as fh: lines2 = [json.loads(l) for l in fh]
for i, (a, b) in enumerate(zip(lines1, lines2)):
    if a != b:
        print(f"  Linea {i} difiere")
        def find_diff(d1, d2, path=""):
            keys = set(d1.keys()) | set(d2.keys())
            for k in sorted(keys):
                v1 = d1.get(k); v2 = d2.get(k)
                if isinstance(v1, dict) and isinstance(v2, dict):
                    find_diff(v1, v2, f"{path}.{k}")
                elif v1 != v2:
                    print(f"    {path}.{k}: run1={repr(v1)[:80]} run2={repr(v2)[:80]}")
        find_diff(a, b)
        break
PYEOF
  fi
done
EOF
chmod +x /tmp/investigate_idemp.sh
bash /tmp/investigate_idemp.sh """ + f'"{SESSION}"'

run(c, investigate_cmd, timeout=180)

# === PARTE 2: Resiliencia con mosquitto_sub ===
print("=== PARTE 2: Resiliencia con verificacion por suscripcion ===")

resilience_cmd = r"""cat > /tmp/resilience_sub.sh << 'EOF'
#!/bin/bash
set -euo pipefail
SESSION_DIR="${1:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"
SPOOL_DIR="/tmp/test_spool_resilience"
PUB_DIR="/tmp/test_published_resilience"
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
OUTPUT="/tmp/mqtt_resilience_test.jsonl"

echo "=== Resiliencia (verificacion por suscripcion MQTT) ==="
rm -rf "$SPOOL_DIR"/* "$PUB_DIR"/* "$OUTPUT" 2>/dev/null || true
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# Iniciar suscriptor
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > "$OUTPUT" 2>/dev/null &
SUB_PID=$!
sleep 2

# Parar mosquitto (simular caida)
sudo systemctl stop mosquitto
echo "--- Mosquitto detenido ---"

export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --mqtt-host localhost --mqtt-port 8883 --tls-enabled --ca-path "$CA" --cert-path "$CERT" --key-path "$KEY" --tls-min-version 1.3 --spool-dir "$SPOOL_DIR" --published-dir "$PUB_DIR" >/dev/null 2>&1

SPOOL_COUNT=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
if [ "$SPOOL_COUNT" -eq 0 ]; then
    kill "$SUB_PID" 2>/dev/null || true
    echo "  [FAIL] No spoolo"
    sudo systemctl start mosquitto
    exit 1
fi
echo "  [INFO] Spool: $SPOOL_COUNT"

# Levantar mosquitto
sudo systemctl start mosquitto
echo "--- Mosquitto iniciado ---"
sleep 2

# Drenar spool
python3 -m fincadiag.gateway.runtime --spool-dir "$SPOOL_DIR" --published-dir "$PUB_DIR" --drain-only >/dev/null 2>&1

# Esperar recepcion
sleep 3
kill "$SUB_PID" 2>/dev/null || true

LINE_COUNT=$(wc -l < "$OUTPUT" 2>/dev/null || echo 0)
echo "  [INFO] Mensajes recibidos en suscriptor: $LINE_COUNT"

SPOOL_AFTER=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
if [ "$SPOOL_AFTER" -gt 0 ]; then echo "  [WARN] Spool residual: $SPOOL_AFTER"; else echo "  [PASS] Spool vacio"; fi

if [ "$LINE_COUNT" -gt 0 ]; then
    echo "  [PASS] Mensajes publicados y recibidos: $LINE_COUNT"
else
    echo "  [FAIL] No se recibieron mensajes en el suscriptor"
    exit 1
fi

echo "[PASS] Resiliencia OK."
EOF
chmod +x /tmp/resilience_sub.sh
bash /tmp/resilience_sub.sh """ + f'"{SESSION}"'

run(c, resilience_cmd, timeout=180)

c.close()
print("=== Terminado ===")
