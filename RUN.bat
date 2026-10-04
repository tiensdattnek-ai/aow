@echo off
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "dist\AstraDroid.exe" (
  echo AstraDroid chua duoc package. Dang chay BUILD.bat...
  call "%~dp0BUILD.bat"
  if errorlevel 1 (
    echo [ERROR] Build that bai. Xem logs\build.log.
    pause
    exit /b 1
  )
)

start "AstraDroid" "%~dp0dist\AstraDroid.exe"
exit /b 0
