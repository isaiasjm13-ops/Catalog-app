@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\start_published_catalog.ps1"
exit /b %ERRORLEVEL%
