#!/bin/bash
# Ejecutar en Raspberry Pi - MODO PRODUCCION TLS
# chmod +x tmp_run_4_sessions_raspberry_production.sh
# ./tmp_run_4_sessions_raspberry_production.sh

set -e

PYTHONPATH=/opt/fincadiag/src
export PYTHONPATH

RUNTIME="python3 -m fincadiag.gateway.runtime"
SPOOL_DIR="/var/lib/fincadiag/spool"
PUBLISHED_DIR="/var/lib/fincadiag/published"

# Configuracion TLS del broker local
MQTT_HOST="127.0.0.1"
MQTT_PORT="8883"
TOPIC_ROOT="fincadiag/la_esmeralda"
CA_PATH="/etc/fincadiag/certs/ca.crt"
CERT_PATH="/etc/fincadiag/certs/client.crt"
KEY_PATH="/etc/fincadiag/certs/client.key"

BASE_DIR="/var/lib/fincadiag/processed/visits"

declare -A SESSIONS
SESSIONS["11_AM"]="$BASE_DIR/Visita_11_05_2026/sesiones/TOMA_AM__2AM__Captura_20260511_021505"
SESSIONS["12_PM"]="$BASE_DIR/Visita_12_05_2026/sesiones/TOMA_PM__1PM__Captura_20260512_130005"
SESSIONS["14_AM"]="$BASE_DIR/Visita_14_05_2026/sesiones/TOMA_AM__2AM__Captura_20260514_021505"
SESSIONS["14_PM"]="$BASE_DIR/Visita_14_05_2026/sesiones/TOMA_PM__1PM__Captura_20260514_130006"

mkdir -p "$SPOOL_DIR"
mkdir -p "$PUBLISHED_DIR"

# Verificar broker Mosquitto activo
if ! systemctl is-active --quiet mosquitto; then
    echo "ADVERTENCIA: mosquitto no esta activo. Iniciando..."
    sudo systemctl start mosquitto
    sleep 2
fi

echo "Broker: $MQTT_HOST:$MQTT_PORT"
echo ""

for key in "11_AM" "12_PM" "14_AM" "14_PM"; do
    session_dir="${SESSIONS[$key]}"
    if [ ! -d "$session_dir" ]; then
        echo "ERROR: Sesion no encontrada: $session_dir"
        exit 1
    fi
    echo ""
    echo "--- Ejecutando $key (PRODUCCION TLS) ---"
    $RUNTIME \
        --visit-dir "$session_dir" \
        --spool-dir "$SPOOL_DIR" \
        --published-dir "$PUBLISHED_DIR" \
        --mqtt-host "$MQTT_HOST" \
        --mqtt-port "$MQTT_PORT" \
        --topic-root "$TOPIC_ROOT" \
        --ca-path "$CA_PATH" \
        --cert-path "$CERT_PATH" \
        --key-path "$KEY_PATH" \
        --tls-min-version 1.3
done

echo ""
echo "=========================================="
echo "Verificando archivos publicados"
echo "=========================================="
ls -la "$PUBLISHED_DIR"/

echo ""
echo "Resumen:"
for f in "$PUBLISHED_DIR"/*.readable.json; do
    if [ -f "$f" ]; then
        name=$(basename "$f")
        msg_count=$(python3 -c "import json; print(json.load(open('$f'))['message_count'])")
        echo "  $name: $msg_count mensajes"
    fi
done
