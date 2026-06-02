#!/bin/bash
# inject_fault_live_pi_v2.sh
# Inyeccion de fallos controlados DURANTE un ordeño real (operacion normal).
# v2: Corrige CSV consistente, trap iptables, verifica reconexion gateway.
#
# Uso: ./inject_fault_live_pi_v2.sh --broker [duracion_s]
#      ./inject_fault_live_pi_v2.sh --network [duracion_s]
#      ./inject_fault_live_pi_v2.sh --kill [cooldown_s]
#      ./inject_fault_live_pi_v2.sh --dry-run

set -euo pipefail

SERVICE="fincadiag-gateway"
RESULTS_FILE="/home/esmeralda/fault_injections.csv"
LOG_FILE="/home/esmeralda/fault_injections.log"

# Defaults (v3-hot: 90s para superar backoff 62s y forzar spooling real)
BROKER_DURATION="${BROKER_DURATION:-90}"
NET_DURATION="${NET_DURATION:-90}"
KILL_COOLDOWN="${KILL_COOLDOWN:-90}"

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
    echo "timestamp,modo,duracion_s,t_recovery_s,estado_daemon_antes,estado_daemon_despues,estado_mosquitto_despues,observacion" > "$RESULTS_FILE"
fi

log() {
    echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"
}

check_daemon() {
    if systemctl is-active --quiet "$SERVICE"; then
        echo "active"
    else
        echo "inactive"
    fi
}

check_mosquitto() {
    if systemctl is-active --quiet mosquitto; then
        echo "active"
    else
        echo "inactive"
    fi
}

TS=$(date -Iseconds)
STATUS_BEFORE=$(check_daemon)
MOSQ_BEFORE=$(check_mosquitto)

if [ "$MODE" = "--dry-run" ]; then
    echo "=== DRY RUN ==="
    echo "Servicio : $SERVICE"
    echo "Daemon   : $STATUS_BEFORE"
    echo "Mosquitto: $MOSQ_BEFORE"
    echo "CSV      : $RESULTS_FILE"
    echo "Comandos que ejecutaria:"
    echo "  --broker  : systemctl restart mosquitto (duracion_s)"
    echo "  --network : iptables DROP 8883 (duracion_s)"
    echo "  --kill    : systemctl kill -s KILL $SERVICE, cooldown_s"
    exit 0
fi

if [ "$MODE" = "--broker" ]; then
    DUR="${1:-$BROKER_DURATION}"
    log "INICIANDO fallo broker: restart mosquitto, esperar ${DUR}s"
    t0=$(date +%s.%N)
    sudo systemctl restart mosquitto
    sleep "$DUR"

    # Verificar que mosquitto volvio
    MOSQ_AFTER=$(check_mosquitto)
    STATUS_AFTER=$(check_daemon)

    # Verificar que el gateway se reconecto (esperar hasta 10s)
    for _ in $(seq 1 20); do
        if systemctl is-active --quiet "$SERVICE"; then
            break
        fi
        sleep 0.5
    done
    STATUS_AFTER=$(check_daemon)

    t1=$(date +%s.%N)
    DT=$(echo "$t1 - $t0" | bc)
    echo "$TS,broker,$DUR,$DT,$STATUS_BEFORE,$STATUS_AFTER,$MOSQ_AFTER,reinicio mosquitto" >> "$RESULTS_FILE"
    log "FIN broker: daemon=$STATUS_AFTER mosquitto=$MOSQ_AFTER dt=${DT}s"

elif [ "$MODE" = "--network" ]; then
    DUR="${1:-$NET_DURATION}"
    log "INICIANDO fallo red: iptables DROP 8883 ${DUR}s"

    # Trap para limpiar iptables si se interrumpe (Ctrl-C, error, etc.)
    cleanup_iptables() {
        log "LIMPIANDO iptables (trap)"
        sudo iptables -D OUTPUT -p tcp --dport 8883 -j DROP 2>/dev/null || true
    }
    trap cleanup_iptables EXIT

    t0=$(date +%s.%N)
    sudo iptables -A OUTPUT -p tcp --dport 8883 -j DROP
    log "  iptables bloqueo activo"
    sleep "$DUR"
    sudo iptables -D OUTPUT -p tcp --dport 8883 -j DROP
    trap - EXIT  # limpiar trap

    STATUS_AFTER=$(check_daemon)
    MOSQ_AFTER=$(check_mosquitto)
    t1=$(date +%s.%N)
    DT=$(echo "$t1 - $t0" | bc)
    echo "$TS,network,$DUR,$DT,$STATUS_BEFORE,$STATUS_AFTER,$MOSQ_AFTER,iptables block+flush" >> "$RESULTS_FILE"
    log "FIN red: daemon=$STATUS_AFTER mosquitto=$MOSQ_AFTER dt=${DT}s"

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
    MOSQ_AFTER=$(check_mosquitto)
    t1=$(date +%s.%N)
    DT=$(echo "$t1 - $t0" | bc)

    # Guardar: duracion_s = cooldown, t_recovery_s = DT real
    echo "$TS,kill,$COOL,$DT,$STATUS_BEFORE,$STATUS_AFTER,$MOSQ_AFTER,systemd restart" >> "$RESULTS_FILE"
    log "FIN kill: daemon=$STATUS_AFTER dt=${DT}s cooldown=${COOL}s"
    sleep "$COOL"

else
    usage
fi

echo "Inyeccion registrada en $RESULTS_FILE"
