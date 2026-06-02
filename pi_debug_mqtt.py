"""Debug MQTT en Pi: probar mosquitto_pub/sub y drain-only verboso."""
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

print("=== Test basico mosquitto_pub/sub ===")
run(c, r"""
CA="/etc/fincadiag/certs/ca.crt"
CERT="/etc/fincadiag/certs/client.crt"
KEY="/etc/fincadiag/certs/client.key"
OUT="/tmp/mqtt_test_basic.txt"
rm -f "$OUT"
mosquitto_sub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "test/topic" -v > "$OUT" 2>/dev/null &
SUB=$!
sleep 1
mosquitto_pub --cafile "$CA" --cert "$CERT" --key "$KEY" -h localhost -p 8883 -t "test/topic" -m '{"msg":"hello"}'
sleep 1
kill "$SUB" 2>/dev/null || true
cat "$OUT"
""", timeout=30)

print("=== Test drain-only verboso ===")
run(c, r"""
export PYTHONPATH=/opt/fincadiag
rm -rf /tmp/spool_test /tmp/pub_test
mkdir -p /tmp/spool_test /tmp/pub_test
cat > /tmp/spool_test/test_batch.jsonl << 'BATCH'
{"type": "session_summary", "payload": {"batch_id": "test", "session_name": "test"}}
BATCH
python3 -m fincadiag.gateway.runtime --spool-dir /tmp/spool_test --published-dir /tmp/pub_test --drain-only 2>&1
""", timeout=30)

print("=== Verificar archivos generados ===")
run(c, "ls -la /tmp/pub_test/")

print("=== Verificar mosquitto logs ===")
run(c, "sudo journalctl -u mosquitto --since '5 minutes ago' --no-pager | tail -20")

c.close()
print("=== Terminado ===")
