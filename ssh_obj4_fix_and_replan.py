"""
1. Cancela at pendientes y mata soak 2h matinal en curso.
2. Limpia CSVs contaminados (MTTR, latency, soak). CONSERVA network y power que son válidos.
3. Sube los 5 scripts corregidos (spool/published aislados).
4. Reagenda RUN 2, RUN 3 y bundle final con los scripts corregidos.
"""
import paramiko, os
from pathlib import Path

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

LOCAL_TESTS = Path(r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests")
DIA_LABEL = "2026-05-28"
OUT_DIR = "/home/esmeralda/obj4_runs"
SCRIPTS = [
    "mttr_stress_pi.sh", "latency_e2e_pi.sh", "soak_test_pi.sh",
    "network_failure_pi.sh", "power_failure_sim_pi.sh",
]


def run(client, cmd, sudo=False, timeout=120, show=True):
    if sudo:
        cmd = f"echo {PASSWORD} | sudo -S bash -c \"{cmd}\""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show:
        print(f"\n$ {cmd[:130]}")
        if out.strip(): print(out)
        if err.strip() and "password for" not in err.lower(): print("[err]", err)
    return out


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("=" * 70); print(" [1/8] Cancelar at pendientes"); print("=" * 70)
out = run(c, "atq", show=True)
for line in out.strip().split("\n"):
    if line.strip():
        jid = line.split()[0]
        run(c, f"atrm {jid}", show=False)
run(c, "atq")

print("\n" + "=" * 70); print(" [2/8] Matar soak 2h matinal vivo (si esta)"); print("=" * 70)
run(c, "pkill -f 'soak_test_pi.sh' 2>&1 || true; pkill -f 'fincadiag.gateway.runtime --session-dir' 2>&1 || true")
run(c, "sleep 2; ps aux | grep -E 'soak_test|session-dir' | grep -v grep", show=True)

print("\n" + "=" * 70); print(" [3/8] Conservar resultados validos (network, power)"); print("=" * 70)
run(c, "mkdir -p /home/esmeralda/obj4_runs/conservados && "
       "cp /home/esmeralda/network_failure_results.csv /home/esmeralda/obj4_runs/conservados/ && "
       "cp /home/esmeralda/power_failure_results.csv /home/esmeralda/obj4_runs/conservados/ && "
       "cp /home/esmeralda/network_failure.log /home/esmeralda/obj4_runs/conservados/ && "
       "cp /home/esmeralda/power_failure.log /home/esmeralda/obj4_runs/conservados/ && "
       "ls -la /home/esmeralda/obj4_runs/conservados/")

print("\n" + "=" * 70); print(" [4/8] Limpiar CSVs contaminados (MTTR, latency, soak)"); print("=" * 70)
# Backup primero
run(c, "mkdir -p /home/esmeralda/obj4_runs/descartados_run1 && "
       "mv /home/esmeralda/mttr_results.csv /home/esmeralda/obj4_runs/descartados_run1/ && "
       "mv /home/esmeralda/latency_e2e_results.csv /home/esmeralda/obj4_runs/descartados_run1/ && "
       "mv /home/esmeralda/soak_results.csv /home/esmeralda/obj4_runs/descartados_run1/ && "
       "mv /home/esmeralda/mttr_stress.log /home/esmeralda/obj4_runs/descartados_run1/ && "
       "mv /home/esmeralda/latency_e2e.log /home/esmeralda/obj4_runs/descartados_run1/ && "
       "mv /home/esmeralda/soak_test.log /home/esmeralda/obj4_runs/descartados_run1/ && "
       "ls -la /home/esmeralda/obj4_runs/descartados_run1/")

# Reset network/power CSVs para acumular nuevos ciclos limpios
run(c, "mv /home/esmeralda/network_failure_results.csv /home/esmeralda/obj4_runs/descartados_run1/network_failure_results_run1_OK.csv 2>/dev/null || true; "
       "mv /home/esmeralda/power_failure_results.csv /home/esmeralda/obj4_runs/descartados_run1/power_failure_results_run1_OK.csv 2>/dev/null || true; "
       "mv /home/esmeralda/network_failure.log /home/esmeralda/obj4_runs/descartados_run1/network_failure_run1_OK.log 2>/dev/null || true; "
       "mv /home/esmeralda/power_failure.log /home/esmeralda/obj4_runs/descartados_run1/power_failure_run1_OK.log 2>/dev/null || true")

# Limpiar el spool/published que pudiera haber quedado contaminado en /tmp (de runs viejos)
run(c, "rm -rf /tmp/test_spool_obj4 /tmp/test_published_obj4 2>&1; mkdir -p /tmp/test_spool_obj4 /tmp/test_published_obj4")

print("\n" + "=" * 70); print(" [5/8] Subir 5 scripts corregidos (spool/published aislados)"); print("=" * 70)
sftp = c.open_sftp()
for f in SCRIPTS:
    sftp.put(str(LOCAL_TESTS / f), f"/home/esmeralda/{f}")
    print(f"  OK: {f}")
sftp.close()
run(c, "chmod +x /home/esmeralda/*.sh")
run(c, "grep -n 'SPOOL_DIR=\\|PUB_DIR=' /home/esmeralda/{mttr_stress,latency_e2e,soak_test,network_failure,power_failure_sim}_pi.sh")

print("\n" + "=" * 70); print(" [6/8] Reagendar RUN 2 (15:00), RUN 3 (20:30) y Bundle (23:00)"); print("=" * 70)


def schedule_at(hora, label, cmd):
    log = f"{OUT_DIR}/{DIA_LABEL}_{label}.log"
    full = f"echo '{cmd} > {log} 2>&1' | at {hora} today"
    run(c, full)


# RUN 2: MTTR + Latency + Soak 1h (en hueco post-PM 14:22 hasta NORMAL 5 17:48)
schedule_at("15:00", "run2_mttr",    "bash /home/esmeralda/mttr_stress_pi.sh 30")
schedule_at("15:20", "run2_latency", "bash /home/esmeralda/latency_e2e_pi.sh 15")
schedule_at("15:55", "run2_soak",    "bash /home/esmeralda/soak_test_pi.sh 1 60")

# RUN 3: Soak 2h + Latency (en hueco post-NORMAL5 19:55 hasta NORMAL 7 23:26)
schedule_at("20:30", "run3_soak",    "bash /home/esmeralda/soak_test_pi.sh 2 60")
schedule_at("22:35", "run3_latency", "bash /home/esmeralda/latency_e2e_pi.sh 15")

# RUN 4 extra: redo MTTR + repetir network/power para ampliar muestra (en la noche tardia)
# Postergamos al dia 2.

# Bundle final del dia 1
bundle_cmd = (
    f"cd /home/esmeralda && tar -czf obj4_bundle_{DIA_LABEL}.tar.gz "
    f"mttr_results.csv latency_e2e_results.csv soak_results.csv "
    f"network_failure_results.csv power_failure_results.csv "
    f"obj4_runs/ mttr_stress.log latency_e2e.log soak_test.log "
    f"network_failure.log power_failure.log 2>/dev/null; "
    f"md5sum obj4_bundle_{DIA_LABEL}.tar.gz > obj4_bundle_{DIA_LABEL}.tar.gz.md5"
)
schedule_at("23:00", "bundle_dia1", bundle_cmd)

print("\n" + "=" * 70); print(" [7/8] Estado final de jobs"); print("=" * 70)
run(c, "atq | sort -k2,5")

print("\n" + "=" * 70); print(" [8/8] Verificacion de spool/published aislados"); print("=" * 70)
run(c, "ls -la /tmp/test_spool_obj4 /tmp/test_published_obj4")
run(c, "ls -la /var/lib/fincadiag/spool /var/lib/fincadiag/published")
run(c, "systemctl is-active fincadiag-gateway")

c.close()
print("\n" + "=" * 70)
print(" RE-PLAN APLICADO")
print("=" * 70)
print("""
 Conservados (en /home/esmeralda/obj4_runs/conservados/):
   - network_failure_results.csv (30/30 PASS, MTTR=0.399s)
   - power_failure_results.csv   (10/10 PASS, MTTR=0.271s)

 Descartados (en /home/esmeralda/obj4_runs/descartados_run1/):
   - MTTR, Latency, Soak del RUN 1 (contaminados por daemon).

 Re-programado:
   15:00  RUN 2  MTTR 30   (script corregido, spool aislado)
   15:20  RUN 2  Latency 15
   15:55  RUN 2  Soak 1h
   20:30  RUN 3  Soak 2h
   22:35  RUN 3  Latency 15
   23:00  Bundle final dia 1

 fincadiag-gateway.service: SIGUE CORRIENDO (no se toco).
""")
