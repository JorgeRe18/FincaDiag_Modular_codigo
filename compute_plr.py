"""
Cálculo de Packet Loss Rate (PLR) para Objetivo 4.

Método:
  - Para cada sesión con captura de ordeño completa, se lee
    pcap_telemetry_udp_events.csv (telemetría SCR puerto 6001).
  - Se computan los inter-arrivals (Δt entre paquetes consecutivos
    de la misma fuente: src_ip, src_port).
  - Se estima la cadencia nominal como la mediana de los Δt
    (robusta a gaps).
  - Para cada gap > 1.5 × nominal, se cuentan los slots perdidos como
    round(gap / nominal) - 1.
  - PLR = perdidos / (recibidos + perdidos) × 100.

Pre-intervención: visitas con fecha < 11/05/2026 (gateway no activo).
Post-intervención: visitas con fecha >= 11/05/2026.

Salida: tabla y test Mann-Whitney U unilateral (H1: PLR_post < PLR_pre).
"""
from pathlib import Path
import json
import pandas as pd
import numpy as np
from scipy import stats

PROCESSED = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits')
POST_START = (2026, 5, 11)  # (anio, mes, dia)


def parse_visit_date(name: str):
    parts = name.replace('Visita_', '').split('_')
    try:
        return (int(parts[2]), int(parts[1]), int(parts[0]))
    except Exception:
        return (0, 0, 0)


def session_plr(session_dir: Path):
    """Calcula PLR de una sesion. Devuelve (plr_pct, n_recibidos, n_perdidos, nominal_ms)."""
    csv_path = session_dir / 'pcap_telemetry_udp_events.csv'
    if not csv_path.exists() or csv_path.stat().st_size == 0:
        return None

    try:
        df = pd.read_csv(csv_path, usecols=['day_ms', 'src_ip', 'src_port'])
    except Exception:
        return None

    if len(df) < 10:
        return None

    df = df.sort_values('day_ms').reset_index(drop=True)
    losses_total = 0
    received_total = 0
    nominal_ms_list = []

    # Procesar por flujo (cada (src_ip, src_port) es un collar/sensor distinto)
    for (sip, sport), g in df.groupby(['src_ip', 'src_port']):
        if len(g) < 5:
            continue
        deltas = np.diff(g['day_ms'].values)
        deltas = deltas[deltas > 0]  # filtrar duplicados
        if len(deltas) < 5:
            continue

        nominal = float(np.median(deltas))
        if nominal <= 0:
            continue

        # Slots perdidos: para cada delta > 1.5 * nominal, contar slots
        gaps = deltas[deltas > 1.5 * nominal]
        lost_slots = int(np.sum(np.round(gaps / nominal) - 1))

        losses_total += lost_slots
        received_total += len(g)
        nominal_ms_list.append(nominal)

    if received_total == 0:
        return None

    expected = received_total + losses_total
    plr_pct = losses_total / expected * 100 if expected > 0 else 0.0
    nominal_ms = float(np.median(nominal_ms_list)) if nominal_ms_list else 0.0
    return plr_pct, received_total, losses_total, nominal_ms


def discover_sessions():
    pre, post = [], []
    for visit in sorted(PROCESSED.iterdir()):
        if not visit.is_dir() or not visit.name.startswith('Visita_'):
            continue
        v_date = parse_visit_date(visit.name)
        if v_date == (0, 0, 0):
            continue
        sesiones = visit / 'sesiones'
        if not sesiones.exists():
            continue
        for s in sorted(sesiones.iterdir()):
            if not s.is_dir():
                continue
            # Solo sesiones de captura completa (no baseline-only)
            if s.name.startswith('BASELINE_ONLY') or 'Captura_' not in s.name:
                continue
            target = post if v_date >= POST_START else pre
            target.append((visit.name, s))
    return pre, post


def summarize(rows, label):
    print(f"\n=== {label} (n={len(rows)}) ===")
    if not rows:
        print("  (sin sesiones)")
        return []

    plrs = [r['plr'] for r in rows]
    print(f"  Media PLR:    {np.mean(plrs):.3f}%")
    print(f"  Mediana PLR:  {np.median(plrs):.3f}%")
    print(f"  Min - Max:    {np.min(plrs):.3f}% - {np.max(plrs):.3f}%")
    print(f"  Desv. est.:   {np.std(plrs, ddof=1):.3f}%")
    return plrs


def main():
    pre, post = discover_sessions()
    print(f"Sesiones pre-intervencion: {len(pre)}")
    print(f"Sesiones post-intervencion: {len(post)}")

    pre_rows, post_rows = [], []

    for label, lst, dest in [('PRE', pre, pre_rows), ('POST', post, post_rows)]:
        for visit_name, s in lst:
            res = session_plr(s)
            if res is None:
                continue
            plr, recv, lost, nominal = res
            dest.append({
                'visit': visit_name,
                'session': s.name,
                'plr': plr,
                'recibidos': recv,
                'perdidos': lost,
                'nominal_ms': nominal
            })

    # Detalle por sesion (top y bottom)
    print("\n--- Detalle PRE (primeras 10) ---")
    for r in pre_rows[:10]:
        print(f"  {r['visit']:<25} {r['session'][:35]:<35} PLR={r['plr']:>6.3f}%  recv={r['recibidos']:>6}  lost={r['perdidos']:>5}  nominal={r['nominal_ms']:.0f}ms")

    print("\n--- Detalle POST (todas) ---")
    for r in post_rows:
        print(f"  {r['visit']:<25} {r['session'][:35]:<35} PLR={r['plr']:>6.3f}%  recv={r['recibidos']:>6}  lost={r['perdidos']:>5}  nominal={r['nominal_ms']:.0f}ms")

    pre_plr = summarize(pre_rows, 'PRE-INTERVENCION')
    post_plr = summarize(post_rows, 'POST-INTERVENCION')

    # Mann-Whitney U unilateral (H1: post < pre, esto es, PLR baja con gateway)
    if len(pre_plr) >= 5 and len(post_plr) >= 5:
        u, p = stats.mannwhitneyu(post_plr, pre_plr, alternative='less')
        n = len(pre_plr) + len(post_plr)
        z = stats.norm.ppf(p) if 0 < p < 1 else 0.0
        r_eff = abs(z) / np.sqrt(n)
        print(f"\n=== Mann-Whitney U (H1: PLR_post < PLR_pre) ===")
        print(f"  U = {u:.2f}")
        print(f"  p = {p:.4f}")
        print(f"  Tamano efecto r = {r_eff:.3f}")
        print(f"  Significativo a alpha=0.05: {'SI' if p < 0.05 else 'NO'}")

    # Guardar JSON
    out = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\plr_results.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump({
            'pre': pre_rows,
            'post': post_rows,
            'summary': {
                'pre_n': len(pre_rows),
                'post_n': len(post_rows),
                'pre_mean_plr': float(np.mean(pre_plr)) if pre_plr else None,
                'pre_median_plr': float(np.median(pre_plr)) if pre_plr else None,
                'post_mean_plr': float(np.mean(post_plr)) if post_plr else None,
                'post_median_plr': float(np.median(post_plr)) if post_plr else None,
            }
        }, f, indent=2, ensure_ascii=False)
    print(f"\nResultados guardados en {out}")


if __name__ == '__main__':
    main()
