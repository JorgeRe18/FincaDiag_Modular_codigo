"""Calcular confianza media a partir de baseline y correlacion para sesiones 21-27 mayo."""
import json
import re
from pathlib import Path

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits')

def calcular_confianza(baseline_path, corr_path):
    """Confianza = proporcion de matches * ponderacion de calidad de red."""
    # Leer baseline
    lat_media = 60.0
    jitter_ms = 10.0
    packet_loss = 0.0
    nodos = 2
    
    if baseline_path.exists():
        try:
            with open(baseline_path, 'r', encoding='utf-8') as f:
                bl = json.load(f)
            pre = bl.get('baseline_pre_summary', {})
            lat_media = pre.get('lat_media', 60.0) or 60.0
            jitter_ms = pre.get('jitter_ms', 10.0) or 10.0
            packet_loss = pre.get('packet_loss', 0.0) or 0.0
            nodos = pre.get('nodos_dinamicos', 2) or 2
        except Exception:
            pass
    
    # Leer correlacion
    serial_events = 0
    matched_events = 0
    if corr_path.exists():
        try:
            with open(corr_path, 'r', encoding='utf-8') as f:
                corr = json.load(f)
            serial_events = corr.get('serial_events', 0)
            matched_events = corr.get('matched_events', 0)
        except Exception:
            pass
    
    if serial_events == 0:
        match_ratio = 0.0
    else:
        match_ratio = matched_events / serial_events
    
    # Ponderadores de calidad de red (baseline)
    # Menor latencia = mejor, menor jitter = mejor, 0 packet_loss = mejor
    quality_factor = 1.0
    quality_factor *= (1.0 - min(packet_loss, 1.0))  # packet_loss penaliza
    quality_factor *= max(0.5, 1.0 - min(jitter_ms / 50.0, 0.5))  # jitter penaliza suave
    quality_factor *= max(0.7, 1.0 - min(lat_media / 300.0, 0.3))  # latencia penaliza muy suave
    
    # Confianza base = match_ratio * quality_factor, escalado a rango 0.25-0.85
    confianza = 0.25 + match_ratio * 0.6 * quality_factor
    
    # Sesiones sin matches: penalizar mas fuerte
    if matched_events == 0:
        confianza = 0.20 + 0.15 * quality_factor
    
    # Sesiones con match perfecto (100%): bonificar
    if match_ratio >= 0.9 and serial_events > 0:
        confianza = min(0.90, confianza + 0.10)
    
    return round(confianza, 2)


# Mapeo de sesiones principales por dia/turno
sessions_map = {
    (21, 'AM'): 'TOMA_AM__2AM__Captura_20260521_021505',
    (21, 'PM'): 'TOMA_PM__1PM__Captura_20260521_130005',
    (22, 'AM'): 'TOMA_AM__2AM__Captura_20260522_021505',
    (22, 'PM'): 'TOMA_PM__1PM__Captura_20260522_130005',
    (23, 'AM'): 'TOMA_AM__2AM__Captura_20260523_021505',
    (23, 'PM'): 'TOMA_PM__1PM__Captura_20260523_130005',
    (24, 'AM'): 'TOMA_AM__2AM__Captura_20260524_021505',
    (24, 'PM'): 'TOMA_PM__1PM__Captura_20260524_130005',
    (25, 'AM'): 'TOMA_AM__2AM__Captura_20260525_021505',
    (25, 'PM'): 'TOMA_PM__1PM__Captura_20260525_130005',
    (26, 'AM'): 'TOMA_AM__2AM__Captura_20260526_021506',
    (26, 'PM'): 'TOMA_PM__1PM__Captura_20260526_130201',
    (27, 'AM'): 'TOMA_AM__2AM__Captura_20260527_021505',
    (27, 'PM'): 'TOMA_PM__1PM__Captura_20260527_130005',
}

print("Confianzas calculadas para sesiones 21-27:")
for (day, turn), session_name in sessions_map.items():
    visit_dir = BASE / f'Visita_{day:02d}_05_2026'
    session_dir = visit_dir / 'sesiones' / session_name
    baseline_path = session_dir / 'baseline_summary.json'
    corr_path = session_dir / 'correlation_summary.json'
    
    conf = calcular_confianza(baseline_path, corr_path)
    print(f"  {day:02d}/05 {turn}: confianza = {conf}")
