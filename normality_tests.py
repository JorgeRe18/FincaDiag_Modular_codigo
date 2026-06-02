"""
Pruebas de normalidad (Shapiro-Wilk) sobre las tres metricas del Objetivo 4:
  - eta (eficiencia de extraccion)
  - PLR (packet loss rate)
  - MTTR (mean time to recovery)

Para cada metrica se aplica Shapiro-Wilk a los grupos pre y post (cuando aplica).
Si p < 0.05 -> rechaza normalidad -> usar test no parametrico (Mann-Whitney U).
Si p >= 0.05 -> no rechaza normalidad -> puede usarse t-test.

Salida: tabla resumen + recomendacion automatica de contraste estadistico.
"""
import json
import os
from pathlib import Path
import numpy as np
from scipy import stats
import pandas as pd

BASE = Path(os.environ.get("FINCADIAG_BASE", Path(__file__).resolve().parent))
PROCESSED = BASE / 'data' / 'processed' / 'visits'
POST_START = (2026, 5, 11)


def parse_visit_date(name: str):
    parts = name.replace('Visita_', '').split('_')
    try:
        return (int(parts[2]), int(parts[1]), int(parts[0]))
    except Exception:
        return (0, 0, 0)


def load_etas():
    """Carga eta_extraccion de todas las sesiones con serial>0, separadas por fase."""
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
            if not s.is_dir() or s.name.startswith('BASELINE_ONLY') or 'Captura_' not in s.name:
                continue
            corr_path = s / 'correlation_summary.json'
            if not corr_path.exists():
                continue
            try:
                with open(corr_path) as f:
                    corr = json.load(f)
                if corr.get('serial_events', 0) == 0:
                    continue
                eta = corr.get('eta_extraccion')
                if eta is None:
                    continue
                target = post if v_date >= POST_START else pre
                target.append(float(eta))
            except Exception:
                continue
    return pre, post


def load_plr():
    """Carga PLR desde plr_results.json (generado por compute_plr.py)."""
    plr_file = BASE / 'plr_results.json'
    if not plr_file.exists():
        return [], []
    with open(plr_file) as f:
        data = json.load(f)
    pre = [r['plr'] for r in data.get('pre', [])]
    post = [r['plr'] for r in data.get('post', [])]
    return pre, post


def load_mttr():
    """Carga MTTR desde mttr_results.csv (generado por mttr_stress_pi.sh)."""
    mttr_file = BASE / 'mttr_results.csv'
    if not mttr_file.exists():
        return []
    try:
        df = pd.read_csv(mttr_file)
        df_pass = df[df['resultado'] == 'PASS']
        return df_pass['t_recovery_s'].astype(float).tolist()
    except Exception:
        return []


def shapiro_report(name: str, data: list, alpha: float = 0.05):
    """Aplica Shapiro-Wilk y reporta."""
    n = len(data)
    if n < 3:
        print(f"  {name}: n={n} insuficiente (minimo 3)")
        return None
    if n > 5000:
        # Shapiro no se recomienda para n>5000
        data = list(np.random.choice(data, 5000, replace=False))
    stat, p = stats.shapiro(data)
    es_normal = p >= alpha
    arr = np.array(data)
    print(f"  {name}: n={n}, media={arr.mean():.3f}, mediana={np.median(arr):.3f}, "
          f"std={arr.std(ddof=1):.3f}")
    print(f"    Shapiro-Wilk: W={stat:.4f}, p={p:.4f}  -> "
          f"{'NORMAL (no rechaza H0)' if es_normal else 'NO NORMAL (rechaza H0)'}")
    return {'n': n, 'W': stat, 'p': p, 'normal': es_normal}


def recommend_test(pre_normal: bool, post_normal: bool):
    if pre_normal and post_normal:
        return 't-test de Student (parametrico, dos muestras independientes)'
    return 'Mann-Whitney U (no parametrico, dos muestras independientes)'


def main():
    alpha = 0.05
    results = {}

    print("=" * 70)
    print("PRUEBAS DE NORMALIDAD (Shapiro-Wilk) - OBJETIVO 4")
    print("=" * 70)
    print(f"Hipotesis nula H0: la muestra proviene de una distribucion normal.")
    print(f"Nivel de significancia alpha = {alpha}")
    print(f"Si p < alpha -> rechaza H0 -> usar test no parametrico.")
    print()

    # 1. eta
    print("--- 1. Eficiencia de extraccion (eta) ---")
    eta_pre, eta_post = load_etas()
    eta_pre_res = shapiro_report('eta PRE', eta_pre, alpha)
    eta_post_res = shapiro_report('eta POST', eta_post, alpha)
    if eta_pre_res and eta_post_res:
        rec = recommend_test(eta_pre_res['normal'], eta_post_res['normal'])
        print(f"  RECOMENDACION: {rec}")
        results['eta'] = {'pre': eta_pre_res, 'post': eta_post_res, 'recomendacion': rec}
    print()

    # 2. PLR
    print("--- 2. Packet Loss Rate (PLR) ---")
    plr_pre, plr_post = load_plr()
    if not plr_pre and not plr_post:
        print("  (sin datos: corre compute_plr.py primero)")
    else:
        plr_pre_res = shapiro_report('PLR PRE', plr_pre, alpha)
        plr_post_res = shapiro_report('PLR POST', plr_post, alpha)
        if plr_pre_res and plr_post_res:
            rec = recommend_test(plr_pre_res['normal'], plr_post_res['normal'])
            print(f"  RECOMENDACION: {rec}")
            results['plr'] = {'pre': plr_pre_res, 'post': plr_post_res, 'recomendacion': rec}
    print()

    # 3. MTTR (una sola muestra, sin pre)
    print("--- 3. Mean Time To Recovery (MTTR) ---")
    mttr = load_mttr()
    if not mttr:
        print("  (sin datos: corre mttr_stress_pi.sh en la Pi primero)")
    else:
        mttr_res = shapiro_report('MTTR (muestra unica)', mttr, alpha)
        if mttr_res:
            print(f"  Nota: MTTR es muestra unica (no hay pre-intervencion). "
                  f"Solo se reporta distribucion.")
            results['mttr'] = {'sample': mttr_res}
    print()

    # Guardar resumen
    out = BASE / 'normality_results.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Resultados guardados en {out}")


if __name__ == '__main__':
    main()
