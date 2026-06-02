"""Subir runtime.py con --drain-only, scripts corregidos y revalidar."""
import paramiko, os
from pathlib import Path

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

LOCAL_RUNTIME = Path(r"c:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\src\fincadiag\gateway\runtime.py")
LOCAL_TESTS = Path(r"c:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests")


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

print("=" * 70); print(" [1/6] Identificar runtime.py en Pi"); print("=" * 70)
run(c, "find /opt/fincadiag -name runtime.py 2>/dev/null; ls -la /opt/fincadiag/fincadiag/gateway/runtime.py 2>&1")

print("\n" + "=" * 70); print(" [2/6] Subir runtime.py modificado (con --drain-only)"); print("=" * 70)
sftp = c.open_sftp()
sftp.put(str(LOCAL_RUNTIME), "/tmp/runtime_obj4.py")
sftp.close()
run(c, "cp -n /opt/fincadiag/fincadiag/gateway/runtime.py /opt/fincadiag/fincadiag/gateway/runtime.py.bak_obj4 && "
       "cp /tmp/runtime_obj4.py /opt/fincadiag/fincadiag/gateway/runtime.py && "
       "chown root:root /opt/fincadiag/fincadiag/gateway/runtime.py && "
       "chmod 644 /opt/fincadiag/fincadiag/gateway/runtime.py && "
       "ls -la /opt/fincadiag/fincadiag/gateway/runtime.py*", sudo=True)

print("\n" + "=" * 70); print(" [3/6] Verificar --drain-only disponible"); print("=" * 70)
run(c, "python3 -m fincadiag.gateway.runtime --help 2>&1 | grep -A1 drain", timeout=30)

print("\n" + "=" * 70); print(" [4/6] Subir scripts corregidos (mttr y soak)"); print("=" * 70)
sftp = c.open_sftp()
sftp.put(str(LOCAL_TESTS / "mttr_stress_pi.sh"), "/home/esmeralda/mttr_stress_pi.sh")
sftp.put(str(LOCAL_TESTS / "soak_test_pi.sh"), "/home/esmeralda/soak_test_pi.sh")
sftp.close()
run(c, "chmod +x /home/esmeralda/mttr_stress_pi.sh /home/esmeralda/soak_test_pi.sh")

print("\n" + "=" * 70); print(" [5/6] Limpiar y revalidar MTTR (3 ciclos)"); print("=" * 70)
run(c, "rm -f /home/esmeralda/mttr_results.csv /home/esmeralda/mttr_stress.log; "
       "rm -rf /tmp/test_spool_obj4/* /tmp/test_published_obj4/*")
run(c, "bash /home/esmeralda/mttr_stress_pi.sh 3 2>&1 | tail -30")
run(c, "echo '--- CSV ---'; cat /home/esmeralda/mttr_results.csv")

print("\n" + "=" * 70); print(" [6/6] Validar Soak corto (90 segundos)"); print("=" * 70)
run(c, "rm -f /home/esmeralda/soak_results.csv /home/esmeralda/soak_test.log; "
       "rm -rf /tmp/test_spool_obj4/* /tmp/test_published_obj4/*")
# 90s = 0.025h, intervalo 30s -> 3 ciclos
run(c, "bash /home/esmeralda/soak_test_pi.sh 0.025 30 2>&1 | tail -30", timeout=300)
run(c, "echo '--- CSV ---'; cat /home/esmeralda/soak_results.csv")

print("\n" + "=" * 70); print(" Estado del daemon (no afectado)"); print("=" * 70)
run(c, "systemctl is-active fincadiag-gateway; ls /var/lib/fincadiag/published/")

c.close()
