"""Restaurar FincaScheduler normal + preparar inyeccion en caliente Dia 3 (30/05).

Ejecutar ESTA NOCHE (29/05 ~23:30) despues de que termine el bundle del Dia 2,
o temprano el 30/05 antes del ordeño AM (04:35).

Acciones:
  1. Cancelar todo job 'at' residual.
  2. Restaurar FincaScheduler.py desde backup (.bak_obj4_28may).
  3. Subir scripts inject_fault_live_pi.sh y measure_live_resilience_pi.sh.
  4. Verificar daemon activo y estado del servicio.
"""
import os
import paramiko

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

LOCAL_SCRIPTS = [
    r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests\inject_fault_live_pi.sh",
    r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests\measure_live_resilience_pi.sh",
]
REMOTE_SCRIPTS = [
    "/home/esmeralda/inject_fault_live_pi.sh",
    "/home/esmeralda/measure_live_resilience_pi.sh",
]
FISCHED_BAK = "/home/esmeralda/FincaScheduler.py.bak_obj4_28may"
FISCHED_DEST = "/home/esmeralda/FincaScheduler.py"
FISCHED_SYSTEM = "/opt/fincadiag/src/fincadiag/FincaScheduler.py"


def run(client, cmd, sudo=False, timeout=60, show=True):
    if sudo:
        cmd = f'echo {PASSWORD} | sudo -S bash -c "{cmd}"'
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show:
        print(f"$ {cmd[:120]}")
        if out.strip():
            print(out)
        if err.strip() and "password for" not in err.lower():
            print("[err]", err)
        print()
    return out, err


print("=== Conectando ===")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("=== 1. Cancelar jobs 'at' pendientes ===")
run(c, "for j in $(atq | awk '{print $1}'); do atrm $j; done")

print("=== 2. Restaurar FincaScheduler.py ===")
out, err = run(c, f"ls -la {FISCHED_BAK}", show=False)
if "No such file" in (err + out):
    print("  [WARN] Backup no existe en ~, intentando copia del repo (necesita permisos)")
else:
    run(c, f"cp {FISCHED_BAK} {FISCHED_DEST}")
    run(c, f"echo {PASSWORD} | sudo -S cp {FISCHED_DEST} {FISCHED_SYSTEM}", show=False)
    run(c, f"echo {PASSWORD} | sudo -S chown esmeralda:esmeralda {FISCHED_SYSTEM}", show=False)
    print("  FincaScheduler.py restaurado.")

print("=== 3. Subir scripts de inyeccion ===")
sftp = c.open_sftp()
for local, remote in zip(LOCAL_SCRIPTS, REMOTE_SCRIPTS):
    sftp.put(local, remote)
    print(f"  Subido: {remote}")
    run(c, f"chmod +x {remote}", show=False)
sftp.close()

print("=== 4. Verificar daemon y servicio ===")
run(c, "systemctl is-active fincadiag-gateway")
run(c, "systemctl is-active mosquitto")

print("=== 5. Verificar crontab (capturas normales) ===")
run(c, "crontab -l | grep FincaScheduler")

c.close()
print("=" * 60)
print(" DIA 3 PREPARADO")
print("=" * 60)
print("""
FincaScheduler restaurado -> capturas normales activas.
Scripts de inyeccion subidos:
  /home/esmeralda/inject_fault_live_pi.sh
  /home/esmeralda/measure_live_resilience_pi.sh

Instrucciones Dia 30/05:
  1. Durante ORDEÑO_AM (~04:50, min 15 del ordeño):
     ssh ... "bash /home/esmeralda/inject_fault_live_pi.sh --broker 5"

  2. Durante ORDEÑO_PM (~13:12, min 10 del ordeño):
     ssh ... "bash /home/esmeralda/inject_fault_live_pi.sh --network 30"

  3. Durante ORDEÑO_PM (~13:27, min 25 del ordeño):
     ssh ... "bash /home/esmeralda/inject_fault_live_pi.sh --kill 60"

  4. Despues de cada sesion:
     ssh ... "bash /home/esmeralda/measure_live_resilience_pi.sh"

  5. Bajar resultados al final del dia:
     scp -P 33000 esmeralda@...:/home/esmeralda/fault_injections.csv .
     scp -P 33000 esmeralda@...:/home/esmeralda/live_resilience_results.csv .
""")
