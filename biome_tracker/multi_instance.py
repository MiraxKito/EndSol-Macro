r"""External MultipleRobloxInstances integration (main window + secondaries).

EndSol never launches Roblox, stores account profiles, owns PIDs, or touches
Roblox mutexes/cookies. Windows can be launched by the built-in
MultipleRobloxInstances application.

MAIN WINDOW: the full detector (fishing, quests, memory match, merchant...)
runs on the user-selected main window (`multi_instance_main_pid`, 0 = auto:
the window owning the newest log file, else first HWND). The tracker's
get_latest_log_file / activate_roblox_window / fullscreen / main Anti-AFK all
resolve through get_main_pid()/get_main_hwnd() so they can never target a
secondary window.

SECONDARY WINDOWS: the idle loop here jumps ONLY windows whose PID differs
from the main PID, and only in FREE windows of the main cycle (see
_wait_main_free / _MAIN_BUSY_FLAGS; capped by multi_instance_busy_max_wait so
a stuck flag can never silence the secondary Anti-AFK).

Instance monitor (multi_instance_alerts): each secondary window's Roblox
client writes its own log file in %LOCALAPPDATA%\Roblox\logs. The monitor
maps every window's PID to ITS log file (process start time vs file creation
time), reads the new lines incrementally (line-safe binary reads) and sends
webhook alerts for biome changes, rare aura rolls and client disconnects.
The main instance is skipped (the main detector already covers it).

Both threads run under supervisor wrappers and restart after any error.
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
_ALERT_THREAD: threading.Thread | None = None
_TRACKER: Any = None
_LAST_WINDOWS: list[dict[str, Any]] = []
_LAST_ACTION: dict[str, Any] | None = None
# pid -> {"title", "log_file", "pos", "biome", "aura", "last_event", "last_alert"}
_INSTANCE_STATE: dict[int, dict[str, Any]] = {}

_MAIN_CACHE: dict[str, Any] = {"pid": None, "at": 0.0}

# Global Anti-AFK focus lock: the multi-instance loop and the main-window
# Anti-AFK must NEVER run a focus/jump sequence at the same time, otherwise
# one thread's focus restore steals the other's (focus ends up on a random
# Roblox window instead of the user's working window).
_JUMP_LOCK = threading.Lock()

# Lowercase log fragments that indicate the client disconnected from the
# server. The explicit "[FLog::Network] Client:Disconnect" line is not
# written by every client version / disconnect type, so a small conservative
# set of alternatives is matched case-insensitively.
DISCONNECT_LOG_PATTERNS = (
    "connection lost",
    "lost connection",
    "id_connection_lost",
    "sending disconnect with reason",
)

# Tracker flags that mean "the main window is mid-action; do NOT steal its
# focus right now". This mirrors the same conflict checks the main loops use
# against each other (eden_ocr_check_loop / merchant_ocr_check_loop /
# _sleep_with_cancel): every big main-window feature is covered.
_MAIN_BUSY_FLAGS = (
    "_fishing_busy",          # fishing bite/reel/sell/merchant cycle
    "_eden_running",          # Eden run
    "_eden_checking",         # Eden OCR check (chat + UI clicks)
    "_potion_thread_active",  # potion crafting
    "_obby_running",          # obby pathing
    "_custom_path_running",   # free custom path replay
    "_br_sc_running",         # BR/SC item usage sequence
    "_mt_running",            # merchant teleporter sequence
    "on_auto_merchant_state", # auto merchant buy sequence
    "_auto_merchant_running", # auto merchant thread
    "_merchant_checking",     # merchant OCR check (chat + UI clicks)
    "_mm_session_active",     # memory match session
    "auto_pop_state",         # auto-pop buff sequence
    "reconnecting_state",     # disconnect/reconnect flow
)


def _main_busy(tracker: Any = None) -> bool:
    """True while the MAIN instance's cycle is in a phase that needs its focus
    (fishing bite/reel, sell/merchant runs, eden/potion/obby, auto-pop,
    reconnect) or while the main action scheduler is executing a click action."""
    tracker = tracker or _TRACKER
    if not tracker:
        return False
    for flag in _MAIN_BUSY_FLAGS:
        if getattr(tracker, flag, False):
            return True
    scheduler = getattr(tracker, "_action_scheduler", None)
    if scheduler is not None:
        try:
            if scheduler._action_active.is_set():
                return True
        except Exception:
            pass
    return False



def is_enabled() -> bool:
    """Public multi-instance enabled check (thread-safe)."""
    with _LOCK:
        return bool(_ENABLED)


def main_busy(tracker: Any = None) -> bool:
    """Public wrapper around _main_busy for the main-window Anti-AFK."""
    return _main_busy(tracker)


def window_count() -> int:
    """How many Roblox windows are open right now (0 when unavailable)."""
    try:
        return len(_windows())
    except Exception:
        return 0


def main_username() -> str:
    """Account username of the resolved MAIN window ('' when unknown)."""
    try:
        return _log_username(get_main_log_path() or "")
    except Exception:
        return ""


def jump_lock() -> threading.Lock:
    """The global Anti-AFK focus lock. The main-window Anti-AFK acquires it
    around its whole focus+jump+restore sequence so it can never interleave
    with a secondary jump."""
    return _JUMP_LOCK


def _latest_log_path_raw(tracker: Any) -> str | None:
    """Newest .log file in the tracker's logs dir, WITHOUT any multi-instance
    resolution (kept recursion-free; do not call get_latest_log_file here)."""
    logs_dir = getattr(tracker, "logs_dir", None)
    if not logs_dir or not os.path.isdir(logs_dir):
        return None
    latest, latest_mtime = None, -1.0
    try:
        for name in os.listdir(logs_dir):
            if not name.endswith(".log"):
                continue
            path = os.path.join(logs_dir, name)
            try:
                mt = os.path.getmtime(path)
            except OSError:
                continue
            if mt > latest_mtime:
                latest_mtime, latest = mt, path
    except Exception:
        return None
    return latest


def get_main_pid() -> int | None:
    """Resolve the MAIN Roblox window's PID.

    Order: user-selected PID (config `multi_instance_main_pid`) if that window
    is still alive; otherwise auto-fallback — the window whose log is the
    newest one (the actively played client writes the freshest log), else the
    first visible window in HWND order. Result is cached for 2 seconds.
    """
    now = time.time()
    with _LOCK:
        cached_pid = _MAIN_CACHE.get("pid")
        cached_at = float(_MAIN_CACHE.get("at") or 0.0)
    if cached_pid is not None and now - cached_at < 2.0:
        return int(cached_pid)

    windows = _windows()
    if not windows:
        with _LOCK:
            _MAIN_CACHE.update(pid=None, at=now)
        return None

    tracker = _TRACKER
    configured = 0
    try:
        configured = int((getattr(tracker, "config", {}) or {}).get("multi_instance_main_pid", 0) or 0)
    except Exception:
        configured = 0

    resolved: int | None = None
    if configured and any(w["pid"] == configured for w in windows):
        resolved = configured
    else:
        # Auto fallback #1: the window whose OWN log belongs to the
        # CONFIGURED MAIN ACCOUNT (roblox_username). "Newest log file" is
        # unreliable with 2+ clients: the alt's log can be newer and the
        # whole detector would track the alt (the main detector once read
        # the alt's log, the username guard rejected every line and
        # detection went blind).
        #
        # The resolution is pinned to the account: once a window is resolved
        # by username it stays the main one while that process lives,
        # instead of re-resolving (and possibly hopping to another
        # instance) every cache expiry. After a reconnect the fresh client
        # of the SAME account is found by username again.
        target_user = ""
        try:
            target_user = str((getattr(tracker, "config", {}) or {}).get("roblox_username", "") or "").strip().lower()
        except Exception:
            target_user = ""
        if target_user:
            sticky_pid = _STICKY_MAIN.get("pid")
            sticky_user = str(_STICKY_MAIN.get("username") or "")
            if (sticky_pid
                    and sticky_user == target_user
                    and any(w["pid"] == int(sticky_pid) for w in windows)):
                resolved = int(sticky_pid)
                # The pin belongs to the ACCOUNT, not the process: a client
                # can relog into another account within the same process.
                # If the pinned window's log now shows a different username,
                # drop the pin and re-resolve.
                try:
                    _spath = _map_logs_to_pids([int(sticky_pid)]).get(int(sticky_pid))
                    _sname = _log_username(_spath or "")
                    if _sname and _sname != target_user:
                        resolved = None
                        with _LOCK:
                            _STICKY_MAIN.update(pid=None, username="")
                except Exception:
                    pass
            if resolved is None:
                mapping = _map_logs_to_pids([w["pid"] for w in windows])
                unknown: list[int] = []
                for wpid, path in mapping.items():
                    name = _log_username(path)
                    if name == target_user:
                        resolved = int(wpid)
                        with _LOCK:
                            _STICKY_MAIN.update(pid=resolved, username=target_user)
                        break
                    if not name:
                        # The username line has not been read from this
                        # client's log yet: the window may still be the
                        # configured main account.
                        unknown.append(int(wpid))
                if resolved is None and unknown:
                    # NEVER hand the main slot to a window whose log is KNOWN
                    # to belong to a DIFFERENT account — a secondary account
                    # must not become the main instance while the configured
                    # main nick is set ( the auto
                    # fallback picked the alt because the main client's
                    # username line had not been read yet). Among unknowns
                    # prefer the freshest log, then HWND order.
                    latest = _latest_log_path_raw(tracker)
                    chosen = None
                    if latest:
                        for wpid in unknown:
                            path = mapping.get(wpid)
                            if not path:
                                continue
                            try:
                                if os.path.abspath(path) == os.path.abspath(latest):
                                    chosen = wpid
                                    break
                            except Exception:
                                continue
                    resolved = int(chosen if chosen is not None else unknown[0])
        if resolved is None:
            # Auto fallback #2: the window that owns the newest log file is
            # the actively played client (also correct right after a
            # reconnect, when the relaunched client writes a fresh log).
            latest = _latest_log_path_raw(tracker)
            if latest:
                mapping = _map_logs_to_pids([w["pid"] for w in windows])
                for wpid, path in mapping.items():
                    try:
                        if os.path.abspath(path) == os.path.abspath(latest):
                            resolved = int(wpid)
                            break
                    except Exception:
                        continue
            if resolved is None:
                resolved = int(windows[0]["pid"])

    with _LOCK:
        _MAIN_CACHE.update(pid=resolved, at=now)
    return resolved


def get_main_hwnd() -> int | None:
    """HWND of the main Roblox window (first visible window of the main PID)."""
    main_pid = get_main_pid()
    if not main_pid:
        return None
    for w in _windows():
        if w["pid"] == main_pid:
            return int(w["hwnd"])
    return None


# short-TTL cache for the main log path. get_latest_log_file resolves
# it on EVERY detection tick (biome 1s + aura 0.6s + item-change 1s), and
# _map_logs_to_pids lists the whole log dir + stats every file + queries
# each PID's create time - ~3x/s of redundant filesystem work. The mapping
# only changes when a client starts or exits, and get_main_pid() above
# re-validates the PID every 2s anyway, so a 2s TTL is safe.
_MAIN_LOG_CACHE: dict[str, Any] = {"pid": None, "path": None, "at": 0.0}
_MAIN_LOG_TTL = 2.0


def get_main_log_path() -> str | None:
    """The main window's OWN Roblox log file (None when it cannot be mapped)."""
    main_pid = get_main_pid()
    if not main_pid:
        return None
    now = time.time()
    with _LOCK:
        cached_pid = _MAIN_LOG_CACHE.get("pid")
        cached_path = _MAIN_LOG_CACHE.get("path")
        cached_at = float(_MAIN_LOG_CACHE.get("at") or 0.0)
    if cached_pid is not None and int(cached_pid) == int(main_pid) \
            and now - cached_at < _MAIN_LOG_TTL:
        return cached_path
    try:
        path = _map_logs_to_pids([int(main_pid)]).get(int(main_pid))
    except Exception:
        return None
    with _LOCK:
        _MAIN_LOG_CACHE.update(pid=int(main_pid), path=path, at=now)
    return path


def reset_main_cache() -> None:
    """Drop the cached main-PID resolution (call after the user re-selects)."""
    with _LOCK:
        _MAIN_CACHE.update(pid=None, at=0.0)


def set_main_pid(pid: int, tracker: Any = None) -> dict[str, Any]:
    """Persist the user-selected main window PID (0 = automatic)."""
    global _TRACKER
    try:
        pid = max(0, int(pid or 0))
    except Exception:
        return {"success": False, "error": "Invalid PID"}
    with _LOCK:
        if tracker:
            _TRACKER = tracker
        _MAIN_CACHE.update(pid=None, at=0.0)
        # A manual selection always wins over the username pin.
        _STICKY_MAIN.update(pid=None, username="")
    tracker = tracker or _TRACKER
    if tracker is not None:
        try:
            config = getattr(tracker, "config", None)
            if isinstance(config, dict):
                config["multi_instance_main_pid"] = pid
            save = getattr(tracker, "save_config", None)
            if callable(save):
                save()
        except Exception:
            pass
    return {"success": True, "main_pid": pid}


def _windows() -> list[dict[str, Any]]:
    """Visible Roblox windows sorted by HWND (deterministic order).

    Delegates to the shared window-first scan (base_support.roblox_top_windows):
    window PIDs are classified individually instead of exe-querying the whole
    process table, which lagged the whole app."""
    try:
        from .base_support import roblox_top_windows
        windows = roblox_top_windows()
    except Exception:
        return []
    return [{
        "hwnd": int(w["hwnd"]), "pid": int(w["pid"]),
        "title": str(w.get("title") or "") or "Roblox",
        "exe": str(w.get("exe") or ""),
        "visible": True, "rect": list(w.get("rect") or [0, 0, 0, 0]),
    } for w in windows]


def _jump_wait(key: str, default: float) -> float:
    """Configurable Anti-AFK timing (clamped 0.2-5s). Low-FPS machines need
    longer waits: the OS focus switch and the game's input polling are slow,
    and a keypress sent too early is simply dropped by the client."""
    try:
        value = float((getattr(_TRACKER, "config", {}) or {}).get(key, default))
    except Exception:
        value = default
    return max(0.2, min(5.0, value))


def _log(message: str) -> None:
    """Best-effort macro log line for Anti-AFK diagnostics."""
    try:
        log = getattr(_TRACKER, "append_log", None)
        if callable(log):
            log(message)
    except Exception:
        pass


def _set_foreground(hwnd: int) -> bool:
    """SetForegroundWindow with the ALT-key unlock trick applied FIRST.

    Windows blocks SetForegroundWindow from background processes; tapping
    ALT BEFORE the call attaches our thread to the foreground input queue,
    which is the standard reliable workaround (same order the working
    single-window Anti-AFK uses via its alt-tab trick). A window raised by
    a bare SetForegroundWindow can end up visually on top while the system
    never completes the user-activation handshake - the window then ignores
    injected keyboard input and the Anti-AFK jump silently does nothing.
    If the ALT trick is not enough, escalate to AttachThreadInput.
    """
    try:
        import ctypes
        import pyautogui
        import win32gui
        import win32process

        try:
            pyautogui.keyDown("alt")
            pyautogui.keyUp("alt")
        except Exception:
            pass
        try:
            win32gui.SetForegroundWindow(hwnd)
        except Exception:
            pass
        if win32gui.GetForegroundWindow() == hwnd:
            return True

        # Escalation: attach our thread to both input queues, retry, detach
        # (mirrors tracker._focus_window_hwnd).
        try:
            current_tid = ctypes.windll.kernel32.GetCurrentThreadId()
            fg_hwnd = win32gui.GetForegroundWindow()
            foreground_tid = win32process.GetWindowThreadProcessId(fg_hwnd)[0]
            target_tid = win32process.GetWindowThreadProcessId(hwnd)[0]
            ctypes.windll.user32.AttachThreadInput(current_tid, foreground_tid, True)
            ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, True)
            try:
                win32gui.SetForegroundWindow(hwnd)
            finally:
                ctypes.windll.user32.AttachThreadInput(current_tid, foreground_tid, False)
                ctypes.windll.user32.AttachThreadInput(current_tid, target_tid, False)
        except Exception:
            pass
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def _send_space_scancode(hold: float = 0.2) -> bool:
    """Press Space as a SCAN-CODE based SendInput event.

    pyautogui sends virtual-key-only events; Roblox reads keyboard input
    through its raw-input/scan-code path and can drop VK-only synthetic
    presses entirely - the window looks focused, but the game never sees
    the key (no jump, idle timer keeps running). Working anti-AFK tools
    send the hardware scan code (Space = 0x39) with KEYEVENTF_SCANCODE.

    The INPUT structure must include MOUSEINPUT in its union so
    ctypes.sizeof(INPUT) matches the real winuser INPUT (40 bytes on x64).
    SendInput silently returns 0 when cbSize is wrong, which used to make
    this helper fall back to pyautogui without anyone noticing.

    Returns True when the scancode SendInput path was used, False when it
    fell back to pyautogui."""
    import ctypes

    PUL = ctypes.POINTER(ctypes.c_ulong)

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [
            ("dx", ctypes.c_long),
            ("dy", ctypes.c_long),
            ("mouseData", ctypes.c_ulong),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", PUL),
        ]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [
            ("wVk", ctypes.c_ushort),
            ("wScan", ctypes.c_ushort),
            ("dwFlags", ctypes.c_ulong),
            ("time", ctypes.c_ulong),
            ("dwExtraInfo", PUL),
        ]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [
            ("uMsg", ctypes.c_ulong),
            ("wParamL", ctypes.c_ushort),
            ("wParamH", ctypes.c_ushort),
        ]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ("union",)
        _fields_ = [("type", ctypes.c_ulong), ("union", _INPUTUNION)]

    KEYEVENTF_SCANCODE = 0x0008
    KEYEVENTF_KEYUP = 0x0002
    INPUT_KEYBOARD = 1
    SPACE_SCAN = 0x39

    def _one(flags: int) -> bool:
        try:
            item = INPUT()
            item.type = INPUT_KEYBOARD
            item.ki = KEYBDINPUT(0, SPACE_SCAN, flags, 0, None)
            sent = ctypes.windll.user32.SendInput(
                1, ctypes.byref(item), ctypes.sizeof(INPUT)
            )
            return bool(sent)
        except Exception:
            return False

    if _one(KEYEVENTF_SCANCODE):
        time.sleep(max(0.05, hold))
        _one(KEYEVENTF_SCANCODE | KEYEVENTF_KEYUP)
        return True

    # SendInput unavailable or rejected: log the fallback so a "silent no
    # jump" is visible in the macro log.
    try:
        _log("[MultiInstance] Anti-AFK: scancode SendInput unavailable, using pyautogui fallback.")
    except Exception:
        pass
    import pyautogui
    pyautogui.keyDown("space")
    time.sleep(max(0.05, hold))
    pyautogui.keyUp("space")
    return False


def _mouse_into_window(hwnd: int) -> None:
    """Move the real cursor INTO the secondary window and wiggle it.

    SetCursorPos generates genuine WM_MOUSEMOVE events for the window under
    the cursor. Roblox's idle reset is input-driven: a window that is in the
    foreground but never sees any mouse presence is a prime suspect for
    jumps that "do not count". Moving the cursor in makes the jump look
    like a real user interaction before the scancode Space press.

    two fixes from the 3-window low-FPS report:
      * a MINIMIZED window reports GetWindowRect around (-32000,-32000) —
        moving the cursor there sent it off-screen and it "disappeared";
        bail out instead (the caller restores the window before this).
      * the move is interpolated over ~0.25s instead of a single teleport,
        so the cursor visibly glides instead of jumping."""
    try:
        import win32api
        import win32gui
        try:
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        except Exception:
            return
        # Minimized windows report off-screen coordinates ~(-32000). Never
        # move the real cursor off-screen.
        if right <= left or bottom <= top or left < -30000 or top < -30000:
            return
        cx = max(left + 1, min((left + right) // 2, right - 1))
        cy = max(top + 1, min((top + bottom) // 2, bottom - 1))
        try:
            start_x, start_y = win32api.GetCursorPos()
            steps = 12
            for i in range(1, steps + 1):
                t = i / steps
                ix = int(start_x + (cx - start_x) * t)
                iy = int(start_y + (cy - start_y) * t)
                win32api.SetCursorPos((ix, iy))
                time.sleep(0.02)
            time.sleep(0.05)
            win32api.SetCursorPos((min(cx + 3, right - 1), min(cy + 2, bottom - 1)))
            time.sleep(0.05)
            win32api.SetCursorPos((cx, cy))
        except Exception:
            pass
    except Exception:
        pass


def _restore_cursor(pos) -> None:
    """give the cursor back to the user after a jump.

    The jump sequence parks the cursor inside the secondary window; when the
    previous window is restored afterwards, the cursor stays hovering over a
    now-BACKGROUND window (or inside the game viewport, which the client can
    hide) — to the user the cursor simply "disappeared". Restoring the exact
    pre-jump position makes the whole jump invisible."""
    if not pos:
        return
    try:
        import win32api
        win32api.SetCursorPos((int(pos[0]), int(pos[1])))
    except Exception:
        pass


def _focus_window_for_jump(hwnd: int, attempts: int = 4) -> bool:
    """Bring the secondary window to the foreground, verifying every attempt."""
    try:
        import win32gui
        for _ in range(attempts):
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return False
            if win32gui.IsIconic(hwnd):
                try:
                    import win32con
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                except Exception:
                    pass
            if win32gui.GetForegroundWindow() == hwnd:
                return True
            if _set_foreground(hwnd):
                return True
            time.sleep(_jump_wait("multi_instance_jump_focus_wait", 1.0) * 0.5)
        return win32gui.GetForegroundWindow() == hwnd
    except Exception:
        return False


def _focus_and_jump(hwnd: int, busy_cb: Any = None) -> tuple[bool, str]:
    """Anti-AFK jump for one secondary window, low-FPS friendly.

    Deliberately slow and verified at every step (configurable via
    `multi_instance_jump_focus_wait` / `multi_instance_jump_settle_wait`,
    both default 1.0s — raise them on weak hardware):
      1. capture the CURRENT foreground window (restored at the end)
      2. focus the secondary window, VERIFY it, wait for it to settle
      3. wait a moment, then jump (Space twice, each held ~0.2s)
      4. wait for the jump to register, then restore the previous window

    `busy_cb`: called after the focus switch and again right before the
    jump. When the main window's cycle became busy in the meantime (bite
    started, sale/merchant running, scheduled action), the jump is aborted
    and the previous focus is restored — the main window must never lose
    focus during its own active cycle.
    """
    try:
        import win32gui
        import pyautogui

        if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
            return False, "window_closed"

        # Serialize with the main-window Anti-AFK: only one focus/jump/restore
        # sequence may run at a time (see _JUMP_LOCK).
        _JUMP_LOCK.acquire()
        try:
            return _focus_and_jump_locked(hwnd, busy_cb)
        finally:
            _JUMP_LOCK.release()

    except Exception as exc:
        return False, type(exc).__name__


def _focus_and_jump_locked(hwnd: int, busy_cb: Any = None) -> tuple[bool, str]:
    """The actual focus/jump sequence; caller holds _JUMP_LOCK."""
    try:
        import win32gui
        import pyautogui

        previous = win32gui.GetForegroundWindow()

        def _restore_previous() -> bool:
            """Return focus to the window the user was working in."""
            if not previous or not win32gui.IsWindow(previous):
                return False
            if win32gui.GetForegroundWindow() == previous:
                return True
            for _ in range(3):
                if _set_foreground(previous):
                    return True
                time.sleep(0.25)
            return win32gui.GetForegroundWindow() == previous

        def _main_became_busy() -> bool:
            if busy_cb is None:
                return False
            try:
                return bool(busy_cb())
            except Exception:
                return False

        focus_wait = _jump_wait("multi_instance_jump_focus_wait", 1.0)
        settle_wait = _jump_wait("multi_instance_jump_settle_wait", 1.0)

        # 1-2: focus + verify + settle. The game needs the extra beat: on
        # low-FPS clients an immediate keypress after the focus switch is
        # dropped entirely.
        if not _focus_window_for_jump(hwnd):
            return False, "focus_failed"
        time.sleep(focus_wait)
        if win32gui.GetForegroundWindow() != hwnd:
            if not _focus_window_for_jump(hwnd, attempts=2):
                return False, "focus_lost_after_wait"

        # The main cycle may have started a bite/action while we were
        # switching focus - bail out and give the main window its focus back.
        if _main_became_busy():
            _restore_previous()
            return False, "main_busy"

        # 2.5: put the real cursor inside the window first - a foreground
        # window that never sees the mouse is treated as untouched by the
        # client's idle logic (focus alone resets nothing in Roblox).
        # remember where the cursor was so it can be given back at the
        # end of the sequence.
        cursor_before = None
        try:
            import win32api
            cursor_before = win32api.GetCursorPos()
        except Exception:
            cursor_before = None
        _mouse_into_window(hwnd)

        # 3: jump - Space twice for reliability, each press held ~0.2s and
        # sent as a SCAN-CODE SendInput (VK-only pyautogui presses are
        # dropped by the Roblox client). Re-verify focus before the second
        # press: some clients steal focus slowly.
        _scancode_ok = _send_space_scancode(0.2)
        if not _scancode_ok:
            _log("[MultiInstance] Anti-AFK: jump input fell back to pyautogui (VK-only) - jump may not register.")
        time.sleep(0.45)
        if win32gui.GetForegroundWindow() != hwnd:
            # the main cycle may have taken the foreground while we
            # were jumping (item sequence, sale, scheduled action started).
            # Re-focusing the secondary NOW would steal focus back from the
            # main window in the middle of its action — bail out instead.
            if _main_became_busy():
                _restore_cursor(cursor_before)
                _restore_previous()
                return False, "main_busy"
            _focus_window_for_jump(hwnd, attempts=2)
            time.sleep(0.3)
            _mouse_into_window(hwnd)
        _send_space_scancode(0.2)

        # 4: wait for the jump to register and the character to land, then
        # always restore the previous window (verified, with retries).
        time.sleep(settle_wait)
        restored = _restore_previous()
        _restore_cursor(cursor_before)  # cursor back where the user left it

        if not restored:
            _log("[MultiInstance] Anti-AFK jump done, but the previous window could not be restored (it may have been closed).")
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


def _busy_max_wait_seconds() -> float:
    """Escape-hatch cap for waiting on the main cycle (seconds, default 300).

    A stuck busy flag (e.g. a leaked `_merchant_checking` after an exception)
    must NEVER silence the secondary Anti-AFK until the macro is stopped:
    Roblox idle-kicks windows after ~20 minutes. After this cap the jump is
    forced even if the main cycle reports busy. Configurable via
    `multi_instance_busy_max_wait` (0 = wait forever, not recommended)."""
    try:
        value = float((getattr(_TRACKER, "config", {}) or {}).get("multi_instance_busy_max_wait", 300))
    except Exception:
        value = 300.0
    if value <= 0:
        return float("inf")
    return max(30.0, value)


def _wait_main_free(tracker: Any) -> tuple[bool, bool]:
    """Wait until the main instance's cycle is in a free window (not fishing
    bite/reel/sale, no scheduled action, no eden/potion/obby run...).

    Returns (should_continue, forced):
      - (False, _) -> the loop should exit (stop requested or mode disabled)
      - (True, False) -> the main cycle is free, jump normally
      - (True, True) -> the main cycle stayed busy longer than the cap
        (`multi_instance_busy_max_wait`, default 300s) — jump anyway, because
        a stuck busy flag must not disable the secondary Anti-AFK entirely.
        One warning is logged per forced wait."""
    global _LAST_ACTION
    waited = 0.0
    warned = False
    cap = _busy_max_wait_seconds()
    while not _STOP.is_set():
        with _LOCK:
            enabled = _ENABLED
            tracker_ref = _TRACKER
        if not enabled:
            return False, False
        if not _main_busy(tracker_ref):
            if waited:
                with _LOCK:
                    _LAST_ACTION = {"status": "main_free_after_wait", "at": time.time()}
            return True, False
        if waited >= cap:
            if not warned:
                warned = True
                try:
                    log = getattr(tracker_ref, "append_log", None)
                    if callable(log):
                        log(
                            f"[MultiInstance] Main cycle busy for {int(waited)}s — "
                            f"forcing secondary Anti-AFK anyway (stuck busy flag?)."
                        )
                except Exception:
                    pass
            with _LOCK:
                _LAST_ACTION = {"status": "main_busy_forced_jump", "at": time.time()}
            return True, True
        with _LOCK:
            _LAST_ACTION = {"status": "waiting_main_free", "at": time.time()}
        _STOP.wait(0.5)
        waited += 0.5
    return False, False


def _loop() -> None:
    """Supervisor wrapper: the idle loop must NEVER die silently — it is the
    only thing keeping the secondary windows from the ~20 min idle-kick."""
    import sys
    while not _STOP.is_set():
        try:
            _loop_impl()
            return  # clean exit (stop requested or mode disabled)
        except Exception as exc:
            try:
                print(f"[MultiInstance] Idle loop error (restarting in 5s): {exc}", file=sys.stderr)
            except Exception:
                pass
            try:
                log = getattr(_TRACKER, "append_log", None)
                if callable(log):
                    log(f"[MultiInstance] Idle loop error (restarting in 5s): {exc}")
            except Exception:
                pass
            _STOP.wait(5.0)


def _loop_impl() -> None:
    """Main idle loop: cycles through the SECONDARY windows with Anti-AFK jumps.

    The MAIN window is never jumped here — the full detector (and its own
    Anti-AFK loop) runs on the main window when multi-instance mode is active.

    Flow per cycle:
      1. First cycle starts immediately
      2. Check if macro is running
      3. Wait until the main cycle is in a free window (fishing idle between
         casts, no bite/reel/sale, no scheduled action)
      4. For each SECONDARY window: focus → wait → space×2 → wait
         (each jump re-checks the main cycle and aborts if it turned busy)
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

        main_pid = get_main_pid()
        secondaries = [w for w in windows if w["pid"] != main_pid]
        if not secondaries:
            with _LOCK:
                _LAST_ACTION = {"status": "no_secondary_windows", "at": time.time()}
            print("[MultiInstance] Only the main window is open; nothing to jump.", file=sys.stderr)
            _STOP.wait(15.0)
            continue

        print(
            f"[MultiInstance] Found {len(windows)} window(s), main PID {main_pid}, "
            f"{len(secondaries)} secondary. Processing...",
            file=sys.stderr,
        )

        # Process each secondary window, always in a free window of the
        # main cycle. If the main cycle turns busy mid-round (bite started,
        # sale began, scheduled action fired), the remaining windows wait
        # for the next free window instead of being skipped entirely.
        # The wait is capped: a stuck busy flag can never silence the
        # secondary Anti-AFK until the macro is stopped.
        for idx, item in enumerate(secondaries):
            if _STOP.is_set():
                return
            run, forced = _wait_main_free(tracker)
            if not run:
                return

            # The window may have been closed while waiting.
            current = _windows()
            if item["pid"] not in {w["pid"] for w in current}:
                continue
            with _LOCK:
                _LAST_WINDOWS = current

            # Forced mode (busy cap exceeded) skips the post-focus re-check:
            # the jump MUST happen, the window would idle-kick otherwise.
            ok, reason = _focus_and_jump(item["hwnd"], busy_cb=None if forced else _main_busy)
            if not ok:
                _log(f"[MultiInstance] Anti-AFK skipped window {idx + 1}/{len(secondaries)} (PID {item['pid']}): {reason}.")
            with _LOCK:
                _LAST_ACTION = {
                    "status": "ok" if ok else "skipped",
                    "reason": reason,
                    "hwnd": item["hwnd"],
                    "pid": item["pid"],
                    "window_index": idx + 1,
                    "total_windows": len(secondaries),
                    "at": time.time(),
                }

            # Brief pause between windows (0.5s for low-end)
            if idx < len(secondaries) - 1:
                _STOP.wait(0.5)



# ---------------------------------------------------------------------------
# Instance monitor: per-window log reading + webhook alerts
# ---------------------------------------------------------------------------

def _alerts_enabled() -> bool:
    try:
        cfg = getattr(_TRACKER, "config", {}) or {}
        return bool(cfg.get("multi_instance_alerts", False))
    except Exception:
        return False


def _aura_min_rarity() -> float:
    try:
        cfg = getattr(_TRACKER, "config", {}) or {}
        return float(cfg.get("multi_instance_aura_min_rarity", 100000))
    except Exception:
        return 100000.0


def _rare_biomes_only() -> bool:
    try:
        cfg = getattr(_TRACKER, "config", {}) or {}
        return bool(cfg.get("multi_instance_alert_rare_biomes_only", True))
    except Exception:
        return True


def _roblox_logs_dir() -> str | None:
    base = os.getenv("LOCALAPPDATA")
    if not base:
        return None
    path = os.path.join(base, "Roblox", "logs")
    return path if os.path.isdir(path) else None


def _assign_logs_to_pids(pids, candidates, create_time_fn) -> dict[int, str]:
    """Greedy log<->PID assignment by process creation time.

    Strict pass: closest ctime within 20s wins, every file claimed once.
    Fallback: nearest-ctime assignment for leftovers WITHOUT the 20s cap —
    a launcher process started next to the clients (or clock skew) could
    otherwise leave a real client without its log, so the monitor would
    never read that window and its username/biome/aura stay unknown
    ( the launcher stole the main account's log)."""
    mapping: dict[int, str] = {}
    claimed: set[str] = set()
    entries: list[tuple[float, int, str]] = []
    for pid in pids:
        try:
            start = float(create_time_fn(pid))
        except Exception:
            continue
        for ctime, path in candidates:
            delta = abs(ctime - start)
            if delta <= 20.0:
                entries.append((delta, pid, path))
    for delta, pid, path in sorted(entries):
        if pid in mapping or path in claimed:
            continue
        mapping[pid] = path
        claimed.add(path)
    leftover_logs = [(ctime, path) for ctime, path in candidates if path not in claimed]
    for pid in [p for p in pids if p not in mapping]:
        try:
            start = float(create_time_fn(pid))
        except Exception:
            continue
        if not leftover_logs:
            break
        best = min(leftover_logs, key=lambda item: abs(item[0] - start))
        leftover_logs.remove(best)
        mapping[pid] = best[1]
        claimed.add(best[1])
    return mapping


def _map_logs_to_pids(pids: list[int]) -> dict[int, str]:
    """Map every running Roblox PID to its OWN client log file.

    Each client creates its log file right at startup, so the file's
    creation time (st_ctime on Windows) is matched against the process
    start time; the closest match within a 20s window wins and every file
    is claimed by at most one PID. Falls back to nothing for PIDs that
    cannot be matched (their events are simply not monitored).
    """
    if os.name != "nt" or not pids:
        return {}
    log_dir = _roblox_logs_dir()
    if not log_dir:
        return {}
    now = time.time()
    candidates: list[tuple[float, str]] = []
    try:
        for name in os.listdir(log_dir):
            if not name.lower().endswith(".log"):
                continue
            path = os.path.join(log_dir, name)
            try:
                st = os.stat(path)
            except OSError:
                continue
            # Only logs that are actually being written right now.
            if now - st.st_mtime > 300:
                continue
            candidates.append((st.st_ctime, path))
    except Exception:
        return {}
    if not candidates:
        return {}

    def create_time_fn(pid: int) -> float:
        return psutil.Process(pid).create_time()

    return _assign_logs_to_pids(list(pids), candidates, create_time_fn)


# Cached TutorialCursor username per log path. Value is (name, checked_at);
# an empty name is retried after _LOG_USERNAME_TTL seconds because the
# TutorialCursor warning can appear deep inside a long-running client's log
# (the MAIN instance's log is usually the oldest and the largest — a bounded
# prefix read missed its username line entirely).
_LOG_USERNAME_CACHE: dict[str, tuple[str, float, int]] = {}  # path -> [name, checked_at, scan_pos]
_LOG_USERNAME_TTL = 60.0
_LOG_USERNAME_SCAN_CHUNK = 1048576  # ~1MB scanned per call (no read bursts)

# Auto-mode pin: once the main window is resolved by ACCOUNT USERNAME it
# stays the main one while that process lives (the owner cannot visually
# tell instances apart by PID; the account name is the stable identity).
_STICKY_MAIN: dict[str, Any] = {"pid": None, "username": ""}


def _log_username(path: str) -> str:
    """Roblox username found in the log's TutorialCursor line ('' unknown).

    Same pattern the main detector's Log Guard uses. The file is scanned
    INCREMENTALLY: every call reads at most ~1MB starting where the previous
    attempt stopped, so even a multi-hundred-MB log of a long-running client
    is covered within a minute WITHOUT multi-megabyte read bursts that lagged
    the panel and kept Antimalware Service Executable busy. A hit is cached for the file's lifetime; new tail data
    written later (a client joining the game) is scanned as it appears."""
    if not path:
        return ""
    try:
        key = os.path.abspath(path)
    except Exception:
        return ""
    now = time.time()
    with _LOCK:
        entry = _LOG_USERNAME_CACHE.get(key)
    name = str(entry[0]) if entry else ""
    pos = int(entry[2]) if entry else 0
    if name:
        return name
    try:
        size = os.path.getsize(key)
    except OSError:
        return ""
    if pos > size:
        pos = 0  # truncated/rotated under us
    if pos >= size:
        # Fully scanned and nothing new: throttle retries.
        if entry is not None and (now - float(entry[1])) < _LOG_USERNAME_TTL:
            return ""
        with _LOCK:
            _LOG_USERNAME_CACHE[key] = ("", now, pos)
        return ""
    name = ""
    userid = ""
    new_pos = min(size, pos + _LOG_USERNAME_SCAN_CHUNK)
    try:
        import re as _re
        pattern = _re.compile(
            r"Players\.([^.']+)\.PlayerGui:WaitForChild\((?:\"|\\\")TutorialCursor",
            _re.IGNORECASE,
        )
        read_from = max(0, pos - 512)  # overlap catches boundary-spanning matches
        with open(path, "rb") as f:
            f.seek(read_from)
            data = f.read(new_pos - read_from)
        m = pattern.search(data.decode("utf-8", errors="ignore"))
        if m:
            name = str(m.group(1) or "").strip().lower()
        else:
            # Fallback (same identification Avaluate's MultipleRobloxInstances
            # uses): the game_join_loadtime line carries the client's
            # universeid/userid; the username comes from the Roblox users
            # API. Covers Bloxstrap-launched clients whose log has no
            # TutorialCursor guard line.
            m2 = _re.search(
                r"game_join_loadtime.*universeid:(\d+),.*userid:(\d+)",
                data.decode("utf-8", errors="ignore"),
            )
            if m2:
                userid = str(m2.group(2) or "")
    except Exception:
        name = ""
    if not name and userid:
        name = _username_for_userid(userid)
    with _LOCK:
        if len(_LOG_USERNAME_CACHE) > 100:
            _LOG_USERNAME_CACHE.clear()
        prev = _LOG_USERNAME_CACHE.get(key)
        # A concurrent scan may have found the name first: keep a hit.
        merged = name or (str(prev[0]) if prev else "")
        _LOG_USERNAME_CACHE[key] = (merged, now, new_pos)
    return name


# userid -> username, resolved once per account via the Roblox users API
# (the same source Avaluate's MultipleRobloxInstances uses). Network calls
# happen OUTSIDE the module lock (see state()).
_USERID_NAME_CACHE: dict[str, str] = {}


def _username_for_userid(userid: str) -> str:
    """Resolve a Roblox userid to the account username (lowercased).

    Fallback for logs without the TutorialCursor guard line (Bloxstrap
    clients): the game_join_loadtime line carries the client's userid.
    Result is cached per userid for the whole session; a failed lookup
    returns '' and is retried on the next scan pass."""
    if not userid:
        return ""
    with _LOCK:
        cached = _USERID_NAME_CACHE.get(userid)
    if cached is not None:
        return cached
    name = ""
    try:
        from .base_support import safe_get
        response = safe_get(f"https://users.roblox.com/v1/users/{userid}", timeout=5)
        if response is not None and getattr(response, "status_code", 0) == 200:
            payload = response.json()
            if isinstance(payload, dict):
                name = str(payload.get("name") or "").strip().lower()
    except Exception:
        name = ""
    with _LOCK:
        if len(_USERID_NAME_CACHE) > 500:
            _USERID_NAME_CACHE.clear()
        _USERID_NAME_CACHE[userid] = name
    return name


def _read_new_lines(path: str, pid: int) -> tuple[list[str], int, dict]:
    """Line-safe incremental read (binary): only complete newline-terminated
    lines are consumed, the offset never lands mid-line (same fix as the
    main log readers). Returns (lines, new_offset, state_dict).

    FIRST ATTACH starts at the END of the file: the monitor reports NEW
    events only. Reading a window's whole history from offset 0 replayed
    every aura the account had ever equipped into the webhook ."""
    with _LOCK:
        st = _INSTANCE_STATE.get(pid) or {}
        # First attach OR the file changed under the same PID (reconnect
        # writes a fresh log): start at the end - history is never replayed.
        first_attach = ("pos" not in st) or (
            st.get("log_file") and os.path.abspath(str(st["log_file"])) != os.path.abspath(path)
        )
        pos = 0
        if first_attach and st:
            # A fresh client log means a fresh session: the remembered
            # biome/aura are stale after a reconnect.
            st.pop("biome", None)
            st.pop("aura", None)
    if first_attach:
        try:
            pos = os.path.getsize(path)
        except OSError:
            pos = 0
    else:
        pos = max(0, int(st.get("pos", 0) or 0))
    try:
        size = os.path.getsize(path)
    except OSError:
        return [], pos, st
    if pos > size:
        pos = 0
    try:
        with open(path, "rb") as f:
            f.seek(pos)
            data = f.read()
    except OSError:
        return [], pos, st
    cut = data.rfind(b"\n")
    if cut == -1:
        return [], pos, st
    lines = data[:cut + 1].decode("utf-8", errors="ignore").splitlines()
    return lines, pos + cut + 1, st


def _aura_rarity(aura_name: str) -> float | None:
    """Rarity lookup through the tracker's aura data (loaded by the main
    detector); None when the aura is unknown."""
    tracker = _TRACKER
    if not tracker or not aura_name:
        return None
    try:
        data = getattr(tracker, "auras_data", None)
        if not isinstance(data, dict) or not data:
            data = tracker.load_auras_json() or {}
        lower = {str(k).lower(): k for k in data.keys()}
        key = lower.get(str(aura_name).lower())
        if not key:
            return None
        rarity = (data.get(key) or {}).get("rarity", None)
        if isinstance(rarity, (int, float)):
            return float(rarity)
    except Exception:
        pass
    return None



def capture_window_image(hwnd: int):
    """Capture ONE window's contents WITHOUT stealing focus (PrintWindow with
    PW_RENDERFULLCONTENT, which works for Direct3D/Roblox windows on Win8.1+).
    Returns a PIL image or None."""
    try:
        import ctypes
        import win32gui
        import win32ui
        from PIL import Image

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width, height = right - left, bottom - top
        if width <= 0 or height <= 0:
            return None
        hwnd_dc = win32gui.GetWindowDC(hwnd)
        mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
        save_dc = mfc_dc.CreateCompatibleDC()
        bmp = win32ui.CreateBitmap()
        bmp.CreateCompatibleBitmap(mfc_dc, width, height)
        save_dc.SelectObject(bmp)
        PW_RENDERFULLCONTENT = 0x0002
        ok = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)
        if not ok:
            ok = ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 0)
        info = bmp.GetInfo()
        buf = bmp.GetBitmapBits(True)
        img = Image.frombuffer(
            "RGB", (info["bmWidth"], info["bmHeight"]), buf, "raw", "BGRX", 0, 1
        )
        win32gui.DeleteObject(bmp.GetHandle())
        save_dc.DeleteDC()
        mfc_dc.DeleteDC()
        win32gui.ReleaseDC(hwnd, hwnd_dc)
        return img if ok else None
    except Exception:
        return None


def screenshot_all_window_images() -> list[dict[str, Any]]:
    """Fullscreen-capture EVERY visible Roblox window (main + secondaries)
    WITHOUT changing focus. Returns [{pid, title, path}]. Used by the remote
    /screenshot_all command; safe while the macro cycle is running."""
    import os
    out: list[dict[str, Any]] = []
    windows = [w for w in _windows() if w.get("visible", True)]
    if not windows:
        return out
    try:
        images_dir = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "EndSolMacro", "images")
    except Exception:
        images_dir = os.path.join(os.path.expanduser("~"), "EndSolMacro", "images")
    try:
        os.makedirs(images_dir, exist_ok=True)
    except Exception:
        pass
    stamp = int(time.time())
    for idx, w in enumerate(windows, 1):
        img = capture_window_image(w["hwnd"])
        if img is None:
            continue
        path = os.path.join(images_dir, f"multi_window_{stamp}_{idx}_pid{w['pid']}.png")
        try:
            img.save(path)
        except Exception:
            continue
        out.append({"pid": w["pid"], "title": w.get("title") or "Roblox", "path": path})
    return out


def _multi_webhook_urls() -> list[str]:
    """Webhook URLs for multi-instance messages.

    A dedicated webhook (`multi_instance_webhook_url`, set on the
    Multi-Instances page) keeps instance traffic out of the main stream so
    it is always clear which messages come from multi-instance mode. When
    the dedicated URL is empty, the main webhook list is used instead."""
    tracker = _TRACKER
    if not tracker:
        return []
    try:
        cfg = getattr(tracker, "config", {}) or {}
        dedicated = str(cfg.get("multi_instance_webhook_url", "") or "").strip()
        if dedicated.lower().startswith("https://"):
            return [dedicated]
    except Exception:
        pass
    try:
        urls = tracker.get_webhook_list() if hasattr(tracker, "get_webhook_list") else []
        return [u for u in urls if isinstance(u, str) and u.strip()]
    except Exception:
        return []


def _post_multi_embed(description: str, color: int, footer: str, content: str = "",
                      title: str = "") -> None:
    """Post one embed to every multi-instance webhook URL. Silent no-op
    without a tracker or URLs; never raises. `content` carries an optional
    Discord mention ping outside the embed (same shape as the main loop).

    embeds mirror the MAIN webhook style (description-only embed,
    timestamp, the shared EndSol footer icon) — the only difference is the
    per-account attribution line inside the description."""
    try:
        from .base_support import safe_request, discord_timestamp
        urls = _multi_webhook_urls()
        if not urls:
            return
        embed = {
            "description": description,
            "color": color,
            "timestamp": discord_timestamp(),
            "footer": {"text": footer,
                       "icon_url": "https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png"},
        }
        if title:
            embed["title"] = title
        payload = {"embeds": [embed]}
        if content:
            payload["content"] = content
        for url in urls:
            if isinstance(url, str) and url.strip():
                safe_request("POST", url.strip(), json=payload, timeout=15)
    except Exception:
        pass


def _send_instance_alert(description: str, color: int = 0xffa500, content: str = "") -> None:
    """Per-window event alert (biome / aura / disconnect). `description` is
    the FULL embed description (main-style heading + account line);
    `content` is an optional mention ping delivered outside the embed."""
    from .base_support import current_ver
    _post_multi_embed(description, color,
                      f"EndSol Macro {current_ver} - instance monitor", content)


def _send_multi_status(text: str, color: int = 0x5865f2) -> None:
    """Multi-instance lifecycle status (started / window count / stopped)."""
    from .base_support import current_ver
    _post_multi_embed(f"> ## {text}", color,
                      f"EndSol Macro {current_ver} - multi-instance status",
                      title="Multi-Instance")


def _instance_biome_ping(biome: str) -> str:
    """Mention content for a rare-biome instance alert.

    Mirrors the main loop's biome ping policy (build_biome_webhook_description):
    the three ultra-rare biomes ping @everyone, every other biome uses its
    per-biome ping entry from `biome_pings` (userid -> <@id>, roleid ->
    <@&id>). Biomes without a configured ping stay silent."""
    try:
        if biome in {"GLITCHED", "DREAMSPACE", "CYBERSPACE"}:
            return "@everyone"
        tracker = _TRACKER
        if not tracker:
            return ""
        cfg = getattr(tracker, "config", {}) or {}
        pings = cfg.get("biome_pings", {}) or {}
        entry = pings.get(biome, {}) if isinstance(pings, dict) else {}
        if not isinstance(entry, dict):
            entry = {}
        ping_id = str(entry.get("id", "") or "").strip()
        ping_type = str(entry.get("type", "userid") or "userid").strip().lower()
        if ping_id and ping_id.lower() not in ("everyone", "here"):
            return f"<@&{ping_id}>" if ping_type == "roleid" else f"<@{ping_id}>"
        return ""
    except Exception:
        return ""


def _instance_aura_ping(aura: str, rarity: float | None) -> str:
    """Mention content for an aura instance alert.

    Mirrors the main loop's aura ping policy (send_aura_webhook):
      - event/limited auras are announced but NEVER pinged;
      - Transcendent / Challenged / Challenged+ bypass the alert threshold
        but are sent WITHOUT a ping;
      - everything else pings only at/above the configured `ping_minimum`
        (same key the main loop uses), plus the `force_ping_auras` list.
    The mention target is the shared `aura_user_id` config value."""
    try:
        tracker = _TRACKER
        if not tracker:
            return ""
        cfg = getattr(tracker, "config", {}) or {}
        user_id = str(cfg.get("aura_user_id", "") or "").strip()
        if not user_id:
            return ""
        aura_info: dict[str, Any] = {}
        resolver = getattr(tracker, "_resolve_aura_info_for_webhook", None)
        if callable(resolver):
            resolved = resolver(aura) or (None, {})
            if isinstance(resolved, tuple) and len(resolved) == 2 and isinstance(resolved[1], dict):
                aura_info = resolved[1]
        class_name = str(aura_info.get("rarity_name", "") or "").strip().lower()
        flags = [str(f).lower() for f in (aura_info.get("flags") or [])]
        if (class_name == "event" or bool(aura_info.get("limited"))
                or "limited" in flags or "event" in flags):
            return ""
        if class_name in ("transcendent", "challenged", "challenged+"):
            return ""
        norm = str(aura).replace("_", "").replace(" ", "").lower()
        force_list = [
            x.strip().replace("_", "").replace(" ", "").lower()
            for x in str(cfg.get("force_ping_auras", "") or "").split(",") if x.strip()
        ]
        if force_list and any(x in norm or norm.startswith(x) for x in force_list):
            return f"<@{user_id}>"
        from .aura_classification import classify_aura
        if aura_info and bool(classify_aura(aura, aura_info).get("always_webhook")):
            return f"<@{user_id}>"
        if rarity is None:
            return ""
        from .mixin_webhook import _parse_rarity_value
        minimum = _parse_rarity_value(cfg.get("ping_minimum", "100000"))
        if minimum is None:
            minimum = 100000.0
        if float(rarity) >= float(minimum):
            return f"<@{user_id}>"
        return ""
    except Exception:
        return ""


# Status announcement bookkeeping (dedicated webhook stream).
_STATUS_STATE: dict[str, Any] = {"announced_start": False, "announced_count": None, "last_at": 0.0}

def _announce_window_count(count: int, main_pid: int | None, force: bool = False, note: str = "") -> None:
    """Announce the current window count (throttled, deduped).

    Sends 'Multi-instance active — N windows (1 main + M secondary)' when the
    count changes, so the dedicated webhook always shows how many windows the
    mode is actually running."""
    now = time.time()
    with _LOCK:
        if not force and _STATUS_STATE.get("announced_count") == count:
            return
        if not force and now - float(_STATUS_STATE.get("last_at") or 0.0) < 10.0:
            return
        _STATUS_STATE["announced_count"] = count
        _STATUS_STATE["last_at"] = now
    main_pid = main_pid if main_pid else get_main_pid()
    secondary = max(0, count - 1)
    main_user = ""
    try:
        main_user = _log_username(get_main_log_path() or "")
    except Exception:
        main_user = ""
    main_part = ("1 main" + (f" ({main_user})" if main_user else "")) if main_pid else "main not resolved yet"
    _send_multi_status(
        f"Multi-instance active — {count} window(s): {main_part}"
        + (f" + {secondary} secondary" if secondary else ", no secondary windows")
        + (f". {note}" if note else "")
        + (f" (main PID {main_pid})" if main_pid else ""),
        color=0x5865f2,
    )


def _announce_start(count: int, main_pid: int | None) -> None:
    """One combined status message on start.

    Previously the start announcement was immediately followed by a
    near-identical forced window-count message — two almost the same embeds
    within seconds. Now a single embed reports the count, the main account
    and the per-window alerts state, and seeds the dedup state so the next
    count change is still announced."""
    now = time.time()
    with _LOCK:
        if _STATUS_STATE.get("announced_start"):
            return
        _STATUS_STATE["announced_start"] = True
        _STATUS_STATE["announced_count"] = count
        _STATUS_STATE["last_at"] = now
    main_pid = main_pid if main_pid else get_main_pid()
    secondary = max(0, count - 1)
    main_user = ""
    try:
        main_user = _log_username(get_main_log_path() or "")
    except Exception:
        main_user = ""
    main_part = ("1 main" + (f" ({main_user})" if main_user else "")) if main_pid else "main not resolved yet"
    alerts = "on" if _alerts_enabled() else "off"
    _send_multi_status(
        f"Multi-instance started — {count} window(s): {main_part}"
        + (f" + {secondary} secondary" if secondary else ", no secondary windows")
        + f". Per-window alerts: {alerts}."
        + (f" (main PID {main_pid})" if main_pid else ""),
        color=0x2ecc71,
    )


def _announce_stop() -> None:
    with _LOCK:
        if not _STATUS_STATE.get("announced_start"):
            return
        _STATUS_STATE["announced_start"] = False
        _STATUS_STATE["announced_count"] = None
    _send_multi_status("Multi-instance paused — the macro has stopped.", color=0xe67e22)


def _instance_join_link(uname: str) -> str:
    """human 'Join Server' URL for the private server the account was
    launched into ('' when unknown — Own Server or no recorded launch)."""
    try:
        from . import instance_launcher
        return instance_launcher.join_server_link(uname)
    except Exception:
        return ""


def _process_instance_events(pid: int, lines: list[str], order: int) -> None:
    """Scan one instance's new log lines and fire alerts. Biome changes and
    disconnects alert always (rare-only filter applies to biomes); auras
    alert when their rarity reaches the configured threshold. Rare biome and
    qualifying aura alerts carry the same Discord mention pings as the main
    loop (@everyone for the ultra-rares, per-biome / aura_user_id otherwise)."""
    import re as _re
    state = _INSTANCE_STATE.setdefault(pid, {})
    # Alerts are labeled with the ACCOUNT NAME when it is known - PIDs mean
    # nothing to a human reading Discord. The account is a dedicated embed
    # line, and the headings match the main webhook style ("Biome Started -
    # X" / "✨ Aura equipped: Y"), so instance alerts read exactly like
    # main-loop alerts apart from that line.
    label = f"Instance {order}"
    try:
        uname = _log_username(str(state.get("log_file") or ""))
        if uname:
            label = uname
    except Exception:
        pass
    account_line = f"> **Account:** {label}"
    # when the account was launched into a private server, rare-biome
    # alerts carry a "Join Server" link so the user can jump into the same
    # server the instance is in.
    join_link = _instance_join_link(uname) if uname else ""
    join_line = f"\n[Join Server]({join_link})" if join_link else ""
    for line in lines:
        try:
            if "[BloxstrapRPC]" in line and '"largeImage"' in line:
                m = _re.search(
                    r'"largeImage"\s*:\s*\{[^}]*"hoverText"\s*:\s*"([^"]+)"', line)
                if m:
                    biome = m.group(1).strip().upper()
                    if biome and biome != state.get("biome"):
                        state["biome"] = biome
                        state["last_event"] = f"biome {biome}"
                        if _rare_biomes_only():
                            from .base_support import special_message_biomes
                            hot = biome in special_message_biomes
                        else:
                            hot = True
                        if hot:
                            from .base_support import discord_timestamp
                            unix_ts = int(time.time())
                            stamp = f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)"
                            _send_instance_alert(
                                f"{stamp}\n> ## Biome Started - {biome}\n{account_line}{join_line}",
                                color=0x4aff65,
                                content=_instance_biome_ping(biome))
                        continue
            match = _re.search(r'"state":"Equipped \\"(.*?)\\"', line)
            if match:
                aura = match.group(1)
                if aura and aura != state.get("aura"):
                    state["aura"] = aura
                    state["last_event"] = f"aura {aura}"
                    rarity = _aura_rarity(aura)
                    threshold = _aura_min_rarity()
                    if threshold <= 0 or (rarity is not None and rarity >= threshold):
                        rarity_line = f"> **Rarity:** 1 in {int(rarity):,}" if rarity else ""
                        _send_instance_alert(
                            f"> ## ✨ Aura equipped: {aura}\n{rarity_line}\n{account_line}".replace("\n\n", "\n"),
                            color=0xffd700,
                            content=_instance_aura_ping(aura, rarity))
                continue
            low = (line or "").lower()
            if any(pat in low for pat in DISCONNECT_LOG_PATTERNS):
                if state.get("last_event") != "disconnect":
                    state["last_event"] = "disconnect"
                    _send_instance_alert(
                        f"> ## Client disconnected\n{account_line}",
                        color=0xff0000)
                    # secondary auto-rejoin was REMOVED at the owner's
                    # request — relaunching from the macro cannot work
                    # reliably behind launchers that confirm/serialize
                    # launches (Bloxstrap's "close running instance?" dialog
                    # blocks the programmatic launch until a human clicks),
                    # and a dead disconnected window piling up is better
                    # handled manually from the panel. The disconnect ALERT
                    # itself is unchanged.
        except Exception:
            continue


def _alert_loop() -> None:
    """Supervisor wrapper: the monitor must NEVER die silently."""
    import sys
    while not _STOP.is_set():
        try:
            _alert_loop_impl()
            return
        except Exception as exc:
            try:
                print(f"[MultiInstance] Alert monitor error (restarting in 5s): {exc}", file=sys.stderr)
            except Exception:
                pass
            try:
                log = getattr(_TRACKER, "append_log", None)
                if callable(log):
                    log(f"[MultiInstance] Alert monitor error (restarting in 5s): {exc}")
            except Exception:
                pass
            _STOP.wait(5.0)


def _alert_loop_impl() -> None:
    """Monitor thread: maps windows to their logs and reports events.

    Runs while the multi-instance mode is on; does real work only when
    `multi_instance_alerts` is enabled in the config and the macro is
    running (same lifecycle as the Anti-AFK idle loop)."""
    import sys
    print("[MultiInstance] Instance monitor thread started.", file=sys.stderr)
    while not _STOP.is_set():
        with _LOCK:
            enabled = _ENABLED
            tracker = _TRACKER
        running = bool(tracker and getattr(tracker, "detection_running", False))
        if not enabled or not tracker:
            _STOP.wait(3.0)
            continue
        if not running:
            # Macro stopped: one status message on the dedicated webhook.
            with _LOCK:
                was_running = bool(_STATUS_STATE.get("announced_start"))
            if was_running:
                _announce_stop()
            _STOP.wait(3.0)
            continue

        # Multi-instance lifecycle status (dedicated webhook): announced
        # regardless of the per-window alerts toggle, so the user always
        # sees that multi-instance mode is running and how many windows
        # it currently tracks.
        windows = _windows()
        main_pid = get_main_pid()
        if windows:
            with _LOCK:
                first_announce = not bool(_STATUS_STATE.get("announced_start"))
            if first_announce:
                _announce_start(len(windows), main_pid)
            else:
                _announce_window_count(len(windows), main_pid)

        if not _alerts_enabled():
            _STOP.wait(3.0)
            continue

        windows = _windows()
        pids = [w["pid"] for w in windows]
        titles = {w["pid"]: w["title"] for w in windows}
        mapping = _map_logs_to_pids(pids)

        # The main instance is already covered by the main detector.
        main_pid = get_main_pid()

        # Dead windows: were monitored, now gone -> one alert each.
        with _LOCK:
            gone = [pid for pid in list(_INSTANCE_STATE.keys()) if pid not in set(pids)]
            for pid in gone:
                _INSTANCE_STATE.pop(pid, None)

        for pid in gone:
            _send_instance_alert(
                f"[Instance] Window closed (PID {pid})", color=0xffaa00)

        for idx, window in enumerate(windows):
            pid = window["pid"]
            log_path = mapping.get(pid)
            if not log_path:
                continue
            if pid == main_pid:
                with _LOCK:
                    prev = _INSTANCE_STATE.get(pid) or {}
                    prev_file = str(prev.get("log_file") or "")
                    changed = bool(prev_file) and os.path.abspath(prev_file) != os.path.abspath(log_path)
                    _INSTANCE_STATE[pid] = {
                        **prev,
                        "title": titles.get(pid, "Roblox"),
                        "log_file": log_path, "main": True,
                    }
                    if changed:
                        # Fresh client log under the same PID (reconnect):
                        # the retained read offset would be past the new
                        # file's size and reset to 0 -> full-history replay.
                        # Drop the stale offset and event memory.
                        _INSTANCE_STATE[pid].pop("pos", None)
                        _INSTANCE_STATE[pid].pop("biome", None)
                        _INSTANCE_STATE[pid].pop("aura", None)
                continue
            lines, new_pos, _st = _read_new_lines(log_path, pid)
            with _LOCK:
                st = _INSTANCE_STATE.setdefault(pid, {})
                st["title"] = titles.get(pid, "Roblox")
                st["log_file"] = log_path
                st["pos"] = new_pos
                st["main"] = False
                st.setdefault("biome", None)
                st.setdefault("aura", None)
                st.setdefault("last_event", None)
            if lines:
                _process_instance_events(pid, lines, idx + 1)

        _STOP.wait(2.0)
    print("[MultiInstance] Instance monitor thread stopped.", file=sys.stderr)


def set_enabled(enabled: bool, tracker: Any = None) -> dict[str, Any]:
    """Toggle the preference. Does NOT start/stop the idle loop directly.

    The toggle is a USER-ONLY control. This function only stores the value.
    The loop starts/stops with the macro cycle (start_idle_loop/stop_idle_loop).
    The built-in launcher's locks (singleton mutex + cookie file), however,
    follow the MODE, not the macro cycle — account launching must work
    while the macro itself is stopped.
    """
    global _ENABLED, _TRACKER
    with _LOCK:
        _TRACKER = tracker or _TRACKER
        _ENABLED = bool(enabled)
    try:
        from . import instance_launcher
        if _ENABLED:
            instance_launcher.ensure_locks()
        else:
            instance_launcher.release_locks()
    except Exception:
        pass
    return {"success": True, "enabled": _ENABLED}


def start_idle_loop() -> None:
    """Start the idle loop (called when detection starts in multi-instance mode)."""
    global _THREAD, _ALERT_THREAD
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
        # The instance monitor shares the same lifecycle; it does real work
        # only when `multi_instance_alerts` is enabled in the config.
        if not _ALERT_THREAD or not _ALERT_THREAD.is_alive():
            _ALERT_THREAD = threading.Thread(target=_alert_loop, name="Multi-instance alert monitor", daemon=True)
            _ALERT_THREAD.start()
        # Built-in launcher: hold the Roblox singleton mutex + cookie lock
        # while the mode runs (replaces the external launcher tool).
        try:
            from . import instance_launcher
            if _TRACKER is not None:
                instance_launcher.attach_tracker(_TRACKER)
            instance_launcher.ensure_locks()
        except Exception:
            pass


def stop_idle_loop() -> None:
    """Stop the idle loop (called when detection stops).

    This pauses the secondary Anti-AFK loop ONLY. The user preference
    `multiple_instances_enabled` is NEVER touched here: F2 / macro stop must
    never disable the mode itself (the toggle is displayed from the
    persisted config, so stopping/restarting the macro never flips it)."""
    _STOP.set()
    try:
        tracker = _TRACKER
        log = getattr(tracker, "append_log", None)
        if callable(log):
            still_on = bool((getattr(tracker, "config", {}) or {}).get("multiple_instances_enabled", False))
            log(f"[MultiInstance] Macro cycle stopped - secondary Anti-AFK paused. "
                f"Preference multiple_instances_enabled stays {'ON' if still_on else 'OFF'} (F1/F2 never change it).")
    except Exception:
        pass
    # Built-in launcher locks follow the MODE (set_enabled), NOT the macro
    # cycle: stop_idle_loop used to call release_locks(), so F2 /
    # macro-stop silently dropped the Roblox singleton mutex while the
    # Multiple-Instances preference was still ON — the launch gate then saw
    # "no lock held" and refused to launch accounts until re-ensured.
    # set_enabled(False) is the only place that releases the locks.


def state() -> dict[str, Any]:
    """Return current state. Does NOT mutate _ENABLED or any toggle state.

    `enabled` reports the PERSISTED preference (tracker config) when a
    tracker is attached, falling back to the in-memory _ENABLED flag. This
    keeps the UI toggle truthful across app restarts: _ENABLED is only set
    when the macro starts, so reporting it alone made the mode look disabled
    after every relaunch even though the config file still had it on."""
    global _LAST_WINDOWS
    # Lock scope kept MINIMAL: username lookups (which may resolve a userid
    # through the Roblox HTTP API once per account) must never run while the
    # module lock is held — a slow network call would stall every other
    # multi-instance thread.
    with _LOCK:
        enabled = _ENABLED
        cfg = getattr(_TRACKER, "config", None)
        if isinstance(cfg, dict) and "multiple_instances_enabled" in cfg:
            enabled = bool(cfg.get("multiple_instances_enabled"))
    # Refresh the window list on EVERY state poll, not only while the mode
    # is enabled: the panel's process list (and the per-window Close
    # buttons) must stay live even with the toggle off, and a frozen list
    # kept showing closed windows after the mode was disabled.
    _LAST_WINDOWS = _windows()
    main_pid = get_main_pid()
    with _LOCK:
        state_snapshot = {
            int(pid): dict(st) for pid, st in _INSTANCE_STATE.items()
        }
    # Per-instance monitor snapshot (biome/aura/last event per window)
    # plus the ACCOUNT USERNAME of every window (PIDs mean nothing to a
    # human; the account name is the visible identity). Username lookups
    # are cached per log file.
    instances = []
    username_by_pid: dict[int, str] = {}
    try:
        if enabled and _LAST_WINDOWS:
            _mapping = _map_logs_to_pids([w["pid"] for w in _LAST_WINDOWS])
            for _wpid, _path in _mapping.items():
                _u = _log_username(_path)
                if _u:
                    username_by_pid[int(_wpid)] = _u
    except Exception:
        username_by_pid = {}
    for w in _LAST_WINDOWS:
        st = state_snapshot.get(w["pid"]) or {}
        is_main = (main_pid is not None and w["pid"] == main_pid)
        instances.append({
            "pid": w["pid"],
            "title": st.get("title") or w.get("title") or "Roblox",
            "username": username_by_pid.get(int(w["pid"])) or None,
            "main": is_main,
            "log_mapped": bool(st.get("log_file")),
            "exe": (w.get("exe") or None),
            "biome": None if is_main else st.get("biome"),
            "aura": None if is_main else st.get("aura"),
            "last_event": None if is_main else st.get("last_event"),
        })
    return {
        "enabled": enabled,
        "provider": "EndSol built-in",
        "windows": list(_LAST_WINDOWS),
        "window_count": len(_LAST_WINDOWS),
        "main_pid": main_pid,
        "last_action": dict(_LAST_ACTION) if _LAST_ACTION else None,
        "alerts_enabled": _alerts_enabled(),
        "dedicated_webhook": bool(str((getattr(_TRACKER, "config", {}) or {}).get("multi_instance_webhook_url", "") or "").strip()),
        "instances": instances,
        "statistics_enabled": True,
        "capabilities": {
            "window_observation": True,
            "ordered_anti_afk": _ENABLED,
            "statistics": True,
            "main_window_selection": True,
            "main_cycle_aware_anti_afk": _ENABLED,
            "biome_detection": False,
            "aura_detection": False,
            "mouse_actions": False,
            "ocr_actions": False,
            "pathing": False,
            "fishing": False,
            "merchant": False,
            "potion_crafting": False,
            "main_instance_mode": _ENABLED,
        },
        "warning": "Roblox may close additional windows randomly; EndSol does not bypass that behavior." if _ENABLED else "",
        }


def _pid_alive(pid: int) -> bool:
    try:
        import psutil
        return psutil.pid_exists(int(pid))
    except Exception:
        return False


def close_instance(pid: int, tracker: Any = None) -> dict[str, Any]:
    """Close ONE Roblox client from the panel's process list.

    Graceful first: WM_CLOSE to every top-level window of the PID — the
    same signal the window X button sends, so the client exits cleanly and
    releases the account cookie itself. A client that ignores WM_CLOSE
    within the grace period is terminated (psutil terminate -> kill), so a
    hung client can never keep the account's session locked.

    Closing the MAIN window while the macro cycle is running is refused by
    the caller (the detector would lose its target mid-session); this
    helper only performs the close."""
    pid = int(pid)
    hwnds = [w["hwnd"] for w in _windows() if w["pid"] == pid]
    if not hwnds:
        if not _pid_alive(pid):
            return {"success": False, "error": "No Roblox window found for this PID (already closed?)."}
        return {"success": False, "error": "No Roblox window found for this PID."}
    closed_message = False
    try:
        import win32con
        import win32gui
        for h in hwnds:
            try:
                win32gui.PostMessage(int(h), win32con.WM_CLOSE, 0, 0)
                closed_message = True
            except Exception:
                pass
    except Exception:
        closed_message = False
    if not closed_message:
        try:
            import ctypes
            for h in hwnds:
                ctypes.windll.user32.PostMessageW(int(h), 0x0010, 0, 0)  # WM_CLOSE
                closed_message = True
        except Exception:
            pass
    # Grace period: give the client time to exit on its own.
    deadline = time.time() + 4.0
    while time.time() < deadline:
        if not _pid_alive(pid):
            break
        time.sleep(0.2)
    forced = False
    if _pid_alive(pid):
        forced = True
        try:
            import psutil
            proc = psutil.Process(pid)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except Exception:
                proc.kill()
        except Exception as e:
            return {"success": False, "error": f"Could not close PID {pid}: {e}"}
    try:
        log = getattr(tracker or _TRACKER, "append_log", None)
        if callable(log):
            log(f"[MultiInstance] Roblox client PID {pid} closed from the panel"
                + (" (forced after the grace period)." if forced else "."))
    except Exception:
        pass
    # Drop the stale per-instance state so the panel stops showing it.
    with _LOCK:
        _INSTANCE_STATE.pop(pid, None)
    return {"success": True, "forced": forced, "pid": pid}


def attach_tracker(tracker: Any) -> None:
    global _TRACKER
    with _LOCK:
        _TRACKER = tracker


def stop() -> None:
    stop_idle_loop()
    # Do NOT call set_enabled(False) here — the toggle is USER-ONLY
    with _LOCK:
        _INSTANCE_STATE.clear()
