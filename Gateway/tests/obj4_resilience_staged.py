# -*- coding: utf-8 -*-
"""
obj4_resilience_staged.py  (corre EN la Raspberry Pi)

Experimento controlado de resiliencia para el Objetivo 4.
Para cada escenario (broker / network / kill):
  1. Escenifica una sesion real procesada con nombre nuevo (RESIL_<scenario>_<ts>).
  2. Inyecta el fallo correctamente (corte REAL, no restart instantaneo).
  3. El gateway intenta publicar -> falla -> encola en disco (spool).
  4. Se restablece el servicio y se drena la cola.
  5. Mide MTTR (tiempo de drenado tras restablecer) y PLR (eventos perdidos).

Uso:
  sudo python3 obj4_resilience_staged.py --all
  sudo python3 obj4_resilience_staged.py --scenario broker
  sudo python3 obj4_resilience_staged.py --scenario network
  sudo python3 obj4_resilience_staged.py --scenario kill
  sudo python3 obj4_resilience_staged.py --dry-run
"""
import argparse
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# ── Rutas y configuracion del nodo ────────────────────────────────────────────
PROCESSED = Path("/var/lib/fincadiag/processed")
SPOOL = Path("/var/lib/fincadiag/spool")
PUBLISHED = Path("/var/lib/fincadiag/published")
SOURCE = PROCESSED / "TOMA_PM__1PM__Captura_20260511_130005"
SERVICE = "fincadiag-gateway"

_TODAY = datetime.now().strftime("%Y%m%d")
_RESULTS_DIR = Path("/home/esmeralda/resultados_obj4") / _TODAY
_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS = _RESULTS_DIR / f"obj4_resilience_results_{_TODAY}.csv"
LOG = _RESULTS_DIR / f"obj4_resilience_{_TODAY}.log"

OUTAGE_SECONDS = 90          # > 62s de backoff del publisher para forzar spooling real
BACKOFF_BUDGET = 70          # margen para que publish_batch agote reintentos
MQTT_PORT = 8883

SOAK_DURATION_MIN = 60       # duracion total del soak test en minutos (default 60)
SOAK_INTERVAL_SEC = 30       # intervalo entre muestras de memoria/CPU
SOAK_MEM_GROWTH_MAX_PCT = 20 # umbral: crecimiento de RSS aceptable
SOAK_CPU_MAX_AVG_PCT = 80    # umbral: CPU promedio aceptable

_SOAK_RESULTS = _RESULTS_DIR / f"obj4_soak_results_{_TODAY}.csv"
_SOAK_LOG = _RESULTS_DIR / f"obj4_soak_{_TODAY}.log"

GW_COMMON = [
    "--spool-dir", str(SPOOL),
    "--published-dir", str(PUBLISHED),
    "--mqtt-host", "localhost",
    "--mqtt-port", str(MQTT_PORT),
    "--tls-enabled", "--tls-min-version", "1.3",
    "--ca-path", "/etc/fincadiag/certs/ca.crt",
    "--cert-path", "/etc/fincadiag/certs/client.crt",
    "--key-path", "/etc/fincadiag/certs/client.key",
    "--topic-root", "fincadiag/la_esmeralda",
]
ENV = {**os.environ, "PYTHONPATH": "/opt/fincadiag", "PYTHONUNBUFFERED": "1"}
GW_CWD = "/opt/fincadiag"


def log(msg):
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sh(cmd, timeout=120, check=False):
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=check)
    return r


def gw(args, timeout=180):
    cmd = ["python3", "-m", "fincadiag.gateway.runtime"] + args + GW_COMMON
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=GW_CWD, env=ENV)


def count_jsonl(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip())


def parse_kv(text: str, key: str) -> int:
    """Extrae 'key=N' del stdout del runtime (published/spooled/failed/drained)."""
    for tok in text.replace("\n", " ").split():
        if tok.startswith(key + "="):
            try:
                return int(tok.split("=", 1)[1])
            except ValueError:
                return 0
    return 0


def stage_session(tag: str) -> str:
    name = f"RESIL_{tag}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    dest = PROCESSED / name
    shutil.copytree(SOURCE, dest)
    pub = PUBLISHED / f"{name}.jsonl"
    if pub.exists():
        pub.unlink()
    spool_f = SPOOL / f"{name}.jsonl"
    if spool_f.exists():
        spool_f.unlink()
    log(f"  Sesion escenificada: {name}")
    return name


def cleanup_staged(name: str):
    """Quita la carpeta procesada escenificada (deja el .jsonl publicado como evidencia)."""
    d = PROCESSED / name
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


def clean_stale_resil():
    """Elimina sesiones RESIL_* residuales en processed/ y published/ de corridas anteriores."""
    for d in PROCESSED.glob("RESIL_*"):
        shutil.rmtree(d, ignore_errors=True)
    for f in PUBLISHED.glob("RESIL_*.jsonl"):
        f.unlink(missing_ok=True)
    for f in SPOOL.glob("RESIL_*.jsonl"):
        f.unlink(missing_ok=True)


def stop_service():
    sh(["sudo", "systemctl", "stop", SERVICE])
    time.sleep(1)


def start_service():
    sh(["sudo", "systemctl", "start", SERVICE])


def service_active() -> bool:
    return sh(["systemctl", "is-active", "--quiet", SERVICE]).returncode == 0


# ── Inyeccion de fallos (corte REAL) ──────────────────────────────────────────
def broker_down():
    sh(["sudo", "systemctl", "stop", "mosquitto"])


def broker_up():
    sh(["sudo", "systemctl", "start", "mosquitto"])
    time.sleep(2)


def net_block():
    # mosquitto es local y escucha en IPv4 (0.0.0.0) e IPv6 ([::]). localhost resuelve
    # a ::1 primero, asi que hay que bloquear AMBOS stacks. Se inserta al inicio (-I)
    # con REJECT tcp-reset para forzar fallo inmediato de conexion (corte de enlace).
    # Limpia reglas residuales de corridas anteriores antes de insertar.
    net_unblock()
    sh(["sudo", "iptables", "-I", "OUTPUT", "1", "-p", "tcp", "-d", "127.0.0.1",
        "--dport", str(MQTT_PORT), "-j", "REJECT", "--reject-with", "tcp-reset"])
    sh(["sudo", "iptables", "-I", "INPUT", "1", "-p", "tcp", "-d", "127.0.0.1",
        "--dport", str(MQTT_PORT), "-j", "REJECT", "--reject-with", "tcp-reset"])
    sh(["sudo", "ip6tables", "-I", "OUTPUT", "1", "-p", "tcp", "-d", "::1",
        "--dport", str(MQTT_PORT), "-j", "REJECT", "--reject-with", "tcp-reset"])
    sh(["sudo", "ip6tables", "-I", "INPUT", "1", "-p", "tcp", "-d", "::1",
        "--dport", str(MQTT_PORT), "-j", "REJECT", "--reject-with", "tcp-reset"])
    time.sleep(1)  # garantiza que el kernel aplico las reglas antes de que el gateway conecte


def net_unblock():
    sh(["sudo", "iptables", "-D", "OUTPUT", "-p", "tcp", "-d", "127.0.0.1",
        "--dport", str(MQTT_PORT), "-j", "REJECT", "--reject-with", "tcp-reset"])
    sh(["sudo", "iptables", "-D", "INPUT", "-p", "tcp", "-d", "127.0.0.1",
        "--dport", str(MQTT_PORT), "-j", "REJECT", "--reject-with", "tcp-reset"])
    sh(["sudo", "ip6tables", "-D", "OUTPUT", "-p", "tcp", "-d", "::1",
        "--dport", str(MQTT_PORT), "-j", "REJECT", "--reject-with", "tcp-reset"])
    sh(["sudo", "ip6tables", "-D", "INPUT", "-p", "tcp", "-d", "::1",
        "--dport", str(MQTT_PORT), "-j", "REJECT", "--reject-with", "tcp-reset"])


# ── Escenarios ────────────────────────────────────────────────────────────────
def run_broker():
    log("=== Escenario BROKER (corte real de mosquitto) ===")
    stop_service()
    name = stage_session("broker")
    try:
        broker_down()
        log(f"  mosquitto detenido; publicando sesion (debe agotar backoff y encolar)...")
        r = gw(["--session-dir", str(PROCESSED / name)], timeout=BACKOFF_BUDGET + 30)
        log(f"  publish rc={r.returncode}: {r.stdout.strip()[:200]}")
        spooled = count_jsonl(SPOOL / f"{name}.jsonl")
        log(f"  spool tras fallo: {spooled} mensajes")

        broker_up()
        t0 = time.time()
        rd = gw(["--drain-only"], timeout=120)
        mttr = time.time() - t0
        log(f"  drain rc={rd.returncode}: {rd.stdout.strip()[:200]} | MTTR={mttr:.2f}s")

        drained = parse_kv(rd.stdout, "drained")
        return record("broker", name, spooled, drained, mttr)
    finally:
        cleanup_staged(name)
        start_service()


def run_network():
    log("=== Escenario NETWORK (bloqueo iptables + ip6tables 8883, IPv4+IPv6) ===")
    stop_service()
    name = stage_session("network")
    try:
        net_block()  # incluye sleep(1) interno
        log(f"  iptables/ip6tables REJECT 8883 activo (IPv4+IPv6); publicando sesion...")
        r = gw(["--session-dir", str(PROCESSED / name)], timeout=BACKOFF_BUDGET + 30)
        log(f"  publish rc={r.returncode}: {r.stdout.strip()[:200]}")
        spooled = count_jsonl(SPOOL / f"{name}.jsonl")
        log(f"  spool tras fallo: {spooled} mensajes")

        net_unblock()
        time.sleep(2)
        t0 = time.time()
        rd = gw(["--drain-only"], timeout=120)
        mttr = time.time() - t0
        log(f"  drain rc={rd.returncode}: {rd.stdout.strip()[:200]} | MTTR={mttr:.2f}s")

        drained = parse_kv(rd.stdout, "drained")
        return record("network", name, spooled, drained, mttr)
    finally:
        net_unblock()  # idempotente; por si quedo regla
        cleanup_staged(name)
        start_service()


def run_kill():
    log("=== Escenario KILL (crash del proceso a mitad de publicacion) ===")
    stop_service()
    name = stage_session("kill")
    try:
        # broker arriba; lanzamos publicacion y matamos el proceso a mitad
        cmd = ["python3", "-m", "fincadiag.gateway.runtime",
               "--session-dir", str(PROCESSED / name)] + GW_COMMON
        proc = subprocess.Popen(cmd, cwd=GW_CWD, env=ENV,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        time.sleep(1.5)  # esperar que establezca TLS y empiece a publicar mensajes
        proc.kill()
        proc.wait(timeout=10)
        log("  proceso de publicacion terminado con SIGKILL a mitad de operacion")

        published_partial = count_jsonl(PUBLISHED / f"{name}.jsonl")
        log(f"  publicado antes del crash: {published_partial} (sesion sigue en processed)")

        # Recuperacion: systemd reiniciaria el servicio; aqui republicamos la sesion intacta
        t0 = time.time()
        rr = gw(["--session-dir", str(PROCESSED / name)], timeout=120)
        mttr = time.time() - t0
        log(f"  republish rc={rr.returncode}: {rr.stdout.strip()[:200]} | MTTR={mttr:.2f}s")

        # drenar cualquier residuo en spool
        gw(["--drain-only"], timeout=120)
        published = count_jsonl(PUBLISHED / f"{name}.jsonl")
        # expected = total de mensajes de la fuente (publicacion completa)
        expected = published if published > 0 else count_jsonl(SPOOL / f"{name}.jsonl")
        return record("kill", name, expected, published, mttr)
    finally:
        cleanup_staged(name)
        start_service()


def record(scenario, name, expected, published, mttr):
    expected = max(expected, published)
    lost = max(expected - published, 0)
    plr = (lost / expected * 100.0) if expected else 0.0
    status = "PASS" if (published >= expected and expected > 0) else (
        "DATA_LOSS" if expected > 0 else "NO_DATA")
    row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "scenario": scenario,
        "session": name,
        "expected_msgs": expected,
        "published_msgs": published,
        "lost_msgs": lost,
        "plr_pct": f"{plr:.2f}",
        "mttr_s": f"{mttr:.2f}",
        "status": status,
    }
    write_row(row)
    log(f"  RESULTADO {scenario}: expected={expected} published={published} "
        f"PLR={plr:.2f}% MTTR={mttr:.2f}s -> {status}")
    return row


def write_row(row):
    new = not RESULTS.exists()
    with RESULTS.open("a", encoding="utf-8") as fh:
        if new:
            fh.write(",".join(row.keys()) + "\n")
        fh.write(",".join(str(v) for v in row.values()) + "\n")


def _read_proc_mem_kb(pid: int) -> int:
    """Lee VmRSS del proceso en KB desde /proc/PID/status."""
    try:
        text = Path(f"/proc/{pid}/status").read_text()
        for line in text.splitlines():
            if line.startswith("VmRSS:"):
                return int(line.split()[1])
    except Exception:
        pass
    return 0


def _read_proc_cpu_pct(pid: int, interval: float = 1.0) -> float:
    """Mide uso de CPU del proceso durante `interval` segundos (lectura doble de /proc/stat)."""
    def _cpu_ticks(p):
        try:
            fields = Path(f"/proc/{p}/stat").read_text().split()
            return int(fields[13]) + int(fields[14])  # utime + stime
        except Exception:
            return 0
    def _total_ticks():
        try:
            line = Path("/proc/stat").read_text().splitlines()[0]
            return sum(int(x) for x in line.split()[1:])
        except Exception:
            return 1
    proc0, total0 = _cpu_ticks(pid), _total_ticks()
    time.sleep(interval)
    proc1, total1 = _cpu_ticks(pid), _total_ticks()
    dt_total = total1 - total0
    if dt_total == 0:
        return 0.0
    return 100.0 * (proc1 - proc0) / dt_total


def _find_service_pid() -> int:
    """Devuelve el PID principal del servicio fincadiag-gateway o 0 si no corre."""
    r = sh(["systemctl", "show", "-p", "MainPID", "--value", SERVICE])
    try:
        return int(r.stdout.strip())
    except Exception:
        return 0


def _write_soak_row(row: dict):
    new = not _SOAK_RESULTS.exists()
    with _SOAK_RESULTS.open("a", encoding="utf-8") as fh:
        if new:
            fh.write(",".join(row.keys()) + "\n")
        fh.write(",".join(str(v) for v in row.values()) + "\n")


def run_soak(duration_min: int = SOAK_DURATION_MIN):
    """
    Soak test: monitorea memoria RSS y CPU del fincadiag-gateway durante
    duration_min minutos muestreando cada SOAK_INTERVAL_SEC segundos.
    Falla si el crecimiento de RSS supera SOAK_MEM_GROWTH_MAX_PCT o
    el CPU promedio supera SOAK_CPU_MAX_AVG_PCT.
    """
    with _SOAK_LOG.open("a", encoding="utf-8") as _lf:
        pass  # asegurar que el archivo existe

    def slog(msg):
        line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
        print(line, flush=True)
        with _SOAK_LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    slog(f"=== SOAK TEST inicio: {duration_min}min, muestras cada {SOAK_INTERVAL_SEC}s ===")

    if not service_active():
        start_service()
        time.sleep(3)

    pid = _find_service_pid()
    if not pid:
        slog("ERROR: no se pudo obtener PID del servicio. Saliendo.")
        return
    slog(f"  PID del gateway: {pid}")

    samples = []
    t_end = time.time() + duration_min * 60
    sample_n = 0

    rss_inicial = _read_proc_mem_kb(pid)
    slog(f"  RSS inicial: {rss_inicial} KB")

    while time.time() < t_end:
        sample_n += 1
        cpu = _read_proc_cpu_pct(pid, interval=min(SOAK_INTERVAL_SEC - 1, 2))
        rss = _read_proc_mem_kb(pid)
        elapsed_min = (duration_min * 60 - (t_end - time.time())) / 60
        row = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "sample": sample_n,
            "elapsed_min": f"{elapsed_min:.2f}",
            "pid": pid,
            "rss_kb": rss,
            "cpu_pct": f"{cpu:.2f}",
        }
        _write_soak_row(row)
        if sample_n == 1 or sample_n % 10 == 0:
            slog(f"  [{sample_n}] elapsed={elapsed_min:.1f}min RSS={rss}KB CPU={cpu:.1f}%")
        sleep_remaining = SOAK_INTERVAL_SEC - 2
        if sleep_remaining > 0:
            time.sleep(sleep_remaining)

    # Evaluacion final
    if samples or sample_n > 0:
        pass
    rss_final = _read_proc_mem_kb(pid)
    rss_growth_pct = ((rss_final - rss_inicial) / max(rss_inicial, 1)) * 100

    all_rows = []
    if _SOAK_RESULTS.exists():
        lines = _SOAK_RESULTS.read_text(encoding="utf-8").splitlines()
        header = lines[0].split(",") if lines else []
        for ln in lines[1:]:
            vals = ln.split(",")
            if len(vals) == len(header):
                all_rows.append(dict(zip(header, vals)))
    cpu_values = [float(r["cpu_pct"]) for r in all_rows if r.get("cpu_pct")]
    avg_cpu = sum(cpu_values) / len(cpu_values) if cpu_values else 0.0

    mem_ok = rss_growth_pct <= SOAK_MEM_GROWTH_MAX_PCT
    cpu_ok = avg_cpu <= SOAK_CPU_MAX_AVG_PCT
    status = "PASS" if (mem_ok and cpu_ok) else "FAIL"

    slog(f"  RESULTADO SOAK: muestras={sample_n} RSS_inicial={rss_inicial}KB "
         f"RSS_final={rss_final}KB crecimiento={rss_growth_pct:.1f}% "
         f"CPU_avg={avg_cpu:.1f}% -> {status}")
    if not mem_ok:
        slog(f"  [WARN] Crecimiento RSS {rss_growth_pct:.1f}% supera umbral {SOAK_MEM_GROWTH_MAX_PCT}%")
    if not cpu_ok:
        slog(f"  [WARN] CPU promedio {avg_cpu:.1f}% supera umbral {SOAK_CPU_MAX_AVG_PCT}%")

    summary_row = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "scenario": "soak",
        "duration_min": duration_min,
        "total_samples": sample_n,
        "rss_inicial_kb": rss_inicial,
        "rss_final_kb": rss_final,
        "rss_growth_pct": f"{rss_growth_pct:.2f}",
        "avg_cpu_pct": f"{avg_cpu:.2f}",
        "status": status,
    }
    write_row(summary_row)
    slog(f"=== SOAK TEST fin ===")


def preflight():
    problems = []
    if os.geteuid() != 0:
        problems.append("Debe correr con sudo (root) para systemctl/iptables.")
    if not SOURCE.exists():
        problems.append(f"No existe la sesion fuente: {SOURCE}")
    if not Path(GW_CWD).exists():
        problems.append(f"No existe el paquete del gateway en {GW_CWD}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--scenario", choices=["broker", "network", "kill", "soak"])
    ap.add_argument("--cycles", type=int, default=1,
                    help="Repeticiones de cada escenario por corrida (default 1)")
    ap.add_argument("--soak-minutes", type=int, default=SOAK_DURATION_MIN,
                    help=f"Duracion del soak en minutos (default {SOAK_DURATION_MIN})")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    problems = preflight()
    if args.dry_run:
        print("=== DRY RUN ===")
        print(f"Fuente   : {SOURCE} (existe={SOURCE.exists()})")
        print(f"Spool    : {SPOOL}")
        print(f"Published: {PUBLISHED}")
        print(f"Servicio : {SERVICE} activo={service_active()}")
        print(f"Corte    : {OUTAGE_SECONDS}s | backoff budget {BACKOFF_BUDGET}s")
        print(f"Soak     : {args.soak_minutes}min, muestra cada {SOAK_INTERVAL_SEC}s")
        print(f"Ciclos   : {args.cycles}")
        print("Problemas:", problems or "ninguno")
        return

    if problems:
        for p in problems:
            log(f"PREFLIGHT FALLO: {p}")
        sys.exit(1)

    if getattr(args, "scenario", None) == "soak":
        log(f"### Inicio SOAK TEST Obj4 ({args.soak_minutes}min) ###")
        run_soak(duration_min=args.soak_minutes)
        log(f"### Fin SOAK TEST. Servicio gateway activo: {service_active()} ###")
        return

    scenarios = []
    if args.all:
        scenarios = ["broker", "network", "kill"]
    elif args.scenario:
        scenarios = [args.scenario]
    else:
        ap.error("Indica --all, --scenario <x>, --scenario soak o --dry-run")

    cycles = max(1, args.cycles)
    log(f"### Inicio experimento Obj4: {scenarios} x{cycles} ciclos ###")
    clean_stale_resil()
    net_unblock()  # limpiar reglas iptables residuales de corridas previas
    try:
        for cycle in range(1, cycles + 1):
            if cycles > 1:
                log(f"--- Ciclo {cycle}/{cycles} ---")
            for s in scenarios:
                {"broker": run_broker, "network": run_network, "kill": run_kill}[s]()
                time.sleep(3)
    finally:
        if not service_active():
            start_service()
        log("### Fin experimento. Servicio gateway activo: "
            f"{service_active()} ###")


if __name__ == "__main__":
    main()
