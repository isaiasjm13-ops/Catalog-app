$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$postgresBin = 'C:\Program Files\PostgreSQL\18\bin'
$psqlPath = Join-Path $postgresBin 'psql.exe'
$dumpPath = Join-Path $postgresBin 'pg_dump.exe'
$restorePath = Join-Path $postgresBin 'pg_restore.exe'
$auditSql = Join-Path $projectRoot 'db\validation\audit_pre_multicompany.sql'

foreach ($required in @($psqlPath, $dumpPath, $restorePath, $auditSql)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "No existe el recurso requerido: $required" }
}

$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$phaseRoot = Join-Path $projectRoot 'backups\phase0-multicompany'
$backupFile = Join-Path $phaseRoot "perfect_catalog_dev-$timestamp.dump"
$backupList = Join-Path $phaseRoot "perfect_catalog_dev-$timestamp.contents.txt"
$backupHash = Join-Path $phaseRoot "perfect_catalog_dev-$timestamp.sha256.txt"
$backupHash = Join-Path $phaseRoot "perfect_catalog_dev-$timestamp.sha256.txt"
$auditReport = Join-Path $phaseRoot "audit-pre-multicompany-$timestamp.txt"
New-Item -ItemType Directory -Force -Path $phaseRoot | Out-Null

Write-Host 'FASE 0 - PREPARACION MULTIEMPRESA' -ForegroundColor Cyan
Write-Host 'La contraseña de postgres se solicita de forma oculta y no se guarda.'
$securePassword = Read-Host 'Contraseña de PostgreSQL para postgres' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)

    Write-Host '1/3 Creando backup lógico completo...'
    & $dumpPath -w -h 127.0.0.1 -p 5432 -U postgres -d perfect_catalog_dev `
        --format=custom --no-owner --file=$backupFile
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $backupFile)) {
        throw "pg_dump no pudo crear el backup (código $LASTEXITCODE)."
    }

    Write-Host '2/3 Verificando que el backup sea legible...'
    & $restorePath --list $backupFile | Out-File -LiteralPath $backupList -Encoding utf8
    if ($LASTEXITCODE -ne 0 -or (Get-Item -LiteralPath $backupList).Length -lt 100) {
        throw "pg_restore no pudo verificar el backup (código $LASTEXITCODE)."
    }
    $hash = Get-FileHash -LiteralPath $backupFile -Algorithm SHA256
    ($hash.Hash.ToLowerInvariant() + '  ' + (Split-Path -Leaf $backupFile)) |
        Set-Content -LiteralPath $backupHash -Encoding ascii
    $hash = Get-FileHash -LiteralPath $backupFile -Algorithm SHA256
    ($hash.Hash.ToLowerInvariant() + '  ' + (Split-Path -Leaf $backupFile)) |
        Set-Content -LiteralPath $backupHash -Encoding ascii

    Write-Host '3/3 Ejecutando auditoría SQL de solo lectura...'
    & $psqlPath -X -w -h 127.0.0.1 -p 5432 -U postgres -d perfect_catalog_dev `
        -v ON_ERROR_STOP=1 -f $auditSql | Out-File -LiteralPath $auditReport -Encoding utf8
    if ($LASTEXITCODE -ne 0 -or (Get-Item -LiteralPath $auditReport).Length -lt 100) {
        throw "psql no pudo completar la auditoría (código $LASTEXITCODE)."
    }

    Write-Host 'FASE 0 COMPLETADA.' -ForegroundColor Green
    Write-Host "Backup: $backupFile"
    Write-Host "Verificación: $backupList"
    Write-Host "Checksum: $backupHash"
    Write-Host "Checksum: $backupHash"
    Write-Host "Auditoría: $auditReport"
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    $securePassword = $null
}

Read-Host 'Presione Enter para cerrar esta ventana'
