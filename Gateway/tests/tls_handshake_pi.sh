#!/bin/bash
# Prueba 2 (Pi): Validacion de TLS — handshake y version minima
# Objetivo: confirmar que el broker solo acepta TLS 1.3 como configurado.
# Relevante para Objetivo 4: garantiza integridad de canal de publicacion.

set -euo pipefail

CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
HOST="localhost"
PORT="8883"

echo "=== Prueba TLS ==="

# Test A: TLS 1.2 debe FALLAR (gateway configura TLS 1.3 minimo)
echo "--- Test A: TLS 1.2 debe rechazarse ---"
if openssl s_client -connect "$HOST:$PORT" -tls1_2 -CAfile "$CA" -cert "$CERT" -key "$KEY" </dev/null 2>/dev/null | grep -q "Verify return code: 0"; then
    echo "  [FAIL] TLS 1.2 fue aceptado (deberia rechazarse)"
    exit 1
else
    echo "  [PASS] TLS 1.2 correctamente rechazado"
fi

# Test B: TLS 1.3 debe OK
echo "--- Test B: TLS 1.3 debe aceptarse ---"
if openssl s_client -connect "$HOST:$PORT" -tls1_3 -CAfile "$CA" -cert "$CERT" -key "$KEY" </dev/null 2>/dev/null | grep -q "Verify return code: 0"; then
    echo "  [PASS] TLS 1.3 aceptado con certificado valido"
else
    echo "  [FAIL] TLS 1.3 rechazado"
    exit 1
fi

# Test C: Certificado sin CA no debe validar
echo "--- Test C: Certificado sin CA debe fallar ---"
if openssl s_client -connect "$HOST:$PORT" -tls1_3 -cert "$CERT" -key "$KEY" </dev/null 2>/dev/null | grep -q "Verify return code: 0"; then
    echo "  [FAIL] Conexion sin CA fue aceptada (deberia fallar)"
    exit 1
else
    echo "  [PASS] Conexion sin CA correctamente rechazada"
fi

echo "[PASS] Todas las pruebas TLS superadas."
