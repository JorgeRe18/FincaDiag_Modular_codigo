"""Borrar __pycache__ y .pyc para forzar recarga del publisher corregido."""
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

print("=== Borrar pycache ===")
run(c, "find /opt/fincadiag -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null; find /opt/fincadiag -name '*.pyc' -delete 2>/dev/null; echo 'pycache borrado'")

print("=== Verificar MD5 del publisher.py ===")
run(c, "md5sum /opt/fincadiag/fincadiag/gateway/publisher.py")
run(c, "grep -n 'loop_start' /opt/fincadiag/fincadiag/gateway/publisher.py")

print("=== Re-ejecutar drain-only con spool de 13 mensajes ===")
run(c, r"""
SESSION_DIR=""" + f'"{SESSION}"' + r"""
SPOOL_DIR="/tmp/spool_nocache"
PUB_DIR="/tmp/pub_nocache"
rm -rf "$SPOOL_DIR" "$PUB_DIR"
mkdir -p "$SPOOL_DIR" "$PUB_DIR"

# Crear spool
sudo systemctl stop mosquitto
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime \
    --session-dir "$SESSION_DIR" \
    --topic-root "fincadiag/la_esmeralda" \
    --mqtt-host localhost --mqtt-port 8883 --tls-enabled \
    --ca-path /etc/fincadiag/certs/ca.crt \
    --cert-path /etc/fincadiag/certs/client.crt \
    --key-path /etc/fincadiag/certs/client.key \
    --tls-min-version 1.3 \
    --spool-dir "$SPOOL_DIR" \
    --published-dir "$PUB_DIR" >/dev/null 2>&1

sudo systemctl start mosquitto
sleep 2

echo "--- Spool antes ---"
wc -l "$SPOOL_DIR"/*.jsonl

# Drenar con modulo -m (sin pycache)
export PYTHONPATH=/opt/fincadiag
python3 -B -m fincadiag.gateway.runtime --spool-dir "$SPOOL_DIR" --published-dir "$PUB_DIR" --drain-only

echo "--- Spool despues ---"
ls -la "$SPOOL_DIR/"
""", timeout=120)

c.close()
print("=== Terminado ===")
