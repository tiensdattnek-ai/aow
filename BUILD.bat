@echo off
setlocal EnableExtensions
cd /d "%~dp0"

where cl.exe >nul 2>nul
if errorlevel 1 (
  set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
  if not exist "%VSWHERE%" (
    echo [ERROR] Khong tim thay MSVC Build Tools.
    echo Cai Visual Studio 2022 Build Tools voi workload Desktop development with C++.
    echo Hoac chay SETUP_WINDOWS.bat truoc.
    exit /b 1
  )
  for /f "usebackq delims=" %%I in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSROOT=%%I"
  if not defined VSROOT (
    echo [ERROR] MSVC C++ workload chua duoc cai.
    exit /b 1
  )
  call "%VSROOT%\VC\Auxiliary\Build\vcvars64.bat" >nul
)

if not exist bin mkdir bin
cl.exe /nologo /std:c++17 /utf-8 /O2 /EHsc /DUNICODE /D_UNICODE /W4 /wd4100 /wd4127 ^
  src\AstraDroid.cpp /Fe:bin\AstraDroid.exe /link Comdlg32.lib Shell32.lib
if errorlevel 1 (
  echo.
  echo [ERROR] Build that bai.
  exit /b 1
)

echo.
echo [OK] Da tao bin\AstraDroid.exe
exit /b 0
