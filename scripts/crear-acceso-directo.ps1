# Crea un acceso directo "Nexo ISA" en el Escritorio de quien lo ejecuta (con el icono de la marca).
# ASCII a proposito (la n de "Diseno2" rompe consolas cmd).
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$python = Join-Path $root '.venv\Scripts\pythonw.exe'
$icon = Join-Path $root 'src\perfect_catalog\static\nexo-isa.ico'
if (-not (Test-Path -LiteralPath $python)) { throw "No existe $python (falta el entorno .venv)." }

$desktop = [Environment]::GetFolderPath('Desktop')
$link = Join-Path $desktop 'Nexo ISA.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($link)
$shortcut.TargetPath = $python
$shortcut.Arguments = '-m perfect_catalog.desktop_app'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Nexo ISA - Control de catalogo'
if (Test-Path -LiteralPath $icon) { $shortcut.IconLocation = $icon }
$shortcut.Save()
Write-Host "Acceso directo creado: $link" -ForegroundColor Green
Write-Host 'Haz doble clic en "Nexo ISA" para abrir la app. Pide la contrasena de PostgreSQL una vez.'
Read-Host 'Pulsa Enter para cerrar' | Out-Null
