"""Validacion rapida: correr 3 ciclos MTTR + 2 ciclos latency con scripts aislados."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]


def run(client, cmd, sudo=False, timeout=300):
    if sudo:
        cmd = f"echo {PASSWORD} | sudo -S bash -c \"{cmd}\""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print(f"\n$ {cmd[:130]}")
    if out.strip(): print(out)
    if err.strip() and "password for" not in err.lower(): print("[err]", err)
    return out


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=120)

print("=" * 70); print(" Validacion: MTTR 3 ciclos (aislamiento /tmp)"); print("=" * 70)
run(c, "bash /home/esmeralda/mttr_stress_pi.sh 3 2>&1 | tail -50")

print("\n" + "=" * 70); print(" CSV MTTR (debe tener 4 lineas: header + 3)"); print("=" * 70)
run(c, "wc -l /home/esmeralda/mttr_results.csv; cat /home/esmeralda/mttr_results.csv")

print("\n" + "=" * 70); print(" Validacion: Soak corto (2 min = 0.0333h)"); print("=" * 70)
run(c, "bash /home/esmeralda/soak_test_pi.sh 0.04 30 2>&1 | tail -30", timeout=600)

print("\n" + "=" * 70); print(" CSV Soak (debe tener filas)"); print("=" * 70)
run(c, "wc -l /home/esmeralda/soak_results.csv; cat /home/esmeralda/soak_results.csv")

print("\n" + "=" * 70); print(" Verificar published producido por el daemon (sigue intacto)"); print("=" * 70)
run(c, "ls -la /var/lib/fincadiag/published/")

print("\n" + "=" * 70); print(" Estado del daemon"); print("=" * 70)
run(c, "systemctl is-active fincadiag-gateway; ps -p 1582 -o pid,etime,cmd | head -2")

c.close()
