$ErrorActionPreference = 'Stop'

$psqlPath = 'C:\Program Files\PostgreSQL\18\bin\psql.exe'
$sqlPath = Join-Path $PSScriptRoot 'reset_application_password.sql'

if (-not (Test-Path -LiteralPath $psqlPath)) {
    throw "psql no existe en la ruta esperada: $psqlPath"
}

Write-Host 'Restablecimiento de perfect_catalog_app.'
Write-Host 'Primero se solicitará la contraseña administrativa actual de postgres.'
Write-Host 'Después escribe y confirma una contraseña nueva para la aplicación.'
Write-Host 'Ninguna contraseña se mostrará ni se guardará.'

& $psqlPath -X -h localhost -p 5432 -U postgres -d postgres -W -v ON_ERROR_STOP=1 -f $sqlPath
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host 'Contraseña de perfect_catalog_app restablecida correctamente.' -ForegroundColor Green
    Write-Host 'Usa esa contraseña en el primer prompt de INICIAR-REVISOR.cmd.'
} else {
    Write-Host 'No se cambió la contraseña. Revisa el mensaje anterior.' -ForegroundColor Red
}

Read-Host 'Presione Enter para cerrar esta ventana'
exit $exitCode
