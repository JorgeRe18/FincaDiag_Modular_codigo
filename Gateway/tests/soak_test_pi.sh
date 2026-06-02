#!/bin/bash
# soak_test_pi.sh
# Prueba de operacion continua (soak test) del gateway.
# Objetivo: verificar estabilidad bajo operacion sostenida durante N horas:
#   - sin memory leaks
#   - sin caidas de conexion no recuperadas
#   - sin acumulacion de errores
#   - sin crecimiento descontrolado de spool
#
# Cada N segundos se relanza la corrida del gateway sobre la misma sesion,
# emulando la cadencia operativa esperada (1 sesion cada 4-6 horas en real).
# Aqui se acelera (cada 60s por default) para acumular ciclos en menos tiempo.
#
# Uso: ./soak_test_pi.sh [DURACION_HORAS] [INTERVALO_S] [SESSION_DIR]
# Default: 2 horas, intervalo 60s entre corridas

set -euo pipefail

DURACION_H="${1:-2}"
INTERVALO_S="${2:-60}"
SESSION_DIR="${3:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"

SPOOL_DIR="${SPOOL_DIR:-/tmp/test_spool_obj4}"
PUB_DIR="${PUB_DIR:-/tmp/test_published_obj4}"
RESULTS_FILE="/home/esmeralda/soak_results.csv"
LOG_FILE="/home/esmeralda/soak_test.log"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

if [ ! -d "$SESSION_DIR" ]; then
    echo "[ERROR] Sesion no existe: $SESSION_DIR"
    exit 1
fi

sudo systemctl start mosquitto
sleep 1

DURACION_S=$(echo "$DURACION_H * 3600 / 1" | bc)  # forzar entero
T_INICIO=$(date +%s)
T_FIN=$((T_INICIO + DURACION_S))

if [ ! -f "$RESULTS_FILE" ]; then
    echo "ciclo,timestamp,t_run_s,mem_mb,cpu_pct,spool_files,pub_files,exit_code" > "$RESULTS_FILE"
fi

echo "=== SOAK TEST: ${DURACION_H}h, intervalo ${INTERVALO_S}s ===" | tee -a "$LOG_FILE"
echo "Sesion: $SESSION_DIR" | tee -a "$LOG_FILE"
echo "Inicio: $(date -Iseconds)" | tee -a "$LOG_FILE"
echo "Fin estimado: $(date -d "@$T_FIN" -Iseconds)" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

export PYTHONPATH=/opt/fincadiag

CICLO=0
while [ "$(date +%s)" -lt "$T_FIN" ]; do
    CICLO=$((CICLO + 1))
    TS=$(date -Iseconds)

    # Limpiar published para no llenar el disco; mantener spool para ver acumulacion
    sudo rm -rf "$PUB_DIR"/* 2>/dev/null || true

    # Lanzar gateway en background, medir mem maxima via /proc/$PID/status
    T_RUN_START=$(date +%s.%N)
    set +e
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
    GW_PID=$!

    # Muestrear memoria mientras corre
    MEM_KB_MAX=0
    while kill -0 "$GW_PID" 2>/dev/null; do
        VMRSS=$(awk '/^VmRSS:/ {print $2}' /proc/$GW_PID/status 2>/dev/null)
        if [ -n "$VMRSS" ] && [ "$VMRSS" -gt "$MEM_KB_MAX" ]; then
            MEM_KB_MAX=$VMRSS
        fi
        sleep 0.1
    done
    wait "$GW_PID"
    EXIT_CODE=$?
    set -e
    T_RUN_END=$(date +%s.%N)
    T_RUN=$(echo "$T_RUN_END - $T_RUN_START" | bc)

    MEM_MB=$(echo "scale=1; $MEM_KB_MAX / 1024" | bc)
    CPU_PCT=0  # ya no se mide CPU% por simplicidad (no critico para soak)

    SPOOL_COUNT=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
    PUB_COUNT=$(find "$PUB_DIR" -name "*.jsonl" 2>/dev/null | wc -l)

    printf "  [%s] ciclo=%d t=%.2fs mem=%.1fMB cpu=%s%% spool=%s pub=%s exit=%s\n" \
        "$TS" "$CICLO" "$T_RUN" "$MEM_MB" "$CPU_PCT" "$SPOOL_COUNT" "$PUB_COUNT" "$EXIT_CODE" \
        | tee -a "$LOG_FILE"

    echo "$CICLO,$TS,$T_RUN,$MEM_MB,$CPU_PCT,$SPOOL_COUNT,$PUB_COUNT,$EXIT_CODE" >> "$RESULTS_FILE"

    # Alerta si memoria crece > 500 MB (posible leak)
    MEM_INT=$(printf "%.0f" "$MEM_MB")
    if [ "$MEM_INT" -gt 500 ]; then
        echo "  [WARN] Memoria alta: ${MEM_MB}MB" | tee -a "$LOG_FILE"
    fi

    # Alerta si spool crece sin parar (mas de 100 archivos = no se vacia)
    if [ "$SPOOL_COUNT" -gt 100 ]; then
        echo "  [WARN] Spool grande: $SPOOL_COUNT archivos" | tee -a "$LOG_FILE"
    fi

    sleep "$INTERVALO_S"
done

rm -f /tmp/soak_stats.txt

echo "" | tee -a "$LOG_FILE"
echo "=== Resumen soak test ===" | tee -a "$LOG_FILE"

python3 - <<PYEOF
import csv
rows = []
with open("$RESULTS_FILE") as f:
    for r in csv.DictReader(f):
        try:
            rows.append({
                'ciclo': int(r['ciclo']),
                't_run': float(r['t_run_s']),
                'mem': float(r['mem_mb']),
                'spool': int(r['spool_files']),
                'pub': int(r['pub_files']),
                'exit': int(r['exit_code']),
            })
        except Exception:
            continue

if rows:
    n = len(rows)
    fails = sum(1 for r in rows if r['exit'] != 0)
    mem_first = rows[0]['mem']
    mem_last = rows[-1]['mem']
    mem_max = max(r['mem'] for r in rows)
    spool_max = max(r['spool'] for r in rows)
    t_run_avg = sum(r['t_run'] for r in rows) / n

    print(f"  Ciclos completados:    {n}")
    print(f"  Fallos (exit!=0):      {fails} ({100*fails/n:.1f}%)")
    print(f"  Tiempo run medio:      {t_run_avg:.3f}s")
    print(f"  Memoria inicial:       {mem_first:.1f}MB")
    print(f"  Memoria final:         {mem_last:.1f}MB")
    print(f"  Memoria max observada: {mem_max:.1f}MB")
    print(f"  Spool max observado:   {spool_max} archivos")

    leak_pct = (mem_last - mem_first) / mem_first * 100 if mem_first > 0 else 0
    print(f"  Variacion de memoria:  {leak_pct:+.1f}%")
    if abs(leak_pct) < 10:
        print(f"  [PASS] Sin indicios de memory leak (variacion < 10%)")
    else:
        print(f"  [WARN] Variacion notable: revisar tendencia")
PYEOF

echo "Fin: $(date -Iseconds)" | tee -a "$LOG_FILE"
echo "Resultados: $RESULTS_FILE" | tee -a "$LOG_FILE"
