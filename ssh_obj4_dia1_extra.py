"""Agregar al Día 1 los 3 jobs adicionales: network failure, power failure, soak extra."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]
DIA_LABEL = "2026-05-28"
OUT_DIR = "/home/esmeralda/obj4_runs"


def run(client, cmd, sudo=False, timeout=120, show=True):
    if sudo:
        cmd = f"echo {PASSWORD} | sudo -S bash -c \"{cmd}\""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show:
        print(f"$ {cmd[:100]}")
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


def schedule_at(hora, label, cmd):
    log = f"{OUT_DIR}/{DIA_LABEL}_{label}.log"
    full = f"echo '{cmd} > {log} 2>&1' | at {hora} today"
    run(c, full)


print("\n=== Programando 3 jobs adicionales ===")
# 06:40 Network failure 30 ciclos (cabe en hueco AM antes de NORMAL 2 a 07:23)
schedule_at("06:40", "extra_network", "bash /home/esmeralda/network_failure_pi.sh 30")

# 10:00 Power failure 10 ciclos (hueco mañana, sin NORMAL 3)
schedule_at("10:00", "extra_power", "bash /home/esmeralda/power_failure_sim_pi.sh 10")

# 10:30 Soak 2h adicional (hueco mañana, hasta 12:30, antes de PM ordeño 13:00)
schedule_at("10:30", "extra_soak2h_am", "bash /home/esmeralda/soak_test_pi.sh 2 60")

print("\n=== Estado completo de jobs ===")
run(c, "atq | sort -k2,5")

c.close()
print("\n" + "=" * 60)
print(" Día 1 OPTIMIZADO con 12 jobs")
print("=" * 60)
print("""
 04:35  RUN 1 - MTTR 30
 04:55  RUN 1 - Latencia 15
 05:30  RUN 1 - Soak 1h
 06:40  EXTRA - Network failure 30          <- NUEVO
 07:23  (NORMAL 2)
 10:00  EXTRA - Power failure 10            <- NUEVO
 10:30  EXTRA - Soak 2h matinal             <- NUEVO
 13:02  (ORDEÑO PM)
 15:00  RUN 2 - MTTR 30
 15:20  RUN 2 - Latencia 15
 15:55  RUN 2 - Soak 1h
 17:48  (NORMAL 5)
 20:30  RUN 3 - Soak 2h nocturno
 22:35  RUN 3 - Latencia 15
 23:00  Bundle final
""")
