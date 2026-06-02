@echo off
chcp 65001 >nul
:: Suite completa de pruebas de gateway para Windows
:: Objetivo: validar contrato, idempotencia y consistencia de metricas
:: antes del contraste estadistico (Objetivo 4).

set "SESSION_DIR=%1"
if "%SESSION_DIR%"=="" (
    echo Uso: run_all_tests.bat ^<ruta_sesion_procesada^>
    echo Ejemplo: run_all_tests.bat data\processed\visits\Visita_15_05_2026\sesiones\TOMA_PM__1PM__Captura_20260515_130005
    exit /b 1
)

echo ==========================================
echo SUITE DE PRUEBAS GATEWAY (Windows)
echo ==========================================
echo.

set "PASS=0"
set "FAIL=0"

:: Prueba 1: Schema
echo [1/3] Validacion de contrato JSON...
call "%~dp0validate_schema.bat" "%SESSION_DIR%"
if %errorlevel% == 0 (
    set /a PASS+=1
) else (
    set /a FAIL+=1
)
echo.

:: Prueba 2: Idempotencia
echo [2/3] Prueba de idempotencia...
call "%~dp0idempotency.bat" "%SESSION_DIR%"
if %errorlevel% == 0 (
    set /a PASS+=1
) else (
    set /a FAIL+=1
)
echo.

:: Prueba 3: Objetivo 4 (metricas)
echo [3/3] Validacion de metricas Objetivo 4...
call "%~dp0validate_objective4.bat" "%SESSION_DIR%"
if %errorlevel% == 0 (
    set /a PASS+=1
) else (
    set /a FAIL+=1
)
echo.

echo ==========================================
echo RESULTADOS: %PASS% pass / %FAIL% fail
echo ==========================================

if %FAIL% == 0 (
    echo [PASS] Suite completada exitosamente.
    exit /b 0
) else (
    echo [FAIL] Hubo errores en la suite.
    exit /b 1
)
