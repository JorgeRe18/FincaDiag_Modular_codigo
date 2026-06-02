# -*- coding: utf-8 -*-
"""Inspeccionar el flujo: scheduler activo, script de inyeccion, watch-dir del gateway."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

cmds = [
    # Que scheduler esta corriendo (lineas de BLOQUES activas)
    "grep -nE 'SUSPENDIDO|inicio.*ordeño|inicio.*normal' /home/esmeralda/FincaScheduler.py | head -20",
    # El watch-dir del gateway: que hay en processed
    "ls -la /var/lib/fincadiag/processed/ 2>/dev/null | tail -15",
    # El script de inyeccion que usan los at jobs
    "ls -la /home/esmeralda/inject_fault_live_pi*.sh /home/esmeralda/measure_live_resilience*.sh 2>/dev/null",
    # Logs del gateway: como publica (ultimas lineas)
    "journalctl -u fincadiag-gateway --no-pager -n 25 2>/dev/null",
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
