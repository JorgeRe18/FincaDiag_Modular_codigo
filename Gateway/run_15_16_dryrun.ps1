# Script para procesar sesiones de Visita_15_05_2026 y Visita_16_05_2026 en modo dry-run
# Compila resultados (published, spooled, failed, cow_event_count) por sesion

$ProjectRoot = "C:\Users\jorge\OneDrive\Documentos\FincaDiag_Modular"
$GatewayBat = "$ProjectRoot\Gateway\run_gateway.bat"
$OutputDir = "$ProjectRoot\data\gateway\published"
$ResultsFile = "$ProjectRoot\data\gateway\results_15_16_dryrun.txt"

# Visita 15/05 - todas las sesiones
$S15 = "$ProjectRoot\data\processed\visits\Visita_15_05_2026\sesiones"
# Visita 16/05 - todas las sesiones
$S16 = "$ProjectRoot\data\processed\visits\Visita_16_05_2026\sesiones"

$SessionDirs = @()
$SessionDirs += Get-ChildItem -Directory $S15 | Select-Object -ExpandProperty FullName
$SessionDirs += Get-ChildItem -Directory $S16 | Select-Object -ExpandProperty FullName

$Results = @()
$Total = $SessionDirs.Count
$Idx = 0

foreach ($Dir in $SessionDirs) {
    $Idx++
    $Name = Split-Path $Dir -Leaf
    Write-Host "[$Idx/$Total] Processing: $Name" -ForegroundColor Cyan
    
    # Clear previous published files for this session to avoid confusion
    $Existing = Get-ChildItem -Path $OutputDir -Filter "*.readable.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*$Name*" }
    if ($Existing) {
        $Existing | Remove-Item -Force
    }
    
    # Run gateway dry-run
    $Proc = Start-Process -FilePath "cmd.exe" -ArgumentList "/c `"$GatewayBat`" dry-run `"$Dir`"" -WorkingDirectory "$ProjectRoot\Gateway" -RedirectStandardOutput "$env:TEMP\gw_out.txt" -RedirectStandardError "$env:TEMP\gw_err.txt" -Wait -PassThru -WindowStyle Hidden
    $ExitCode = $Proc.ExitCode
    
    # Read output
    $OutText = ""
    if (Test-Path "$env:TEMP\gw_out.txt") {
        $OutText = Get-Content "$env:TEMP\gw_out.txt" -Raw
    }
    $ErrText = ""
    if (Test-Path "$env:TEMP\gw_err.txt") {
        $ErrText = Get-Content "$env:TEMP\gw_err.txt" -Raw
    }
    
    # Extract published/spooled/failed from output text
    $Published = if ($OutText -match 'published[:=]\s*(\d+)') { $matches[1] } else { "N/A" }
    $Spooled   = if ($OutText -match 'spooled[:=]\s*(\d+)')   { $matches[1] } else { "N/A" }
    $Failed    = if ($OutText -match 'failed[:=]\s*(\d+)')    { $matches[1] } else { "N/A" }
    
    # Count cow_event from readable.json
    $CowCount = 0
    $Readable = Get-ChildItem -Path $OutputDir -Filter "*.readable.json" -ErrorAction SilentlyContinue | Where-Object { $_.Name -like "*$Name*" } | Select-Object -First 1
    if ($Readable) {
        try {
            $Json = Get-Content $Readable.FullName -Raw | ConvertFrom-Json
            if ($Json.counts_by_event_type -and $Json.counts_by_event_type.cow_event) {
                $CowCount = [int]$Json.counts_by_event_type.cow_event
            }
            if ($Json.message_count) {
                $Published = $Json.message_count
            }
            if ($Json.counts_by_event_type) {
                # Could infer spooled/failed from other sources if available
            }
        } catch {
            # ignore json parse errors
        }
    }
    
    $Result = [PSCustomObject]@{
        Session     = $Name
        ExitCode    = $ExitCode
        Published   = $Published
        Spooled     = $Spooled
        Failed      = $Failed
        CowEvents   = $CowCount
        HasReadable = if ($Readable) { "Yes" } else { "No" }
    }
    $Results += $Result
    
    Write-Host "  -> published=$Published, spooled=$Spooled, failed=$Failed, cow_event=$CowCount, exit=$ExitCode" -ForegroundColor $(if ($ExitCode -eq 0) { "Green" } else { "Red" })
}

# Write results
"Dry-run results for Visita_15_05_2026 and Visita_16_05_2026" | Set-Content $ResultsFile
"Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" | Add-Content $ResultsFile
"" | Add-Content $ResultsFile

$Results | Format-Table -AutoSize | Out-String | Add-Content $ResultsFile

# Summary
$Success = ($Results | Where-Object { $_.ExitCode -eq 0 }).Count
$Fail = ($Results | Where-Object { $_.ExitCode -ne 0 }).Count
$TotalCow = ($Results | Measure-Object -Property CowEvents -Sum).Sum
$TotalPub = ($Results | Where-Object { $_.Published -ne "N/A" } | Measure-Object -Property { [int]$_.Published } -Sum).Sum

"" | Add-Content $ResultsFile
"SUMMARY" | Add-Content $ResultsFile
"Total sessions: $Total" | Add-Content $ResultsFile
"Successful: $Success" | Add-Content $ResultsFile
"Failed: $Fail" | Add-Content $ResultsFile
"Total published: $TotalPub" | Add-Content $ResultsFile
"Total cow_event: $TotalCow" | Add-Content $ResultsFile

Write-Host ""
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "DRY-RUN COMPLETE" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Yellow
Write-Host "Total sessions: $Total"
Write-Host "Successful: $Success"
Write-Host "Failed: $Fail"
Write-Host "Total cow_event: $TotalCow"
Write-Host "Results saved to: $ResultsFile"
