@echo off
chcp 65001 > nul
echo ===================================================
echo   DeskMate Windows Edge 边缘端智能体服务启动中...
echo ===================================================

cd /d "%~dp0\.."

python -m deskmate_edge %*
pause
