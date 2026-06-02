"""Re-validar soak con script refactorizado (sin /usr/bin/time)."""
import paramiko, os
from pathlib import Path

HOST = "gateway-esmeralda-ssh.at.remote.it"; PORT = 33000; USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]
LOCAL = Path(r"c:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests\soak_test_pi.sh")


def run(client, cmd, timeout=300):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace"); err = stderr.read().decode(errors="replace")
    print(f"\n$ {cmd[:130]}")
    if out.strip(): print(out)
    if err.strip(): print("[err]", err)
    return out


c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=120)

print("=== Subir soak refactor ===")
sftp = c.open_sftp(); sftp.put(str(LOCAL), "/home/esmeralda/soak_test_pi.sh"); sftp.close()
run(c, "chmod +x /home/esmeralda/soak_test_pi.sh")

print("\n=== Limpiar y revalidar (3 ciclos en 90s) ===")
run(c, "rm -f /home/esmeralda/soak_results.csv /home/esmeralda/soak_test.log; rm -rf /tmp/test_spool_obj4/* /tmp/test_published_obj4/*")
run(c, "bash /home/esmeralda/soak_test_pi.sh 0.025 30 2>&1 | tail -25", timeout=300)
run(c, "echo '--- CSV ---'; cat /home/esmeralda/soak_results.csv")
c.close()
