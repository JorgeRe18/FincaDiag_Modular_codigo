#!/bin/bash
# run_obj4_tests_pi.sh
# Orquestador de pruebas de campo para el Objetivo 4.
# Corre en secuencia: MTTR (estres) + Latencia E2E.
# El soak test se lanza por separado porque dura horas.
#
# Uso:
#   bash run_obj4_tests_pi.sh                  # MTTR=30 ciclos, latencia=10 ciclos
#   bash run_obj4_tests_pi.sh 30 10            # explicito
#   bash run_obj4_tests_pi.sh 5 3              # modo rapido para verificar

set -euo pipefail

MTTR_CICLOS="${1:-30}"
LATENCY_CICLOS="${2:-10}"
SCRIPT_DIR="/home/esmeralda"
TS_INICIO=$(date -Iseconds)
MASTER_LOG="/home/esmeralda/obj4_master.log"

echo "================================================================"
echo " ORQUESTADOR PRUEBAS OBJETIVO 4"
echo "================================================================"
echo " Inicio: $TS_INICIO"
echo " MTTR:    $MTTR_CICLOS ciclos"
echo " Latency: $LATENCY_CICLOS ciclos"
echo "================================================================"
echo ""

{
echo "================================================================"
echo " ORQUESTADOR PRUEBAS OBJETIVO 4 - $TS_INICIO"
echo "================================================================"
} >> "$MASTER_LOG"

# --- Pre-flight checks ---
echo "[1/5] Verificando prerrequisitos..."

if ! command -v mosquitto_pub >/dev/null 2>&1; then
    echo "  [ERROR] Falta mosquitto-clients. Instalar con:"
    echo "          sudo apt install mosquitto-clients"
    exit 1
fi

if ! command -v bc >/dev/null 2>&1; then
    echo "  [ERROR] Falta bc. Instalar con: sudo apt install bc"
    exit 1
fi

if [ ! -d "/var/lib/fincadiag/processed/visits" ]; then
    echo "  [ERROR] No existe /var/lib/fincadiag/processed/visits"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/mttr_stress_pi.sh" ]; then
    echo "  [ERROR] Falta $SCRIPT_DIR/mttr_stress_pi.sh"
    exit 1
fi

if [ ! -f "$SCRIPT_DIR/latency_e2e_pi.sh" ]; then
    echo "  [ERROR] Falta $SCRIPT_DIR/latency_e2e_pi.sh"
    exit 1
fi

echo "  OK"
echo ""

# --- Asegurar mosquitto activo ---
echo "[2/5] Asegurando mosquitto activo..."
sudo systemctl start mosquitto
sleep 1
if ! systemctl is-active --quiet mosquitto; then
    echo "  [ERROR] mosquitto no esta activo"
    exit 1
fi
echo "  OK"
echo ""

# --- MTTR Stress Test ---
echo "[3/5] Ejecutando MTTR stress ($MTTR_CICLOS ciclos)..."
echo "      Salida: /home/esmeralda/mttr_results.csv"
T0=$(date +%s)
if bash "$SCRIPT_DIR/mttr_stress_pi.sh" "$MTTR_CICLOS" 2>&1 | tee -a "$MASTER_LOG"; then
    T1=$(date +%s)
    echo "  COMPLETADO en $((T1 - T0))s"
else
    echo "  [WARN] MTTR fallo, continuando..."
fi
echo ""

# Pausa para estabilizar
sleep 5

# --- Latency E2E ---
echo "[4/5] Ejecutando Latencia E2E ($LATENCY_CICLOS ciclos)..."
echo "      Salida: /home/esmeralda/latency_e2e_results.csv"
T0=$(date +%s)
if bash "$SCRIPT_DIR/latency_e2e_pi.sh" "$LATENCY_CICLOS" 2>&1 | tee -a "$MASTER_LOG"; then
    T1=$(date +%s)
    echo "  COMPLETADO en $((T1 - T0))s"
else
    echo "  [WARN] Latencia fallo, continuando..."
fi
echo ""

# --- Resumen final ---
echo "[5/5] RESUMEN FINAL"
echo "================================================================"
echo " Fin: $(date -Iseconds)"
echo "================================================================"

if [ -f /home/esmeralda/mttr_results.csv ]; then
    n_mttr=$(($(wc -l < /home/esmeralda/mttr_results.csv) - 1))
    n_pass=$(grep -c ',PASS$' /home/esmeralda/mttr_results.csv 2>/dev/null || echo 0)
    echo " MTTR:    $n_mttr ciclos totales, $n_pass exitosos"
fi

if [ -f /home/esmeralda/latency_e2e_results.csv ]; then
    n_lat=$(($(wc -l < /home/esmeralda/latency_e2e_results.csv) - 1))
    echo " Latency: $n_lat ciclos registrados"
fi

echo ""
echo " ARCHIVOS A DESCARGAR A WINDOWS:"
echo "   /home/esmeralda/mttr_results.csv"
echo "   /home/esmeralda/latency_e2e_results.csv"
echo "   /home/esmeralda/obj4_master.log"
echo ""
echo " (soak_test_pi.sh se ejecuta por separado, ~2h)"
echo "================================================================"
