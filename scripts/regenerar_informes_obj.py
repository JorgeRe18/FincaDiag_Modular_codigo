"""
Regenera los informes por sesion (technical_report.txt + human_report.txt)
leyendo los JSON ya procesados en data/processed/visits/  -- NO re-corre el motor.

Uso:
    python scripts/regenerar_informes_obj.py --objetivo 3
    python scripts/regenerar_informes_obj.py --objetivo 4
    python scripts/regenerar_informes_obj.py --objetivo 1   # restaurar default
"""
import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from fincadiag.config import DEFAULT_WINDOW_MS
from fincadiag.export.report_builder import generate_reports

PROCESSED_VISITS = PROJECT_ROOT / "data" / "processed" / "visits"
REPORTS_VISITS = PROJECT_ROOT / "reports" / "visits"

_REQUIRED = [
    "baseline_summary.json",
    "serial_summary.json",
    "antenna_udp_summary.json",
    "pcap_summary.json",
    "correlation_summary.json",
    "alerts.json",
]


def load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def discover_sessions() -> list[Path]:
    """Devuelve todas las carpetas de sesion que tengan baseline_summary.json."""
    sessions = []
    for visit_dir in sorted(PROCESSED_VISITS.iterdir()):
        sesiones_dir = visit_dir / "sesiones"
        if not sesiones_dir.is_dir():
            continue
        for sess_dir in sorted(sesiones_dir.iterdir()):
            if (sess_dir / "baseline_summary.json").exists():
                sessions.append(sess_dir)
    return sessions


def main():
    ap = argparse.ArgumentParser(description="Regenera informes por sesion sin re-correr el motor")
    ap.add_argument("--objetivo", type=int, choices=[1, 3, 4], default=3,
                    help="Objetivo del TFG para enmarcar el informe (default: 3)")
    ap.add_argument("--visit", default=None,
                    help="Nombre de visita especifica (p.ej. Visita_06_04_2026_PM). Si no se da, procesa todas.")
    args = ap.parse_args()

    sessions = discover_sessions()
    if args.visit:
        sessions = [s for s in sessions if args.visit in str(s)]
    if not sessions:
        print("[ERROR] No se encontraron sesiones procesadas.")
        sys.exit(1)

    print(f"[INFO] Sesiones encontradas: {len(sessions)}")
    print(f"[INFO] Objetivo: {args.objetivo}")
    print()

    ok = 0
    errors = 0
    for sess_dir in sessions:
        sample_name = sess_dir.name
        visit_name = sess_dir.parent.parent.name

        baseline = load(sess_dir / "baseline_summary.json")
        serial = load(sess_dir / "serial_summary.json")
        antenna_udp = load(sess_dir / "antenna_udp_summary.json")
        pcap = load(sess_dir / "pcap_summary.json")
        correlation = load(sess_dir / "correlation_summary.json")
        field_validation = load(sess_dir / "field_validation_summary.json")
        alerts = load(sess_dir / "alerts.json")
        gw_exp = load(sess_dir / "gateway_expectations.json")

        operation_mode = gw_exp.get("operation_mode", baseline.get("operation_mode", "indeterminado"))
        block_label = gw_exp.get("block_label", "")

        report_dir = REPORTS_VISITS / visit_name / "por_hora"
        report_dir.mkdir(parents=True, exist_ok=True)

        try:
            tech_path, human_path = generate_reports(
                sample_name=sample_name,
                baseline=baseline,
                serial=serial,
                antenna_udp=antenna_udp,
                pcap=pcap,
                correlation=correlation,
                alerts=alerts,
                window_ms=DEFAULT_WINDOW_MS,
                output_dir=report_dir,
                etl_path="",
                operation_mode=operation_mode,
                block_label=block_label,
                field_validation=field_validation,
                objetivo=args.objetivo,
            )
            print(f"  [OK] {visit_name} / {sample_name}")
            ok += 1
        except Exception as exc:
            print(f"  [ERROR] {sample_name}: {exc}")
            errors += 1

    print()
    print(f"Listo: {ok} informes regenerados, {errors} errores.")
    print(f"Ruta de informes: {REPORTS_VISITS}")

    print()
    print("Parcheando resumenes globales...")
    patch_global_summaries(args.objetivo)


_GLOBAL_PATCHES = {
    1: {
        "OBJETIVO 3: PASARELA IoT (GATEWAY MQTT/TLS)":   "OBJETIVO 1: CARACTERIZACION FORENSE DEL SISTEMA",
        "OBJETIVO 4: RESILIENCIA DEL GATEWAY":            "OBJETIVO 1: CARACTERIZACION FORENSE DEL SISTEMA",
        "PREPARACION PARA GATEWAY (OBJETIVO 3)":         "CARACTERIZACION FORENSE (OBJETIVO 1)",
        "CONTEXTO DE RED PARA RESILIENCIA (OBJETIVO 4)": "CARACTERIZACION FORENSE (OBJETIVO 1)",
        "CONCLUSIONES OBJETIVO 3":                       "CONCLUSIONES OBJETIVO 1",
        "CONCLUSIONES OBJETIVO 4":                       "CONCLUSIONES OBJETIVO 1",
    },
    3: {
        "OBJETIVO 1: CARACTERIZACION FORENSE DEL SISTEMA":  "OBJETIVO 3: PASARELA IoT (GATEWAY MQTT/TLS)",
        "OBJETIVO 4: RESILIENCIA DEL GATEWAY":              "OBJETIVO 3: PASARELA IoT (GATEWAY MQTT/TLS)",
        "CARACTERIZACION FORENSE (OBJETIVO 1)":             "PREPARACION PARA GATEWAY (OBJETIVO 3)",
        "CONTEXTO DE RED PARA RESILIENCIA (OBJETIVO 4)":    "PREPARACION PARA GATEWAY (OBJETIVO 3)",
        "CONCLUSIONES OBJETIVO 1":                          "CONCLUSIONES OBJETIVO 3",
        "CONCLUSIONES OBJETIVO 4":                          "CONCLUSIONES OBJETIVO 3",
        "caracterizacion del Objetivo 1":                   "preparacion gateway del Objetivo 3",
        "Lectura de caracterizacion para el Objetivo 1":    "Lectura de preparacion para el Objetivo 3",
        "Proposito: caracterizacion forense y linea base del Objetivo 1.": "Proposito: preparacion de datos para pasarela IoT (Objetivo 3).",
        "Capacidades defendibles del Objetivo 1":           "Capacidades defendibles del Objetivo 3",
        "Perfiles por fase para el Objetivo 1":             "Perfiles por fase para el Objetivo 3",
        "Capacidades validadas del Objetivo 1":             "Capacidades validadas del Objetivo 3",
    },
    4: {
        "OBJETIVO 1: CARACTERIZACION FORENSE DEL SISTEMA":  "OBJETIVO 4: RESILIENCIA DEL GATEWAY",
        "OBJETIVO 3: PASARELA IoT (GATEWAY MQTT/TLS)":      "OBJETIVO 4: RESILIENCIA DEL GATEWAY",
        "CARACTERIZACION FORENSE (OBJETIVO 1)":             "CONTEXTO DE RED PARA RESILIENCIA (OBJETIVO 4)",
        "PREPARACION PARA GATEWAY (OBJETIVO 3)":            "CONTEXTO DE RED PARA RESILIENCIA (OBJETIVO 4)",
        "CONCLUSIONES OBJETIVO 1":                          "CONCLUSIONES OBJETIVO 4",
        "CONCLUSIONES OBJETIVO 3":                          "CONCLUSIONES OBJETIVO 4",
        "caracterizacion del Objetivo 1":                   "contexto de resiliencia del Objetivo 4",
        "Lectura de caracterizacion para el Objetivo 1":    "Lectura de contexto para el Objetivo 4",
        "Proposito: caracterizacion forense y linea base del Objetivo 1.": "Proposito: contexto de red para pruebas de resiliencia (Objetivo 4).",
        "Capacidades defendibles del Objetivo 1":           "Capacidades defendibles del Objetivo 4",
        "Perfiles por fase para el Objetivo 1":             "Perfiles por fase para el Objetivo 4",
        "Capacidades validadas del Objetivo 1":             "Capacidades validadas del Objetivo 4",
    },
}


def patch_global_summaries(objetivo: int) -> None:
    """Parchea los archivos de resumen global existentes sin re-generar desde cero."""
    run_name = f"Etapa_Obj{objetivo}" if objetivo in (3, 4) else None
    if not run_name:
        print("[INFO] Objetivo 1: los resumenes globales no necesitan parche (son el default).")
        return

    reports_global = PROJECT_ROOT / "reports" / "global" / "resumen_arbol" / run_name
    patches = _GLOBAL_PATCHES.get(objetivo, {})

    txt_files = list(reports_global.glob("*.txt")) if reports_global.exists() else []
    if not txt_files:
        print(f"[WARN] No se encontraron archivos .txt en {reports_global}")
        print(f"       (El resumen global se generara la proxima vez que corras el motor con --objetivo {objetivo})")
        return

    for txt_path in txt_files:
        content = txt_path.read_text(encoding="utf-8")
        modified = content
        for old, new in patches.items():
            modified = modified.replace(old, new)
        if modified != content:
            txt_path.write_text(modified, encoding="utf-8")
            print(f"  [OK] Parcheado: {txt_path.name}")
        else:
            print(f"  [--] Sin cambios: {txt_path.name}")


if __name__ == "__main__":
    main()
