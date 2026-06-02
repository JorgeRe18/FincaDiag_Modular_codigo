"""
Paso 1: Subir 5 scripts a la Pi y leer el crontab actual (sin modificar nada).
"""
import paramiko
import os
from pathlib import Path

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ.get("PI_PASSWORD")
if not PASSWORD:
    raise SystemExit("Set env var PI_PASSWORD before running.")

LOCAL = Path(r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests")
FILES = [
    "mttr_stress_pi.sh",
    "latency_e2e_pi.sh",
    "soak_test_pi.sh",
    "schedule_obj4_pi.sh",
    "suspend_intermediate_captures_pi.sh",
]

print(f"=== Conectando a {USER}@{HOST}:{PORT} ===")
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("=== Subiendo archivos ===")
sftp = client.open_sftp()
for f in FILES:
    src = LOCAL / f
    dst = f"/home/esmeralda/{f}"
    sftp.put(str(src), dst)
    print(f"  OK: {f}")
sftp.close()

print("\n=== chmod +x ===")
stdin, stdout, stderr = client.exec_command("chmod +x /home/esmeralda/*.sh && ls -lh /home/esmeralda/*.sh")
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)

print("\n=== Crontab actual (usuario esmeralda) ===")
stdin, stdout, stderr = client.exec_command("crontab -l 2>&1")
print(stdout.read().decode())

print("\n=== Crontab root (sudo) ===")
stdin, stdout, stderr = client.exec_command(f"echo {PASSWORD} | sudo -S crontab -l 2>&1")
print(stdout.read().decode())

print("\n=== Hora actual de la Pi ===")
stdin, stdout, stderr = client.exec_command("date && timedatectl | head -5")
print(stdout.read().decode())

print("\n=== Verificar 'at', mosquitto-clients, bc ===")
stdin, stdout, stderr = client.exec_command("which at mosquitto_pub mosquitto_sub bc 2>&1; echo '---'; systemctl is-active atd 2>&1 || true")
print(stdout.read().decode())

client.close()
print("\nPaso 1 completado.")
