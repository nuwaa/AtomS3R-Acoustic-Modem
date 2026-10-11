@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "outputs\environment\test_group_order.ps1"
set "result=%ERRORLEVEL%"
echo Exit code: %result%
pause
exit /b %result%
