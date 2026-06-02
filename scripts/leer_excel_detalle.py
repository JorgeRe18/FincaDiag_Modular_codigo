"""Leer del Excel confianza media y desfase medio para sesiones 21-27 mayo."""
import pandas as pd
from pathlib import Path

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
excel_path = BASE / 'RESULTADOS_FincaDiag_Caps4_5_6_Mayo2026.xlsx'

if not excel_path.exists():
    print(f"No encontrado: {excel_path}")
    exit(1)

# Try common sheet names
sheets = pd.ExcelFile(excel_path).sheet_names
print("Hojas disponibles:", sheets)

for sheet in sheets:
    df = pd.read_excel(excel_path, sheet_name=sheet)
    print(f"\n--- {sheet} ---")
    print("Columnas:", df.columns.tolist()[:15])
    # Search for date-like or session-like columns
    date_cols = [c for c in df.columns if any(k in str(c).lower() for k in ['fecha', 'dia', 'session', 'sesion', 'visit'])]
    if date_cols:
        print(f"Posibles columnas de fecha: {date_cols}")
        for dc in date_cols[:2]:
            print(f"  {dc}: {df[dc].dropna().unique()[:5]}")
