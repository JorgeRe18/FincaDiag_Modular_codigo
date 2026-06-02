"""SSH a Pi y extraer telemetry_packets de pcap_summary.json para 21-27 mayo."""
import json
import paramiko
from pathlib import Path

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASS = "fincaPPA26"
REMOTE_DIR = "/var/lib/fincadiag/processed/visits"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)
    print("Conectado a Pi")
    
    # Listar directorios de visitas 21-27
    stdin, stdout, stderr = client.exec_command(
        f"ls -d {REMOTE_DIR}/Visita_2[1-7]_05_2026"
    )
    visit_dirs = stdout.read().decode().strip().split('\n')
    print(f"Visitas encontradas: {len(visit_dirs)}")
    for vd in visit_dirs:
        print(f"  {vd}")
    
    # Extraer pcap_summary de cada sesion
    results = []
    for vd in visit_dirs:
        if not vd.strip():
            continue
        stdin, stdout, stderr = client.exec_command(
            f"find {vd} -name 'pcap_summary.json' -exec cat {{}} \\;"
        )
        raw = stdout.read().decode()
        err = stderr.read().decode()
        if err:
            print(f"  Error en {vd}: {err[:200]}")
        
        # Cada cat puede devolver multiples JSON concatenados
        for line in raw.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                telemetry = data.get('telemetry', {})
                packets = telemetry.get('telemetry_packets', 0)
                results.append(packets)
                print(f"  {vd}: packets={packets}")
            except json.JSONDecodeError:
                pass
    
    print(f"\nTotal pcap_summary encontrados: {len(results)}")
    if results:
        print(f"Valores: {results}")
        print(f"Media: {sum(results)/len(results):.1f}")
        
except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
