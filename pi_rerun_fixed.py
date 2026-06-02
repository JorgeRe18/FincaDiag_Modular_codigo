"""Subir scripts corregidos en formato Unix y re-ejecutar pruebas en Pi."""
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

# Script 1: validate_schema_fixed
validate_script = r'''#!/bin/bash
set -euo pipefail
SESSION_DIR="${1:-}"
if [ -z "$SESSION_DIR" ]; then echo "Uso: $0 <ruta>"; exit 1; fi
echo "=== Validando: $SESSION_DIR ==="
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run >/dev/null 2>&1 || { echo "[FAIL] dry-run"; exit 1; }
JSON_FILE=$(ls data/gateway/published/*.readable.json | tail -1)
if [ -z "$JSON_FILE" ]; then echo "[FAIL] No .readable.json"; exit 1; fi
echo "Archivo: $JSON_FILE"
python3 - <<PYEOF
import json, sys
with open("$JSON_FILE") as f: data = json.load(f)
errors = []
for field in ['batch_name','message_count','counts_by_event_type','messages_by_event_type']:
    if field not in data: errors.append(f'Falta: {field}')
counts = data.get('counts_by_event_type', {})
if data.get('message_count') != sum(counts.values()):
    errors.append("count mismatch")
required = ['session_summary','baseline_snapshot','pcap_summary','alerts_summary','collar_summary','correlation_summary']
for t in required:
    if t not in counts: errors.append(f'Falta tipo: {t}')
if 'field_validation_summary' in counts: print("  [INFO] field_validation_summary presente")
cow = data.get('messages_by_event_type', {}).get('cow_event', [])
for i, ev in enumerate(cow):
    p = ev.get('payload', {})
    for f in ['batch_id','slot_index','event_id','c2_timestamp','status']:
        if f not in p: errors.append(f'cow[{i}] falta {f}')
if errors:
    for e in errors: print(f'  [FAIL] {e}')
    sys.exit(1)
else:
    print(f"  [PASS] Contrato OK | msg={data.get('message_count')} cow={len(cow)}")
PYEOF
echo "[PASS] Validacion OK."
'''

# Script 2: resilience_isolated
resilience_script = r'''#!/bin/bash
set -euo pipefail
SESSION_DIR="${1:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"
SPOOL_DIR="/tmp/test_spool_resilience"
PUB_DIR="/tmp/test_published_resilience"
echo "=== Resiliencia (broker caido) ==="
rm -rf "$SPOOL_DIR"/* "$PUB_DIR"/* 2>/dev/null || true
mkdir -p "$SPOOL_DIR" "$PUB_DIR"
sudo systemctl stop mosquitto
echo "--- Mosquitto detenido ---"
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --mqtt-host localhost --mqtt-port 8883 --tls-enabled --ca-path /etc/fincadiag/certs/ca.crt --cert-path /etc/fincadiag/certs/client.crt --key-path /etc/fincadiag/certs/client.key --tls-min-version 1.3 --spool-dir "$SPOOL_DIR" --published-dir "$PUB_DIR" >/dev/null 2>&1
SPOOL_COUNT=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
if [ "$SPOOL_COUNT" -eq 0 ]; then echo "  [FAIL] No spoolo"; sudo systemctl start mosquitto; exit 1; fi
echo "  [INFO] Spool: $SPOOL_COUNT"
sudo systemctl start mosquitto
echo "--- Mosquitto iniciado ---"
sleep 2
python3 -m fincadiag.gateway.runtime --spool-dir "$SPOOL_DIR" --published-dir "$PUB_DIR" --drain-only >/dev/null 2>&1
SPOOL_AFTER=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
if [ "$SPOOL_AFTER" -gt 0 ]; then echo "  [WARN] Spool residual: $SPOOL_AFTER"; else echo "  [PASS] Spool vacio"; fi
PUB_COUNT=$(find "$PUB_DIR" -name "*.jsonl" 2>/dev/null | wc -l)
if [ "$PUB_COUNT" -gt 0 ]; then echo "  [PASS] Publicados: $PUB_COUNT"; else echo "  [FAIL] Sin publicados"; exit 1; fi
echo "[PASS] Resiliencia OK."
'''

# Script 3: idempotency_isolated
idemp_script = r'''#!/bin/bash
set -euo pipefail
SESSION_DIR="${1:-}"
if [ -z "$SESSION_DIR" ]; then echo "Uso: $0 <ruta>"; exit 1; fi
export PYTHONPATH=/opt/fincadiag
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT
SPOOL1="$TMPDIR/spool1"; PUB1="$TMPDIR/pub1"
SPOOL2="$TMPDIR/spool2"; PUB2="$TMPDIR/pub2"
mkdir -p "$SPOOL1" "$PUB1" "$SPOOL2" "$PUB2"
echo "=== Idempotencia (aislado) ==="
python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run --spool-dir "$SPOOL1" --published-dir "$PUB1" >/dev/null 2>&1 || { echo "[FAIL] Run 1"; exit 1; }
for f in "$PUB1"/*.jsonl; do [ -f "$f" ] && md5sum "$f" > "$TMPDIR/run1_$(basename "$f").md5"; done
python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run --spool-dir "$SPOOL2" --published-dir "$PUB2" >/dev/null 2>&1 || { echo "[FAIL] Run 2"; exit 1; }
for f in "$PUB2"/*.jsonl; do [ -f "$f" ] && md5sum "$f" > "$TMPDIR/run2_$(basename "$f").md5"; done
MATCH=0; MISMATCH=0
for f1 in "$TMPDIR"/run1_*.md5; do
  [ -f "$f1" ] || continue
  name=$(basename "$f1" | sed 's/^run1_/run2_/')
  f2="$TMPDIR/$name"
  if [ -f "$f2" ]; then
    if diff -q "$f1" "$f2" >/dev/null 2>&1; then MATCH=$((MATCH+1)); else MISMATCH=$((MISMATCH+1)); echo "  [MISMATCH] $name"; fi
  else MISMATCH=$((MISMATCH+1)); echo "  [MISSING] $name"; fi
done
for f2 in "$TMPDIR"/run2_*.md5; do
  [ -f "$f2" ] || continue
  name=$(basename "$f2" | sed 's/^run2_/run1_/')
  f1="$TMPDIR/$name"
  if [ ! -f "$f1" ]; then MISMATCH=$((MISMATCH+1)); echo "  [EXTRA] $(basename $f2)"; fi
done
echo "  Coinciden: $MATCH, Difieren: $MISMATCH"
if [ "$MISMATCH" -eq 0 ]; then echo "[PASS] Idempotencia OK"; exit 0; else echo "[FAIL] $MISMATCH difieren"; exit 1; fi
'''

# Subir scripts via sftp (usando BytesIO para formato Unix)
sftp = c.open_sftp()
for name, content in [("/tmp/validate_schema_fixed.sh", validate_script),
                      ("/tmp/resilience_isolated.sh", resilience_script),
                      ("/tmp/idempotency_isolated.sh", idemp_script)]:
    bio = io.BytesIO(content.encode("utf-8"))
    sftp.putfo(bio, name)
    print(f"  Subido: {name}")
sftp.close()

# Dar permisos
run(c, "chmod +x /tmp/validate_schema_fixed.sh /tmp/resilience_isolated.sh /tmp/idempotency_isolated.sh", show=False)

# Verificar formato
run(c, "file /tmp/validate_schema_fixed.sh /tmp/resilience_isolated.sh /tmp/idempotency_isolated.sh")

# Ejecutar pruebas
print("=== [1/5] Schema corregido ===")
run(c, f"bash /tmp/validate_schema_fixed.sh {SESSION}")

print("=== [2/5] TLS ===")
run(c, "bash /opt/fincadiag/Gateway/tests/tls_handshake_pi.sh")

print("=== [3/5] Resiliencia aislado ===")
run(c, f"bash /tmp/resilience_isolated.sh {SESSION}")

print("=== [4/5] Idempotencia aislado ===")
run(c, f"bash /tmp/idempotency_isolated.sh {SESSION}")

print("=== [5/5] Objetivo 4 ===")
run(c, f"bash /opt/fincadiag/Gateway/tests/validate_objective4_pi.sh {SESSION}")

c.close()
print("=== Terminado ===")
