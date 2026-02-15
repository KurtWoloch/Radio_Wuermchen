@echo off
REM --- CONFIGURATION ---
set PYTHON_EXE="C:\Program Files\Python311\python.exe"
set PYTHON_SCRIPT=radio-wuermchen/radio_streamer.py

echo Starting Agent-Driven Direct Streamer (Requires manual Icecast start)...
echo.

REM Execute Python script directly. Assumes Icecast is already running.
%PYTHON_EXE% %PYTHON_SCRIPT%

REM --- INFO (This will only print if the stream ends) ---
echo.
echo --- RADIO STATION OFFLINE ---
pause