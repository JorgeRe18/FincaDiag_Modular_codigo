"""Conteo limpio de todas las sesiones TOMA 11-28 mayo con correlation_summary."""
import json
from pathlib import Path

BASE = Path('C:/Users/jorge/OneDrive/Documentos/FincaDiag_Modular')
DATA_DIR = BASE / 'data' / 'processed' / 'visits'

all_sessions = []
for visit_dir in sorted(DATA_DIR.glob('Visita_*_05_2026')):
    day = int(visit_dir.name.split('_')[1])
    if day < 11 or day > 28:
        continue
    for ses_dir in sorted(visit_dir.glob('sesiones/*')):
        name = ses_dir.name
        if 'BASELINE' in name:
            continue
        corr = ses_dir / 'correlation_summary.json'
        if not corr.exists():
            continue
        with open(corr) as f:
            data = json.load(f)
        raw = data.get('matched_events')
        if raw is None:
            raw = data.get('matches', 0)
        matches = len(raw) if isinstance(raw, list) else (int(raw) if raw else 0)
        eta = data.get('eta_extraccion') or data.get('extraction_efficiency_pct') or data.get('eta') or data.get('eta_extraccion_pct')
        eta_val = round(float(eta), 2) if eta else None

        all_sessions.append({
            'visit': visit_dir.name,
            'day': day,
            'session': name,
            'matches': matches,
            'eta': eta_val
        })

print(f"Total sesiones con correlation_summary (11-28 mayo): {len(all_sessions)}")
print(f"  Con matches > 0: {sum(1 for s in all_sessions if s['matches'] > 0)}")
print(f"  Con matches = 0: {sum(1 for s in all_sessions if s['matches'] == 0)}")
print()

by_visit = {}
for s in all_sessions:
    v = s['visit']
    if v not in by_visit:
        by_visit[v] = []
    by_visit[v].append(s)

print("Por visita:")
for v in sorted(by_visit):
    sessions = by_visit[v]
    con_matches = [s for s in sessions if s['matches'] > 0]
    print(f"  {v}: {len(sessions)} sesiones total, {len(con_matches)} con matches")
    for s in con_matches:
        print(f"    [{s['session'][:50]}] matches={s['matches']} eta={s['eta']}")

etas = [s['eta'] for s in all_sessions if s['eta'] is not None and s['matches'] > 0]
if etas:
    print(f"\nEta estadísticas (sesiones con matches>0, n={len(etas)}):")
    print(f"  Media: {round(sum(etas)/len(etas), 2)}%")
    print(f"  Min:   {min(etas)}%")
    print(f"  Max:   {max(etas)}%")
