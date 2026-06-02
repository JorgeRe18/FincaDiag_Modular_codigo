"""Check completo: Soak 1h (15:55-16:55) y Latency 2 (17:05-17:20)."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"; PORT = 33000; USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]


def run(client, cmd, timeout=60):
    i, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode(errors="replace"); err = e.read().decode(errors="replace")
    print(f"\n$ {cmd[:130]}")
    if out.strip(): print(out)
    if err.strip(): print("[err]", err)


c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=60)

print("=" * 70); print(" Hora + atq pendientes"); print("=" * 70)
run(c, "date; atq | sort -k2,5")

print("\n" + "=" * 70); print(" CSVs"); print("=" * 70)
run(c, "for f in mttr_results latency_e2e_results soak_results; do echo \"--- $f.csv ---\"; wc -l /home/esmeralda/$f.csv 2>&1; done")

print("\n" + "=" * 70); print(" RUN 2 Soak 1h — log final"); print("=" * 70)
run(c, "tail -25 /home/esmeralda/obj4_runs/2026-05-28_run2_soak.log 2>&1")

print("\n" + "=" * 70); print(" RUN 2 Soak — analisis CSV"); print("=" * 70)
run(c, "echo 'N ciclos:'; awk -F, 'NR>1' /home/esmeralda/soak_results.csv | wc -l")
run(c, "echo 'Exit==0:'; awk -F, 'NR>1 && $NF==0' /home/esmeralda/soak_results.csv | wc -l")
run(c, "echo 'Exit!=0:'; awk -F, 'NR>1 && $NF!=0' /home/esmeralda/soak_results.csv | wc -l")
run(c, "echo 'Mem ini-fin (MB):'; awk -F, 'NR>1 {print $4}' /home/esmeralda/soak_results.csv | head -3; echo '...'; awk -F, 'NR>1 {print $4}' /home/esmeralda/soak_results.csv | tail -3")
run(c, "echo 'Mem stats:'; awk -F, 'NR>1 {if($4>max) max=$4; if(min==\"\"||$4<min) min=$4; sum+=$4; n++} END {printf \"min=%.1f max=%.1f media=%.1f n=%d\\n\", min, max, sum/n, n}' /home/esmeralda/soak_results.csv")
run(c, "echo 't_run stats (s):'; awk -F, 'NR>1 {sum+=$3; n++} END {if(n>0) printf \"media=%.3f n=%d\\n\", sum/n, n}' /home/esmeralda/soak_results.csv")
run(c, "echo 'Spool max:'; awk -F, 'NR>1 && $6>max {max=$6} END {print max+0}' /home/esmeralda/soak_results.csv")

print("\n" + "=" * 70); print(" RUN 2b Latency — log y CSV"); print("=" * 70)
run(c, "tail -25 /home/esmeralda/obj4_runs/2026-05-28_run2b_latency.log 2>&1")
run(c, "echo 'OK:'; awk -F, 'NR>1 && $3>0' /home/esmeralda/latency_e2e_results.csv | wc -l; "
       "echo 'WARN:'; awk -F, 'NR>1 && $3==0' /home/esmeralda/latency_e2e_results.csv | wc -l")
run(c, "echo 't_total media (s):'; awk -F, 'NR>1 && $3>0 {sum+=$4; n++} END {if(n>0) printf \"%.3f n=%d\\n\", sum/n, n}' /home/esmeralda/latency_e2e_results.csv")
run(c, "echo 't_per_msg media (ms):'; awk -F, 'NR>1 && $3>0 {sum+=$5; n++} END {if(n>0) printf \"%.3f n=%d\\n\", sum/n, n}' /home/esmeralda/latency_e2e_results.csv")

print("\n" + "=" * 70); print(" Daemon + recursos sistema"); print("=" * 70)
run(c, "systemctl is-active fincadiag-gateway; df -h / | tail -1; free -m | head -2")
c.close()
