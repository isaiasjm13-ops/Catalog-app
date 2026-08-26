@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0db\bootstrap\run_image_match_review_migration.ps1"
exit /b %ERRORLEVEL%
