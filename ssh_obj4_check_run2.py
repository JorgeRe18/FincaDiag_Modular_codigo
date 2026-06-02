"""Check RUN 2: MTTR (15:00), Latency (15:20), Soak (15:55 en curso)."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"; PORT = 33000; USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]


def run(client, cmd, timeout=60):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace"); err = stderr.read().decode(errors="replace")
    print(f"\n$ {cmd[:130]}")
    if out.strip(): print(out)
    if err.strip(): print("[err]", err)


c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=60)

print("=" * 70); print(" Hora + atq"); print("=" * 70)
run(c, "date; atq | sort -k2,5")

print("\n" + "=" * 70); print(" CSVs ahora"); print("=" * 70)
run(c, "for f in mttr_results latency_e2e_results soak_results; do echo \"--- $f.csv ---\"; wc -l /home/esmeralda/$f.csv 2>&1; done")

print("\n" + "=" * 70); print(" RUN 2 MTTR — resumen"); print("=" * 70)
run(c, "tail -20 /home/esmeralda/obj4_runs/2026-05-28_run2_mttr.log 2>&1")
run(c, "echo 'PASS:'; awk -F, 'NR>1 && $NF==\"PASS\" {n++} END {print n}' /home/esmeralda/mttr_results.csv; "
       "echo 'FAIL:'; awk -F, 'NR>1 && $NF!=\"PASS\" {n++} END {print n+0}' /home/esmeralda/mttr_results.csv; "
       "echo 'MTTR media (s):'; awk -F, 'NR>1 && $NF==\"PASS\" {sum+=$4; n++} END {if(n>0) printf \"%.4f n=%d\\n\", sum/n, n}' /home/esmeralda/mttr_results.csv")

print("\n" + "=" * 70); print(" RUN 2 Latency — resumen"); print("=" * 70)
run(c, "tail -15 /home/esmeralda/obj4_runs/2026-05-28_run2_latency.log 2>&1")
run(c, "echo 'OK:'; awk -F, 'NR>1 && $3>0 {n++} END {print n+0}' /home/esmeralda/latency_e2e_results.csv; "
       "echo 'WARN:'; awk -F, 'NR>1 && $3==0 {n++} END {print n+0}' /home/esmeralda/latency_e2e_results.csv; "
       "echo 'Lat media per_msg (ms):'; awk -F, 'NR>1 && $5>0 {sum+=$5; n++} END {if(n>0) printf \"%.3f n=%d\\n\", sum/n, n}' /home/esmeralda/latency_e2e_results.csv")

print("\n" + "=" * 70); print(" RUN 2 Soak — en curso (15:55-16:55)"); print("=" * 70)
run(c, "tail -20 /home/esmeralda/obj4_runs/2026-05-28_run2_soak.log 2>&1")
run(c, "ls /tmp/test_spool_obj4 /tmp/test_published_obj4 2>&1")
run(c, "ps aux | grep -E 'soak_test|fincadiag.gateway.runtime --session-dir' | grep -v grep")

print("\n" + "=" * 70); print(" Daemon"); print("=" * 70)
run(c, "systemctl is-active fincadiag-gateway; ls /var/lib/fincadiag/published/")
c.close()
