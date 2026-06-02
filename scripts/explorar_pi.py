"""Explorar estado actual de la Pi para saber como correr motor de correlacion."""
import paramiko

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PW = __import__('os').environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PW, timeout=60, banner_timeout=60, auth_timeout=60)

def run(cmd):
    _, out, err = c.exec_command(cmd)
    return out.read().decode(errors='replace'), err.read().decode(errors='replace')

print("=== 1. Estructura /opt/fincadiag ===")
o, _ = run("ls -la /opt/fincadiag/fincadiag/")
print(o)

print("\n=== 2. Buscar motor de correlacion ===")
o, _ = run("find /opt/fincadiag -name '*.py' | grep -iE 'corr|match|serial' | head -20")
print(o)

print("\n=== 3. Visitas 21-27 existentes ===")
o, _ = run("ls /var/lib/fincadiag/processed/visits/ | grep 'Visita_2' | sort")
print(o)

print("\n=== 4. Sesiones dentro de Visita_21 ===")
o, _ = run("ls /var/lib/fincadiag/processed/visits/Visita_21_05_2026/sesiones/ 2>/dev/null")
print(o)

print("\n=== 5. Que archivos hay en una sesion de Visita_21 ===")
o, _ = run("ls /var/lib/fincadiag/processed/visits/Visita_21_05_2026/sesiones/TOMA_PM__1PM__Captura_20260521_130005/ 2>/dev/null | head -20")
print(o)

print("\n=== 6. correlation_summary existentes en Pi ===")
o, _ = run("find /var/lib/fincadiag/processed/visits -name 'correlation_summary.json' | grep Visita | sort")
print(o)

print("\n=== 7. Verificar si hay un script main.py o similar ===")
o, _ = run("ls /opt/fincadiag/")
print(o)

print("\n=== 8. Revisar si existe un runbook o script de procesamiento ===")
o, _ = run("ls /opt/fincadiag/scripts/ 2>/dev/null || echo 'no scripts dir'")
print(o)

c.close()
