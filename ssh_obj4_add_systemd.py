"""Sube mttr_systemd_pi.sh y lo agenda en un hueco del Dia 2 (29/05/2026).

Mide MTTR del servicio fincadiag-gateway gestionado por systemd:
kill -9 al servicio -> espera Restart=always -> mide tiempo hasta MQTT ready.

Complementa power_failure_sim_pi.sh (que mide runtime puro aislado).
"""
import os
import paramiko

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]
DIA_LABEL = "2026-05-29"
OUT_DIR = "/home/esmeralda/obj4_runs"

LOCAL_SCRIPT = r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests\mttr_systemd_pi.sh"
REMOTE_SCRIPT = "/home/esmeralda/mttr_systemd_pi.sh"


def run(client, cmd, timeout=60, show=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show:
        print(f"$ {cmd[:120]}")
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

print("=== Subiendo mttr_systemd_pi.sh ===")
sftp = c.open_sftp()
sftp.put(LOCAL_SCRIPT, REMOTE_SCRIPT)
sftp.close()
run(c, f"chmod +x {REMOTE_SCRIPT}")
run(c, f"head -20 {REMOTE_SCRIPT}")

print("=== Asegurando OUT_DIR ===")
run(c, f"mkdir -p {OUT_DIR}")

print("=== Agendando 10 ciclos en Dia 2 a las 09:30 ===")
log = f"{OUT_DIR}/{DIA_LABEL}_mttr_systemd.log"
# 10 ciclos x ~20s cooldown + recovery -> ~5 min total. Hueco amplio.
at_cmd = f"echo 'bash {REMOTE_SCRIPT} 10 > {log} 2>&1' | at 09:30 2026-05-29"
run(c, at_cmd)

print("=== Estado de jobs ===")
run(c, "atq | sort -k2,5")

c.close()
print("=" * 60)
print(" mttr_systemd agendado: Dia 2 (29/05) a las 09:30, 10 ciclos")
print("=" * 60)
print("""
Despues de la corrida revisar:
  cat /home/esmeralda/mttr_systemd_results.csv
  cat /home/esmeralda/mttr_systemd.log

Verificar que el daemon sigue activo:
  systemctl is-active fincadiag-gateway
""")
