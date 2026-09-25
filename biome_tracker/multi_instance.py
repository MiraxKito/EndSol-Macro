"""External MultipleRobloxInstances integration.

EndSol never launches Roblox, stores account profiles, owns PIDs, or touches
Roblox mutexes/cookies. The user launches windows with Avaluate's
MultipleRobloxInstances application; this module only observes visible Roblox
windows and sends one Anti-AFK jump to each window in deterministic HWND order.

The idle loop only runs while the main macro cycle (detection_running) is active.
Enabling the toggle stores the preference; the loop starts/stops with the macro.

Cooperates with low-end hardware: generous waits between focus switch and input.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Any

import psutil

_LOCK = threading.RLock()
_ENABLED = False
_STOP = threading.Event()
_THREAD: threading.Thread | None = None
_TRACKER: Any = None
_LAST_WINDOWS: list[dict[str, Any]] = []
_LAST_ACTION: dict[str, Any] | None = None

ROBLOX_NAMES = {"robloxplayerbeta.exe", "windows10universal.exe"}


def _windows() -> list[dict[str, Any]]:
    """Enumerate visible Roblox windows sorted by HWND (deterministic order)."""
    if os.name != "nt":
        return []
    try:
        import win32gui
        import win32process
        pids = {
            int(p.info["pid"])
            for p in psutil.process_iter(["pid", "name"])
            if str(p.info.get("name") or "").casefold() in ROBLOX_NAMES
        }
        result: list[dict[str, Any]] = []

        def visit(hwnd: int, _param: Any) -> bool:
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                _tid, pid = win32process.GetWindowThreadProcessId(hwnd)
                if pid not in pids or not win32gui.IsWindow(hwnd):
                    return True
                left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                result.append({
                    "hwnd": int(hwnd), "pid": int(pid),
                    "title": win32gui.GetWindowText(hwnd) or "Roblox",
                    "visible": True, "rect": [left, top, right, bottom],
                })
            except Exception:
                pass
            return True

        win32gui.EnumWindows(visit, None)
        return sorted(result, key=lambda x: (x["hwnd"], x["pid"]))
    except Exception:
        return []


def _focus_and_jump(hwnd: int) -> tuple[bool, str]:
    """Focus a window, wait for it to settle, press Space, wait again, restore focus.

    Designed for low-end hardware: generous waits (0.4s after focus, 0.3s after jump)
    ensure the OS has time to switch foreground and the game registers the keypress.
    """
    try:
        import win32gui
        import pyautogui

        previous = win32gui.GetForegroundWindow()

        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return False, "window_closed"

        # Switch focus
        win32gui.SetForegroundWindow(hwnd)
        # Wait for focus to fully settle (OS + game need time)
        time.sleep(0.4)

        # Verify focus landed
        actual = win32gui.GetForegroundWindow()
        if actual != hwnd:
            # Retry once
            time.sleep(0.2)
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.4)
            if win32gui.GetForegroundWindow() != hwnd:
                return False, "focus_failed"

        # Press space (jump) — twice for reliability on low-end PCs.
        # Each keyDown is held ~0.15 s (about 0.1 s longer than before): an
        # instant tap can be missed entirely on low-FPS (<=30) clients.
        pyautogui.keyDown("space")
        time.sleep(0.15)
        pyautogui.keyUp("space")
        time.sleep(0.25)
        pyautogui.keyDown("space")
        time.sleep(0.15)
        pyautogui.keyUp("space")

        # Wait for the jump to register and the character to land
        time.sleep(0.3)

        # Restore previous focus
        if previous and win32gui.IsWindow(previous):
            try:
                win32gui.SetForegroundWindow(previous)
            except Exception:
                pass

        return True, "ok"

    except Exception as exc:
        return False, type(exc).__name__


def _cooldown_seconds() -> float:
    """Seconds between complete cycles (all windows). Based on anti_afk_interval.

    This is the total pause AFTER all windows have been processed, before the
    next round begins. Matches the main Anti-AFK loop's clamp: 1-20 minutes.
    """
    try:
        tracker = _TRACKER
        if tracker:
            value = float(getattr(tracker, "config", {}).get("anti_afk_interval", 5))
        else:
            value = 5.0
    except Exception:
        value = 5.0
    return max(60.0, min(1200.0, value * 60.0))


def _loop() -> None:
    """Main idle loop: cycles through all windows with Anti-AFK jumps.

    Flow per cycle:
      1. First cycle starts immediately
      2. Check if macro is running
      3. Enumerate windows
      4. For each window: focus → wait → space×2 → wait
      5. After all windows: wait cooldown, then repeat
    """
    global _LAST_WINDOWS, _LAST_ACTION
    import sys
    print("[MultiInstance] Idle loop started.", file=sys.stderr)

    first_run = True

    while not _STOP.is_set():
        # Wait for cooldown between full cycles (skip on first run)
        if not first_run:
            cooldown = _cooldown_seconds()
            _STOP.wait(cooldown)
            if _STOP.is_set():
                return
        first_run = False

        with _LOCK:
            if not _ENABLED:
                print("[MultiInstance] Not enabled, stopping loop.", file=sys.stderr)
                return
            tracker = _TRACKER

        # Only run when main macro cycle is active
        if not tracker or not getattr(tracker, "detection_running", False):
            with _LOCK:
                _LAST_ACTION = {"status": "waiting_for_macro", "at": time.time()}
            print("[MultiInstance] Waiting for macro to start...", file=sys.stderr)
            _STOP.wait(3.0)
            continue

        windows = _windows()
        with _LOCK:
            _LAST_WINDOWS = windows

        if not windows:
            with _LOCK:
                _LAST_ACTION = {"status": "no_windows", "at": time.time()}
            print("[MultiInstance] No Roblox windows found.", file=sys.stderr)
            # Retry soon instead of waiting a full cycle - the user may still
            # be opening the windows.
            _STOP.wait(5.0)
            continue

        print(f"[MultiInstance] Found {len(windows)} window(s). Processing...", file=sys.stderr)

        # Process each window
        for idx, item in enumerate(windows):
            if _STOP.is_set():
                return

            ok, reason = _focus_and_jump(item["hwnd"])
            with _LOCK:
                _LAST_ACTION = {
                    "status": "ok" if ok else "skipped",
                    "reason": reason,
                    "hwnd": item["hwnd"],
                    "pid": item["pid"],
                    "window_index": idx + 1,
                    "total_windows": len(windows),
                    "at": time.time(),
                }

            # Brief pause between windows (0.5s for low-end)
            if idx < len(windows) - 1:
                _STOP.wait(0.5)


def set_enabled(enabled: bool, tracker: Any = None) -> dict[str, Any]:
    """Toggle the preference. Does NOT start/stop the idle loop directly.

    The toggle is a USER-ONLY control. This function only stores the value.
    The loop starts/stops with the macro cycle (start_idle_loop/stop_idle_loop).
    """
    global _ENABLED, _TRACKER
    with _LOCK:
        _TRACKER = tracker or _TRACKER
        _ENABLED = bool(enabled)
        return {"success": True, "enabled": _ENABLED}


def start_idle_loop() -> None:
    """Start the idle loop (called when detection starts in multi-instance mode)."""
    global _THREAD
    with _LOCK:
        if not _ENABLED:
            import sys
            print("[MultiInstance] start_idle_loop called but not enabled, skipping.", file=sys.stderr)
            return
        _STOP.clear()
        _LAST_WINDOWS = _windows()
        if not _THREAD or not _THREAD.is_alive():
            _THREAD = threading.Thread(target=_loop, name="External Roblox idle monitor", daemon=True)
            _THREAD.start()
            import sys
            print("[MultiInstance] Idle loop thread started.", file=sys.stderr)


def stop_idle_loop() -> None:
    """Stop the idle loop (called when detection stops)."""
    _STOP.set()


def state() -> dict[str, Any]:
    """Return current state. Does NOT mutate _ENABLED or any toggle state."""
    global _LAST_WINDOWS
    with _LOCK:
        if _ENABLED:
            _LAST_WINDOWS = _windows()
        return {
            "enabled": _ENABLED,
            "provider": "Avaluate/MultipleRobloxInstances",
            "windows": list(_LAST_WINDOWS),
            "window_count": len(_LAST_WINDOWS),
            "last_action": dict(_LAST_ACTION) if _LAST_ACTION else None,
            "statistics_enabled": not _ENABLED,
            "capabilities": {
                "window_observation": True,
                "ordered_anti_afk": _ENABLED,
                "statistics": not _ENABLED,
                "biome_detection": False,
                "aura_detection": False,
                "mouse_actions": False,
                "ocr_actions": False,
                "pathing": False,
                "fishing": False,
                "merchant": False,
                "potion_crafting": False,
                "main_instance_mode": False,
            },
            "warning": "Roblox may close additional windows randomly; EndSol does not bypass that behavior." if _ENABLED else "",
        }


def attach_tracker(tracker: Any) -> None:
    global _TRACKER
    with _LOCK:
        _TRACKER = tracker


def stop() -> None:
    stop_idle_loop()
    # Do NOT call set_enabled(False) here — the toggle is USER-ONLY
