@echo off
setlocal
cd /d "%~dp0"
rem Abre el generador publico en su propia ventana y despues el revisor (apuntado al puerto real).
rem Cada uno pide la contrasena de Postgres. Los servidores mueren al cerrar su ventana.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\iniciar-todo.ps1"
exit /b %ERRORLEVEL%
