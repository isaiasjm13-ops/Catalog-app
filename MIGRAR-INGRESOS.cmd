@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File db\bootstrap\run_intake_migration.ps1
