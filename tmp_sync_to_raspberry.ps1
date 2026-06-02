# Script para transferir sesiones procesadas de Windows a Raspberry
# Ejecutar en PowerShell como Administrador si es necesario

$RASPBERRY_USER = "esmeralda"
$RASPBERRY_HOST = "gateway-esmeralda-ssh.at.remote.it"
$RASPBERRY_PORT = 33000
$RASPBERRY_DEST = "/var/lib/fincadiag/processed/visits"

$localVisits = @(
    "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_15_05_2026",
    "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular\data\processed\visits\Visita_16_05_2026"
)

foreach ($visit in $localVisits) {
    $visitName = Split-Path $visit -Leaf
    Write-Host "Transferiendo $visitName ..."
    $destPath = "${RASPBERRY_USER}@${RASPBERRY_HOST}:${RASPBERRY_DEST}/"
    scp -P $RASPBERRY_PORT -r $visit $destPath
}

Write-Host "Transferencia completada."
