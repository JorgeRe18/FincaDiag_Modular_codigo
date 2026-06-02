"""Generar coordenadas TikZ para la figura eta_temporal del Cap 6, extendida al 27/05."""
import json, os
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
DATA = BASE / 'data' / 'processed' / 'visits'

start = datetime(2026, 4, 10)

# Sesiones post-intervencion: 11-27 mayo 2026
post_dates = []
for day in range(11, 28):  # 11 a 27 inclusive
    post_dates.append((2026, 5, day))

etas_post = []

for vd in sorted(DATA.iterdir()):
    if not vd.is_dir() or not vd.name.startswith('Visita_'):
        continue
    parts = vd.name.replace('Visita_', '').split('_')
    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    
    if year != 2026 or month != 5:
        continue
    if day < 11 or day > 27:
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
            
            d = datetime(year, month, day)
            delta = (d - start).days
            
            etas_post.append({
                'date': f"{day:02d}/05",
                'day': delta,
                'eta': eta,
                'session': sd.name
            })
        except Exception as e:
            print(f"Error en {corr_file}: {e}")
            continue

# Ordenar por fecha luego por sesion
etas_post.sort(key=lambda x: (x['day'], x['session']))

print(f"Total sesiones post con serial_events>0: {len(etas_post)}")
print("\nCoordenadas TikZ (estrellas):")
for item in etas_post:
    print(f"({item['day']},{item['eta']:.2f})  % {item['date']} {item['session']}")

# También generar las coordenadas de la figura de barras de eventos de red
print("\n\nSesiones para figura eventos_red:")
for item in etas_post:
    print(f"{item['date']} AM/PM -> {item['day']} dias, eta={item['eta']:.2f}%")

# Guardar a JSON para referencia
import json as _json
out = BASE / 'scripts' / 'cap6_coords_tikz.json'
with open(out, 'w', encoding='utf-8') as f:
    _json.dump(etas_post, f, indent=2, ensure_ascii=False)
print(f"\nGuardado en {out}")

# Calcular estadisticas
etas_vals = [e['eta'] for e in etas_post]
print(f"\nEstadisticas post-intervencion:")
print(f"  n = {len(etas_vals)}")
print(f"  eta_media = {sum(etas_vals)/len(etas_vals):.4f}%")
print(f"  min = {min(etas_vals):.2f}%, max = {max(etas_vals):.2f}%")

# Calcular matches y total events
matches_total = 0
serial_total = 0
for vd in sorted(DATA.iterdir()):
    if not vd.is_dir() or not vd.name.startswith('Visita_'):
        continue
    parts = vd.name.replace('Visita_', '').split('_')
    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
    if year != 2026 or month != 5 or day < 11 or day > 27:
        continue
    for sd in sorted(vd.iterdir()):
        corr_file = sd / 'correlation_summary.json'
        if not corr_file.exists():
            continue
        try:
            with open(corr_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if data.get('serial_events', 0) > 0:
                matches_total += data.get('matches', 0)
                serial_total += data.get('serial_events', 0)
        except:
            pass

print(f"  matches_total = {matches_total}, serial_total = {serial_total}")
print(f"  proporcion global = {100*matches_total/serial_total:.2f}%")
