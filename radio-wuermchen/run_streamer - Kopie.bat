@echo off
REM --- MAKE SURE RELATIVE PATHS ARE RESOLVED CORRECTLY ---
cd C:\Users\kurt_\.openclaw\workspace

REM --- SETTINGS ---
SET FFMPEG_BIN=C:/msys64/mingw64/bin/ffmpeg.exe
SET PYTHON_SCRIPT=radio-wuermchen/radio_streamer.py
SET ICECAST_URL=icecast://source:hackme@localhost:8000/stream
SET PYTHON_BIN=python

REM --- EXECUTION ---
echo Starting Pipe Chain Streamer (Two FFmpeg processes)...
echo Listener URL: http://localhost:8000/stream

REM FINAL CRITICAL FIX: Redirect Python's stderr (2>) to a log file BEFORE piping stdout (|).
REM We are now running the DEBUG_RUNNER.py to capture the hidden Python crash stack trace.
start "Pipe Chain Stream Log" cmd /k call "%PYTHON_BIN%" "%PYTHON_SCRIPT%" 2> radio-wuermchen\dj_debug.log ^| "%FFMPEG_BIN%" -f mp3 -i pipe:0 -c:a copy -f mp3 -content_type audio/mpeg "%ICECAST_URL%"

echo.
echo Check the new window for status and errors, and check dj_debug.log for Python stack trace.
