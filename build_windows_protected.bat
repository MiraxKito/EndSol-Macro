@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title EndSol Macro - Protected Nuitka Builder
set "PY_CMD=.venv\Scripts\python.exe"

echo Checking Python and MSVC toolchain...
if not exist "%PY_CMD%" goto :missing_python
if not exist "frontend\dist\index.html" goto :missing_frontend

"%PY_CMD%" -m pip install "Nuitka>=2.6,<3"
if errorlevel 1 goto :fail

where cl >nul 2>nul
if errorlevel 1 goto :missing_msvc

rmdir /s /q build-protected 2>nul
rmdir /s /q dist-protected 2>nul
mkdir dist-protected

"%PY_CMD%" -m nuitka main.py ^
  --onefile ^
  --windows-console-mode=disable ^
  --assume-yes-for-downloads ^
  --follow-imports ^
  --include-package=biome_tracker ^
  --include-data-dir=frontend\dist=dist ^
  --include-data-file=biome_tracker\auras_cache.json=biome_tracker\auras_cache.json ^
  --include-data-dir=crafting_files_do_not_open=crafting_files_do_not_open ^
  --include-data-dir=paths=paths ^
  --include-data-dir=lib=lib ^
  --include-data-file=assets\endsol-macro.ico=assets\endsol-macro.ico ^
  --windows-icon-from-ico=assets\endsol-macro.ico ^
  --output-dir=dist-protected ^
  --output-filename=EndSolMacro.exe
if errorlevel 1 goto :fail
if not exist "dist-protected\EndSolMacro.exe" goto :fail

copy /y "dist-protected\EndSolMacro.exe" "EndSolMacro-protected.exe" >nul
if errorlevel 1 goto :fail

rem Optional Authenticode signing. A real Windows signature requires your certificate.
rem Set ENDSOL_SIGN_CERT and optionally ENDSOL_SIGN_PASSWORD before running this file.
if not defined ENDSOL_SIGN_CERT goto :unsigned
where signtool >nul 2>nul
if errorlevel 1 goto :missing_signtool
if defined ENDSOL_SIGN_PASSWORD goto :sign_with_password
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f "%ENDSOL_SIGN_CERT%" "EndSolMacro-protected.exe"
if errorlevel 1 goto :sign_failed
goto :signed
:sign_with_password
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f "%ENDSOL_SIGN_CERT%" /p "%ENDSOL_SIGN_PASSWORD%" "EndSolMacro-protected.exe"
if errorlevel 1 goto :sign_failed
goto :signed

:unsigned
echo.
echo SUCCESS: Protected EXE built without Authenticode signing.
echo To sign it, set ENDSOL_SIGN_CERT to a code-signing certificate and rerun.
goto :finish

:signed
echo.
echo SUCCESS: Protected EXE built and Authenticode-signed.
goto :finish

:finish
echo Output: EndSolMacro-protected.exe
pause
endlocal
exit /b 0

:missing_python
echo ERROR: .venv\Scripts\python.exe was not found. Run build_windows_exe.bat first.
goto :fail_pause
:missing_frontend
echo ERROR: frontend\dist\index.html is missing. Run the frontend build first.
goto :fail_pause
:missing_msvc
echo ERROR: MSVC compiler was not found. Open x64 Native Tools Command Prompt for VS 2022.
goto :fail_pause
:missing_signtool
echo ERROR: ENDSOL_SIGN_CERT was set, but signtool.exe was not found.
goto :fail_pause
:sign_failed
echo ERROR: Authenticode signing failed. The EXE was built but is not signed.
goto :fail_pause
:fail
echo.
echo ERROR: Protected Nuitka build failed. Read the error above.
:fail_pause
pause
endlocal
exit /b 1
