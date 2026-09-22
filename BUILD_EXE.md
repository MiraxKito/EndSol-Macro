# EndSol Macro — one-file EXE build

## Important security note

A packaged Python executable cannot be made impossible to decompile. PyInstaller contains Python bytecode and native dependencies that can be extracted. The supplied build makes casual copying harder, but it is not DRM or encryption.

For stronger protection, keep sensitive logic server-side or move the most valuable algorithms to a compiled extension (Cython/Rust/C++), and never embed secrets, cookies, or bot tokens in the executable.

## Build on Windows

1. Open `build_windows_exe.bat` from the project root.
2. The script detects Python and Node.js. If either is missing, it attempts to install it automatically with winget (the Windows App Installer).
3. If winget is unavailable, install/update **App Installer** from the Microsoft Store and rerun the script.
4. Run the script with an internet connection and accept the requested installation permissions.
5. The script creates `.venv`, installs `requirements.txt`, builds `frontend/dist`, and runs PyInstaller.
6. The result is `dist\EndSolMacro.exe`.

The build is intentionally one-file (`EXE`, not `COLLECT`). It extracts bundled assets to a temporary PyInstaller directory at runtime.

The requirements use the Python 3.13-compatible `pywin32` range (`>=311,<313`); the old `pywin32==307` pin was incompatible with Python 3.13 and caused pip to stop before PyInstaller.


## Included runtime assets

- `frontend/dist/index.html` under the frozen app's `dist` directory
- `biome_tracker/auras_cache.json`
- `crafting_files_do_not_open/`
- `paths/`
- AutoIt DLLs from `lib/`, packaged at runtime under `autoit/lib/` because PyAutoIt loads them relative to its package directory
- `assets/endsol-macro.ico` as the EXE, native window, taskbar, and panel icon

## User data locations

The executable must not write beside itself. Runtime data goes to:

- `%LOCALAPPDATA%\EndSolMacro\config.json`
- `%LOCALAPPDATA%\EndSolMacro\logs\macro_logs.txt`
- `%LOCALAPPDATA%\EndSolMacro\logs\error_logs.txt`
- `%LOCALAPPDATA%\EndSolMacro\themes\endsol-theme.json`

Roblox's own logs remain in `%LOCALAPPDATA%\Roblox\logs`.

## Release checks

Test the EXE on a clean Windows user profile:

- first launch and frontend startup;
- config, logs, themes, paths, and crafting files;
- 1920x1080 / 100% / Fullscreen calibration;
- fullscreen without toggling an already-fullscreen Roblox window;
- fishing and path replay;
- Auto Pop ordering;
- Bloxstrap/single-instance guard;
- import/export and restart persistence.

If one-file startup is too slow or antivirus flags it, ship the equivalent one-folder build instead; it is more reliable for pywebview and native DLLs.

## Running without compiling

For source-mode frontend testing, run `build_frontend.bat` once. It runs `npm ci` only when the locked dependencies are missing, then runs `npm run build`. Later source tests only need `Start.bat`.

The archive is also runnable as source. On Windows, install the dependencies first, build the frontend if `frontend\dist\index.html` is missing, then run:

```bat
.venv\Scripts\activate
python main.py
```

The source mode uses the same AppData folders and the same generated icon. The one-file EXE is only the packaged distribution; it is not required for development or testing.

## Protected release build

For the harder-to-reverse one-file release, use `build_windows_protected.bat` and `BUILD_PROTECTED_EXE.md`. It uses Nuitka and requires the MSVC C++ toolchain.
