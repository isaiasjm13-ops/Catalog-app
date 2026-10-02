# Arranca generador publico + revisor, apuntando el revisor al puerto REAL del publico.
# ASCII a proposito (la n de "Diseno2" rompe consolas cmd).
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$launcher = Join-Path $here 'iniciar-servicio.ps1'

function Test-PortBusy($p) {
    [bool](Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue)
}

# Si ya hay un generador publico corriendo, reutilizar su puerto (el lanzador decide si esta viejo).
$publicPort = 0
$existing = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -and $_.CommandLine -like '*perfect-catalog-public*' } |
    Select-Object -First 1
if ($existing -and $existing.CommandLine -match '--port\s+(\d+)') { $publicPort = [int]$Matches[1] }

# Si no, elegir el primer puerto libre desde 8082 (8081 queda para el revisor).
if ($publicPort -eq 0) {
    $publicPort = 8082
    while ((Test-PortBusy $publicPort) -or $publicPort -eq 8081) { $publicPort++ }
}
Write-Host "Generador publico: http://127.0.0.1:$publicPort" -ForegroundColor Cyan

Start-Process powershell.exe -ArgumentList @(
    '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$launcher`"",
    '-Service', 'public', '-Port', $publicPort
)

& $launcher -Service operator -PublicPort $publicPort
exit $LASTEXITCODE
