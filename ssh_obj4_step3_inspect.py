"""Paso 3 inspect: bajar FincaScheduler.py para entender como suspender normales."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

sftp = c.open_sftp()
local = r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\FincaScheduler_pi.py"
sftp.get("/home/esmeralda/FincaScheduler.py", local)
print(f"Bajado a: {local}")
sftp.close()
c.close()

# Mostrar estructura
print("\n=== Tamano y resumen ===")
size = os.path.getsize(local)
print(f"  bytes: {size}")
with open(local, encoding="utf-8") as f:
    lines = f.readlines()
print(f"  lineas: {len(lines)}")
print("\n=== Primeras 80 lineas ===")
for i, l in enumerate(lines[:80], 1):
    print(f"{i:4d}: {l}", end="")
