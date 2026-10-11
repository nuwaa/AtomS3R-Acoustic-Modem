@echo off
setlocal EnableExtensions
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_PC_PEER_CHAT.ps1" -Port "%~1"
set "result=%ERRORLEVEL%"
if not "%result%"=="0" pause
exit /b %result%
