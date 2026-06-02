# -*- coding: utf-8 -*-
"""Corre obj4_resilience_staged.py HOY en la Pi: dry-run, y si esta limpio, --all."""
import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("gateway-esmeralda-ssh.at.remote.it", port=33000,
          username="esmeralda", password=os.environ["PI_PASSWORD"], timeout=30)


def run(cmd, timeout):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    o = out.read().decode(errors="replace").strip()
    e = err.read().decode(errors="replace").strip()
    return o, e


# 1. Dry run
print("===== DRY RUN =====")
o, e = run("sudo python3 /home/esmeralda/obj4_resilience_staged.py --dry-run 2>&1", 60)
print(o or e)

# 2. Inspeccion del scheduler para elegir hora de cron sin chocar capturas
print("\n===== Bloques del FincaScheduler (horas de captura) =====")
o, e = run("grep -nE 'HORA|hora|block|bloque|[0-9]{1,2}:[0-9]{2}|schedule|TOMA' /home/esmeralda/FincaScheduler.py 2>&1 | head -40", 30)
print(o or e or "(no se pudo leer)")

c.close()
print("\n[FIN]")
