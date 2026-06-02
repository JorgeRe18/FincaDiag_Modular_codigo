@echo off
setlocal

cd /d "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway"

echo === 11/05 AM ===
run_gateway.bat dry-run "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_11_05_2026\sesiones\TOMA_AM__2AM__Captura_20260511_021505"

echo.
echo === 12/05 PM ===
run_gateway.bat dry-run "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_12_05_2026\sesiones\TOMA_PM__1PM__Captura_20260512_130005"

echo.
echo === 14/05 AM ===
run_gateway.bat dry-run "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_14_05_2026\sesiones\TOMA_AM__2AM__Captura_20260514_021505"

echo.
echo === 14/05 PM ===
run_gateway.bat dry-run "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_14_05_2026\sesiones\TOMA_PM__1PM__Captura_20260514_130006"
