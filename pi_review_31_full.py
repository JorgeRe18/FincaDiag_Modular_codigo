# -*- coding: utf-8 -*-
"""Revisión exhaustiva de archivos del 31 de mayo en la Raspberry Pi."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

cmds = [
    ("find /home/esmeralda -maxdepth 3 -type f -newermt '2026-05-31' ! -newermt '2026-06-01' | sort", "Archivos del 31 en /home/esmeralda"),
    ("ls -laR /home/esmeralda/obj4_runs/ 2>/dev/null || echo 'no existe'", "Contenido obj4_runs"),
    ("find /tmp -maxdepth 2 -type f -newermt '2026-05-31' ! -newermt '2026-06-01' | sort", "Archivos del 31 en /tmp"),
    ("find /var/lib/fincadiag -maxdepth 3 -type f -newermt '2026-05-31' ! -newermt '2026-06-01' | sort", "Archivos del 31 en /var/lib/fincadiag"),
    ("find /home/esmeralda -maxdepth 2 \( -name '*.csv' -o -name '*.log' -o -name '*.jsonl' \) | xargs ls -lt 2>/dev/null | head -20", "Archivos recientes csv/log/jsonl"),
    ("cat /home/esmeralda/obj4_resilience_results.csv 2>/dev/null", "Resultados resiliencia (completo)"),
    ("wc -l /home/esmeralda/obj4_resilience.log 2>/dev/null", "Lineas totales del log resiliencia"),
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
print("\n=== Revisión exhaustiva completada ===")
