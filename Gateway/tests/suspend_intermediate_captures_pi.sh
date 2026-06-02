#!/bin/bash
# suspend_intermediate_captures_pi.sh
# Comenta las entradas de captura intermedias en el crontab del usuario,
# dejando SOLO los ordenos AM (2AM) y PM (1PM).
#
# Uso:
#   bash suspend_intermediate_captures_pi.sh           # dry-run (muestra cambios)
#   bash suspend_intermediate_captures_pi.sh --apply   # aplica cambios
#   bash suspend_intermediate_captures_pi.sh --restore # restaura backup mas reciente
#
# Hace backup en /home/esmeralda/crontab_backup_<timestamp>.txt antes de aplicar.

set -euo pipefail

ACCION="${1:-dry-run}"
BACKUP_DIR="/home/esmeralda"

# Patrones a SUSPENDER: capturas que NO son 2AM ni 1PM
# (es decir, 5AM, 7AM, 10AM, 12AM, 3PM, 6PM, 9PM, baselines, etc.)
PATTERNS_SUSPEND=(
    "5AM"
    "7AM"
    "10AM"
    "12AM"
    "3PM"
    "6PM"
    "9PM"
    "BASELINE_ONLY"
    "Baseline_"
)

if [ "$ACCION" = "--restore" ]; then
    LATEST=$(ls -t "$BACKUP_DIR"/crontab_backup_*.txt 2>/dev/null | head -1)
    if [ -z "$LATEST" ]; then
        echo "[ERROR] No hay backups en $BACKUP_DIR"
        exit 1
    fi
    echo "Restaurando desde: $LATEST"
    crontab "$LATEST"
    echo "Crontab restaurado."
    exit 0
fi

# Capturar crontab actual
CURRENT=$(mktemp)
crontab -l > "$CURRENT" 2>/dev/null || {
    echo "[ERROR] No hay crontab para el usuario actual."
    rm -f "$CURRENT"
    exit 1
}

if [ ! -s "$CURRENT" ]; then
    echo "[ERROR] Crontab vacio."
    rm -f "$CURRENT"
    exit 1
fi

# Generar nueva version comentando las lineas que matcheen los patrones
NEW=$(mktemp)
SUSPENDED=0

while IFS= read -r line; do
    # Saltar lineas ya comentadas
    if [[ "$line" =~ ^[[:space:]]*# ]] || [ -z "$line" ]; then
        echo "$line" >> "$NEW"
        continue
    fi

    # Verificar si la linea contiene algun patron a suspender
    matched=false
    for pat in "${PATTERNS_SUSPEND[@]}"; do
        if echo "$line" | grep -q "$pat"; then
            matched=true
            break
        fi
    done

    if [ "$matched" = "true" ]; then
        echo "# [SUSPENDIDO_OBJ4] $line" >> "$NEW"
        SUSPENDED=$((SUSPENDED + 1))
    else
        echo "$line" >> "$NEW"
    fi
done < "$CURRENT"

echo "================================================================"
echo " Crontab actual:"
echo "================================================================"
cat "$CURRENT"
echo ""
echo "================================================================"
echo " Crontab propuesto (lineas a suspender marcadas con #):"
echo "================================================================"
cat "$NEW"
echo ""
echo "================================================================"
echo " RESUMEN: $SUSPENDED lineas se suspenderian."
echo "================================================================"

if [ "$ACCION" = "--apply" ]; then
    if [ "$SUSPENDED" -eq 0 ]; then
        echo "Nada que suspender. No se modifica el crontab."
        rm -f "$CURRENT" "$NEW"
        exit 0
    fi

    TS=$(date +%Y%m%d_%H%M%S)
    BACKUP="$BACKUP_DIR/crontab_backup_$TS.txt"
    cp "$CURRENT" "$BACKUP"
    echo ""
    echo "Backup guardado en: $BACKUP"
    crontab "$NEW"
    echo "Crontab actualizado."
    echo ""
    echo "Para revertir mas tarde:"
    echo "  bash suspend_intermediate_captures_pi.sh --restore"
else
    echo ""
    echo "DRY-RUN: no se modifico nada."
    echo "Para aplicar: bash suspend_intermediate_captures_pi.sh --apply"
fi

rm -f "$CURRENT" "$NEW"
