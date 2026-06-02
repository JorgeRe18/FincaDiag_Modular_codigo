"""Subir publisher.py corregido a Pi y re-ejecutar pruebas de resiliencia + idempotencia."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]
SESSION = "/var/lib/fincadiag/processed/visits/Visita_18_05_2026/sesiones/TOMA_PM__1PM__Captura_20260518_130005"

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

# Subir publisher.py corregido a /tmp y mover con sudo
print("=== Subiendo publisher.py corregido ===")
sftp = c.open_sftp()
sftp.put("C:\\Users\\jorge\\OneDrive\\Documentos\\FincaDiag_Modular\\src\\fincadiag\\gateway\\publisher.py", "/tmp/publisher_fix.py")
sftp.close()
run(c, "sudo cp /tmp/publisher_fix.py /opt/fincadiag/fincadiag/gateway/publisher.py && sudo chown root:root /opt/fincadiag/fincadiag/gateway/publisher.py")
run(c, "md5sum /opt/fincadiag/fincadiag/gateway/publisher.py")

# Test 1: Resiliencia con mosquitto_sub reiniciado post-recovery
print("=== [1/2] Resiliencia con suscriptor ===")
run(c, f"bash /tmp/resilience_sub2.sh {SESSION}", timeout=180)

# Test 2: Idempotencia aislada
print("=== [2/2] Idempotencia aislada ===")
run(c, f"bash /tmp/idempotency_isolated.sh {SESSION}", timeout=180)

# Test 3: Objetivo 4
print("=== [3/3] Objetivo 4 ===")
run(c, f"bash /opt/fincadiag/Gateway/tests/validate_objective4_pi.sh {SESSION}")

c.close()
print("=== Terminado ===")
