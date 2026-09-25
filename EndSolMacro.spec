# PyInstaller one-file build for EndSol Macro.
# Build on Windows with: python -m PyInstaller --clean --noconfirm EndSolMacro.spec
from pathlib import Path
from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH)
frontend_dist = ROOT / "frontend" / "dist"

hiddenimports = [
    "webview.platforms.edgechromium",
    "webview.platforms.winforms",
    "webview.platforms.cef",
    "win32api", "win32con", "win32gui", "win32process", "win32clipboard",
    "pythoncom", "pywintypes",
    "PIL._imaging", "cv2", "mss", "autoit", "keyboard", "mouse",
    "winocr", "ttkbootstrap", "discord", "numpy",
]
hiddenimports += collect_submodules("webview")

datas = [
    (str(frontend_dist), "dist"),
    (str(ROOT / "biome_tracker" / "auras_cache.json"), "biome_tracker"),
    (str(ROOT / "biome_tracker" / "biomes_fandom.json"), "biome_tracker"),
    (str(ROOT / "biome_tracker" / "auras_fandom.json"), "biome_tracker"),
    (str(ROOT / "biome_tracker" / "items_fandom.json"), "biome_tracker"),
    (str(ROOT / "biome_tracker" / "gauntlets_fandom.json"), "biome_tracker"),
    (str(ROOT / "crafting_files_do_not_open"), "crafting_files_do_not_open"),
    (str(ROOT / "paths"), "paths"),
    (str(ROOT / "assets" / "endsol-macro.ico"), "assets"),
]
binaries = [
    # PyAutoIt loads DLLs relative to autoit/__file__ + autoit/lib.
    # They must therefore be collected under autoit/lib, not project lib.
    (str(ROOT / "lib" / "AutoItX3.dll"), "autoit/lib"),
    (str(ROOT / "lib" / "AutoItX3_x64.dll"), "autoit/lib"),
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter.test"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="EndSolMacro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(ROOT / "assets" / "endsol-macro.ico"),
)
