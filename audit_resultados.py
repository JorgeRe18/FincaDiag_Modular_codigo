"""Audit completo de resultados de pruebas gateway - qué hay, qué falta, qué fechas."""
import json
from pathlib import Path

BASE = Path('C:/Users/jorge/OneDrive/Documentos/FincaDiag_Modular')

print("=" * 70)
print("AUDIT DE RESULTADOS GATEWAY - ¿QUÉ HAY Y DE QUÉ FECHAS?")
print("=" * 70)

# --- 1. DATOS DEL MOTOR (procesamiento) ---
print("\n[1] SESIONES PROCESADAS POR EL MOTOR (correlation_summary.json)")
print("    Fuente: data/processed/visits/")
data_dir = BASE / 'data' / 'processed' / 'visits'
motor_by_day = {}
for visit_dir in sorted(data_dir.glob('Visita_*_05_2026')):
    day = int(visit_dir.name.split('_')[1])
    sessions_with_matches = []
    for ses in visit_dir.glob('sesiones/*/correlation_summary.json'):
        if 'BASELINE' in ses.parent.name:
            continue
        d = json.loads(ses.read_text())
        raw = d.get('matched_events')
        if raw is None:
            raw = d.get('matches', 0)
        matches = len(raw) if isinstance(raw, list) else (int(raw) if raw else 0)
        eta = d.get('eta_extraccion') or d.get('eta_extraccion_pct')
        if matches > 0:
            sessions_with_matches.append({'session': ses.parent.name, 'matches': matches, 'eta': round(float(eta),2) if eta else None})
    if sessions_with_matches:
        motor_by_day[day] = sessions_with_matches

for day in sorted(motor_by_day):
    sessions = motor_by_day[day]
    print(f"    Mayo {day:02d}: {len(sessions)} sesión(es) con matches")

total_motor = sum(len(v) for v in motor_by_day.values())
print(f"    TOTAL sesiones motor: {total_motor} en {len(motor_by_day)} visitas (Mayo 11-28)")

# --- 2. PRUEBAS WINDOWS (dry-run: schema + idempotencia + obj4) ---
print("\n[2] PRUEBAS WINDOWS (schema + idempotencia + obj4)")
win_results = {}

f1 = BASE / 'gateway_test_results_11_20.json'
if f1.exists():
    data = json.loads(f1.read_text())
    for r in data:
        day = int(r['visit'].split('_')[1])
        win_results[day] = {
            'schema': r['results']['schema']['pass'],
            'idempotency': r['results']['idempotency']['pass'],
            'objective4': r['results']['objective4']['pass'],
            'eta': r['results']['objective4']['msg']
        }
    print(f"    Archivo: gateway_test_results_11_20.json → {len(data)} visitas (Mayo 11-20)")

f2 = BASE / 'gateway_test_results_21_28.json'
if f2.exists():
    data2 = json.loads(f2.read_text())
    for r in data2:
        day = int(r['visit'].split('_')[1])
        if day not in win_results:
            win_results[day] = {'schema': r['schema'], 'idempotency': r['idempotency'], 'objective4': r['objective4'], 'eta': r.get('msg','')}
    print(f"    Archivo: gateway_test_results_21_28.json → {len(data2)} sesiones (Mayo 21-28)")

for day in sorted(win_results):
    r = win_results[day]
    print(f"    Mayo {day:02d}: schema={'PASS' if r['schema'] else 'FAIL'} idem={'PASS' if r['idempotency'] else 'FAIL'} obj4={'PASS' if r['objective4'] else 'FAIL'}")

# --- 3. PRUEBAS Pi (TLS + resilience + subscribe + idempotencia) ---
print("\n[3] PRUEBAS RASPBERRY PI (TLS + resiliencia + suscripción + idempotencia)")
pi_file = BASE / 'consolidado_11_20_mayo_final.json'
if pi_file.exists():
    c = json.loads(pi_file.read_text())
    pi_results = c['pruebas_raspberry_pi']['resultados']
    print(f"    Archivo: consolidado_11_20_mayo_final.json → {len(pi_results)} visitas")
    for r in pi_results:
        day = int(r['visit'].split('_')[1])
        print(f"    Mayo {day:02d}: schema={r['schema']} tls={r['tls']} resilience={r['resilience']} subscribe={r['subscribe']} obj4={r['objective4']}")

pi_tonight = BASE / 'pi_test_results_29may.json'
if pi_tonight.exists():
    pt = json.loads(pi_tonight.read_text())
    print(f"    Archivo: pi_test_results_29may.json → sesión Mayo 18 PM (29/05/2026)")
    for k, v in pt['pruebas'].items():
        print(f"    {k}: {'PASS' if v['pass'] else 'FAIL'}")

# --- 4. QUÉ FALTA ---
print("\n[4] COBERTURA - QUÉ TIENE PRUEBAS Pi Y QUÉ SOLO TIENE WINDOWS")
print("    (Las pruebas Pi cubren TLS/resilience/subscribe - solo se corrieron para 11-20)")
all_days = sorted(motor_by_day.keys())
for day in all_days:
    has_win = day in win_results
    has_pi = day <= 20  # consolidado cubre 11-20
    print(f"    Mayo {day:02d}: Motor=✓  Windows={'✓' if has_win else '✗'}  Pi={'✓' if has_pi else '(no corrido)'}")

print("\n[5] RESUMEN FINAL")
print(f"    Período: Mayo 11-28, {len(all_days)} visitas, {total_motor} sesiones con correlación")
print(f"    Pruebas Windows completas: Mayo 11-28 ({len(win_results)} visitas)")
print(f"    Pruebas Pi completas: Mayo 11-20 (10 visitas) + sesión spot May18 PM")
print(f"    Pruebas Pi Mayo 21-28: NO corridas formalmente (datos del motor sí existen)")
