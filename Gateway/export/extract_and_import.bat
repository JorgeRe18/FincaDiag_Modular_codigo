@echo off
chcp 65001 >nul
:: extract_and_import.bat
:: Extrae un tar.gz descargado de la Pi y lo coloca en data/processed/visits/
:: Uso: extract_and_import.bat ^<ruta_al_tar.gz^>

set "TAR_GZ=%1"
if "%TAR_GZ%"=="" (
    echo Uso: extract_and_import.bat ^<archivo.tar.gz^>
    echo Ejemplo: extract_and_import.bat C:\Users\%USERNAME%\Downloads\Visita_20_05_2026.tar.gz
    exit /b 1
)

if not exist "%TAR_GZ%" (
    echo [ERROR] No existe: %TAR_GZ%
    exit /b 1
)

set "PROJECT_DIR=%~dp0..\.."
set "DEST_DIR=%PROJECT_DIR%\data\processed\visits"
set "MD5_FILE=%TAR_GZ%.md5"

echo === Importando visita desde Raspberry Pi ===
echo   Archivo: %TAR_GZ%
echo   Destino: %DEST_DIR%

:: Verificar MD5 si existe el archivo .md5
if exist "%MD5_FILE%" (
    echo   Verificando MD5...
    for /f "tokens=1" %%m in ('type "%MD5_FILE%"') do set "EXPECTED_MD5=%%m"
    for /f "skip=1 tokens=*" %%m in ('certutil -hashfile "%TAR_GZ%" MD5') do (
        if not defined ACTUAL_MD5 set "ACTUAL_MD5=%%m"
    )
    :: certutil deja espacios en el hash; limpiar
    set "ACTUAL_MD5=!ACTUAL_MD5: =!"
    if "!ACTUAL_MD5!" neq "!EXPECTED_MD5!" (
        echo [ERROR] MD5 no coincide.
        echo   Esperado: !EXPECTED_MD5!
        echo   Actual:   !ACTUAL_MD5!
        echo   El archivo puede estar corrupto por la transferencia.
        exit /b 1
    )
    echo   [PASS] MD5 verificado correctamente.
) else (
    echo   [WARN] No se encontro archivo .md5 — saltando verificacion.
)

:: Extraer
tar -xzf "%TAR_GZ%" -C "%DEST_DIR%"
if errorlevel 1 (
    echo [ERROR] Fallo la extraccion. Asegurate de tener tar.exe en el PATH.
    exit /b 1
)

:: Extraer nombre de la visita del archivo
for %%f in ("%TAR_GZ%") do set "VISITA_NAME=%%~nf"

if exist "%DEST_DIR%\%VISITA_NAME%" (
    echo [OK] Visita importada: %DEST_DIR%\%VISITA_NAME%
    echo.
    echo Proximo paso: correr el pipeline de procesamiento si no esta procesada.
) else (
    echo [WARN] No se encontro el directorio esperado despues de extraer.
)
