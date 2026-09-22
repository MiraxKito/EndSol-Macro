@echo off
:: EndSol Macro — silent launcher
:: Console closes automatically when the macro panel (pywebview) shuts down.
cd /d "%~dp0"

:: Source mode must use a bundle built from frontend/src.
if not exist "frontend\dist\index.html" (
    echo frontend\dist\index.html is missing.
    echo Run build_frontend.bat once, then run Start.bat again.
    pause
    exit /b 1
)

:: Use Python 3.10 pythonw (no console window).
:: To debug, change pythonw.exe to python.exe below.
set "PY=%LOCALAPPDATA%\Programs\Python\Python310\pythonw.exe"

if exist "%PY%" (
    start "" "%PY%" main.py
    goto :eof
)

:: Fallback: try any pythonw on PATH
where pythonw.exe >nul 2>&1 && (
    start "" pythonw.exe main.py
    goto :eof
)

:: Last resort: VBS wrapper to hide console
echo Set s = CreateObject("WScript.Shell") > "%TEMP%\endsol.vbs"
echo s.Run "python.exe main.py", 0, False >> "%TEMP%\endsol.vbs"
cscript //nologo "%TEMP%\endsol.vbs"
del "%TEMP%\endsol.vbs" >nul 2>&1
