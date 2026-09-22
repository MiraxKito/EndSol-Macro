@echo off
setlocal EnableExtensions
cd /d "%~dp0frontend"
title EndSol Macro - Frontend Builder

where npm >nul 2>nul
if errorlevel 1 (
  echo ERROR: npm was not found. Install Node.js LTS, then run this script again.
  pause
  exit /b 1
)

if not exist "node_modules\vite\package.json" (
  echo Frontend dependencies are not installed.
  echo The first run downloads the locked dependencies from package-lock.json.
  call npm ci
  if errorlevel 1 goto :fail
)

echo Building frontend from current source...
call npm run build
if errorlevel 1 goto :fail

echo.
echo SUCCESS: frontend\dist was rebuilt.
pause
exit /b 0

:fail
echo.
echo ERROR: Frontend build failed. Read the error above.
pause
exit /b 1
