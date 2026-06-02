"""Ver definicion .service y propiedades clave."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"; PORT = 33000; USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]
c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=60)


def run(cmd, sudo=False):
    if sudo: cmd = f"echo {PASSWORD} | sudo -S bash -c \"{cmd}\""
    i, o, e = c.exec_command(cmd, timeout=60)
    print(f"\n--- {cmd[:100]} ---")
    print(o.read().decode())


run("cat /etc/systemd/system/fincadiag-gateway.service")
run("systemctl is-enabled fincadiag-gateway; systemctl is-active fincadiag-gateway")
run("systemctl show fincadiag-gateway -p Restart -p RestartSec -p KillMode -p WantedBy")
run("vcgencmd get_throttled")
c.close()
