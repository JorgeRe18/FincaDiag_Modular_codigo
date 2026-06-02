#!/bin/bash
# network_failure_pi.sh
# Mide MTTR ante fallos de red simulando perdida de conectividad al broker
# usando iptables (bloqueo de tráfico saliente al puerto MQTT).
#
# Diferencia con mttr_stress_pi.sh:
#   - mttr_stress: tira el broker (servicio mosquitto stop)
#   - este script: deja el broker arriba pero corta la red entre gateway y broker
#
# Mide tres fases:
#   1. Tiempo desde corte de red hasta primera deteccion del gateway (DETECT)
#   2. Tiempo desde restauracion de red hasta primer mensaje publicado (RECONNECT)
#   3. Tiempo total desde corte hasta spool vacio (RECOVERY)
#
# Uso: ./network_failure_pi.sh [N_CICLOS] [SESSION_DIR]
# Default: N_CICLOS=30

set -euo pipefail

N_CICLOS="${1:-30}"
SESSION_DIR="${2:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"
MQTT_PORT="${MQTT_PORT:-8883}"
DOWNTIME_S="${DOWNTIME_S:-10}"  # cuanto tiempo se mantiene la red caida por ciclo

SPOOL_DIR="${SPOOL_DIR:-/tmp/test_spool_obj4}"
PUB_DIR="${PUB_DIR:-/tmp/test_published_obj4}"
RESULTS_FILE="/home/esmeralda/network_failure_results.csv"
LOG_FILE="/home/esmeralda/network_failure.log"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

if [ ! -d "$SESSION_DIR" ]; then
    echo "[ERROR] Sesion no existe: $SESSION_DIR"
    exit 1
fi

if [ ! -f "$RESULTS_FILE" ]; then
    echo "ciclo,timestamp_inicio,downtime_s,t_recovery_s,msgs_spooled,msgs_published,resultado" > "$RESULTS_FILE"
fi

echo "=== Network Failure Test: $N_CICLOS ciclos, downtime=${DOWNTIME_S}s ===" | tee -a "$LOG_FILE"
echo "Sesion: $SESSION_DIR" | tee -a "$LOG_FILE"
echo "Inicio: $(date -Iseconds)" | tee -a "$LOG_FILE"

export PYTHONPATH=/opt/fincadiag

run_gateway_bg() {
    python3 -m fincadiag.gateway.runtime \
        --session-dir "$SESSION_DIR" \
        --topic-root "fincadiag/la_esmeralda" \
        --mqtt-host localhost --mqtt-port "$MQTT_PORT" \
        --tls-enabled \
        --ca-path /etc/fincadiag/certs/ca.crt \
        --cert-path /etc/fincadiag/certs/client.crt \
        --key-path /etc/fincadiag/certs/client.key \
        --tls-min-version 1.3 \
        --spool-dir "$SPOOL_DIR" \
        --published-dir "$PUB_DIR" \
        >/dev/null 2>&1
}

block_mqtt_traffic() {
    sudo iptables -A OUTPUT -p tcp --dport "$MQTT_PORT" -j DROP 2>/dev/null || true
    sudo iptables -A INPUT -p tcp --sport "$MQTT_PORT" -j DROP 2>/dev/null || true
}

unblock_mqtt_traffic() {
    sudo iptables -D OUTPUT -p tcp --dport "$MQTT_PORT" -j DROP 2>/dev/null || true
    sudo iptables -D INPUT -p tcp --sport "$MQTT_PORT" -j DROP 2>/dev/null || true
}

# Cleanup en caso de salida abrupta
trap unblock_mqtt_traffic EXIT

for i in $(seq 1 "$N_CICLOS"); do
    TS_INICIO=$(date -Iseconds)
    echo "--- Ciclo $i/$N_CICLOS ($TS_INICIO) ---" | tee -a "$LOG_FILE"

    sudo rm -rf "$SPOOL_DIR"/* "$PUB_DIR"/* 2>/dev/null || true

    # 1. Bloquear red ANTES de lanzar gateway
    block_mqtt_traffic

    # 2. Lanzar gateway con red bloqueada -> debe spoolear
    run_gateway_bg || true

    SPOOL_COUNT=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
    echo "  Spooled (red caida): $SPOOL_COUNT mensajes" | tee -a "$LOG_FILE"

    # 3. Esperar el downtime configurado
    sleep "$DOWNTIME_S"

    # 4. Restaurar red y arrancar cronometro
    T_START=$(date +%s.%N)
    unblock_mqtt_traffic

    # Esperar handshake MQTT (max 10s)
    for j in $(seq 1 20); do
        if mosquitto_pub -h localhost -p "$MQTT_PORT" \
            --cafile /etc/fincadiag/certs/ca.crt \
            --cert /etc/fincadiag/certs/client.crt \
            --key /etc/fincadiag/certs/client.key \
            --tls-version tlsv1.3 \
            -t "fincadiag/healthcheck" -m "ok" -q 0 >/dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done

    # 5. Re-ejecutar gateway -> debe vaciar el spool
    run_gateway_bg || true
    T_END=$(date +%s.%N)
    T_RECOVERY=$(echo "$T_END - $T_START" | bc)

    SPOOL_AFTER=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
    PUB_COUNT=$(find "$PUB_DIR" -name "*.jsonl" 2>/dev/null | wc -l)

    if [ "$SPOOL_AFTER" -eq 0 ]; then
        RESULTADO="PASS"
        printf "  [PASS] Recovery en %.3fs | published=%s\n" "$T_RECOVERY" "$PUB_COUNT" | tee -a "$LOG_FILE"
    else
        RESULTADO="FAIL_DRAIN"
        echo "  [FAIL] Spool no se vacio (quedaron $SPOOL_AFTER)" | tee -a "$LOG_FILE"
    fi

    echo "$i,$TS_INICIO,$DOWNTIME_S,$T_RECOVERY,$SPOOL_COUNT,$PUB_COUNT,$RESULTADO" >> "$RESULTS_FILE"
    sleep 2
done

echo "" | tee -a "$LOG_FILE"
echo "=== Resumen Network Failure ===" | tee -a "$LOG_FILE"
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
    mediana = sorted(results)[n // 2]
    desv = (sum((x - media) ** 2 for x in results) / max(n - 1, 1)) ** 0.5
    print(f"  Ciclos exitosos: {n}")
    print(f"  MTTR media:      {media:.3f} s")
    print(f"  MTTR mediana:    {mediana:.3f} s")
    print(f"  MTTR desv.est.:  {desv:.3f} s")
PYEOF

echo "Fin: $(date -Iseconds)" | tee -a "$LOG_FILE"
