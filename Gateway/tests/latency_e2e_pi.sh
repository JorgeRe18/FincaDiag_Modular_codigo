#!/bin/bash
# latency_e2e_pi.sh
# Mide latencia end-to-end del gateway: tiempo desde que se inicia el
# procesamiento de una sesion hasta que el ultimo mensaje queda publicado en MQTT.
#
# Metodologia:
#   - Suscriptor MQTT en background captura timestamps de llegada.
#   - Se lanza el gateway con la sesion objetivo.
#   - Se registra t_inicio (antes de lanzar) y t_fin (ultimo mensaje recibido).
#   - latency_total = t_fin - t_inicio.
#   - latency_per_msg = latency_total / N_mensajes.
#
# Uso: ./latency_e2e_pi.sh [N_CICLOS] [SESSION_DIR]
# Default: N_CICLOS=10

set -euo pipefail

N_CICLOS="${1:-10}"
SESSION_DIR="${2:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"

SPOOL_DIR="${SPOOL_DIR:-/tmp/test_spool_obj4}"
PUB_DIR="${PUB_DIR:-/tmp/test_published_obj4}"
RESULTS_FILE="/home/esmeralda/latency_e2e_results.csv"
LOG_FILE="/home/esmeralda/latency_e2e.log"
SUB_LOG="/tmp/mqtt_sub_$$.log"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

if [ ! -d "$SESSION_DIR" ]; then
    echo "[ERROR] Sesion no existe: $SESSION_DIR"
    exit 1
fi

# Asegurar mosquitto activo
sudo systemctl start mosquitto
sleep 1

if [ ! -f "$RESULTS_FILE" ]; then
    echo "ciclo,timestamp_inicio,n_mensajes,t_total_s,t_per_msg_ms,t_primer_msg_s,t_ultimo_msg_s" > "$RESULTS_FILE"
fi

echo "=== Latencia E2E: $N_CICLOS ciclos ===" | tee -a "$LOG_FILE"
echo "Sesion: $SESSION_DIR" | tee -a "$LOG_FILE"
echo "Inicio: $(date -Iseconds)" | tee -a "$LOG_FILE"

export PYTHONPATH=/opt/fincadiag

for i in $(seq 1 "$N_CICLOS"); do
    TS_INICIO=$(date -Iseconds)
    echo "--- Ciclo $i/$N_CICLOS ($TS_INICIO) ---" | tee -a "$LOG_FILE"

    # Limpiar publicaciones previas
    sudo rm -rf "$SPOOL_DIR"/* "$PUB_DIR"/* 2>/dev/null || true

    # Lanzar suscriptor en background (captura tiempo de cada mensaje)
    > "$SUB_LOG"
    mosquitto_sub -h localhost -p 8883 \
        --cafile /etc/fincadiag/certs/ca.crt \
        --cert /etc/fincadiag/certs/client.crt \
        --key /etc/fincadiag/certs/client.key \
        --tls-version tlsv1.3 \
        -t "fincadiag/la_esmeralda/#" -v \
        -F "%U %t" \
        > "$SUB_LOG" 2>/dev/null &
    SUB_PID=$!

    # Esperar a que el subscriber este realmente conectado (TLS 1.3 handshake)
    # Truco: enviar un mensaje warmup en topic separado y ver si llega
    SUB_READY=0
    for j in $(seq 1 30); do
        mosquitto_pub -h localhost -p 8883 \
            --cafile /etc/fincadiag/certs/ca.crt \
            --cert /etc/fincadiag/certs/client.crt \
            --key /etc/fincadiag/certs/client.key \
            --tls-version tlsv1.3 \
            -t "fincadiag/la_esmeralda/_warmup" -m "ping" -q 0 >/dev/null 2>&1
        sleep 0.2
        if grep -q "_warmup" "$SUB_LOG" 2>/dev/null; then
            SUB_READY=1
            break
        fi
    done

    if [ "$SUB_READY" -eq 0 ]; then
        echo "  [SKIP] Subscriber no se conecto en 6s" | tee -a "$LOG_FILE"
        kill $SUB_PID 2>/dev/null || true
        echo "$i,$TS_INICIO,0,0,0,0,0" >> "$RESULTS_FILE"
        continue
    fi

    # Limpiar el warmup del log para que no contamine el conteo
    grep -v "_warmup" "$SUB_LOG" > "${SUB_LOG}.clean" && mv "${SUB_LOG}.clean" "$SUB_LOG"

    T_START=$(date +%s.%N)

    # Lanzar gateway (publicacion real)
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
        >/dev/null 2>&1 || {
        echo "  [SKIP] Gateway fallo" | tee -a "$LOG_FILE"
        kill $SUB_PID 2>/dev/null || true
        continue
    }

    T_END_GW=$(date +%s.%N)

    # Esperar 2s para que lleguen los ultimos mensajes
    sleep 2
    kill $SUB_PID 2>/dev/null || true
    wait $SUB_PID 2>/dev/null || true

    # Procesar log del suscriptor
    N_MSGS=$(wc -l < "$SUB_LOG")
    if [ "$N_MSGS" -eq 0 ]; then
        echo "  [WARN] Sin mensajes recibidos por subscriptor" | tee -a "$LOG_FILE"
        echo "$i,$TS_INICIO,0,0,0,0,0" >> "$RESULTS_FILE"
        continue
    fi

    # Primer y ultimo timestamp del log (formato: epoch.frac topic)
    T_FIRST=$(head -n1 "$SUB_LOG" | awk '{print $1}')
    T_LAST=$(tail -n1 "$SUB_LOG" | awk '{print $1}')

    T_TOTAL=$(echo "$T_LAST - $T_START" | bc)
    T_PRIMER=$(echo "$T_FIRST - $T_START" | bc)
    T_ULTIMO=$(echo "$T_LAST - $T_START" | bc)
    T_PER_MSG=$(echo "scale=3; ($T_TOTAL * 1000) / $N_MSGS" | bc)

    printf "  [OK] n=%s, total=%.3fs, primer=%.3fs, ultimo=%.3fs, per_msg=%.3fms\n" \
        "$N_MSGS" "$T_TOTAL" "$T_PRIMER" "$T_ULTIMO" "$T_PER_MSG" | tee -a "$LOG_FILE"

    echo "$i,$TS_INICIO,$N_MSGS,$T_TOTAL,$T_PER_MSG,$T_PRIMER,$T_ULTIMO" >> "$RESULTS_FILE"

    sleep 2
done

rm -f "$SUB_LOG"

echo "" | tee -a "$LOG_FILE"
echo "=== Resumen ===" | tee -a "$LOG_FILE"

python3 - <<PYEOF
import csv
rows = []
with open("$RESULTS_FILE") as f:
    for r in csv.DictReader(f):
        try:
            n = int(r['n_mensajes'])
            if n > 0:
                rows.append({
                    'total': float(r['t_total_s']),
                    'per_msg': float(r['t_per_msg_ms']),
                    'primer': float(r['t_primer_msg_s']),
                })
        except Exception:
            continue

if rows:
    n = len(rows)
    def stats(vals):
        m = sum(vals) / n
        srt = sorted(vals)
        med = srt[n // 2]
        return m, med, min(vals), max(vals)
    tt = stats([r['total'] for r in rows])
    pm = stats([r['per_msg'] for r in rows])
    pr = stats([r['primer'] for r in rows])
    print(f"  Ciclos validos: {n}")
    print(f"  Latencia total: media={tt[0]:.3f}s, mediana={tt[1]:.3f}s, min={tt[2]:.3f}s, max={tt[3]:.3f}s")
    print(f"  Por mensaje:    media={pm[0]:.3f}ms, mediana={pm[1]:.3f}ms")
    print(f"  Primer msg:     media={pr[0]:.3f}s, mediana={pr[1]:.3f}s")
PYEOF

echo "Fin: $(date -Iseconds)" | tee -a "$LOG_FILE"
echo "Resultados: $RESULTS_FILE" | tee -a "$LOG_FILE"
