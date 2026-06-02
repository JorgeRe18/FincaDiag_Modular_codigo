#!/bin/bash
# power_failure_sim_pi.sh
# Simulacion software de corte de energia: kill -9 al gateway en pleno
# procesamiento, luego relanza y mide cuanto tarda en recuperarse.
# Es proxy de un corte de energia (no remplaza la prueba fisica de desenchufe).
#
# Por ciclo:
#   1. Limpia spool y published.
#   2. Lanza gateway en background.
#   3. Espera N segundos para que empiece a publicar.
#   4. kill -9 al proceso gateway.
#   5. Verifica spool/published parcial.
#   6. Relanza gateway en limpio y arranca cronometro.
#   7. Mide tiempo hasta spool vacio = MTTR proceso.
#
# Uso: ./power_failure_sim_pi.sh [N_CICLOS] [SESSION_DIR]
# Default: N_CICLOS=10 (suficiente proxy)

set -euo pipefail

N_CICLOS="${1:-10}"
SESSION_DIR="${2:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"
DELAY_KILL_S="${DELAY_KILL_S:-5}"  # segundos antes de hacer kill

SPOOL_DIR="${SPOOL_DIR:-/tmp/test_spool_obj4}"
PUB_DIR="${PUB_DIR:-/tmp/test_published_obj4}"
RESULTS_FILE="/home/esmeralda/power_failure_results.csv"
LOG_FILE="/home/esmeralda/power_failure.log"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

if [ ! -d "$SESSION_DIR" ]; then
    echo "[ERROR] Sesion no existe: $SESSION_DIR"
    exit 1
fi

if [ ! -f "$RESULTS_FILE" ]; then
    echo "ciclo,timestamp_inicio,delay_kill_s,t_recovery_s,msgs_pre_kill,msgs_post_recovery,resultado" > "$RESULTS_FILE"
fi

sudo systemctl start mosquitto
sleep 1

echo "=== Power Failure Sim: $N_CICLOS ciclos, kill tras ${DELAY_KILL_S}s ===" | tee -a "$LOG_FILE"
echo "Sesion: $SESSION_DIR" | tee -a "$LOG_FILE"
echo "Inicio: $(date -Iseconds)" | tee -a "$LOG_FILE"

export PYTHONPATH=/opt/fincadiag

run_gateway_bg() {
    python3 -m fincadiag.gateway.runtime \
        --session-dir "$SESSION_DIR" \
        --topic-root "fincadiag/la_esmeralda" \
        --mqtt-host localhost --mqtt-port 8883 \
        --tls-enabled \
        --ca-path /etc/fincadiag/certs/ca.crt \
        --cert-path /etc/fincadiag/certs/client.crt \
        --key-path /etc/fincadiag/certs/client.key \
        --tls-min-version 1.3 \
        --spool-dir "$SPOOL_DIR" \
        --published-dir "$PUB_DIR" \
        >/dev/null 2>&1 &
    echo $!
}

for i in $(seq 1 "$N_CICLOS"); do
    TS_INICIO=$(date -Iseconds)
    echo "--- Ciclo $i/$N_CICLOS ($TS_INICIO) ---" | tee -a "$LOG_FILE"

    sudo rm -rf "$SPOOL_DIR"/* "$PUB_DIR"/* 2>/dev/null || true

    # 1. Lanzar gateway en background
    GW_PID=$(run_gateway_bg)
    echo "  Gateway PID: $GW_PID" | tee -a "$LOG_FILE"

    # 2. Esperar
    sleep "$DELAY_KILL_S"

    # 3. Snapshot pre-kill
    PUB_PRE=$(find "$PUB_DIR" -name "*.jsonl" 2>/dev/null | wc -l)
    SPOOL_PRE=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)

    # 4. KILL -9 (simula corte abrupto)
    sudo kill -9 "$GW_PID" 2>/dev/null || true
    wait "$GW_PID" 2>/dev/null || true
    echo "  Killed: spool=$SPOOL_PRE published=$PUB_PRE" | tee -a "$LOG_FILE"

    # 5. Arrancar cronometro y relanzar
    T_START=$(date +%s.%N)

    # Re-ejecutar gateway en foreground hasta terminar
    if ! python3 -m fincadiag.gateway.runtime \
        --session-dir "$SESSION_DIR" \
        --topic-root "fincadiag/la_esmeralda" \
        --mqtt-host localhost --mqtt-port 8883 \
        --tls-enabled \
        --ca-path /etc/fincadiag/certs/ca.crt \
        --cert-path /etc/fincadiag/certs/client.crt \
        --key-path /etc/fincadiag/certs/client.key \
        --tls-min-version 1.3 \
        --spool-dir "$SPOOL_DIR" \
        --published-dir "$PUB_DIR" \
        >/dev/null 2>&1; then
        T_END=$(date +%s.%N)
        T_RECOVERY=$(echo "$T_END - $T_START" | bc)
        echo "$i,$TS_INICIO,$DELAY_KILL_S,$T_RECOVERY,$PUB_PRE,0,FAIL_RELAUNCH" >> "$RESULTS_FILE"
        echo "  [FAIL] Relanzamiento fallo" | tee -a "$LOG_FILE"
        continue
    fi
    T_END=$(date +%s.%N)
    T_RECOVERY=$(echo "$T_END - $T_START" | bc)

    SPOOL_AFTER=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
    PUB_AFTER=$(find "$PUB_DIR" -name "*.jsonl" 2>/dev/null | wc -l)

    if [ "$SPOOL_AFTER" -eq 0 ]; then
        RESULTADO="PASS"
        printf "  [PASS] Recovery en %.3fs | published=%s\n" "$T_RECOVERY" "$PUB_AFTER" | tee -a "$LOG_FILE"
    else
        RESULTADO="FAIL_DRAIN"
        echo "  [FAIL] Spool no vacio ($SPOOL_AFTER)" | tee -a "$LOG_FILE"
    fi

    echo "$i,$TS_INICIO,$DELAY_KILL_S,$T_RECOVERY,$PUB_PRE,$PUB_AFTER,$RESULTADO" >> "$RESULTS_FILE"
    sleep 2
done

echo "" | tee -a "$LOG_FILE"
echo "=== Resumen Power Failure Sim ===" | tee -a "$LOG_FILE"
python3 - <<PYEOF
import csv
results = []
with open("$RESULTS_FILE") as f:
    for r in csv.DictReader(f):
        if r['resultado'] == 'PASS':
            results.append(float(r['t_recovery_s']))

if results:
    n = len(results)
    media = sum(results) / n
    desv = (sum((x - media) ** 2 for x in results) / max(n - 1, 1)) ** 0.5
    print(f"  Ciclos exitosos: {n}")
    print(f"  MTTR media:      {media:.3f} s")
    print(f"  MTTR desv.est.:  {desv:.3f} s")
PYEOF

echo "Fin: $(date -Iseconds)" | tee -a "$LOG_FILE"
