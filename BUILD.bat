@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title AstraDroid - PyInstaller build

set "LOGDIR=%~dp0logs"
set "LOGFILE=%LOGDIR%\build.log"
if not exist "%LOGDIR%" mkdir "%LOGDIR%" >nul 2>nul

> "%LOGFILE%" (
  echo ================================================================
  echo AstraDroid PyInstaller build log
  echo Started: %DATE% %TIME%
  echo Project: %CD%
  echo ================================================================
)

echo.
echo ================================================================
echo   AstraDroid - PyInstaller BUILD
echo ================================================================
echo Khong can Visual Studio hay MSVC C++ Build Tools.
echo Dang tao Windows GUI EXE tu Python...
echo Log day du: "%LOGFILE%"
echo.

call :BuildWithPyInstaller >> "%LOGFILE%" 2>&1
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
echo [BUILD SUCCESS] Da tao: dist\AstraDroid.exe
echo Chay RUN.bat hoac mo truc tiep dist\AstraDroid.exe
echo ================================================================
pause
exit /b 0

:BuildWithPyInstaller
if not exist "python\app.py" (
  echo [ERROR] Khong tim thay python\app.py.
  exit /b 2
)
if not exist "python\engine.py" (
  echo [ERROR] Khong tim thay python\engine.py.
  exit /b 3
)

where py.exe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Khong tim thay Python Launcher ^(py.exe^).
  echo Cai Python 3 x64 tu python.org hoac chay SETUP_WINDOWS.bat.
  exit /b 4
)

py -3 -m ensurepip --upgrade
if errorlevel 1 (
  echo [ERROR] Python pip khong san sang.
  exit /b 5
)

echo [INFO] Cai/cap nhat PyInstaller cho Python 3...
py -3 -m pip install --disable-pip-version-check --upgrade pyinstaller
if errorlevel 1 (
  echo [ERROR] Khong cai duoc PyInstaller. Kiem tra Internet/proxy hoac pip.
  exit /b 6
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name AstraDroid ^
  --paths python --add-data "scripts;scripts" python\app.py
if errorlevel 1 (
  echo [ERROR] PyInstaller khong tao duoc EXE.
  exit /b 7
)

if not exist "dist\AstraDroid.exe" (
  echo [ERROR] PyInstaller ket thuc nhung khong co dist\AstraDroid.exe.
  exit /b 8
)
exit /b 0
