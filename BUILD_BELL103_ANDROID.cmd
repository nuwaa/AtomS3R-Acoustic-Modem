@echo off
setlocal
cd /d "%~dp0outputs\android\AtomUsbChat"
if not defined JAVA_HOME set "JAVA_HOME=C:\Program Files\Android\Android Studio\jbr"
if not defined ANDROID_HOME set "ANDROID_HOME=%LOCALAPPDATA%\Android\Sdk"
set "PATH=%JAVA_HOME%\bin;%PATH%"
call gradlew.bat :app:assembleDebug
set "result=%ERRORLEVEL%"
echo.
if "%result%"=="0" (
  echo BUILD PASS: %CD%\app\build\outputs\apk\debug\app-debug.apk
) else (
  echo BUILD FAILED: exit code %result%
)
pause
exit /b %result%
