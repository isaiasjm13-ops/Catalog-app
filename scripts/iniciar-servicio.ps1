# Lanzador comun del revisor (operator) y del generador publico (public).
# ASCII a proposito: evita problemas con la n de "Diseno2" en consolas cmd.
param(
    [Parameter(Mandatory)][ValidateSet('operator', 'public')][string]$Service,
    [int]$Port = 0,
    [int]$PublicPort = 8082,   # solo para operator: a que generador publico apuntar
    [switch]$NoPause
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$defaults = @{ operator = 8081; public = 8082 }
$exeNames = @{ operator = 'perfect-catalog-operator.exe'; public = 'perfect-catalog-public.exe' }
if ($Port -eq 0) { $Port = $defaults[$Service] }
$exe = Join-Path $root ".venv\Scripts\$($exeNames[$Service])"
$logDir = Join-Path $root 'logs'
$log = Join-Path $logDir "$Service-live.log"

function Write-Log($msg) {
    $line = "{0:yyyy-MM-dd HH:mm:ss}  {1}" -f (Get-Date), $msg
    try { Add-Content -LiteralPath $log -Value $line -Encoding UTF8 } catch { }
}

function Stop-WithMessage($msg, $code = 1) {
    Write-Host ""
    Write-Host "ERROR: $msg" -ForegroundColor Red
    Write-Log "ERROR: $msg"
    if (-not $NoPause) { Read-Host "Pulsa Enter para cerrar" | Out-Null }
    exit $code
}

function Get-Listener($p) {
    Get-NetTCPConnection -State Listen -LocalPort $p -ErrorAction SilentlyContinue | Select-Object -First 1
}

# Procesos python (shim del venv + hijo) cuya linea de comandos es este servicio.
function Get-ServiceProcesses($svc) {
    Get-CimInstance Win32_Process |
        Where-Object { $_.Name -match '^(python|pythonw|perfect-catalog)' -and $_.CommandLine -and $_.CommandLine -like "*perfect-catalog-$svc*" }
}

# Ultima modificacion del codigo fuente (py, plantillas, estaticos).
function Get-CodeStamp {
    Get-ChildItem (Join-Path $root 'src\perfect_catalog') -Recurse -File -Include *.py, *.html, *.js, *.css -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1 -ExpandProperty LastWriteTime
}

if (-not (Test-Path -LiteralPath $exe)) {
    Stop-WithMessage "No existe $exe. Falta instalar el entorno (.venv)."
}
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# 3. Postgres debe estar corriendo antes de pedir la contrasena.
$pg = Get-Service -Name 'postgresql*' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -eq $pg) {
    Write-Host "Aviso: no encontre un servicio PostgreSQL local; sigo por si la base esta en otra maquina." -ForegroundColor Yellow
} elseif ($pg.Status -ne 'Running') {
    Stop-WithMessage "Postgres esta apagado (servicio '$($pg.Name)': $($pg.Status)). Inicialo desde Servicios de Windows y vuelve a abrir este archivo."
}

# 7. Si ya hay una instancia de ESTE servicio en el puerto, ver si es vieja.
$listener = Get-Listener $Port
if ($listener) {
    $procs = @(Get-ServiceProcesses $Service)
    $stamp = Get-CodeStamp
    $stale = $false
    if ($procs.Count -gt 0 -and $stamp) {
        $started = ($procs | Sort-Object CreationDate | Select-Object -First 1).CreationDate
        $stale = $started -lt $stamp
    }
    if ($procs.Count -gt 0 -and $stale) {
        Write-Host "Hay un '$Service' viejo en el puerto $Port (arrancado antes del ultimo cambio de codigo). Lo reinicio." -ForegroundColor Yellow
        Write-Log "Reiniciando $Service viejo (PIDs: $($procs.ProcessId -join ','))"
        foreach ($p in $procs) { & taskkill.exe /PID $p.ProcessId /T /F 2>$null | Out-Null }
        Start-Sleep -Seconds 2
    } elseif ($procs.Count -gt 0) {
        Write-Host "El '$Service' ya esta corriendo y esta al dia: http://127.0.0.1:$Port" -ForegroundColor Green
        Write-Log "$Service ya corriendo en $Port (al dia); no se lanza otro"
        if ($Service -eq 'operator') { Start-Process "http://127.0.0.1:$Port" }
        if (-not $NoPause) { Read-Host "Pulsa Enter para cerrar" | Out-Null }
        exit 0
    }
}

# 1. Puerto libre: si lo ocupa otra cosa, usar el siguiente y decirlo.
$original = $Port
while (Get-Listener $Port) { $Port++ ; if ($Port -gt $original + 20) { Stop-WithMessage "No encontre un puerto libre cerca de $original." } }
if ($Port -ne $original) {
    Write-Host "El puerto $original estaba ocupado por otro programa; uso el $Port." -ForegroundColor Yellow
    Write-Log "Puerto $original ocupado; usando $Port"
}

$url = "http://127.0.0.1:$Port"
$argList = @('--host', '127.0.0.1', '--port', $Port, '--prompt-password')
if ($Service -eq 'operator') {
    $argList += @('--generate-access-code', '--open-browser', '--public-generator-url', "http://127.0.0.1:$PublicPort")
}

# 2. URL completa a la vista antes de arrancar.
Write-Host ""
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host "  $Service  ->  $url" -ForegroundColor Cyan
Write-Host "  El servidor se apaga al cerrar esta ventana." -ForegroundColor Cyan
Write-Host "==============================================" -ForegroundColor Cyan
Write-Host ""
Write-Log "Inicio $Service en $url"

& $exe @argList
$code = $LASTEXITCODE

# 4/5. El servidor termino: dejarlo escrito en el log y explicarlo en pantalla.
Write-Log "$Service termino con codigo $code"
Write-Host ""
if ($code -ne 0) {
    Write-Host "El servicio '$Service' se cerro con error (codigo $code)." -ForegroundColor Red
    Write-Host "Causas comunes: contrasena de Postgres incorrecta, Postgres apagado, puerto en uso." -ForegroundColor Red
    Write-Host "Detalle del arranque: $log" -ForegroundColor Red
} else {
    Write-Host "El servicio '$Service' se cerro normalmente."
}
if (-not $NoPause) { Read-Host "Pulsa Enter para cerrar" | Out-Null }
exit $code
