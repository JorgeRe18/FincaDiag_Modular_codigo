@echo off
setlocal enableextensions

set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..") do set PROJECT_ROOT=%%~fI

set SESSION_PRIMARY=%PROJECT_ROOT%\data\processed\visits\Visita_06_04_2026_PM\sesiones\Visita_06_04_2026__TOMA_PM__1PM__Captura_20260406_125505
set SESSION_SECONDARY=%PROJECT_ROOT%\data\processed\visits\Visita_09_04_2026_PM\sesiones\Visita_09_04_2026__TOMA_PM__1PM__Captura_20260409_125505

echo [smoke] gateway offline validation
call "%SCRIPT_DIR%run_gateway.bat" dry-run "%SESSION_PRIMARY%"
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
call "%SCRIPT_DIR%run_gateway.bat" dry-run "%SESSION_SECONDARY%"
if errorlevel 1 exit /b %ERRORLEVEL%

echo.
echo [smoke] completed
exit /b 0
