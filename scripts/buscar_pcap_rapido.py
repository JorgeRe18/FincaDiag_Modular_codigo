"""Buscar pcap_summary.json solo en data/processed/visits/Visita_*_05_2026."""
import json
from pathlib import Path
from collections import defaultdict

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
DATA = BASE / 'data' / 'processed' / 'visits'

post_pcaps = []

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
        if pcap_file.exists():
            try:
                with open(pcap_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                telemetry = data.get('telemetry', {})
                packets = telemetry.get('telemetry_packets', 0)
                post_pcaps.append({
                    'day': day,
                    'session': sd.name,
                    'packets': packets
                })
            except Exception as e:
                print(f"  Error en {pcap_file}: {e}")

print(f"Total pcap_summary.json del 11-27 mayo: {len(post_pcaps)}")
# Agrupar por día
by_day = defaultdict(list)
for item in post_pcaps:
    by_day[item['day']].append(item['packets'])

for day in sorted(by_day.keys()):
    packets_list = by_day[day]
    print(f"  {day}/05: {packets_list} (n={len(packets_list)})")
