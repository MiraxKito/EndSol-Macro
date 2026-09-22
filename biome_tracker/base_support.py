import traceback
import pygetwindow as gw
from tkinter import messagebox, filedialog, simpledialog
import tkinter as tk
from PIL import Image, ImageTk
from datetime import datetime, timedelta, timezone
import ttkbootstrap as ttk
import logging
import shutil, glob
import atexit
import difflib
import itertools
import zipfile, subprocess, tempfile
import keyboard as kb
import json, requests, time, os, threading, re, webbrowser, random, keyboard, pyautogui, autoit, psutil, \
    locale, win32gui, win32process, win32con, ctypes, queue, mouse, sys, hashlib, winocr, asyncio, win32api, traceback

current_ver = os.environ.get("ENDSOL_MACRO_VERSION", "v1.0.5")

rare_biomes = ["GLITCHED", "DREAMSPACE", "CYBERSPACE", "SINGULARITY"]
admin_biomes = ["THE HYPERSPACE REALM", "赤い満月", "THE NULL'S EXISTENCE", "THE CITADEL OF ORDERS"]
special_message_biomes = set(rare_biomes + admin_biomes)


# в”Ђв”Ђ Discord webhook helpers в”Ђв”Ђ
def discord_timestamp() -> str:
    """
    Build an ISO-8601 timestamp string Discord will accept.

    Discord requires strict ISO-8601 with 'T' separator and explicit timezone.
    Returning a naive datetime string (which is what `str(datetime)` produces)
    causes Discord to reject the embed with HTTP 400.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S+00:00")


def discord_color(value) -> int:
    """
    Normalize a color value to a 0-0xFFFFFF integer for Discord.

    Accepts:
      - int                  -> returned as-is
      - "0xRRGGBB"           -> parsed
      - "#RRGGBB" / "RRGGBB" -> parsed
    Returns 0xffffff on anything unparseable so Discord never gets a 400.
    """
    if isinstance(value, int):
        return value & 0xFFFFFF
    if not isinstance(value, str):
        return 0xFFFFFF
    s = value.strip().lstrip("#")
    if s.lower().startswith("0x"):
        s = s[2:]
    try:
        return int(s, 16) & 0xFFFFFF
    except (ValueError, TypeError):
        return 0xFFFFFF


# в”Ђв”Ђ Keyboard layout helpers в”Ђв”Ђ
# Macro actions that send literal characters (e.g. "/aura", chat commands)
# only produce the expected keys when the active Windows input language is
# English. We auto-switch on macro start so symbols are never typed in the
# wrong script (Cyrillic/etc. layouts turn "/aura" into "...").
# LCID 0x0409 = English (US). Any other 0x04xx variant also counts as English.

_ENGLISH_LCIDS = {
    0x0409,  # English (US)
    0x0809,  # English (UK)
    0x0C09,  # English (Australian)
    0x1009,  # English (Canadian)
    0x1409,  # English (New Zealand)
    0x1809,  # English (Ireland)
    0x1C09,  # English (South Africa)
    0x2009,  # English (Jamaica)
    0x2409,  # English (Caribbean)
    0x2809,  # English (Belize)
    0x2C09,  # English (Trinidad)
    0x3009,  # English (Zimbabwe)
    0x3409,  # English (Philippines)
    0x4009,  # English (India)
    0x4409,  # English (Malaysia)
    0x4809,  # English (Singapore)
}

# Win32 constants for ActivateKeyboardLayout
_KLF_SETFORPROCESS = 0x00000100
_HKL_NEXT = 1
_HKL_PREV = 0


def _hkl_to_lcid(hkl):
    """Extract the language identifier from an HKL handle."""
    if not hkl:
        return 0
    return hkl & 0xFFFF


def get_active_keyboard_lcid() -> int:
    """Return the LCID of the foreground thread's active keyboard layout."""
    try:
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        if hwnd:
            tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None)
        else:
            tid = ctypes.windll.kernel32.GetCurrentThreadId()
        hkl = ctypes.windll.user32.GetKeyboardLayout(tid)
        return _hkl_to_lcid(hkl)
    except Exception:
        return 0


def is_english_layout_active() -> bool:
    """True if the foreground window's keyboard layout is any English variant."""
    return get_active_keyboard_lcid() in _ENGLISH_LCIDS


def find_english_hkl():
    """Walk loaded keyboard layouts and return the first English HKL we find."""
    try:
        # Max number of layouts the OS will report
        max_count = 64
        buf = (ctypes.c_void_p * max_count)()
        n = ctypes.windll.user32.GetKeyboardLayoutList(max_count, buf)
        for i in range(n):
            hkl = buf[i]
            if _hkl_to_lcid(hkl) in _ENGLISH_LCIDS:
                return hkl
    except Exception:
        pass
    return None


def switch_to_english_layout() -> dict:
    """
    Try to make an English keyboard layout active for the foreground window.

    Returns a dict describing the outcome so the caller can surface a message:
        {
            "ok": bool,
            "already_english": bool,
            "english_available": bool,
            "error": str | None,
        }
    """
    result = {
        "ok": False,
        "already_english": False,
        "english_available": False,
        "error": None,
    }
    try:
        if is_english_layout_active():
            result["ok"] = True
            result["already_english"] = True
            result["english_available"] = True
            return result

        target = find_english_hkl()
        if not target:
            result["error"] = "No English keyboard layout installed on this system"
            return result
        result["english_available"] = True

        # Switch layout for the foreground window's thread, with the
        # KLF_SETFORPROCESS flag so the change sticks for the whole process
        hwnd = ctypes.windll.user32.GetForegroundWindow()
        tid = ctypes.windll.user32.GetWindowThreadProcessId(hwnd, None) if hwnd else ctypes.windll.kernel32.GetCurrentThreadId()
        ok = ctypes.windll.user32.ActivateKeyboardLayout(target, _KLF_SETFORPROCESS)
        if not ok:
            # Try without KLF flag as a fallback
            ok = ctypes.windll.user32.ActivateKeyboardLayout(target, 0)
        if ok:
            result["ok"] = True
        else:
            result["error"] = "ActivateKeyboardLayout returned NULL"
    except Exception as e:
        result["error"] = str(e)
    return result


# в”Ђв”Ђ Safe HTTP request helper в”Ђв”Ђ
# This machine's network blocks/breaks standard SSL for some hosts.
# Use verify=False + longer timeouts + retry on transient failures so fetch
# works reliably whether GitHub is slow, the SSL handshake hangs, or there's
# a temporary connection drop.
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib3

# Silence the InsecureRequestWarning globally for this macro
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_DEFAULT_TIMEOUT = 15  # seconds, used when caller doesn

def ensure_english_layout_silent() -> bool:
    """
    Re-assert the English layout just before a keyboard-emitting action.
    Use as defensive wrapper around any function that calls
    `keyboard.press_and_release`, `pyautogui.press`, or otherwise types
    literal characters. Windows may revert to the user's preferred layout
    between actions. If an English layout is not available we silently
    return False; the caller should already have aborted at startup.
    """
    try:
        if is_english_layout_active():
            return True
        result = switch_to_english_layout()
        return bool(result.get("ok"))
    except Exception:
        return False

_DEFAULT_TIMEOUT = 15  # seconds, used when caller doesn't specify
_USER_AGENT = "EndSol-Macro/1.0"


def _build_session() -> "requests.Session":
    """Build a requests.Session with retries enabled for transient failures."""
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.6,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=frozenset(["GET", "POST", "PUT", "DELETE", "HEAD", "PATCH"]),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({"User-Agent": _USER_AGENT})
    return session


_SHARED_SESSION = _build_session()


def safe_request(
    method: str,
    url: str,
    *,
    timeout: float = _DEFAULT_TIMEOUT,
    verify: bool = True,
    retries: int = 2,
    backoff: float = 0.6,
    **kwargs,
) -> "requests.Response | None":
    """
    Make an HTTP request with built-in resilience.

    - verify=True   : validate TLS certificates by default
    - retries       : additional attempts on connection errors, read timeouts
      and chunked-encoding hiccups
    - backoff       : sleep multiplier between retries
    - timeout       : per-attempt timeout, default 15s (was 0.5вЂ“5s in many
      call sites, too aggressive for this network)

    Returns the Response on success, or None if every attempt failed.
    Callers should treat None as "feature unavailable" rather than crashing.
    """
    last_err = None
    attempts = max(1, retries + 1)
    for attempt in range(attempts):
        try:
            resp = _SHARED_SESSION.request(
                method,
                url,
                timeout=timeout,
                verify=verify,
                **kwargs,
            )
            return resp
        except (
            requests.exceptions.SSLError,
            requests.exceptions.ConnectionError,
            requests.exceptions.Timeout,
            requests.exceptions.ChunkedEncodingError,
            requests.exceptions.ContentDecodingError,
        ) as e:
            last_err = e
            if attempt < attempts - 1:
                sleep_s = backoff * (2 ** attempt)
                time.sleep(sleep_s)
                continue
        except Exception as e:
            last_err = e
            break
    # All attempts failed
    try:
        import sys as _sys
        print(f"[safe_request] {method} {url} failed after {attempts} attempt(s): {last_err}", file=_sys.stderr)
    except Exception:
        pass
    return None


def safe_get(url: str, **kwargs) -> "requests.Response | None":
    return safe_request("GET", url, **kwargs)


def safe_post(url: str, **kwargs) -> "requests.Response | None":
    return safe_request("POST", url, **kwargs)


# ━━━ Fandom rate-limit protection ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Fandom (MediaWiki) throttles API hosts aggressively: parallel or rapid
# requests get 429s, which made Sol's Book load inconsistently (some runs
# fetched fresh data, others silently fell back to the offline snapshot).
# Rules used here:
#   * never hit a Fandom host more than once per FANDOM_MIN_INTERVAL seconds
#     process-wide (all threads go through the same gate),
#   * when a 429 arrives, pause EVERY Fandom request for Retry-After seconds
#     (MediaWiki etiquette: wait at least 5s, prefer the header),
#   * the urllib3 Retry on the shared adapter already respects Retry-After
#     for transport-level retries; fandom_get adds the process-wide pacing
#     and cooldown on top.
_FANDOM_HOST_MARKERS = ("fandom.com", "fandom.dev", "wikia.nocookie.net", "wikia.com")
_FANDOM_LOCK = threading.Lock()
_FANDOM_STATE = {"last": 0.0, "cooldown_until": 0.0}
FANDOM_MIN_INTERVAL = 1.0        # s between two Fandom requests process-wide
_FANDOM_COOLDOWN_DEFAULT = 45.0  # s when 429 has no usable Retry-After
_FANDOM_COOLDOWN_MAX = 120.0


def _is_fandom_url(url: str) -> bool:
    try:
        low = str(url).lower()
        return any(m in low for m in _FANDOM_HOST_MARKERS)
    except Exception:
        return False


def _fandom_gate() -> None:
    """Block the calling thread until the next Fandom request is allowed."""
    while True:
        with _FANDOM_LOCK:
            now = time.time()
            wait = _FANDOM_STATE["last"] + FANDOM_MIN_INTERVAL - now
            cd = _FANDOM_STATE["cooldown_until"] - now
            wait = max(wait, cd)
            if wait <= 0:
                _FANDOM_STATE["last"] = now
                return
        time.sleep(min(max(wait, 0.05), 2.0))


def _fandom_report_429(retry_after_raw) -> None:
    """Record a 429 so every Fandom request pauses for Retry-After seconds."""
    with _FANDOM_LOCK:
        try:
            wait = float(retry_after_raw) if retry_after_raw not in (None, "") else _FANDOM_COOLDOWN_DEFAULT
        except (TypeError, ValueError):
            wait = _FANDOM_COOLDOWN_DEFAULT
        wait = min(max(wait, 5.0), _FANDOM_COOLDOWN_MAX)
        until = time.time() + wait
        if until > _FANDOM_STATE["cooldown_until"]:
            _FANDOM_STATE["cooldown_until"] = until


def fandom_get(url: str, *, timeout: float = _DEFAULT_TIMEOUT, retries: int = 2, **kwargs) -> "requests.Response | None":
    """GET for Fandom endpoints: paced process-wide, 429/Retry-After aware.

    Returns the Response on success, or None after repeated 429s / failures —
    callers treat None as "use the next source / offline snapshot".
    Non-Fandom URLs behave exactly like safe_get.
    """
    if not _is_fandom_url(url):
        return safe_get(url, timeout=timeout, retries=retries, **kwargs)
    attempts = max(1, retries + 1)
    last_429 = False
    for attempt in range(attempts):
        _fandom_gate()
        resp = safe_request("GET", url, timeout=timeout, retries=0, **kwargs)
        if resp is None:
            return None  # network-level failure already retried/logged upstream
        if resp.status_code == 429:
            last_429 = True
            _fandom_report_429(resp.headers.get("Retry-After"))
            continue
        return resp
    if last_429:
        try:
            print(f"[fandom_get] giving up after {attempts} attempt(s) with 429: {url}", file=sys.stderr)
        except Exception:
            pass
    return None


def is_network_available(hosts: list = None) -> bool:
    """Quick connectivity probe. Returns True if any host responds."""
    hosts = hosts or [
        "https://raw.githubusercontent.com",
        "https://sol-rng.fandom.com",
        "https://discord.com",
    ]
    for host in hosts:
        try:
            r = _SHARED_SESSION.get(host, timeout=5, verify=True, stream=True)
            try:
                r.close()
            except Exception:
                pass
            return True
        except Exception:
            continue
    return False

# в”Ђв”Ђ Biome category classification (based on Sol's RNG wiki data) в”Ђв”Ђ
BIOME_CATEGORY_WEATHER  = "weather"
BIOME_CATEGORY_RARE     = "rare"
BIOME_CATEGORY_EVENT    = "event"
BIOME_CATEGORY_ADMIN    = "admin"
BIOME_CATEGORY_OTHER    = "other"

BIOME_CATEGORIES: dict[str, str] = {
    # Weather / Normal
    "NORMAL":       BIOME_CATEGORY_WEATHER,
    "WINDY":        BIOME_CATEGORY_WEATHER,
    "SNOWY":        BIOME_CATEGORY_WEATHER,
    "RAINY":        BIOME_CATEGORY_WEATHER,
    "SAND STORM":   BIOME_CATEGORY_WEATHER,
    "HELL":         BIOME_CATEGORY_WEATHER,
    "STARFALL":     BIOME_CATEGORY_WEATHER,
    "HEAVEN":       BIOME_CATEGORY_WEATHER,
    "CORRUPTION":   BIOME_CATEGORY_WEATHER,
    "NULL":         BIOME_CATEGORY_WEATHER,
    # Rare (4)
    "GLITCHED":     BIOME_CATEGORY_RARE,
    "DREAMSPACE":   BIOME_CATEGORY_RARE,
    "CYBERSPACE":   BIOME_CATEGORY_RARE,
    "SINGULARITY":  BIOME_CATEGORY_RARE,
    # Limited / Event
    "PUMPKIN MOON": BIOME_CATEGORY_EVENT,
    "GRAVEYARD":    BIOME_CATEGORY_EVENT,
    "BLOOD RAIN":   BIOME_CATEGORY_EVENT,
    "AURORA":       BIOME_CATEGORY_EVENT,
    "EGGLAND":      BIOME_CATEGORY_EVENT,
    "BLAZING SUN":  BIOME_CATEGORY_EVENT,
    "INCINERATOR":   BIOME_CATEGORY_EVENT,
    # Developer Event / Admin
    "THE HYPERSPACE REALM":   BIOME_CATEGORY_ADMIN,
    "иµ¤гЃ„жєЂжњ€":              BIOME_CATEGORY_ADMIN,
    "THE NULL'S EXISTENCE":  BIOME_CATEGORY_ADMIN,
    "THE CITADEL OF ORDERS": BIOME_CATEGORY_ADMIN,
}

BIOME_CATEGORY_LABELS: dict[str, str] = {
    BIOME_CATEGORY_WEATHER: "Normal (Weather)",
    BIOME_CATEGORY_RARE:    "Rare",
    BIOME_CATEGORY_EVENT:   "Event (Limited)",
    BIOME_CATEGORY_ADMIN:   "Admin (Dev Event)",
    BIOME_CATEGORY_OTHER:   "Other / Unlisted",
}

def get_biome_category(biome_name: str) -> str:
    """Return the category key for a biome, falling back to 'other'."""
    return BIOME_CATEGORIES.get(biome_name.upper().strip(), BIOME_CATEGORY_OTHER)

class ConfigVar:
    def __init__(self, config: dict, key: str, default=None):
        self._cfg = config
        self._key = key
        self._default = default

    def get(self):
        return self._cfg.get(self._key, self._default)

    def set(self, value):
        self._cfg[self._key] = value


def fuzzy_match_any(text, candidates, threshold=0.6):
    try:
        import difflib
    except Exception:
        return False

    if not text:
        return False

    t = str(text).lower().strip()
    tokens = [tok for tok in re.split(r"\s+|[^a-z0-9]", t) if tok]

    for cand in candidates:
        c = str(cand).lower().strip()
        if not c:
            continue
        if c in t:
            return True
        try:
            whole_ratio = difflib.SequenceMatcher(None, c, t).ratio()
            if whole_ratio >= threshold:
                return True
        except Exception:
            pass
        for tok in tokens:
            try:
                if difflib.SequenceMatcher(None, c, tok).ratio() >= threshold:
                    return True
            except Exception:
                pass
    return False

def fuzzy_correct_item_name(text, mapping, threshold=0.6):
    try:
        import difflib
    except Exception:
        return text

    if not text:
        return text

    t = str(text).lower().strip()
    for mis, correct in mapping.items():
        if t == mis.lower().strip():
            return correct
    tokens = [tok for tok in re.split(r"\s+|[^a-z0-9]", t) if tok]

    best_score = 0.0
    best_correct = None
    best_key = None

    for mis, correct in mapping.items():
        mis_norm = str(mis).lower().strip()
        try:
            if mis_norm in t:
                return correct
        except Exception:
            pass
        try:
            score_whole = difflib.SequenceMatcher(None, t, mis_norm).ratio()
            if score_whole > best_score:
                best_score = score_whole
                best_correct = correct
                best_key = mis
        except Exception:
            pass
        for tok in tokens:
            try:
                score_tok = difflib.SequenceMatcher(None, tok, mis_norm).ratio()
                if score_tok > best_score:
                    best_score = score_tok
                    best_correct = correct
                    best_key = mis
            except Exception:
                pass

    if best_score >= float(threshold):
        return best_correct

    return text

class SnippingWidget:
    def __init__(self, root, config_key=None, callback=None):
        self.root = root
        self.config_key = config_key
        self.callback = callback
        self.snipping_window = None
        self.begin_x = None
        self.begin_y = None
        self.end_x = None
        self.end_y = None

    def start(self):
        self.snipping_window = tk.Toplevel(self.root)
        self.snipping_window.attributes('-fullscreen', True)
        self.snipping_window.attributes('-topmost', True)
        self.snipping_window.attributes('-alpha', 0.3)
        self.snipping_window.configure(bg="lightblue", cursor="cross_reverse")

        self.snipping_window.bind("<Button-1>", self.on_mouse_press)
        self.snipping_window.bind("<B1-Motion>", self.on_mouse_drag)
        self.snipping_window.bind("<ButtonRelease-1>", self.on_mouse_release)

        self.canvas = tk.Canvas(self.snipping_window, bg="lightblue", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.snipping_window.lift()
        self.snipping_window.focus_force()

    def on_mouse_press(self, event):
        self.begin_x = event.x
        self.begin_y = event.y
        self.canvas.delete("selection_rect")

    def on_mouse_drag(self, event):
        self.end_x, self.end_y = event.x, event.y
        self.canvas.delete("selection_rect")
        self.canvas.create_rectangle(self.begin_x, self.begin_y, self.end_x, self.end_y,
                                     outline="white", width=2, tag="selection_rect")

    def on_mouse_release(self, event):
        self.end_x = event.x
        self.end_y = event.y

        x1, y1 = min(self.begin_x, self.end_x), min(self.begin_y, self.end_y)
        x2, y2 = max(self.begin_x, self.end_x), max(self.begin_y, self.end_y)

        self.capture_region(x1, y1, x2, y2)
        self.snipping_window.destroy()

    def capture_region(self, x1, y1, x2, y2):
        if self.config_key:
            region = [x1, y1, x2 - x1, y2 - y1]
            print(f"Region for '{self.config_key}' set to {region}")

            if self.callback:
                self.callback(region)


class CalibrationManager:
    def __init__(self):
        self._queue = queue.Queue()
        self._window = None  # pywebview window ref
        self._tracker = None
        self._save_fn = None
        self._emit_fn = None
        self._overlay_window = None
        threading.Thread(target=self._tk_loop, daemon=True).start()

    def set_refs(self, window, tracker, save_fn, emit_fn):
        self._window = window
        self._tracker = tracker
        self._save_fn = save_fn
        self._emit_fn = emit_fn

    def request_calibration(self, config_key, window_type="point"):
        print(f"[CalibrationManager] Queued snip for '{config_key}', type: {window_type}")
        self._queue.put({"action": "calibrate", "key": config_key, "type": window_type})

    def request_display(self, config_key, label=None, duration_ms=2500):
        self._queue.put({
            "action": "display",
            "key": config_key,
            "label": label or str(config_key),
            "duration_ms": int(duration_ms) if duration_ms else 2500
        })

    def request_display_many(self, items, duration_ms=2500):
        self._queue.put({
            "action": "display_many",
            "items": items if isinstance(items, list) else [],
            "duration_ms": int(duration_ms) if duration_ms else 2500
        })

    def _destroy_overlay(self):
        try:
            if self._overlay_window is not None:
                try:
                    self._overlay_window.destroy()
                except Exception:
                    pass
                self._overlay_window = None
        except Exception:
            self._overlay_window = None

    def _render_calibration_overlay(self, root, value, label, duration_ms=2500):
        try:
            if not isinstance(value, (list, tuple)) or len(value) < 2:
                return

            self._destroy_overlay()
            overlay = ttk.Toplevel(root)
            overlay.overrideredirect(True)
            overlay.attributes("-topmost", True)
            try:
                overlay.attributes("-alpha", 0.22)
            except Exception:
                pass

            screen_w = overlay.winfo_screenwidth()
            screen_h = overlay.winfo_screenheight()
            overlay.geometry(f"{screen_w}x{screen_h}+0+0")
            overlay.configure(bg="black")

            canvas = ttk.Canvas(overlay, bg="black", highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)

            is_region = len(value) >= 4
            if is_region:
                x, y, w, h = int(value[0]), int(value[1]), max(1, int(value[2])), max(1, int(value[3]))
                x2, y2 = x + w, y + h
                color = "#00ff87"
                canvas.create_rectangle(x, y, x2, y2, outline=color, width=3)
                text = f"{label}: ({x}, {y}, {w}, {h})"
                tx = max(10, min(screen_w - 10, x + 6))
                ty = max(24, min(screen_h - 10, y - 10))
                text_id = canvas.create_text(
                    tx,
                    ty,
                    text=text,
                    anchor="sw",
                    fill=color,
                    font=("Segoe UI", 13, "bold")
                )
                bbox = canvas.bbox(text_id)
                if bbox:
                    pad = 5
                    bg = canvas.create_rectangle(
                        bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad,
                        fill="#000000", outline=color, width=1
                    )
                    canvas.tag_lower(bg, text_id)
            else:
                x, y = int(value[0]), int(value[1])
                color = "#ffcc00"
                radius = 11
                canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline=color, width=3)
                canvas.create_line(x - 24, y, x + 24, y, fill=color, width=2)
                canvas.create_line(x, y - 24, x, y + 24, fill=color, width=2)
                text = f"{label}: ({x}, {y})"
                tx = max(10, min(screen_w - 10, x + 20))
                ty = max(24, min(screen_h - 10, y - 18))
                text_id = canvas.create_text(
                    tx,
                    ty,
                    text=text,
                    anchor="sw",
                    fill=color,
                    font=("Segoe UI", 13, "bold")
                )
                bbox = canvas.bbox(text_id)
                if bbox:
                    pad = 5
                    bg = canvas.create_rectangle(
                        bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad,
                        fill="#000000", outline=color, width=1
                    )
                    canvas.tag_lower(bg, text_id)

            def _close_overlay(_evt=None):
                self._overlay_window = None
                try:
                    overlay.destroy()
                except Exception:
                    pass

            overlay.bind("<Escape>", _close_overlay)
            overlay.bind("<Button-1>", _close_overlay)
            overlay.after(max(600, int(duration_ms)), _close_overlay)
            overlay.focus_force()
            self._overlay_window = overlay
        except Exception as e:
            try:
                print(f"[CalibrationManager] Failed to render overlay: {e}")
            except Exception:
                pass

    def _render_calibration_overlay_many(self, root, items, duration_ms=2500):
        try:
            valid_items = []
            if isinstance(items, list):
                for item in items:
                    if not isinstance(item, dict):
                        continue
                    value = item.get("value")
                    if not isinstance(value, (list, tuple)) or len(value) < 2:
                        continue
                    label = str(item.get("label", item.get("key", "Calibration")))
                    valid_items.append({"label": label, "value": value})

            if not valid_items:
                return

            self._destroy_overlay()
            overlay = ttk.Toplevel(root)
            overlay.overrideredirect(True)
            overlay.attributes("-topmost", True)
            try:
                overlay.attributes("-alpha", 0.20)
            except Exception:
                pass

            screen_w = overlay.winfo_screenwidth()
            screen_h = overlay.winfo_screenheight()
            overlay.geometry(f"{screen_w}x{screen_h}+0+0")
            overlay.configure(bg="black")

            canvas = ttk.Canvas(overlay, bg="black", highlightthickness=0)
            canvas.pack(fill=tk.BOTH, expand=True)

            title_id = canvas.create_text(
                20, 20,
                text="Fishing Calibrations (all values)",
                anchor="nw",
                fill="#ffffff",
                font=("Segoe UI", 15, "bold")
            )
            title_bbox = canvas.bbox(title_id)
            if title_bbox:
                canvas.create_rectangle(
                    title_bbox[0] - 6, title_bbox[1] - 4, title_bbox[2] + 6, title_bbox[3] + 4,
                    fill="#111111", outline="#dddddd", width=1
                )
                canvas.tag_raise(title_id)

            colors = ["#ffcc00", "#00ff87", "#66b3ff", "#ff77aa", "#c2ff4d", "#ff9f40", "#b794f4"]
            for idx, item in enumerate(valid_items):
                label = item["label"]
                value = item["value"]
                color = colors[idx % len(colors)]
                is_region = len(value) >= 4

                if is_region:
                    x = int(value[0])
                    y = int(value[1])
                    w = max(1, int(value[2]))
                    h = max(1, int(value[3]))
                    x2, y2 = x + w, y + h
                    canvas.create_rectangle(x, y, x2, y2, outline=color, width=3)
                    text = f"{label}: ({x}, {y}, {w}, {h})"
                    tx = max(10, min(screen_w - 10, x + 6))
                    ty = max(24, min(screen_h - 10, y - 10))
                else:
                    x = int(value[0])
                    y = int(value[1])
                    radius = 10
                    canvas.create_oval(x - radius, y - radius, x + radius, y + radius, outline=color, width=3)
                    canvas.create_line(x - 22, y, x + 22, y, fill=color, width=2)
                    canvas.create_line(x, y - 22, x, y + 22, fill=color, width=2)
                    text = f"{label}: ({x}, {y})"
                    tx = max(10, min(screen_w - 10, x + 18))
                    ty = max(24, min(screen_h - 10, y - 16))

                text_id = canvas.create_text(
                    tx,
                    ty,
                    text=text,
                    anchor="sw",
                    fill=color,
                    font=("Segoe UI", 12, "bold")
                )
                bbox = canvas.bbox(text_id)
                if bbox:
                    bg = canvas.create_rectangle(
                        bbox[0] - 4, bbox[1] - 3, bbox[2] + 4, bbox[3] + 3,
                        fill="#000000", outline=color, width=1
                    )
                    canvas.tag_lower(bg, text_id)

            def _close_overlay(_evt=None):
                self._overlay_window = None
                try:
                    overlay.destroy()
                except Exception:
                    pass

            overlay.bind("<Escape>", _close_overlay)
            overlay.bind("<Button-1>", _close_overlay)
            overlay.after(max(700, int(duration_ms)), _close_overlay)
            overlay.focus_force()
            self._overlay_window = overlay
        except Exception as e:
            try:
                print(f"[CalibrationManager] Failed to render multi overlay: {e}")
            except Exception:
                pass

    def _tk_loop(self):
        try:
            import sys as _sys
            if getattr(_sys, 'frozen', False) or getattr(_sys, '__compiled__', False):
                try:
                    _base = _sys._MEIPASS if hasattr(_sys, '_MEIPASS') else os.path.dirname(_sys.executable)
                    for _sub in os.listdir(_base):
                        _full = os.path.join(_base, _sub)
                        if os.path.isdir(_full):
                            _low = _sub.lower()
                            if _low.startswith("tcl") and "TCL_LIBRARY" not in os.environ:
                                os.environ["TCL_LIBRARY"] = _full
                            elif _low.startswith("tk") and "TK_LIBRARY" not in os.environ:
                                os.environ["TK_LIBRARY"] = _full
                except Exception:
                    pass

            root = tk.Tk()
            root.withdraw()
        except Exception as e:
            print(f"[CalibrationManager] FATAL: Failed to create tkinter root: {e}")
            traceback.print_exc()
            return

        def poll():
            try:
                req = self._queue.get_nowait()
                action = req.get("action", "calibrate")
                config_key = req.get("key")

                if action == "display_many":
                    duration_ms = req.get("duration_ms", 2500)
                    items = req.get("items", [])
                    self._render_calibration_overlay_many(root, items, duration_ms=duration_ms)
                    root.after(100, poll)
                    return

                if action == "display":
                    if not config_key:
                        root.after(100, poll)
                        return
                    label = req.get("label", str(config_key))
                    duration_ms = req.get("duration_ms", 2500)
                    value = None
                    try:
                        if self._tracker and hasattr(self._tracker, "config"):
                            value = self._tracker.config.get(config_key)
                    except Exception:
                        value = None
                    self._render_calibration_overlay(root, value, label, duration_ms=duration_ms)
                    root.after(100, poll)
                    return

                if not config_key:
                    root.after(100, poll)
                    return
                window_type = req["type"]

                print(f"[CalibrationManager] Opening snipping widget for '{config_key}'")

                if self._window is not None:
                    try: self._window.hide()
                    except: pass

                def on_snip(region):
                    if window_type == "point":
                        value = [region[0], region[1]]
                    else:
                        value = [region[0], region[1], region[2], region[3]]

                    _is_virtual = config_key.startswith("egg_click_failsafe_")

                    if not _is_virtual and self._tracker and hasattr(self._tracker, 'config'):
                        self._tracker.config[config_key] = value
                        if self._save_fn:
                            self._save_fn(self._tracker.config)

                    if self._window is not None:
                        try: self._window.show()
                        except: pass

                    if self._emit_fn:
                        self._emit_fn({"key": config_key, "value": value})

                try:
                    snipper = SnippingWidget(root, config_key=config_key, callback=on_snip)
                    snipper.start()
                except Exception as e:
                    print(f"[CalibrationManager] Failed to create snipping window: {e}")
                    traceback.print_exc()
                    if self._window is not None:
                        try: self._window.show()
                        except: pass

            except queue.Empty:
                pass
            except Exception as e:
                print(f"[CalibrationManager] Unexpected error in poll: {e}")
                traceback.print_exc()

            root.after(100, poll)

        root.after(100, poll)
        root.mainloop()

class ActionScheduler:
    def __init__(self, owner, worker_name="ActionScheduler"):
        self.owner = owner
        self._pq = queue.PriorityQueue()
        self._counter = itertools.count()
        self._running = True
        self._worker_thread = threading.Thread(target=self._worker, name=worker_name, daemon=True)
        self._worker_thread.start()
        self._action_lock = threading.RLock()
        self._action_active = threading.Event()

    def enqueue_action(self, fn, name=None, priority=5, block=False, timeout=None):
        idx = next(self._counter)
        qname = name or f"action-{idx}"
        self._pq.put((priority, idx, qname, fn))
        if block:
            start = time.time()
            while True:
                with self._action_lock:
                    pass
                if timeout is not None and (time.time() - start) > timeout:
                    break
                time.sleep(0.08)
            return True
        return True

    def _worker(self):
        while self._running:
            try:
                try:
                    priority, idx, name, fn = self._pq.get(timeout=0.7)
                except Exception:
                    continue

                self._action_active.set()
                self._action_lock.acquire()
                try:
                    try:
                        fn()
                    except Exception:
                        try:
                            self.owner.error_logging(
                                sys.exc_info(),
                                f"Error executing scheduled action {name}"
                            )
                        except Exception:
                            pass
                finally:
                    try:
                        self._action_lock.release()
                    except Exception:
                        pass
                    self._action_active.clear()

            except Exception:
                self._action_active.clear()
                try:
                    self._action_lock.release()
                except Exception:
                    pass

    def stop(self):
        self._running = False
        try:
            while not self._pq.empty():
                self._pq.get_nowait()
        except Exception:
            pass
