@echo off
REM ============================================================
REM  EndSol Macro - GitHub publish script
REM  Pushes the source code to github.com/MiraxKito/EndSol-Macro
REM
REM  Works for BOTH cases:
REM   - empty repo  -> pushes the full history;
REM   - repo already has commits (e.g. you pushed v1.0.6 before)
REM     -> puts the current files ON TOP of the existing history
REM        (no force, no conflicts, commit history is preserved).
REM
REM  Run from the project root (where main.py is). Edit VERSION
REM  below for a new release.
REM ============================================================

setlocal
cd /d "%~dp0"

set VERSION=v1.0.6

REM ---- 1. Check that git is installed ------------------------
where git >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Git is not installed.
    echo Install it from https://git-scm.com/download/win and run this script again.
    pause
    exit /b 1
)

REM ---- 2. Initialize repo if this is the first run ----------
if not exist .git (
    git init
    echo [OK] Initialized new git repository.
)

REM ---- 3. Remove AGENTS.md (development-only file, never publish)
if exist AGENTS.md (
    del AGENTS.md
    echo [OK] Removed AGENTS.md before publishing.
)

REM ---- 4. Safety check: make sure secrets are ignored -------
REM Needs an existing repository, therefore runs after git init.
git check-ignore -q config.json
if errorlevel 1 (
    echo [WARNING] config.json is NOT covered by .gitignore!
    echo Do NOT publish until config.json is added to .gitignore.
    pause
    exit /b 1
)
echo [OK] config.json is ignored - secrets are safe.

REM ---- 5. Set branch and remote ------------------------------
git branch -M main
git remote remove origin >nul 2>&1
git remote add origin https://github.com/MiraxKito/EndSol-Macro.git

REM ---- 6. Look at what GitHub already has --------------------
echo.
echo Checking the current state of the GitHub repository...
set REMOTE_HAS_MAIN=0
git fetch origin main >nul 2>&1
if not errorlevel 1 (
    git rev-parse --verify -q origin/main >nul 2>&1
    if not errorlevel 1 set REMOTE_HAS_MAIN=1
)

REM ---- 7. Stage local files ----------------------------------
git add .

if "%REMOTE_HAS_MAIN%"=="1" (
    echo [OK] Remote main found - rebasing local files on top of it.
    git reset --soft origin/main
) else (
    echo [OK] Remote main is empty - first push.
)

git diff --cached --quiet >nul 2>&1
if errorlevel 1 (
    git commit -m "%VERSION% source update" -m "Auto-update toggle restored, biome media galleries, media thumbnails (FPS fix), fishing delay default 200, reset settings button, resilient remote bot."
    if errorlevel 1 (
        echo [ERROR] Commit failed. Resolve any git errors above and re-run.
        pause
        exit /b 1
    )
) else (
    echo [OK] Local files match the remote - nothing to commit.
)

REM ---- 8. Push -----------------------------------------------
echo.
echo Pushing to GitHub... (credentials are taken from Windows Credential Manager)
git push -u origin main
if errorlevel 1 (
    echo [ERROR] Push failed. Check your GitHub login / repo permissions.
    pause
    exit /b 1
)

REM ---- 9. Release tag ----------------------------------------
git ls-remote --exit-code --tags origin refs/tags/%VERSION% >nul 2>&1
if errorlevel 1 (
    git tag -f %VERSION%
    git push origin %VERSION%
    if errorlevel 1 (
        echo [ERROR] Tag push failed.
        pause
        exit /b 1
    )
    echo [OK] Tag %VERSION% created.
) else (
    echo [OK] Tag %VERSION% already exists on GitHub - left untouched.
    echo      To update the release, replace the EXE asset on the release page.
)

echo.
echo ============================================================
echo  DONE! Source code is on GitHub.
echo.
echo  If the %VERSION% release already exists, update its
echo  EndSolMacro.exe asset at:
echo  https://github.com/MiraxKito/EndSol-Macro/releases
echo ============================================================
pause
endlocal
