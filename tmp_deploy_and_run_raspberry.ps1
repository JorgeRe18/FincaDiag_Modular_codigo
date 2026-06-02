# Script PowerShell: Sincroniza sesiones y ejecuta gateway en Raspberry
# Ejecutar desde Windows PowerShell en la carpeta del proyecto
#   .\tmp_deploy_and_run_raspberry.ps1

$RASPBERRY_USER = "esmeralda"
$RASPBERRY_HOST = "gateway-esmeralda-ssh.at.remote.it"
$RASPBERRY_PORT = 33000
$RASPBERRY_DEST = "/var/lib/fincadiag/processed/visits"

$localVisits = @(
    "data\processed\visits\Visita_11_05_2026",
    "data\processed\visits\Visita_12_05_2026",
    "data\processed\visits\Visita_13_05_2026",
    "data\processed\visits\Visita_14_05_2026"
)

$sshPrefix = "${RASPBERRY_USER}@${RASPBERRY_HOST}"

Write-Host "========================================"
Write-Host "FincaDiag - Gateway en Raspberry"
Write-Host "========================================"

# 1. Verificar conexion SSH
Write-Host ""
Write-Host "1. Verificando conexion SSH..."
$test = ssh -p $RASPBERRY_PORT -o ConnectTimeout=10 $sshPrefix "hostname" 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "No se pudo conectar a la Raspberry via SSH. Verifica remote.it y la conexion."
    exit 1
}
Write-Host "   Conectado a: $test"

# 2. Subir sesiones procesadas
Write-Host ""
Write-Host "2. Sincronizando sesiones procesadas..."
foreach ($visit in $localVisits) {
    $visitName = Split-Path $visit -Leaf
    Write-Host "   -> $visitName"
    scp -P $RASPBERRY_PORT -r $visit "${sshPrefix}:${RASPBERRY_DEST}/"
}

# 3. Subir script bash de ejecucion
Write-Host ""
Write-Host "3. Subiendo script de ejecucion..."
scp -P $RASPBERRY_PORT "tmp_run_4_sessions_raspberry_production.sh" "${sshPrefix}:/tmp/"
ssh -p $RASPBERRY_PORT $sshPrefix "chmod +x /tmp/tmp_run_4_sessions_raspberry_production.sh"

# 4. Ejecutar en Raspberry
Write-Host ""
Write-Host "4. Ejecutando gateway en Raspberry (PRODUCCION TLS)..."
Write-Host "   Esto puede tardar varios minutos."
ssh -p $RASPBERRY_PORT $sshPrefix "bash /tmp/tmp_run_4_sessions_raspberry_production.sh" | Tee-Object -FilePath "gateway_raspberry_output.txt"

# 5. Descargar resultados
Write-Host ""
Write-Host "5. Descargando resultados..."
$remotePublished = "/var/lib/fincadiag/published"
$localPublished = "data\gateway\published\raspberry"
New-Item -ItemType Directory -Force -Path $localPublished | Out-Null
scp -P $RASPBERRY_PORT "${sshPrefix}:${remotePublished}/*.readable.json" "$localPublished/"

Write-Host ""
Write-Host "========================================"
Write-Host "COMPLETADO"
Write-Host "Resultados en: $localPublished"
Write-Host "Log en: gateway_raspberry_output.txt"
Write-Host "========================================"
