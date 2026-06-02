@echo off
setlocal enableextensions enabledelayedexpansion

set CA_PATH=C:\mqtt-lab\certs\ca.crt
set CERT_PATH=C:\mqtt-lab\certs\client.crt
set KEY_PATH=C:\mqtt-lab\certs\client.key
set MQTT_HOST=localhost
set MQTT_PORT=8883
set TOPIC_ROOT=fincadiag/la_esmeralda
set TLS_MIN_VERSION=1.3

Gateway\run_gateway.bat mqtt-tls "data\processed\visits\Visita_06_04_2026_PM\sesiones\Visita_06_04_2026__TOMA_PM__1PM__Captura_20260406_125505"
