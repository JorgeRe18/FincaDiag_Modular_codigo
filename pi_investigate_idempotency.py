"""Investigar no-idempotencia del gateway en Pi: comparar dos corridas del mismo .jsonl."""
import paramiko, os, json, difflib

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

# Script para correr dos veces y comparar
script = r"""#!/bin/bash
set -euo pipefail
SESSION_DIR="$1"
export PYTHONPATH=/opt/fincadiag
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT
mkdir -p "$TMPDIR/run1" "$TMPDIR/run2"

# Run 1
python3 -m fincadiag.gateway.runtime \
  --session-dir "$SESSION_DIR" \
  --topic-root "fincadiag/la_esmeralda" \
  --dry-run \
  --spool-dir "$TMPDIR/spool1" \
  --published-dir "$TMPDIR/run1" >/dev/null 2>&1

# Run 2
python3 -m fincadiag.gateway.runtime \
  --session-dir "$SESSION_DIR" \
  --topic-root "fincadiag/la_esmeralda" \
  --dry-run \
  --spool-dir "$TMPDIR/spool2" \
  --published-dir "$TMPDIR/run2" >/dev/null 2>&1

# Comparar
for f1 in "$TMPDIR/run1"/*.jsonl; do
  [ -f "$f1" ] || continue
  name=$(basename "$f1")
  f2="$TMPDIR/run2/$name"
  if [ ! -f "$f2" ]; then echo "MISSING: $name"; continue; fi
  if diff -q "$f1" "$f2" >/dev/null 2>&1; then
    echo "IDENTICO: $name"
  else
    echo "DIFERENTE: $name"
    # Mostrar diferencias
    python3 - <<PYEOF
import json
with open("$f1") as fh: lines1 = [json.loads(l) for l in fh]
with open("$f2") as fh: lines2 = [json.loads(l) for l in fh]
for i, (a, b) in enumerate(zip(lines1, lines2)):
    if a != b:
        print(f"  Linea {i} difiere")
        # Encontrar campos que difieren
        def find_diff(d1, d2, path=""):
            keys = set(d1.keys()) | set(d2.keys())
            for k in sorted(keys):
                v1 = d1.get(k)
                v2 = d2.get(k)
                if isinstance(v1, dict) and isinstance(v2, dict):
                    find_diff(v1, v2, f"{path}.{k}")
                elif v1 != v2:
                    print(f"    {path}.{k}: run1={repr(v1)[:60]} run2={repr(v2)[:60]}")
        find_diff(a, b)
        break
PYEOF
  fi
done
"""

with open("C:\\Users\\jorge\\OneDrive\\Documentos\\FincaDiag_Modular\\tmp_idemp.sh", "w") as f:
    f.write(script)

sftp = c.open_sftp()
sftp.put("C:\\Users\\jorge\\OneDrive\\Documentos\\FincaDiag_Modular\\tmp_idemp.sh", "/tmp/idemp_investigate.sh")
sftp.close()
run(c, "chmod +x /tmp/idemp_investigate.sh", show=False)

print("=== Investigando diferencias ===")
run(c, f"bash /tmp/idemp_investigate.sh {SESSION}", timeout=180)

c.close()
print("=== Terminado ===")
