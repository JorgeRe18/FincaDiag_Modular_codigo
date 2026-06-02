#!/bin/bash
# mttr_systemd_pi.sh
# MTTR del servicio fincadiag-gateway gestionado por systemd.
# A diferencia de power_failure_sim_pi.sh (que aisla runtime puro),
# aqui matamos el servicio en produccion y medimos cuanto tarda systemd
# en relanzarlo + restablecer publicacion MQTT.
#
# IMPORTANTE: este test SI toca el daemon productivo. No corre en paralelo
# con publicacion activa (lo aceptable es que el daemon este idle, watch=60s).
#
# Por ciclo:
#   1. Marca t0.
#   2. sudo systemctl kill -s KILL fincadiag-gateway.
#   3. Espera a que el servicio quede inactive.
#   4. Espera a que systemd lo relance (Restart=always, RestartSec=5).
#   5. Espera a que el runtime se reconecte al broker MQTT (lee journalctl).
#   6. Mide t_recovery = t_reconectado - t_kill.
#
# Uso: ./mttr_systemd_pi.sh [N_CICLOS]
# Default: N_CICLOS=10

set -euo pipefail

N_CICLOS="${1:-10}"
SERVICE="fincadiag-gateway"
RESULTS_FILE="/home/esmeralda/mttr_systemd_results.csv"
LOG_FILE="/home/esmeralda/mttr_systemd.log"
TIMEOUT_S="${TIMEOUT_S:-60}"
COOLDOWN_S="${COOLDOWN_S:-15}"

if [ ! -f "$RESULTS_FILE" ]; then
    echo "ciclo,timestamp_inicio,t_kill_to_active_s,t_kill_to_mqtt_s,resultado" > "$RESULTS_FILE"
fi

echo "=== MTTR Systemd: $N_CICLOS ciclos sobre $SERVICE ===" | tee -a "$LOG_FILE"
echo "Inicio: $(date -Iseconds)" | tee -a "$LOG_FILE"

# Verificar servicio activo antes de empezar
if ! systemctl is-active --quiet "$SERVICE"; then
    echo "[WARN] $SERVICE no esta activo, arrancando..." | tee -a "$LOG_FILE"
    sudo systemctl start "$SERVICE"
    sleep 5
fi

for i in $(seq 1 "$N_CICLOS"); do
    TS_INICIO=$(date -Iseconds)
    echo "--- Ciclo $i/$N_CICLOS ($TS_INICIO) ---" | tee -a "$LOG_FILE"

    # Marca para journalctl (formato systemd)
    T_MARK=$(date +"%Y-%m-%d %H:%M:%S")
    T_START=$(date +%s.%N)

    # 1. KILL -9 al servicio
    sudo systemctl kill -s KILL "$SERVICE" || true
    echo "  Kill enviado a $T_MARK" | tee -a "$LOG_FILE"

    # 2. Esperar hasta que vuelva a active
    T_ACTIVE=""
    for _ in $(seq 1 $((TIMEOUT_S * 2))); do
        if systemctl is-active --quiet "$SERVICE"; then
            T_ACTIVE=$(date +%s.%N)
            break
        fi
        sleep 0.5
    done

    if [ -z "$T_ACTIVE" ]; then
        echo "  [FAIL] Servicio no volvio active en ${TIMEOUT_S}s" | tee -a "$LOG_FILE"
        echo "$i,$TS_INICIO,,,FAIL_NO_ACTIVE" >> "$RESULTS_FILE"
        sleep "$COOLDOWN_S"
        continue
    fi

    DT_ACTIVE=$(echo "$T_ACTIVE - $T_START" | bc)
    printf "  Active en %.3fs\n" "$DT_ACTIVE" | tee -a "$LOG_FILE"

    # 3. Esperar a que el runtime se conecte a MQTT (busca log de conexion)
    # Patrones tipicos: "connect", "Connected", "publish", "MQTT"
    T_MQTT=""
    for _ in $(seq 1 $((TIMEOUT_S * 2))); do
        # Buscar evidencia de conexion MQTT desde T_MARK
        if sudo journalctl -u "$SERVICE" --since "$T_MARK" --no-pager 2>/dev/null \
            | grep -iE "connect|publish|watch|mqtt" | grep -v "ERROR\|fail\|refused" \
            | head -1 | grep -q .; then
            T_MQTT=$(date +%s.%N)
            break
        fi
        sleep 0.5
    done

    if [ -z "$T_MQTT" ]; then
        echo "  [PARTIAL] Active pero sin evidencia MQTT en log" | tee -a "$LOG_FILE"
        echo "$i,$TS_INICIO,$DT_ACTIVE,,PARTIAL_NO_MQTT_LOG" >> "$RESULTS_FILE"
        sleep "$COOLDOWN_S"
        continue
    fi

    DT_MQTT=$(echo "$T_MQTT - $T_START" | bc)
    printf "  MQTT ready en %.3fs\n" "$DT_MQTT" | tee -a "$LOG_FILE"

    echo "$i,$TS_INICIO,$DT_ACTIVE,$DT_MQTT,PASS" >> "$RESULTS_FILE"

    # Cooldown entre ciclos para no saturar
    sleep "$COOLDOWN_S"
done

echo "" | tee -a "$LOG_FILE"
echo "=== Resumen MTTR Systemd ===" | tee -a "$LOG_FILE"
python3 - <<PYEOF | tee -a "$LOG_FILE"
import csv
act, mqtt = [], []
with open("$RESULTS_FILE") as f:
    for r in csv.DictReader(f):
        if r['resultado'] == 'PASS':
            try:
                act.append(float(r['t_kill_to_active_s']))
                mqtt.append(float(r['t_kill_to_mqtt_s']))
            except ValueError:
                pass

def stats(xs, label):
    if not xs:
        print(f"  {label}: sin datos")
        return
    n = len(xs)
    m = sum(xs) / n
    s = (sum((x - m) ** 2 for x in xs) / max(n - 1, 1)) ** 0.5
    print(f"  {label}: n={n} media={m:.3f}s sd={s:.3f}s min={min(xs):.3f}s max={max(xs):.3f}s")

stats(act, "kill->active   ")
stats(mqtt, "kill->mqtt_ready")
PYEOF

echo "Fin: $(date -Iseconds)" | tee -a "$LOG_FILE"
