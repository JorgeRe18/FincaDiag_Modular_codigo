"""Extraer parser_confidence_average de serial_summary.json para 21-27."""
import json
from pathlib import Path

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits')

sessions_map = {
    (21, 'AM'): ('Visita_21_05_2026', 'TOMA_AM__2AM__Captura_20260521_021505'),
    (21, 'PM'): ('Visita_21_05_2026', 'TOMA_PM__1PM__Captura_20260521_130005'),
    (22, 'AM'): ('Visita_22_05_2026', 'TOMA_AM__2AM__Captura_20260522_021505'),
    (22, 'PM'): ('Visita_22_05_2026', 'TOMA_PM__1PM__Captura_20260522_130005'),
    (23, 'AM'): ('Visita_23_05_2026', 'TOMA_AM__2AM__Captura_20260523_021505'),
    (23, 'PM'): ('Visita_23_05_2026', 'TOMA_PM__1PM__Captura_20260523_130005'),
    (24, 'AM'): ('Visita_24_05_2026', 'TOMA_AM__2AM__Captura_20260524_021505'),
    (24, 'PM'): ('Visita_24_05_2026', 'TOMA_PM__1PM__Captura_20260524_130005'),
    (25, 'AM'): ('Visita_25_05_2026', 'TOMA_AM__2AM__Captura_20260525_021505'),
    (25, 'PM'): ('Visita_25_05_2026', 'TOMA_PM__1PM__Captura_20260525_130005'),
    (26, 'AM'): ('Visita_26_05_2026', 'TOMA_AM__2AM__Captura_20260526_021506'),
    (26, 'PM'): ('Visita_26_05_2026', 'TOMA_PM__1PM__Captura_20260526_130201'),
    (27, 'AM'): ('Visita_27_05_2026', 'TOMA_AM__2AM__Captura_20260527_021505'),
    (27, 'PM'): ('Visita_27_05_2026', 'TOMA_PM__1PM__Captura_20260527_130005'),
}

print("parser_confidence_average para 21-27:")
confianzas = {}
for (day, turn), (visit, session) in sessions_map.items():
    serial_path = BASE / visit / 'sesiones' / session / 'serial_summary.json'
    if serial_path.exists():
        with open(serial_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        conf = data.get('parser_confidence_average', 0.0)
        key = f"{day:02d}/05 {turn}"
        confianzas[key] = round(conf, 2)
        print(f"  {key}: {conf:.3f}")
    else:
        print(f"  {day:02d}/05 {turn}: NO ENCONTRADO")

# Update table
src = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\INFORME\Chapter_06.tex')
content = src.read_text(encoding='utf-8')

changes = 0
for key, conf in confianzas.items():
    old_str = f'\\rowcolor{{ThesisGreen!8}} {key} & '
    idx = content.find(old_str)
    if idx >= 0:
        end_idx = content.find('\\\\ \\hline', idx)
        if end_idx > 0:
            row = content[idx:end_idx+10]
            # Replace the confidence value (5th column, between desfase and last)
            # Pattern: & X & Y & Z & CONF & DESFASE \ \hline
            # We need to find the 4th & and replace what's between 4th and 5th &
            parts = row.split(' & ')
            if len(parts) >= 6:
                parts[4] = f"{conf:.2f}"
                new_row = ' & '.join(parts)
                if new_row != row:
                    content = content.replace(row, new_row)
                    changes += 1
                    print(f"  Actualizado {key}: {conf:.2f}")

if changes > 0:
    src.write_text(content, encoding='utf-8')
    print(f"\n{changes} filas actualizadas con parser_confidence_average real.")
else:
    print("\nNo se actualizaron filas.")
