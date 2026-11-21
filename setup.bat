@echo off
chcp 65001 >nul
REM Cai dat lai moi truong. Them -ResetData de xoa CSDL va nap lai tu database\dti_platform.sql
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\setup.ps1" %*
pause
