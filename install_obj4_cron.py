# -*- coding: utf-8 -*-
"""Sube obj4_resilience_staged.py a la Pi e instala cron con 10 entradas:
  - 9 ventanas --all en caliente (~25 min dentro de cada bloque de captura)
  - 1 soak a las 08:00 diario (monitoreo 2h de memoria/CPU bajo carga real)
Preserva FincaScheduler. Idempotente."""
import io
import os
import paramiko
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SCRIPT_LOCAL = BASE_DIR / "Gateway" / "tests" / "obj4_resilience_staged.py"
SCRIPT_REMOTE = "/home/esmeralda/obj4_resilience_staged.py"
PI_HOST = os.environ["PI_HOST"]
PI_PORT = int(os.environ.get("PI_PORT", "22"))
PI_USER = os.environ.get("PI_USER", "esmeralda")

CMD_ALL  = ("/usr/bin/python3 /home/esmeralda/obj4_resilience_staged.py --all --cycles 7 "
            ">> /home/esmeralda/resultados_obj4/cron_obj4.log 2>&1")
CMD_SOAK = ("/usr/bin/python3 /home/esmeralda/obj4_resilience_staged.py --scenario soak "
            "--soak-minutes 60 "
            ">> /home/esmeralda/resultados_obj4/cron_obj4_soak.log 2>&1")

# 9 ventanas --all (7 ciclos c/u) + 2 soaks de 60 min
ALL_WINDOWS = [
    (50, 2),   # ORDEÑO AM  (02:25)
    (0,  5),   # NORMAL 1   (04:34)
    (50, 7),   # NORMAL 2   (07:23)
    (38, 10),  # NORMAL 3   (10:12)
    (28, 13),  # ORDEÑO PM  (13:02)
    (36, 15),  # NORMAL 4   (15:10)
    (14, 18),  # NORMAL 5   (17:48)
    (3,  21),  # NORMAL 6   (20:37)
    (52, 23),  # NORMAL 7   (23:26)
]
CRON_LINES = [f"{m} {h} * * * {CMD_ALL}" for (m, h) in ALL_WINDOWS]
CRON_LINES.append(f"15 8 * * * {CMD_SOAK}")   # soak 1: 08:15-09:15 (tras --all 07:50 ~25min)
CRON_LINES.append(f"5 16 * * * {CMD_SOAK}")   # soak 2: 16:05-17:05 (tras --all 15:36 ~25min)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(PI_HOST, port=PI_PORT,
          username=PI_USER, password=os.environ["PI_PASSWORD"], timeout=30)


def run(cmd, timeout=30):
    _, out, err = c.exec_command(cmd, timeout=timeout)
    return out.read().decode(errors="replace").strip(), err.read().decode(errors="replace").strip()


# 1. Subir script actualizado (con soak)
print("===== SUBIENDO script actualizado a la Pi =====")
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(SCRIPT_LOCAL.read_bytes()), SCRIPT_REMOTE)
sftp.close()
print(f"  Script subido: {SCRIPT_REMOTE}")

# 2. Dry-run para confirmar que el script se ejecuta bien
print("\n===== DRY RUN de verificacion =====")
o, e = run("sudo python3 /home/esmeralda/obj4_resilience_staged.py --dry-run 2>&1", timeout=30)
print(o or e)

# 3. Instalar crontab (idempotente: quita lineas obj4 viejas, inserta las 10 nuevas)
print("\n===== INSTALANDO crontab (10 entradas) =====")
add_cmds = ";".join([f"echo '{ln}' >> /tmp/root_cron_new" for ln in CRON_LINES])
install_script = (
    "sudo crontab -l 2>/dev/null | grep -v 'obj4_resilience_staged' > /tmp/root_cron_new; "
    f"{add_cmds}; "
    "sudo crontab /tmp/root_cron_new; "
    "rm -f /tmp/root_cron_new"
)
o, e = run(install_script, timeout=30)
if e:
    print("[stderr]", e)

print("\n===== CRONTAB FINAL (lineas obj4) =====")
o, _ = run("sudo crontab -l 2>/dev/null | grep -E 'obj4_resilience|FincaScheduler'")
print(o or "(vacio)")

c.close()
print("\n[FIN] Script subido + cron 10 entradas instalado (9x --all en caliente + soak 08:00).")
print(f"Soak guarda en: /home/esmeralda/resultados_obj4/obj4_soak_results_YYYYMMDD.csv")
