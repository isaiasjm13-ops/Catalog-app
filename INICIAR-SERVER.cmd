@echo off
cd /d "%~dp0"
.venv\Scripts\perfect-catalog-api.exe --host 127.0.0.1 --port 8080 --source-dir data\imports
pause
