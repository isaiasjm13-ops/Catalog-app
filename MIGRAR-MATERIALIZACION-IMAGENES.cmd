@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\run_approved_image_materialization_migration.ps1"
exit /b %ERRORLEVEL%
