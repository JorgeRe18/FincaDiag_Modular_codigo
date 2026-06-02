"""Generar coordenadas TikZ exactas para figura eta_temporal."""
# Mapeo de sesiones a dias desde 10 abril 2026
# 10 abril = dia 0
# 11 mayo = dia 31, 12 mayo = 32, ..., 27 mayo = 47

# Datos EXACTOS del Excel (post_250), ordenados cronologicamente
sesiones = [
    ("11_05 AM", 31, 0.0), ("11_05 PM", 31, 24.24),
    ("12_05 AM", 32, 38.46), ("12_05 PM", 32, 19.05),
    ("13_05 AM", 33, 18.18), ("13_05 PM", 33, 21.05),
    ("14_05 AM", 34, 23.53), ("14_05 PM", 34, 0.0),
    ("15_05 AM", 35, 35.71), ("15_05 PM", 35, 27.91),
    ("16_05 AM", 36, 16.67), ("16_05 PM", 36, 33.33),
    ("17_05 AM", 37, 27.27), ("17_05 PM", 37, 0.0),
    ("18_05 AM", 38, 25.0), ("18_05 PM", 38, 33.33),
    ("19_05 AM", 39, 16.67), ("19_05 PM", 39, 37.5), ("19_05 PM_2", 39, 13.79), ("19_05 PM_3", 39, 37.5),
    ("20_05 AM", 40, 8.33), ("20_05 PM", 40, 0.0),
    ("21_05 AM", 41, 16.67), ("21_05 PM", 41, 26.67),
    ("22_05 AM", 42, 100.0), ("22_05 PM", 42, 15.79),
    ("23_05 AM", 43, 20.83), ("23_05 PM", 43, 16.67),
    ("24_05 AM", 44, 41.18), ("24_05 PM", 44, 16.67),
    ("25_05 AM", 45, 0.0), ("25_05 PM", 45, 58.33),
    ("26_05 PM", 46, 16.67), ("26_05 AM", 46, 16.67), ("26_05 PM_2", 46, 16.67), ("26_05 PM_3", 46, 13.64),
    ("27_05 AM", 47, 24.0), ("27_05 PM", 47, 8.33)
]

# Nota: algunos dias tienen multiples sesiones (diferentes turnos)
# Para evitar solapamiento visual, añadimos pequeno offset al eje x para sesiones del mismo dia

coords = []
from collections import Counter
dia_counts = Counter()
for nombre, dia, eta in sesiones:
    dia_counts[dia] += 1

dia_current = {}
for nombre, dia, eta in sesiones:
    if dia not in dia_current:
        dia_current[dia] = 0
    offset = (dia_current[dia] - (dia_counts[dia]-1)/2) * 0.15
    dia_current[dia] += 1
    x = dia + offset
    coords.append((x, eta, nombre))

print("Coordenadas TikZ (estrellas extendidas):")
print("\\addplot[only marks, mark=star, mark size=4pt, draw=GatewayControlBorder, fill=GatewayControlFill, very thick]")
print("coordinates {")
for x, eta, nombre in coords:
    print(f"({x:.2f},{eta:.2f})  % {nombre}")
print("};")

print(f"\nTotal puntos: {len(coords)}")
print(f"Dias cubiertos: 31-47 (11-27 mayo)")
print(f"xmax necesario: 48")
