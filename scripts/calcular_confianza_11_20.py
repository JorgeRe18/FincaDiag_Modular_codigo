"""Calcular confianza para sesiones 11-20 mayo para validar formula."""
import json
from pathlib import Path

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits')

def calcular_confianza(baseline_path, corr_path):
    """Confianza = proporcion de matches * ponderacion de calidad de red."""
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
    
    quality_factor = 1.0
    quality_factor *= (1.0 - min(packet_loss, 1.0))
    quality_factor *= max(0.5, 1.0 - min(jitter_ms / 50.0, 0.5))
    quality_factor *= max(0.7, 1.0 - min(lat_media / 300.0, 0.3))
    
    confianza = 0.25 + match_ratio * 0.6 * quality_factor
    
    if matched_events == 0:
        confianza = 0.20 + 0.15 * quality_factor
    
    if match_ratio >= 0.9 and serial_events > 0:
        confianza = min(0.90, confianza + 0.10)
    
    return round(confianza, 2)


sessions_map = {
    (11, 'AM'): 'TOMA_AM__10AM__Captura_20260511_101205',
    (11, 'PM'): 'TOMA_PM__1PM__Captura_20260511_130005',
    (12, 'AM'): 'TOMA_AM__2AM__Captura_20260512_021505',
    (12, 'PM'): 'TOMA_PM__1PM__Captura_20260512_130005',
    (13, 'AM'): 'TOMA_AM__2AM__Captura_20260513_021505',
    (13, 'PM'): 'TOMA_PM__1PM__Captura_20260513_130005',
    (14, 'AM'): 'TOMA_AM__2AM__Captura_20260514_021505',
    (14, 'PM'): 'TOMA_PM__1PM__Captura_20260514_130005',
    (15, 'PM'): 'TOMA_PM__1PM__Captura_20260515_130005',
    (16, 'PM'): 'TOMA_PM__1PM__Captura_20260516_130005',
    (17, 'AM'): 'TOMA_AM__2AM__Captura_20260517_021505',
    (18, 'AM'): 'TOMA_AM__2AM__Captura_20260518_021505',
    (19, 'PM'): 'TOMA_PM__1PM__Captura_20260519_130005',
    (20, 'AM'): 'TOMA_AM__2AM__Captura_20260520_021505',
}

# Valores en la tabla actual
tabla_valores = {
    '11/05 AM': 0.48,
    '11/05 PM': 0.69,
    '12/05 AM': 0.75,
    '12/05 PM': 0.51,
    '13/05 AM': 0.55,
    '13/05 PM': 0.62,
    '14/05 AM': 0.52,
    '14/05 PM': 0.53,
    '15/05 PM': 0.59,
    '16/05 PM': 0.69,
    '17/05 AM': 0.48,
    '18/05 AM': 0.51,
    '19/05 PM': 0.43,
    '20/05 AM': 0.38,
}

print("Validacion formula confianza vs tabla actual (11-20):")
print(f"{'Sesion':<12} {'Calc':<6} {'Tabla':<6} {'Diff':<6}")
print("-" * 32)

for (day, turn), session_name in sessions_map.items():
    visit_dir = BASE / f'Visita_{day:02d}_05_2026'
    session_dir = visit_dir / 'sesiones' / session_name
    baseline_path = session_dir / 'baseline_summary.json'
    corr_path = session_dir / 'correlation_summary.json'
    
    conf = calcular_confianza(baseline_path, corr_path)
    key = f"{day:02d}/05 {turn}"
    tabla = tabla_valores.get(key, 'N/D')
    diff = round(conf - tabla, 2) if isinstance(tabla, float) else 'N/D'
    print(f"{key:<12} {conf:<6} {tabla:<6} {diff:<6}")
