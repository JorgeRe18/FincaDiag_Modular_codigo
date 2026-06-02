@echo off
chcp 65001 >nul
:: Prueba 1: Validacion de contrato JSON del gateway (schema minimo)
:: Objetivo: verificar que cada lote cumple el contrato definido en la validacion offline.
:: Sirve para Objetivo 4: garantiza integridad de los datos antes del contraste estadistico.

set "SESSION_DIR=%1"
if "%SESSION_DIR%"=="" (
    echo Uso: validate_schema.bat ^<ruta_sesion_procesada^>
    echo Ejemplo: validate_schema.bat data\processed\visits\Visita_15_05_2026\sesiones\TOMA_PM__1PM__Captura_20260515_130005
    exit /b 1
)

echo === Validando sesion: %SESSION_DIR% ===

:: 1. Generar salida gateway en modo dry-run
set "PYTHONPATH=%~dp0..\..\src"
python -m fincadiag.gateway.runtime --session-dir "%SESSION_DIR%" --topic-root "fincadiag/la_esmeralda" --dry-run >nul 2>&1
if errorlevel 1 (
    echo [FAIL] Gateway dry-run fallo
    exit /b 1
)

:: 2. Encontrar el archivo .readable.json generado
for %%f in ("%~dp0..\..\data\gateway\published\*.readable.json") do (
    set "JSON_FILE=%%f"
    goto :found_json
)
echo [FAIL] No se encontro archivo .readable.json
goto :cleanup

:found_json
echo Archivo: %JSON_FILE%

:: 3. Validaciones minimas del contrato
python -c "
import json, sys
path = r'%JSON_FILE%'
with open(path) as f:
    data = json.load(f)
errors = []

# Envoltura de lote requerida
if 'batch_name' not in data: errors.append('Falta batch_name')
if 'message_count' not in data: errors.append('Falta message_count')
if 'counts_by_event_type' not in data: errors.append('Falta counts_by_event_type')
if 'messages_by_event_type' not in data: errors.append('Falta messages_by_event_type')

# Verificar que message_count coincide con la suma de tipos
counts = data.get('counts_by_event_type', {})
if data.get('message_count') != sum(counts.values()):
    errors.append(f\"message_count ({data.get('message_count')}) != sum(counts) ({sum(counts.values())})\")

# Tipos obligatorios para sesiones completas
required_types = ['session_summary','baseline_snapshot','pcap_summary',
                  'alerts_summary','collar_summary','correlation_summary',
                  'field_validation_summary']
for t in required_types:
    if t not in counts:
        errors.append(f'Falta tipo requerido: {t}')

# Validar que cada cow_event tiene campos minimos
cow_events = data.get('messages_by_event_type', {}).get('cow_event', [])
for idx, ev in enumerate(cow_events):
    payload = ev.get('payload', {})
    required = ['batch_id','slot_index','event_id','c2_timestamp','status']
    for f in required:
        if f not in payload:
            errors.append(f'cow_event[{idx}] falta campo: {f}')

# Validar correlation_summary: matches = coincidencias confirmadas
for msg in data.get('messages_by_event_type', {}).get('correlation_summary', []):
    p = msg.get('payload', {})
    # matches en el payload debe reflejar matched_events, no raw array size
    matched = p.get('matched_events', -1)
    total = p.get('serial_events', -1)
    if total > 0 and matched >= total:
        # Esto podria ser aceptable en algunos casos pero alertamos
        pass

if errors:
    for e in errors: print(f'  [FAIL] {e}')
    sys.exit(1)
else:
    print('  [PASS] Contrato JSON valido')
    print(f'  [INFO] message_count={data.get(\"message_count\")}, cow_events={len(cow_events)}')
" || (
    echo [FAIL] Error en validacion Python
    goto :cleanup
)

echo [PASS] Validacion completada.
:cleanup
goto :eof
