@echo off
chcp 65001 >nul
echo ================================================
echo        Cooper Factory Quick Start
echo ================================================
echo.

cd /d "%~dp0backend"
echo Starting Cooper Factory...
echo.
python main.py

pause
