@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "PYTHON_EXE=python"
if exist "outputs\environment\settings.json" for /f "delims=" %%I in ('powershell.exe -NoProfile -Command "$s=Get-Content 'outputs/environment/settings.json' -Raw | ConvertFrom-Json; if($s.python){$s.python}"') do set "PYTHON_EXE=%%I"
if exist "outputs\environment\settings.json" for /f "delims=" %%I in ('powershell.exe -NoProfile -Command "$s=Get-Content 'outputs/environment/settings.json' -Raw | ConvertFrom-Json; if($s.python_libraries){$s.python_libraries}"') do set "PYTHONPATH=%%I"
"%PYTHON_EXE%" "outputs\tests\test_ggwave_air.py" %* --long
set "result=%ERRORLEVEL%"
echo Exit code: %result%
pause
exit /b %result%
