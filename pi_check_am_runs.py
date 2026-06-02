# -*- coding: utf-8 -*-
"""Revisar corridas AM, ventanas de ordeno e inyecciones de fallo en la Pi."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

cmds = [
    "cat /home/esmeralda/fault_injections.csv 2>/dev/null",
    "cat /home/esmeralda/FincaLogs/fincadiag_scheduler_state.json",
    "grep -iE 'ventana|window|ordeno|milk|captura|sesion' /home/esmeralda/FincaLogs/fincadiag_scheduler_events.log 2>/dev/null | tail -20",
    "ls -la /var/lib/fincadiag/published/",
    "crontab -l 2>/dev/null | grep -v '^#'",
]

for cmd in cmds:
    stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print("$ " + cmd)
    if out.strip():
        print(out)
    if err.strip():
        print("[err]", err)
    print()

c.close()
