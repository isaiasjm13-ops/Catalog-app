@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\run_intake_promotion_migration.ps1"
exit /b %ERRORLEVEL%
