"""Revisar logs faltantes: RUN 1 MTTR, latency, Soak 1h."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

def run(client, cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    print(out)
    err = stderr.read().decode(errors="replace")
    if err.strip(): print("[err]", err)

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("=" * 70); print(" atq pendiente"); print("=" * 70)
run(c, "date; atq | sort -k2,5")

print("\n" + "=" * 70); print(" CSVs: filas"); print("=" * 70)
run(c, "for f in mttr_results.csv latency_e2e_results.csv soak_results.csv network_failure_results.csv power_failure_results.csv; do echo \"--- $f ---\"; wc -l /home/esmeralda/$f 2>&1; done")

print("\n" + "=" * 70); print(" RUN 1 MTTR log (final)"); print("=" * 70)
run(c, "tail -40 /home/esmeralda/obj4_runs/2026-05-28_run1_mttr.log 2>&1")

print("\n" + "=" * 70); print(" RUN 1 Latency log (final)"); print("=" * 70)
run(c, "tail -40 /home/esmeralda/obj4_runs/2026-05-28_run1_latency.log 2>&1")

print("\n" + "=" * 70); print(" RUN 1 Soak 1h log (final)"); print("=" * 70)
run(c, "tail -50 /home/esmeralda/obj4_runs/2026-05-28_run1_soak.log 2>&1")
run(c, "wc -l /home/esmeralda/obj4_runs/2026-05-28_run1_soak.log")

print("\n" + "=" * 70); print(" Soak 2h matinal — en progreso"); print("=" * 70)
run(c, "tail -25 /home/esmeralda/obj4_runs/2026-05-28_extra_soak2h_am.log 2>&1")
run(c, "ps aux | grep soak_test | grep -v grep")

c.close()
