"""Paso 2b: refrescar apt, reintentar instalacion, descubrir donde esta fincadiag."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

def run(client, cmd, sudo=False, timeout=300):
    if sudo:
        cmd = f"echo {PASSWORD} | sudo -S bash -c '{cmd}'"
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out.strip(): print(out)
    if err.strip() and "password for" not in err.lower(): print("[stderr]", err)
    return out

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("\n=== [A] Buscar fincadiag en la Pi ===")
run(c, "find /opt /usr/local /home/esmeralda -maxdepth 5 -name 'runtime.py' -path '*gateway*' 2>/dev/null")
print("--- pip show ---")
run(c, "python3 -m pip show fincadiag 2>&1 || echo 'pip show fallo'")
print("--- which fincadiag CLI ---")
run(c, "which fincadiag 2>&1; python3 -c 'import fincadiag; print(fincadiag.__file__)' 2>&1")

print("\n=== [B] apt-get update + install at + bc ===")
run(c, "apt-get update && apt-get install -y at bc", sudo=True, timeout=300)

print("\n=== [C] Estado de atd ===")
run(c, "systemctl status atd --no-pager 2>&1 | head -10", sudo=True)
run(c, "systemctl enable --now atd 2>&1; systemctl is-active atd", sudo=True)

print("\n=== [D] Verificar binarios ===")
run(c, "which at atq atrm bc")

c.close()
print("\nPaso 2b completado.")
