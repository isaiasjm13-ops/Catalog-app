# Respaldo manual de la base. La contrasena se pide oculta y nunca se guarda.
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$pgDumpPath = 'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe'
$databaseName = 'perfect_catalog_dev'
$backupDir = Join-Path $projectRoot 'backups'

if (-not (Test-Path -LiteralPath $pgDumpPath)) { throw "pg_dump no existe: $pgDumpPath" }
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

Write-Host 'RESPALDAR BASE - Perfect Catalog' -ForegroundColor Cyan
$securePassword = Read-Host 'Contrasena de PostgreSQL para postgres (entrada oculta)' -AsSecureString
$pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $target = Join-Path $backupDir "$databaseName-$stamp.dump"
    & $pgDumpPath -w -h localhost -p 5432 -U postgres -d $databaseName -F c -f $target
    if ($LASTEXITCODE -ne 0) {
        if (Test-Path -LiteralPath $target) { Remove-Item -LiteralPath $target -Force }
        throw "pg_dump termino con codigo $LASTEXITCODE (contrasena incorrecta o Postgres apagado)."
    }
    $mb = [math]::Round((Get-Item -LiteralPath $target).Length / 1MB, 1)
    Write-Host "Respaldo listo: $target ($mb MB)" -ForegroundColor Green
}
finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    $securePassword = $null
}
Read-Host 'Presione Enter para cerrar esta ventana'
