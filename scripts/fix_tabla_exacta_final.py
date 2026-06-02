"""Actualizar tab:progresion_eta con datos exactos del CSV para 21-27 mayo."""
import csv
from pathlib import Path
import re

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
            # Skip anomalous 26/05 session
            if 'TOMA_PM__1PM__Captura_20260526_125240' in sample:
                continue
            
            turn = 'AM' if 'TOMA_AM' in sample else 'PM'
            key = f"{day:02d}/05 {turn}"
            
            if key not in rows:
                rows[key] = {
                    'coincid': int(row.get('matched_events', 0)),
                    'eta': float(row.get('eta_extraccion', 0)),
                    'eventos_red': int(float(row.get('eventos_red', 0))),
                    'desfase': float(row.get('desfase_medio_ms', 0)),
                }

# Build LaTeX replacement
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
            elif eta >= 25:
                eta_str = f"\\textbf{{{eta:.2f}}}"
            else:
                eta_str = f"{eta:.2f}"
            
            # Format coincid
            coincid_str = f"\\textbf{{{coincid}}}" if eta >= 25 else str(coincid)
            
            # Format eventos
            eventos_str = f"\\textbf{{{eventos}}}" if eta >= 25 else str(eventos)
            
            # Format desfase
            desfase_str = '0.0' if desfase == 0.0 else f"{desfase:.1f}"
            
            latex_rows.append(f"\\rowcolor{{ThesisGreen!8}} {day:02d}/05 {turn} & {coincid_str} & {eta_str} & {eventos_str} & N/D & {desfase_str} \\\\ \\\hline")

latex_block = '\n'.join(latex_rows)

# Read current file
src = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\INFORME\Chapter_06.tex')
content = src.read_text(encoding='utf-8')

# Find and replace via regex
pattern = r'\\rowcolor\{ThesisGreen!8\} 21/05 AM.*?\\rowcolor\{ThesisGreen!8\} 27/05 PM.*?\\\\ \\hline'
match = re.search(pattern, content, re.DOTALL)

if match:
    old_text = match.group(0)
    content = content.replace(old_text, latex_block)
    src.write_text(content, encoding='utf-8')
    print("Tabla actualizada con datos exactos del CSV.")
    print(f"Reemplazado bloque de {len(old_text)} chars con {len(latex_block)} chars")
else:
    print("Patron regex no encontrado")
