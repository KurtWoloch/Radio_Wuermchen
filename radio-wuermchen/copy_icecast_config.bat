@echo off
REM --- Copy Icecast config to the OpenClaw workspace for inspection ---
set ICECAST_PATH="C:\Program Files\Icecast\icecast.xml"
set WORKSPACE_PATH="%~dp0icecast.xml"
copy %ICECAST_PATH% %WORKSPACE_PATH%
if exist %WORKSPACE_PATH% (
    echo.
    echo SUCCESS: Icecast config copied to workspace.
) else (
    echo.
    echo ERROR: Failed to copy Icecast config. Check the path and permissions.
)
pause