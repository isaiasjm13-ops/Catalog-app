$ErrorActionPreference = 'Stop'

$pythonPath = Join-Path $PSScriptRoot '..\.venv\Scripts\python.exe'
$resultPath = Join-Path $env:TEMP 'perfect_catalog_productive_block.exit'
$transcriptPath = Join-Path $env:TEMP 'perfect_catalog_productive_block.log'
$sourcePath = Join-Path $PSScriptRoot '..\data\imports\NATSUKI_EMPAQUES_MAESTRO.xlsx'

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "No existe el Python del entorno virtual: $pythonPath"
}

Set-Location (Join-Path $PSScriptRoot '..')
$env:PERFECT_CATALOG_RUN_INTEGRATION = '1'
Start-Transcript -LiteralPath $transcriptPath -Force | Out-Null

Write-Host '1/2 Pruebas de integracion PostgreSQL (usuario postgres).'
Write-Host 'La entrada de contraseña permanece completamente oculta.'
& $pythonPath -m unittest discover -s tests -p test_postgresql_integration.py -v
$integrationExit = $LASTEXITCODE
if ($integrationExit -ne 0) {
    Set-Content -LiteralPath $resultPath -Value "integration=$integrationExit;import=not-run" -Encoding ascii
    Write-Host "Las pruebas fallaron con codigo $integrationExit; el dry-run no fue ejecutado."
    Stop-Transcript | Out-Null
    Read-Host 'Presione Enter para cerrar esta ventana'
    exit $integrationExit
}

Write-Host ''
Write-Host '2/2 Dry-run de Odoo (usuario perfect_catalog_app).'
Write-Host 'Introduzca ahora la contraseña de perfect_catalog_app; también permanecerá oculta.'
& $pythonPath -m perfect_catalog import-odoo $sourcePath --prompt-password
$importExit = $LASTEXITCODE

Set-Content -LiteralPath $resultPath -Value "integration=$integrationExit;import=$importExit" -Encoding ascii
Write-Host "Resultado final: integration=$integrationExit; import=$importExit"
Stop-Transcript | Out-Null
Read-Host 'Presione Enter para cerrar esta ventana'
exit $importExit
