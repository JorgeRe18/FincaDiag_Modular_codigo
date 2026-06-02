# -*- coding: utf-8 -*-
"""Auditoría completa del home de esmeralda en la Raspberry Pi."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

cmds = [
    ("ls -la /home/esmeralda/",                                                         "HOME raíz"),
    ("ls -la /home/esmeralda/obj4_runs/ 2>/dev/null || echo 'no existe'",               "obj4_runs/"),
    ("find /tmp -maxdepth 1 -type f -o -maxdepth 1 -type d | grep -E 'test|resil|pub_|spool|mqtt|RESIL' | sort", "/tmp archivos de prueba"),
    ("ls -la /home/esmeralda/FincaLogs/",                                               "FincaLogs/"),
    ("find /var/lib/fincadiag -type f | sort",                                          "/var/lib/fincadiag archivos"),
    ("find /var/lib/fincadiag/processed -maxdepth 4 -type d | sort",                    "processed dirs"),
    ("find /home/esmeralda -maxdepth 1 -name '*.py' | sort",                            "scripts .py en home"),
    ("find /home/esmeralda -maxdepth 1 -name '*.sh' | sort",                            "scripts .sh en home"),
    ("find /home/esmeralda -maxdepth 1 -name '*.csv' | sort",                           "CSV en home"),
    ("find /home/esmeralda -maxdepth 1 -name '*.log' | sort",                           "logs en home"),
    ("find /home/esmeralda -maxdepth 1 -name '*.json' | sort",                          "JSON en home"),
    ("df -h /home /var",                                                                 "Espacio en disco"),
    ("atq",                                                                              "Jobs at programados"),
]

for cmd, title in cmds:
    _, stdout, stderr = c.exec_command(cmd, timeout=30)
    out = stdout.read().decode(errors="replace").strip()
    print(f"\n{'='*55}")
    print(f"  {title}")
    print("="*55)
    if out:
        print(out)
    else:
        print("(vacío)")

c.close()
print("\n=== Auditoría completada ===")
