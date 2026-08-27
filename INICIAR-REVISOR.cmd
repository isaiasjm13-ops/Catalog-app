@echo off
cd /d "%~dp0"
.venv\Scripts\perfect-catalog-operator.exe --host 127.0.0.1 --port 8081 --prompt-password --generate-access-code --open-browser
pause
