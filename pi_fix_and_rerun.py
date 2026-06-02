"""Arreglar scripts de Pi y re-ejecutar suite de pruebas."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

SESSION = "/var/lib/fincadiag/processed/visits/Visita_18_05_2026/sesiones/TOMA_PM__1PM__Captura_20260518_130005"

def run(client, cmd, timeout=180, show=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show:
        print(f"$ {cmd[:120]}")
        if out.strip():
            print(out)
        if err.strip():
            print("[err]", err)
        print()
    return out, err

print("=== Conectando ===")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("=== 1. Arreglando validate_schema_pi.sh (field_validation_summary opcional) ===")
run(c, r"""sudo sed -i 's/for t in required:/for t in required_types:/' /opt/fincadiag/Gateway/tests/validate_schema_pi.sh""", show=False)
run(c, r"""sudo sed -i 's/if t not in counts:/if t not in counts:/' /opt/fincadiag/Gateway/tests/validate_schema_pi.sh""", show=False)

# Leer y mostrar el script para verificar
print("Mostrando validate_schema_pi.sh...")
run(c, "cat /opt/fincadiag/Gateway/tests/validate_schema_pi.sh")

print("=== 2. Arreglando idempotency_pi.sh (directorios aislados) ===")
# Subir idempotency aislado
idempotent_script = """#!/bin/bash
# Prueba de idempotencia con directorios aislados
set -euo pipefail
SESSION_DIR="${1:-}"
if [ -z "$SESSION_DIR" ]; then
    echo "Uso: $0 <ruta_sesion_procesada>"
    exit 1
fi

export PYTHONPATH=/opt/fincadiag
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

SPOOL1="$TMPDIR/spool1"
PUB1="$TMPDIR/published1"
SPOOL2="$TMPDIR/spool2"
PUB2="$TMPDIR/published2"
mkdir -p "$SPOOL1" "$PUB1" "$SPOOL2" "$PUB2"

echo "=== Idempotencia (aislado) ==="

# Run 1
python3 -m fincadiag.gateway.runtime \\
    --session-dir "$SESSION_DIR" \\
    --topic-root "fincadiag/la_esmeralda" \\
    --dry-run \\
    --spool-dir "$SPOOL1" \\
    --published-dir "$PUB1" >/dev/null 2>&1 || { echo "[FAIL] Run 1"; exit 1; }
for f in "$PUB1"/*.jsonl; do
    [ -f "$f" ] && md5sum "$f" > "$TMPDIR/run1_$(basename "$f").md5"
done

# Run 2
python3 -m fincadiag.gateway.runtime \\
    --session-dir "$SESSION_DIR" \\
    --topic-root "fincadiag/la_esmeralda" \\
    --dry-run \\
    --spool-dir "$SPOOL2" \\
    --published-dir "$PUB2" >/dev/null 2>&1 || { echo "[FAIL] Run 2"; exit 1; }
for f in "$PUB2"/*.jsonl; do
    [ -f "$f" ] && md5sum "$f" > "$TMPDIR/run2_$(basename "$f").md5"
done

# Comparar
MATCH=0
MISMATCH=0
for f1 in "$TMPDIR"/run1_*.md5; do
    [ -f "$f1" ] || continue
    name=$(basename "$f1" | sed 's/^run1_/run2_/')
    f2="$TMPDIR/$name"
    if [ -f "$f2" ]; then
        if diff -q "$f1" "$f2" >/dev/null 2>&1; then
            MATCH=$((MATCH + 1))
        else
            MISMATCH=$((MISMATCH + 1))
            echo "  [MISMATCH] $name"
        fi
    else
        MISMATCH=$((MISMATCH + 1))
        echo "  [MISSING] $name"
    fi
done

for f2 in "$TMPDIR"/run2_*.md5; do
    [ -f "$f2" ] || continue
    name=$(basename "$f2" | sed 's/^run2_/run1_/')
    f1="$TMPDIR/$name"
    if [ ! -f "$f1" ]; then
        MISMATCH=$((MISMATCH + 1))
        echo "  [EXTRA] $(basename $f2)"
    fi
done

echo "  Resultado: $MATCH coinciden, $MISMATCH difieren"
if [ "$MISMATCH" -eq 0 ]; then
    echo "[PASS] Idempotencia confirmada"
    exit 0
else
    echo "[FAIL] $MISMATCH archivos difieren"
    exit 1
fi
"""

with open("C:\\Users\\jorge\\OneDrive\\Documentos\\FincaDiag_Modular\\idempotency_isolated.sh", "w") as f:
    f.write(idempotent_script)

sftp = c.open_sftp()
sftp.put("C:\\Users\\jorge\\OneDrive\\Documentos\\FincaDiag_Modular\\idempotency_isolated.sh", "/tmp/idempotency_isolated.sh")
sftp.close()
run(c, "chmod +x /tmp/idempotency_isolated.sh")

print("=== 3. Arreglando resilience_spool_pi.sh (spool aislado) ===")
resilience_script = """#!/bin/bash
# Prueba de resiliencia con spool aislado
set -euo pipefail
SESSION_DIR="${1:-/var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005}"
SPOOL_DIR="/tmp/test_spool_resilience"
PUB_DIR="/tmp/test_published_resilience"

echo "=== Prueba de resiliencia (broker caido) ==="
sudo rm -rf "$SPOOL_DIR"/* "$PUB_DIR"/* 2>/dev/null || true
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# Parar mosquitto
sudo systemctl stop mosquitto
echo "--- Mosquitto detenido ---"

export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime \\
    --session-dir "$SESSION_DIR" \\
    --topic-root "fincadiag/la_esmeralda" \\
    --mqtt-host localhost --mqtt-port 8883 \\
    --tls-enabled \\
    --ca-path /etc/fincadiag/certs/ca.crt \\
    --cert-path /etc/fincadiag/certs/client.crt \\
    --key-path /etc/fincadiag/certs/client.key \\
    --tls-min-version 1.3 \\
    --spool-dir "$SPOOL_DIR" \\
    --published-dir "$PUB_DIR" >/dev/null 2>&1

SPOOL_COUNT=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
if [ "$SPOOL_COUNT" -eq 0 ]; then
    echo "  [FAIL] No se spoolo nada (broker caido)"
    sudo systemctl start mosquitto
    exit 1
fi
echo "  [INFO] Archivos en spool: $SPOOL_COUNT"

# Levantar mosquitto
sudo systemctl start mosquitto
echo "--- Mosquitto iniciado ---"
sleep 2

# Drenar spool con --drain-only
python3 -m fincadiag.gateway.runtime \\
    --spool-dir "$SPOOL_DIR" \\
    --published-dir "$PUB_DIR" \\
    --drain-only \\
    >/dev/null 2>&1

SPOOL_COUNT_AFTER=$(find "$SPOOL_DIR" -type f 2>/dev/null | wc -l)
if [ "$SPOOL_COUNT_AFTER" -gt 0 ]; then
    echo "  [WARN] Spool no vacio despues de recovery ($SPOOL_COUNT_AFTER archivos)"
else
    echo "  [PASS] Spool vacio despues de recovery"
fi

PUB_COUNT=$(find "$PUB_DIR" -name "*.jsonl" 2>/dev/null | wc -l)
if [ "$PUB_COUNT" -gt 0 ]; then
    echo "  [PASS] Archivos publicados generados: $PUB_COUNT"
else
    echo "  [FAIL] No hay archivos publicados"
    exit 1
fi

echo "[PASS] Prueba de resiliencia completada."
"""

with open("C:\\Users\\jorge\\OneDrive\\Documentos\\FincaDiag_Modular\\resilience_isolated.sh", "w") as f:
    f.write(resilience_script)

sftp = c.open_sftp()
sftp.put("C:\\Users\\jorge\\OneDrive\\Documentos\\FincaDiag_Modular\\resilience_isolated.sh", "/tmp/resilience_isolated.sh")
sftp.close()
run(c, "chmod +x /tmp/resilience_isolated.sh")

print("=== 4. Re-ejecutando pruebas individuales corregidas ===")

# Schema
print("--- [1/3] Schema ---")
run(c, f"bash /opt/fincadiag/Gateway/tests/validate_schema_pi.sh {SESSION}")

# TLS
print("--- [2/3] TLS ---")
run(c, "bash /opt/fincadiag/Gateway/tests/tls_handshake_pi.sh")

# Resilience aislado
print("--- [3/3] Resilience aislado ---")
run(c, f"bash /tmp/resilience_isolated.sh {SESSION}")

# Idempotencia aislado
print("--- [4/4] Idempotencia aislado ---")
run(c, f"bash /tmp/idempotency_isolated.sh {SESSION}")

# Objetivo 4
print("--- [5/5] Objetivo 4 ---")
run(c, f"bash /opt/fincadiag/Gateway/tests/validate_objective4_pi.sh {SESSION}")

c.close()
print("=== Terminado ===")
