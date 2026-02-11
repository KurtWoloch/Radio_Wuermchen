@echo off
REM --- ICECAST SERVER STARTUP ---
echo Checking/Starting Icecast...
start "Icecast Server" cmd /k "cd /d "C:\Program Files\Icecast\" & "C:\Program Files\Icecast\icecast.bat""
echo.
timeout /t 5 /nobreak > nul

REM --- CONTINUOUS STREAMING (PIPE CHAIN) ---
set FFMPEG_BIN=C:\msys64\mingw64\bin\ffmpeg.exe
set PYTHON_SCRIPT=C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\radio_streamer.py

echo Starting Pipe Chain Streamer...

REM The entire pipe chain is started in a single window:
REM 1. Python runs the FFmpeg encoder for segments (outputs to stdout)
REM 2. Pipe (|) redirects output to the second FFmpeg process's stdin
REM 3. Second FFmpeg process reads continuous data from stdin and streams to Icecast.
start "Pipe Chain Stream Log" cmd /k "python %PYTHON_SCRIPT% | %FFMPEG_BIN% -i - -f mp3 -acodec libmp3lame -content_type audio/mpeg icecast://source:hackme@localhost:8000/stream"

REM --- INFO ---
echo.
echo --- RADIO STATION ONLINE (PIPE MODE) ---
echo URL: http://localhost:8000/radio.mp3
echo.
pause
