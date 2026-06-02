"""Verificar como se invoca el daemon fincadiag-gateway."""
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

print("=== Verificar unit del daemon ===")
run(c, "systemctl cat fincadiag-gateway | grep -E 'ExecStart|PYTHONPATH'")
run(c, "cat /etc/systemd/system/fincadiag-gateway.service 2>/dev/null || cat /lib/systemd/system/fincadiag-gateway.service 2>/dev/null")

c.close()
print("=== Terminado ===")
