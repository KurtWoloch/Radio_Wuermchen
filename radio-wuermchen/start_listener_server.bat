@echo off
echo ==========================================
echo   Radio Wuermchen - Listener Server
echo ==========================================
echo.
echo Starting listener web server on port 8001...
echo.

cd /d "%~dp0"
"C:\Program Files\Python311\python.exe" listener_server.py
pause
