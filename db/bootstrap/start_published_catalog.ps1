$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$psqlPath = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$apiPath = Join-Path $projectRoot '.venv\Scripts\perfect-catalog-api.exe'

foreach ($required in @($psqlPath, $apiPath)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "No existe el recurso requerido: $required" }
}

Write-Host 'CATALOGO PUBLICADO - Perfect Catalog' -ForegroundColor Cyan
Write-Host 'Se pedira la contrasena de postgres dos veces: una para listar las marcas con'
Write-Host 'un release publicado, y otra al abrir el visor (nunca se guarda ni se reutiliza).'

$securePassword = Read-Host 'Contrasena de PostgreSQL para postgres (para listar marcas)' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
$brands = @()
try {
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    $rows = & $psqlPath -X -w -h 127.0.0.1 -p 5432 -U postgres -d perfect_catalog_dev `
        -t -A -F '|' -v ON_ERROR_STOP=1 -c @'
SELECT DISTINCT b.code, b.name
FROM perfect_catalog.catalog_release AS r
JOIN perfect_catalog.brand AS b ON b.brand_id = r.brand_id
WHERE r.status = 'published'
ORDER BY b.name;
'@
    if ($LASTEXITCODE -ne 0) { throw "psql no pudo listar las marcas (codigo $LASTEXITCODE)." }
    foreach ($line in $rows) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line -split '\|', 2
        $brands += [pscustomobject]@{ Code = $parts[0]; Name = $parts[1] }
    }
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    $securePassword = $null
}

if ($brands.Count -eq 0) {
    Write-Host 'Ninguna marca tiene un release publicado todavia.' -ForegroundColor Yellow
    Read-Host 'Presione Enter para cerrar esta ventana'
    exit 1
}

Write-Host ''
Write-Host 'Marcas con release publicado:'
foreach ($brand in $brands) { Write-Host ("  - {0} ({1})" -f $brand.Name, $brand.Code) }
Write-Host ''
$chosen = Read-Host 'Codigo de la marca a abrir'
if ([string]::IsNullOrWhiteSpace($chosen)) {
    Write-Host 'No se indico ninguna marca.' -ForegroundColor Yellow
    Read-Host 'Presione Enter para cerrar esta ventana'
    exit 1
}

Write-Host "Abriendo el ultimo release publicado de $chosen en modo solo lectura."
& $apiPath --host 127.0.0.1 --port 8080 --brand $chosen --prompt-password
exit $LASTEXITCODE
