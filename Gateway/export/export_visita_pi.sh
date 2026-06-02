#!/bin/bash
# export_visita_pi.sh
# Comprime una visita (procesada o logs crudos) en un solo tar.gz para transferencia rapida via WinSCP.
# Uso manual:  ./export_visita_pi.sh Visita_20_05_2026
# Uso cron:    ./export_visita_pi.sh $(date -d 'yesterday' +Visita_%d_%m_%Y)
#
# El resultado queda en /home/esmeralda/exports/ como un solo archivo grande.

set -euo pipefail

VISITA="${1:-}"
if [ -z "$VISITA" ]; then
    echo "Uso: $0 <nombre_visita>"
    echo "Ejemplo: $0 Visita_20_05_2026"
    echo ""
    echo "Visitas procesadas en /var/lib/fincadiag/processed/visits/:"
    ls /var/lib/fincadiag/processed/visits/ 2>/dev/null || echo "  (directorio no encontrado)"
    echo ""
    echo "Visitas crudas en /home/esmeralda/FincaLogs/:"
    ls /home/esmeralda/FincaLogs/ 2>/dev/null || echo "  (directorio no encontrado)"
    exit 1
fi

# Buscar primero en procesadas, si no existe en logs crudos
SRC_PROCESSED="/var/lib/fincadiag/processed/visits/${VISITA}"
SRC_LOGS="/home/esmeralda/FincaLogs/${VISITA}"

if [ -d "$SRC_PROCESSED" ]; then
    SRC_DIR="$SRC_PROCESSED"
    echo "[INFO] Usando visita procesada: $SRC_DIR"
elif [ -d "$SRC_LOGS" ]; then
    SRC_DIR="$SRC_LOGS"
    echo "[INFO] Usando logs crudos: $SRC_DIR"
else
    echo "[ERROR] No existe: ni $SRC_PROCESSED ni $SRC_LOGS"
    exit 1
fi

EXPORT_DIR="/home/esmeralda/exports"
DEST_FILE="${EXPORT_DIR}/${VISITA}.tar.gz"

mkdir -p "$EXPORT_DIR"

# Contar archivos originales
FILE_COUNT=$(find "$SRC_DIR" -type f | wc -l)
echo "=== Exportando ${VISITA} ==="
echo "  Archivos originales: $FILE_COUNT"
echo "  Origen:  $SRC_DIR"
echo "  Destino: $DEST_FILE"

# Comprimir (preserva paths relativos a SRC_DIR)
tar -czf "$DEST_FILE" -C "$(dirname "$SRC_DIR")" "$(basename "$SRC_DIR")"

DEST_SIZE=$(du -sh "$DEST_FILE" | cut -f1)
echo "  [OK] Exportado: $DEST_SIZE ($FILE_COUNT archivos comprimidos)"

# Generar MD5 checksum para verificar integridad en transferencia
MD5_FILE="${DEST_FILE}.md5"
md5sum "$DEST_FILE" > "$MD5_FILE"
echo "  [OK] MD5: $(cat "$MD5_FILE" | awk '{print $1}')"

echo ""
echo "Ahora usa WinSCP para descargar ambos archivos:"
echo "  /home/esmeralda/exports/${VISITA}.tar.gz"
echo "  /home/esmeralda/exports/${VISITA}.tar.gz.md5"
echo ""

