#!/bin/bash
# Script para ejecutar en Raspberry Pi
# Correr dry-run de las 4 sesiones de ordeño completo (15/05 y 16/05)

cd ~/fincadiag_modular
export PYTHONPATH=~/fincadiag_modular/src
export TOPIC_ROOT=fincadiag/la_esmeralda

echo "=== 15/05 AM 2AM ==="
python3 -m fincadiag.gateway.runtime \
  --session-dir "data/processed/visits/Visita_15_05_2026/sesiones/TOMA_AM__2AM__Captura_20260515_021505" \
  --topic-root "$TOPIC_ROOT" \
  --dry-run

echo ""
echo "=== 15/05 PM 1PM ==="
python3 -m fincadiag.gateway.runtime \
  --session-dir "data/processed/visits/Visita_15_05_2026/sesiones/TOMA_PM__1PM__Captura_20260515_130005" \
  --topic-root "$TOPIC_ROOT" \
  --dry-run

echo ""
echo "=== 16/05 AM 2AM ==="
python3 -m fincadiag.gateway.runtime \
  --session-dir "data/processed/visits/Visita_16_05_2026/sesiones/TOMA_AM__2AM__Captura_20260516_021505" \
  --topic-root "$TOPIC_ROOT" \
  --dry-run

echo ""
echo "=== 16/05 PM 1PM ==="
python3 -m fincadiag.gateway.runtime \
  --session-dir "data/processed/visits/Visita_16_05_2026/sesiones/TOMA_PM__1PM__Captura_20260516_130005" \
  --topic-root "$TOPIC_ROOT" \
  --dry-run

echo ""
echo "=== 17/05 AM 2AM ==="
python3 -m fincadiag.gateway.runtime \
  --session-dir "data/processed/visits/Visita_17_05_2026/sesiones/TOMA_AM__2AM__Captura_20260517_021505" \
  --topic-root "$TOPIC_ROOT" \
  --dry-run

echo ""
echo "=== 17/05 PM 1PM ==="
python3 -m fincadiag.gateway.runtime \
  --session-dir "data/processed/visits/Visita_17_05_2026/sesiones/TOMA_PM__1PM__Captura_20260517_130005" \
  --topic-root "$TOPIC_ROOT" \
  --dry-run

echo ""
echo "Done."
