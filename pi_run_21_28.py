"""Ejecutar suite Pi para sesiones May 21-28 con spool y published aislados."""
import paramiko, os

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]

def run(client, cmd, timeout=180, show=True):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if show:
        print(f"$ {cmd[:120]}")
        if out.strip(): print(out)
        if err.strip(): print("[err]", err)
        print()
    return out, err

# Sesiones May 21-28 con matches > 0 (por session_dir real en Pi)
SESSIONS = [
    ("Visita_21", "/var/lib/fincadiag/processed/visits/Visita_21_05_2026/sesiones/TOMA_AM__2AM__Captura_20260521_021505", 1),
    ("Visita_21", "/var/lib/fincadiag/processed/visits/Visita_21_05_2026/sesiones/TOMA_PM__1PM__Captura_20260521_130005", 8),
    ("Visita_22", "/var/lib/fincadiag/processed/visits/Visita_22_05_2026/sesiones/TOMA_AM__2AM__Captura_20260522_021505", 1),
    ("Visita_22", "/var/lib/fincadiag/processed/visits/Visita_22_05_2026/sesiones/TOMA_PM__1PM__Captura_20260522_130005", 3),
    ("Visita_23", "/var/lib/fincadiag/processed/visits/Visita_23_05_2026/sesiones/TOMA_AM__2AM__Captura_20260523_021505", 5),
    ("Visita_23", "/var/lib/fincadiag/processed/visits/Visita_23_05_2026/sesiones/TOMA_PM__1PM__Captura_20260523_130005", 3),
    ("Visita_24", "/var/lib/fincadiag/processed/visits/Visita_24_05_2026/sesiones/TOMA_AM__2AM__Captura_20260524_021505", 7),
    ("Visita_24", "/var/lib/fincadiag/processed/visits/Visita_24_05_2026/sesiones/TOMA_PM__1PM__Captura_20260524_130005", 1),
    ("Visita_25", "/var/lib/fincadiag/processed/visits/Visita_25_05_2026/sesiones/TOMA_PM__1PM__Captura_20260525_130005", 7),
    ("Visita_26", "/var/lib/fincadiag/processed/visits/Visita_26_05_2026/sesiones/TOMA_AM__2AM__Captura_20260526_021506", 1),
    ("Visita_26", "/var/lib/fincadiag/processed/visits/Visita_26_05_2026/sesiones/TOMA_PM__1PM__Captura_20260526_130201", 3),
    ("Visita_27", "/var/lib/fincadiag/processed/visits/Visita_27_05_2026/sesiones/TOMA_AM__2AM__Captura_20260527_021505", 12),
    ("Visita_27", "/var/lib/fincadiag/processed/visits/Visita_27_05_2026/sesiones/TOMA_PM__1PM__Captura_20260527_130005", 1),
]

print("=== Conectando ===")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

# Upload drain helper
run(c, r"""
cat > /tmp/drain_spool.py << 'EOF'
#!/usr/bin/env python3
import sys
from pathlib import Path
sys.path.insert(0, '/opt/fincadiag')
from fincadiag.gateway.runtime import GatewayRuntime
from fincadiag.gateway.config import GatewayConfig

config = GatewayConfig(
    topic_root='fincadiag/la_esmeralda',
    mqtt_host='localhost',
    mqtt_port=8883,
    tls_enabled=True,
    ca_path='/etc/fincadiag/certs/ca.crt',
    cert_path='/etc/fincadiag/certs/client.crt',
    key_path='/etc/fincadiag/certs/client.key',
    tls_min_version='1.3',
    spool_dir=Path(sys.argv[1]),
    published_dir=Path(sys.argv[2]),
    dry_run=False
)
runtime = GatewayRuntime(config)
result = runtime.drain_spool()
print(f'drained={result.published_count} failed={result.failed_count}')
EOF
chmod +x /tmp/drain_spool.py
""")

results = []
for visit_label, session_dir, expected_matches in SESSIONS:
    print(f"\n{'='*60}")
    print(f"=== {visit_label}: {os.path.basename(session_dir)} ===")
    print(f"{'='*60}")
    
    SPOOL = f"/tmp/spool_{visit_label}_{os.path.basename(session_dir)}"
    PUB = f"/tmp/pub_{visit_label}_{os.path.basename(session_dir)}"
    CA = "/etc/fincadiag/certs/ca.crt"
    CERT = "/etc/fincadiag/certs/client.crt"
    KEY = "/etc/fincadiag/certs/client.key"
    OUTPUT = f"/tmp/mqtt_{visit_label}.txt"
    
    out, err = run(c, f'''
    rm -rf "{SPOOL}" "{PUB}" "{OUTPUT}"
    mkdir -p "{SPOOL}" "{PUB}"
    
    # 1. Schema + dry-run -> genera published
    export PYTHONPATH=/opt/fincadiag
    python3 -m fincadiag.gateway.runtime \
        --session-dir "{session_dir}" \
        --topic-root "fincadiag/la_esmeralda" \
        --dry-run \
        --spool-dir "{SPOOL}" \
        --published-dir "{PUB}" >/dev/null 2>&1
    
    # Count published files
    PUB_COUNT=$(find "{PUB}" -type f 2>/dev/null | wc -l)
    echo "PUBLISHED_FILES=$PUB_COUNT"
    ''', timeout=60)
    
    schema_pass = 'PUBLISHED_FILES=' in out and int(out.split('PUBLISHED_FILES=')[1].split()[0]) > 0
    
    # 2. Idempotencia
    out2, _ = run(c, f'''
    export PYTHONPATH=/opt/fincadiag
    HASH1=$(find "{PUB}" -name "*.jsonl" -exec md5sum {{}} + | md5sum | awk '{{print $1}}')
    rm -rf "{PUB}"/*
    python3 -m fincadiag.gateway.runtime \
        --session-dir "{session_dir}" \
        --topic-root "fincadiag/la_esmeralda" \
        --dry-run \
        --spool-dir "{SPOOL}2" \
        --published-dir "{PUB}2" >/dev/null 2>&1
    HASH2=$(find "{PUB}2" -name "*.jsonl" -exec md5sum {{}} + | md5sum | awk '{{print $1}}')
    if [ "$HASH1" = "$HASH2" ]; then echo "IDEM=PASS"; else echo "IDEM=FAIL"; fi
    ''', timeout=60)
    idem_pass = 'IDEM=PASS' in out2
    
    # 3. Resiliencia + subscribe
    out3, _ = run(c, f'''
    rm -rf "{SPOOL}" "{OUTPUT}"
    mkdir -p "{SPOOL}"
    
    # Stop mosquitto, spool
    sudo systemctl stop mosquitto
    export PYTHONPATH=/opt/fincadiag
    python3 -m fincadiag.gateway.runtime \
        --session-dir "{session_dir}" \
        --topic-root "fincadiag/la_esmeralda" \
        --mqtt-host localhost --mqtt-port 8883 --tls-enabled \
        --ca-path "{CA}" --cert-path "{CERT}" --key-path "{KEY}" \
        --tls-min-version 1.3 \
        --spool-dir "{SPOOL}" \
        --published-dir "/tmp/pub_res" >/dev/null 2>&1
    
    SPOOL_COUNT=$(find "{SPOOL}" -type f 2>/dev/null | wc -l)
    SPOOL_LINES=$(cat "{SPOOL}"/*.jsonl 2>/dev/null | wc -l)
    echo "SPOOL_FILES=$SPOOL_COUNT SPOOL_LINES=$SPOOL_LINES"
    
    # Start mosquitto + sub + drain
    sudo systemctl start mosquitto
    sleep 3
    mosquitto_sub --cafile "{CA}" --cert "{CERT}" --key "{KEY}" -h localhost -p 8883 -t "fincadiag/la_esmeralda/#" -v > "{OUTPUT}" 2>/dev/null &
    SUB_PID=$!
    sleep 2
    python3 /tmp/drain_spool.py "{SPOOL}" "/tmp/pub_drain"
    sleep 3
    kill $SUB_PID 2>/dev/null || true
    
    LINE_COUNT=$(wc -l < "{OUTPUT}" 2>/dev/null || echo 0)
    SPOOL_AFTER=$(find "{SPOOL}" -type f 2>/dev/null | wc -l)
    echo "RECEIVED=$LINE_COUNT SPOOL_AFTER=$SPOOL_AFTER"
    ''', timeout=120)
    
    res_lines = [l for l in out3.split('\n') if 'RECEIVED=' in l]
    if res_lines:
        parts = res_lines[-1].split()
        received = int([p for p in parts if p.startswith('RECEIVED=')][0].split('=')[1])
        spool_after = int([p for p in parts if p.startswith('SPOOL_AFTER=')][0].split('=')[1])
        res_pass = received > 0 and spool_after == 0
    else:
        res_pass = False
        received = 0
        spool_after = 999
    
    # 4. TLS handshake (una vez, no por sesión)
    # 5. Objetivo 4
    results.append({
        'visit': visit_label,
        'session': os.path.basename(session_dir),
        'schema': schema_pass,
        'idempotency': idem_pass,
        'resilience': res_pass,
        'received': received,
        'spool_after': spool_after
    })
    print(f"Result: schema={'PASS' if schema_pass else 'FAIL'} idem={'PASS' if idem_pass else 'FAIL'} res={'PASS' if res_pass else 'FAIL'}")

c.close()

print("\n" + "="*60)
print("RESUMEN MAY 21-28")
total = len(results)
for r in results:
    print(f"{r['visit']} {r['session'][:40]}: S={r['schema']} I={r['idempotency']} R={r['resilience']}")
print(f"Total: {total}")
