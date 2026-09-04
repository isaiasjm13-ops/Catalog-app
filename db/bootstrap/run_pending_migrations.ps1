$ErrorActionPreference = 'Stop'
$psqlPath = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$sqlPath = Join-Path $PSScriptRoot 'apply_pending_migrations.sql'
$migration0017 = Join-Path $PSScriptRoot '..\migrations\0017_migration_ledger.sql'
$migration0018 = Join-Path $PSScriptRoot '..\migrations\0018_companies.sql'
$migration0019 = Join-Path $PSScriptRoot '..\migrations\0019_company_visual_identity.sql'
$migration0020 = Join-Path $PSScriptRoot '..\migrations\0020_company_intake_context.sql'
$migration0021 = Join-Path $PSScriptRoot '..\migrations\0021_company_administration.sql'
$migration0022 = Join-Path $PSScriptRoot '..\migrations\0022_controlled_product_updates.sql'
$migration0023 = Join-Path $PSScriptRoot '..\migrations\0023_brand_profile_linking.sql'
$migration0024 = Join-Path $PSScriptRoot '..\migrations\0024_intake_submission_archiving.sql'
$migration0025 = Join-Path $PSScriptRoot '..\migrations\0025_natsuki_company_restored.sql'
$migration0026 = Join-Path $PSScriptRoot '..\migrations\0026_product_photo_variants.sql'
$migration0027 = Join-Path $PSScriptRoot '..\migrations\0027_image_variant_letter_suffix.sql'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$logDirectory = Join-Path $projectRoot 'logs'
$logPath = Join-Path $logDirectory 'actualizar-sistema-ultimo.log'
if (-not (Test-Path -LiteralPath $psqlPath)) { throw "psql no existe: $psqlPath" }
if (-not (Test-Path -LiteralPath $sqlPath)) { throw "No existe el actualizador: $sqlPath" }
$checksum0017 = (Get-FileHash -LiteralPath $migration0017 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0018 = (Get-FileHash -LiteralPath $migration0018 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0019 = (Get-FileHash -LiteralPath $migration0019 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0020 = (Get-FileHash -LiteralPath $migration0020 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0021 = (Get-FileHash -LiteralPath $migration0021 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0022 = (Get-FileHash -LiteralPath $migration0022 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0023 = (Get-FileHash -LiteralPath $migration0023 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0024 = (Get-FileHash -LiteralPath $migration0024 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0025 = (Get-FileHash -LiteralPath $migration0025 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0026 = (Get-FileHash -LiteralPath $migration0026 -Algorithm SHA256).Hash.ToLowerInvariant()
$checksum0027 = (Get-FileHash -LiteralPath $migration0027 -Algorithm SHA256).Hash.ToLowerInvariant()
New-Item -ItemType Directory -Path $logDirectory -Force | Out-Null
Write-Host 'ACTUALIZAR SISTEMA - Perfect Catalog'
Write-Host 'Detecta y aplica solamente los cambios pendientes (0007-0027).'
Write-Host 'La contrasena de postgres no muestra caracteres mientras se escribe.'
# psql escribe NOTICE y errores en stderr; el codigo de salida es la senal fiable.
$ErrorActionPreference = 'Continue'
& $psqlPath -X -h localhost -p 5432 -U postgres -d perfect_catalog_dev -W `
    -v ON_ERROR_STOP=1 -v "checksum_0017=$checksum0017" -v "checksum_0018=$checksum0018" `
    -v "checksum_0019=$checksum0019" -v "checksum_0020=$checksum0020" `
    -v "checksum_0021=$checksum0021" -v "checksum_0022=$checksum0022" `
    -v "checksum_0023=$checksum0023" -v "checksum_0024=$checksum0024" `
    -v "checksum_0025=$checksum0025" -v "checksum_0026=$checksum0026" `
    -v "checksum_0027=$checksum0027" -f $sqlPath 2>&1 |
    Tee-Object -FilePath $logPath
$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    Write-Host 'ACTUALIZACION COMPLETADA.' -ForegroundColor Green
} else {
    Write-Host "ACTUALIZACION NO COMPLETADA (psql: $exitCode)." -ForegroundColor Red
    Write-Host "Diagnostico guardado en: $logPath" -ForegroundColor Yellow
}
Read-Host 'Presione Enter para cerrar esta ventana'
exit $exitCode
