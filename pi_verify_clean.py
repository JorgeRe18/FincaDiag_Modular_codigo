# -*- coding: utf-8 -*-
"""Verificar estado limpio de la Pi tras el experimento de resiliencia."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

cmds = [
    "systemctl is-active fincadiag-gateway mosquitto",
    "sudo iptables -S | grep 8883 || echo 'iptables 8883: limpio'",
    "sudo ip6tables -S | grep 8883 || echo 'ip6tables 8883: limpio'",
    "ls -d /var/lib/fincadiag/processed/RESIL_* 2>/dev/null || echo 'processed RESIL_: limpio'",
    "ls /var/lib/fincadiag/spool/ 2>/dev/null | wc -l",
    "ls /var/lib/fincadiag/published/RESIL_* 2>/dev/null | wc -l",
]

for cmd in cmds:
    stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print("$ " + cmd)
    if out.strip():
        print(out.strip())
    if err.strip():
        print("[err]", err.strip())
    print("-" * 55)

c.close()
