$ErrorActionPreference = 'Stop'
$psqlPath = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$sqlPath = Join-Path $PSScriptRoot 'apply_pending_migrations.sql'
if (-not (Test-Path -LiteralPath $psqlPath)) { throw "psql no existe: $psqlPath" }
if (-not (Test-Path -LiteralPath $sqlPath)) { throw "No existe el actualizador: $sqlPath" }
Write-Host 'ACTUALIZAR SISTEMA - Perfect Catalog'
Write-Host 'Detecta y aplica solamente los cambios pendientes (0007-0014).'
Write-Host 'La contrasena de postgres no muestra caracteres mientras se escribe.'
& $psqlPath -X -h localhost -p 5432 -U postgres -d perfect_catalog_dev -W -v ON_ERROR_STOP=1 -f $sqlPath
$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    Write-Host 'ACTUALIZACION COMPLETADA.' -ForegroundColor Green
} else {
    Write-Host "ACTUALIZACION NO COMPLETADA (psql: $exitCode)." -ForegroundColor Red
}
Read-Host 'Presione Enter para cerrar esta ventana'
exit $exitCode
