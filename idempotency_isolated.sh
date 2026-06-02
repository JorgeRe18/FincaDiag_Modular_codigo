#!/bin/bash
# Prueba de idempotencia con directorios aislados
set -euo pipefail
SESSION_DIR="${1:-}"
if [ -z "$SESSION_DIR" ]; then
    echo "Uso: $0 <ruta_sesion_procesada>"
    exit 1
fi

export PYTHONPATH=/opt/fincadiag
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

SPOOL1="$TMPDIR/spool1"
PUB1="$TMPDIR/published1"
SPOOL2="$TMPDIR/spool2"
PUB2="$TMPDIR/published2"
mkdir -p "$SPOOL1" "$PUB1" "$SPOOL2" "$PUB2"

echo "=== Idempotencia (aislado) ==="

# Run 1
python3 -m fincadiag.gateway.runtime \
    --session-dir "$SESSION_DIR" \
    --topic-root "fincadiag/la_esmeralda" \
    --dry-run \
    --spool-dir "$SPOOL1" \
    --published-dir "$PUB1" >/dev/null 2>&1 || { echo "[FAIL] Run 1"; exit 1; }
for f in "$PUB1"/*.jsonl; do
    [ -f "$f" ] && md5sum "$f" > "$TMPDIR/run1_$(basename "$f").md5"
done

# Run 2
python3 -m fincadiag.gateway.runtime \
    --session-dir "$SESSION_DIR" \
    --topic-root "fincadiag/la_esmeralda" \
    --dry-run \
    --spool-dir "$SPOOL2" \
    --published-dir "$PUB2" >/dev/null 2>&1 || { echo "[FAIL] Run 2"; exit 1; }
for f in "$PUB2"/*.jsonl; do
    [ -f "$f" ] && md5sum "$f" > "$TMPDIR/run2_$(basename "$f").md5"
done

# Comparar
MATCH=0
MISMATCH=0
for f1 in "$TMPDIR"/run1_*.md5; do
    [ -f "$f1" ] || continue
    name=$(basename "$f1" | sed 's/^run1_/run2_/')
    f2="$TMPDIR/$name"
    if [ -f "$f2" ]; then
        if diff -q "$f1" "$f2" >/dev/null 2>&1; then
            MATCH=$((MATCH + 1))
        else
            MISMATCH=$((MISMATCH + 1))
            echo "  [MISMATCH] $name"
        fi
    else
        MISMATCH=$((MISMATCH + 1))
        echo "  [MISSING] $name"
    fi
done

for f2 in "$TMPDIR"/run2_*.md5; do
    [ -f "$f2" ] || continue
    name=$(basename "$f2" | sed 's/^run2_/run1_/')
    f1="$TMPDIR/$name"
    if [ ! -f "$f1" ]; then
        MISMATCH=$((MISMATCH + 1))
        echo "  [EXTRA] $(basename $f2)"
    fi
done

echo "  Resultado: $MATCH coinciden, $MISMATCH difieren"
if [ "$MISMATCH" -eq 0 ]; then
    echo "[PASS] Idempotencia confirmada"
    exit 0
else
    echo "[FAIL] $MISMATCH archivos difieren"
    exit 1
fi
