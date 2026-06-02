"""Agendar Latency adicional 17:05 (15 ciclos) para llegar a n>=30 en dia 1."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"; PORT = 33000; USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=30)


def sh(cmd):
    i, o, e = c.exec_command(cmd)
    out = o.read().decode(); err = e.read().decode()
    print(f"$ {cmd[:130]}")
    if out.strip(): print(out)
    if err.strip(): print("[err]", err)


sh("echo 'bash /home/esmeralda/latency_e2e_pi.sh 15 > /home/esmeralda/obj4_runs/2026-05-28_run2b_latency.log 2>&1' | at 17:05 today")
sh("date; atq | sort -k2,5")
c.close()
