"""
Análisis de sensibilidad de la ventana de correlación: 250 ms vs 300 ms.
No reprocesa desde raw — reutiliza los matches ya calculados en correlation_summary.json.
Solo aplica para sesiones post-intervención (11-16 mayo) con serial_events > 0.
"""
import json
from pathlib import Path

PROCESSED = Path('data/processed/visits')

# Fecha de inicio de la fase post-intervención (gateway activo)
POST_INTERVENTION_START = (2026, 5, 11)  # año, mes, día


def parse_visit_date(visit_name: str):
    """Extrae (año, mes, día) del nombre Visita_DD_MM_YYYY."""
    parts = visit_name.replace('Visita_', '').split('_')
    try:
        return (int(parts[2]), int(parts[1]), int(parts[0]))
    except Exception:
        return (0, 0, 0)


def discover_post_sessions(base: Path) -> list[tuple[str, Path]]:
    """Descubre todas las sesiones de ordeño completo post-intervención, ordenadas por fecha."""
    sessions = []
    for visit_dir in sorted(base.iterdir()):
        if not visit_dir.is_dir() or not visit_dir.name.startswith('Visita_'):
            continue
        if parse_visit_date(visit_dir.name) < POST_INTERVENTION_START:
            continue
        sesiones_dir = visit_dir / 'sesiones'
        if not sesiones_dir.exists():
            continue
        for s in sorted(sesiones_dir.iterdir()):
            if not s.is_dir():
                continue
            name = s.name
            # Solo sesiones de captura completa (TOMA_*_Captura_*), no BASELINE_ONLY
            if name.startswith('BASELINE_ONLY') or 'Captura_' not in name:
                continue
            corr_path = s / 'correlation_summary.json'
            if corr_path.exists():
                try:
                    with open(corr_path) as f:
                        corr = json.load(f)
                    if corr.get('serial_events', 0) > 0 and corr.get('matches'):
                        sessions.append((visit_dir.name, s))
                except Exception:
                    pass
    return sessions


def simulate_window(matches: list, window_ms: int) -> tuple[int, float, float]:
    matched = [m for m in matches if m['abs_delta_ms'] <= window_ms]
    serial_events = len(matches)  # one candidate per serial event
    n_matched = len(matched)
    eta = round(n_matched / serial_events * 100, 2) if serial_events else 0.0
    desfase = round(sum(m['abs_delta_ms'] for m in matched) / n_matched, 1) if matched else 0.0
    return n_matched, eta, desfase


sessions_found = discover_post_sessions(PROCESSED)
print(f"Sesiones post-intervención con correlación encontradas: {len(sessions_found)}\n")

print(f"{'Sesion':<30} {'Serial':>6} {'W250 eta%':>8} {'W250 m':>6} {'W300 eta%':>8} {'W300 m':>6} {'Deta':>7} {'Nota'}")
print('-' * 100)

etas_250, etas_300 = [], []
gains = []

for visit_name, sp in sessions_found:
    corr_path = sp / 'correlation_summary.json'
    with open(corr_path) as f:
        corr = json.load(f)

    serial_n = corr.get('serial_events', 0)
    matches   = corr.get('matches', [])

    toma = 'AM' if 'AM__2AM' in sp.name else 'PM'
    date = visit_name.replace('Visita_','').replace('_2026','').replace('_05_','/')
    label = f"{date} {toma}"

    if serial_n == 0 or not matches:
        print(f"  {label:<30} {'0':>6} {'—':>8} {'—':>6} {'—':>8} {'—':>6} {'—':>7} sin serial/corr")
        continue

    m250, eta250, d250 = simulate_window(matches, 250)
    m300, eta300, d300 = simulate_window(matches, 300)
    delta_eta = round(eta300 - eta250, 2)
    nota = '<- MEJORA' if delta_eta > 0 else ('eta=0 ambas' if eta250 == 0 and eta300 == 0 else '')

    print(f"  {label:<30} {serial_n:>6} {eta250:>8.1f} {m250:>6} {eta300:>8.1f} {m300:>6} {delta_eta:>+7.1f} {nota}")

    etas_250.append(eta250)
    etas_300.append(eta300)
    if delta_eta > 0:
        gains.append((label, eta250, eta300, delta_eta))

print('-' * 100)
n = len(etas_250)
media_250 = round(sum(etas_250)/n, 2) if n else 0
media_300 = round(sum(etas_300)/n, 2) if n else 0
print(f"\n  {'PROMEDIO (n='+str(n)+')':<30} {'':>6} {media_250:>8.2f} {'':>6} {media_300:>8.2f} {'':>6} {media_300-media_250:>+7.2f}")

print(f"\n  Sesiones con mejora al ampliar a 300 ms: {len(gains)}/{n}")
for label, e250, e300, d in gains:
    print(f"    {label}: {e250:.1f}% → {e300:.1f}% (+{d:.1f} pp)")

print(f"\n  Resumen para Cap 6:")
print(f"    eta media (W=250 ms): {media_250:.2f}%")
print(f"    eta media (W=300 ms): {media_300:.2f}%")
print(f"    Ganancia sensibilidad: +{media_300-media_250:.2f} pp")
