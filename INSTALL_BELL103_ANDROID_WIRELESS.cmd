@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
set "ADB=%LOCALAPPDATA%\Android\Sdk\platform-tools\adb.exe"
set "APK=%~dp0outputs\android\AtomUsbChat\app\build\outputs\apk\debug\app-debug.apk"
if not exist "%ADB%" (echo ERROR: adb.exe not found in Android SDK Platform-Tools.& pause& exit /b 1)
if not exist "%APK%" (echo ERROR: Build the Android APK first.& pause& exit /b 1)
echo Keep the Android phone and PC on the same Wi-Fi for installation.
echo Temporarily disconnect ATOM Acoustic IP VPN on the phone.
echo Open Developer options - Wireless debugging on the phone.
echo.
set /p "PAIR_ADDRESS=Pairing IP:port (Enter if already paired): "
if not "!PAIR_ADDRESS!"=="" (
  set /p "PAIR_CODE=Six-digit pairing code: "
  "%ADB%" pair !PAIR_ADDRESS! !PAIR_CODE!
  if errorlevel 1 (echo PAIRING FAILED. Generate a fresh pairing code.& pause& exit /b 2)
)
echo Use the Wi-Fi IP:port on the main Wireless debugging screen.
set /p "CONNECT_ADDRESS=Connection IP:port: "
if "!CONNECT_ADDRESS!"=="" (echo ERROR: connection address required.& pause& exit /b 2)
echo !CONNECT_ADDRESS!|findstr /B /C:"10.77." >nul
if not errorlevel 1 (echo ERROR: 10.77.x.x is the acoustic VPN address. Use the Wi-Fi address.& pause& exit /b 2)
"%ADB%" connect !CONNECT_ADDRESS!
if errorlevel 1 (echo CONNECT FAILED.& pause& exit /b 2)
"%ADB%" -s !CONNECT_ADDRESS! get-state
if errorlevel 1 (echo DEVICE OFFLINE. Keep it unlocked and wireless debugging enabled.& pause& exit /b 2)
"%ADB%" -s !CONNECT_ADDRESS! install -r "%APK%"
if errorlevel 1 (echo INSTALL FAILED.& pause& exit /b 3)
"%ADB%" -s !CONNECT_ADDRESS! shell am force-stop jp.jn1eep.atomusbchat
"%ADB%" -s !CONNECT_ADDRESS! shell am start -n jp.jn1eep.atomusbchat/.MainActivity
echo INSTALL PASS: ATOM USB Chat 0.3.2
pause
exit /b 0
