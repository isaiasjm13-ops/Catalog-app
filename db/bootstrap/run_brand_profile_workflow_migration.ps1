$ErrorActionPreference = 'Stop'
$psqlPath = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$sqlPath = Join-Path $PSScriptRoot 'apply_brand_profile_workflow_migration.sql'
if (-not (Test-Path -LiteralPath $psqlPath)) { throw "psql no existe: $psqlPath" }
Write-Host 'Aplicando migracion 0014 de marca por importacion y catalogo.'
Write-Host 'La contrasena de postgres no muestra caracteres mientras se escribe.'
& $psqlPath -X -h localhost -p 5432 -U postgres -d perfect_catalog_dev -W -v ON_ERROR_STOP=1 -f $sqlPath
$exitCode = $LASTEXITCODE
Write-Host "Resultado de psql: $exitCode"
Read-Host 'Presione Enter para cerrar esta ventana'
exit $exitCode
