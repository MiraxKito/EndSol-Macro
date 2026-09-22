"""Windows DPI-aware coordinate mapping for Roblox client-relative calibration.

Calibration values are stored as normalized coordinates inside the Roblox client
area. Runtime pixel coordinates are derived from the current client rectangle,
so moving between DPI scales, resolutions, windowed mode, and fullscreen does
not require rewriting user settings.
"""
from __future__ import annotations

import ctypes
import os
from pathlib import Path
from typing import Any

CALIBRATION_META_KEY = "_calibration_meta"


def enable_dpi_awareness() -> None:
    """Make screen APIs report physical pixels consistently on Windows."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def _roblox_hwnds() -> list[int]:
    try:
        import psutil
        import win32gui
        import win32process
        names = {"robloxplayerbeta.exe", "windows10universal.exe"}
        pids = {
            int(p.info["pid"])
            for p in psutil.process_iter(["pid", "name"])
            if str(p.info.get("name") or "").lower() in names
        }
        result: list[int] = []
        def visit(hwnd: int, _param: Any) -> bool:
            try:
                if win32gui.IsWindowVisible(hwnd):
                    _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if pid in pids:
                        result.append(int(hwnd))
            except Exception:
                pass
            return True
        win32gui.EnumWindows(visit, None)
        # In multi-instance mode the first enumerated window is not stable.
        # Prefer the foreground Roblox client, then keep the remaining windows
        # as fallback candidates for legacy single-client flows.
        try:
            foreground = int(win32gui.GetForegroundWindow() or 0)
            if foreground in result:
                result.remove(foreground)
                result.insert(0, foreground)
        except Exception:
            pass
        return result
    except Exception:
        return []


def get_client_rect_screen(hwnd: int | None = None) -> tuple[int, int, int, int] | None:
    """Return Roblox client area as screen x, y, width, height."""
    if os.name != "nt":
        return None
    try:
        import win32gui
        if hwnd is None:
            hwnds = _roblox_hwnds()
            hwnd = hwnds[0] if hwnds else None
        if not hwnd:
            return None
        left, top, right, bottom = win32gui.GetClientRect(hwnd)
        origin_x, origin_y = win32gui.ClientToScreen(hwnd, (0, 0))
        width = max(1, int(right - left))
        height = max(1, int(bottom - top))
        return int(origin_x), int(origin_y), width, height
    except Exception:
        return None


def _valid_rect(rect: tuple[int, int, int, int] | None) -> bool:
    return bool(rect and rect[2] > 0 and rect[3] > 0)


def capture_calibration(value: list[int] | tuple[int, ...], rect: tuple[int, int, int, int] | None = None) -> dict[str, Any] | None:
    """Convert physical screen coordinates into client-relative normalized data."""
    rect = rect or get_client_rect_screen()
    if not _valid_rect(rect) or len(value) < 2:
        return None
    x0, y0, width, height = rect
    x, y = float(value[0]), float(value[1])
    meta: dict[str, Any] = {
        "space": "roblox_client_normalized",
        "x": max(0.0, min(1.0, (x - x0) / width)),
        "y": max(0.0, min(1.0, (y - y0) / height)),
    }
    if len(value) >= 4:
        meta["w"] = max(0.0, min(1.0, float(value[2]) / width))
        meta["h"] = max(0.0, min(1.0, float(value[3]) / height))
    return meta


def resolve_calibration(meta: dict[str, Any], rect: tuple[int, int, int, int] | None = None) -> list[int] | None:
    """Convert normalized client-relative calibration into physical screen pixels."""
    rect = rect or get_client_rect_screen()
    if not _valid_rect(rect) or not isinstance(meta, dict):
        return None
    if meta.get("space") != "roblox_client_normalized":
        return None
    x0, y0, width, height = rect
    try:
        x = round(x0 + float(meta["x"]) * width)
        y = round(y0 + float(meta["y"]) * height)
        if "w" in meta and "h" in meta:
            return [x, y, max(1, round(float(meta["w"]) * width)), max(1, round(float(meta["h"]) * height))]
        return [x, y]
    except (TypeError, ValueError, KeyError):
        return None


def apply_calibrations(config: dict[str, Any], rect: tuple[int, int, int, int] | None = None) -> dict[str, Any]:
    """Update only runtime coordinate values; calibration metadata remains authoritative."""
    if not isinstance(config, dict):
        return config
    meta_map = config.get(CALIBRATION_META_KEY)
    if not isinstance(meta_map, dict):
        return config
    rect = rect or get_client_rect_screen()
    for key, meta in list(meta_map.items()):
        resolved = resolve_calibration(meta, rect)
        if resolved is not None:
            config[key] = resolved
    config["_calibration_runtime_rect"] = list(rect) if _valid_rect(rect) else None
    return config


def record_calibration(config: dict[str, Any], key: str, value: list[int] | tuple[int, ...], rect: tuple[int, int, int, int] | None = None) -> None:
    """Persist normalized calibration metadata without discarding legacy values."""
    meta = capture_calibration(value, rect)
    if meta is None:
        return
    meta_map = config.setdefault(CALIBRATION_META_KEY, {})
    if isinstance(meta_map, dict):
        meta_map[str(key)] = meta
    config[str(key)] = list(map(int, value))
    apply_calibrations(config, rect)

_RUNTIME_CONFIG: dict[str, Any] | None = None
_RUNTIME_RECT_CACHE: tuple[int, int, int, int] | None = None
_RUNTIME_RECT_CACHE_AT = 0.0
_RUNTIME_VALUE_CACHE: dict[tuple[tuple[int, ...], bool, tuple[int, int, int, int] | None], Any] = {}


def set_runtime_config(config: dict[str, Any] | None) -> None:
    global _RUNTIME_CONFIG, _RUNTIME_RECT_CACHE, _RUNTIME_RECT_CACHE_AT, _RUNTIME_VALUE_CACHE
    _RUNTIME_CONFIG = config if isinstance(config, dict) else None
    _RUNTIME_RECT_CACHE = None
    _RUNTIME_RECT_CACHE_AT = 0.0
    _RUNTIME_VALUE_CACHE = {}


def _cached_runtime_rect() -> tuple[int, int, int, int] | None:
    """Avoid enumerating processes/windows on every fishing pixel/click poll."""
    global _RUNTIME_RECT_CACHE, _RUNTIME_RECT_CACHE_AT, _RUNTIME_VALUE_CACHE
    import time as _time
    now = _time.monotonic()
    if now - _RUNTIME_RECT_CACHE_AT >= 0.25:
        new_rect = get_client_rect_screen()
        if new_rect != _RUNTIME_RECT_CACHE:
            _RUNTIME_VALUE_CACHE = {}
        _RUNTIME_RECT_CACHE = new_rect
        _RUNTIME_RECT_CACHE_AT = now
    return _RUNTIME_RECT_CACHE


def _runtime_value(value: Any, region: bool = False) -> Any:
    cfg = _RUNTIME_CONFIG
    if not cfg:
        return value
    try:
        key_value = tuple(int(v) for v in value)
        rect = _cached_runtime_rect()
        cache_key = (key_value, bool(region), rect)
        if cache_key in _RUNTIME_VALUE_CACHE:
            return _RUNTIME_VALUE_CACHE[cache_key]
        meta_map = cfg.get(CALIBRATION_META_KEY, {})
        if not isinstance(meta_map, dict): return value
        for key, meta in meta_map.items():
            current = cfg.get(key)
            if isinstance(current, (list, tuple)) and len(current) >= (4 if region else 2):
                if all(int(current[i]) == int(value[i]) for i in range(4 if region else 2)):
                    resolved = resolve_calibration(meta, rect)
                    if resolved is not None:
                        result = tuple(resolved) if region else (resolved[0], resolved[1])
                        _RUNTIME_VALUE_CACHE[cache_key] = result
                        return result
        _RUNTIME_VALUE_CACHE[cache_key] = value
    except Exception:
        pass
    return value

def runtime_point(value: Any) -> Any:
    """Resolve a saved point against the current Roblox client rectangle."""
    try:
        return _runtime_value(tuple(value), region=False) if isinstance(value, (list, tuple)) else value
    except Exception:
        return value


def runtime_region(value: Any) -> Any:
    """Resolve a saved screen region against the current Roblox client rectangle."""
    try:
        return _runtime_value(tuple(value), region=True) if isinstance(value, (list, tuple)) else value
    except Exception:
        return value


def install_input_wrappers() -> None:
    """Route legacy direct AutoIt/PyAutoGUI calls through the same mapper."""
    try:
        import autoit
        if not getattr(autoit, "_endsol_calibrated", False):
            original_click = autoit.mouse_click
            def mouse_click(button, x, y, *args, **kwargs):
                px, py = runtime_point((x, y))
                return original_click(button, px, py, *args, **kwargs)
            # Do not wrap mouse_move: recorded camera/path playback uses
            # absolute event coordinates and must preserve the recording.
            autoit.mouse_click = mouse_click
            autoit._endsol_calibrated = True
    except Exception:
        pass
    try:
        import pyautogui
        if not getattr(pyautogui, "_endsol_calibrated", False):
            original_screenshot = pyautogui.screenshot
            def screenshot(*args, **kwargs):
                region = kwargs.get("region")
                if region is not None:
                    kwargs["region"] = _runtime_value(tuple(region), region=True)
                return original_screenshot(*args, **kwargs)
            pyautogui.screenshot = screenshot
            pyautogui._endsol_calibrated = True
    except Exception:
        pass
