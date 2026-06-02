#!/bin/bash
# inject_fault_live_pi.sh
# Inyeccion de fallos controlados DURANTE un ordeño real (operacion normal).
# NO usar en huecos aislados; este script esta disenado para tocar el daemon
# en produccion mientras llegan datos reales del establo.
#
# Uso: ./inject_fault_live_pi.sh --broker [duracion_s]
#      ./inject_fault_live_pi.sh --network [duracion_s]
#      ./inject_fault_live_pi.sh --kill [cooldown_s]
#      ./inject_fault_live_pi.sh --dry-run
#
# Registra cada inyeccion en /home/esmeralda/fault_injections.csv

set -euo pipefail

SERVICE="fincadiag-gateway"
RESULTS_FILE="/home/esmeralda/fault_injections.csv"

# Defaults
BROKER_DURATION="${BROKER_DURATION:-5}"
NET_DURATION="${NET_DURATION:-30}"
KILL_COOLDOWN="${KILL_COOLDOWN:-60}"

usage() {
    echo "Uso: $0 --broker [duracion_s] | --network [duracion_s] | --kill [cooldown_s] | --dry-run"
    exit 1
}

if [ $# -lt 1 ]; then
    usage
fi

MODE="$1"
shift

if [ ! -f "$RESULTS_FILE" ]; then
    echo "timestamp,modo,duracion_s,t_before_kill_or_restart,t_after_recovery,estado_daemon_antes,estado_daemon_despues,observacion" > "$RESULTS_FILE"
fi

log() {
    echo "[$(date -Iseconds)] $*" | tee -a /home/esmeralda/fault_injections.log
}

check_daemon() {
    if systemctl is-active --quiet "$SERVICE"; then
        echo "active"
    else
        echo "inactive"
    fi
}

TS=$(date -Iseconds)
STATUS_BEFORE=$(check_daemon)

if [ "$MODE" = "--dry-run" ]; then
    echo "=== DRY RUN ==="
    echo "Servicio: $SERVICE"
    echo "Estado  : $STATUS_BEFORE"
    echo "CSV     : $RESULTS_FILE"
    echo "Comandos que ejecutaria:"
    echo "  --broker  : systemctl restart mosquitto (5 s)"
    echo "  --network : iptables DROP 8883 (30 s)"
    echo "  --kill    : systemctl kill -s KILL $SERVICE"
    exit 0
fi

if [ "$MODE" = "--broker" ]; then
    DUR="${1:-$BROKER_DURATION}"
    log "INICIANDO fallo broker: restart mosquitto, esperar ${DUR}s"
    t0=$(date +%s.%N)
    sudo systemctl restart mosquitto
    sleep "$DUR"
    STATUS_AFTER=$(check_daemon)
    t1=$(date +%s.%N)
    DT=$(echo "$t1 - $t0" | bc)
    echo "$TS,broker,$DUR,$t0,$t1,$STATUS_BEFORE,$STATUS_AFTER,reinicio mosquitto" >> "$RESULTS_FILE"
    log "FIN broker: daemon after=$STATUS_AFTER, dt=${DT}s"

elif [ "$MODE" = "--network" ]; then
    DUR="${1:-$NET_DURATION}"
    log "INICIANDO fallo red: iptables DROP 8883 ${DUR}s"
    t0=$(date +%s.%N)
    sudo iptables -A OUTPUT -p tcp --dport 8883 -j DROP
    log "  iptables bloqueo activo"
    sleep "$DUR"
    sudo iptables -D OUTPUT -p tcp --dport 8883 -j DROP
    STATUS_AFTER=$(check_daemon)
    t1=$(date +%s.%N)
    DT=$(echo "$t1 - $t0" | bc)
    echo "$TS,network,$DUR,$t0,$t1,$STATUS_BEFORE,$STATUS_AFTER,iptables block+flush" >> "$RESULTS_FILE"
    log "FIN red: daemon after=$STATUS_AFTER, dt=${DT}s"

elif [ "$MODE" = "--kill" ]; then
    COOL="${1:-$KILL_COOLDOWN}"
    log "INICIANDO fallo kill: systemctl kill -s KILL $SERVICE"
    t0=$(date +%s.%N)
    sudo systemctl kill -s KILL "$SERVICE" || true
    log "  Kill enviado, esperando reinicio systemd..."
    # Esperar hasta active (timeout 60 s)
    for _ in $(seq 1 120); do
        if systemctl is-active --quiet "$SERVICE"; then
            break
        fi
        sleep 0.5
    done
    STATUS_AFTER=$(check_daemon)
    t1=$(date +%s.%N)
    DT=$(echo "$t1 - $t0" | bc)
    echo "$TS,kill,$DT,$t0,$t1,$STATUS_BEFORE,$STATUS_AFTER,systemd restart" >> "$RESULTS_FILE"
    log "FIN kill: daemon after=$STATUS_AFTER, dt=${DT}s, cooldown=${COOL}s"
    sleep "$COOL"

else
    usage
fi

echo "Inyeccion registrada en $RESULTS_FILE"
