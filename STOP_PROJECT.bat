@echo off
setlocal
cd /d "%~dp0"

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop-project.ps1"
if errorlevel 1 (
    echo.
    echo Project shutdown failed. See the message above.
    pause
)

endlocal
