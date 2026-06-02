# Runbook — Pruebas de campo Objetivo 4

**Modo recomendado: AUTOMATIZADO** (ver sección "Modo automatizado" abajo).

Si querés correrlas manualmente paso a paso, seguí el orden estricto de las secciones A → I.

---

## Modo automatizado (RECOMENDADO)

Las pruebas se programan con `at` para ejecutarse en los huecos entre ordeños:

| Hora (Pi) | Tarea | Duración | Hueco |
|-----------|-------|----------|-------|
| 03:00 | MTTR stress (30 ciclos) | ~15 min | Entre 2AM y 5AM |
| 03:30 | Latencia E2E (10 ciclos) | ~5 min | Mismo hueco |
| 05:00 | Soak test (2h) | ~2 h | Entre 5AM y 7AM |
| 07:50 | Empaquetar resultados en `.tar.gz` | <1 min | Post 7AM capture |

### Paso 1: Subir scripts (Windows PowerShell)

```powershell
$PI = "esmeralda@gateway-esmeralda-ssh.at.remote.it"
$PORT = 33000
$LOCAL = "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests"

scp -P $PORT "$LOCAL\mttr_stress_pi.sh"      ${PI}:/home/esmeralda/
scp -P $PORT "$LOCAL\latency_e2e_pi.sh"      ${PI}:/home/esmeralda/
scp -P $PORT "$LOCAL\soak_test_pi.sh"        ${PI}:/home/esmeralda/
scp -P $PORT "$LOCAL\schedule_obj4_pi.sh"    ${PI}:/home/esmeralda/
```

### Paso 2: Programar las corridas (en la Pi vía SSH)

```powershell
ssh -p $PORT $PI
```

```bash
# Una sola vez: instalar 'at' si falta
sudo apt install -y at mosquitto-clients bc
sudo systemctl enable --now atd

chmod +x /home/esmeralda/*.sh

# Programar para mañana
bash /home/esmeralda/schedule_obj4_pi.sh tomorrow

# Verificar
bash /home/esmeralda/schedule_obj4_pi.sh status
```

Cerrar SSH (`exit`). Las corridas se ejecutan solas.

### Paso 3: Descargar el bundle (al día siguiente, después de 11:30)

```powershell
$DIA = (Get-Date).ToString("yyyy-MM-dd")
$DEST = "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular"

scp -P $PORT "${PI}:/home/esmeralda/obj4_bundle_${DIA}.tar.gz"      "$DEST\"
scp -P $PORT "${PI}:/home/esmeralda/obj4_bundle_${DIA}.tar.gz.md5"  "$DEST\"

# Extraer
tar -xzf "$DEST\obj4_bundle_${DIA}.tar.gz" -C $DEST
```

### Paso 4: Análisis en Windows

```powershell
python "$DEST\compute_plr.py"
python "$DEST\normality_tests.py"
```

### Cancelar / reprogramar

```bash
bash /home/esmeralda/schedule_obj4_pi.sh cancel    # cancela todo
bash /home/esmeralda/schedule_obj4_pi.sh status    # estado
```

---

## Modo manual (paso a paso)

## A. Subir scripts a la Pi (Windows PowerShell)

```powershell
$PI = "esmeralda@gateway-esmeralda-ssh.at.remote.it"
$PORT = 33000
$LOCAL = "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\Gateway\tests"

scp -P $PORT "$LOCAL\mttr_stress_pi.sh"     ${PI}:/home/esmeralda/
scp -P $PORT "$LOCAL\latency_e2e_pi.sh"     ${PI}:/home/esmeralda/
scp -P $PORT "$LOCAL\soak_test_pi.sh"       ${PI}:/home/esmeralda/
scp -P $PORT "$LOCAL\run_obj4_tests_pi.sh"  ${PI}:/home/esmeralda/
```

## B. Conectarse a la Pi y dar permisos

```powershell
ssh -p $PORT $PI
```

Dentro de la Pi:

```bash
chmod +x /home/esmeralda/*.sh
ls -lh /home/esmeralda/*.sh
```

## C. Verificar prerrequisitos en la Pi

```bash
# mosquitto-clients (para mosquitto_pub/sub)
which mosquitto_pub mosquitto_sub bc

# Si falta:
sudo apt install -y mosquitto-clients bc
```

## D. Test rápido de smoke (recomendado primero)

Antes de la corrida real, validar con muy pocos ciclos (~3 minutos):

```bash
bash /home/esmeralda/run_obj4_tests_pi.sh 5 3
```

Si todo PASS, seguir con la corrida real. Si falla, revisar el log:

```bash
tail -100 /home/esmeralda/obj4_master.log
```

## E. Corrida real (MTTR + Latencia, ~20 minutos)

```bash
bash /home/esmeralda/run_obj4_tests_pi.sh 30 10
```

Esperar a que termine. Vas a ver:
- 30 ciclos de MTTR (cada uno ~30s)
- 10 ciclos de Latencia (cada uno ~30s)
- Resumen final con archivos a descargar

## F. (Opcional) Soak test 2 horas

Lanzarlo en background con `nohup` para que sobreviva al cierre de la sesión SSH:

```bash
nohup bash /home/esmeralda/soak_test_pi.sh 2 60 > /home/esmeralda/soak_run.log 2>&1 &
echo "PID: $!"
```

Para verificar progreso después:

```bash
tail -f /home/esmeralda/soak_test.log
```

Para matar antes de tiempo si hace falta:

```bash
pkill -f soak_test_pi.sh
```

## G. Descargar resultados a Windows

Salir de la sesión SSH (`exit`) y desde PowerShell:

```powershell
$PI = "esmeralda@gateway-esmeralda-ssh.at.remote.it"
$PORT = 33000
$DEST = "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular"

scp -P $PORT ${PI}:/home/esmeralda/mttr_results.csv         "$DEST\"
scp -P $PORT ${PI}:/home/esmeralda/latency_e2e_results.csv  "$DEST\"
scp -P $PORT ${PI}:/home/esmeralda/soak_results.csv         "$DEST\"   # si corriste soak
scp -P $PORT ${PI}:/home/esmeralda/obj4_master.log          "$DEST\"
```

## H. Análisis en Windows

```powershell
$BASE = "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular"

# 1. PLR desde capturas existentes
python "$BASE\compute_plr.py"

# 2. Pruebas de normalidad sobre las 3 metricas
python "$BASE\normality_tests.py"
```

## I. Salidas esperadas

Al final tenés en `C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\`:

- `plr_results.json` — PLR por sesion + resumen pre/post + Mann-Whitney
- `mttr_results.csv` — 30 ciclos de MTTR
- `latency_e2e_results.csv` — 10 ciclos de latencia E2E
- `soak_results.csv` — (opcional) ciclos de soak con memoria/CPU
- `normality_results.json` — Shapiro-Wilk + recomendacion de test

Con esto se cierra el indicador del Objetivo 4.

## Pruebas complementarias de robustez (manuales)

Estas pruebas extienden el contraste de MTTR cubriendo modos de falla que los scripts automáticos no pueden simular sin tocar producción.

### Tabla escalonada de MTTR planeada

| Tipo de fallo | Script | n objetivo | Estadística |
|---|---|---|---|
| Caída de broker MQTT | `mttr_stress_pi.sh` | ≥30 | Mann-Whitney/t-test |
| Bloqueo de red (iptables) | `network_failure_pi.sh` | ≥30 | Mann-Whitney/t-test |
| Crash de proceso (runtime) | `power_failure_sim_pi.sh` | ≥20 | Mann-Whitney/t-test |
| Kill servicio + restart systemd | `mttr_systemd_pi.sh` | ≥10 | descriptiva + IC95 |
| Reboot físico (corte de energía) | manual cronómetro | 3–5 | descriptiva |

### A — MTTR systemd (kill servicio en producción)

Se ejecuta automáticamente vía `ssh_obj4_add_systemd.py`. Si se requiere correr manualmente:

```bash
ssh esmeralda@gateway-esmeralda-ssh.at.remote.it -p 33000
bash /home/esmeralda/mttr_systemd_pi.sh 10
cat /home/esmeralda/mttr_systemd_results.csv
```

Mide dos tiempos por ciclo:
- `kill -> active`: tiempo hasta que systemd reporta el servicio activo (incluye `RestartSec=5s`).
- `kill -> mqtt_ready`: tiempo hasta primera evidencia de conexión MQTT en `journalctl`.

### B — Reboot físico cronometrado (n=3–5)

Procedimiento manual el día 2 al final de la jornada:

1. **Preparación** (Windows): tener un suscriptor MQTT corriendo para detectar primer mensaje post-reboot:
   ```powershell
   mosquitto_sub -h <broker> -p 8883 --cafile ca.crt -t "fincadiag/la_esmeralda/#" -v
   ```
2. **Por cada ciclo** (repetir 3 a 5 veces):
   - Anotar `t0` con reloj (segundero) o cronómetro de celular.
   - Desconectar físicamente la alimentación de la Raspberry Pi.
   - Esperar 30 s.
   - Reconectar alimentación → la Pi arranca, systemd levanta `fincadiag-gateway` automáticamente (`enabled`).
   - Anotar `t1` cuando aparezca el primer mensaje en el suscriptor (o consultar `journalctl -u fincadiag-gateway --since` después).
   - `MTTR_energia = t1 - t0` (esperado: 60–120 s; depende de boot + `network-online.target`).
3. **Registro**: anotar en `/home/esmeralda/reboot_manual.csv` una vez recuperada la conexión:
   ```bash
   echo "ciclo,fecha,t0,t1,mttr_s,observacion" > /home/esmeralda/reboot_manual.csv
   echo "1,2026-05-29,21:30:00,21:31:45,105,ok" >> /home/esmeralda/reboot_manual.csv
   ```

**Nota**: con n=3–5 no aplica contraste estadístico, pero sirve como evidencia descriptiva del peor caso de recuperación realista. Reportar en tesis como cota superior del MTTR end-to-end.

---

## Troubleshooting rápido

| Problema | Solución |
|----------|----------|
| `mosquitto_pub: command not found` | `sudo apt install mosquitto-clients` |
| `Permission denied` al `systemctl stop` | Configurar sudoers: `esmeralda ALL=(ALL) NOPASSWD: /bin/systemctl stop mosquitto, /bin/systemctl start mosquitto` |
| Spool no se vacía | Ver `/var/log/fincadiag/gateway.log` o re-ejecutar el ciclo |
| SSH se cae a mitad | Usar `tmux` o `screen` antes de lanzar el test largo |
