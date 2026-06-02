#!/bin/bash
# schedule_obj4_pi.sh
# Programa la corrida automatica de las pruebas de Objetivo 4 en la Raspberry Pi
# usando 'at' (one-shot scheduling). Las pruebas se ejecutan en los huecos
# entre ordenos AM y PM para no interferir con la captura.
#
# Cronograma (hora local de la Pi) - ajustado a huecos entre ordenos AM:
#   03:00  -> MTTR stress (30 ciclos, ~15 min)         [hueco 2AM-5AM]
#   03:30  -> Latencia E2E (10 ciclos, ~5 min)         [mismo hueco]
#   05:00  -> Soak test (2 horas, hasta ~07:00)        [hueco 5AM-7AM]
#   07:50  -> Empaquetado de resultados (.tar.gz)      [post 7AM capture]
#
# Uso:
#   bash schedule_obj4_pi.sh             # programa para mañana
#   bash schedule_obj4_pi.sh today       # programa para hoy (si aun hay tiempo)
#   bash schedule_obj4_pi.sh status      # muestra jobs pendientes
#   bash schedule_obj4_pi.sh cancel      # cancela todos los jobs Obj4 pendientes

set -euo pipefail

ACCION="${1:-tomorrow}"
SCRIPT_DIR="/home/esmeralda"
OUT_DIR="/home/esmeralda/obj4_runs"
mkdir -p "$OUT_DIR"

# --- Sub-comandos ---
if [ "$ACCION" = "status" ]; then
    echo "=== Jobs 'at' pendientes ==="
    atq
    if [ -d /var/spool/cron/atjobs ]; then
        echo ""
        echo "=== Detalle (si hay) ==="
        for j in $(atq | awk '{print $1}'); do
            echo "--- Job $j ---"
            at -c "$j" | tail -20
        done
    fi
    exit 0
fi

if [ "$ACCION" = "cancel" ]; then
    echo "=== Cancelando jobs pendientes ==="
    for j in $(atq | awk '{print $1}'); do
        atrm "$j" && echo "  Cancelado job $j"
    done
    exit 0
fi

# --- Verificar 'at' instalado ---
if ! command -v at >/dev/null 2>&1; then
    echo "[ERROR] 'at' no esta instalado. Instalar con:"
    echo "        sudo apt install -y at"
    echo "        sudo systemctl enable --now atd"
    exit 1
fi

if ! systemctl is-active --quiet atd; then
    echo "[WARN] atd no esta activo. Activando..."
    sudo systemctl start atd
fi

# --- Validar que existan los scripts ---
for f in mttr_stress_pi.sh latency_e2e_pi.sh soak_test_pi.sh; do
    if [ ! -f "$SCRIPT_DIR/$f" ]; then
        echo "[ERROR] Falta $SCRIPT_DIR/$f"
        exit 1
    fi
    chmod +x "$SCRIPT_DIR/$f"
done

# --- Determinar fecha base ---
if [ "$ACCION" = "today" ]; then
    DIA="today"
    DIA_LABEL=$(date +%Y-%m-%d)
else
    DIA="tomorrow"
    DIA_LABEL=$(date -d tomorrow +%Y-%m-%d)
fi

echo "================================================================"
echo " Programando pruebas Obj 4 para: $DIA_LABEL"
echo "================================================================"

# --- Helper: programa un job ---
schedule_job() {
    local hora="$1"
    local nombre="$2"
    local cmd="$3"
    local logfile="$OUT_DIR/${DIA_LABEL}_${nombre}.log"

    echo "$cmd > $logfile 2>&1" | at "$hora $DIA" 2>&1 | tail -1
    echo "  [$hora $DIA_LABEL] $nombre  -> $logfile"
}

echo ""
echo "Programando jobs..."

# 1. MTTR a las 03:00 (hueco 2AM->5AM)
schedule_job "03:00" "mttr" \
    "bash $SCRIPT_DIR/mttr_stress_pi.sh 30"

# 2. Latencia E2E a las 03:30
schedule_job "03:30" "latency" \
    "bash $SCRIPT_DIR/latency_e2e_pi.sh 10"

# 3. Soak test a las 05:00 (dura 2h, hueco 5AM->7AM)
schedule_job "05:00" "soak" \
    "bash $SCRIPT_DIR/soak_test_pi.sh 2 60"

# 4. Empaquetado de resultados a las 07:50 (post 7AM capture)
schedule_job "07:50" "bundle" \
    "cd /home/esmeralda && tar -czf obj4_bundle_${DIA_LABEL}.tar.gz mttr_results.csv latency_e2e_results.csv soak_results.csv obj4_runs/ mttr_stress.log latency_e2e.log soak_test.log 2>/dev/null; md5sum obj4_bundle_${DIA_LABEL}.tar.gz > obj4_bundle_${DIA_LABEL}.tar.gz.md5"

echo ""
echo "================================================================"
echo " Jobs programados. Verificar con:"
echo "   bash schedule_obj4_pi.sh status"
echo ""
echo " Cancelar todos con:"
echo "   bash schedule_obj4_pi.sh cancel"
echo ""
echo " Una vez completados (~11:30), descargar desde Windows:"
echo "   scp -P PORT esmeralda@PI:/home/esmeralda/obj4_bundle_${DIA_LABEL}.tar.gz ."
echo "================================================================"
