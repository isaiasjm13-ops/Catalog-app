@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\prepare_multicompany_phase0.ps1"
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo FASE 0 NO COMPLETADA. Revise el mensaje anterior.
exit /b %RESULT%
