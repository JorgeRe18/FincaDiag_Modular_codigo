# === MODIFICADO PARA OBJ4 (Jorge, 2026-05-28): NORMAL_1/3/4/6 suspendidos ===
"""
FincaScheduler.py — v3.1-obj4
Orquestador de capturas alineado al timeline verificado de la finca.

Timeline del día (9 bloques, descanso ~45min entre bloques):
  02:25  ORDEÑO AM → Baseline / Serial+Antena+PCAP 1h20 / Baseline / Descanso 45min
  04:34  NORMAL 1  → Baseline / Antena 1h / PCAP 1h / Baseline / Descanso 45min
  07:23  NORMAL 2  → Baseline / Antena 1h / PCAP 1h / Baseline / Descanso 45min
  10:12  NORMAL 3  → Baseline / Antena 1h / PCAP 1h / Baseline / Descanso 39min
  13:02  ORDEÑO PM → Baseline / Serial+Antena+PCAP 1h15 / Baseline / Descanso 45min
  15:10  NORMAL 4  → Baseline / Antena 1h / PCAP 1h / Baseline / Descanso 45min
  17:48  NORMAL 5  → Baseline / Antena 1h / PCAP 1h / Baseline / Descanso 45min
  20:37  NORMAL 6  → Baseline / Antena 1h / PCAP 1h / Baseline / Descanso 45min
  23:26  NORMAL 7  → Baseline / Antena 1h / PCAP 1h / Baseline / Descanso 55min

Modos de FincaDiag.py:
  -m 1  Antena UDP + PCAP filtrado puerto 6001
  -m 2  Serial + PCAP completo  ← bloque ORDEÑO, serial y PCAP en paralelo
  -m 3  Solo PCAP completo      ← bloque NORMAL, 1h
  -m 4  Baseline
"""

import copy
import json
import os
import socket
import subprocess
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta

try:
    import fcntl
except ImportError:
    fcntl = None


# ── Rutas ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FINCADIAG  = os.path.join(SCRIPT_DIR, "FincaDiag.py")
BASE_DIR   = "/home/esmeralda/FincaLogs"
STATE_FILE = os.path.join(BASE_DIR, "fincadiag_scheduler_state.json")
LOCK_FILE  = os.path.join(BASE_DIR, "fincadiag_scheduler.lock")
EVENT_LOG  = os.path.join(BASE_DIR, "fincadiag_scheduler_events.log")

# ── Red ───────────────────────────────────────────────────────────────────────
INTERFACE_NAME = "eth0"
PING_HOST      = "8.8.8.8"

# ── Tiempos internos ──────────────────────────────────────────────────────────
HEARTBEAT_SECONDS        = 15
NETWORK_CHECK_SECONDS    = 30
CAPTURE_GRACE_SECONDS    = 60   # margen extra antes de forzar kill
BASELINE_TIMEOUT_SECONDS = 120  # máximo que puede tardar un baseline

# ── Duraciones de captura ─────────────────────────────────────────────────────
DUR_ANTENA          = 3600   # 1 hora  — modo 1
DUR_PCAP_SERIAL_AM  = 4800   # 1h 20min — modo 2 ordeño AM  (02:25 → 03:45)
DUR_PCAP_SERIAL_PM  = 4800   # 1h 20min — modo 2 ordeño PM  (13:02 → 14:58)
DUR_PCAP            = 3600   # 1 hora  — modo 3

# ── Definición del timeline ───────────────────────────────────────────────────
# inicio: (hora, minuto) en formato 24h local
# tipo:   "ordeño" lanza Antena → PCAP+Serial(2h)
#         "normal" lanza Antena → PCAP(1h)
BLOQUES = [
    {"id": "ordeño_am", "inicio": ( 2, 15), "tipo": "ordeño", "dur_captura": DUR_PCAP_SERIAL_AM},
    # [SUSPENDIDO_OBJ4_28MAY] {"id": "normal_1",  "inicio": ( 4, 34), "tipo": "normal"},
    {"id": "normal_2",  "inicio": ( 7, 23), "tipo": "normal"},
    # [SUSPENDIDO_OBJ4_28MAY] {"id": "normal_3",  "inicio": (10, 12), "tipo": "normal"},
    {"id": "ordeño_pm", "inicio": (13, 00), "tipo": "ordeño", "dur_captura": DUR_PCAP_SERIAL_PM},
    # [SUSPENDIDO_OBJ4_28MAY] {"id": "normal_4",  "inicio": (15, 10), "tipo": "normal"},
    {"id": "normal_5",  "inicio": (17, 48), "tipo": "normal"},
    # [SUSPENDIDO_OBJ4_28MAY] {"id": "normal_6",  "inicio": (20, 37), "tipo": "normal"},
    {"id": "normal_7",  "inicio": (23, 26), "tipo": "normal"},
]


def carpeta_bloque(bloque_id, inicio_dt):
    """
    Construye el nombre de carpeta para un bloque.
    Ejemplo: ordeño_am_20260402_0225
    """
    fecha_hora = inicio_dt.strftime("%Y%m%d_%H%M")
    nombre = f"{bloque_id}_{fecha_hora}"
    return os.path.join(BASE_DIR, nombre)


def fases_para_tipo(tipo, dur_captura=None):
    """
    Devuelve la secuencia de fases para un bloque según su tipo.
    Bloque ORDEÑO:  baseline_inicio → pcap_serial(dur_captura) → baseline_fin
    Bloque NORMAL:  baseline_inicio → antena(1h) → pcap(1h)    → baseline_fin
    """
    if tipo == "ordeño":
        dur = dur_captura if dur_captura is not None else DUR_PCAP_SERIAL_AM
        return [
            {"id": "baseline_inicio", "label": "Baseline inicial",
             "mode": "4", "kind": "baseline", "planned_seconds": 0},
            {"id": "serial_antena_pcap", "label": "Serial + Antena UDP + PCAP",
             "mode": "5", "kind": "capture",  "planned_seconds": dur},
            {"id": "baseline_fin",    "label": "Baseline final",
             "mode": "4", "kind": "baseline", "planned_seconds": 0},
        ]
    else:
        # En bloque normal: Antena primero, PCAP después.
        return [
            {"id": "baseline_inicio", "label": "Baseline inicial",
             "mode": "4", "kind": "baseline", "planned_seconds": 0},
            {"id": "antena",          "label": "Antena UDP",
             "mode": "1", "kind": "capture",  "planned_seconds": DUR_ANTENA},
            {"id": "pcap",            "label": "PCAP completo",
             "mode": "3", "kind": "capture",  "planned_seconds": DUR_PCAP},
            {"id": "baseline_fin",    "label": "Baseline final",
             "mode": "4", "kind": "baseline", "planned_seconds": 0},
        ]


# ── Utilidades generales ──────────────────────────────────────────────────────
def ensure_dir(path):
    os.makedirs(path, exist_ok=True)


def now_local():
    return datetime.now()


def iso_now():
    return now_local().isoformat(timespec="seconds")


def log_event(event, **kw):
    ensure_dir(BASE_DIR)
    parts = [f"time={iso_now()}", f"event={event}"]
    parts += [f"{k}={v}" for k, v in kw.items()]
    with open(EVENT_LOG, "a", encoding="utf-8") as fh:
        fh.write(" ".join(parts) + "\n")


def load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None


def save_json(path, data):
    """Escritura atómica: usa .tmp + os.replace para sobrevivir cortes de luz."""
    ensure_dir(os.path.dirname(path))
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=True)
    os.replace(tmp, path)


def seconds_until(moment, now=None):
    now = now or now_local()
    return max(0, int((moment - now).total_seconds()))


# ── Sistema ───────────────────────────────────────────────────────────────────
def get_boot_id():
    try:
        with open("/proc/sys/kernel/random/boot_id", "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return "unknown"


def get_uptime_seconds():
    try:
        with open("/proc/uptime", "r", encoding="utf-8") as fh:
            return float(fh.read().split()[0])
    except (OSError, ValueError):
        return 0.0


# ── Red ───────────────────────────────────────────────────────────────────────
def get_default_gateway():
    try:
        out = subprocess.check_output(
            ["ip", "-4", "route", "show", "default"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""
    for line in out.splitlines():
        parts = line.split()
        if "via" in parts:
            return parts[parts.index("via") + 1]
    return ""


def get_interface_state():
    try:
        with open(f"/sys/class/net/{INTERFACE_NAME}/operstate",
                  "r", encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return "unknown"


def get_interface_ip():
    try:
        out = subprocess.check_output(
            ["ip", "-4", "-o", "addr", "show", "dev", INTERFACE_NAME],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return ""
    for line in out.splitlines():
        parts = line.split()
        if "inet" in parts:
            return parts[parts.index("inet") + 1].split("/")[0]
    return ""


def can_connect(host, port, timeout=2):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def network_snapshot():
    gw = get_default_gateway()
    return {
        "iface_state": get_interface_state(),
        "ip":          get_interface_ip(),
        "gateway":     gw,
        "gateway_ok":  bool(gw) and can_connect(gw, 53, timeout=1),
        "internet_ok": can_connect(PING_HOST, 53, timeout=2),
    }


def log_network_changes(prev, curr, bloque_id, fase_id):
    if prev is None:
        return
    changes = []
    for k in ["iface_state", "ip", "gateway", "gateway_ok", "internet_ok"]:
        if prev.get(k) != curr.get(k):
            changes.append(f"{k}:{prev.get(k)}->{curr.get(k)}")
    if changes:
        log_event("network_change", bloque=bloque_id,
                  fase=fase_id, changes="|".join(changes))


# ── Lógica de bloques ─────────────────────────────────────────────────────────
def bloque_actual(now=None):
    """
    Determina qué bloque del timeline corresponde a la hora actual.
    Devuelve el bloque y su ventana (inicio, fin como datetimes).
    Devuelve None si la hora actual cae en un período de descanso.
    """
    now = now or now_local()
    today = now.replace(second=0, microsecond=0)

    # Construir lista de (inicio_dt, fin_dt, bloque) para hoy y ayer
    ventanas = []
    for i, bloque in enumerate(BLOQUES):
        h, m = bloque["inicio"]
        inicio_dt = today.replace(hour=h, minute=m)

        # Calcular fin = inicio del siguiente bloque menos 1 minuto de descanso
        # El fin real es cuando arranca el siguiente bloque
        if i + 1 < len(BLOQUES):
            h_next, m_next = BLOQUES[i + 1]["inicio"]
            fin_dt = today.replace(hour=h_next, minute=m_next)
            if fin_dt <= inicio_dt:
                fin_dt += timedelta(days=1)
        else:
            # Último bloque del día: termina cuando arranca el primero del día siguiente
            h_first, m_first = BLOQUES[0]["inicio"]
            fin_dt = today.replace(hour=h_first, minute=m_first) + timedelta(days=1)

        ventanas.append((inicio_dt, fin_dt, bloque))

    # También considerar el último bloque del día anterior
    last = BLOQUES[-1]
    h, m = last["inicio"]
    inicio_ayer = (today - timedelta(days=1)).replace(hour=h, minute=m)
    h_first, m_first = BLOQUES[0]["inicio"]
    fin_ayer = today.replace(hour=h_first, minute=m_first)
    ventanas.append((inicio_ayer, fin_ayer, last))

    for inicio_dt, fin_dt, bloque in ventanas:
        if inicio_dt <= now < fin_dt:
            return bloque, inicio_dt, fin_dt

    return None, None, None


def es_inicio_de_bloque(now=None):
    """Devuelve True si la hora actual coincide con el inicio de algún bloque."""
    now = now or now_local()
    for bloque in BLOQUES:
        h, m = bloque["inicio"]
        if now.hour == h and now.minute == m:
            return True, bloque
    return False, None


# ── Estado persistente ────────────────────────────────────────────────────────
def build_state(bloque, inicio_dt, fin_dt, boot_id):
    fases = []
    for f in fases_para_tipo(bloque["tipo"], bloque.get("dur_captura")):
        fase = copy.deepcopy(f)
        fase.update({
            "status":           "pending",
            "attempts":         0,
            "executed_seconds": 0,
            "started_at":       None,
            "completed_at":     None,
        })
        fases.append(fase)

    return {
        "bloque_id":    bloque["id"],
        "bloque_tipo":  bloque["tipo"],
        "bloque_inicio": inicio_dt.isoformat(timespec="seconds"),
        "bloque_fin":    fin_dt.isoformat(timespec="seconds"),
        "status":        "pending",
        "boot_id":       boot_id,
        "last_heartbeat_at": iso_now(),
        "active_phase_id":   None,
        "fases":             fases,
        "recoveries":        [],
    }


def find_fase(state, fase_id):
    for f in state["fases"]:
        if f["id"] == fase_id:
            return f
    return None


def update_heartbeat(state, boot_id):
    state["boot_id"]           = boot_id
    state["last_heartbeat_at"] = iso_now()
    save_json(STATE_FILE, state)


def reset_if_needed(state, boot_id, bloque, inicio_dt):
    """Si había una fase corriendo cuando el sistema se cayó, la resetea."""
    if state is None:
        return None

    if state.get("bloque_id") != bloque["id"]:
        return None

    # Verificar que el bloque guardado corresponde a la misma ejecución del día
    saved_inicio = state.get("bloque_inicio", "")
    if saved_inicio != inicio_dt.isoformat(timespec="seconds"):
        return None

    active_id = state.get("active_phase_id")
    if not active_id:
        return state

    fase = find_fase(state, active_id)
    if not fase:
        return state

    recovery = {"fase_id": active_id, "recovered_at": iso_now()}

    if state.get("boot_id") != boot_id:
        recovery["reason"] = "reboot_detected"
        log_event("reboot_detected",
                  bloque=state["bloque_id"],
                  fase=active_id,
                  prev_boot=state.get("boot_id"),
                  curr_boot=boot_id,
                  uptime=round(get_uptime_seconds(), 1))
    else:
        recovery["reason"] = "scheduler_recovered"
        log_event("scheduler_recovered",
                  bloque=state["bloque_id"], fase=active_id)

    state.setdefault("recoveries", []).append(recovery)
    fase["status"]           = "pending"
    state["active_phase_id"] = None
    state["status"]          = "pending"
    state["boot_id"]         = boot_id
    state["last_heartbeat_at"] = iso_now()
    return state


# ── Lock de instancia única ───────────────────────────────────────────────────
@contextmanager
def scheduler_lock():
    ensure_dir(BASE_DIR)
    with open(LOCK_FILE, "a+", encoding="utf-8") as fh:
        if fcntl is None:
            yield True
            return
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fh.seek(0); fh.truncate()
            fh.write(str(os.getpid()))
            fh.flush()
            yield True
        except BlockingIOError:
            yield False
        finally:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
            except OSError:
                pass


# ── Ejecución de fases ────────────────────────────────────────────────────────
def run_fase(state, fase, bloque_id, bloque_tipo, fin_dt, boot_id, bloque_dir=None):
    """
    Lanza FincaDiag para una fase y supervisa su ejecución.
    Escribe heartbeat cada HEARTBEAT_SECONDS.
    Monitorea la red cada NETWORK_CHECK_SECONDS durante capturas.
    Devuelve True si la fase completó correctamente.
    """
    remaining = seconds_until(fin_dt)
    if remaining <= 0:
        log_event("bloque_sin_tiempo", bloque=bloque_id, fase=fase["id"])
        return False

    # Calcular tiempo objetivo para esta fase
    if fase["kind"] == "baseline":
        target_seconds = 0
        timeout = min(remaining, BASELINE_TIMEOUT_SECONDS)
    else:
        already_done   = fase["executed_seconds"]
        pending        = max(0, fase["planned_seconds"] - already_done)
        target_seconds = min(pending, remaining)
        timeout        = target_seconds + CAPTURE_GRACE_SECONDS
        if target_seconds <= 0:
            state["status"] = "incomplete"
            update_heartbeat(state, boot_id)
            return False

    # Construir comando
    cmd = [sys.executable, FINCADIAG, "-m", fase["mode"]]
    if fase["kind"] == "capture":
        cmd.extend(["-t", str(target_seconds)])

    # Actualizar estado antes de lanzar
    fase["attempts"]       += 1
    fase["status"]          = "running"
    fase["started_at"]      = iso_now()
    state["status"]         = "running"
    state["active_phase_id"] = fase["id"]
    update_heartbeat(state, boot_id)

    log_event("fase_iniciada",
              bloque=bloque_id,
              tipo=bloque_tipo,
              fase=fase["id"],
              label=fase["label"],
              target_seconds=target_seconds,
              cmd=" ".join(cmd))

    # Pasar la carpeta del bloque como BASE_DIR al subproceso
    # FincaDiag crea Captura_* y Baseline_* dentro de esa carpeta
    env = os.environ.copy()
    if bloque_dir:
        env["FINCA_BASE_DIR"] = bloque_dir
    process         = subprocess.Popen(cmd, cwd=SCRIPT_DIR, env=env)
    t0              = time.monotonic()
    next_heartbeat  = t0 + HEARTBEAT_SECONDS
    next_net_check  = t0
    last_net        = network_snapshot() if fase["kind"] == "capture" else None
    executed_before = fase["executed_seconds"]
    forced_stop     = False

    while True:
        rc      = process.poll()
        elapsed = int(time.monotonic() - t0)
        progress = min(target_seconds, elapsed)

        if fase["kind"] == "capture":
            fase["executed_seconds"] = min(
                fase["planned_seconds"], executed_before + progress
            )

        if rc is not None:
            break

        if elapsed >= timeout:
            forced_stop = True
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            break

        mono = time.monotonic()
        if mono >= next_heartbeat:
            update_heartbeat(state, boot_id)
            next_heartbeat = mono + HEARTBEAT_SECONDS

        if fase["kind"] == "capture" and mono >= next_net_check:
            curr_net = network_snapshot()
            log_network_changes(last_net, curr_net, bloque_id, fase["id"])
            last_net       = curr_net
            next_net_check = mono + NETWORK_CHECK_SECONDS

        time.sleep(1)

    # Actualizar segundos ejecutados con el tiempo final real
    final_elapsed = int(time.monotonic() - t0)
    if fase["kind"] == "capture":
        fase["executed_seconds"] = min(
            fase["planned_seconds"],
            executed_before + min(target_seconds, final_elapsed),
        )

    state["active_phase_id"]   = None
    state["boot_id"]           = boot_id
    state["last_heartbeat_at"] = iso_now()
    exit_code = process.returncode

    # Evaluar resultado
    if fase["kind"] == "baseline":
        if exit_code == 0 and not forced_stop:
            fase["status"]       = "completed"
            fase["completed_at"] = iso_now()
            log_event("fase_completada", bloque=bloque_id, fase=fase["id"])
            update_heartbeat(state, boot_id)
            return True
        fase["status"]  = "pending"
        state["status"] = "incomplete"
        log_event("fase_interrumpida", bloque=bloque_id, fase=fase["id"],
                  exit_code=exit_code, forced_stop=forced_stop)
        update_heartbeat(state, boot_id)
        return False

    # Fase de captura
    completed = fase["executed_seconds"] >= fase["planned_seconds"]
    if completed:
        fase["status"]       = "completed"
        fase["completed_at"] = iso_now()
        log_event("fase_completada", bloque=bloque_id, fase=fase["id"],
                  executed_seconds=fase["executed_seconds"])
        update_heartbeat(state, boot_id)
        return True

    fase["status"]  = "pending"
    state["status"] = "incomplete" if forced_stop else "pending"
    log_event("fase_parcial", bloque=bloque_id, fase=fase["id"],
              executed_seconds=fase["executed_seconds"],
              planned_seconds=fase["planned_seconds"],
              exit_code=exit_code, forced_stop=forced_stop)
    update_heartbeat(state, boot_id)
    return False


# ── Bucle principal ───────────────────────────────────────────────────────────
def run_scheduler():
    ensure_dir(BASE_DIR)

    if not os.path.exists(FINCADIAG):
        raise FileNotFoundError(f"No se encontró FincaDiag.py en {FINCADIAG}")

    now     = now_local()
    boot_id = get_boot_id()

    # Determinar si estamos dentro de un bloque activo
    bloque, inicio_dt, fin_dt = bloque_actual(now)

    if bloque is None:
        # Período de descanso — no hacer nada
        log_event("descanso", hora=now.strftime("%H:%M"))
        return

    # Cargar o crear estado
    state = load_json(STATE_FILE)
    state = reset_if_needed(state, boot_id, bloque, inicio_dt)

    if state is None:
        # Primera ejecución del bloque: arrancar siempre que haya tiempo restante.
        # No importa cuántos minutos tarde llegó el Scheduler — si el bloque
        # todavía no terminó, se arranca y se ejecuta lo que alcance.
        minutos_desde_inicio = int((now - inicio_dt).total_seconds() / 60)
        minutos_restantes    = int((fin_dt - now).total_seconds() / 60)
        if minutos_restantes <= 2:
            log_event("bloque_sin_tiempo_suficiente",
                      bloque=bloque["id"],
                      minutos_tarde=minutos_desde_inicio,
                      minutos_restantes=minutos_restantes)
            return
        state = build_state(bloque, inicio_dt, fin_dt, boot_id)
        save_json(STATE_FILE, state)
        log_event("bloque_iniciado",
                  bloque=bloque["id"],
                  tipo=bloque["tipo"],
                  minutos_tarde=minutos_desde_inicio,
                  fin=fin_dt.isoformat(timespec="seconds"))
    else:
        update_heartbeat(state, boot_id)

    if state.get("status") == "completed":
        log_event("bloque_ya_completado", bloque=bloque["id"])
        return

    # Crear carpeta del bloque donde se guardarán todos los archivos
    bloque_out_dir = carpeta_bloque(bloque["id"], inicio_dt)
    ensure_dir(bloque_out_dir)
    log_event("carpeta_bloque_creada",
              bloque=bloque["id"], carpeta=bloque_out_dir)

    # Ejecutar fases pendientes en orden
    for fase in state["fases"]:
        if fase["status"] == "completed":
            continue

        if seconds_until(fin_dt) <= 0:
            state["status"] = "incomplete"
            update_heartbeat(state, boot_id)
            log_event("bloque_tiempo_agotado", bloque=bloque["id"])
            return

        ok = run_fase(state, fase, bloque["id"], bloque["tipo"],
                      fin_dt, boot_id, bloque_dir=bloque_out_dir)
        if not ok:
            return

    # Todas las fases completadas
    all_done = all(f["status"] == "completed" for f in state["fases"])
    state["status"] = "completed" if all_done else "incomplete"
    update_heartbeat(state, boot_id)
    log_event("bloque_finalizado",
              bloque=bloque["id"], status=state["status"])


def main():
    with scheduler_lock() as acquired:
        if not acquired:
            log_event("scheduler_bloqueado")
            return
        run_scheduler()


if __name__ == "__main__":
    main()
