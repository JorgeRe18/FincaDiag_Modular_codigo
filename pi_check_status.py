"""Verificar estado de la Raspberry Pi: jobs, procesos, conectividad."""
import paramiko, os, time

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

def run(client, cmd, timeout=60, show=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show:
        print(f"$ {cmd[:120]}")
        if out.strip():
            print(out)
        if err.strip():
            print("[err]", err)
        print()
    return out, err

print("=== Intentando conectar a Pi ===")
for i in range(5):
    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)
        print(f"Conectado en intento {i+1}")
        break
    except Exception as e:
        print(f"Intento {i+1} fallo: {e}")
        time.sleep(10)
else:
    print("No se pudo conectar despues de 5 intentos")
    exit(1)

print("=== Estado de la Pi ===")
run(c, "date")
run(c, "atq | sort -k2,5")
run(c, "ps aux | grep -E 'mosquitto|fincadiag|python' | grep -v grep")
run(c, "systemctl is-active mosquitto")
run(c, "systemctl is-active fincadiag-gateway")
run(c, "uptime")
run(c, "free -h")

c.close()
print("=== Terminado ===")
