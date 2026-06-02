# -*- coding: utf-8 -*-
"""Diagnostico read-only: por que no corrieron las pruebas Obj4 hoy en la Pi."""
import os
import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("gateway-esmeralda-ssh.at.remote.it", port=33000,
          username="esmeralda", password=os.environ["PI_PASSWORD"], timeout=30)

cmds = [
    ("Fecha/hora Pi", "date"),
    ("Cron del usuario esmeralda", "crontab -l 2>&1 || echo '(sin crontab)'"),
    ("Cron root", "sudo crontab -l 2>&1 || echo '(sin crontab root)'"),
    ("At jobs pendientes", "atq 2>&1 || echo '(at no disponible)'"),
    ("Timers systemd (obj4/fincadiag)", "systemctl list-timers --all --no-pager 2>&1 | grep -iE 'obj4|fincadiag|resilien' || echo '(ningun timer obj4)'"),
    ("Procesos obj4 activos", "ps aux | grep -iE 'obj4|resilien|mttr|soak|latency' | grep -v grep || echo '(ningun proceso obj4 corriendo)'"),
    ("Resultados de HOY en obj4_runs", "ls -lh /home/esmeralda/obj4_runs/ 2>&1 | grep \"$(date +%Y-%m-%d)\" || echo '(nada de hoy en obj4_runs)'"),
    ("Resultados de HOY en resultados_obj4", "ls -lh /home/esmeralda/resultados_obj4/ 2>&1 | grep \"$(date +%Y-%m-%d)\" || echo '(nada de hoy en resultados_obj4)'"),
    ("Ultimos CSV modificados", "ls -lht /home/esmeralda/*.csv 2>&1 | head -8"),
    ("Scripts obj4 presentes", "ls -lh /home/esmeralda/*obj4* /home/esmeralda/mttr_stress_pi.sh /home/esmeralda/latency_e2e_pi.sh /home/esmeralda/soak_test_pi.sh 2>&1"),
]

for title, cmd in cmds:
    _, out, err = c.exec_command(cmd, timeout=30)
    output = out.read().decode(errors="replace").strip()
    errtxt = err.read().decode(errors="replace").strip()
    print(f"\n===== {title} =====")
    if output:
        print(output)
    if errtxt and "sudo" not in cmd:
        print(f"[stderr] {errtxt}")

c.close()
print("\n[FIN DIAGNOSTICO]")
