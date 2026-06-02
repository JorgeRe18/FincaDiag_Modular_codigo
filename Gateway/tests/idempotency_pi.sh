#!/bin/bash
# Prueba 4 (Pi): Idempotencia del gateway
# Objetivo: confirmar que dos corridas identicas producen salida identica.
# Sirve para Objetivo 4: ruido del gateway no afecta η entre corridas.

set -euo pipefail

SESSION_DIR="${1:-}"
if [ -z "$SESSION_DIR" ]; then
    echo "Uso: $0 <ruta_sesion_procesada>"
    exit 1
fi

echo "=== Prueba de idempotencia: $SESSION_DIR ==="

export PYTHONPATH=/opt/fincadiag
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Primera corrida
echo "--- Run 1 ---"
python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run >/dev/null 2>&1 || { echo "[FAIL] Run 1"; exit 1; }
for f in data/gateway/published/*.jsonl; do
    [ -f "$f" ] && md5sum "$f" > "$TMPDIR/run1_$(basename "$f").md5"
done

# Borrar published
rm -rf data/gateway/published/*

# Segunda corrida
echo "--- Run 2 ---"
python3 -m fincadiag.gateway.runtime --session-dir "$SESSION_DIR" --topic-root "fincadiag/la_esmeralda" --dry-run >/dev/null 2>&1 || { echo "[FAIL] Run 2"; exit 1; }
for f in data/gateway/published/*.jsonl; do
    [ -f "$f" ] && md5sum "$f" > "$TMPDIR/run2_$(basename "$f").md5"
done

# Comparar
echo "--- Comparacion ---"
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

if [ "$MISMATCH" -eq 0 ]; then
    echo "[PASS] Idempotencia verificada ($MATCH archivos identicos)"
else
    echo "[FAIL] $MISMATCH archivos difieren ($MATCH coinciden)"
    exit 1
fi
