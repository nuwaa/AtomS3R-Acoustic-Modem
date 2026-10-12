@echo off
setlocal EnableExtensions
cd /d "%~dp0"
set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
set "APK=%~dp0outputs\android\AtomUsbChat\app\build\outputs\apk\debug\app-debug.apk"

if not exist "%ADB%" (
  echo ERROR: Android SDK Platform-Tools adb.exe was not found.
  pause
  exit /b 1
)
if not exist "%APK%" (
  echo ERROR: Android APK was not found. Run BUILD_BELL103_ANDROID.cmd first.
  pause
  exit /b 1
)

echo Connect only the target Android phone to this PC by USB.
echo Unlock it and approve the USB debugging prompt if shown.
echo.
"%ADB%" devices -l
echo.
"%ADB%" -d get-state
if errorlevel 1 (
  echo ERROR: No unique USB debugging device is available. Check the cable and phone authorization.
  pause
  exit /b 2
)

"%ADB%" -d install -r "%APK%"
if errorlevel 1 (
  echo INSTALL FAILED. Copy the error above when reporting the issue.
  pause
  exit /b 3
)

"%ADB%" -d shell am force-stop jp.jn1eep.atomusbchat
"%ADB%" -d shell am start -n jp.jn1eep.atomusbchat/.MainActivity
echo INSTALL PASS: ATOM USB Chat 0.3.6 on the USB-connected Android device.
pause
exit /b 0
