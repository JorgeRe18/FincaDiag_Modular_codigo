"""Corregir celdas N/D incorrectas en panel_cobertura_eta."""
from pathlib import Path

src = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\INFORME\Chapter_06.tex')
content = src.read_text(encoding='utf-8')

# Correcciones: (fila, dia, valor_real, es_bold)
correcciones = [
    # Fila AM
    ('AM', '15/05', '35.71', True),
    ('AM', '16/05', '16.67', False),
    ('AM', '19/05', '16.67', False),
    # Fila PM
    ('PM', '17/05', '0.00', False),  # ZeroCell
    ('PM', '18/05', '33.33', True),
    ('PM', '20/05', '0.00', False),  # ZeroCell
]

changes = 0
for fila, dia, valor, es_bold in correcciones:
    # Buscar el bloque de la fila
    if fila == 'AM':
        pattern = r'\\textbf\{AM\}.*?\\\\ \\hline'
    else:
        pattern = r'\\textbf\{PM\}.*?\\\\ \\hline'
    
    import re
    match = re.search(pattern, content, re.DOTALL)
    if match:
        fila_text = match.group(0)
        # Contar cuántas celdas hay antes para saber la posición
        # Las columnas son: 04/05, 06/05, 07/05, 11/05, 12/05, 13/05, 14/05, 15/05, 16/05, 17/05, 18/05, 19/05, 20/05, 21/05, 22/05, 23/05, 24/05, 25/05, 26/05, 27/05
        # Necesitamos un enfoque más directo: reemplazar \NAcell en la posición correcta
        pass

# Enfoque más simple: reemplazos directos en el texto completo
# Para AM 15/05: buscar entre 14/05 y 16/05 en fila AM
# Para AM 16/05: buscar entre 15/05 y 17/05 en fila AM
# etc.

# Vamos a usar un enfoque de reemplazo directo por contexto
replacements = [
    # AM 15/05: está entre 23.53 y 27.27
    ('\\cellcolor{ThesisGreen!24}23.53 & \\NAcell & \\NAcell & \\cellcolor{ThesisGreen!27}', 
     '\\cellcolor{ThesisGreen!24}23.53 & \\cellcolor{ThesisGreen!35}\\textbf{35.71} & \\cellcolor{ThesisGreen!16}16.67 & \\cellcolor{ThesisGreen!27}'),
    # AM 19/05: está entre 25.00 y 8.33
    ('\\cellcolor{ThesisGreen!25}\\textbf{25.00} & \\NAcell & \\cellcolor{ThesisGreen!8}8.33',
     '\\cellcolor{ThesisGreen!25}\\textbf{25.00} & \\cellcolor{ThesisGreen!16}16.67 & \\cellcolor{ThesisGreen!8}8.33'),
    # PM 17/05: está entre 33.33 y 16.67 (pero hay dos \NAcell consecutivos)
    ('\\cellcolor{ThesisGreen!33}\\textbf{33.33} & \\NAcell & \\NAcell & \\cellcolor{ThesisGreen!17}16.67',
     '\\cellcolor{ThesisGreen!33}\\textbf{33.33} & \\ZeroCell & \\cellcolor{ThesisGreen!33}\\textbf{33.33} & \\cellcolor{ThesisGreen!17}16.67'),
    # PM 20/05: está entre 16.67 y 26.67
    ('\\cellcolor{ThesisGreen!17}16.67 & \\NAcell & \\cellcolor{ThesisGreen!27}',
     '\\cellcolor{ThesisGreen!17}16.67 & \\ZeroCell & \\cellcolor{ThesisGreen!27}'),
]

for old, new in replacements:
    if old in content:
        content = content.replace(old, new)
        changes += 1
        print(f"  Reemplazado: {old[:50]}...")
    else:
        print(f"  NO ENCONTRADO: {old[:50]}...")

if changes > 0:
    src.write_text(content, encoding='utf-8')
    print(f"\n{changes} reemplazos aplicados.")
else:
    print("\nNingun reemplazo aplicado.")
