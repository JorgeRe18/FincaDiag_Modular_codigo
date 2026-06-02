@echo off
chcp 65001 >nul
:: Prueba 4: Idempotencia del gateway
:: Objetivo: confirmar que dos corridas identicas producen salida identica.
:: Sirve para Objetivo 4: ruido del gateway no afecta η entre corridas.

set "SESSION_DIR=%1"
if "%SESSION_DIR%"=="" (
    echo Uso: idempotency.bat ^<ruta_sesion_procesada^>
    exit /b 1
)

set "PYTHONPATH=%~dp0..\..\src"
set "PUB_DIR=%~dp0..\..\data\gateway\published"

echo === Prueba de idempotencia: %SESSION_DIR% ===

:: Primera corrida
echo --- Run 1 ---
python -m fincadiag.gateway.runtime --session-dir "%SESSION_DIR%" --topic-root "fincadiag/la_esmeralda" --dry-run >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Run 1 fallo
    exit /b 1
)
for %%f in ("%PUB_DIR%\*.jsonl") do (
    certutil -hashfile "%%f" MD5 | findstr /v "CertUtil" > "%~dp0run1_%%~nf.md5"
)

:: Borrar published para segunda corrida
del /q "%PUB_DIR%\*.*" 2>nul

:: Segunda corrida
echo --- Run 2 ---
python -m fincadiag.gateway.runtime --session-dir "%SESSION_DIR%" --topic-root "fincadiag/la_esmeralda" --dry-run >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Run 2 fallo
    exit /b 1
)
for %%f in ("%PUB_DIR%\*.jsonl") do (
    certutil -hashfile "%%f" MD5 | findstr /v "CertUtil" > "%~dp0run2_%%~nf.md5"
)

:: Comparar checksums
echo --- Comparacion ---
set "MATCH=0"
set "MISMATCH=0"
for %%a in ("%~dp0run1_*.md5") do (
    set "name=%%~na"
    set "name=!name:run1_=run2_!"
    if exist "%~dp0!name!.md5" (
        fc /b "%%a" "%~dp0!name!.md5" >nul 2>&1
        if !errorlevel! == 0 (
            set /a MATCH+=1
        ) else (
            set /a MISMATCH+=1
            echo [MISMATCH] %%~na
        )
    ) else (
        echo [MISSING] %%~na
        set /a MISMATCH+=1
    )
)

del /q "%~dp0run1_*.md5" "%~dp0run2_*.md5" 2>nul

if %MISMATCH% == 0 (
    echo [PASS] Idempotencia verificada (%MATCH% archivos identicos)
) else (
    echo [FAIL] %MISMATCH% archivos difieren (%MATCH% coinciden)
    exit /b 1
)
