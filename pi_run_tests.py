"""Ejecutar suite de pruebas gateway en Raspberry Pi via SSH."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

def run(client, cmd, timeout=120, show=True):
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

print("=== 1. Sesiones disponibles ===")
run(c, "find /var/lib/fincadiag/processed/visits -name 'correlation_summary.json' | head -15")

print("=== 2. Scripts de prueba ===")
run(c, "ls /home/esmeralda/*_pi.sh /opt/fincadiag/Gateway/tests/*_pi.sh 2>/dev/null | grep -E 'validate_schema|tls_handshake|resilience_spool|subscribe_validate|idempotency|validate_objective4|run_all_tests'")

print("=== 3. Estado mosquitto ===")
run(c, "systemctl is-active mosquitto")

print("=== 4. Estado daemon ===")
run(c, "systemctl is-active fincadiag-gateway")

c.close()
print("=== Listo ===")
