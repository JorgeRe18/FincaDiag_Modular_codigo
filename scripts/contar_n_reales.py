"""Contar n reales para Cap 4, 5, 6 sin mentiras."""
import json
from pathlib import Path

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
DATA = BASE / 'data/processed/visits'

pre_visits = []
post_visits = []
pre_sessions = []
post_sessions = []

for vd in sorted(DATA.iterdir()):
    if not vd.is_dir() or not vd.name.startswith('Visita_'):
        continue
    parts = vd.name.replace('Visita_', '').split('_')
    day = int(parts[0])
    month = int(parts[1])
    year = int(parts[2])
    is_post = (year, month, day) >= (2026, 5, 11)
    
    sessions = []
    ses_dir = vd / 'sesiones'
    if ses_dir.exists():
        for s in sorted(ses_dir.iterdir()):
            if not s.is_dir() or 'BASELINE_ONLY' in s.name or 'Captura_' not in s.name:
                continue
            corr_path = s / 'correlation_summary.json'
            if corr_path.exists():
                try:
                    corr = json.loads(corr_path.read_text())
                    raw = corr.get('matched_events')
                    if raw is None: raw = corr.get('matches', 0)
                    matches = len(raw) if isinstance(raw, list) else (int(raw) if raw else 0)
                    serial = corr.get('serial_events', 0)
                    if serial > 0:
                        sessions.append({'name': s.name, 'matches': matches, 'serial': serial})
                except:
                    pass
    
    if is_post:
        post_visits.append({'name': vd.name, 'sessions': sessions})
        post_sessions.extend(sessions)
    else:
        pre_visits.append({'name': vd.name, 'sessions': sessions})
        pre_sessions.extend(sessions)

print('=== PRE-INTERVENCION (antes del 11 mayo) ===')
print(f'Visitas: {len(pre_visits)}')
print(f'Sesiones con serial_events > 0: {len(pre_sessions)}')
pre_with_matches = [s for s in pre_sessions if s['matches'] > 0]
print(f'Sesiones con matches > 0: {len(pre_with_matches)}')
if pre_sessions:
    etas = [s['matches']/s['serial']*100 for s in pre_sessions if s['serial'] > 0]
    print(f'eta promedio (todas las sesiones): {sum(etas)/len(etas):.2f}%')
    etas_match = [s['matches']/s['serial']*100 for s in pre_with_matches]
    print(f'eta promedio (solo con matches): {sum(etas_match)/len(etas_match):.2f}%')

print()
print('=== POST-INTERVENCION (11-27 mayo) ===')
print(f'Visitas: {len(post_visits)}')
print(f'Sesiones con serial_events > 0: {len(post_sessions)}')
post_with_matches = [s for s in post_sessions if s['matches'] > 0]
print(f'Sesiones con matches > 0: {len(post_with_matches)}')
if post_sessions:
    etas = [s['matches']/s['serial']*100 for s in post_sessions if s['serial'] > 0]
    print(f'eta promedio (todas las sesiones): {sum(etas)/len(etas):.2f}%')
    etas_match = [s['matches']/s['serial']*100 for s in post_with_matches]
    print(f'eta promedio (solo con matches): {sum(etas_match)/len(etas_match):.2f}%')

print()
print('=== TODAS LAS SESIONES CON MATCHES > 0 (para gateway dry-run) ===')
all_with_matches = pre_with_matches + post_with_matches
print(f'Total: {len(all_with_matches)}')
for s in all_with_matches[:15]:
    print(f'  {s["name"][:50]}: matches={s["matches"]}, serial={s["serial"]}')
if len(all_with_matches) > 15:
    print(f'  ... y {len(all_with_matches)-15} mas')
