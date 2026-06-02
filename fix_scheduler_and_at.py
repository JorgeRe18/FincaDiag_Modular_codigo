"""Buscar FincaScheduler real, copiarlo, y reprogramar job AM."""
import paramiko

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = "fincaPPA26"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

# 1. Buscar FincaScheduler
stdin, stdout, stderr = c.exec_command("find / -name FincaScheduler.py 2>/dev/null | head -5")
out = stdout.read().decode()
err = stderr.read().decode()
print("=== FincaScheduler locations ===")
print(out)
if err.strip():
    print("[err]", err[:200])

# 2. Copiar a path correcto si existe en /opt
stdin, stdout, stderr = c.exec_command("ls -la /opt/fincadiag/src/fincadiag/ 2>/dev/null || echo NOT_FOUND")
ls_out = stdout.read().decode()
print("\n=== /opt/fincadiag/src/fincadiag/ ===")
print(ls_out)

# 3. Si no existe el dir, buscar donde esta instalado
if "NOT_FOUND" in ls_out:
    stdin, stdout, stderr = c.exec_command("find /opt -name FincaScheduler.py 2>/dev/null")
    opt_out = stdout.read().decode()
    print("=== find /opt ===")
    print(opt_out if opt_out.strip() else "No encontrado en /opt")

# 4. Reprogramar broker AM para 03:15
print("\n=== Reprogramando broker AM 03:15 ===")
cmd_at = 'echo "export PATH=/usr/local/bin:/usr/bin:/bin; bash /home/esmeralda/inject_fault_live_pi.sh --broker 90" | at 03:15 today'
stdin, stdout, stderr = c.exec_command(cmd_at)
at_out = stdout.read().decode()
at_err = stderr.read().decode()
print(at_out)
if at_err.strip():
    print("[err]", at_err)

# 5. Verificar jobs
stdin, stdout, stderr = c.exec_command("atq")
print("\n=== atq ===")
print(stdout.read().decode())

c.close()
print("\nDone.")
