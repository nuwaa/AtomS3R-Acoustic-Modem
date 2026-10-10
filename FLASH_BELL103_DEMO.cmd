@echo off
setlocal EnableExtensions
cd /d "%~dp0"
echo Flash the Bell 103 sound demo to ONE ATOM S3R.
echo Close chat, IP tunnel, and Serial Monitor on its COM port first.
echo.
reg query HKLM\HARDWARE\DEVICEMAP\SERIALCOMM 2>nul
echo.
set /p "PORT=ATOM COM port: "
if "%PORT%"=="" (
  echo ERROR: COM port is required.
  pause
  exit /b 2
)
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "outputs\environment\flash_firmware.ps1" -Port "%PORT%"
set "result=%ERRORLEVEL%"
if "%result%"=="0" (echo FLASH PASS) else (echo FLASH FAILED: exit code %result%)
pause
exit /b %result%
