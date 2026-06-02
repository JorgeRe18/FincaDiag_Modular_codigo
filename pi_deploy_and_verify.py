# -*- coding: utf-8 -*-
import paramiko, os, io
from pathlib import Path

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("gateway-esmeralda-ssh.at.remote.it", port=33000,
          username="esmeralda", password=os.environ["PI_PASSWORD"], timeout=30)

script = Path(r"C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests\obj4_resilience_staged.py").read_bytes()
sftp = c.open_sftp()
sftp.putfo(io.BytesIO(script), "/home/esmeralda/obj4_resilience_staged.py")
sftp.close()
print("Script subido.")

cmds = [
    ("sudo python3 /home/esmeralda/obj4_resilience_staged.py --dry-run 2>&1", "Dry run"),
    ("grep -n 'RESULTS\\|_TODAY\\|_RESULTS_DIR' /home/esmeralda/obj4_resilience_staged.py | head -8", "Rutas de salida"),
]
for cmd, title in cmds:
    _, out, _ = c.exec_command(cmd, timeout=20)
    print(f"\n=== {title} ===")
    print(out.read().decode(errors="replace").strip())

c.close()
