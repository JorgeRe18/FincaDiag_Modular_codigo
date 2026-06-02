"""Buscar TODOS los pcap_summary.json recursivamente y extraer telemetry_packets."""
import json
from pathlib import Path
from collections import defaultdict

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')

# Buscar TODOS los pcap_summary.json
all_pcap = list(BASE.rglob('pcap_summary.json'))
print(f"Total pcap_summary.json encontrados: {len(all_pcap)}")

# Filtrar por fechas 11-27 mayo 2026
post_pcaps = []
for pcap_file in all_pcap:
    path_str = str(pcap_file)
    # Buscar fechas tipo 20260521, 20260522, etc.
    if '202605' in path_str:
        day_str = path_str.split('202605')[1][:2] if '202605' in path_str else None
        if day_str and day_str.isdigit():
            day = int(day_str)
            if 11 <= day <= 27:
                try:
                    with open(pcap_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    telemetry = data.get('telemetry', {})
                    packets = telemetry.get('telemetry_packets', 0)
                    post_pcaps.append({
                        'file': str(pcap_file.relative_to(BASE)),
                        'day': day,
                        'packets': packets
                    })
                except Exception as e:
                    print(f"  Error en {pcap_file}: {e}")

print(f"\npcap_summary del 11-27 mayo: {len(post_pcaps)}")
# Agrupar por día
by_day = defaultdict(list)
for item in post_pcaps:
    by_day[item['day']].append(item['packets'])

for day in sorted(by_day.keys()):
    packets_list = by_day[day]
    print(f"  {day}/05: {packets_list} (n={len(packets_list)})")

# Ver si hay alguno en tmp_upload o tmp_17_05_upload
print("\n--- Verificar tmp_17_05_upload ---")
tmp_dir = BASE / 'tmp_17_05_upload'
if tmp_dir.exists():
    tmp_pcaps = list(tmp_dir.rglob('pcap_summary.json'))
    print(f"  tmp_17_05_upload pcap_summary.json: {len(tmp_pcaps)}")
    for pcap_file in tmp_pcaps:
        try:
            with open(pcap_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            telemetry = data.get('telemetry', {})
            packets = telemetry.get('telemetry_packets', 0)
            print(f"    {pcap_file.name}: packets={packets}")
        except Exception as e:
            print(f"    Error: {e}")
else:
    print("  No existe tmp_17_05_upload")
