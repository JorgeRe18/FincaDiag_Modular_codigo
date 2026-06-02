"""Verificar estructura de FincaScheduler en la Pi."""
import paramiko

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = "fincaPPA26"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

# Buscar milking block con varios patrones
print("=== milking block search ===")
for pattern in ["MILK", "milking", "ORDE", "CAPTURA", "BLOQUE", "schedule", "block"]:
    stdin, stdout, stderr = c.exec_command(f"grep -ic '{pattern}' /home/esmeralda/FincaScheduler.py")
    print(f"  {pattern}: {stdout.read().decode().strip()}")

# Ver estructura de funciones
print("\n=== Funciones ===")
stdin, stdout, stderr = c.exec_command("grep -n 'def ' /home/esmeralda/FincaScheduler.py")
out = stdout.read().decode()
for line in out.splitlines()[:15]:
    print(f"  {line}")

# Verificar si existe algun tipo de configuracion de horarios
print("\n=== Horarios/bloques ===")
stdin, stdout, stderr = c.exec_command("grep -n '0[0-9]:' /home/esmeralda/FincaScheduler.py | head -10")
out = stdout.read().decode().strip()
if out:
    print(out)
else:
    print("  No se encontraron patrones de hora simples")

c.close()
print("\nDone.")
