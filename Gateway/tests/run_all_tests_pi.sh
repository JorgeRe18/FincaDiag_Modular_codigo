#!/bin/bash
# Suite completa de pruebas de gateway para Raspberry Pi
# Objetivo: validar contrato, TLS, resiliencia, suscripcion, idempotencia
# y consistencia de metricas antes del contraste estadistico (Objetivo 4).

set -euo pipefail

SESSION_DIR="${1:-}"
if [ -z "$SESSION_DIR" ]; then
    echo "Uso: $0 <ruta_sesion_procesada>"
    echo "Ejemplo: $0 /var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PASS=0
FAIL=0

echo "=========================================="
echo "SUITE DE PRUEBAS GATEWAY (Raspberry Pi)"
echo "=========================================="
echo ""

# Prueba 1: Schema
echo "[1/6] Validacion de contrato JSON..."
if bash "$SCRIPT_DIR/validate_schema_pi.sh" "$SESSION_DIR"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
fi
echo ""

# Prueba 2: TLS handshake
echo "[2/6] Prueba TLS (handshake)..."
if bash "$SCRIPT_DIR/tls_handshake_pi.sh"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
fi
echo ""

# Prueba 3: Resiliencia (broker caido)
echo "[3/6] Prueba de resiliencia (spool)..."
if bash "$SCRIPT_DIR/resilience_spool_pi.sh" "$SESSION_DIR"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
fi
echo ""

# Prueba 4: Suscripcion MQTT
echo "[4/6] Validacion semantica con mosquitto_sub..."
if bash "$SCRIPT_DIR/subscribe_validate_pi.sh" "$SESSION_DIR"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
fi
echo ""

# Prueba 5: Idempotencia
echo "[5/6] Prueba de idempotencia..."
if bash "$SCRIPT_DIR/idempotency_pi.sh" "$SESSION_DIR"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
fi
echo ""

# Prueba 6: Objetivo 4 (metricas)
echo "[6/6] Validacion de metricas Objetivo 4..."
if bash "$SCRIPT_DIR/validate_objective4_pi.sh" "$SESSION_DIR"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
fi
echo ""

echo "=========================================="
echo "RESULTADOS: $PASS pass / $FAIL fail"
echo "=========================================="

if [ "$FAIL" -eq 0 ]; then
    echo "[PASS] Suite completada exitosamente."
    exit 0
else
    echo "[FAIL] Hubo errores en la suite."
    exit 1
fi
