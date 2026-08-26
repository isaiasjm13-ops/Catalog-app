$ErrorActionPreference = 'Stop'

$psqlPath = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$sqlPath = Join-Path $PSScriptRoot 'apply_intake_promotion_migration.sql'
$resultPath = Join-Path $env:LOCALAPPDATA 'Temp\perfect_catalog_0008.exit'
$logPath = Join-Path $env:LOCALAPPDATA 'Temp\perfect_catalog_0008.log'

if (Test-Path -LiteralPath $resultPath) { Remove-Item -LiteralPath $resultPath -Force }
if (Test-Path -LiteralPath $logPath) { Remove-Item -LiteralPath $logPath -Force }
if (-not (Test-Path -LiteralPath $psqlPath)) { throw "psql no existe en la ruta esperada: $psqlPath" }

Write-Host 'Aplicando migracion 0008 en perfect_catalog_dev.'
Write-Host 'La contrasena de postgres no muestra caracteres mientras se escribe.'
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $psqlPath -X -h localhost -p 5432 -U postgres -d perfect_catalog_dev -W -v ON_ERROR_STOP=1 -f $sqlPath 2>&1 |
    Tee-Object -FilePath $logPath
$exitCode = $LASTEXITCODE
$ErrorActionPreference = $previousErrorActionPreference
Set-Content -LiteralPath $resultPath -Value $exitCode -Encoding ascii
Write-Host "Resultado de psql: $exitCode"
Write-Host "Diagnostico tecnico: $logPath"
Read-Host 'Presione Enter para cerrar esta ventana'
exit $exitCode
