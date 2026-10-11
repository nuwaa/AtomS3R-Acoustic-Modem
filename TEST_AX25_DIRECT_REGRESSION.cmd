@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "outputs\environment\test_ax25_direct_regression.ps1" -A COM5 -B COM6
set "result=%ERRORLEVEL%"
echo Exit code: %result%
pause
exit /b %result%
