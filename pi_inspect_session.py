# -*- coding: utf-8 -*-
"""Inspeccionar estructura de una sesion procesada y config del gateway service."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

cmds = [
    "ls -la /var/lib/fincadiag/processed/TOMA_PM__1PM__Captura_20260511_130005/",
    "wc -l /var/lib/fincadiag/processed/TOMA_PM__1PM__Captura_20260511_130005/cow_events.csv 2>/dev/null",
    "cat /var/lib/fincadiag/published/TOMA_PM__1PM__Captura_20260511_130005.jsonl | grep -c cow_event",
    "cat /etc/systemd/system/fincadiag-gateway.service 2>/dev/null || systemctl cat fincadiag-gateway 2>/dev/null",
    "sudo -n true 2>&1 && echo 'SUDO_NOPASSWD_OK' || echo 'SUDO_NEEDS_PASSWORD'",
    "ls /var/lib/fincadiag/processed/visits/ 2>/dev/null | head",
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
    print("-" * 70)

c.close()
