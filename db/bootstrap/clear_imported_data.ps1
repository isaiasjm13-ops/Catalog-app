$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$dataRoot = (Resolve-Path -LiteralPath (Join-Path $projectRoot 'data')).Path
$backupRoot = Join-Path $dataRoot 'backups'
$psqlPath = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$pgDumpPath = 'C:\Program Files\PostgreSQL\18\bin\pg_dump.exe'
$sqlPath = Join-Path $PSScriptRoot 'reset_imported_data.sql'
$databaseName = 'perfect_catalog_dev'
$activeFolders = @('imports', 'intake', 'images', 'exports')

function Assert-ChildPath {
    param([string]$Candidate, [string]$Parent)
    $fullCandidate = [IO.Path]::GetFullPath($Candidate).TrimEnd('\')
    $fullParent = [IO.Path]::GetFullPath($Parent).TrimEnd('\')
    if (-not $fullCandidate.StartsWith($fullParent + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Ruta fuera del directorio permitido: $fullCandidate"
    }
}

if (-not (Test-Path -LiteralPath $psqlPath)) { throw "psql no existe: $psqlPath" }
if (-not (Test-Path -LiteralPath $pgDumpPath)) { throw "pg_dump no existe: $pgDumpPath" }
if (-not (Test-Path -LiteralPath $sqlPath)) { throw "SQL de limpieza no existe: $sqlPath" }

$listener = Get-NetTCPConnection -LocalPort 8081 -State Listen -ErrorAction SilentlyContinue
if ($listener) {
    throw 'Cierra primero INICIAR-REVISOR: el puerto 8081 sigue en uso.'
}

Write-Host ''
Write-Host 'LIMPIEZA DE IMPORTACIONES DE PERFECT CATALOG' -ForegroundColor Yellow
Write-Host 'Se conservaran PostgreSQL, usuarios, contrasenas, migraciones y el programa.'
Write-Host 'Se retiraran de uso los Excel, imagenes, ingresos, planes, productos y exportaciones.'
Write-Host 'Antes se creara un respaldo recuperable en data\backups.'
Write-Host ''
$confirmation = Read-Host 'Escribe LIMPIAR IMPORTACIONES para continuar'
if ($confirmation -cne 'LIMPIAR IMPORTACIONES') {
    Write-Host 'Cancelado. No se modifico nada.'
    exit 0
}

$securePassword = Read-Host 'Contrasena de PostgreSQL (entrada oculta)' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $backupDir = Join-Path $backupRoot "limpieza-$stamp"
    Assert-ChildPath -Candidate $backupDir -Parent $dataRoot
    New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

    $databaseBackup = Join-Path $backupDir "$databaseName.dump"
    Write-Host 'Creando respaldo de PostgreSQL...'
    & $pgDumpPath -h localhost -p 5432 -U postgres -d $databaseName -F c -f $databaseBackup
    if ($LASTEXITCODE -ne 0) { throw "pg_dump termino con codigo $LASTEXITCODE" }

    $filesBackup = Join-Path $backupDir 'archivos'
    New-Item -ItemType Directory -Path $filesBackup -Force | Out-Null
    foreach ($folderName in $activeFolders) {
        $source = Join-Path $dataRoot $folderName
        $destination = Join-Path $filesBackup $folderName
        Assert-ChildPath -Candidate $source -Parent $dataRoot
        Assert-ChildPath -Candidate $destination -Parent $backupDir
        New-Item -ItemType Directory -Path $destination -Force | Out-Null
        if (Test-Path -LiteralPath $source) {
            Get-ChildItem -LiteralPath $source -Force | Move-Item -Destination $destination -Force
        }
        else {
            New-Item -ItemType Directory -Path $source -Force | Out-Null
        }
        New-Item -ItemType File -Path (Join-Path $source '.gitkeep') -Force | Out-Null
    }

    Write-Host 'Limpiando datos y reaplicando migraciones...'
    & $psqlPath -X -h localhost -p 5432 -U postgres -d $databaseName -v ON_ERROR_STOP=1 -f $sqlPath
    if ($LASTEXITCODE -ne 0) {
        throw "psql termino con codigo $LASTEXITCODE. El respaldo esta en: $backupDir"
    }

    Write-Host ''
    Write-Host 'LISTO: Perfect Catalog quedo sin importaciones.' -ForegroundColor Green
    Write-Host "Respaldo recuperable: $backupDir"
    Write-Host 'Ya puedes abrir INICIAR-REVISOR.cmd e importar un Excel nuevo.'
}
finally {
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
}

Read-Host 'Presione Enter para cerrar esta ventana'
