#!/usr/bin/env python3
"""Verificar estado de inyecciones del 31/05/2026 en Raspberry Pi."""
import paramiko

HOST = "gateway-esmeralda-ssh.at.remote.it"
PORT = 33000
USER = "esmeralda"
PASS = "fincaPPA26"

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(HOST, port=PORT, username=USER, password=PASS, timeout=30)

def run(cmd):
    s, o, e = c.exec_command(cmd)
    return o.read().decode(errors="replace").strip()

print("=" * 50)
print("VERIFICACION INYECCIONES 31/05")
print("=" * 50)

# 1. Jobs at pendientes (si quedan, algo fallo)
print("\n[1] Jobs 'at' pendientes:")
atq = run("atq")
print(atq if atq else "  (ninguno pendiente = todos ejecutados)")

# 2. Inyecciones registradas
print("\n[2] Inyecciones registradas:")
faults = run("cat /home/esmeralda/fault_injections.csv 2>/dev/null || echo NO_EXISTE")
print(faults)

# 3. Mediciones de resiliencia
print("\n[3] Mediciones de resiliencia:")
res = run("cat /home/esmeralda/live_resilience_results.csv 2>/dev/null || echo NO_EXISTE")
print(res)

# 4. Capturas raw del 31/05
print("\n[4] Capturas raw del 31/05:")
raw = run("ls /var/lib/fincadiag/raw/ | grep 20260531 || echo NO_CAPTURAS_31MAY")
print(raw)

# 5. Publicaciones del 31/05
print("\n[5] Publicaciones .jsonl del 31/05:")
pub = run("find /var/lib/fincadiag/published -name '*.jsonl' -newermt '2026-05-31' ! -newermt '2026-06-01' -exec basename {} \; 2>/dev/null || echo NO_PUBLICACIONES")
print(pub)

# 6. Estado de servicios
print("\n[6] Estado de servicios:")
print("  fincadiag-gateway:", run("systemctl is-active fincadiag-gateway"))
print("  mosquitto        :", run("systemctl is-active mosquitto"))
print("  spool residual   :", run("ls /var/lib/fincadiag/spool/ | wc -l"), "archivos")

print("\n" + "=" * 50)
print("FIN VERIFICACION")
print("=" * 50)

c.close()
