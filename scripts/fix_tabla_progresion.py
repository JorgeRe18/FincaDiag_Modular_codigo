"""Extender tabla tab:progresion_eta hasta 27/05."""
from pathlib import Path

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
src = BASE / 'INFORME' / 'Chapter_06.tex'
content = src.read_text(encoding='utf-8')

old_end = '\\rowcolor{ThesisGreen!8} 20/05 AM & 1 & 8.33 & 2595 & 0.38 & 85.0 \\\\ \\hline\n\\end{tabular}'

new_rows = '''\\rowcolor{ThesisGreen!8} 20/05 AM & 1 & 8.33 & 2595 & 0.38 & 85.0 \\\\ \\hline
\\rowcolor{ThesisGreen!8} 21/05 AM & 2 & 16.67 & 2630 & N/D & N/D \\\\ \\hline
\\rowcolor{ThesisGreen!8} 21/05 PM & \\textbf{8} & \\textbf{26.67} & \\textbf{2615} & \\textbf{N/D} & \\textbf{N/D} \\\\ \\hline
\\rowcolor{ThesisGreen!8} 22/05 AM & \\textbf{1} & \\textbf{100.00} & \\textbf{2670} & \\textbf{N/D} & \\textbf{N/D} \\\\ \\hline
\\rowcolor{ThesisGreen!8} 22/05 PM & 3 & 15.79 & 2605 & N/D & N/D \\\\ \\hline
\\rowcolor{ThesisGreen!8} 23/05 AM & 5 & 20.83 & 2640 & N/D & N/D \\\\ \\hline
\\rowcolor{ThesisGreen!8} 23/05 PM & 3 & 16.67 & 2590 & N/D & N/D \\\\ \\hline
\\rowcolor{ThesisGreen!8} 24/05 AM & \\textbf{7} & \\textbf{41.18} & \\textbf{2655} & \\textbf{N/D} & \\textbf{N/D} \\\\ \\hline
\\rowcolor{ThesisGreen!8} 24/05 PM & 1 & 16.67 & 2620 & N/D & N/D \\\\ \\hline
\\rowcolor{ThesisGreen!8} 25/05 AM & 0 & 0.00 & 2585 & N/D & 0.0 \\\\ \\hline
\\rowcolor{ThesisGreen!8} 25/05 PM & \\textbf{7} & \\textbf{58.33} & \\textbf{2660} & \\textbf{N/D} & \\textbf{N/D} \\\\ \\hline
\\rowcolor{ThesisGreen!8} 26/05 AM & 1 & 16.67 & 2600 & N/D & N/D \\\\ \\hline
\\rowcolor{ThesisGreen!8} 26/05 PM & 3 & 13.64 & 2595 & N/D & N/D \\\\ \\hline
\\rowcolor{ThesisGreen!8} 27/05 AM & 12 & 24.00 & 2645 & N/D & N/D \\\\ \\hline
\\rowcolor{ThesisGreen!8} 27/05 PM & 1 & 8.33 & 2610 & N/D & N/D \\\\ \\hline
\\end{tabular}'''

if old_end in content:
    content = content.replace(old_end, new_rows)
    src.write_text(content, encoding='utf-8')
    print("Tabla progresion_eta extendida hasta 27/05")
else:
    print("Patron no encontrado")
