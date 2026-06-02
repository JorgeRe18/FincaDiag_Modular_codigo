"""Extender fig:panel_cobertura_eta hasta 27/05."""
from pathlib import Path

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
src = BASE / 'INFORME' / 'Chapter_06.tex'
content = src.read_text(encoding='utf-8')

# Old table header and rows
old_header = '\\rowcolor{gray!20} \\TableHeaderFirst{Turno} & \\TableHeader{04/05} & \\TableHeader{06/05} & \\TableHeaderDouble{07/05} & \\TableHeader{11/05} & \\TableHeader{12/05} & \\TableHeader{13/05} & \\TableHeader{14/05} & \\TableHeader{15/05} & \\TableHeader{16/05} & \\TableHeader{17/05} & \\TableHeader{18/05} & \\TableHeader{19/05} & \\TableHeader{20/05} \\\\ \\hline'
new_header = '\\rowcolor{gray!20} \\TableHeaderFirst{Turno} & \\TableHeader{04/05} & \\TableHeader{06/05} & \\TableHeaderDouble{07/05} & \\TableHeader{11/05} & \\TableHeader{12/05} & \\TableHeader{13/05} & \\TableHeader{14/05} & \\TableHeader{15/05} & \\TableHeader{16/05} & \\TableHeader{17/05} & \\TableHeader{18/05} & \\TableHeader{19/05} & \\TableHeader{20/05} & \\TableHeader{21/05} & \\TableHeader{22/05} & \\TableHeader{23/05} & \\TableHeader{24/05} & \\TableHeader{25/05} & \\TableHeader{26/05} & \\TableHeaderDouble{27/05} \\\\ \\hline'

old_am = '\\textbf{AM} & \\NAcell & \\NAcell & \\NAcell & \\ZeroCell & \\cellcolor{ThesisGreen!38}\\textbf{38.46} & \\cellcolor{ThesisGreen!18}18.18 & \\cellcolor{ThesisGreen!24}23.53 & \\NAcell & \\NAcell & \\cellcolor{ThesisGreen!27}\\textbf{27.27} & \\cellcolor{ThesisGreen!25}\\textbf{25.00} & \\NAcell & \\cellcolor{ThesisGreen!8}8.33 \\\\ \\hline'
new_am = '\\textbf{AM} & \\NAcell & \\NAcell & \\NAcell & \\ZeroCell & \\cellcolor{ThesisGreen!38}\\textbf{38.46} & \\cellcolor{ThesisGreen!18}18.18 & \\cellcolor{ThesisGreen!24}23.53 & \\NAcell & \\NAcell & \\cellcolor{ThesisGreen!27}\\textbf{27.27} & \\cellcolor{ThesisGreen!25}\\textbf{25.00} & \\NAcell & \\cellcolor{ThesisGreen!8}8.33 & \\cellcolor{ThesisGreen!17}16.67 & \\cellcolor{ThesisGreen!100}\\textbf{100.00} & \\cellcolor{ThesisGreen!21}20.83 & \\cellcolor{ThesisGreen!41}\\textbf{41.18} & \\ZeroCell & \\cellcolor{ThesisGreen!17}16.67 & \\cellcolor{ThesisGreen!24}24.00 \\\\ \\hline'

old_pm = '\\textbf{PM} & \\cellcolor{ThesisGreen!8}8.00 & \\cellcolor{ThesisGreen!5}5.10 & \\cellcolor{ThesisGreen!16}16.20 & \\cellcolor{ThesisGreen!24}24.24 & \\cellcolor{ThesisGreen!19}19.05 & \\cellcolor{ThesisGreen!21}21.05 & \\ZeroCell & \\cellcolor{ThesisGreen!28}\\textbf{27.91} & \\cellcolor{ThesisGreen!33}\\textbf{33.33} & \\NAcell & \\NAcell & \\cellcolor{ThesisGreen!17}16.67 & \\NAcell \\\\ \\hline'
new_pm = '\\textbf{PM} & \\cellcolor{ThesisGreen!8}8.00 & \\cellcolor{ThesisGreen!5}5.10 & \\cellcolor{ThesisGreen!16}16.20 & \\cellcolor{ThesisGreen!24}24.24 & \\cellcolor{ThesisGreen!19}19.05 & \\cellcolor{ThesisGreen!21}21.05 & \\ZeroCell & \\cellcolor{ThesisGreen!28}\\textbf{27.91} & \\cellcolor{ThesisGreen!33}\\textbf{33.33} & \\NAcell & \\NAcell & \\cellcolor{ThesisGreen!17}16.67 & \\NAcell & \\cellcolor{ThesisGreen!27}\\textbf{26.67} & \\cellcolor{ThesisGreen!16}15.79 & \\cellcolor{ThesisGreen!17}16.67 & \\cellcolor{ThesisGreen!17}16.67 & \\cellcolor{ThesisGreen!58}\\textbf{58.33} & \\cellcolor{ThesisGreen!14}13.64 & \\cellcolor{ThesisGreen!8}8.33 \\\\ \\hline'

changes = 0
if old_header in content:
    content = content.replace(old_header, new_header)
    changes += 1
    print("1. Header extendido")
else:
    print("1. Header no encontrado")

if old_am in content:
    content = content.replace(old_am, new_am)
    changes += 1
    print("2. Fila AM extendida")
else:
    print("2. Fila AM no encontrada")

if old_pm in content:
    content = content.replace(old_pm, new_pm)
    changes += 1
    print("3. Fila PM extendida")
else:
    print("3. Fila PM no encontrada")

if changes > 0:
    src.write_text(content, encoding='utf-8')
    print(f"Guardado: {src}")
else:
    print("Nada cambiado")
