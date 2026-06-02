"""Ejecutar run_all_tests_pi.sh en la Raspberry Pi."""
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

print(f"=== Ejecutando suite con sesion: {SESSION} ===")
run(c, f"bash /opt/fincadiag/Gateway/tests/run_all_tests_pi.sh {SESSION}", timeout=300)

c.close()
print("=== Terminado ===")
