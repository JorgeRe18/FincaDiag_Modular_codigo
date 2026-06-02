"""
Suite de pruebas gateway implementada en Python (reemplaza .bat files).
Valida: schema JSON, idempotencia, y métricas Objetivo 4.
"""
import json, sys, os, subprocess, glob, hashlib
from pathlib import Path

BASE = r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular'
PUBLISHED_DIR = os.path.join(BASE, 'data', 'gateway', 'published')


def run_dry_run(session_dir):
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.join(BASE, 'src')
    cmd = [
        sys.executable, '-m', 'fincadiag.gateway.runtime',
        '--session-dir', session_dir,
        '--topic-root', 'fincadiag/la_esmeralda',
        '--dry-run'
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE, env=env)
    return result.returncode == 0


def get_readable_json():
    files = glob.glob(os.path.join(PUBLISHED_DIR, '*.readable.json'))
    return files[0] if files else None


def get_jsonl_files():
    return glob.glob(os.path.join(PUBLISHED_DIR, '*.jsonl'))


def file_hash(path):
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def test_schema(session_dir):
    readable = get_readable_json()
    if not readable:
        return False, 'No se genero .readable.json'

    with open(readable) as f:
        data = json.load(f)

    errors = []
    for field in ['batch_name', 'message_count', 'counts_by_event_type', 'messages_by_event_type']:
        if field not in data:
            errors.append(f'Falta campo: {field}')

    counts = data.get('counts_by_event_type', {})
    if data.get('message_count') != sum(counts.values()):
        errors.append(f'message_count != sum(counts)')

    required = ['session_summary', 'baseline_snapshot', 'pcap_summary',
                'alerts_summary', 'collar_summary', 'correlation_summary',
                'field_validation_summary']
    for t in required:
        if t not in counts:
            errors.append(f'Falta tipo: {t}')

    cow_events = data.get('messages_by_event_type', {}).get('cow_event', [])
    for idx, ev in enumerate(cow_events):
        payload = ev.get('payload', {})
        for f in ['batch_id', 'slot_index', 'event_id', 'c2_timestamp', 'status']:
            if f not in payload:
                errors.append(f'cow_event[{idx}] falta: {f}')

    if errors:
        return False, '; '.join(errors[:5])
    return True, f'message_count={data.get("message_count")}, cow_events={len(cow_events)}'


def test_idempotency(session_dir):
    jsonl1 = {}
    for j in get_jsonl_files():
        jsonl1[os.path.basename(j)] = file_hash(j)

    # Clean and re-run
    for j in get_jsonl_files():
        os.remove(j)
    for r in glob.glob(os.path.join(PUBLISHED_DIR, '*.readable.json')):
        os.remove(r)

    ok = run_dry_run(session_dir)
    if not ok:
        return False, 'Segunda corrida fallo'

    jsonl2 = {}
    for j in get_jsonl_files():
        jsonl2[os.path.basename(j)] = file_hash(j)

    if jsonl1 != jsonl2:
        missing1 = set(jsonl1.keys()) - set(jsonl2.keys())
        missing2 = set(jsonl2.keys()) - set(jsonl1.keys())
        mismatched = [k for k in jsonl1 if k in jsonl2 and jsonl1[k] != jsonl2[k]]
        return False, f'diferencias: missing={missing1|missing2}, mismatched={mismatched}'

    return True, f'{len(jsonl1)} archivos identicos'


def test_objective4(session_dir):
    corr_path = os.path.join(session_dir, 'correlation_summary.json')
    if not os.path.exists(corr_path):
        return False, 'No existe correlation_summary.json'

    with open(corr_path) as f:
        motor = json.load(f)

    readable = get_readable_json()
    if not readable:
        return False, 'No se genero .readable.json'

    with open(readable) as f:
        gw = json.load(f)

    gw_corr = None
    for msg in gw.get('messages_by_event_type', {}).get('correlation_summary', []):
        gw_corr = msg.get('payload', {})
        break

    if not gw_corr:
        return False, 'correlation_summary no encontrado en gateway'

    motor_eta = motor.get('eta_extraccion')
    gw_eta = gw_corr.get('eta_extraccion_pct')
    motor_matches = motor.get('matched_events', -1)
    gw_matches = gw_corr.get('matches', -1)
    serial_events = motor.get('serial_events', 0)

    errors = []
    if serial_events == 0:
        errors.append('serial_events=0')
    if motor_eta is None:
        errors.append('motor sin eta')
    if gw_eta is None:
        errors.append('gateway sin eta')
    if motor_eta is not None and gw_eta is not None:
        if abs(float(motor_eta) - float(gw_eta)) > 0.01:
            errors.append(f'divergencia eta: motor={motor_eta} vs gw={gw_eta}')
    if motor_matches >= 0 and gw_matches >= 0:
        if motor_matches != gw_matches:
            errors.append(f'divergencia matches: motor={motor_matches} vs gw={gw_matches}')

    if errors:
        return False, '; '.join(errors)
    return True, f'eta={motor_eta}, matches={motor_matches}'


def clean_published():
    for f in glob.glob(os.path.join(PUBLISHED_DIR, '*')):
        os.remove(f)


def run_suite(session_dir):
    clean_published()

    # Dry-run inicial
    if not run_dry_run(session_dir):
        return {'schema': (False, 'dry-run fallo'), 'idempotency': (False, 'dry-run fallo'), 'objective4': (False, 'dry-run fallo')}

    schema_ok, schema_msg = test_schema(session_dir)
    idem_ok, idem_msg = test_idempotency(session_dir)

    # Re-run dry-run para objective4 (idempotency lo limpio)
    clean_published()
    if not run_dry_run(session_dir):
        obj4_ok, obj4_msg = False, 'dry-run fallo'
    else:
        obj4_ok, obj4_msg = test_objective4(session_dir)

    return {
        'schema': (schema_ok, schema_msg),
        'idempotency': (idem_ok, idem_msg),
        'objective4': (obj4_ok, obj4_msg)
    }


def main():
    visits = ['Visita_{:02d}_05_2026'.format(i) for i in range(11, 21)]

    # Identificar mejor sesion por visita
    sessions = []
    for v in visits:
        sesiones_dir = os.path.join(BASE, 'data', 'processed', 'visits', v, 'sesiones')
        pattern = os.path.join(sesiones_dir, '*', 'correlation_summary.json')
        files = glob.glob(pattern)
        best_session = None
        best_matches = -1
        for f in files:
            try:
                with open(f) as fh:
                    corr = json.load(fh)
                matches = corr.get('matched_events', 0)
                if matches > best_matches:
                    best_matches = matches
                    best_session = os.path.dirname(f)
            except:
                continue
        if best_session:
            sessions.append((v, best_session, best_matches))

    print(f'Sesiones a probar: {len(sessions)}')
    all_results = []

    for visit, session_dir, matches in sessions:
        print(f'\n=== {visit} | {os.path.basename(session_dir)} (matches={matches}) ===')
        results = run_suite(session_dir)

        for test_name, (ok, msg) in results.items():
            status = 'PASS' if ok else 'FAIL'
            print(f'  [{status}] {test_name}: {msg}')

        all_results.append({
            'visit': visit,
            'session': os.path.basename(session_dir),
            'matches': matches,
            'results': {k: {'pass': v[0], 'msg': v[1]} for k, v in results.items()}
        })

    print('\n=== RESUMEN ===')
    for r in all_results:
        visit = r['visit']
        s = r['results']['schema']['pass']
        i = r['results']['idempotency']['pass']
        o = r['results']['objective4']['pass']
        overall = 'PASS' if s and i and o else 'FAIL'
        print(f'{visit}: schema={s}, idempotency={i}, objective4={o} -> {overall}')

    out_path = os.path.join(BASE, 'gateway_test_results_11_20.json')
    with open(out_path, 'w') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f'\nResultados guardados en {out_path}')


if __name__ == '__main__':
    main()
