@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set /p "ORIG=Originator ATOM COM port [COM5]: "
if "%ORIG%"=="" set "ORIG=COM5"
set /p "ANS=Answerer ATOM COM port [COM6]: "
if "%ANS%"=="" set "ANS=COM6"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "outputs\environment\test_bell103_air.ps1" -Originator "%ORIG%" -Answerer "%ANS%"
set "result=%ERRORLEVEL%"
echo Exit code: %result%
pause
exit /b %result%
