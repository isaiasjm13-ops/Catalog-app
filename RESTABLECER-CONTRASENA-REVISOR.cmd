@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\reset_application_password.ps1"
exit /b %ERRORLEVEL%
