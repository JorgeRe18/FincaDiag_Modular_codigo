"""Copiar correlation_summary.json de Windows a Pi para sesiones 21-27."""
import paramiko, os, json
from pathlib import Path

BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')
DATA = BASE / 'data' / 'processed' / 'visits'
PI_ROOT = "/var/lib/fincadiag/processed/visits"

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PW = os.environ["PI_PASSWORD"]

# Descubrir sesiones 21-27 con correlation_summary.json en Windows
sessions_to_sync = []
for vd in sorted(DATA.glob('Visita_*_05_2026')):
    day = int(vd.name.split('_')[1])
    if day < 21 or day > 27:
        continue
    for ses in vd.glob('sesiones/*/correlation_summary.json'):
        if 'BASELINE' in ses.parent.name:
            continue
        d = json.loads(ses.read_text())
        raw = d.get('matched_events')
        if raw is None: raw = d.get('matches', 0)
        matches = len(raw) if isinstance(raw, list) else (int(raw) if raw else 0)
        if matches > 0:
            sessions_to_sync.append({
                'visit': vd.name,
                'session': ses.parent.name,
                'local_path': str(ses),
                'pi_dir': f"{PI_ROOT}/{vd.name}/sesiones/{ses.parent.name}"
            })

print(f"Sesiones a sincronizar: {len(sessions_to_sync)}")
for s in sessions_to_sync:
    print(f"  {s['visit']} / {s['session']}")

if not sessions_to_sync:
    print("Nada que sincronizar.")
    exit(0)

# Conectar
print("\nConectando a Pi...")
transport = paramiko.Transport((HOST, PORT))
transport.connect(username=USER, password=PW)
sftp = paramiko.SFTPClient.from_transport(transport)

# Crear directorios y subir archivos
for s in sessions_to_sync:
    try:
        # Crear directorio en Pi
        parts = s['pi_dir'].split('/')
        current = ''
        for part in parts:
            current = current + '/' + part if current else part
            try:
                sftp.mkdir(current)
            except IOError:
                pass  # ya existe

        # Subir archivo
        remote_path = s['pi_dir'] + '/correlation_summary.json'
        sftp.put(s['local_path'], remote_path)
        print(f"  OK: {s['visit']}/{s['session']} -> {remote_path}")
    except Exception as e:
        print(f"  ERROR: {s['visit']}/{s['session']}: {e}")

sftp.close()
transport.close()
print("\nSincronizacion completada.")

# Verificar
print("\nVerificando en Pi...")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PW, timeout=60)
for s in sessions_to_sync:
    cmd = f"cat {s['pi_dir']}/correlation_summary.json | python3 -c \"import sys,json; d=json.load(sys.stdin); m=d.get('matched_events') or d.get('matches',0); print(len(m) if isinstance(m,list) else int(m or 0))\""
    stdin, stdout, stderr = c.exec_command(cmd)
    out = stdout.read().decode().strip()
    print(f"  {s['visit']}/{s['session']}: matches={out}")
c.close()
print("Verificacion completada.")
