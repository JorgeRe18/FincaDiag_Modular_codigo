@echo off
setlocal enableextensions enabledelayedexpansion

set SCRIPT_DIR=%~dp0
for %%I in ("%SCRIPT_DIR%..") do set PROJECT_ROOT=%%~fI
if "%PYTHONPATH%"=="" (
  set PYTHONPATH=%PROJECT_ROOT%\src
) else (
  set PYTHONPATH=%PROJECT_ROOT%\src;%PYTHONPATH%
)

REM Usage:
REM   run_gateway.bat dry-run "C:\path\to\processed\session"
REM   run_gateway.bat mqtt-tls "C:\path\to\processed\session"
REM
REM Optional environment variables for mqtt-tls:
REM   MQTT_HOST (default 127.0.0.1)
REM   MQTT_PORT (default 8883)
REM   TOPIC_ROOT (default fincadiag/la_esmeralda)
REM   CA_PATH
REM   CERT_PATH
REM   KEY_PATH
REM   TLS_MIN_VERSION (default 1.3)

if "%~1"=="" goto :usage
if "%~2"=="" goto :usage

set MODE=%~1
set SESSION_DIR=%~2

if "%MQTT_HOST%"=="" set MQTT_HOST=127.0.0.1
if "%MQTT_PORT%"=="" set MQTT_PORT=8883
if "%TOPIC_ROOT%"=="" set TOPIC_ROOT=fincadiag/la_esmeralda
if "%TLS_MIN_VERSION%"=="" set TLS_MIN_VERSION=1.3

if /I "%MODE%"=="dry-run" goto :dryrun
if /I "%MODE%"=="mqtt-tls" goto :mqtttls

echo Unknown mode: %MODE%
goto :usage

:dryrun
echo [gateway] mode=dry-run
echo [gateway] session-dir=%SESSION_DIR%
python -m fincadiag.gateway.runtime --session-dir "%SESSION_DIR%" --topic-root "%TOPIC_ROOT%" --dry-run
exit /b %ERRORLEVEL%

:mqtttls
echo [gateway] mode=mqtt-tls
echo [gateway] session-dir=%SESSION_DIR%
echo [gateway] mqtt=%MQTT_HOST%:%MQTT_PORT%
echo [gateway] topic-root=%TOPIC_ROOT%
echo [gateway] tls-min=%TLS_MIN_VERSION%

if "%CA_PATH%"=="" (
  echo ERROR: CA_PATH is not set.
  echo        Set CA_PATH to the broker CA PEM file.
  exit /b 2
)
if "%CERT_PATH%"=="" (
  echo ERROR: CERT_PATH is not set.
  echo        Set CERT_PATH to the client certificate PEM file.
  exit /b 2
)
if "%KEY_PATH%"=="" (
  echo ERROR: KEY_PATH is not set.
  echo        Set KEY_PATH to the client private key PEM file.
  exit /b 2
)

python -m fincadiag.gateway.runtime --session-dir "%SESSION_DIR%" --topic-root "%TOPIC_ROOT%" --mqtt-host "%MQTT_HOST%" --mqtt-port %MQTT_PORT% --tls-enabled --tls-min-version "%TLS_MIN_VERSION%" --ca-path "%CA_PATH%" --cert-path "%CERT_PATH%" --key-path "%KEY_PATH%"
exit /b %ERRORLEVEL%

:usage
echo Usage:
echo   %~nx0 dry-run "C:\path\to\processed\session"
echo   %~nx0 mqtt-tls "C:\path\to\processed\session"
echo.
echo For mqtt-tls, set env vars:
echo   set CA_PATH=...
echo   set CERT_PATH=...
echo   set KEY_PATH=...
echo Optional:
echo   set MQTT_HOST=127.0.0.1
echo   set MQTT_PORT=8883
echo   set TOPIC_ROOT=fincadiag/la_esmeralda
echo   set TLS_MIN_VERSION=1.3
exit /b 1
