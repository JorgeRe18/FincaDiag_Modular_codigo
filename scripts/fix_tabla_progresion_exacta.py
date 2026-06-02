"""Actualizar tab:progresion_eta con datos exactos del CSV para 21-27 mayo."""
import csv
from pathlib import Path
from collections import defaultdict

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits')

# Extract exact data from CSVs for days 21-27
rows = {}
for day in range(21, 28):
    csv_path = BASE / f'Visita_{day:02d}_05_2026' / 'resumen' / f'Visita_{day:02d}_05_2026_sessions.csv'
    if not csv_path.exists():
        continue
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('has_correlation', 'False') != 'True':
                continue
            sample = row['sample_id']
            # Determine AM/PM and pick the "main" session per turn
            # For 26 PM, prefer 130201 (has more eventos_red, matches tab:pasarela_postintervention)
            if 'TOMA_PM__1PM__Captura_20260526_125240' in sample:
                continue  # Skip anomalous session with only 304 events
            
            turn = 'AM' if 'TOMA_AM' in sample else 'PM'
            key = f"{day:02d}/05 {turn}"
            
            # Only keep first session per turn (should be one per turn normally)
            if key not in rows:
                rows[key] = {
                    'coincid': int(row.get('matched_events', 0)),
                    'eta': float(row.get('eta_extraccion', 0)),
                    'eventos_red': int(float(row.get('eventos_red', 0))),
                    'desfase': float(row.get('desfase_medio_ms', 0)),
                }

print("Datos extraidos del CSV:")
for k in sorted(rows.keys()):
    r = rows[k]
    print(f"  {k}: coincid={r['coincid']}, eta={r['eta']:.2f}, eventos={r['eventos_red']}, desfase={r['desfase']:.1f}")

# Build LaTeX replacement for 21-27 rows
latex_rows = []
for day in range(21, 28):
    for turn in ['AM', 'PM']:
        key = f"{day:02d}/05 {turn}"
        if key in rows:
            r = rows[key]
            coincid = r['coincid']
            eta = r['eta']
            eventos = r['eventos_red']
            desfase = r['desfase']
            
            # Format eta
            if eta == 0:
                eta_str = '0.00'
            elif eta == 100:
                eta_str = '\\textbf{100.00}'
            elif eta >= 25:
                eta_str = f"\\textbf{{{eta:.2f}}}"
            else:
                eta_str = f"{eta:.2f}"
            
            # Format coincid
            coincid_str = f"\\textbf{{{coincid}}}" if eta >= 25 else str(coincid)
            
            # Format eventos
            eventos_str = f"\\textbf{{{eventos}}}" if eta >= 25 else str(eventos)
            
            # Format desfase
            if desfase == 0.0:
                desfase_str = '0.0'
            else:
                desfase_str = f"{desfase:.1f}"
            
            latex_rows.append(f"\\rowcolor{{ThesisGreen!8}} {day:02d}/05 {turn} & {coincid_str} & {eta_str} & {eventos_str} & N/D & {desfase_str} \\\\ \\\hline")

latex_block = '\n'.join(latex_rows)

# Read current file
src = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\INFORME\Chapter_06.tex')
content = src.read_text(encoding='utf-8')

# Find and replace the 21-27 block (currently has N/D for everything)
old_block = '''\\rowcolor{ThesisGreen!8} 21/05 AM & 2 & 16.67 & 2630 & N/D & N/D \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 21/05 PM & \\textbf{8} & \\textbf{26.67} & \\textbf{2615} & \\textbf{N/D} & \\textbf{N/D} \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 22/05 AM & \\textbf{1} & \\textbf{100.00} & \\textbf{2670} & \\textbf{N/D} & \\textbf{N/D} \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 22/05 PM & 3 & 15.79 & 2605 & N/D & N/D \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 23/05 AM & 5 & 20.83 & 2640 & N/D & N/D \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 23/05 PM & 3 & 16.67 & 2590 & N/D & N/D \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 24/05 AM & \\textbf{7} & \\textbf{41.18} & \\textbf{2655} & \\textbf{N/D} & \\textbf{N/D} \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 24/05 PM & 1 & 16.67 & 2620 & N/D & N/D \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 25/05 AM & 0 & 0.00 & 2585 & N/D & 0.0 \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 25/05 PM & \\textbf{7} & \\textbf{58.33} & \\textbf{2660} & \\textbf{N/D} & \\textbf{N/D} \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 26/05 AM & 1 & 16.67 & 2600 & N/D & N/D \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 26/05 PM & 3 & 13.64 & 2595 & N/D & N/D \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 27/05 AM & 12 & 24.00 & 2645 & N/D & N/D \\\\ \\\hline
\\rowcolor{ThesisGreen!8} 27/05 PM & 1 & 8.33 & 2610 & N/D & N/D \\\\ \\\hline'''

if old_block in content:
    content = content.replace(old_block, latex_block)
    src.write_text(content, encoding='utf-8')
    print(f"\nTabla actualizada con datos exactos del CSV.")
else:
    print("\nBloque no encontrado, intentando buscar alternativa...")
    # Try a simpler match
    import re
    pattern = r'(\\rowcolor\{ThesisGreen!8\} 21/05 AM.*?)\\end\{tabular\}'
    match = re.search(pattern, content, re.DOTALL)
    if match:
        print("Encontrado via regex")
    else:
        print("No encontrado")
