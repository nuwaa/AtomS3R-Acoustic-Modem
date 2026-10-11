@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "outputs\environment\test_bell103_session_air.ps1" -Caller COM5 -Answerer COM6
set "result=%ERRORLEVEL%"
echo Exit code: %result%
pause
exit /b %result%
