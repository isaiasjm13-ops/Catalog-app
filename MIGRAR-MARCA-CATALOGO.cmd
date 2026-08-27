@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\run_brand_profile_workflow_migration.ps1"
exit /b %ERRORLEVEL%
