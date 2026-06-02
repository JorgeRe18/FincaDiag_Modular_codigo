"""Ajustar formula de confianza para alinear con valores de tabla 11-20."""
import json
from pathlib import Path
import numpy as np
from numpy.polynomial import polynomial as P

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits')

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

sessions_map = {
    (11, 'AM'): ('Visita_11_05_2026', 'TOMA_AM__10AM__Captura_20260511_101205'),
    (11, 'PM'): ('Visita_11_05_2026', 'TOMA_PM__1PM__Captura_20260511_130005'),
    (12, 'AM'): ('Visita_12_05_2026', 'TOMA_AM__2AM__Captura_20260512_021505'),
    (12, 'PM'): ('Visita_12_05_2026', 'TOMA_PM__1PM__Captura_20260512_130005'),
    (13, 'AM'): ('Visita_13_05_2026', 'TOMA_AM__2AM__Captura_20260513_021505'),
    (13, 'PM'): ('Visita_13_05_2026', 'TOMA_PM__1PM__Captura_20260513_130005'),
    (14, 'AM'): ('Visita_14_05_2026', 'TOMA_AM__2AM__Captura_20260514_021505'),
    (14, 'PM'): ('Visita_14_05_2026', 'TOMA_PM__1PM__Captura_20260514_130005'),
    (15, 'PM'): ('Visita_15_05_2026', 'TOMA_PM__1PM__Captura_20260515_130005'),
    (16, 'PM'): ('Visita_16_05_2026', 'TOMA_PM__1PM__Captura_20260516_130005'),
    (17, 'AM'): ('Visita_17_05_2026', 'TOMA_AM__2AM__Captura_20260517_021505'),
    (18, 'AM'): ('Visita_18_05_2026', 'TOMA_AM__2AM__Captura_20260518_021505'),
    (19, 'PM'): ('Visita_19_05_2026', 'TOMA_PM__1PM__Captura_20260519_130005'),
    (20, 'AM'): ('Visita_20_05_2026', 'TOMA_AM__2AM__Captura_20260520_021505'),
}

# Extraer features
X = []
y = []
session_names = []

for (day, turn), (visit, session) in sessions_map.items():
    key = f"{day:02d}/05 {turn}"
    conf = tabla_valores[key]
    
    session_dir = BASE / visit / 'sesiones' / session
    baseline_path = session_dir / 'baseline_summary.json'
    corr_path = session_dir / 'correlation_summary.json'
    
    lat, jitter, loss, nodos = 60.0, 10.0, 0.0, 2
    has_baseline = False
    if baseline_path.exists():
        with open(baseline_path) as f:
            bl = json.load(f)
        pre = bl.get('baseline_pre_summary', {})
        lat = pre.get('lat_media', 60.0) or 60.0
        jitter = pre.get('jitter_ms', 10.0) or 10.0
        loss = pre.get('packet_loss', 0.0) or 0.0
        nodos = pre.get('nodos_dinamicos', 2) or 2
        if lat > 0:
            has_baseline = True
    
    matched, serial_events, mode = 0, 0, ''
    has_corr = False
    if corr_path.exists():
        with open(corr_path) as f:
            corr = json.load(f)
        matched = corr.get('matched_events', 0)
        serial_events = corr.get('serial_events', 0)
        mode = corr.get('network_mode', '')
        has_corr = True
    
    match_ratio = matched / serial_events if serial_events > 0 else 0
    has_matches = 1 if matched > 0 else 0
    is_firma = 1 if mode == 'firma_56d100' else 0
    
    # Features: [has_baseline, has_matches, match_ratio, is_firma, lat, jitter, nodos]
    features = [has_baseline, has_matches, match_ratio, is_firma, lat, jitter, nodos]
    X.append(features)
    y.append(conf)
    session_names.append(key)

X = np.array(X)
y = np.array(y)

# Simple linear regression: find coeffs that minimize MSE
# Add bias term
Xb = np.column_stack([np.ones(len(X)), X])

# Solve least squares
coeffs, residuals, rank, s = np.linalg.lstsq(Xb, y, rcond=None)

print("Coeficientes de regresion lineal:")
labels = ['bias', 'has_baseline', 'has_matches', 'match_ratio', 'is_firma', 'lat', 'jitter', 'nodos']
for label, c in zip(labels, coeffs):
    print(f"  {label:<15}: {c:+.4f}")

print(f"\nResiduals: {residuals}")

# Predict and compare
print(f"\n{'Sesion':<12} {'Real':<6} {'Pred':<6} {'Diff':<6}")
print("-" * 32)
for i, name in enumerate(session_names):
    pred = np.dot(Xb[i], coeffs)
    pred = max(0.20, min(0.90, pred))  # clip
    diff = y[i] - pred
    print(f"{name:<12} {y[i]:<6.2f} {pred:<6.2f} {diff:<+6.2f}")
