"""Diagnóstico profundo: MTTR PASS reales, soak vivo o muerto."""
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

print("=" * 70); print(" 1. MTTR CSV - PASS vs FAIL"); print("=" * 70)
run(c, "head -1 /home/esmeralda/mttr_results.csv; echo '...'; awk -F, 'NR>1 {print $1, $5, $NF}' /home/esmeralda/mttr_results.csv | column -t")
run(c, "echo 'PASS count:'; awk -F, 'NR>1 && $NF==\"PASS\" {n++} END {print n}' /home/esmeralda/mttr_results.csv")
run(c, "echo 'FAIL count:'; awk -F, 'NR>1 && $NF!=\"PASS\" {n++} END {print n}' /home/esmeralda/mttr_results.csv")
run(c, "echo 'MTTR PASS medio (s):'; awk -F, 'NR>1 && $NF==\"PASS\" {sum+=$5; n++} END {if(n>0) printf \"%.4f (n=%d)\\n\", sum/n, n}' /home/esmeralda/mttr_results.csv")

print("\n" + "=" * 70); print(" 2. Latency CSV completo"); print("=" * 70)
run(c, "cat /home/esmeralda/latency_e2e_results.csv")

print("\n" + "=" * 70); print(" 3. Soak: que paso?"); print("=" * 70)
run(c, "ls -la /home/esmeralda/soak_results.csv /home/esmeralda/soak_test.log 2>&1")
run(c, "cat /home/esmeralda/soak_results.csv")
run(c, "echo '--- soak_test.log ---'; tail -40 /home/esmeralda/soak_test.log 2>&1 | head -80")

print("\n" + "=" * 70); print(" 4. Procesos soak vivos?"); print("=" * 70)
run(c, "ps auxf | grep -E 'soak|fincadiag.gateway' | grep -v grep")

print("\n" + "=" * 70); print(" 5. Ver script soak_test_pi.sh (resumen)"); print("=" * 70)
run(c, "wc -l /home/esmeralda/soak_test_pi.sh; head -30 /home/esmeralda/soak_test_pi.sh")
run(c, "grep -n 'soak_results\\|RESULTS_FILE\\|psutil\\|sleep\\|csv' /home/esmeralda/soak_test_pi.sh | head -20")

c.close()
