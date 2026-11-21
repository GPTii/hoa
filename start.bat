@echo off
chcp 65001 >nul
REM Bam dup: lan dau tu cai dat (Python, Node.js, PostgreSQL, thu vien, du lieu) roi chay va mo http://localhost:8000
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0deploy\run.ps1"
if errorlevel 1 pause
