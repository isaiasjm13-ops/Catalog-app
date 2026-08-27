@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\run_vehicle_application_workflow_migration.ps1"
exit /b %ERRORLEVEL%
