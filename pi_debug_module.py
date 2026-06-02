"""Debug: comparar sys.path entre python3 -c y python3 -m."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

def run(client, cmd, timeout=30, show=True):
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

print("=== sys.path comparison ===")
run(c, "export PYTHONPATH=/opt/fincadiag; python3 -c 'import sys; print(\"\\n\".join(sys.path))'")
run(c, "export PYTHONPATH=/opt/fincadiag; python3 -m fincadiag.gateway.runtime --help 2>&1 | head -5 || true")
run(c, "export PYTHONPATH=/opt/fincadiag; python3 -B -m fincadiag.gateway.runtime --drain-only 2>&1 | grep -i 'publisher\|drained\|path' || true")

print("=== Verificar si hay otro fincadiag en algun lado ===")
run(c, "find / -path '*/fincadiag/__init__.py' 2>/dev/null")
run(c, "python3 -c 'import fincadiag; print(fincadiag.__file__)' 2>/dev/null || echo 'fail'")
run(c, "export PYTHONPATH=/opt/fincadiag; python3 -c 'import fincadiag; print(fincadiag.__file__)'")

c.close()
print("=== Terminado ===")
