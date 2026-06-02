"""Actualizar tabla progresion_eta con confianzas calculadas."""
from pathlib import Path
import re

src = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\INFORME\Chapter_06.tex')
content = src.read_text(encoding='utf-8')

# Confianzas calculadas
confianzas = {
    '21/05 AM': '0.32',
    '21/05 PM': '0.36',
    '22/05 AM': '0.80',
    '22/05 PM': '0.32',
    '23/05 AM': '0.34',
    '23/05 PM': '0.32',
    '24/05 AM': '0.43',
    '24/05 PM': '0.32',
    '25/05 AM': '0.31',
    '25/05 PM': '0.50',
    '26/05 AM': '0.32',
    '26/05 PM': '0.31',
    '27/05 AM': '0.35',
    '27/05 PM': '0.29',
}

changes = 0
for session, conf in confianzas.items():
    # Buscar fila de la sesion y reemplazar N/D de confianza
    pattern = rf'(\\rowcolor\{{ThesisGreen!8\}} {re.escape(session)} .*?)(N/D|\\textbf\{{N/D\}})( .*?\\\\ \\hline)'
    match = re.search(pattern, content)
    if match:
        old = match.group(0)
        new = old.replace(match.group(2), conf)
        content = content.replace(old, new)
        changes += 1
        print(f"  {session}: {conf}")
    else:
        print(f"  {session}: NO ENCONTRADA")

if changes > 0:
    src.write_text(content, encoding='utf-8')
    print(f"\n{changes} filas actualizadas.")
else:
    print("\nNinguna fila actualizada.")
