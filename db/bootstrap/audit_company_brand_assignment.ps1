$ErrorActionPreference = 'Stop'

$projectRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$psqlPath = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$auditSql = Join-Path $projectRoot 'db\validation\audit_company_brand_assignment.sql'

foreach ($required in @($psqlPath, $auditSql)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "No existe el recurso requerido: $required" }
}

$logDirectory = Join-Path $projectRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDirectory | Out-Null
$reportPath = Join-Path $logDirectory ("auditoria-empresas-marcas-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.txt')

Write-Host 'AUDITORIA DE SOLO LECTURA: EMPRESAS Y MARCAS' -ForegroundColor Cyan
Write-Host 'No modifica nada. La contrasena de postgres se solicita oculta y no se guarda.'
$securePassword = Read-Host 'Contrasena de PostgreSQL para postgres' -AsSecureString
$passwordPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($securePassword)
try {
    $env:PGPASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPointer)
    & $psqlPath -X -w -h 127.0.0.1 -p 5432 -U postgres -d perfect_catalog_dev `
        -v ON_ERROR_STOP=1 -f $auditSql | Tee-Object -FilePath $reportPath
    $exitCode = $LASTEXITCODE
}
finally {
    if ($passwordPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPointer)
    }
    Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    $securePassword = $null
}

if ($exitCode -eq 0) {
    Write-Host "AUDITORIA COMPLETADA. Reporte guardado en: $reportPath" -ForegroundColor Green
} else {
    Write-Host "LA AUDITORIA NO SE COMPLETO (psql: $exitCode)." -ForegroundColor Red
}
Read-Host 'Presione Enter para cerrar esta ventana'
exit $exitCode
