# pull_from_pi.ps1
# Descarga automatica del export .tar.gz mas reciente desde la Raspberry Pi.
# Requiere que la Pi ya haya corrido export_visita_pi.sh.
# Usa el cliente SCP incluido en Windows 10/11 (OpenSSH).
#
# Uso:
#   .\pull_from_pi.ps1 -Visita Visita_20_05_2026
#   .\pull_from_pi.ps1              # descarga el mas reciente en /home/esmeralda/exports/

param(
    [string]$Visita = "",
    [string]$PiHost = "gateway-esmeralda-ssh.at.remote.it",
    [int]$PiPort = 33000,
    [string]$PiUser = "esmeralda",
    [string]$LocalDest = "C:\Users\$env:USERNAME\OneDrive\Documentos\FincaDiag_Modular\data\raw\pi_imports",
    [string]$RemoteExportDir = "/home/esmeralda/exports"
)

# Crear directorio local
New-Item -ItemType Directory -Force -Path $LocalDest | Out-Null

# Pedir password (se puede hardcodear o usar key auth en el futuro)
$pass = Read-Host -Prompt "Password para ${PiUser}@${PiHost}" -AsSecureString
$cred = New-Object System.Management.Automation.PSCredential($PiUser, $pass)
$BSTR = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($pass)
$plainPass = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($BSTR)

if ($Visita) {
    $RemoteFile = "${RemoteExportDir}/${Visita}.tar.gz"
    $LocalFile = Join-Path $LocalDest "${Visita}.tar.gz"
} else {
    # Encontrar el tar.gz mas reciente en la Pi
    $sshCmd = "ls -t ${RemoteExportDir}/*.tar.gz 2>/dev/null | head -1"
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "ssh"
    $psi.Arguments = "-p ${PiPort} ${PiUser}@${PiHost} `"${sshCmd}`""
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.StandardOutputEncoding = [System.Text.Encoding]::UTF8
    $proc = [System.Diagnostics.Process]::Start($psi)
    $remotePath = $proc.StandardOutput.ReadToEnd().Trim()
    $proc.WaitForExit()

    if (-not $remotePath) {
        Write-Error "No se encontro ningun .tar.gz en ${RemoteExportDir} de la Pi. Corre primero export_visita_pi.sh en la Pi."
        exit 1
    }
    $fileName = Split-Path $remotePath -Leaf
    $LocalFile = Join-Path $LocalDest $fileName
    $RemoteFile = $remotePath
}

Write-Host "=== Descargando desde Raspberry Pi ==="
Write-Host "  Remoto:  ${PiUser}@${PiHost}:${RemoteFile}"
Write-Host "  Local:   ${LocalFile}"

# Usar scp para descargar
# Nota: sshpass no esta en Windows por defecto, asi que usamos expect alternativa con key auth
# o mejor: generar clave SSH sin password para automatizar esto.
# Por ahora, documentamos que requiere password o key auth.

Write-Host ""
Write-Host "Comando para ejecutar manualmente (si no tienes key auth):"
Write-Host "  scp -P ${PiPort} ${PiUser}@${PiHost}:${RemoteFile} `"${LocalFile}`""
Write-Host ""
Write-Host "Para automatizar completamente, genera una clave SSH sin password:"
Write-Host "  ssh-keygen -t ed25519 -f %USERPROFILE%\.ssh\pi_esmeralda"
Write-Host "  scp -P ${PiPort} %USERPROFILE%\.ssh\pi_esmeralda.pub ${PiUser}@${PiHost}:/home/${PiUser}/.ssh/authorized_keys"
Write-Host "  Luego este script puede correr sin intervencion."
