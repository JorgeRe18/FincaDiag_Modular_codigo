@echo off
setlocal
set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..") do set PROJECT_ROOT=%%~fI
if "%PYTHONPATH%"=="" (
  set PYTHONPATH=%PROJECT_ROOT%\src
) else (
  set PYTHONPATH=%PROJECT_ROOT%\src;%PYTHONPATH%
)
set TOPIC_ROOT=fincadiag/la_esmeralda

echo === 15/05 AM 2AM ===
python -m fincadiag.gateway.runtime --session-dir "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_15_05_2026\sesiones\TOMA_AM__2AM__Captura_20260515_021505" --topic-root "%TOPIC_ROOT%" --dry-run
if errorlevel 1 echo FAILED

echo.
echo === 15/05 PM 1PM ===
python -m fincadiag.gateway.runtime --session-dir "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_15_05_2026\sesiones\TOMA_PM__1PM__Captura_20260515_130005" --topic-root "%TOPIC_ROOT%" --dry-run
if errorlevel 1 echo FAILED

echo.
echo === 16/05 AM 2AM ===
python -m fincadiag.gateway.runtime --session-dir "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_16_05_2026\sesiones\TOMA_AM__2AM__Captura_20260516_021505" --topic-root "%TOPIC_ROOT%" --dry-run
if errorlevel 1 echo FAILED

echo.
echo === 16/05 PM 1PM ===
python -m fincadiag.gateway.runtime --session-dir "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_16_05_2026\sesiones\TOMA_PM__1PM__Captura_20260516_130005" --topic-root "%TOPIC_ROOT%" --dry-run
if errorlevel 1 echo FAILED

echo.
echo === 17/05 AM 2AM ===
python -m fincadiag.gateway.runtime --session-dir "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_17_05_2026\sesiones\TOMA_AM__2AM__Captura_20260517_021505" --topic-root "%TOPIC_ROOT%" --dry-run
if errorlevel 1 echo FAILED

echo.
echo === 17/05 PM 1PM ===
python -m fincadiag.gateway.runtime --session-dir "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_17_05_2026\sesiones\TOMA_PM__1PM__Captura_20260517_130005" --topic-root "%TOPIC_ROOT%" --dry-run
if errorlevel 1 echo FAILED

echo.
echo Done.
