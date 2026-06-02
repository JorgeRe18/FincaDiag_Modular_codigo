# -*- coding: utf-8 -*-
"""Diagnostico: a que direccion resuelve localhost y donde escucha mosquitto."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

cmds = [
    "getent hosts localhost",
    "ss -tlnp 2>/dev/null | grep 8883 || sudo ss -tlnp | grep 8883",
    "grep -riE 'listener|bind_address' /etc/mosquitto/ 2>/dev/null",
    "python3 -c \"import socket; print(socket.getaddrinfo('localhost',8883,proto=socket.IPPROTO_TCP))\"",
]

for cmd in cmds:
    stdin, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print("$ " + cmd)
    if out.strip():
        print(out)
    if err.strip():
        print("[err]", err)
    print("-" * 60)

c.close()
