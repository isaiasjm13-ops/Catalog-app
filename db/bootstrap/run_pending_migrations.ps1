$ErrorActionPreference = 'Stop'
$psqlPath = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$sqlPath = Join-Path $PSScriptRoot 'apply_pending_migrations.sql'
$migration0017 = Join-Path $PSScriptRoot '..\migrations\0017_migration_ledger.sql'
$migration0018 = Join-Path $PSScriptRoot '..\migrations\0018_companies.sql'
if (-not (Test-Path -LiteralPath $psqlPath)) { throw "psql no existe: $psqlPath" }
if (-not (Test-Path -LiteralPath $sqlPath)) { throw "No existe el actualizador: $sqlPath" }
$checksum0017 = (Get-FileHash -LiteralPath $migration0017 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0018 = (Get-FileHash -LiteralPath $migration0018 -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Host 'ACTUALIZAR SISTEMA - Perfect Catalog'
Write-Host 'Detecta y aplica solamente los cambios pendientes (0007-0018).'
Write-Host 'La contrasena de postgres no muestra caracteres mientras se escribe.'
& $psqlPath -X -h localhost -p 5432 -U postgres -d perfect_catalog_dev -W `
    -v ON_ERROR_STOP=1 -v "checksum_0017=$checksum0017" -v "checksum_0018=$checksum0018" -f $sqlPath
$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    Write-Host 'ACTUALIZACION COMPLETADA.' -ForegroundColor Green
} else {
    Write-Host "ACTUALIZACION NO COMPLETADA (psql: $exitCode)." -ForegroundColor Red
}
Read-Host 'Presione Enter para cerrar esta ventana'
exit $exitCode
