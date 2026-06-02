# Exportacion automatica de visitas desde Raspberry Pi

El problema: WinSCP se vuelve lento al transferir miles de archivos pequenos uno por uno.
La solucion: la Pi comprime cada visita en un **solo archivo .tar.gz** al final del dia.
Asi WinSCP solo baja 1 archivo grande (100-500 MB tipico) en lugar de 5,000+ archivos.

## Flujo de trabajo

```
[Pi] Captura ordeño --> [Pi] Procesa visita --> [Pi] tar.gz automatico a las 23:30
                                                    |
[PC] WinSCP: descarga 1 archivo .tar.gz <-----------+
[PC] extract_and_import.bat --> data/processed/visits/
```

## Archivos incluidos

| Archivo | Plataforma | Funcion |
|---------|-----------|---------|
| `export_visita_pi.sh` | Raspberry Pi | Comprime una visita en tar.gz (uso manual o cron) |
| `setup_cron_export.sh` | Raspberry Pi | Instala cron job para exportar automatico diario |
| `pull_from_pi.ps1` | Windows | PowerShell helper para descarga automatica (requiere setup SSH key) |
| `extract_and_import.bat` | Windows | Extrae el tar.gz descargado a `data/processed/visits/` |

---

## Instalacion en la Raspberry Pi (hacer una sola vez)

### Paso 1: Subir scripts a la Pi

Desde tu PC, con WinSCP o el terminal:

```bash
# En la Pi
mkdir -p /home/esmeralda/exports
chmod +x /home/esmeralda/export_visita_pi.sh
```

### Paso 2: Probar manualmente

```bash
# En la Pi
./export_visita_pi.sh Visita_17_05_2026
```

Deberia crear dos archivos:
- `/home/esmeralda/exports/Visita_17_05_2026.tar.gz`
- `/home/esmeralda/exports/Visita_17_05_2026.tar.gz.md5` (checksum de integridad)

### Paso 3: Instalar exportacion automatica diaria

```bash
# En la Pi, como usuario esmeralda
crontab -e
```

Agregar esta linea:

```
30 23 * * * /home/esmeralda/export_visita_pi.sh "$(date -d 'yesterday' +Visita_%d_%m_%Y)" >> /home/esmeralda/exports/cron.log 2>&1
```

Guardar y salir. Esto comprime automaticamente la visita del dia anterior a las **23:30 cada noche**, generando el `.tar.gz` y su `.md5` en `/home/esmeralda/exports/`.

Verificar:
```bash
crontab -l
```

---

## Descarga en Windows (tres opciones)

### Opcion A: WinSCP manual (rapido porque es 1 archivo + checksum)

1. Abrir WinSCP
2. Navegar a `/home/esmeralda/exports/`
3. Descargar **ambos archivos**:
   - `Visita_XX_XX_XXXX.tar.gz`
   - `Visita_XX_XX_XXXX.tar.gz.md5`
4. Correr en CMD:
   ```batch
   extract_and_import.bat C:\Users\%USERNAME%\Downloads\Visita_XX_XX_XXXX.tar.gz
   ```
   El script verifica automaticamente el MD5 antes de extraer. Si no coincide, aborta.

### Opcion B: Script automatico con clave SSH (sin password)

Generar clave SSH en Windows (sin password):

```batch
ssh-keygen -t ed25519 -f %USERPROFILE%\.ssh\pi_esmeralda -N ""
scp -P 33000 %USERPROFILE%\.ssh\pi_esmeralda.pub esmeralda@gateway-esmeralda-ssh.at.remote.it:/home/esmeralda/.ssh/authorized_keys
```

Luego editar `pull_from_pi.ps1` y descomentar la seccion de key auth.

### Opcion C: Comando scp directo (si ya tienes clave o password)

```batch
scp -P 33000 esmeralda@gateway-esmeralda-ssh.at.remote.it:/home/esmeralda/exports/Visita_17_05_2026.tar.gz C:\Users\%USERNAME%\Downloads\
```

---

## Comparacion de velocidad estimada

| Metodo | Archivos transferidos | Tiempo estimado (visita tipica) |
|--------|----------------------|--------------------------------|
| WinSCP individual (original) | ~5,000 archivos | 15-30 minutos |
| **tar.gz unico (nuevo)** | **1 archivo** | **30-60 segundos** |

El tar.gz tambien mantiene permisos y estructura de directorios intactos.
