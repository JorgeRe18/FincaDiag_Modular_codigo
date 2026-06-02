"""SSH a Pi y explorar estructura de directorios para pcap_summary.json."""
import json
import paramiko

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASS = "fincaPPA26"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

try:
    client.connect(HOST, port=PORT, username=USER, password=PASS, timeout=20)
    
    # Explorar una visita en detalle
    for visit in ["Visita_21_05_2026", "Visita_22_05_2026"]:
        path = f"/var/lib/fincadiag/processed/visits/{visit}"
        stdin, stdout, stderr = client.exec_command(f"find {path} -type f -name '*.json' | head -20")
        files = stdout.read().decode().strip()
        print(f"\n{visit} JSON files:")
        print(files if files else "  (ninguno)")
        
        # Listar subdirectorios de sesiones
        stdin, stdout, stderr = client.exec_command(f"ls -la {path}/")
        ls = stdout.read().decode().strip()
        print(f"\n{visit} contenido:")
        print(ls[:1000])
        
except Exception as e:
    print(f"Error: {e}")
finally:
    client.close()
