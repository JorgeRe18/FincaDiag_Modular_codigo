# -*- coding: utf-8 -*-
import paramiko, os

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("gateway-esmeralda-ssh.at.remote.it", port=33000,
          username="esmeralda", password=os.environ["PI_PASSWORD"], timeout=30)

cmds = [
    ("date", "Fecha/hora actual"),
    ("systemctl is-active fincadiag-gateway mosquitto", "Servicios"),
    ("cat /home/esmeralda/FincaLogs/fincadiag_scheduler_state.json", "Estado scheduler"),
    ("ls /home/esmeralda/FincaLogs/ | grep 20260601 || echo 'sin capturas del 1 junio aun'", "Capturas del 1 junio"),
    ("ls -la /home/esmeralda/obj4_resilience_staged.py", "Script resiliencia (fecha)"),
    ("head -5 /home/esmeralda/obj4_resilience_staged.py | grep -E 'sleep|net_block|clean_stale'", "Confirmar fixes en script"),
    ("grep -n 'sleep(1)\\|clean_stale\\|net_unblock' /home/esmeralda/obj4_resilience_staged.py | head -10", "Verificar lineas clave"),
]

for cmd, title in cmds:
    _, out, _ = c.exec_command(cmd, timeout=15)
    result = out.read().decode(errors="replace").strip()
    print(f"\n=== {title} ===")
    print(result if result else "(vacío)")

c.close()
