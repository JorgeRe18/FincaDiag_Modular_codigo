# -*- coding: utf-8 -*-
"""Corre obj4_resilience_staged.py --all en la Pi (bloqueante, ~7 min) y muestra CSV de hoy."""
import os
import paramiko

PI_HOST = os.environ["PI_HOST"]
PI_PORT = int(os.environ.get("PI_PORT", "22"))
PI_USER = os.environ.get("PI_USER", "esmeralda")

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(PI_HOST, port=PI_PORT,
          username=PI_USER, password=os.environ["PI_PASSWORD"], timeout=30)

print("===== EJECUTANDO --all (esto tarda varios minutos) =====")
cmd = "sudo python3 /home/esmeralda/obj4_resilience_staged.py --all 2>&1"
chan = c.get_transport().open_session()
chan.settimeout(600)
chan.exec_command(cmd)
buf = b""
while True:
    if chan.recv_ready():
        buf += chan.recv(4096)
    if chan.exit_status_ready() and not chan.recv_ready():
        break
# drenar lo que quede
while chan.recv_ready():
    buf += chan.recv(4096)
print(buf.decode(errors="replace").strip())
print(f"\n[exit status = {chan.recv_exit_status()}]")

# Mostrar CSV de hoy
print("\n===== CSV resultado de HOY =====")
_, out, _ = c.exec_command(
    "ls -lh /home/esmeralda/resultados_obj4/obj4_resilience_results_$(date +%Y%m%d).csv 2>&1; "
    "echo '---'; cat /home/esmeralda/resultados_obj4/obj4_resilience_results_$(date +%Y%m%d).csv 2>&1", timeout=30)
print(out.read().decode(errors="replace").strip())

c.close()
print("\n[FIN]")
