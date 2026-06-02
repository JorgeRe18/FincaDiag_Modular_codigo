"""Revisar logs y resultados de las pruebas Obj 4 corridas hasta ahora."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]


def run(client, cmd, sudo=False, timeout=120):
    if sudo:
        cmd = f"echo {PASSWORD} | sudo -S bash -c \"{cmd}\""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    print(f"\n$ {cmd[:120]}")
    if out.strip():
        print(out)
    if err.strip() and "password for" not in err.lower():
        print("[err]", err)
    return out


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("=" * 70)
print(" 1. Hora actual + jobs pendientes")
print("=" * 70)
run(c, "date")
run(c, "atq | sort -k2,5")

print("\n" + "=" * 70)
print(" 2. CSVs de resultados (tamano y filas)")
print("=" * 70)
run(c, "ls -la /home/esmeralda/*.csv 2>&1")
for csv in ["mttr_results.csv", "latency_e2e_results.csv", "soak_results.csv",
            "network_failure_results.csv", "power_failure_results.csv"]:
    run(c, f"echo '--- {csv} ---'; wc -l /home/esmeralda/{csv} 2>/dev/null; head -3 /home/esmeralda/{csv} 2>/dev/null; echo '...'; tail -3 /home/esmeralda/{csv} 2>/dev/null")

print("\n" + "=" * 70)
print(" 3. Logs de cada job (resumen)")
print("=" * 70)
run(c, "ls -la /home/esmeralda/obj4_runs/ 2>&1")

for label in ["run1_mttr", "run1_latency", "run1_soak", "extra_network",
              "extra_power", "extra_soak2h_am"]:
    fname = f"/home/esmeralda/obj4_runs/2026-05-28_{label}.log"
    run(c, f"echo '--- {label} ---'; ls -la {fname} 2>/dev/null; echo 'Ultimas lineas:'; tail -10 {fname} 2>/dev/null")

print("\n" + "=" * 70)
print(" 4. FincaScheduler events (sigue corriendo bien?)")
print("=" * 70)
run(c, "tail -30 /home/esmeralda/FincaLogs/fincadiag_scheduler_events.log 2>/dev/null")
run(c, "tail -20 /home/esmeralda/FincaLogs/cron_scheduler.log 2>/dev/null")

print("\n" + "=" * 70)
print(" 5. Estado de espacio en disco")
print("=" * 70)
run(c, "df -h / /var /home")

print("\n" + "=" * 70)
print(" 6. Procesos relevantes ahora")
print("=" * 70)
run(c, "ps aux | grep -E 'python3|mosquitto|FincaDiag|gateway|soak|mttr' | grep -v grep")

c.close()
