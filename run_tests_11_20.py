import os, sys, subprocess, glob, json, time

base = r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular'
sys.path.insert(0, os.path.join(base, 'src'))

published_dir = os.path.join(base, 'data', 'gateway', 'published')

visits = ['Visita_{:02d}_05_2026'.format(i) for i in range(11, 21)]

sessions_to_test = []
for v in visits:
    sesiones_dir = os.path.join(base, 'data', 'processed', 'visits', v, 'sesiones')
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
        sessions_to_test.append((v, best_session, best_matches))

print(f'Sesiones a probar: {len(sessions_to_test)}')

env = os.environ.copy()
env['PYTHONPATH'] = os.path.join(base, 'src')

test_script = os.path.join(base, 'Gateway', 'tests', 'run_all_tests.bat')

all_results = []
for visit, session_dir, matches in sessions_to_test:
    print(f'\n=== {visit} | {os.path.basename(session_dir)} (matches={matches}) ===')
    
    # 1. Limpiar published
    if os.path.exists(published_dir):
        for f in os.listdir(published_dir):
            os.remove(os.path.join(published_dir, f))
    
    # 2. Dry-run
    cmd_dry = [
        sys.executable, '-m', 'fincadiag.gateway.runtime',
        '--session-dir', session_dir,
        '--topic-root', 'fincadiag/la_esmeralda',
        '--dry-run'
    ]
    print('[DRY-RUN] ...', end='', flush=True)
    result_dry = subprocess.run(cmd_dry, capture_output=True, text=True, cwd=base, env=env)
    dry_ok = result_dry.returncode == 0
    print(f' OK' if dry_ok else f' FAIL {result_dry.returncode}')
    
    # 3. Test suite
    cmd_test = [test_script, session_dir]
    print('[TESTS] ...', end='', flush=True)
    result_test = subprocess.run(cmd_test, capture_output=True, text=True, cwd=base, env=env)
    test_ok = result_test.returncode == 0
    print(f' OK' if test_ok else f' FAIL {result_test.returncode}')
    if not test_ok:
        print(f'  stdout: {result_test.stdout[:300]}')
        print(f'  stderr: {result_test.stderr[:300]}')
    
    all_results.append({
        'visit': visit,
        'session': os.path.basename(session_dir),
        'matches': matches,
        'dry_ok': dry_ok,
        'test_ok': test_ok
    })

print('\n=== RESUMEN PRUEBAS ===')
for r in all_results:
    status = 'PASS' if r['dry_ok'] and r['test_ok'] else 'FAIL'
    print(f"{r['visit']}: {r['session']} (m={r['matches']}) -> {status}")

with open(os.path.join(base, 'test_results_11_20_mayo.json'), 'w') as f:
    json.dump(all_results, f, indent=2, ensure_ascii=False)
print('\nResultados guardados en test_results_11_20_mayo.json')
