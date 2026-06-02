"""Investigar setup electrico/systemd del gateway."""
import paramiko, os
HOST = "gateway-esmeralda-ssh.at.remote.it"; PORT = 33000; USER = "esmeralda"
PASSWORD = os.environ["PI_PASSWORD"]


def run(client, cmd, sudo=False, timeout=60):
    if sudo:
        cmd = f"echo {PASSWORD} | sudo -S bash -c \"{cmd}\""
    i, o, e = client.exec_command(cmd, timeout=timeout)
    out = o.read().decode(errors="replace"); err = e.read().decode(errors="replace")
    print(f"\n$ {cmd[:130]}")
    if out.strip(): print(out)
    if err.strip() and "password for" not in err.lower(): print("[err]", err)


c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASSWORD, timeout=60)

print("=" * 70); print(" 1. Definicion del .service"); print("=" * 70)
run(c, "find /etc/systemd /lib/systemd -name 'fincadiag-gateway.service' 2>/dev/null")
run(c, "cat /etc/systemd/system/fincadiag-gateway.service 2>&1 || cat /lib/systemd/system/fincadiag-gateway.service 2>&1")

print("\n" + "=" * 70); print(" 2. Estado y enabled"); print("=" * 70)
run(c, "systemctl status fincadiag-gateway --no-pager 2>&1 | head -20")
run(c, "systemctl is-enabled fincadiag-gateway")
run(c, "systemctl show fincadiag-gateway -p Restart,RestartSec,WatchdogSec,TimeoutStartSec,KillMode,TimeoutStopSec,User,WorkingDirectory")

print("\n" + "=" * 70); print(" 3. Servicios criticos al boot (mosquitto, scheduler)"); print("=" * 70)
run(c, "systemctl is-enabled mosquitto; systemctl is-active mosquitto")
run(c, "systemctl list-dependencies fincadiag-gateway --no-pager 2>&1 | head -20")

print("\n" + "=" * 70); print(" 4. UPS / batteria / fuente de poder"); print("=" * 70)
run(c, "ls /sys/class/power_supply/ 2>&1")
run(c, "vcgencmd get_throttled 2>&1 || true")
run(c, "dmesg 2>&1 | grep -iE 'under-voltage|throttl|power' | tail -10", sudo=True)

print("\n" + "=" * 70); print(" 5. Uptime + ultimos reboots"); print("=" * 70)
run(c, "uptime; last reboot 2>&1 | head -10")

print("\n" + "=" * 70); print(" 6. Logs del servicio (ultimos restarts)"); print("=" * 70)
run(c, "journalctl -u fincadiag-gateway --no-pager -n 30 2>&1 | tail -40", sudo=True)

c.close()
