@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\run_pending_migrations.ps1"
exit /b %ERRORLEVEL%
