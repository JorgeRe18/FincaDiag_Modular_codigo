"""Subir latency corregido y validar 5 ciclos."""
import paramiko, os
from pathlib import Path
HOST = "gateway-esmeralda-ssh.at.remote.it"; PORT = 33000; USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]
LOCAL = Path(r"c:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests\latency_e2e_pi.sh")


def run(client, cmd, timeout=300):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace"); err = stderr.read().decode(errors="replace")
    print(f"\n$ {cmd[:130]}")
    if out.strip(): print(out)
    if err.strip(): print("[err]", err)


c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=120)

print("=== Backup CSV RUN 2 latency (5/15 OK) ===")
run(c, "mkdir -p /home/esmeralda/obj4_runs/run2_latency_buggy && "
       "cp /home/esmeralda/latency_e2e_results.csv /home/esmeralda/obj4_runs/run2_latency_buggy/ && "
       "cp /home/esmeralda/latency_e2e.log /home/esmeralda/obj4_runs/run2_latency_buggy/ 2>/dev/null; "
       "ls /home/esmeralda/obj4_runs/run2_latency_buggy/")

print("\n=== Subir latency corregido (con warmup TLS) ===")
sftp = c.open_sftp(); sftp.put(str(LOCAL), "/home/esmeralda/latency_e2e_pi.sh"); sftp.close()
run(c, "chmod +x /home/esmeralda/latency_e2e_pi.sh")

print("\n=== Reset CSV y validar 5 ciclos ===")
run(c, "rm -f /home/esmeralda/latency_e2e_results.csv /home/esmeralda/latency_e2e.log; "
       "rm -rf /tmp/test_spool_obj4/* /tmp/test_published_obj4/*")
run(c, "bash /home/esmeralda/latency_e2e_pi.sh 5 2>&1 | tail -30", timeout=300)
run(c, "echo '--- CSV ---'; cat /home/esmeralda/latency_e2e_results.csv")

print("\n=== Si OK, restaurar el CSV de RUN 2 buggy para no perder ese chiquito ===")
# Conservamos el CSV nuevo de validacion como referencia
run(c, "mv /home/esmeralda/latency_e2e_results.csv /home/esmeralda/obj4_runs/validacion/latency_e2e_results_postfix.csv 2>/dev/null; "
       "mv /home/esmeralda/latency_e2e.log /home/esmeralda/obj4_runs/validacion/latency_e2e_postfix.log 2>/dev/null; "
       "ls /home/esmeralda/*.csv 2>&1; echo '---'; "
       "echo 'Validacion postfix:'; cat /home/esmeralda/obj4_runs/validacion/latency_e2e_results_postfix.csv 2>/dev/null")

print("\n=== Estado atq ===")
run(c, "date; atq | sort -k2,5; systemctl is-active fincadiag-gateway")
c.close()
