#!/bin/bash
# Ejecutar en Raspberry Pi
# chmod +x tmp_run_4_sessions_raspberry.sh
# ./tmp_run_4_sessions_raspberry.sh

set -e

PYTHONPATH=/opt/fincadiag/src
export PYTHONPATH

RUNTIME="python3 -m fincadiag.gateway.runtime"
SPOOL_DIR="/var/lib/fincadiag/spool"
PUBLISHED_DIR="/var/lib/fincadiag/published"

# Ruta base de sesiones procesadas en Raspberry
BASE_DIR="/var/lib/fincadiag/processed/visits"

# Sesiones a ejecutar
declare -A SESSIONS
SESSIONS["11_AM"]="$BASE_DIR/Visita_11_05_2026/sesiones/TOMA_AM__2AM__Captura_20260511_021505"
SESSIONS["12_PM"]="$BASE_DIR/Visita_12_05_2026/sesiones/TOMA_PM__1PM__Captura_20260512_130005"
SESSIONS["14_AM"]="$BASE_DIR/Visita_14_05_2026/sesiones/TOMA_AM__2AM__Captura_20260514_021505"
SESSIONS["14_PM"]="$BASE_DIR/Visita_14_05_2026/sesiones/TOMA_PM__1PM__Captura_20260514_130006"

mkdir -p "$SPOOL_DIR"
mkdir -p "$PUBLISHED_DIR"

# Verificar que existan las sesiones
for key in "${!SESSIONS[@]}"; do
    session_dir="${SESSIONS[$key]}"
    if [ ! -d "$session_dir" ]; then
        echo "ERROR: Sesion no encontrada: $session_dir"
        exit 1
    fi
    echo "OK: $key -> $session_dir"
done

echo ""
echo "=========================================="
echo "Ejecutando 4 sesiones en DRY-RUN"
echo "=========================================="

for key in "11_AM" "12_PM" "14_AM" "14_PM"; do
    session_dir="${SESSIONS[$key]}"
    echo ""
    echo "--- Ejecutando $key ---"
    $RUNTIME \
        --visit-dir "$session_dir" \
        --spool-dir "$SPOOL_DIR" \
        --published-dir "$PUBLISHED_DIR" \
        --dry-run
done

echo ""
echo "=========================================="
echo "Verificando archivos publicados"
echo "=========================================="
ls -la "$PUBLISHED_DIR"/

echo ""
echo "Resumen de resultados:"
for f in "$PUBLISHED_DIR"/*.readable.json; do
    if [ -f "$f" ]; then
        name=$(basename "$f")
        msg_count=$(python3 -c "import json; print(json.load(open('$f'))['message_count'])")
        echo "  $name: $msg_count mensajes"
    fi
done
