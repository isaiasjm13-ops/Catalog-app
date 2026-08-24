@echo off
cd /d "%~dp0"
set PYTHONPATH=.
.venv\Scripts\python.exe scripts\run_catalog_web.py --host 127.0.0.1 --port 8080
pause
