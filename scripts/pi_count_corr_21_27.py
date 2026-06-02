"""Contar correlation_summary.json en Pi para visitas 21-27."""
import paramiko, os

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('gateway-esmeralda-ssh.at.remote.it', port=33000, username='esmeralda', password=os.environ['PI_PASSWORD'], timeout=60, banner_timeout=60, auth_timeout=60)

for day in range(21, 28):
    visit = f'Visita_{day}_05_2026'
    cmd = f"find /var/lib/fincadiag/processed/visits/{visit} -name 'correlation_summary.json' 2>/dev/null | wc -l"
    stdin, stdout, stderr = c.exec_command(cmd)
    count = int(stdout.read().decode().strip() or 0)
    print(f'{visit}: {count} correlation_summary.json')

c.close()
