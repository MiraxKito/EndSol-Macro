# Protected EXE build (Nuitka)

PyInstaller is kept as a compatibility/source build, but the recommended release build is Nuitka. Nuitka compiles Python modules to native C/C++-generated code before producing the one-file EXE. This is substantially harder to reverse than PyInstaller `.pyc` packaging, although no local executable can be made impossible to reverse-engineer.

## Build

1. Run `build_windows_exe.bat` once to install Python dependencies and build `frontend/dist`.
2. Install Visual Studio Build Tools 2022 with **Desktop development with C++**. The MSVC compiler (`cl.exe`) must be available.
3. Open a **Developer Command Prompt for VS 2022**.
4. Run:

```bat
build_windows_protected.bat
```

Output:

```text
dist-protected\EndSolMacro.exe
EndSolMacro-protected.exe
```

## Security model

- Nuitka native compilation: stronger than PyInstaller against casual bytecode extraction.
- One-file packaging: convenient distribution, not encryption.
- Do not embed cookies, bot tokens, API secrets, or private keys.
- For stronger protection, move only the most valuable algorithms to a separately compiled Cython/Rust/C++ extension and use code signing/licensing.

## Icon verification

The icon is a simple, explicit-color SVG converted into a multi-size ICO. It avoids SVG gradients and filters because some Windows/ImageMagick conversion paths render those as black. The same ICO is used for:

- Nuitka/EXE icon;
- runtime native window icon;
- taskbar icon;
- popup/recorder windows;
- frontend sidebar via SVG import.
