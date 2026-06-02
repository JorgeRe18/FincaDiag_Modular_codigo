"""Extraer todos los valores eta del 11-27 mayo de correlation_summary.json."""
import json
from pathlib import Path

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
DATA = BASE / 'data' / 'processed' / 'visits'

results = []

for vd in sorted(DATA.iterdir()):
    if not vd.is_dir() or not vd.name.startswith('Visita_'):
        continue
    parts = vd.name.replace('Visita_', '').split('_')
    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    
    if year != 2026 or month != 5 or day < 11 or day > 27:
        continue
    
    for sd in sorted(vd.iterdir()):
        if not sd.is_dir():
            continue
        corr_file = sd / 'correlation_summary.json'
        if not corr_file.exists():
            continue
        
        try:
            with open(corr_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            serial_events = data.get('serial_events', 0)
            if serial_events == 0:
                continue
            
            eta = data.get('eta', 0.0)
            matches = data.get('matches', 0)
            
            results.append({
                'visit': vd.name,
                'session': sd.name,
                'day': day,
                'eta': eta,
                'matches': matches,
                'serial_events': serial_events
            })
        except Exception as e:
            print(f"Error en {corr_file}: {e}")

# Ordenar por fecha y sesion
results.sort(key=lambda x: (x['day'], x['session']))

print(f"Total sesiones post con serial_events>0: {len(results)}")
print("\nLista completa:")
for r in results:
    print(f"  {r['day']:02d}/05 | {r['session'][:40]:40s} | eta={r['eta']:6.2f}% | matches={r['matches']:2d}/{r['serial_events']:2d}")

if results:
    etas = [r['eta'] for r in results]
    print(f"\nEstadisticas:")
    print(f"  n = {len(etas)}")
    print(f"  media = {sum(etas)/len(etas):.4f}%")
    print(f"  min = {min(etas):.2f}%, max = {max(etas):.2f}%")
    
    matches_total = sum(r['matches'] for r in results)
    serial_total = sum(r['serial_events'] for r in results)
    print(f"  matches_total = {matches_total}, serial_total = {serial_total}")
    print(f"  proporcion = {100*matches_total/serial_total:.2f}%")

# Guardar
out = BASE / 'scripts' / 'eta_post_11_27_completo.json'
with open(out, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\nGuardado en {out}")
