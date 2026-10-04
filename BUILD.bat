@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title AstraDroid - Native Windows build

set "LOGDIR=%~dp0logs"
set "LOGFILE=%LOGDIR%\build.log"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>nul

> "%LOGFILE%" (
  echo ================================================================
  echo AstraDroid native build log
  echo Started: %DATE% %TIME%
  echo Project: %CD%
  echo ================================================================
)

echo.
echo ================================================================
echo   AstraDroid - BUILD.bat
echo ================================================================
echo Dang kiem tra MSVC va build GUI C++...
echo Log day du: "%LOGFILE%"
echo.

call :BuildNative >> "%LOGFILE%" 2>&1
set "RESULT=%ERRORLEVEL%"

echo.
type "%LOGFILE%"
echo.
if not "%RESULT%"=="0" (
  echo ================================================================
  echo [BUILD FAILED] Cua so nay duoc giu mo de ban doc loi.
  echo Gui noi dung file logs\build.log neu can minh sua tiep.
  echo ================================================================
  pause
  exit /b %RESULT%
)

echo ================================================================
echo [BUILD SUCCESS] Da tao: bin\AstraDroid.exe
echo Ban co the chay RUN.bat hoac mo bin\AstraDroid.exe
echo ================================================================
pause
exit /b 0

:BuildNative
if not exist "src\AstraDroid.cpp" (
  echo [ERROR] Khong tim thay src\AstraDroid.cpp.
  exit /b 2
)

where cl.exe >nul 2>nul
if errorlevel 1 (
  set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
  if not exist "!VSWHERE!" (
    echo [ERROR] Khong tim thay MSVC Build Tools hay vswhere.exe.
    echo Cai Visual Studio 2022 Build Tools va workload Desktop development with C++.
    exit /b 3
  )
  for /f "usebackq delims=" %%I in (`"!VSWHERE!" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSROOT=%%I"
  if not defined VSROOT (
    echo [ERROR] Da tim thay Visual Studio Installer nhung chua co C++ x64 workload.
    echo Mo Visual Studio Installer ^> Modify ^> tick Desktop development with C++.
    exit /b 4
  )
  if not exist "!VSROOT!\VC\Auxiliary\Build\vcvars64.bat" (
    echo [ERROR] Khong tim thay vcvars64.bat trong: !VSROOT!
    exit /b 5
  )
  call "!VSROOT!\VC\Auxiliary\Build\vcvars64.bat"
  if errorlevel 1 (
    echo [ERROR] Khong the khoi tao MSVC x64 environment.
    exit /b 6
  )
)

where cl.exe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] cl.exe van khong san sang sau khi khoi tao MSVC.
  exit /b 7
)

if not exist bin mkdir bin
cl.exe /nologo /std:c++17 /utf-8 /O2 /EHsc /FS /DUNICODE /D_UNICODE /W4 /wd4100 /wd4127 ^
  src\AstraDroid.cpp /Fe:bin\AstraDroid.exe ^
  /link /SUBSYSTEM:WINDOWS Comdlg32.lib Shell32.lib Dwmapi.lib Msimg32.lib
if errorlevel 1 (
  echo [ERROR] MSVC bao loi khi bien dich/link. Xem dong loi o tren.
  exit /b 8
)

exit /b 0
