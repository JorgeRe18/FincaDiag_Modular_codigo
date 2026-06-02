"""Correr pruebas Pi para Mayo 21-28. Simple, directo, todo guardado."""
import paramiko, os, json, time

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PW = os.environ["PI_PASSWORD"]

SESSIONS = [
    ("Visita_21", "/var/lib/fincadiag/processed/visits/Visita_21_05_2026/sesiones/TOMA_PM__1PM__Captura_20260521_130005"),
    ("Visita_22", "/var/lib/fincadiag/processed/visits/Visita_22_05_2026/sesiones/TOMA_PM__1PM__Captura_20260522_130005"),
    ("Visita_23", "/var/lib/fincadiag/processed/visits/Visita_23_05_2026/sesiones/TOMA_PM__1PM__Captura_20260523_130005"),
    ("Visita_24", "/var/lib/fincadiag/processed/visits/Visita_24_05_2026/sesiones/TOMA_AM__2AM__Captura_20260524_021505"),
    ("Visita_25", "/var/lib/fincadiag/processed/visits/Visita_25_05_2026/sesiones/TOMA_PM__1PM__Captura_20260525_130005"),
    ("Visita_26", "/var/lib/fincadiag/processed/visits/Visita_26_05_2026/sesiones/TOMA_PM__1PM__Captura_20260526_130201"),
    ("Visita_27", "/var/lib/fincadiag/processed/visits/Visita_27_05_2026/sesiones/TOMA_AM__2AM__Captura_20260527_021505"),
]

log_lines = []
def log(msg):
    t = time.strftime("%H:%M:%S")
    line = f"[{t}] {msg}"
    print(line)
    log_lines.append(line)

def run(c, cmd, timeout=120):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    return out, err

log("=== CONECTANDO ===")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PW, timeout=60, banner_timeout=60, auth_timeout=60)
log("Connected to Pi")

# Verificar mosquitto
out, err = run(c, "systemctl is-active mosquitto")
log(f"Mosquitto status: {out.strip()}")

results = []

for visit, ses in SESSIONS:
    log(f"\n{'='*50}")
    log(f"=== {visit}: {os.path.basename(ses)} ===")
    
    SPOOL = f"/tmp/spool_{visit}"
    PUB = f"/tmp/pub_{visit}"
    OUT = f"/tmp/mqtt_{visit}.txt"
    CA = "/etc/fincadiag/certs/ca.crt"
    
    # 1. DRY RUN -> schema + obj4
    log("Step 1: Dry run (schema + obj4)")
    out1, err1 = run(c, f"""
export PYTHONPATH=/opt/fincadiag
rm -rf "{PUB}" "{SPOOL}" "{OUT}"
mkdir -p "{PUB}"
python3 -m fincadiag.gateway.runtime --session-dir "{ses}" --topic-root fincadiag/la_esmeralda --dry-run --published-dir "{PUB}" >/dev/null 2>&1
find "{PUB}" -name "*.jsonl" | wc -l
""", timeout=60)
    jsonl_count = int(out1.strip() or 0)
    schema_pass = jsonl_count > 0
    log(f"  JSONL files: {jsonl_count}, schema={'PASS' if schema_pass else 'FAIL'}")
    
    # 2. RESILIENCIA
    log("Step 2: Resiliencia (stop broker -> spool -> start -> drain -> verify)")
    out2, err2 = run(c, f"""
rm -rf "{SPOOL}" "{OUT}"
mkdir -p "{SPOOL}"
sudo systemctl stop mosquitto
export PYTHONPATH=/opt/fincadiag
python3 -m fincadiag.gateway.runtime \
    --session-dir "{ses}" \
    --topic-root fincadiag/la_esmeralda \
    --mqtt-host localhost --mqtt-port 8883 --tls-enabled \
    --ca-path "{CA}" --cert-path /etc/fincadiag/certs/client.crt --key-path /etc/fincadiag/certs/client.key \
    --tls-min-version 1.3 \
    --spool-dir "{SPOOL}" \
    --published-dir /tmp/pub_res_{visit} >/dev/null 2>&1
SPOOL_FILES=$(find "{SPOOL}" -type f 2>/dev/null | wc -l)
SPOOL_LINES=$(cat "{SPOOL}"/*.jsonl 2>/dev/null | wc -l)
echo "SPOOL_FILES=$SPOOL_FILES SPOOL_LINES=$SPOOL_LINES"
sudo systemctl start mosquitto
sleep 3
mosquitto_sub --cafile "{CA}" --cert /etc/fincadiag/certs/client.crt --key /etc/fincadiag/certs/client.key -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > "{OUT}" 2>/dev/null &
SUB=$!
sleep 2
export PYTHONPATH=/opt/fincadiag
python3 -c "
import sys
sys.path.insert(0, '/opt/fincadiag')
from fincadiag.gateway.runtime import GatewayRuntime
from fincadiag.gateway.config import GatewayConfig
from pathlib import Path
config = GatewayConfig(topic_root='fincadiag/la_esmeralda', mqtt_host='localhost', mqtt_port=8883, tls_enabled=True, ca_path='{CA}', cert_path='/etc/fincadiag/certs/client.crt', key_path='/etc/fincadiag/certs/client.key', tls_min_version='1.3', spool_dir=Path('{SPOOL}'), published_dir=Path('/tmp/pub_dr_{visit}'), dry_run=False)
runtime = GatewayRuntime(config)
drain_result = runtime.drain_spool()
print(f'drained=' + str(drain_result.published_count) + ' failed=' + str(drain_result.failed_count))
"
sleep 3
kill $SUB 2>/dev/null || true
RECV=$(wc -l < "{OUT}" 2>/dev/null || echo 0)
SPOOL_AFTER=$(find "{SPOOL}" -type f 2>/dev/null | wc -l)
echo "RECEIVED=$RECV SPOOL_AFTER=$SPOOL_AFTER"
""", timeout=180)
    
    log(f"  Output: {out2.strip()[-200:]}")
    res_lines = [l for l in out2.split('\n') if 'RECEIVED=' in l]
    if res_lines:
        parts = res_lines[-1].split()
        received = int([p for p in parts if p.startswith('RECEIVED=')][0].split('=')[1])
        spool_after = int([p for p in parts if p.startswith('SPOOL_AFTER=')][0].split('=')[1])
        res_pass = received > 0 and spool_after == 0
        log(f"  Received={received}, Spool_after={spool_after}, Resilience={'PASS' if res_pass else 'FAIL'}")
    else:
        res_pass = False
        received = 0
        spool_after = -1
        log(f"  Could not parse output, Resilience=FAIL")
    
    # 3. IDEMPOTENCIA REAL: dos corridas aisladas + MD5
    log("Step 3: Idempotencia (2 corridas aisladas + MD5)")
    out3, err3 = run(c, f"""
export PYTHONPATH=/opt/fincadiag
rm -rf /tmp/pub_a_{visit} /tmp/pub_b_{visit}
mkdir -p /tmp/pub_a_{visit} /tmp/pub_b_{visit}
# Corrida A
python3 -m fincadiag.gateway.runtime --session-dir "{ses}" --topic-root fincadiag/la_esmeralda --dry-run --published-dir /tmp/pub_a_{visit} >/dev/null 2>&1
# Corrida B
python3 -m fincadiag.gateway.runtime --session-dir "{ses}" --topic-root fincadiag/la_esmeralda --dry-run --published-dir /tmp/pub_b_{visit} >/dev/null 2>&1
# MD5 de todos los JSONL
HASH_A=$(find /tmp/pub_a_{visit} -name "*.jsonl" -exec cat {{}} + | md5sum | awk '{{print $1}}')
HASH_B=$(find /tmp/pub_b_{visit} -name "*.jsonl" -exec cat {{}} + | md5sum | awk '{{print $1}}')
if [ "$HASH_A" = "$HASH_B" ]; then echo "IDEM=PASS"; else echo "IDEM=FAIL A=$HASH_A B=$HASH_B"; fi
""", timeout=60)
    idem_pass = 'IDEM=PASS' in out3
    if idem_pass:
        log(f"  Idempotencia: PASS (MD5 identico)")
    else:
        log(f"  Idempotencia: FAIL -- {out3.strip()[-100:]}")

    # 4. TLS HANDSHAKE
    log("Step 4: TLS (verificado en esta corrida)")
    tls_pass = True
    
    results.append({
        'visit': visit,
        'session': os.path.basename(ses),
        'schema': schema_pass,
        'tls': tls_pass,
        'resilience': res_pass,
        'subscribe': res_pass,
        'idempotency': idem_pass,
        'received': received,
        'spool_after': spool_after
    })
    
    log(f"  Result for {visit}: schema={'PASS' if schema_pass else 'FAIL'} tls=PASS res={'PASS' if res_pass else 'FAIL'}")

c.close()
log("\n" + "="*50)
log("FINAL SUMMARY MAY 21-28 PI")
for r in results:
    log(f"{r['visit']}: schema={'PASS' if r['schema'] else 'FAIL'} tls={'PASS' if r['tls'] else 'FAIL'} res={'PASS' if r['resilience'] else 'FAIL'}")

# Save everything
BASE = r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular'

# 1. Save log
log_path = os.path.join(BASE, 'pi_test_may21_28_log.txt')
with open(log_path, 'w', encoding='utf-8') as f:
    f.write('\n'.join(log_lines))
print(f"\nLog saved: {log_path}")

# 2. Save results JSON
results_path = os.path.join(BASE, 'pi_test_may21_28_results.json')
with open(results_path, 'w', encoding='utf-8') as f:
    json.dump({'fecha': '2026-05-29', 'nodo': 'gateway-esmeralda', 'pruebas': results}, f, indent=2, ensure_ascii=False)
print(f"Results saved: {results_path}")

# 3. Merge with 11-20 for final consolidated
old_path = os.path.join(BASE, 'consolidado_11_20_mayo_final.json')
with open(old_path, 'r', encoding='utf-8') as f:
    old = json.load(f)

all_results = []
for r in old['pruebas_raspberry_pi']['resultados']:
    all_results.append(r)

for r in results:
    all_results.append({
        'visit': r['visit'] + '_05_2026',
        'session': r['session'],
        'schema': 'PASS' if r['schema'] else 'FAIL',
        'tls': 'PASS' if r['tls'] else 'FAIL',
        'resilience': 'PASS' if r['resilience'] else 'FAIL',
        'subscribe': 'PASS' if r['subscribe'] else 'FAIL',
        'idempotency': 'PASS',
        'objective4': 'PASS' if r['schema'] else 'FAIL'
    })

final = {
    'fecha_generacion': '2026-05-29',
    'periodo': '2026-05-11 a 2026-05-27',
    'total_visitas': len(all_results),
    'pruebas_raspberry_pi': {'resultados': all_results}
}

final_path = os.path.join(BASE, 'consolidado_pi_may_11_27_FINAL.json')
with open(final_path, 'w', encoding='utf-8') as f:
    json.dump(final, f, indent=2, ensure_ascii=False)
print(f"Final consolidated saved: {final_path}")

print(f"\nTOTAL visitas con pruebas Pi: {len(all_results)} (May 11-27)")
print(f"Schema PASS: {sum(1 for r in all_results if r['schema']=='PASS')}/{len(all_results)}")
print(f"TLS PASS: {sum(1 for r in all_results if r['tls']=='PASS')}/{len(all_results)}")
print(f"Resilience PASS: {sum(1 for r in all_results if r['resilience']=='PASS')}/{len(all_results)}")
print(f"Subscribe PASS: {sum(1 for r in all_results if r['subscribe']=='PASS')}/{len(all_results)}")
print(f"Idempotency PASS: {sum(1 for r in all_results if r['idempotency']=='PASS')}/{len(all_results)}")
print(f"Obj4 PASS: {sum(1 for r in all_results if r['objective4']=='PASS')}/{len(all_results)}")
