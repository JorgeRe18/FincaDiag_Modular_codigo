"""Verificar causa raiz: comparar correlation_summary.json en Pi vs Windows para visitas 21-27."""
import paramiko, os, json
from pathlib import Path

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PW = os.environ["PI_PASSWORD"]
PI_ROOT = "/var/lib/fincadiag/processed/visits"
BASE = Path(r'C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular')

SESSIONS = [
    ("Visita_21_05_2026", "TOMA_PM__1PM__Captura_20260521_130005"),
    ("Visita_24_05_2026", "TOMA_AM__2AM__Captura_20260524_021505"),
    ("Visita_27_05_2026", "TOMA_AM__2AM__Captura_20260527_021505"),
    # control: una que SI pasa (11-20)
    ("Visita_18_05_2026", "TOMA_AM__2AM__Captura_20260518_021505"),
]

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PW, timeout=60, banner_timeout=60, auth_timeout=60)

for visit, ses in SESSIONS:
    print(f"\n{'='*60}")
    print(f"{visit} / {ses}")
    print('='*60)

    # Pi
    pi_path = f"{PI_ROOT}/{visit}/sesiones/{ses}/correlation_summary.json"
    stdin, stdout, stderr = c.exec_command(f"cat '{pi_path}' 2>/dev/null")
    pi_raw = stdout.read().decode(errors='replace')
    if pi_raw.strip():
        try:
            d = json.loads(pi_raw)
            raw = d.get('matched_events')
            if raw is None: raw = d.get('matches', 0)
            pi_matches = len(raw) if isinstance(raw, list) else (int(raw) if raw else 0)
            pi_eta = d.get('eta_extraccion') or d.get('eta_extraccion_pct') or d.get('extraction_efficiency_pct')
            print(f"  PI:      matches={pi_matches}, eta={pi_eta}")
        except Exception as e:
            print(f"  PI: error parse {e}; primeros 200 chars: {pi_raw[:200]}")
    else:
        # Check if file exists
        stdin, stdout, stderr = c.exec_command(f"ls -la '{pi_path}' 2>&1")
        print(f"  PI: archivo vacio o no existe -> {stdout.read().decode().strip()}")

    # Windows
    win_path = BASE / 'data' / 'processed' / 'visits' / visit / 'sesiones' / ses / 'correlation_summary.json'
    if win_path.exists():
        d = json.loads(win_path.read_text())
        raw = d.get('matched_events')
        if raw is None: raw = d.get('matches', 0)
        win_matches = len(raw) if isinstance(raw, list) else (int(raw) if raw else 0)
        win_eta = d.get('eta_extraccion') or d.get('eta_extraccion_pct') or d.get('extraction_efficiency_pct')
        print(f"  WINDOWS: matches={win_matches}, eta={win_eta}")
    else:
        print(f"  WINDOWS: no existe {win_path}")

    # Pi file mtime
    stdin, stdout, stderr = c.exec_command(f"stat -c '%y' '{pi_path}' 2>/dev/null")
    print(f"  PI mtime: {stdout.read().decode().strip()}")

c.close()
