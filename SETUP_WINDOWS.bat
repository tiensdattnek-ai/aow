@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title AstraDroid setup for Windows

echo ================================================================
echo  AstraDroid ^| PyInstaller GUI setup for Windows 10/11 x64
echo ================================================================
echo.
echo Ban build GUI EXE bang PyInstaller: KHONG can Visual Studio hay MSVC.
echo Script khong thay doi BIOS/UEFI va khong download APK cua ban.
echo.

if /I not "%PROCESSOR_ARCHITECTURE%"=="AMD64" if /I not "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
  echo [WARNING] Android Emulator can Windows 64-bit.
)

where winget.exe >nul 2>nul
if errorlevel 1 (
  echo [WARNING] Khong tim thay winget. Cai thu cong Python 3 x64 va Android Studio.
  echo Xem README.md de biet yeu cau chi tiet.
) else (
  where py.exe >nul 2>nul
  if errorlevel 1 (
    choice /C YN /M "Cai Python 3.13 x64 voi winget"
    if not errorlevel 2 winget install --id Python.Python.3.13 -e --source winget --accept-package-agreements --accept-source-agreements
  ) else (
    echo [OK] Python Launcher ^(py.exe^) da san sang.
  )

  set "SDK=!LOCALAPPDATA!\Android\Sdk"
  if not exist "!SDK!\emulator\emulator.exe" (
    echo.
    echo Android Studio cung cap Android SDK Emulator chinh thuc.
    choice /C YN /M "Cai Android Studio voi winget"
    if not errorlevel 2 winget install --id Google.AndroidStudio -e --source winget --accept-package-agreements --accept-source-agreements
  ) else (
    echo [OK] Android Emulator da tim thay tai !SDK!
  )
)

echo.
echo ----------------------------------------------------------------
echo NEXT STEPS
echo 1. Luu BIOS va restart sau khi bat Intel VT-x / AMD SVM.
echo 2. Mo Android Studio mot lan va hoan tat SDK Setup Wizard.
echo 3. Trong SDK Manager, cai Android Emulator, Platform-Tools,
echo    Command-line Tools, Build-Tools va Google APIs x86_64 system image.
echo 4. Chay BUILD.bat ^(PyInstaller se tu cai neu chua co^), sau do RUN.bat.
echo ----------------------------------------------------------------
echo.
choice /C YN /M "Build AstraDroid GUI EXE ngay bay gio"
if not errorlevel 2 call "%~dp0BUILD.bat"
echo.
pause
