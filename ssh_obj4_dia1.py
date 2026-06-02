"""
SSH Día 1 (28/05): aplicar todo en la Pi.
  1. Subir scripts adicionales (network/power failure)
  2. Modificar FincaScheduler.py (suspender NORMAL_1, NORMAL_3, NORMAL_4, NORMAL_6)
  3. Programar 3 RUNs de hoy via 'at'
  4. Verificar
"""
import paramiko, os, re
from pathlib import Path

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

LOCAL_SCHED = Path(r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\FincaScheduler_pi.py")
LOCAL_TESTS = Path(r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests")
SUSPEND = ["normal_1", "normal_3", "normal_4", "normal_6"]
DIA_LABEL = "2026-05-28"


def run(client, cmd, sudo=False, timeout=120, show=True):
    if sudo:
        cmd = f"echo {PASSWORD} | sudo -S bash -c \"{cmd}\""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show:
        print(f"$ {cmd[:90]}")
        if out.strip():
            print(out)
        if err.strip() and "password for" not in err.lower():
            print("[err]", err)
        print()
    return out, err


# ── Construir version reducida de FincaScheduler.py ──────────────────────────
print("=== [1/7] Construyendo FincaScheduler reducido ===")
with open(LOCAL_SCHED, encoding="utf-8") as f:
    content = f.read()

out_lines = []
suspended = 0
for line in content.split("\n"):
    matched = False
    for bid in SUSPEND:
        pat = rf'"id"\s*:\s*"{re.escape(bid)}"'
        if re.search(pat, line) and not line.lstrip().startswith("#"):
            out_lines.append("    # [SUSPENDIDO_OBJ4_28MAY] " + line.lstrip())
            suspended += 1
            matched = True
            break
    if not matched:
        out_lines.append(line)

new_content = "\n".join(out_lines)
marker = "# === MODIFICADO PARA OBJ4 (Jorge, 2026-05-28): NORMAL_1/3/4/6 suspendidos ===\n"
new_content = new_content.replace(
    '"""\nFincaScheduler.py — v3.0',
    marker + '"""\nFincaScheduler.py — v3.1-obj4'
)

LOCAL_NEW = LOCAL_SCHED.with_name("FincaScheduler_pi_obj4.py")
with open(LOCAL_NEW, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"  Suspendidos en codigo: {suspended}/{len(SUSPEND)}")
if suspended != len(SUSPEND):
    raise SystemExit("[ERROR] No se suspendieron todos los bloques esperados")


# ── Conectar y ejecutar ──────────────────────────────────────────────────────
print("\n=== [2/7] Conectando ===")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("\n=== [3/7] Subir scripts de tests adicionales ===")
sftp = c.open_sftp()
for f in ["network_failure_pi.sh", "power_failure_sim_pi.sh"]:
    src = LOCAL_TESTS / f
    dst = f"/home/esmeralda/{f}"
    sftp.put(str(src), dst)
    print(f"  OK: {f}")
sftp.close()
run(c, "chmod +x /home/esmeralda/network_failure_pi.sh /home/esmeralda/power_failure_sim_pi.sh")

print("\n=== [4/7] Backup y reemplazo de FincaScheduler.py ===")
# El archivo original es de root, hay que usar sudo
run(c, "cp -n /home/esmeralda/FincaScheduler.py /home/esmeralda/FincaScheduler.py.bak_obj4_28may", sudo=True)
run(c, "ls -la /home/esmeralda/FincaScheduler.py*")

# Subir a /tmp (escritura libre) y luego mover con sudo
sftp = c.open_sftp()
sftp.put(str(LOCAL_NEW), "/tmp/FincaScheduler_obj4.py")
sftp.close()
run(c, "mv /tmp/FincaScheduler_obj4.py /home/esmeralda/FincaScheduler.py && chown root:root /home/esmeralda/FincaScheduler.py && chmod 644 /home/esmeralda/FincaScheduler.py", sudo=True)

run(c, "head -5 /home/esmeralda/FincaScheduler.py")
run(c, "grep -n 'SUSPENDIDO_OBJ4_28MAY\\|\"id\":' /home/esmeralda/FincaScheduler.py")

print("\n=== [5/7] Limpiar 'at' previo ===")
out, _ = run(c, "atq", show=False)
for line in out.strip().split("\n"):
    if line.strip():
        run(c, f"atrm {line.split()[0]}", show=False)
run(c, "atq")

print("\n=== [6/7] Programando RUN 1, 2, 3 (28/05) ===")
OUT_DIR = "/home/esmeralda/obj4_runs"
run(c, f"mkdir -p {OUT_DIR}")


def schedule_at(hora, label, cmd):
    log = f"{OUT_DIR}/{DIA_LABEL}_{label}.log"
    full = f"echo '{cmd} > {log} 2>&1' | at {hora} today"
    run(c, full)


# RUN 1 (madrugada): MTTR 30 + Latencia 15 + Soak 1h
schedule_at("04:35", "run1_mttr",    "bash /home/esmeralda/mttr_stress_pi.sh 30")
schedule_at("04:55", "run1_latency", "bash /home/esmeralda/latency_e2e_pi.sh 15")
schedule_at("05:30", "run1_soak",    "bash /home/esmeralda/soak_test_pi.sh 1 60")

# RUN 2 (tarde, donde estaba NORMAL_4): MTTR 30 + Latencia 15 + Soak 1h
schedule_at("15:00", "run2_mttr",    "bash /home/esmeralda/mttr_stress_pi.sh 30")
schedule_at("15:20", "run2_latency", "bash /home/esmeralda/latency_e2e_pi.sh 15")
schedule_at("15:55", "run2_soak",    "bash /home/esmeralda/soak_test_pi.sh 1 60")

# RUN 3 (noche, donde estaba NORMAL_6): Soak 2h + Latencia 15
schedule_at("20:30", "run3_soak",    "bash /home/esmeralda/soak_test_pi.sh 2 60")
schedule_at("22:35", "run3_latency", "bash /home/esmeralda/latency_e2e_pi.sh 15")

# Bundle final
bundle_cmd = (
    f"cd /home/esmeralda && tar -czf obj4_bundle_{DIA_LABEL}.tar.gz "
    f"mttr_results.csv latency_e2e_results.csv soak_results.csv "
    f"network_failure_results.csv power_failure_results.csv "
    f"obj4_runs/ mttr_stress.log latency_e2e.log soak_test.log "
    f"network_failure.log power_failure.log 2>/dev/null; "
    f"md5sum obj4_bundle_{DIA_LABEL}.tar.gz > obj4_bundle_{DIA_LABEL}.tar.gz.md5"
)
schedule_at("23:00", "bundle_dia1", bundle_cmd)

print("\n=== [7/7] Estado final de jobs ===")
run(c, "atq")
out, _ = run(c, "atq | sort -k2,3 | awk '{print $1}'", show=False)
print("\n--- Detalle ---")
for jid in out.strip().split("\n"):
    if jid.strip():
        print(f"\n--- Job {jid} ---")
        run(c, f"at -c {jid} | tail -3")

c.close()
print("\n" + "=" * 60)
print(" DIA 1 PROGRAMADO")
print("=" * 60)
print("\n RUN 1 (madrugada): 04:35 - 06:35  (MTTR 30 + Lat 15 + Soak 1h)")
print(" RUN 2 (tarde):     15:00 - 17:00  (MTTR 30 + Lat 15 + Soak 1h)")
print(" RUN 3 (noche):     20:30 - 22:45  (Soak 2h + Lat 15)")
print(" Bundle:            23:00")
print("\n Manana 29/05 ~01:00 corre script ssh_obj4_dia2.py para fallos.")
print(" Manana ~07:00 podes descargar obj4_bundle_2026-05-28.tar.gz")
