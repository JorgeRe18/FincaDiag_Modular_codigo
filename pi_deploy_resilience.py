# -*- coding: utf-8 -*-
"""Subir obj4_resilience_staged.py a la Pi y ejecutarlo."""
import paramiko, os, sys

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

LOCAL = r"Gateway\tests\obj4_resilience_staged.py"
REMOTE = "/home/esmeralda/obj4_resilience_staged.py"

mode = sys.argv[1] if len(sys.argv) > 1 else "--dry-run"  # --dry-run | --all | --scenario broker

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

# Subir
sftp = c.open_sftp()
sftp.put(LOCAL, REMOTE)
sftp.close()
print(f"Subido {REMOTE}")

# Ejecutar (sudo necesario para systemctl/iptables)
if mode == "--dry-run":
    cmd = f"python3 {REMOTE} --dry-run"
else:
    cmd = f"sudo python3 {REMOTE} {mode}"

print(f"$ {cmd}\n")
stdin, stdout, stderr = c.exec_command(cmd, timeout=900, get_pty=True)
for line in iter(stdout.readline, ""):
    print(line, end="")
err = stderr.read().decode(errors="replace")
if err.strip():
    print("[err]", err)

# Mostrar resultados
print("\n=== obj4_resilience_results.csv ===")
_, o, _ = c.exec_command("cat /home/esmeralda/obj4_resilience_results.csv 2>/dev/null")
print(o.read().decode(errors="replace"))

c.close()
