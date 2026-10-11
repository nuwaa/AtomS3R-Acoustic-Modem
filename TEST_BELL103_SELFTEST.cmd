@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "outputs\environment\test_bell103_selftest.ps1" -Port COM6
set "result=%ERRORLEVEL%"
echo Exit code: %result%
pause
exit /b %result%
