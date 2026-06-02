"""
Paso 2: Instalar at + bc, validar entorno del gateway, programar pruebas Obj 4.
"""
import paramiko
import os
import time

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ.get("PI_PASSWORD")
if not PASSWORD:
    raise SystemExit("Set env var PI_PASSWORD")


def run(client, cmd, sudo=False, show=True, timeout=120):
    if sudo:
        cmd = f"echo {PASSWORD} | sudo -S bash -c '{cmd}'"
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show:
        if out.strip():
            print(out)
        if err.strip() and "password for esmeralda" not in err.lower():
            print("[stderr]", err)
    return out, err


print("=== Conectando ===")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("\n=== [1/6] Validando entorno del gateway ===")
checks = [
    ("PYTHONPATH /opt/fincadiag", "ls /opt/fincadiag/src/fincadiag/gateway/runtime.py 2>&1"),
    ("certs",                     "ls -la /etc/fincadiag/certs/ 2>&1"),
    ("processed visits",           "ls /var/lib/fincadiag/processed/visits/ | head -5"),
    ("spool dir",                  "ls -ld /var/lib/fincadiag/spool /var/lib/fincadiag/published 2>&1"),
    ("sesion target del soak",     "ls /var/lib/fincadiag/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005/correlation_summary.json 2>&1"),
]
for name, cmd in checks:
    print(f"--- {name} ---")
    run(client, cmd)

print("\n=== [2/6] Instalando at + bc ===")
run(client, "apt-get install -y at bc", sudo=True, timeout=180)

print("\n=== [3/6] Habilitando servicio atd ===")
run(client, "systemctl enable --now atd && systemctl is-active atd", sudo=True)

print("\n=== [4/6] Verificando atq antes de programar (debe estar vacio o solo con jobs viejos) ===")
run(client, "atq")

print("\n=== [5/6] Programando jobs Obj 4 (today) ===")
run(client, "bash /home/esmeralda/schedule_obj4_pi.sh today")

print("\n=== [6/6] Estado final de jobs ===")
run(client, "atq")

print("\n=== Detalle de cada job ===")
out, _ = run(client, "atq | awk '{print $1}'", show=False)
job_ids = [j.strip() for j in out.strip().split("\n") if j.strip()]
for j in job_ids:
    print(f"\n--- Job {j} ---")
    run(client, f"at -c {j} | tail -5")

client.close()
print("\nPaso 2 completado.")
