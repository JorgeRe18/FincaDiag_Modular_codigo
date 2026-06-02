"""Corre la suite gateway (schema/idempotencia/obj4) para visitas 21-28 de mayo."""
import json, sys, os, subprocess, glob, hashlib, shutil
from pathlib import Path

BASE = r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular'
DATA_DIR = os.path.join(BASE, 'data', 'processed', 'visits')
PUBLISHED_DIR = os.path.join(BASE, 'data', 'gateway', 'published')


def clear_published():
    os.makedirs(PUBLISHED_DIR, exist_ok=True)
    for f in glob.glob(os.path.join(PUBLISHED_DIR, '*')):
        try:
            os.remove(f)
        except Exception:
            pass


def run_dry_run(session_dir):
    env = os.environ.copy()
    env['PYTHONPATH'] = os.path.join(BASE, 'src')
    cmd = [sys.executable, '-m', 'fincadiag.gateway.runtime',
           '--session-dir', session_dir,
           '--topic-root', 'fincadiag/la_esmeralda',
           '--dry-run']
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=BASE, env=env)
    return r.returncode == 0


def get_jsonl_files():
    return glob.glob(os.path.join(PUBLISHED_DIR, '*.jsonl'))


def file_hash(p):
    with open(p, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def test_obj4(session_dir):
    corr = os.path.join(session_dir, 'correlation_summary.json')
    if not os.path.exists(corr):
        return False, 'No correlation_summary.json', None
    with open(corr) as f:
        data = json.load(f)
    eta = data.get('eta_extraccion') or data.get('extraction_efficiency_pct') or data.get('eta')
    raw = data.get('matched_events')
    if raw is None:
        raw = data.get('matches', 0)
    motor_matches = len(raw) if isinstance(raw, list) else (int(raw) if raw else 0)
    jfiles = get_jsonl_files()
    if not jfiles:
        return False, 'No JSONL publicado', None
    with open(jfiles[0]) as f:
        msgs = [json.loads(line) for line in f if line.strip()]
    corr_msg = next((m for m in msgs if m.get('event_type') == 'correlation_summary'), None)
    eta_val = round(float(eta), 2) if eta else None
    if corr_msg is None:
        return False, 'No correlation_summary en JSONL', eta_val
    gw_payload = corr_msg.get('payload', {})
    gw_matches = gw_payload.get('matches', gw_payload.get('matched_events', 0))
    gw_eta = gw_payload.get('eta_extraccion_pct', gw_payload.get('eta_extraccion'))
    if gw_matches == motor_matches:
        return True, "eta=" + str(eta_val) + " matches=" + str(motor_matches), eta_val
    return False, "gw_matches=" + str(gw_matches) + " motor=" + str(motor_matches), eta_val


results = []
for visit_dir in sorted(Path(DATA_DIR).glob('Visita_*_05_2026')):
    day = int(visit_dir.name.split('_')[1])
    if day < 21 or day > 28:
        continue
    for ses_dir in sorted(visit_dir.glob('sesiones/TOMA_*')):
        name = ses_dir.name
        corr_file = ses_dir / 'correlation_summary.json'
        if not corr_file.exists():
            continue
        with open(corr_file) as f:
            cdata = json.load(f)
        raw_m = cdata.get('matched_events')
        if raw_m is None:
            raw_m = cdata.get('matches', 0)
        matches = len(raw_m) if isinstance(raw_m, list) else (int(raw_m) if raw_m else 0)
        if not matches:
            continue

        clear_published()
        ok1 = run_dry_run(str(ses_dir))
        if not ok1:
            results.append({'visit': visit_dir.name, 'session': name,
                            'schema': False, 'idempotency': False, 'objective4': False, 'eta': None})
            print("FAIL dry-run: " + visit_dir.name + " | " + name[:50])
            continue

        hashes1 = {os.path.basename(f): file_hash(f) for f in get_jsonl_files()}
        run_dry_run(str(ses_dir))
        hashes2 = {os.path.basename(f): file_hash(f) for f in get_jsonl_files()}
        idem = hashes1 == hashes2

        schema_ok = len(get_jsonl_files()) > 0
        obj4_ok, obj4_msg, eta_val = test_obj4(str(ses_dir))

        results.append({
            'visit': visit_dir.name,
            'session': name,
            'schema': schema_ok,
            'idempotency': idem,
            'objective4': obj4_ok,
            'eta': eta_val,
            'matches': int(matches),
            'msg': obj4_msg
        })
        print(visit_dir.name + " | " + name[:45] + " | eta=" + str(eta_val) + " obj4=" + str(obj4_ok))

print("\n=== RESUMEN ===")
total = len(results)
schema_pass = sum(1 for r in results if r['schema'])
idem_pass = sum(1 for r in results if r['idempotency'])
obj4_pass = sum(1 for r in results if r['objective4'])
etas = [r['eta'] for r in results if r['eta'] is not None]
print("Total sesiones: " + str(total))
print("Schema PASS: " + str(schema_pass) + "/" + str(total))
print("Idempotencia PASS: " + str(idem_pass) + "/" + str(total))
print("Objetivo 4 PASS: " + str(obj4_pass) + "/" + str(total))
if etas:
    print("eta media: " + str(round(sum(etas)/len(etas), 2)) + "%")
    print("eta min/max: " + str(min(etas)) + "% / " + str(max(etas)) + "%")

out_path = os.path.join(BASE, 'gateway_test_results_21_28.json')
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print("\nGuardado: " + out_path)
