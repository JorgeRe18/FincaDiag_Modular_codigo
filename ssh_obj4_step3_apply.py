"""
Paso 3: Modificar FincaScheduler en la Pi para reducir bloques NORMAL,
y programar los tests Obj 4 en el hueco resultante.

Suspende: normal_1, normal_3, normal_4, normal_6, normal_7
Conserva: ordeño_am, normal_2, ordeño_pm, normal_5
"""
import paramiko, os, re
from pathlib import Path

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

LOCAL_SCHED = Path(r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\FincaScheduler_pi.py")

# Bloques a SUSPENDER (comentar en la lista)
SUSPEND = ["normal_1", "normal_3", "normal_4", "normal_6", "normal_7"]


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


# === Construir version modificada de FincaScheduler.py ===
print("=== [1/6] Construyendo version reducida de FincaScheduler.py ===")
with open(LOCAL_SCHED, encoding="utf-8") as f:
    content = f.read()

# Comentar lineas de bloques a suspender
out_lines = []
suspended_count = 0
for line in content.split("\n"):
    matched = False
    for bid in SUSPEND:
        # buscar `"id": "normal_1",` o variaciones
        pattern = rf'"id"\s*:\s*"{re.escape(bid)}"'
        if re.search(pattern, line) and not line.lstrip().startswith("#"):
            out_lines.append("    # [SUSPENDIDO_OBJ4] " + line.lstrip())
            suspended_count += 1
            matched = True
            break
    if not matched:
        out_lines.append(line)

new_content = "\n".join(out_lines)

# Anadir marca de version arriba
marker = "# === MODIFICADO PARA OBJ4 (Jorge, 2026-05-28): bloques NORMAL reducidos ===\n"
new_content = new_content.replace('"""\nFincaScheduler.py — v3.0',
                                   marker + '"""\nFincaScheduler.py — v3.1-obj4')

LOCAL_NEW = LOCAL_SCHED.with_name("FincaScheduler_pi_obj4.py")
with open(LOCAL_NEW, "w", encoding="utf-8") as f:
    f.write(new_content)
print(f"  Suspendidos en codigo: {suspended_count}/{len(SUSPEND)}")
print(f"  Generado: {LOCAL_NEW}")

if suspended_count != len(SUSPEND):
    print("[ERROR] No se encontraron todos los bloques. Abortando.")
    raise SystemExit(1)


# === Conectar y ejecutar ===
print("\n=== [2/6] Conectando ===")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("\n=== [3/6] Backup de FincaScheduler.py original ===")
run(c, "cp /home/esmeralda/FincaScheduler.py /home/esmeralda/FincaScheduler.py.bak_obj4 && ls -la /home/esmeralda/FincaScheduler.py*")

print("\n=== [4/6] Subiendo version reducida ===")
sftp = c.open_sftp()
sftp.put(str(LOCAL_NEW), "/home/esmeralda/FincaScheduler.py")
sftp.close()
run(c, "head -5 /home/esmeralda/FincaScheduler.py")
run(c, "grep -n 'SUSPENDIDO_OBJ4\\|\"id\":' /home/esmeralda/FincaScheduler.py | head -20")

print("\n=== [5/6] Programando tests Obj 4 con 'at' (hoy 28/05) ===")
print("  04:35 MTTR (30 ciclos)")
print("  04:55 Latencia E2E (10 ciclos)")
print("  05:30 Soak test (1h)")
print("  06:45 Bundle parcial")

DIA_LABEL = "2026-05-28"
OUT_DIR = "/home/esmeralda/obj4_runs"
run(c, f"mkdir -p {OUT_DIR}")

# Limpiar atq previo de Obj4 (por si hay basura)
out, _ = run(c, "atq", show=False)
for line in out.strip().split("\n"):
    if line.strip():
        jid = line.split()[0]
        run(c, f"atrm {jid}", show=False)

def schedule(hora, nombre, cmd):
    logfile = f"{OUT_DIR}/{DIA_LABEL}_{nombre}.log"
    full = f"echo '{cmd} > {logfile} 2>&1' | at {hora} today"
    run(c, full)

schedule("04:35", "mttr",    "bash /home/esmeralda/mttr_stress_pi.sh 30")
schedule("04:55", "latency", "bash /home/esmeralda/latency_e2e_pi.sh 10")
schedule("05:30", "soak",    "bash /home/esmeralda/soak_test_pi.sh 1 60")
schedule("06:45", "bundle",
    f"cd /home/esmeralda && tar -czf obj4_bundle_{DIA_LABEL}.tar.gz "
    f"mttr_results.csv latency_e2e_results.csv soak_results.csv "
    f"obj4_runs/ mttr_stress.log latency_e2e.log soak_test.log 2>/dev/null; "
    f"md5sum obj4_bundle_{DIA_LABEL}.tar.gz > obj4_bundle_{DIA_LABEL}.tar.gz.md5")

print("\n=== [6/6] Estado final ===")
run(c, "atq")
out, _ = run(c, "atq | awk '{print $1}'", show=False)
print("\n--- Detalle de cada job ---")
for jid in out.strip().split("\n"):
    if jid.strip():
        print(f"\n--- Job {jid} ---")
        run(c, f"at -c {jid} | tail -3")

c.close()
print("\n" + "=" * 60)
print(" PASO 3 COMPLETADO")
print("=" * 60)
print(" Manana despues de las 07:00 descargar:")
print(f"   obj4_bundle_{DIA_LABEL}.tar.gz")
print("\n Para revertir FincaScheduler:")
print("   ssh y ejecutar:")
print("   cp /home/esmeralda/FincaScheduler.py.bak_obj4 /home/esmeralda/FincaScheduler.py")
