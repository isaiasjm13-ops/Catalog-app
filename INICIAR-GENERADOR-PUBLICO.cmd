@echo off
cd /d "%~dp0"
.venv\Scripts\perfect-catalog-public.exe --host 127.0.0.1 --port 8082 --prompt-password
pause
