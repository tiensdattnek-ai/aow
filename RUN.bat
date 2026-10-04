@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "bin\AstraDroid.exe" (
  echo AstraDroid chua duoc build. Dang build...
  call "%~dp0BUILD.bat"
  if errorlevel 1 pause & exit /b 1
)

where py.exe >nul 2>nul
if errorlevel 1 (
  echo [ERROR] Can cai Python 3 x64 va bat Python Launcher (py.exe).
  echo Hay chay SETUP_WINDOWS.bat.
  pause
  exit /b 1
)

start "AstraDroid" "%~dp0bin\AstraDroid.exe"
exit /b 0
