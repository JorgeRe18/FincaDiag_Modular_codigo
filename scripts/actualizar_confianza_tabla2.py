"""Actualizar tabla progresion_eta con confianzas calculadas."""
from pathlib import Path

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
    # Simple string replace for each row
    old_str = f'\\rowcolor{{ThesisGreen!8}} {session} & '
    # Find the row and replace the N/D before the last column
    idx = content.find(old_str)
    if idx >= 0:
        # Find the end of this row
        end_idx = content.find('\\\\ \\hline', idx)
        if end_idx > 0:
            row = content[idx:end_idx+10]
            # Replace N/D (confianza column) - it's the 5th column
            # Pattern: ... & N/D & desfase...
            new_row = row.replace(' & N/D & ', f' & {conf} & ', 1)
            if new_row != row:
                content = content.replace(row, new_row)
                changes += 1
                print(f"  {session}: {conf}")
            else:
                print(f"  {session}: ya tiene valor")
        else:
            print(f"  {session}: fin de fila no encontrado")
    else:
        print(f"  {session}: fila no encontrada")

if changes > 0:
    src.write_text(content, encoding='utf-8')
    print(f"\n{changes} filas actualizadas.")
else:
    print("\nNinguna fila actualizada.")
