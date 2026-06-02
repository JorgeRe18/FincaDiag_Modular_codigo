#!/bin/bash
# setup_cron_export.sh
# Instala un cron job en la Raspberry Pi que comprime automaticamente
# la visita del dia anterior a las 23:30.
# Correr esto una sola vez en la Pi.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXPORT_SCRIPT="/home/esmeralda/export_visita_pi.sh"
EXPORT_DIR="/home/esmeralda/exports"
CRON_LINE="30 23 * * * ${EXPORT_SCRIPT} \"\$(date -d 'yesterday' +Visita_%d_%m_%Y)\" >> ${EXPORT_DIR}/cron.log 2>&1"

echo "=== Instalando cron job de exportacion diaria ==="

# Verificar que export_visita_pi.sh existe
if [ ! -f "$EXPORT_SCRIPT" ]; then
    echo "[WARN] No se encontro ${EXPORT_SCRIPT}"
    echo "       Copialo primero a la Pi y luego corre este script."
    exit 1
fi

chmod +x "$EXPORT_SCRIPT"
mkdir -p "$EXPORT_DIR"

# Verificar si ya existe el cron job
if crontab -l 2>/dev/null | grep -q "export_visita_pi.sh"; then
    echo "[INFO] Cron job ya existe. Reemplazando..."
    crontab -l 2>/dev/null | grep -v "export_visita_pi.sh" | crontab -
fi

# Instalar nuevo cron job
(crontab -l 2>/dev/null || true; echo "$CRON_LINE") | crontab -

echo "[OK] Cron job instalado:"
echo "     $CRON_LINE"
echo ""
echo "Verificacion:"
crontab -l | grep "export_visita_pi" || echo "     (no encontrado, revisar manualmente)"
echo ""
echo "Para probar ahora manualmente:"
echo "     ${EXPORT_SCRIPT} Visita_$(date -d 'yesterday' +%d_%m_%Y)"

echo ""
echo "Verificar:"
echo "   crontab -l"
echo "   sudo systemctl restart cron"
