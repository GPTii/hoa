@echo off
chcp 65001 >nul
REM Xuat CSDL hien tai ra database\dti_platform.sql de push len git
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\export-db.ps1"
pause
