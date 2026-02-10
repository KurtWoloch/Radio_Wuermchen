@echo off
REM --- ICECAST SERVER STARTUP (Required) ---
echo Checking/Starting Icecast...
start "Icecast Server" cmd /c "cd /d "C:\Program Files\Icecast\" && "C:\Program Files\Icecast\icecast.bat""
echo.
timeout /t 5 /nobreak > nul

REM --- CONFIGURATION (CRITICAL FIX: Use short path to avoid quote hell) ---
set FFMPEG_BIN=C:\msys64\mingw64\bin\ffmpeg.exe
set PYTHON_EXE=C:\PROGRA~1\Python311\python.exe
set PYTHON_SCRIPT=C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\radio_streamer.py
set ICECAST_URL=icecast://source:hackme@localhost:8000/stream

echo Starting Agent-Driven Pipe Chain Streamer...

REM FINAL ATTEMPT: Use the complex START structure that achieved continuity with unquoted short path.
start "Pipe Chain Stream Log" cmd /k %PYTHON_EXE% %PYTHON_SCRIPT% ^| %FFMPEG_BIN% -i - -f mp3 -acodec libmp3lame -content_type audio/mpeg %ICECAST_URL%

REM --- INFO ---
echo.
echo --- RADIO STATION ONLINE (PIPE MODE) ---
echo URL: http://localhost:8000/stream
echo.
pause