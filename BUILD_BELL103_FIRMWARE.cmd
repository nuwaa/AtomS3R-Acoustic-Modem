@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "outputs\environment\build_firmware.ps1"
set "result=%ERRORLEVEL%"
echo.
if "%result%"=="0" (echo BUILD PASS) else (echo BUILD FAILED: exit code %result%)
pause
exit /b %result%
