# -*- coding: utf-8 -*-
"""Revisión completa de resultados en la Raspberry Pi."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

cmds = [
    # Estado general
    ("date", "Fecha actual"),
    ("uptime", "Uptime"),
    ("free -h", "Memoria"),
    ("systemctl is-active fincadiag-gateway mosquitto", "Servicios activos"),
    # Capturas de hoy
    ("ls -la /home/esmeralda/FincaLogs/ 2>/dev/null | tail -10", "Directorio FincaLogs"),
    ("ls -la /home/esmeralda/FincaLogs/ | grep '20260531'", "Capturas del 31 mayo"),
    # Estado del scheduler
    ("cat /home/esmeralda/FincaLogs/fincadiag_scheduler_state.json 2>/dev/null", "Estado scheduler"),
    # Experimentos de resiliencia
    ("cat /home/esmeralda/obj4_resilience_results.csv 2>/dev/null", "Resultados resiliencia"),
    ("cat /home/esmeralda/obj4_resilience.log 2>/dev/null | tail -30", "Log resiliencia"),
    # Publicaciones
    ("ls -la /var/lib/fincadiag/published/ 2>/dev/null", "Archivos publicados"),
    ("ls -la /var/lib/fincadiag/spool/ 2>/dev/null", "Cola de spool"),
    # Jobs programados
    ("atq | sort -k2,5", "Jobs at programados"),
    # Logs del gateway
    ("journalctl -u fincadiag-gateway --no-pager -n 15 2>/dev/null", "Logs gateway (últimas 15)"),
    # Inyecciones de fallo
    ("cat /home/esmeralda/fault_injections.csv 2>/dev/null", "Inyecciones de fallo (live)"),
]

for cmd, title in cmds:
    stdin, stdout, stderr = c.exec_command(cmd, timeout=60)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"  $ {cmd}")
    print("="*60)
    if out.strip():
        print(out.strip())
    if err.strip() and err.strip() not in out:
        print("[err]", err.strip())
    if not out.strip() and not err.strip():
        print("(vacío)")

c.close()
print("\n=== Revisión completada ===")
