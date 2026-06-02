"""Restaurar FincaScheduler normal + preparar inyeccion en caliente (v2).

Acciones:
  1. Cancelar todo job 'at' residual.
  2. Restaurar FincaScheduler.py desde backup (.bak_obj4_28may).
  3. Recrear crontab con horarios de captura AM/PM.
  4. Subir scripts inject_fault_live_pi_v2.sh y measure_live_resilience_pi_v2.sh.
  5. Verificar daemon activo y estado del servicio.
  6. Lanzar FincaScheduler manualmente para verificar.
"""
import os
import paramiko

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = "fincaPPA26"

LOCAL_SCRIPTS = [
    r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests\inject_fault_live_pi_v2.sh",
    r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests\measure_live_resilience_pi_v2.sh",
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
    print("  [ERROR] Backup no existe. Abortando.")
    c.close()
    raise SystemExit(1)

run(c, f"cp {FISCHED_BAK} {FISCHED_DEST}")
run(c, f"cp {FISCHED_DEST} {FISCHED_SYSTEM}", sudo=True)
run(c, f"chown esmeralda:esmeralda {FISCHED_SYSTEM}", sudo=True)
print("  FincaScheduler.py restaurado a v3.0 normal.")

print("=== 3. Recrear crontab con capturas AM/PM ===")
# Crontab: FincaScheduler cada minuto, export_visita a las 23:30
CRON_LINES = """* * * * * /usr/bin/python3 /home/esmeralda/FincaScheduler.py >> /home/esmeralda/fincadiag_scheduler.log 2>&1
30 23 * * * /home/esmeralda/export_visita_pi.sh "$(date -d 'yesterday' +\\\"Visita_%d_%m_%Y\\\")" >> /home/esmeralda/exports/cron.log 2>&1
"""
run(c, f"echo '{CRON_LINES}' | crontab -")
run(c, "crontab -l")

print("=== 4. Subir scripts de inyeccion (v2) ===")
sftp = c.open_sftp()
for local, remote in zip(LOCAL_SCRIPTS, REMOTE_SCRIPTS):
    sftp.put(local, remote)
    print(f"  Subido: {remote}")
    run(c, f"chmod +x {remote}", show=False)
sftp.close()

print("=== 5. Verificar daemon y servicio ===")
run(c, "systemctl is-active fincadiag-gateway")
run(c, "systemctl is-active mosquitto")
run(c, "systemctl restart fincadiag-gateway", sudo=True)
run(c, "sleep 3 && systemctl is-active fincadiag-gateway")

print("=== 6. Probar scripts ===")
run(c, "/home/esmeralda/inject_fault_live_pi.sh --dry-run")
run(c, "/home/esmeralda/measure_live_resilience_pi.sh 2 30")

print("=== 7. Programar inyecciones en caliente via 'at' (duracion 90s) ===")
# AM: broker 90s a las 02:45
run(c, 'echo "export PATH=/usr/local/bin:/usr/bin:/bin; bash /home/esmeralda/inject_fault_live_pi.sh --broker 90" | at 02:45 today')
# PM: network 90s a las 13:15
run(c, 'echo "export PATH=/usr/local/bin:/usr/bin:/bin; bash /home/esmeralda/inject_fault_live_pi.sh --network 90" | at 13:15 today')
# PM: kill 90s a las 13:35
run(c, 'echo "export PATH=/usr/local/bin:/usr/bin:/bin; bash /home/esmeralda/inject_fault_live_pi.sh --kill 90" | at 13:35 today')
# Medicion post-AM a las 04:00
run(c, 'echo "export PATH=/usr/local/bin:/usr/bin:/bin; bash /home/esmeralda/measure_live_resilience_pi.sh 2 30" | at 04:00 today')
# Medicion post-PM a las 14:30
run(c, 'echo "export PATH=/usr/local/bin:/usr/bin:/bin; bash /home/esmeralda/measure_live_resilience_pi.sh 2 30" | at 14:30 today')

print("=== 8. Verificar jobs programados ===")
run(c, "atq")

c.close()
print("=" * 60)
print(" PREPARACION COMPLETADA - INYECCIONES PROGRAMADAS")
print("=" * 60)
print("""
FincaScheduler restaurado -> capturas normales activas.
Crontab recreado con ejecucion cada minuto.
Scripts de inyeccion subidos (v3-hot, defaults 90s).

INYECCIONES AUTOMATICAS PROGRAMADAS para hoy 31/05:
  02:45  -> inject_fault_live_pi.sh --broker 90   (AM en caliente)
  13:15  -> inject_fault_live_pi.sh --network 90   (PM en caliente)
  13:35  -> inject_fault_live_pi.sh --kill 90      (PM en caliente)

MEDICIONES AUTOMATICAS PROGRAMADAS:
  04:00  -> measure_live_resilience_pi.sh 2 30     (post-AM)
  14:30  -> measure_live_resilience_pi.sh 2 30     (post-PM)

Los defaults ahora son 90s para SUPERAR el backoff de 62s
y forzar spooling real durante los ordeños.

Verificar manana:
  - atq (jobs deberian estar vacios = ejecutados)
  - cat /home/esmeralda/fault_injections.csv
  - cat /home/esmeralda/live_resilience_results.csv
  - ls /var/lib/fincadiag/raw/ (capturas AM/PM)
  - ls /var/lib/fincadiag/published/ (publicaciones)
  - ls /var/lib/fincadiag/spool/ (spool residual si hubo)
""")
