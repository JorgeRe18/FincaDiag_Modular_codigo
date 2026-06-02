# -*- coding: utf-8 -*-
"""
Limpieza y reorganización del home de esmeralda en la Raspberry Pi.

ESTRUCTURA RESULTANTE:
/home/esmeralda/
├── FincaDiag.py                     (script principal - se queda)
├── FincaScheduler.py                (scheduler activo - se queda)
├── FincaLogs/                       (logs activos del sistema - se queda)
├── data/                            (datos de campo - se queda)
├── exports/                         (exportaciones - se queda)
├── run_gateway.sh                   (script de sistema - se queda)
├── export_visita_pi.sh              (exportación - se queda)
├── inject_fault_live_pi.sh          (inyección live - se queda)
├── measure_live_resilience_pi.sh    (medición live - se queda)
├── obj4_resilience_staged.py        (script experimento final - se queda)
└── resultados_obj4/
    ├── FINALES_31mayo/              (resultados válidos para el TFG)
    │   ├── obj4_resilience_results.csv
    │   ├── obj4_resilience.log
    │   ├── fault_injections.csv
    │   └── fault_injections.log
    └── HISTORICOS_28_29mayo/        (iteraciones previas)
        ├── mttr_results.csv
        ├── mttr_stress.log
        ├── mttr_systemd.log
        ├── mttr_systemd_results.csv
        ├── latency_e2e.log
        ├── latency_e2e_results.csv
        ├── soak_results.csv
        ├── soak_test.log
        ├── obj4_bundle_2026-05-28.tar.gz
        └── runs/  (contenido de obj4_runs/)

ELIMINADO:
- FincaScheduler.py.bak_obj4_28may  (backup obsoleto)
- __pycache__/                       (artefacto Python)
- obj4_bundle_2026-05-28.tar.gz.md5 (archivo vacío)
- fincadiag_cron.log                 (log viejo de marzo, reemplazado por FincaLogs/)
- fincadiag_scheduler.log            (log viejo de abril, reemplazado por FincaLogs/)
- Scripts de pruebas individuales ya obsoletos (9 scripts .sh)
"""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

def run(cmd, label=""):
    _, stdout, stderr = c.exec_command(cmd, timeout=60)
    out = stdout.read().decode(errors="replace").strip()
    err = stderr.read().decode(errors="replace").strip()
    if label:
        print(f"  [{label}] {cmd[:80]}")
    if out:
        print(f"    {out}")
    if err:
        print(f"    [err] {err}")
    return out

print("=" * 60)
print("  REORGANIZACIÓN del home de esmeralda")
print("=" * 60)

# ── 1. Crear estructura de carpetas ──────────────────────────
print("\n[1/4] Creando estructura resultados_obj4/")
run("mkdir -p /home/esmeralda/resultados_obj4/FINALES_31mayo",    "mkdir")
run("mkdir -p /home/esmeralda/resultados_obj4/HISTORICOS_28_29mayo/runs", "mkdir")

# ── 2. Mover resultados finales (31 mayo) ────────────────────
print("\n[2/4] Moviendo resultados FINALES (31 mayo)...")
finales = [
    "obj4_resilience_results.csv",
    "obj4_resilience.log",
    "fault_injections.csv",
    "fault_injections.log",
]
for f in finales:
    run(f"mv /home/esmeralda/{f} /home/esmeralda/resultados_obj4/FINALES_31mayo/{f} 2>/dev/null || echo 'no encontrado: {f}'", "mv")

# ── 3. Mover resultados históricos (28-29 mayo) ───────────────
print("\n[3/4] Moviendo resultados HISTORICOS (28-29 mayo)...")
historicos = [
    "mttr_results.csv",
    "mttr_stress.log",
    "mttr_systemd.log",
    "mttr_systemd_results.csv",
    "latency_e2e.log",
    "latency_e2e_results.csv",
    "soak_results.csv",
    "soak_test.log",
    "obj4_bundle_2026-05-28.tar.gz",
]
for f in historicos:
    run(f"mv /home/esmeralda/{f} /home/esmeralda/resultados_obj4/HISTORICOS_28_29mayo/{f} 2>/dev/null || echo 'no encontrado: {f}'", "mv")

# Mover obj4_runs/ como subdirectorio runs/
run("mv /home/esmeralda/obj4_runs/* /home/esmeralda/resultados_obj4/HISTORICOS_28_29mayo/runs/ 2>/dev/null || true", "mv runs")
run("rmdir /home/esmeralda/obj4_runs 2>/dev/null || true", "rmdir obj4_runs")

# ── 4. Eliminar archivos obsoletos ───────────────────────────
print("\n[4/4] Eliminando archivos obsoletos...")

to_delete = [
    # Backup obsoleto
    "/home/esmeralda/FincaScheduler.py.bak_obj4_28may",
    # Artefacto Python
    "/home/esmeralda/__pycache__",
    # Archivo vacío (md5 de 0 bytes)
    "/home/esmeralda/obj4_bundle_2026-05-28.tar.gz.md5",
    # Logs viejos del home (reemplazados por FincaLogs/)
    "/home/esmeralda/fincadiag_cron.log",
    "/home/esmeralda/fincadiag_scheduler.log",
    # Scripts de pruebas individuales obsoletos (reemplazados por obj4_resilience_staged.py)
    "/home/esmeralda/latency_e2e_pi.sh",
    "/home/esmeralda/mttr_stress_pi.sh",
    "/home/esmeralda/mttr_systemd_pi.sh",
    "/home/esmeralda/network_failure_pi.sh",
    "/home/esmeralda/power_failure_sim_pi.sh",
    "/home/esmeralda/schedule_obj4_pi.sh",
    "/home/esmeralda/setup_cron_export.sh",
    "/home/esmeralda/soak_test_pi.sh",
    "/home/esmeralda/suspend_intermediate_captures_pi.sh",
]
for path in to_delete:
    run(f"rm -rf {path}", "rm")

# ── 5. Estado final ──────────────────────────────────────────
print("\n" + "=" * 60)
print("  ESTADO FINAL")
print("=" * 60)

print("\n--- /home/esmeralda/ ---")
run("ls -la /home/esmeralda/")

print("\n--- resultados_obj4/ ---")
run("find /home/esmeralda/resultados_obj4 | sort")

c.close()
print("\n=== Reorganización completada ===")
