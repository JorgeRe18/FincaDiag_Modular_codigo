@echo off
chcp 65001 >nul
:: Prueba 6: Validacion de metricas Objetivo 4
:: Compara η del motor (correlation_summary.json) contra η reportado por el gateway.
:: Tambien valida que serial_events > 0 para sesiones incluidas en el contraste.
::
:: Uso: validate_objective4.bat ^<ruta_sesion_procesada^>

set "SESSION_DIR=%1"
if "%SESSION_DIR%"=="" (
    echo Uso: validate_objective4.bat ^<ruta_sesion_procesada^>
    exit /b 1
)

set "PYTHONPATH=%~dp0..\..\src"
set "CORR_FILE=%SESSION_DIR%\correlation_summary.json"

echo === Validacion Objetivo 4: %SESSION_DIR% ===

:: 1. Verificar que correlation_summary.json existe
if not exist "%CORR_FILE%" (
    echo [FAIL] No existe correlation_summary.json
    exit /b 1
)

:: 2. Correr gateway dry-run
python -m fincadiag.gateway.runtime --session-dir "%SESSION_DIR%" --topic-root "fincadiag/la_esmeralda" --dry-run >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Gateway dry-run fallo
    exit /b 1
)

:: 3. Extraer metricas del motor
for %%f in ("%~dp0..\..\data\gateway\published\*.readable.json") do set "READABLE=%%f"

python -c "
import json, sys

# Leer correlation_summary.json del motor
with open(r'%CORR_FILE%') as f:
    motor = json.load(f)

# Leer readable.json del gateway
with open(r'%READABLE%') as f:
    gw = json.load(f)

# Encontrar correlation_summary en el gateway
gw_corr = None
for msg in gw.get('messages_by_event_type', {}).get('correlation_summary', []):
    gw_corr = msg.get('payload', {})
    break

if not gw_corr:
    print('[FAIL] correlation_summary no encontrado en salida del gateway')
    sys.exit(1)

motor_eta = motor.get('eta_extraccion')
gw_eta = gw_corr.get('eta_extraccion_pct')
motor_matches = motor.get('matched_events', -1)
gw_matches = gw_corr.get('matches', -1)
serial_events = motor.get('serial_events', 0)

print(f'  Motor:   eta={motor_eta}, matched={motor_matches}, serial_events={serial_events}')
print(f'  Gateway: eta={gw_eta}, matches={gw_matches}')

errors = []
if serial_events == 0:
    errors.append('serial_events=0 (sesion no apta para contraste Objetivo 4)')
if motor_eta is None:
    errors.append('Motor no reporta eta')
if gw_eta is None:
    errors.append('Gateway no reporta eta')
if motor_eta is not None and gw_eta is not None:
    if abs(float(motor_eta) - float(gw_eta)) > 0.01:
        errors.append(f'Divergencia eta: motor={motor_eta} vs gateway={gw_eta}')
if motor_matches >= 0 and gw_matches >= 0:
    if motor_matches != gw_matches:
        errors.append(f'Divergencia matches: motor={motor_matches} vs gateway={gw_matches}')

if errors:
    for e in errors: print(f'  [FAIL] {e}')
    sys.exit(1)
else:
    print('  [PASS] Metricas consistentes')
" || (
    echo [FAIL] Error en validacion Python
    exit /b 1
)

echo [PASS] Validacion Objetivo 4 completada.
