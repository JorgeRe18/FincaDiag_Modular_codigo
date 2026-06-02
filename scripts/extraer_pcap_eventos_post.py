"""Extraer telemetry_packets de pcap_summary.json para figura eventos_red."""
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
        pcap_file = sd / 'pcap_summary.json'
        if not pcap_file.exists():
            continue
        
        try:
            with open(pcap_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            telemetry = data.get('telemetry', {})
            packets = telemetry.get('telemetry_packets', 0)
            
            results.append({
                'visit': vd.name,
                'session': sd.name,
                'day': day,
                'packets': packets
            })
        except Exception as e:
            print(f"Error en {pcap_file}: {e}")

# Ordenar por fecha y sesion
results.sort(key=lambda x: (x['day'], x['session']))

print(f"Total sesiones post con pcap_summary: {len(results)}")
print("\nCoordenadas TikZ (eventos de red):")
for r in results:
    print(f"({r['packets']},{r['day']:02d}/05)  % {r['session'][:40]}")

# Estadisticas
if results:
    packets = [r['packets'] for r in results]
    print(f"\nEstadisticas:")
    print(f"  n = {len(packets)}")
    print(f"  media = {sum(packets)/len(packets):.1f}")
    print(f"  min = {min(packets)}, max = {max(packets)}")
