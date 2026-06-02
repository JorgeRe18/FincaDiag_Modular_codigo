"""Verificar que el publisher corregido funciona con prueba directa."""
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

print("=== Verificar publisher.py tiene loop_start ===")
run(c, "grep -n 'loop_start' /opt/fincadiag/fincadiag/gateway/publisher.py")

print("=== Test directo: spool real + mosquitto_sub reiniciado post-drain ===")
run(c, r"""
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
rm -rf /tmp/spool_direct /tmp/pub_direct /tmp/mqtt_direct.txt
mkdir -p /tmp/spool_direct /tmp/pub_direct

# Crear spool con formato GatewayMessage real
cat > /tmp/spool_direct/test_batch.jsonl << 'BATCH'
{"topic": "fincadiag/la_esmeralda/session/test_direct", "payload": {"batch_id": "direct_test", "status": "ok"}, "qos": 1, "retain": false, "source_sample_id": "", "event_type": "session_summary", "event_timestamp": "2026-05-29T00:00:00"}
BATCH

# Iniciar mosquitto_sub (con stderr visible)
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > /tmp/mqtt_direct.txt 2>/tmp/mqtt_direct.err &
SUB=$!
sleep 1
cat /tmp/mqtt_direct.err

# Drenar spool
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime --spool-dir /tmp/spool_direct --published-dir /tmp/pub_direct --drain-only

# Esperar recepcion
sleep 2
kill "$SUB" 2>/dev/null || true

echo "--- Mensajes recibidos ---"
cat /tmp/mqtt_direct.txt
echo "--- Errores mosquitto_sub ---"
cat /tmp/mqtt_direct.err
echo "--- Archivos spool ---"
ls -la /tmp/spool_direct/
""", timeout=60)

c.close()
print("=== Terminado ===")
