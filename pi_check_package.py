"""Verificar si hay paquete fincadiag instalado en site-packages."""
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

print("=== Verificar path del modulo ===")
run(c, "export PYTHONPATH=/opt/fincadiag; python3 -c 'import fincadiag.gateway.runtime; print(fincadiag.gateway.runtime.__file__)'")
run(c, "python3 -c 'import fincadiag.gateway.runtime; print(fincadiag.gateway.runtime.__file__)'")
run(c, "python3 -c 'import sys; print(\"\\n\".join(sys.path))'")
run(c, "find /usr -path '*/site-packages/fincadiag*' -o -path '*/dist-packages/fincadiag*' 2>/dev/null | head -10")
run(c, "pip3 show fincadiag 2>/dev/null || echo 'No instalado via pip'")

c.close()
print("=== Terminado ===")
