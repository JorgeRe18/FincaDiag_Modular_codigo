#!/bin/bash
# mttr_stress_pi.sh
# Prueba de estres para medir MTTR (Mean Time To Recovery) del gateway.
# Indicador Objetivo 4: tiempo medio que tarda el sistema en restaurar
# la publicacion tras una caida del broker MQTT.
#
# Protocolo:
#   1. Inicia ciclo: tira mosquitto.
#   2. Lanza el gateway -> debe spoolear.
#   3. Restaura mosquitto y arranca el cronometro.
#   4. Re-ejecuta gateway: vacia el spool y publica.
#   5. Detiene cronometro cuando el spool queda en 0 archivos.
#   6. Registra: timestamp_inicio, t_spool_max, t_recovery_s, msgs_spooled, msgs_published.
#   7. Repite N veces para acumular muestra estadistica.
#
# Uso: ./mttr_stress_pi.sh [N_CICLOS] [SESSION_DIR]
# Default: N_CICLOS=30, sesion 15/05 PM 1PM (mejor sesion historica del proyecto).

set -euo pipefail

N_CICLOS="${1:-30}"
SESSION_DIR="${2:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"

SPOOL_DIR="${SPOOL_DIR:-/tmp/test_spool_obj4}"
PUB_DIR="${PUB_DIR:-/tmp/test_published_obj4}"
RESULTS_FILE="/home/esmeralda/mttr_results.csv"
LOG_FILE="/home/esmeralda/mttr_stress.log"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# Validar sesion
if [ ! -d "$SESSION_DIR" ]; then
    echo "[ERROR] Sesion no existe: $SESSION_DIR"
    exit 1
fi

# Inicializar CSV de resultados
if [ ! -f "$RESULTS_FILE" ]; then
    echo "ciclo,timestamp_inicio,msgs_spooled,t_recovery_s,msgs_published,resultado" > "$RESULTS_FILE"
fi

echo "=== MTTR Stress Test: $N_CICLOS ciclos ===" | tee -a "$LOG_FILE"
echo "Sesion: $SESSION_DIR" | tee -a "$LOG_FILE"
echo "Inicio: $(date -Iseconds)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

export PYTHONPATH=/opt/fincadiag

run_gateway() {
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
        >/dev/null 2>&1 || return 1
    return 0
}

for i in $(seq 1 "$N_CICLOS"); do
    TS_INICIO=$(date -Iseconds)
    echo "--- Ciclo $i/$N_CICLOS ($TS_INICIO) ---" | tee -a "$LOG_FILE"

    # 1. Limpiar estado previo
    sudo rm -rf "$SPOOL_DIR"/* "$PUB_DIR"/* 2>/dev/null || true

    # 2. Tirar broker
    sudo systemctl stop mosquitto
    sleep 1

    # 3. Lanzar gateway con broker caido -> debe spoolear
    if ! run_gateway; then
        echo "  [SKIP] Gateway fallo al spoolear" | tee -a "$LOG_FILE"
        sudo systemctl start mosquitto
        echo "$i,$TS_INICIO,0,0,0,FAIL_SPOOL" >> "$RESULTS_FILE"
        continue
    fi

    SPOOL_COUNT=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
    echo "  Spooled: $SPOOL_COUNT mensajes" | tee -a "$LOG_FILE"

    if [ "$SPOOL_COUNT" -eq 0 ]; then
        sudo systemctl start mosquitto
        echo "$i,$TS_INICIO,0,0,0,NO_SPOOL" >> "$RESULTS_FILE"
        continue
    fi

    # 4. Restaurar broker y arrancar cronometro
    T_START=$(date +%s.%N)
    sudo systemctl start mosquitto

    # Esperar a que mosquitto este aceptando conexiones (max 10s)
    for j in $(seq 1 20); do
        if mosquitto_pub -h localhost -p 8883 \
            --cafile /etc/fincadiag/certs/ca.crt \
            --cert /etc/fincadiag/certs/client.crt \
            --key /etc/fincadiag/certs/client.key \
            --tls-version tlsv1.3 \
            -t "fincadiag/healthcheck" -m "ok" -q 0 >/dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done

    # 5. Drenar spool con --drain-only (sin reprocesar sesion)
    set +e
    python3 -m fincadiag.gateway.runtime \
        --drain-only \
        --topic-root "fincadiag/la_esmeralda" \
        --mqtt-host localhost --mqtt-port 8883 \
        --tls-enabled \
        --ca-path /etc/fincadiag/certs/ca.crt \
        --cert-path /etc/fincadiag/certs/client.crt \
        --key-path /etc/fincadiag/certs/client.key \
        --tls-min-version 1.3 \
        --spool-dir "$SPOOL_DIR" \
        --published-dir "$PUB_DIR" \
        >/dev/null 2>&1
    DRAIN_RC=$?
    set -e
    if [ "$DRAIN_RC" -ne 0 ]; then
        T_END=$(date +%s.%N)
        T_RECOVERY=$(echo "$T_END - $T_START" | bc)
        echo "$i,$TS_INICIO,$SPOOL_COUNT,$T_RECOVERY,0,FAIL_RECOVERY" >> "$RESULTS_FILE"
        echo "  [FAIL] Drain fallo (rc=$DRAIN_RC)" | tee -a "$LOG_FILE"
        continue
    fi
    T_END=$(date +%s.%N)
    T_RECOVERY=$(echo "$T_END - $T_START" | bc)

    # 6. Verificar spool vacio
    SPOOL_AFTER=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
    PUB_COUNT=$(find "$PUB_DIR" -name "*.jsonl" 2>/dev/null | wc -l)

    if [ "$SPOOL_AFTER" -eq 0 ]; then
        RESULTADO="PASS"
        printf "  [PASS] Recovery en %.3fs | published=%s\n" "$T_RECOVERY" "$PUB_COUNT" | tee -a "$LOG_FILE"
    else
        RESULTADO="FAIL_DRAIN"
        echo "  [FAIL] Spool no se vacio (quedaron $SPOOL_AFTER)" | tee -a "$LOG_FILE"
    fi

    echo "$i,$TS_INICIO,$SPOOL_COUNT,$T_RECOVERY,$PUB_COUNT,$RESULTADO" >> "$RESULTS_FILE"

    # Pausa entre ciclos para no sobrecargar el broker
    sleep 2
done

echo "" | tee -a "$LOG_FILE"
echo "=== Resumen ===" | tee -a "$LOG_FILE"
echo "Resultados en: $RESULTS_FILE" | tee -a "$LOG_FILE"

# Calculo rapido de MTTR media en los PASS
python3 - <<PYEOF
import csv
results = []
with open("$RESULTS_FILE") as f:
    reader = csv.DictReader(f)
    for row in reader:
        if row['resultado'] == 'PASS':
            results.append(float(row['t_recovery_s']))

if results:
    n = len(results)
    media = sum(results) / n
    mediana = sorted(results)[n // 2]
    minimo = min(results)
    maximo = max(results)
    desv = (sum((x - media) ** 2 for x in results) / max(n - 1, 1)) ** 0.5
    print(f"  Ciclos exitosos: {n}")
    print(f"  MTTR media:      {media:.3f} s")
    print(f"  MTTR mediana:    {mediana:.3f} s")
    print(f"  MTTR min - max:  {minimo:.3f} - {maximo:.3f} s")
    print(f"  MTTR desv.est.:  {desv:.3f} s")
else:
    print("  Sin ciclos exitosos.")
PYEOF

echo "Fin: $(date -Iseconds)" | tee -a "$LOG_FILE"
