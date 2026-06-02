"""Investigar el daemon gateway (PID 1582) sin tocarlo."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]


def run(client, cmd, sudo=False, timeout=60):
    if sudo:
        cmd = f"echo {PASSWORD} | sudo -S bash -c \"{cmd}\""
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode(errors="replace")
    print(f"\n$ {cmd[:150]}")
    if out.strip(): print(out)
    err = stderr.read().decode(errors="replace")
    if err.strip() and "password for" not in err.lower(): print("[err]", err)


c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)

print("=" * 70); print(" 1. Quien lanzo el daemon? (padre PID)"); print("=" * 70)
run(c, "ps -o pid,ppid,user,etime,start,cmd -p 1582 2>&1")
run(c, "ps -o pid,ppid,user,cmd -p $(ps -o ppid= -p 1582 | tr -d ' ') 2>&1")

print("\n" + "=" * 70); print(" 2. Cadena completa de procesos padres"); print("=" * 70)
run(c, "pstree -ps 1582 2>&1")

print("\n" + "=" * 70); print(" 3. systemd: hay algun servicio fincadiag?"); print("=" * 70)
run(c, "systemctl list-units --all | grep -i finca")
run(c, "systemctl list-unit-files | grep -i finca")
run(c, "ls /etc/systemd/system/ | grep -i finca")
run(c, "ls /lib/systemd/system/ | grep -i finca")

print("\n" + "=" * 70); print(" 4. cgroup del proceso (de donde viene?)"); print("=" * 70)
run(c, "cat /proc/1582/cgroup 2>&1")
run(c, "cat /proc/1582/status 2>&1 | head -10")

print("\n" + "=" * 70); print(" 5. Archivos abiertos por el daemon"); print("=" * 70)
run(c, "ls -la /proc/1582/cwd /proc/1582/exe 2>&1")
run(c, "ls /proc/1582/fd/ 2>&1 | head -20")

print("\n" + "=" * 70); print(" 6. Que esta procesando? Spool y published"); print("=" * 70)
run(c, "ls -la /var/lib/fincadiag/spool/ /var/lib/fincadiag/published/ 2>&1")
run(c, "ls /var/lib/fincadiag/processed/visits/ 2>&1")
run(c, "find /var/lib/fincadiag/processed -maxdepth 5 -name 'correlation_summary.json' -newer /tmp/anchor 2>/dev/null | head -5")
run(c, "date; stat -c '%y %n' /var/lib/fincadiag/published/*.jsonl 2>/dev/null | tail -10")

print("\n" + "=" * 70); print(" 7. Historial de comandos recientes"); print("=" * 70)
run(c, "tail -30 /home/esmeralda/.bash_history 2>/dev/null")
run(c, "tail -30 /root/.bash_history 2>&1", sudo=True)

print("\n" + "=" * 70); print(" 8. cron y otros services"); print("=" * 70)
run(c, "crontab -l 2>&1")
run(c, "crontab -l 2>&1", sudo=True)
run(c, "systemctl list-units --type=service --state=running | grep -iE 'finca|gateway' 2>&1")

print("\n" + "=" * 70); print(" 9. Log de gateway si existe"); print("=" * 70)
run(c, "find /var/log -name '*finca*' -o -name '*gateway*' 2>/dev/null | head -10")
run(c, "find /home/esmeralda -name '*.log' -mmin -1440 2>/dev/null | xargs ls -la 2>/dev/null | head -20")

c.close()
