@echo off
echo ==========================================
echo   Radio Wuermchen - External Access
echo ==========================================
echo.
echo Starting listener server on port 8001...
cd /d "%~dp0"
start "" "C:\Program Files\Python311\python.exe" listener_server.py

echo Starting ngrok tunnel to listener server (port 8001)...
start "" /B "C:\Users\kurt_\AppData\Local\Microsoft\WinGet\Packages\Ngrok.Ngrok_Microsoft.Winget.Source_8wekyb3d8bbwe\ngrok.exe" http 8001

timeout /t 5 /nobreak >nul

echo Fetching public URL...
echo.
powershell -Command "try { $r = Invoke-RestMethod http://127.0.0.1:4040/api/tunnels; $url = $r.tunnels[0].public_url; Write-Host '========================================'; Write-Host '  Station page (with player + requests):'; Write-Host \"  $url\"; Write-Host ''; Write-Host '  Direct stream URL:'; Write-Host \"  $url/stream\"; Write-Host '========================================'; Write-Host ''; Write-Host 'ngrok + listener server running.'; Write-Host 'To stop: taskkill /F /IM ngrok.exe ^& taskkill /F /IM python.exe' } catch { Write-Host 'ERROR: Could not reach ngrok API.'; Write-Host 'Try waiting a moment and check manually.' }"
echo.
pause
