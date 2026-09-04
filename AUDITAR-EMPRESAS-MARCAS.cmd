@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\audit_company_brand_assignment.ps1"
exit /b %ERRORLEVEL%
