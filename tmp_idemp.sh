#!/bin/bash
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
