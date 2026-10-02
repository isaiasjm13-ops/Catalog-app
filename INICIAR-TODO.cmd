@echo off
setlocal
cd /d "%~dp0"
rem Abre el generador publico en su propia ventana y despues el revisor.
rem Cada uno pide la contrasena de Postgres. Los servidores mueren al cerrar su ventana.
start "Generador publico" powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar-servicio.ps1" -Service public
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar-servicio.ps1" -Service operator
exit /b %ERRORLEVEL%
