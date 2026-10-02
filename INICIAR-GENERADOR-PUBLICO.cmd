@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar-servicio.ps1" -Service public
exit /b %ERRORLEVEL%
