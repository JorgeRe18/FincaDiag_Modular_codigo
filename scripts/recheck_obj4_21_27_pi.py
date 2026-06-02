"""Re-correr Obj4 en Pi para 21-27 con los correlation_summary.json recien copiados."""
import paramiko, os, json, time

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PW = os.environ["PI_PASSWORD"]
PI_ROOT = "/var/lib/fincadiag/processed/visits"

SESSIONS = [
    ("Visita_21", "TOMA_PM__1PM__Captura_20260521_130005"),
    ("Visita_22", "TOMA_PM__1PM__Captura_20260522_130005"),
    ("Visita_23", "TOMA_PM__1PM__Captura_20260523_130005"),
    ("Visita_24", "TOMA_AM__2AM__Captura_20260524_021505"),
    ("Visita_25", "TOMA_PM__1PM__Captura_20260525_130005"),
    ("Visita_26", "TOMA_PM__1PM__Captura_20260526_130201"),
    ("Visita_27", "TOMA_AM__2AM__Captura_20260527_021505"),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PW, timeout=60, banner_timeout=60, auth_timeout=60)

results = []

for visit_label, sname in SESSIONS:
    visit = visit_label + "_05_2026"
    ses = f"{PI_ROOT}/{visit}/sesiones/{sname}"
    
    # Leer motor matches
    cmd1 = f"cat {ses}/correlation_summary.json | python3 -c \"import sys,json; d=json.load(sys.stdin); m=d.get('matched_events') or d.get('matches',0); print(len(m) if isinstance(m,list) else int(m or 0))\""
    stdin, stdout, stderr = c.exec_command(cmd1)
    motor_matches = int(stdout.read().decode().strip() or 0)
    
    # Dry-run gateway
    cmd2 = f"""
export PYTHONPATH=/opt/fincadiag
rm -rf /tmp/pub_obj4_{visit_label}
mkdir -p /tmp/pub_obj4_{visit_label}
python3 -m fincadiag.gateway.runtime --session-dir "{ses}" --topic-root fincadiag/la_esmeralda --dry-run --published-dir /tmp/pub_obj4_{visit_label} >/dev/null 2>&1
python3 -c "
import json, glob
files = glob.glob('/tmp/pub_obj4_{visit_label}/*.jsonl')
if files:
    for line in open(files[0]):
        line = line.strip()
        if not line: continue
        d = json.loads(line)
        if d.get('event_type') == 'correlation_summary':
            p = d.get('payload', {{}})
            print('matches_gw=' + str(p.get('matches',0)))
            print('eta_gw=' + str(p.get('eta_extraccion_pct','None')))
else:
    print('NO_FILES')
"
"""
    stdin, stdout, stderr = c.exec_command(cmd2, timeout=60)
    out = stdout.read().decode()
    
    obj4_pass = False
    gw_matches = 0
    if 'matches_gw=' in out:
        gw_matches = int(out.split('matches_gw=')[1].split('\n')[0])
        obj4_pass = (gw_matches == motor_matches)
    
    results.append({
        'visit': visit,
        'session': sname,
        'motor_matches': motor_matches,
        'gw_matches': gw_matches,
        'obj4_pass': obj4_pass
    })
    print(f"{visit}: motor={motor_matches} gw={gw_matches} obj4={'PASS' if obj4_pass else 'FAIL'}")

c.close()

# Guardar
BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
out_path = BASE / 'obj4_recheck_21_27_pi.json'
with open(out_path, 'w') as f:
    json.dump({'fecha': time.strftime('%Y-%m-%d %H:%M:%S'), 'results': results}, f, indent=2)

print(f"\nGuardado: {out_path}")
pass_count = sum(1 for r in results if r['obj4_pass'])
print(f"Obj4 PASS: {pass_count}/{len(results)}")
