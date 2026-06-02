"""Probar drain-only con formato real de GatewayMessage y mosquitto_sub."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

def run(client, cmd, timeout=60, show=True):
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

print("=== Test: spool con formato GatewayMessage real + mosquitto_sub ===")
run(c, r"""
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
rm -rf /tmp/spool_real /tmp/pub_real /tmp/mqtt_real.txt
mkdir -p /tmp/spool_real /tmp/pub_real

# Crear spool con formato correcto de GatewayMessage
cat > /tmp/spool_real/test_batch.jsonl << 'BATCH'
{"topic": "fincadiag/la_esmeralda/session/test", "payload": {"batch_id": "test", "status": "ok"}, "qos": 1, "retain": false, "source_sample_id": "", "event_type": "session_summary", "event_timestamp": "2026-05-29T00:00:00"}
BATCH

# Iniciar mosquitto_sub
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > /tmp/mqtt_real.txt 2>/dev/null &
SUB=$!
sleep 1

# Verificar que mosquitto esta activo
systemctl is-active mosquitto

# Drenar spool
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --spool-dir /tmp/spool_real --published-dir /tmp/pub_real --drain-only

# Esperar recepcion
sleep 2
kill "$SUB" 2>/dev/null || true

echo "--- Mensajes recibidos ---"
cat /tmp/mqtt_real.txt
echo "--- Archivos en pub_real ---"
ls -la /tmp/pub_real/
echo "--- Archivos en spool_real ---"
ls -la /tmp/spool_real/
""", timeout=60)

c.close()
print("=== Terminado ===")
