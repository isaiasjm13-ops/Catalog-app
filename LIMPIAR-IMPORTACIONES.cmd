@echo off
setlocal
title Limpiar importaciones de Perfect Catalog
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\clear_imported_data.ps1"
set "RESULTADO=%ERRORLEVEL%"
if not "%RESULTADO%"=="0" (
  echo.
  echo La limpieza no se completo. Ninguna copia de respaldo existente fue eliminada.
  pause
)
exit /b %RESULTADO%
