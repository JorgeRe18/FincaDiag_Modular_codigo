import paramiko, hashlib, os

def exec_cmd(client, cmd, timeout=30):
    stdin, stdout, stderr = client.exec_command(cmd, timeout=timeout)
    out = stdout.read().decode('utf-8', errors='ignore').strip()
    err = stderr.read().decode('utf-8', errors='ignore').strip()
    rc = stdout.channel.recv_exit_status()
    return rc, out, err

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect('gateway-esmeralda-ssh.at.remote.it', port=33000,
          username='esmeralda', password='fincaPPA26', timeout=30, banner_timeout=30)

# Find where fincadiag is installed
rc, out, _ = exec_cmd(c, "python3 -c \"import fincadiag; print(fincadiag.__file__)\" 2>/dev/null || echo NOT_FOUND")
print(f"fincadiag location: {out}")

rc, out, _ = exec_cmd(c, "find /opt /home /usr/local/lib -name 'pcap_parser.py' 2>/dev/null | head -5")
print(f"pcap_parser.py: {out if out else 'not found'}")

rc, out, _ = exec_cmd(c, "find /opt /home /usr/local/lib -name 'alerts.py' -path '*/fincadiag/*' 2>/dev/null | head -5")
print(f"alerts.py: {out if out else 'not found'}")

rc, out, _ = exec_cmd(c, "find /opt /home /usr/local/lib -name 'runtime.py' -path '*/gateway/*' 2>/dev/null | head -5")
print(f"runtime.py: {out if out else 'not found'}")

# Also check PYTHONPATH
rc, out, _ = exec_cmd(c, "cat /etc/environment 2>/dev/null | grep PYTHON; cat /opt/fincadiag/fincadiag.env 2>/dev/null | head -10")
print(f"\nPYTHONPATH config: {out if out else 'not found'}")

rc, out, _ = exec_cmd(c, "ls /opt/fincadiag/ 2>/dev/null")
print(f"\n/opt/fincadiag/: {out}")

c.close()
