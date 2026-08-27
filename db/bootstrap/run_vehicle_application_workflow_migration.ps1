$ErrorActionPreference = 'Stop'
$psqlPath = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$sqlPath = Join-Path $PSScriptRoot 'apply_vehicle_application_workflow_migration.sql'
$resultPath = Join-Path $env:LOCALAPPDATA 'Temp\perfect_catalog_0012.exit'
if (Test-Path -LiteralPath $resultPath) { Remove-Item -LiteralPath $resultPath -Force }
if (-not (Test-Path -LiteralPath $psqlPath)) { throw "psql no existe en la ruta esperada: $psqlPath" }
Write-Host 'Aplicando migracion 0012 de aplicaciones vehiculares en perfect_catalog_dev.'
Write-Host 'La contrasena de postgres no muestra caracteres mientras se escribe.'
& $psqlPath -X -h localhost -p 5432 -U postgres -d perfect_catalog_dev -W -v ON_ERROR_STOP=1 -f $sqlPath
$exitCode = $LASTEXITCODE
Set-Content -LiteralPath $resultPath -Value $exitCode -Encoding ascii
Write-Host "Resultado de psql: $exitCode"
Read-Host 'Presione Enter para cerrar esta ventana'
exit $exitCode
