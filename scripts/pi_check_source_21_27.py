"""Verificar si hay archivos fuente en Pi para sesiones 21-27 (para correr motor)."""
import paramiko, os

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('gateway-esmeralda-ssh.at.remote.it', port=33000, username='esmeralda', password=os.environ['PI_PASSWORD'], timeout=60, banner_timeout=60, auth_timeout=60)

for day in range(21, 28):
    visit = f'Visita_{day}_05_2026'
    cmd = f"ls /var/lib/fincadiag/processed/visits/{visit}/sesiones/ 2>/dev/null | head -5"
    stdin, stdout, stderr = c.exec_command(cmd)
    sessions = stdout.read().decode().strip()
    if not sessions:
        print(f'{visit}: NO TIENE SESIONES')
        continue
    # Tomar primera sesion
    first = sessions.split('\n')[0]
    cmd2 = f"ls /var/lib/fincadiag/processed/visits/{visit}/sesiones/{first}/ | head -20"
    stdin, stdout, stderr = c.exec_command(cmd2)
    files = stdout.read().decode().strip()
    print(f'{visit} / {first}:')
    for line in files.split('\n')[:10]:
        print(f'  {line}')
    print()

c.close()
