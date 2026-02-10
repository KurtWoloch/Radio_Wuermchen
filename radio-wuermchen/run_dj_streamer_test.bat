@echo off
REM --- ICECAST SERVER STARTUP (Required) ---
echo Checking/Starting Icecast...
start "Icecast Server" cmd /c "cd /d "C:\Program Files\Icecast\" && "C:\Program Files\Icecast\icecast.bat""
echo.
timeout /t 5 /nobreak > nul

REM --- CONFIGURATION ---
set FFMPEG_BIN=C:\msys64\mingw64\bin\ffmpeg.exe
set ICECAST_URL=icecast://source:hackme@localhost:8000/source1.mp3
set TEST_MP3=C:\Users\kurt_\.openclaw\workspace\!!! - Heart of hearts.mp3

echo Starting TEST Streamer (Direct MP3)...

REM Test: Stream a single, known file to /source1.mp3
%FFMPEG_BIN% -i "%TEST_MP3%" -f mp3 -acodec libmp3lame -content_type audio/mpeg %ICECAST_URL%

REM --- INFO (This will only print if the stream ends) ---
echo.
echo --- RADIO STATION OFFLINE ---
pause