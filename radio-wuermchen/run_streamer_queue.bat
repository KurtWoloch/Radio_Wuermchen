@echo off
REM --- ICECAST SERVER STARTUP ---
echo Checking/Starting Icecast...
start "Icecast Server" cmd /k "cd /d "C:\Program Files\Icecast\" & "C:\Program Files\Icecast\icecast.bat""
echo.
timeout /t 5 /nobreak > nul

REM --- CONTINUOUS STREAMING (PIPE CHAIN) ---
REM This is the proven working pipe chain from Feb 9th.
REM Python outputs MP3 segments to stdout, piped to FFmpeg which streams to Icecast.
REM DO NOT MODIFY the pipe chain line below unless you know exactly what you're doing.

set FFMPEG_BIN=C:\msys64\mingw64\bin\ffmpeg.exe
set PYTHON_SCRIPT=C:\Users\kurt_\.openclaw\workspace\radio-wuermchen\streamer.py

echo Starting Queue-Based Pipe Chain Streamer...
echo Listener URL: http://localhost:8000/stream
echo.
echo Log output goes to: radio-wuermchen\streamer.log
echo.

cmd /k "python %PYTHON_SCRIPT% | %FFMPEG_BIN% -i - -f mp3 -acodec libmp3lame -content_type audio/mpeg icecast://source:hackme@localhost:8000/stream"

pause
