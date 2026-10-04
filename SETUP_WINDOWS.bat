@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title AstraDroid setup for Windows

echo ================================================================
echo  AstraDroid ^| Local APK workspace for Windows 10/11 x64
echo ================================================================
echo.
echo This installer only prepares developer tools. It does NOT download APKs,
echo bypass Android protections, or change UEFI/BIOS virtualization settings.
echo.

if /I not "%PROCESSOR_ARCHITECTURE%"=="AMD64" if /I not "%PROCESSOR_ARCHITEW6432%"=="AMD64" (
  echo [WARNING] Android Emulator needs a 64-bit Windows installation.
)

where winget.exe >nul 2>nul
if errorlevel 1 (
  echo [WARNING] winget was not found. Install App Installer from Microsoft Store,
  echo then install the tools listed in README.vi.md manually.
) else (
  where py.exe >nul 2>nul
  if errorlevel 1 (
    choice /C YN /M "Install Python 3.13 x64 with winget"
    if not errorlevel 2 winget install --id Python.Python.3.13 -e --source winget --accept-package-agreements --accept-source-agreements
  ) else (
    echo [OK] Python Launcher found.
  )

  set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
  if not exist "%VSWHERE%" (
    choice /C YN /M "Install Visual Studio 2022 Build Tools (C++ workload, may take time)"
    if not errorlevel 2 winget install --id Microsoft.VisualStudio.2022.BuildTools -e --source winget --accept-package-agreements --accept-source-agreements --override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools --includeRecommended"
  ) else (
    echo [OK] Visual Studio Build Tools locator found.
  )

  set "SDK=%LOCALAPPDATA%\Android\Sdk"
  if not exist "%SDK%\emulator\emulator.exe" (
    echo.
    echo Android Studio supplies the official Android SDK Emulator.
    choice /C YN /M "Install Android Studio with winget"
    if not errorlevel 2 winget install --id Google.AndroidStudio -e --source winget --accept-package-agreements --accept-source-agreements
  ) else (
    echo [OK] Android Emulator found in %SDK%
  )
)

echo.
echo ----------------------------------------------------------------
echo NEXT STEPS
echo 1. Enable Intel VT-x or AMD SVM in UEFI/BIOS. This cannot be automated.
echo 2. If Android Studio was just installed, open it once and finish its SDK wizard.
echo 3. In Android Studio SDK Manager, install Android Emulator, Platform-Tools,
echo    Command-line Tools (latest), Build-Tools, and a Google APIs x86_64 image.
echo 4. Run BUILD.bat, then RUN.bat.
echo ----------------------------------------------------------------
echo.
choice /C YN /M "Build AstraDroid now"
if not errorlevel 2 call "%~dp0BUILD.bat"
echo.
pause
