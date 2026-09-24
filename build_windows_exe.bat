@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title EndSol Macro - Windows EXE Builder

set "PY_CMD="
set "VENV_PY=.venv\Scripts\python.exe"

REM Prefer Python 3.10/3.11: the winocr dependency (winsdk) ships
REM prebuilt wheels only up to 3.11. On 3.12+ pip falls back to
REM compiling winsdk from source, which looks like an endless
REM "Preparing metadata (pyproject.toml)" with 100% CPU.
echo [1/6] Detecting Python 3.10 or 3.11...
if exist "%LocalAppData%\Programs\Python\Python310\python.exe" (
  set "PY_CMD=%LocalAppData%\Programs\Python\Python310\python.exe"
  goto :found_python
)
py -3.10 --version >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=py -3.10"
  goto :found_python
)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
  set "PY_CMD=%LocalAppData%\Programs\Python\Python311\python.exe"
  goto :found_python
)
py -3.11 --version >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=py -3.11"
  goto :found_python
)
py -3 --version >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=py -3"
  goto :found_python
)
python --version >nul 2>nul
if not errorlevel 1 (
  set "PY_CMD=python"
  goto :found_python
)

if not defined PY_CMD (
  echo Python was not found. Trying automatic installation with winget...
  winget --version >nul 2>nul
  if errorlevel 1 goto :fail_no_installer
  winget install --id Python.Python.3.10 --exact --scope user --accept-source-agreements --accept-package-agreements
  if errorlevel 1 goto :fail
  set "PATH=%LocalAppData%\Programs\Python\Python310;%LocalAppData%\Programs\Python\Python310\Scripts;%PATH%"
  py -3.10 --version >nul 2>nul
  if not errorlevel 1 set "PY_CMD=py -3.10"
  if not defined PY_CMD (
    python --version >nul 2>nul
    if not errorlevel 1 set "PY_CMD=python"
  )
)
if not defined PY_CMD goto :fail_python

:found_python
echo Using %PY_CMD%
rem Always recreate venv to ensure correct Python version
if exist "%VENV_PY%" (
  echo Recreating venv for correct Python version...
  rmdir /s /q .venv 2>nul
)
echo [2/6] Creating Python virtual environment...
%PY_CMD% -m venv .venv
if errorlevel 1 goto :fail
call .venv\Scripts\activate.bat
if errorlevel 1 goto :fail
set "PY_CMD=.venv\Scripts\python.exe"

echo [3/6] Installing Python dependencies...
%PY_CMD% -m pip install --upgrade pip
if errorlevel 1 goto :fail
%PY_CMD% -m pip install -r requirements.txt
if errorlevel 1 goto :fail

rem Always rebuild the frontend so a stale dist bundle cannot be packaged.
echo [4/6] Checking Node.js/npm...
where npm >nul 2>nul
if errorlevel 1 (
  echo Node.js was not found. Trying automatic installation with winget...
  winget --version >nul 2>nul
  if errorlevel 1 goto :fail_no_installer
  winget install --id OpenJS.NodeJS.LTS --exact --scope user --accept-source-agreements --accept-package-agreements
  if errorlevel 1 goto :fail
  set "PATH=%ProgramFiles%\nodejs;%LocalAppData%\Programs\nodejs;%PATH%"
)
where npm >nul 2>nul
if errorlevel 1 goto :fail_node
echo [5/6] Building frontend...
call npm --prefix frontend install
if errorlevel 1 goto :fail
call npm --prefix frontend run build
if errorlevel 1 goto :fail

echo [6/6] Building one-file EXE with PyInstaller...
if not exist assets\endsol-macro.ico goto :fail_icon
rmdir /s /q build 2>nul
rmdir /s /q dist\EndSolMacro 2>nul
if exist dist\EndSolMacro.exe del /q dist\EndSolMacro.exe
%PY_CMD% -m PyInstaller --noconfirm --clean EndSolMacro.spec
if errorlevel 1 goto :fail
if not exist dist\EndSolMacro.exe goto :fail_no_exe

echo.
echo SUCCESS: dist\EndSolMacro.exe
pause
endlocal
exit /b 0

:fail_no_installer
echo ERROR: Python/Node.js is missing and winget is unavailable. Install App Installer from Microsoft Store, then rerun.
goto :pause_fail
:fail_python
echo ERROR: Python 3.10/3.11 was not found. Install Python 3.10 from https://www.python.org/downloads/ (winsdk wheels exist only up to 3.11)
goto :pause_fail
:fail_node
echo ERROR: Node.js installation completed but npm was not detected. Restart this script or Windows and retry.
goto :pause_fail
:fail_icon
echo ERROR: assets\endsol-macro.ico is missing.
goto :pause_fail
:fail_no_exe
echo ERROR: PyInstaller finished but dist\EndSolMacro.exe was not created.
goto :pause_fail
:fail
echo.
echo ERROR: A build command failed. Read the error above.
goto :pause_fail
:pause_fail
pause
endlocal
exit /b 1
