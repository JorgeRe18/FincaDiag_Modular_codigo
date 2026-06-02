"""Paso 2c: descubrir donde esta instalado fincadiag."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

def run(client, cmd, sudo=False, timeout=120):
    if sudo:
        cmd = f"echo {PASSWORD} | sudo -S bash -c \"{cmd}\""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print(f"$ {cmd[:80]}")
    if out.strip(): print(out)
    if err.strip() and "password for" not in err.lower(): print("[err]", err)
    print()
    return out

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

# 1. ls /opt
run(c, "ls -la /opt 2>&1")

# 2. find runtime.py
run(c, "find / -name 'runtime.py' -path '*gateway*' 2>/dev/null | head -10")

# 3. find fincadiag package
run(c, "find / -name 'fincadiag' -type d 2>/dev/null | head -10")

# 4. pip show fincadiag (puede que este en venv)
run(c, "python3 -m pip show fincadiag 2>&1 | head -10")

# 5. busqueda alterna
run(c, "find /home/esmeralda -maxdepth 4 -name '__init__.py' -path '*fincadiag*' 2>/dev/null | head -5")
run(c, "find /home/esmeralda -maxdepth 4 -name '*.py' -path '*gateway*runtime*' 2>/dev/null | head -5")

# 6. revisar scripts existentes que ya usan el gateway
run(c, "cat /home/esmeralda/export_visita_pi.sh 2>&1 | head -30")
run(c, "ls /home/esmeralda/*.py 2>&1 | head -30")
run(c, "head -30 /home/esmeralda/FincaScheduler.py 2>&1")

c.close()
