@echo off
REM --- SETTINGS ---
SET FFMPEG_BIN=C:/msys64/mingw64/bin/ffmpeg.exe
SET PYTHON_SCRIPT=radio-wuermchen/radio_streamer.py
SET ICECAST_URL=icecast://source:hackme@localhost:8000/stream
SET PYTHON_BIN=python

REM --- EXECUTION ---
echo Starting Pipe Chain Streamer (Two FFmpeg processes)...
echo Listener URL: http://localhost:8000/stream

REM FINAL CRITICAL FIX: Quote the whole command for 'start' to run in a new cmd shell.
start "Pipe Chain Stream Log" "%PYTHON_BIN%" "%PYTHON_SCRIPT%" ^| "%FFMPEG_BIN%" -f mp3 -i pipe:0 -c:a copy -f mp3 -content_type audio/mpeg "%ICECAST_URL%"

echo.
echo Check the new window for status and errors.
