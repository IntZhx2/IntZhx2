@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_deskmate.ps1"
if %errorlevel% neq 0 pause
