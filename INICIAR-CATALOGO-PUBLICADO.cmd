@echo off
cd /d "%~dp0"
echo Abriendo el ultimo release publicado de NATSUKI en modo solo lectura.
echo La contrasena de PostgreSQL no muestra caracteres mientras se escribe.
.venv\Scripts\perfect-catalog-api.exe --host 127.0.0.1 --port 8080 --brand NATSUKI --prompt-password
pause
