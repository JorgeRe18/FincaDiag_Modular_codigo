import json
from pathlib import Path

base = Path('C:/Users/jorge/OneDrive/Documentos/FincaDiag_Modular')
data_dir = base / 'data' / 'processed'

by_visit = {}
for dd in sorted(data_dir.glob('visits/Visita_*_05_2026')):
    day = int(dd.name.split('_')[1])
    if day < 21 or day > 28:
        continue
    for ses in sorted(dd.glob('sesiones/*/correlation_summary.json')):
        name = ses.parent.name
        if 'BASELINE' in name:
            continue
        s = json.loads(ses.read_text(encoding='utf-8'))
        eta_key = next((k for k in ['extraction_efficiency_pct','eta','extraction_efficiency'] if k in s), None)
        eta = round(float(s[eta_key]), 2) if eta_key and s[eta_key] not in (None, 'N/A') else None
        matches = s.get('matched_events', s.get('matches', 0))
        if matches > 0:
            v = dd.name
            if v not in by_visit:
                by_visit[v] = []
            by_visit[v].append({'session': name, 'eta': eta, 'matches': matches})

total = 0
for v, sessions in sorted(by_visit.items()):
    print(f"{v}: {len(sessions)} sesiones")
    for s in sessions:
        print(f"  {s['session']}: eta={s['eta']}, matches={s['matches']}")
    total += len(sessions)

print(f"\nTotal sesiones ordeño completo con matches>0: {total}")
print(f"Visitas: {len(by_visit)}")
