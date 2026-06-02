"""Validar latency 3 ciclos + limpiar CSVs para RUN 2 limpio."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"; PORT = 33000; USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]


def run(client, cmd, timeout=300):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace"); err = stderr.read().decode(errors="replace")
    print(f"\n$ {cmd[:130]}")
    if out.strip(): print(out)
    if err.strip(): print("[err]", err)
    return out


c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=120)

print("=== Validar Latency (3 ciclos) ===")
run(c, "rm -f /home/esmeralda/latency_e2e_results.csv /home/esmeralda/latency_e2e.log; "
       "rm -rf /tmp/test_spool_obj4/* /tmp/test_published_obj4/*")
run(c, "bash /home/esmeralda/latency_e2e_pi.sh 3 2>&1 | tail -25", timeout=180)
run(c, "echo '--- CSV ---'; cat /home/esmeralda/latency_e2e_results.csv")

print("\n=== Limpiar CSVs de validacion para RUN 2 limpio ===")
run(c, "mkdir -p /home/esmeralda/obj4_runs/validacion && "
       "mv /home/esmeralda/mttr_results.csv /home/esmeralda/obj4_runs/validacion/ 2>/dev/null; "
       "mv /home/esmeralda/latency_e2e_results.csv /home/esmeralda/obj4_runs/validacion/ 2>/dev/null; "
       "mv /home/esmeralda/soak_results.csv /home/esmeralda/obj4_runs/validacion/ 2>/dev/null; "
       "mv /home/esmeralda/mttr_stress.log /home/esmeralda/obj4_runs/validacion/ 2>/dev/null; "
       "mv /home/esmeralda/latency_e2e.log /home/esmeralda/obj4_runs/validacion/ 2>/dev/null; "
       "mv /home/esmeralda/soak_test.log /home/esmeralda/obj4_runs/validacion/ 2>/dev/null; "
       "rm -rf /tmp/test_spool_obj4/* /tmp/test_published_obj4/*; "
       "ls /home/esmeralda/obj4_runs/validacion/")

print("\n=== Estado final ===")
run(c, "ls /home/esmeralda/*.csv 2>&1; echo '--- atq ---'; atq | sort -k2,5; echo '--- daemon ---'; systemctl is-active fincadiag-gateway")
c.close()
