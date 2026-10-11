@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "START_BELL103_PC_CHAT.ps1"
set "result=%ERRORLEVEL%"
echo PC chat stopped. Exit code: %result%
pause
exit /b %result%
