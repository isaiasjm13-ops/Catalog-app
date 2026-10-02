@echo off
setlocal
cd /d "%~dp0"
rem Nexo ISA como app: pide la contrasena de PostgreSQL una vez, entra solo y abre su propia ventana.
rem Al cerrar la ventana se apagan los servidores. Detalle de errores: logs\desktop-app.log
if not exist ".venv\Scripts\pythonw.exe" (
  echo No existe el entorno .venv. Pidele a quien instalo el sistema que lo prepare.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" -m perfect_catalog.desktop_app
exit /b 0
