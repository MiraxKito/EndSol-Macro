from __future__ import annotations

import traceback
import json
import threading
from typing import Optional, Any
import ctypes
import win32gui, win32con, win32api
import webbrowser
import webview
import os
import sys
import re
import time
import psutil
from datetime import datetime, timezone
import logging
import shutil
import urllib.request
import urllib.parse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import socket
import random
from pathlib import Path
from biome_tracker.config import APPDATA_BASE
from biome_tracker.coordinates import apply_calibrations, get_client_rect_screen, record_calibration, enable_dpi_awareness
from biome_tracker import multi_instance

enable_dpi_awareness()
import keyboard

ORIGINAL_ABS_FILE = os.path.abspath(__file__)
os.environ['WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS'] = '--disable-gpu'

# paths crafting_files_do_not_open and macoroni logs go into appdata/local instead of next to the EXE (maybe)
APPDATA_BASE.mkdir(parents=True, exist_ok=True)
LOGS_DIR = APPDATA_BASE / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
os.chdir(APPDATA_BASE)

_mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "EndSolMacroSingleInstance")
if ctypes.windll.kernel32.GetLastError() == 183:  # ERROR_ALREADY_EXISTS
    _old_pid_arg = None
    try:
        if "--endsol-old-pid" in sys.argv:
            _idx = sys.argv.index("--endsol-old-pid")
            if _idx + 1 < len(sys.argv): _old_pid_arg = int(sys.argv[_idx + 1])
    except Exception:
        pass

    if _old_pid_arg is not None:
        for _ in range(90):
            try:
                p = psutil.Process(_old_pid_arg)
                if not p.is_running(): break
                p.wait(timeout=0.5)
            except (psutil.NoSuchProcess, psutil.TimeoutExpired):
                break
            except Exception:
                time.sleep(0.5)

        ctypes.windll.kernel32.CloseHandle(_mutex)
        _mutex = ctypes.windll.kernel32.CreateMutexW(None, True, "EndSolMacroSingleInstance")
        if ctypes.windll.kernel32.GetLastError() == 183:
            ctypes.windll.user32.MessageBoxW(0, "EndSol Macro is already running!\n\nPlease close the existing instance before opening a new one.", "EndSol Macro", 0x30)
            sys.exit(0)
    else:
        ctypes.windll.user32.MessageBoxW(0, "EndSol Macro is already running!\n\nPlease close the existing instance before opening a new one.", "EndSol Macro", 0x30)
        sys.exit(0)

try:
    import numpy
    import pyautogui
except Exception as e:
    err_text = str(e)
    if "numpy" in err_text.lower() or "c-extension" in err_text.lower() or "dll" in err_text.lower():
        msg = (
            "EndSol Macro failed to load required components.\n\n"
            "This is because your computer is missing the standard 'Visual C++ Redistributable (x64)' (i think so).\n\n"
            "Please download and install it from Microsoft's official website and try open the macro again!\n\n"
            f"Error details: {err_text}"
        )
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, msg, "Missing Windows Component", 0x10 | 0x0)
        except Exception:
            pass
        sys.exit(1)
    else:
        raise


# i added this so we can easily change macro version upon releases without having to change multiple back-end & front-end behaviours
# for future people that is reading the open source code, hello :p
current_version = "v1.0.7"
os.environ["ENDSOL_MACRO_VERSION"] = current_version
from biome_tracker.config import GITHUB_RELEASES_API, GITHUB_RAW_BASE
UPDATE_LATEST_RELEASE_API_URL = GITHUB_RELEASES_API
os.environ["ENDSOL_UPDATE_API_URL"] = UPDATE_LATEST_RELEASE_API_URL
os.environ["WEBKIT_DISABLE_COMPOSITING_MODE"] = "1" 

_wv2_user_data_base = os.path.join(
    os.environ.get("LOCALAPPDATA", os.path.expanduser("~")),
    "EndSolMacro", "WebView2UserData"
)
try:
    if os.path.exists(_wv2_user_data_base):
        for _f in os.listdir(_wv2_user_data_base):
            try: shutil.rmtree(os.path.join(_wv2_user_data_base, _f), ignore_errors=True)
            except Exception: pass
except Exception:
    pass

_wv2_user_data = os.path.join(_wv2_user_data_base, f"Session_{int(time.time())}")
os.makedirs(_wv2_user_data, exist_ok=True)
os.environ["WEBVIEW2_USER_DATA_FOLDER"] = _wv2_user_data

try: psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
except Exception: pass

from biome_tracker.config import (
    ensure_workspace_files,
    sync_config,
    load_config,
    save_config,
    normalize_auto_pop_biomes,
)
from biome_tracker.core import BiomeTracker

def get_base_path(): return sys._MEIPASS if hasattr(sys, '_MEIPASS') else os.path.dirname(ORIGINAL_ABS_FILE)


def validate_calibration_values(values, allow_incomplete: bool = True):
    """Validate a calibration payload {key: [x, y] | [x, y, w, h]}.

    Returns (clean_dict, errors): invalid entries are dropped and reported in
    `errors`; with allow_incomplete=False an empty result is an error too.
    Used by the portable calibration profile save/load/import flows.
    """
    errors, clean = [], {}
    if not isinstance(values, dict):
        return {}, ["Calibration payload is not an object."]
    for key, value in values.items():
        if not isinstance(key, str) or not key:
            errors.append(f"Invalid key: {key!r}")
            continue
        if key == "_calibration_meta" and isinstance(value, dict):
            clean[key] = value
            continue
        if not isinstance(value, (list, tuple)) or len(value) not in (2, 4) or not all(
            isinstance(v, (int, float)) and not isinstance(v, bool) for v in value
        ):
            errors.append(f"{key}: expected [x, y] or [x, y, w, h] numbers")
            continue
        coords = [int(v) for v in value]
        if len(coords) == 2:
            if not (0 <= coords[0] <= 20000 and 0 <= coords[1] <= 20000):
                errors.append(f"{key}: coordinates out of range")
                continue
        else:
            if coords[2] <= 0 or coords[3] <= 0 or coords[0] + coords[2] > 20000 or coords[1] + coords[3] > 20000:
                errors.append(f"{key}: invalid region size")
                continue
        clean[key] = coords
    if not allow_incomplete and not clean:
        errors.append("No valid calibration coordinates found.")
    return clean, errors

def _app_icon_path():
    candidates = [
        os.path.join(get_base_path(), "assets", "endsol-macro.ico"),
        os.path.join(os.path.dirname(ORIGINAL_ABS_FILE), "assets", "endsol-macro.ico"),
    ]
    return next((p for p in candidates if os.path.exists(p)), "")

def _apply_native_window_icon_when_ready(title: str):
    """Apply the same ICO to the native Windows window titlebar/taskbar."""
    if os.name != "nt":
        return
    icon_path = _app_icon_path()
    if not icon_path:
        return
    try:
        import win32con
        import win32gui
        import ctypes
        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x00000010
        LR_DEFAULTSIZE = 0x00000040
        WM_SETICON = 0x0080
        ICON_SMALL, ICON_BIG = 0, 1
        hicon = ctypes.windll.user32.LoadImageW(
            0, icon_path, IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE
        )
        if not hicon:
            return
        for _ in range(100):
            hwnd = win32gui.FindWindow(None, title)
            if hwnd:
                win32gui.SendMessage(hwnd, WM_SETICON, ICON_BIG, hicon)
                win32gui.SendMessage(hwnd, WM_SETICON, ICON_SMALL, hicon)
                return
            time.sleep(0.1)
    except Exception as exc:
        print(f"[Icon] Could not apply native window icon: {exc}")

def _get_frontend_dist_dirs() -> list[str]:
    base_path = get_base_path()
    from biome_tracker.config import APPDATA_BASE
    
    # In source mode the project bundle must win over an older cached bundle
    # in %LOCALAPPDATA%\EndSolMacro. Otherwise Start.bat silently keeps
    # showing the previous frontend after source edits/builds.
    dirs = [
        os.path.join(os.getcwd(), "frontend", "dist"),
        os.path.join(os.getcwd(), "dist"),
        os.path.join(str(base_path), "frontend", "dist"),
        os.path.join(str(APPDATA_BASE), "dist"),
        os.path.join(str(APPDATA_BASE), "frontend", "dist"),
    ]
    
    if getattr(sys, "frozen", False):
        dirs.append(os.path.join(base_path, "lib", "dist"))
        dirs.append(os.path.join(base_path, "dist"))
    else:
        dirs.append(os.path.join(base_path, "frontend", "dist"))
        dirs.append(os.path.join(base_path, "lib", "dist"))
        dirs.append(os.path.join(base_path, "dist"))

    return [d for d in dirs if os.path.exists(d)]


_FRONTEND_ENTRY_CACHE = None
_FRONTEND_ENTRY_LOCK = threading.Lock()

def get_frontend_entry():
    """Resolve and read the bundled frontend once per Python process.

    Secondary windows (biome confirmation/recorders) reuse this in-memory
    document. They must not reread the several-hundred-kilobyte bundle or
    fetch/copy it again while the macro is running.
    """
    global _FRONTEND_ENTRY_CACHE
    if _FRONTEND_ENTRY_CACHE is not None:
        return _FRONTEND_ENTRY_CACHE

    with _FRONTEND_ENTRY_LOCK:
        if _FRONTEND_ENTRY_CACHE is not None:
            return _FRONTEND_ENTRY_CACHE

        for dist_dir in _get_frontend_dist_dirs():
            index_file = os.path.join(dist_dir, "index.html")
            if os.path.exists(index_file):
                try:
                    abs_path = os.path.abspath(index_file).replace("\\", "/")
                    with open(index_file, "r", encoding="utf-8") as f:
                        html_content = f.read()
                    _FRONTEND_ENTRY_CACHE = {"html": html_content, "url": f"file:///{abs_path}"}
                    print(f"Loaded frontend once from local: {abs_path}")
                    return _FRONTEND_ENTRY_CACHE
                except Exception as e:
                    print(f"Error reading local index.html: {e}")

        frontend_url = GITHUB_RAW_BASE + "/assets/index.html"
        try:
            from biome_tracker.config import APPDATA_BASE
            appdata_dist = os.path.join(str(APPDATA_BASE), "dist")
            os.makedirs(appdata_dist, exist_ok=True)

            req = urllib.request.Request(frontend_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                html_content = response.read().decode('utf-8')
                if html_content and len(html_content) > 1000:
                    saved_path = os.path.join(appdata_dist, "index.html")
                    with open(saved_path, "w", encoding="utf-8") as f:
                        f.write(html_content)
                    abs_path = os.path.abspath(saved_path).replace("\\", "/")
                    _FRONTEND_ENTRY_CACHE = {"html": html_content, "url": f"file:///{abs_path}"}
                    print(f"Fetched frontend once from GitHub -> saved to: {abs_path}")
                    return _FRONTEND_ENTRY_CACHE
        except Exception as e:
            print(f"Failed to fetch frontend from GitHub: {e}")

        _FRONTEND_ENTRY_CACHE = {"url": "http://localhost:5173"}
        return _FRONTEND_ENTRY_CACHE


def _read_cli_value(flag, default=""):
    try:
        if flag not in sys.argv: return default
        idx = sys.argv.index(flag)
        if idx + 1 >= len(sys.argv): return default
        return str(sys.argv[idx + 1]).strip()
    except Exception:
        return default


def _cfg_bool(cfg, key, default=False):
    try:
        if not isinstance(cfg, dict): return bool(default)
        val = cfg.get(key, default)
        if isinstance(val, str):
            val = val.strip().lower()
            return val in ("1", "true", "yes", "on")
        return bool(val)
    except Exception:
        return bool(default)

class LoggerWriter:
    def __init__(self, filename="macro_logs.txt", original_stream=None):
        self.terminal = original_stream
        # All application stdout/stderr logs belong in the per-user logs dir,
        # never beside the source tree or executable.
        LOGS_DIR.mkdir(parents=True, exist_ok=True)
        self.filename = str(LOGS_DIR / Path(filename).name)

    def write(self, message):
        if self.terminal is not None:
            try:
                self.terminal.write(message)
                self.terminal.flush()
            except UnicodeEncodeError:
                try:
                    self.terminal.write(message.encode("ascii", "replace").decode("ascii"))
                    self.terminal.flush()
                except Exception:
                    pass
            except Exception:
                pass
        try:
            with open(self.filename, "a", encoding="utf-8") as f:
                f.write(message)
        except Exception:
            pass

    def flush(self):
        if self.terminal is not None:
            try:
                self.terminal.flush()
            except Exception:
                pass

sys.stdout = LoggerWriter("macro_logs.txt", sys.stdout)
sys.stderr = LoggerWriter("macro_logs.txt", sys.stderr)

class Api:
    def __init__(self, tracker=None):
        self._tracker = tracker
        self._window = None
        self._calib_mgr = None
        self._pending_calibration_key = None
        self._pending_calibration_mode = None

        # fishing mode stuff
        self._fishing_stop_event = threading.Event()
        self._fishing_thread = None
        self._fishing_lock = threading.Lock()
        self._fishing_runtime_state = {
            "fish_caught_count": 0,
            "fish_caught_since_merchant": 0,
            "fish_caught_since_br_sc": 0,
            "rejoin_in_progress": False,
            "force_sell_on_next_cycle": False,
            "merchant_requires_reset": False,
        }

        # rare biome pop up confirmation
        self._biome_confirm_evt = threading.Event()
        self._biome_confirm_result = None
        self.emergency_port = None

        # Sol's Book items/gauntlets: per-kind throttle state for the
        # background wiki refresh (items / gauntlets).
        self._sol_book_refresh_state = {}

        # Trim the Fandom media cache once at startup: purge leftover .part
        # files and delete oldest entries above the 300 MB cap, so the
        # folder cannot grow unbounded between sessions.
        try:
            self._enforce_media_cache_cap()
        except Exception:
            pass

    def set_window(self, window):
        self._window = window
        if self._calib_mgr is None:
            from biome_tracker.base_support import CalibrationManager
            self._calib_mgr = CalibrationManager()
        self._calib_mgr.set_refs(
            window=window,
            tracker=self._tracker,
            save_fn=save_config,
            emit_fn=self.emit_calibration_result
        )

    # ---- External MultipleRobloxInstances integration -------------------
    def get_multi_instance_state(self):
        return multi_instance.state()

    def set_multi_instance_enabled(self, enabled):
        enabled = bool(enabled)
        print(f"[MultiInstance] set_multi_instance_enabled({enabled})", flush=True)
        cfg = self.get_config()
        if isinstance(cfg, dict):
            cfg["multiple_instances_enabled"] = enabled
            save_config(cfg)
        if self._tracker and isinstance(getattr(self._tracker, "config", None), dict):
            self._tracker.config["multiple_instances_enabled"] = enabled
            multi_instance.attach_tracker(self._tracker)
        # Just save the preference — do NOT start/stop the idle loop here.
        # The loop starts/stops with the macro cycle (set_biome_detection).
        multi_instance.set_enabled(enabled, self._tracker)
        return {"success": True, "enabled": enabled}

    def reset_stats(self):
        """Reset user statistics: biomes, merchants, auras, session time."""
        cfg = self.get_config()
        if not isinstance(cfg, dict):
            return {"success": False, "error": "Config is not loaded"}
        for key in ("biome_counts", "merchant_counts", "aura_counts", "merchants_found"):
            cfg[key] = {}
        for key in ("total_fish_caught", "total_auras_detected", "total_biomes_found",
                    "jester_exchange_count"):
            cfg[key] = 0
        cfg["session_time"] = "0:00:00"
        # Reset the live tracker state too, otherwise the next periodic save
        # resurrects the old counters (save_config writes tracker objects).
        t = self._tracker
        if t:
            if isinstance(getattr(t, "biome_counts", None), dict):
                t.biome_counts.clear()
            if isinstance(getattr(t, "merchant_counts", None), dict):
                t.merchant_counts.clear()
            t.saved_session = 0
        try:
            save_config(cfg)
        except Exception as e:
            return {"success": False, "error": str(e)}
        self._emit_stats_update()
        print("[Stats] User statistics reset via panel.", flush=True)
        return {"success": True}

    def get_config(self):
        t = self._tracker
        if t and isinstance(getattr(t, 'config', None), dict) and t.config:
            return t.config
        return load_config()

    def get_biome_data(self):
        if self._tracker and isinstance(getattr(self._tracker, "biome_data", None), dict):
            result = {}
            for biome, data in self._tracker.biome_data.items():
                color = data.get("color", "0xffffff")
                if isinstance(color, str) and color.startswith("0x"): color = "#" + color[2:]
                result[biome] = color
            return result
        return {}

    def get_full_biome_data(self):
        if self._tracker:
            data = getattr(self._tracker, "biome_data", None)
            if not isinstance(data, dict) or not data:
                try: data = self._tracker.load_biome_data()
                except Exception: data = {}
            if isinstance(data, dict):
                # Defensive: TIME is not a detectable biome and never renders.
                return {k: v for k, v in data.items() if k.strip().upper() != "TIME"}
            return {}
        return {}

    def get_data_source_status(self):
        if self._tracker:
            return {
                "biome": getattr(self._tracker, "_biome_source_status", {"source": "unknown", "reachable": False, "error": "Not loaded"}),
                "aura": getattr(self._tracker, "_aura_source_status", {"source": "unknown", "reachable": False, "error": "Not loaded"}),
            }
        return {"biome": {"source": "unknown", "reachable": False, "error": "Tracker unavailable"}, "aura": {"source": "unknown", "reachable": False, "error": "Tracker unavailable"}}

    def get_biome_source_status(self):
        return self.get_data_source_status()["biome"]

    def get_aura_detail(self, aura_name):
        if self._tracker and hasattr(self._tracker, "load_fandom_aura_detail"):
            return self._tracker.load_fandom_aura_detail(aura_name)
        return {"error": "Tracker unavailable"}

    def get_biome_detail(self, biome_name):
        """Fandom gallery + music for a biome (same pipeline as aura media)."""
        if self._tracker and hasattr(self._tracker, "load_fandom_biome_detail"):
            return self._tracker.load_fandom_biome_detail(biome_name)
        return {"error": "Tracker unavailable"}

    # ── Media cache & download (Sol's Book) ─────────────────────────────
    # Root cause of videos/music failing inside the WebView: Fandom's CDN
    # (Cloudflare) 403-challenges media requests that carry no Referer —
    # and a file:// page cannot send one for <video>/<audio>. Python CAN
    # pass with browser-like headers (verified: 206 for .mp4), so media is
    # fetched here into a local cache and played back as a local file.
    _MEDIA_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                 "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0")
    # 300 MB LRU cap: enough for a browsing session of aura videos/music,
    # small enough not to bloat the local folder. Everything above the cap
    # is deleted oldest-first, also once at every app startup.
    _MEDIA_CACHE_MAX_BYTES = 300 * 1024 * 1024  # 300 MB LRU cap
    _media_download_lock = threading.Lock()

    def _media_cache_dir(self):
        d = Path(str(APPDATA_BASE)) / "media_cache"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _media_ext(url: str) -> str:
        try:
            raw = urllib.parse.unquote(str(url))
            # Matches "Name.mp4/revision/latest", "Name.ogg?cb=", "Name.mp3".
            m = re.search(r"(\.(?:mp4|webm|mov|ogv|ogg|oga|mp3|wav|gif|jpg|jpeg|png|webp))(?:/revision|[?#]|$)", raw, re.I)
            return m.group(1).lower() if m else ".bin"
        except Exception:
            return ".bin"

    def _media_local_path(self, url: str):
        import hashlib
        key = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return self._media_cache_dir() / (key + self._media_ext(url))

    def _resolve_media_url(self, url: str) -> str:
        """Resolve Special:FilePath links to the direct CDN URL.

        The wiki-host redirect itself is Cloudflare-challenged for
        python-requests, but api.php imageinfo is not — the resolved
        static.wikia URL downloads fine with browser headers (verified 206).
        """
        if "Special:FilePath/" not in url:
            return url
        try:
            name = urllib.parse.unquote(url.split("Special:FilePath/", 1)[1].split("?")[0])
            params = {"action": "query", "titles": "File:" + name.replace("_", " "),
                      "prop": "imageinfo", "iiprop": "url", "format": "json", "formatversion": "2"}
            from biome_tracker.base_support import fandom_get
            resp = fandom_get("https://sol-rng.fandom.com/api.php?" + urllib.parse.urlencode(params), timeout=20)
            if resp is not None and resp.ok:
                data = resp.json()
                for p in ((data or {}).get("query") or {}).get("pages") or []:
                    ii = (p.get("imageinfo") or [{}])[0]
                    if ii.get("url"):
                        return str(ii["url"])
        except Exception as e:
            try:
                print(f"[MediaCache] Resolve failed, using original URL: {e}")
            except Exception:
                pass
        return url

    def _fetch_media_to(self, url: str, dest: Path, referer: str = "https://sol-rng.fandom.com/wiki/Auras") -> dict:
        """Stream a Fandom media file to dest with browser-like headers.

        fandom_get adds process-wide pacing and 429 handling; the browser
        header set (Referer + client hints) is what gets past the CDN
        challenge that blocks the WebView's own media requests.
        """
        headers = {
            "User-Agent": self._MEDIA_UA,
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": referer,
            "sec-ch-ua": '"Chromium";v="128", "Not;A=Brand";v="24", "Microsoft Edge";v="128"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        from biome_tracker.base_support import fandom_get
        try:
            resp = fandom_get(url, timeout=(15, 120), retries=2, stream=True, headers=headers)
        except Exception as e:
            return {"success": False, "error": f"Network error: {e}"}
        if resp is None:
            return {"success": False, "error": "Media request failed (network)"}
        if resp.status_code not in (200, 206):
            return {"success": False, "error": f"CDN refused the download (HTTP {resp.status_code})"}
        try:
            total = int(resp.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            total = 0
        if total > 1024 * 1024 * 1024:
            return {"success": False, "error": "File is too large"}
        tmp = dest.with_suffix(dest.suffix + ".part")
        got = 0
        try:
            with open(tmp, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 512):
                    if not chunk:
                        continue
                    got += len(chunk)
                    if got > 1024 * 1024 * 1024:
                        raise ValueError("File is too large")
                    f.write(chunk)
            if got == 0:
                return {"success": False, "error": "Empty response"}
            os.replace(str(tmp), str(dest))
            return {"success": True, "size": got}
        except Exception as e:
            try:
                tmp.unlink(missing_ok=True)
            except Exception:
                pass
            return {"success": False, "error": f"Save failed: {e}"}
        finally:
            try:
                resp.close()
            except Exception:
                pass

    def _enforce_media_cache_cap(self):
        try:
            self._media_cache_dir()
            # Purge abandoned partial downloads from crashed/finished runs
            # before measuring the total size.
            for p in self._media_cache_dir().glob("*.part"):
                try:
                    p.unlink()
                except Exception:
                    pass
            entries = [(p.stat().st_mtime, p.stat().st_size, p)
                       for p in self._media_cache_dir().iterdir() if p.is_file()]
        except Exception:
            return
        total = sum(size for _, size, _ in entries)
        if total <= self._MEDIA_CACHE_MAX_BYTES:
            return
        for mtime, size, p in sorted(entries):
            if total <= self._MEDIA_CACHE_MAX_BYTES:
                break
            try:
                total -= size
                p.unlink()
            except Exception:
                continue

    def ensure_media_cached(self, url):
        """Download a Fandom media file into the local cache and return a
        file:// URL the WebView can play reliably (local = no CDN challenges)."""
        url = str(url or "").strip()
        try:
            from biome_tracker.base_support import _is_fandom_url
            if not url or not _is_fandom_url(url):
                return {"success": False, "error": "Not a Fandom media URL"}
            url = self._resolve_media_url(url)
            dest = self._media_local_path(url)
            if dest.exists() and dest.stat().st_size > 0:
                return {"success": True, "cached": True, "size": dest.stat().st_size,
                        "path": str(dest), "local_url": dest.as_uri()}
            with self._media_download_lock:
                # Double-check after acquiring: another thread may have it.
                if dest.exists() and dest.stat().st_size > 0:
                    return {"success": True, "cached": True, "size": dest.stat().st_size,
                            "path": str(dest), "local_url": dest.as_uri()}
                res = self._fetch_media_to(url, dest)
            if not res.get("success"):
                return res
            self._enforce_media_cache_cap()
            return {"success": True, "cached": False, "size": res.get("size", 0),
                    "path": str(dest), "local_url": dest.as_uri()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def ensure_media_thumbnail(self, url, max_dim=288):
        """Static downscaled preview for grids/lists/galleries.

        Root cause of the FPS drops while browsing Sol's Book media: the
        thumbnail strips and galleries rendered the FULL obtainment GIFs
        (several MB, dozens of frames) side by side, and WebView2 kept
        compositing every animation at once. The fix: lists get a small
        static PNG (first frame for GIFs) generated once per file; the
        full animation is only loaded in the main viewer.
        """
        base = {}
        try:
            base = self.ensure_media_cached(url) or {}
            if not base.get("success"):
                return base
            src = Path(base["path"])
            if src.suffix.lower() not in (".gif", ".png", ".jpg", ".jpeg", ".webp"):
                return base  # videos/audio have no thumbnail
            try:
                max_dim = max(64, min(int(max_dim or 288), 512))
            except Exception:
                max_dim = 288
            thumb = src.with_name(src.stem + f"_t{max_dim}.png")
            if not thumb.exists() or thumb.stat().st_size <= 0:
                from PIL import Image
                with Image.open(str(src)) as im:
                    try:
                        im.seek(0)  # first frame for animated sources
                    except Exception:
                        pass
                    frame = im.convert("RGBA")
                    w, h = frame.size
                    scale = min(1.0, max_dim / float(max(w, h)))
                    if scale < 1.0:
                        frame = frame.resize(
                            (max(1, int(w * scale)), max(1, int(h * scale))),
                            Image.LANCZOS,
                        )
                    tmp = thumb.with_name(thumb.name + ".part")
                    frame.save(str(tmp), "PNG")
                os.replace(str(tmp), str(thumb))
            return {"success": True, "cached": True, "path": str(thumb),
                    "local_url": thumb.as_uri(), "full_url": base.get("local_url")}
        except Exception as e:
            # Any thumbnail failure falls back to the full cached file.
            if base.get("success") and base.get("local_url"):
                return base
            return {"success": False, "error": str(e)}

    def ensure_media_preview(self, url, max_dim=288):
        """Backward-compatible alias — some UI builds call the preview name."""
        return self.ensure_media_thumbnail(url, max_dim=max_dim)

    def download_media(self, url, filename=""):
        """Save a Fandom media file via a Save-As dialog (works where the
        WebView's built-in cross-origin download button silently does nothing)."""
        url = str(url or "").strip()
        try:
            from biome_tracker.base_support import _is_fandom_url
            if not url or not _is_fandom_url(url):
                return {"success": False, "error": "Not a Fandom media URL"}

            # Resolve the source file (cache first, then CDN).
            cached = self.ensure_media_cached(url)
            src = None
            if cached.get("success") and cached.get("path"):
                src = Path(cached["path"])
            if src is None or not src.exists():
                return {"success": False, "error": cached.get("error") or "Could not fetch the media file"}

            ext = src.suffix or self._media_ext(url)
            suggested = re.sub(r"[^\w\-. ()\[\]]+", "_", str(filename or "").strip()) or ("media" + ext)
            if not suggested.lower().endswith(ext):
                suggested += ext

            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            try:
                root.attributes("-topmost", True)
            except Exception:
                pass
            try:
                chosen = filedialog.asksaveasfilename(
                    title="Save media file",
                    defaultextension=ext,
                    initialfile=suggested,
                    filetypes=[("Media file", "*" + ext), ("All files", "*.*")],
                )
            finally:
                root.destroy()
            if not chosen:
                return {"success": False, "cancelled": True, "error": "Save cancelled"}
            shutil.copyfile(str(src), chosen)
            return {"success": True, "path": chosen}
        except Exception as e:
            return {"success": False, "error": str(e)}


    def run_memory_match_now(self):
        """Manual Memory Match run for testing — ignores the 12h cooldown."""
        tracker = self._tracker
        if not tracker:
            return {"ok": False, "error": "Tracker not available"}
        if not getattr(tracker, "detection_running", False):
            return {"ok": False, "error": "Start the macro first"}
        if not tracker.mm_is_enabled():
            return {"ok": False, "error": "Enable Memory Match first"}
        if getattr(tracker, "_mm_session_active", False):
            return {"ok": False, "error": "A Memory Match session is already running"}
        import threading as _th

        def _run():
            try:
                res = tracker.play_memory_match()
                try:
                    tracker.append_log(f"[MemoryMatch] Manual run finished: {res}")
                except Exception:
                    pass
            except Exception as e:
                try:
                    tracker.error_logging(e, "manual memory match run")
                except Exception:
                    pass

        _th.Thread(target=_run, daemon=True).start()
        return {"ok": True}

    def get_full_item_data(self):
        """Items dataset for Sol's Book: verified offline snapshot first,
        then the live-refreshed cache; triggers a background wiki refresh
        when the auto-update setting is on and the cache is stale."""
        data = self._sol_book_cached("items") or self._sol_book_bundled("items")
        self._maybe_refresh_sol_book("items")
        return data

    def get_full_gauntlet_data(self):
        """Gauntlets dataset for Sol's Book (same rules as items)."""
        data = self._sol_book_cached("gauntlets") or self._sol_book_bundled("gauntlets")
        self._maybe_refresh_sol_book("gauntlets")
        return data

    # ── Sol's Book items/gauntlets: offline snapshot + live refresh ─────
    # The offline snapshots (biome_tracker/items_fandom.json,
    # biome_tracker/gauntlets_fandom.json) are the verified source of truth.
    # The wiki pipeline (biome_tracker/sol_book_data.py) refreshes a cache
    # copy in the background; a failed or rejected refresh NEVER touches the
    # offline files, and error responses are never cached.
    _SOL_BOOK_REFRESH_INTERVAL = 12 * 3600  # s between wiki refreshes

    def _sol_book_bundled(self, kind):
        import sys as _sys
        base = _sys._MEIPASS if hasattr(_sys, "_MEIPASS") else os.path.dirname(os.path.abspath(__file__))
        path = os.path.join(base, "biome_tracker", f"{kind}_fandom.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                return data
        except Exception:
            pass
        return {}

    def _sol_book_cached(self, kind):
        try:
            path = APPDATA_BASE / "cache" / f"{kind}_fandom.json"
            if path.is_file():
                data = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(data, dict) and data and self._sol_book_records_valid(data, kind):
                    return data
        except Exception:
            pass
        return {}

    def _sol_book_records_valid(self, data, kind):
        try:
            from biome_tracker import sol_book_data as _sbd
        except Exception:
            return False
        try:
            ok, _reason = _sbd.validate_records(data, kind)
        except Exception:
            return False
        return ok

    def _maybe_refresh_sol_book(self, kind):
        try:
            cfg = self.get_config()
            if isinstance(cfg, dict) and cfg.get("auto_update_biome_aura_data") is False:
                return
            now = time.time()
            if now - self._sol_book_refresh_state.get(kind, 0.0) < self._SOL_BOOK_REFRESH_INTERVAL:
                return
            cache_path = APPDATA_BASE / "cache" / f"{kind}_fandom.json"
            try:
                mtime = cache_path.stat().st_mtime if cache_path.is_file() else 0
            except Exception:
                mtime = 0
            if now - mtime < self._SOL_BOOK_REFRESH_INTERVAL:
                return
            self._sol_book_refresh_state[kind] = now
            threading.Thread(target=self._refresh_sol_book_task, args=(kind,), daemon=True).start()
        except Exception:
            pass

    def _refresh_sol_book_task(self, kind):
        try:
            from biome_tracker import sol_book_data as _sbd

            def _log(msg):
                try:
                    print(msg, flush=True)
                except Exception:
                    pass

            current = self._sol_book_cached(kind) or self._sol_book_bundled(kind)
            if kind == "items":
                fresh, dropped = _sbd.refresh_items(current=current, progress=_log)
            else:
                fresh = _sbd.refresh_gauntlets(current=current, progress=_log)
                dropped = []
            if fresh is None:
                _log(f"[SolBook] {kind}: wiki unavailable or refresh rejected — offline dataset kept")
                return
            cache_dir = APPDATA_BASE / "cache"
            cache_dir.mkdir(parents=True, exist_ok=True)
            tmp = cache_dir / f"{kind}_fandom.json.tmp"
            tmp.write_text(json.dumps(fresh, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(str(tmp), str(cache_dir / f"{kind}_fandom.json"))
            _log(
                f"[SolBook] {kind}: refreshed from Fandom ({len(fresh)} records"
                + (f", dropped: {', '.join(dropped)}" if dropped else "")
                + ")"
            )
        except Exception as e:
            # allow a retry on the next Sol's Book open
            try:
                self._sol_book_refresh_state[kind] = 0.0
            except Exception:
                pass
            print(f"[SolBook] {kind} refresh failed: {e}", flush=True)

    def get_item_detail(self, item_name):
        """Live wiki detail for one item (analog of get_aura_detail)."""
        try:
            from biome_tracker import sol_book_data as _sbd
        except Exception:
            return {"error": "sol_book_data unavailable"}
        current = (self.get_full_item_data() or {}).get(str(item_name)) or {}
        return _sbd.load_item_detail(item_name, current=current)

    def get_gauntlet_detail(self, gauntlet_name):
        """Live wiki detail for one gauntlet/lantern/talisman."""
        try:
            from biome_tracker import sol_book_data as _sbd
        except Exception:
            return {"error": "sol_book_data unavailable"}
        current = (self.get_full_gauntlet_data() or {}).get(str(gauntlet_name)) or {}
        return _sbd.load_gauntlet_detail(gauntlet_name, current=current)

    def get_full_aura_data(self):
        if self._tracker:
            data = getattr(self._tracker, "auras_data", None)
            if not isinstance(data, dict) or not data:
                try: data = self._tracker.load_auras_json()
                except Exception: data = {}
            return data if isinstance(data, dict) else {}
        return {}

    def open_appdata(self):
        try:
            os.startfile(str(APPDATA_BASE))
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Extras (v1.0.7): schedule, profiles, logs ──────────────────────
    def get_feature_schedule(self):
        try:
            if not self._tracker:
                return {"success": False, "error": "Tracker not available"}
            return {"success": True, **self._tracker.feature_schedule()}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _profiles_dir(self):
        d = APPDATA_BASE / "profiles"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def list_config_profiles(self):
        try:
            names = sorted(p.stem for p in self._profiles_dir().glob("*.json"))
            return {"success": True, "profiles": names}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_config_profile(self, name):
        try:
            safe = re.sub(r"[^\w\-. ]+", "_", str(name or "").strip())[:60]
            if not safe:
                return {"success": False, "error": "Profile name is empty"}
            cfg = self.get_config()
            if not isinstance(cfg, dict):
                return {"success": False, "error": "Config is not available"}
            payload = {
                "format": "EndSolMacroProfile",
                "version": 1,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "config": cfg,
            }
            path = self._profiles_dir() / (safe + ".json")
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"success": True, "name": safe, "path": str(path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_config_profile(self, name):
        try:
            safe = re.sub(r"[^\w\-. ]+", "_", str(name or "").strip())[:60]
            path = self._profiles_dir() / (safe + ".json")
            if path.exists():
                path.unlink()
                return {"success": True, "name": safe}
            return {"success": False, "error": f"Profile '{safe}' not found"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_config_profile(self, name):
        try:
            safe = re.sub(r"[^\w\-. ]+", "_", str(name or "").strip())[:60]
            path = self._profiles_dir() / (safe + ".json")
            if not path.exists():
                return {"success": False, "error": f"Profile '{safe}' not found"}
            payload = json.loads(path.read_text(encoding="utf-8"))
            cfg = payload.get("config") if isinstance(payload, dict) else None
            if not isinstance(cfg, dict):
                return {"success": False, "error": "This is not an EndSol profile file."}
            if self._tracker and isinstance(getattr(self._tracker, "config", None), dict):
                self._tracker.config.update(cfg)
            save_config(cfg)
            return {"success": True, "name": safe, "count": len(cfg)}
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid profile JSON file."}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def clear_logs(self):
        """Archive and truncate the macro and error logs."""
        try:
            import shutil as _shutil
            logs_dir = APPDATA_BASE / "logs"
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cleared = []
            for name in ("macro_logs.txt", "error_logs.txt"):
                log_file = logs_dir / name
                if log_file.exists():
                    try:
                        _shutil.copyfile(str(log_file), str(logs_dir / f"{log_file.stem}_{stamp}{log_file.suffix}"))
                    except Exception:
                        pass
                    log_file.write_text("", encoding="utf-8")
                    cleared.append(name)
            return {"success": True, "cleared": cleared}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_config(self, config_data):
        prev_anti_afk = False
        if self._tracker and isinstance(getattr(self._tracker, "config", None), dict):
            prev_anti_afk = bool(self._tracker.config.get("anti_afk", False))

        cfg = dict(config_data) if isinstance(config_data, dict) else dict(self.get_config())

        raw_urls = cfg.get("webhook_url") or cfg.get("webhook_urls") or []
        if isinstance(raw_urls, str):
            try:
                parsed_urls = json.loads(raw_urls) if raw_urls.strip().startswith("[") else [raw_urls]
            except Exception:
                parsed_urls = [raw_urls]
        else:
            parsed_urls = raw_urls if isinstance(raw_urls, list) else []
        parsed_urls = [str(url).strip() for url in parsed_urls if str(url).strip()]
        cfg["webhook_url"] = parsed_urls
        cfg["webhook_urls"] = parsed_urls

        # normalize auto pop biomes with whatever biome list we have
        biome_names = []
        if self._tracker and isinstance(getattr(self._tracker, "biome_data", None), dict):
            biome_names = list(self._tracker.biome_data.keys())
        cfg["auto_pop_biomes"] = normalize_auto_pop_biomes(cfg, biome_names=biome_names)


        if _cfg_bool(cfg, "fishing_failsafe_rejoin") and not _cfg_bool(cfg, "auto_reconnect"):
            cfg["fishing_failsafe_rejoin"] = False

        save_config(cfg)
        if self._tracker:
            if not isinstance(getattr(self._tracker, "config", None), dict):
                self._tracker.config = {}
            self._tracker.config.update(cfg)

            # sync webhook urls to the tracker
            if 'webhook_url' in cfg or 'webhook_urls' in cfg:
                self._tracker.webhook_urls = list(cfg.get('webhook_url') or cfg.get('webhook_urls') or [])
                try:
                    if hasattr(self._tracker, "refresh_active_webhook_channels"):
                        self._tracker.refresh_active_webhook_channels(force=True)
                except Exception:
                    pass

            if self._tracker.detection_running:
                # hot-swap fishing mode
                if self._is_fishing_mode_enabled():
                    self._start_fishing_worker()
                else:
                    self._stop_fishing_worker()

                if not prev_anti_afk and self._tracker.config.get("anti_afk", False):
                    try:
                        threading.Thread(target=self._tracker.perform_anti_afk_action, daemon=True).start()
                    except Exception:
                        pass

    def import_config(self):
        try:
            if not self._window:
                return {"success": False, "error": "Window not available"}

            result = self._window.create_file_dialog(
                webview.FileDialog.OPEN, allow_multiple=False,
                file_types=("JSON Files (*.json)",),
            )
            if not result:
                return {"success": False, "error": "No file selected"}

            path = result[0] if isinstance(result, (list, tuple)) else result
            with open(path, "r", encoding="utf-8") as f:
                imported = json.loads(f.read())
            if not isinstance(imported, dict):
                return {"success": False, "error": "Invalid config file: must be a JSON object"}

            save_config(imported)

            if self._tracker:
                if not isinstance(getattr(self._tracker, "config", None), dict):
                    self._tracker.config = {}
                self._tracker.config.update(imported)
                if 'webhook_url' in imported:
                    self._tracker.webhook_urls = imported['webhook_url']
                try:
                    if hasattr(self._tracker, "refresh_active_webhook_channels"):
                        self._tracker.refresh_active_webhook_channels(force=True)
                except Exception: pass

            return {"success": True, "config": imported}
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid JSON file"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def close_window(self):
        self._stop_fishing_worker()
        if self._window:
            try:
                self._window.destroy()
            except Exception:
                pass
        
        def delayed_exit():
            time.sleep(1.5)
            os._exit(0)
        threading.Thread(target=delayed_exit, daemon=True).start()
        return {"success": True}

    def minimize_window(self):
        if self._window:
            self._window.minimize()

    def toggle_maximize_window(self):
        if self._window:
            self._window.toggle_fullscreen()

    def set_always_on_top(self, enabled: bool):
        if self._window:
            try:
                hwnd = None
                if hasattr(self._window.gui, 'hwnd'):
                     hwnd = self._window.gui.hwnd
                else:
                     hwnd = win32gui.FindWindow(None, self._window.title)
                     
                if hwnd:
                     flag = win32con.HWND_TOPMOST if enabled else win32con.HWND_NOTOPMOST
                     win32gui.SetWindowPos(hwnd, flag, 0, 0, 0, 0,
                                           win32con.SWP_NOMOVE | win32con.SWP_NOSIZE)
            except Exception as e:
                print(f"Failed to set always on top via win32gui: {e}")
                self._window.on_top = enabled

    def open_url(self, url: str):
        webbrowser.open(url)

    def get_macro_status(self):
        if self._tracker and getattr(self._tracker, 'detection_running', False):
            return "RUNNING"
        return "STOPPED"

    def get_macro_version(self):
        return current_version

    def _setup_emergency_server(self):
        class SafeModeHandler(BaseHTTPRequestHandler):
            api = self

            def do_GET(self):
                if self.path == "/health":
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(b"OK")
                else:
                    # Serve files from any valid dist directory
                    file_path = self.path.split('?')[0].lstrip('/')
                    if not file_path or file_path == 'index.html':
                        file_path = 'index.html'
                    
                    found_full_path = None
                    for dist_dir in _get_frontend_dist_dirs():
                        full_path = os.path.join(dist_dir, file_path)
                        if os.path.exists(full_path) and os.path.isfile(full_path):
                            found_full_path = full_path
                            break
                    
                    if found_full_path:
                        self.send_response(200)
                        if file_path.endswith('.js'): self.send_header('Content-type', 'application/javascript')
                        elif file_path.endswith('.css'): self.send_header('Content-type', 'text/css')
                        elif file_path.endswith('.html'): self.send_header('Content-type', 'text/html')
                        self.end_headers()
                        with open(found_full_path, 'rb') as f:
                            self.wfile.write(f.read())
                    else:
                        self.send_response(404)
                        self.end_headers()

            def do_POST(self):
                if self.path.startswith("/api/"):
                    method_name = self.path.replace("/api/", "")
                    content_length = int(self.headers['Content-Length'])
                    post_data = self.rfile.read(content_length)
                    try:
                        args = json.loads(post_data) if post_data else []
                    except:
                        args = []
                    
                    method = getattr(self.api, method_name, None)
                    if method and callable(method):
                        try:
                            if isinstance(args, list): result = method(*args)
                            elif isinstance(args, dict): result = method(**args)
                            else: result = method()
                            
                            self.send_response(200)
                            self.send_header('Content-type', 'application/json')
                            self.send_header('Access-Control-Allow-Origin', '*')
                            self.end_headers()
                            self.wfile.write(json.dumps(result).encode())
                        except Exception as e:
                            self.send_response(500)
                            self.end_headers()
                            self.wfile.write(str(e).encode())
                
            def do_OPTIONS(self):
                self.send_response(200)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
                self.send_header('Access-Control-Allow-Headers', 'Content-Type')
                self.end_headers()

            def log_message(self, format, *args): pass

        self.emergency_port = random.randint(18000, 19000)
        def _run():
            try:
                server = ThreadingHTTPServer(('127.0.0.1', self.emergency_port), SafeModeHandler)
                print(f"Browser mode running on http://127.0.0.1:{self.emergency_port}")
                server.serve_forever()
            except Exception as e:
                print(f"Server failed: {e}")

        threading.Thread(target=_run, daemon=True).start()

    def _setup_emergency_hotkey(self):
        def trigger():
            print("Emergency UI Triggered! Hiding main window...")
            if hasattr(self, '_window') and self._window:
                try:
                    self._window.hide()
                    print("Main window hidden.")
                except Exception as e:
                    print(f"Note: Could not hide window: {e}")

            url = f"http://127.0.0.1:{self.emergency_port}/index.html?safe_mode=1"
            webbrowser.open(url)
            print(f"Emergency UI opened in browser: {url}")

        # The ``keyboard`` package installs a global low-level hook. Even with
        # one hotkey that hook can add latency to key-down/key-up delivery on
        # some systems. Use the Windows message-based hotkey API instead; it
        # does not intercept or suppress ordinary keyboard input.
        if os.name != "nt":
            return
        def _native_hotkey_loop():
            try:
                from ctypes import wintypes
                MOD_CONTROL = 0x0002
                MOD_SHIFT = 0x0004
                VK_F10 = 0x79
                HOTKEY_ID = 0x454E44
                user32 = ctypes.windll.user32
                if not user32.RegisterHotKey(None, HOTKEY_ID, MOD_CONTROL | MOD_SHIFT, VK_F10):
                    print("[Hotkey] Native emergency hotkey registration failed; no global keyboard hook installed.")
                    return
                msg = wintypes.MSG()
                try:
                    while True:
                        result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
                        if result <= 0:
                            break
                        if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:
                            trigger()
                finally:
                    user32.UnregisterHotKey(None, HOTKEY_ID)
            except Exception as e:
                print(f"[Hotkey] Native emergency hotkey unavailable: {e}")
        threading.Thread(target=_native_hotkey_loop, name="NativeEmergencyHotkey", daemon=True).start()

    def get_active_modules(self):
        if not self._tracker: return {}
        t = self._tracker
        cfg = t.config
        
        modules = {}
        det = t.detection_running
        
        categories = {
            "Core Features": {
                "Biome Detection": {"active": det, "enabled": True},
                "Aura Detection": {"active": det and _cfg_bool(cfg, "enable_aura_detection"), "enabled": _cfg_bool(cfg, "enable_aura_detection")},
                "Macro Idle Mode": {"active": _cfg_bool(cfg, "enable_idle_mode"), "enabled": _cfg_bool(cfg, "enable_idle_mode")},
                "Anti-AFK": {"active": det and _cfg_bool(cfg, "anti_afk", True), "enabled": _cfg_bool(cfg, "anti_afk", True)},
                "Auto Reconnect": {"active": det and _cfg_bool(cfg, "auto_reconnect"), "enabled": _cfg_bool(cfg, "auto_reconnect")},
                "OCR Failsafe": {"active": det and _cfg_bool(cfg, "enable_ocr_failsafe"), "enabled": _cfg_bool(cfg, "enable_ocr_failsafe")},
                "Remote Control (Discord)": {"active": bool(getattr(t, "_remote_bot_running", False)), "enabled": _cfg_bool(cfg, "remote_access_enabled")},
                "Player Logger": {"active": det and _cfg_bool(cfg, "player_logger", True), "enabled": _cfg_bool(cfg, "player_logger", True)},
                "Discord Webhooks": {"active": det and bool(getattr(t, "webhook_urls", [])), "enabled": bool(getattr(t, "webhook_urls", []))},
                "Auto Start on Idle": {"active": det and _cfg_bool(cfg, "auto_start_on_idle"), "enabled": _cfg_bool(cfg, "auto_start_on_idle")},
                "Rare Biome Confirmation Popup": {"active": det and _cfg_bool(cfg, "rare_biome_confirmation_popup"), "enabled": _cfg_bool(cfg, "rare_biome_confirmation_popup")},
            },
            "Fishing": {
                "Fishing Mode": {"active": det and self._is_fishing_mode_enabled(), "enabled": _cfg_bool(cfg, "fishing_mode")},
                "Fishing Selling": {"active": _cfg_bool(cfg, "fishing_enable_selling") and _cfg_bool(cfg, "fishing_mode"), "enabled": _cfg_bool(cfg, "fishing_enable_selling")},
                "Fishing Failsafe (rejoin)": {"active": _cfg_bool(cfg, "fishing_failsafe_rejoin") and _cfg_bool(cfg, "fishing_mode"), "enabled": _cfg_bool(cfg, "fishing_failsafe_rejoin")},
                "Fishing UI Nav Close": {"active": _cfg_bool(cfg, "fishing_ui_nav_close") and _cfg_bool(cfg, "fishing_mode"), "enabled": _cfg_bool(cfg, "fishing_ui_nav_close")},
                "Fishing Aura Equip": {"active": _cfg_bool(cfg, "fishing_equip_aura_before_movement") and _cfg_bool(cfg, "fishing_mode"), "enabled": _cfg_bool(cfg, "fishing_equip_aura_before_movement")},
                "Fishing Merchant Every X": {"active": _cfg_bool(cfg, "fishing_use_merchant_every_x_fish") and _cfg_bool(cfg, "fishing_mode"), "enabled": _cfg_bool(cfg, "fishing_use_merchant_every_x_fish")},
                "Fishing BR/SC Every X": {"active": _cfg_bool(cfg, "fishing_use_br_sc_every_x_fish") and _cfg_bool(cfg, "fishing_mode"), "enabled": _cfg_bool(cfg, "fishing_use_br_sc_every_x_fish")},
            },
            "Mini-Games & Quests": {
                "Memory Match": {"active": det and _cfg_bool(cfg, "memory_match_enabled"), "enabled": _cfg_bool(cfg, "memory_match_enabled")},
                "Memory Match with Fishing": {"active": det and _cfg_bool(cfg, "memory_match_enabled") and _cfg_bool(cfg, "memory_match_play_on_fishing", True) and _cfg_bool(cfg, "fishing_mode"), "enabled": _cfg_bool(cfg, "memory_match_play_on_fishing", True)},
                "Quest Board": {"active": det and _cfg_bool(cfg, "quest_board_enabled"), "enabled": _cfg_bool(cfg, "quest_board_enabled")},
                "Quest Board Auto Accept": {"active": det and _cfg_bool(cfg, "quest_board_enabled") and _cfg_bool(cfg, "quest_board_auto_accept", True), "enabled": _cfg_bool(cfg, "quest_board_auto_accept", True)},
                "Daily Event Check-in": {"active": det and _cfg_bool(cfg, "collect_daily_event_checkin"), "enabled": _cfg_bool(cfg, "collect_daily_event_checkin")},
            },
            "Pathing & Movement": {
                "Eden Path": {"active": bool(getattr(t, "_eden_running", False)), "enabled": _cfg_bool(cfg, "go_to_eden_spawn")},
                "Eden Detection": {"active": det and _cfg_bool(cfg, "eden_detection"), "enabled": _cfg_bool(cfg, "eden_detection")},
                "Auto Eden Contract": {"active": bool(getattr(t, "_eden_running", False)) and _cfg_bool(cfg, "auto_eden_contract"), "enabled": _cfg_bool(cfg, "auto_eden_contract")},
                "Basic Obby": {"active": bool(getattr(t, "_obby_running", False)), "enabled": _cfg_bool(cfg, "enable_obby_path") or _cfg_bool(cfg, "enable_auto_obby")},
                "Easter Egg Path": {"active": bool(getattr(t, "_egg_running", False)), "enabled": _cfg_bool(cfg, "collect_easter_egg")},
                "Reset on Rare Biomes": {"active": det and _cfg_bool(cfg, "reset_on_rare"), "enabled": _cfg_bool(cfg, "reset_on_rare")},
                "Teleport Back to Limbo": {"active": det and _cfg_bool(cfg, "teleport_back_to_limbo"), "enabled": _cfg_bool(cfg, "teleport_back_to_limbo")},
                "Auto Roblox Fullscreen": {"active": det and _cfg_bool(cfg, "auto_roblox_fullscreen"), "enabled": _cfg_bool(cfg, "auto_roblox_fullscreen")},
                "Auto Chat Close": {"active": det and _cfg_bool(cfg, "auto_chat_close"), "enabled": _cfg_bool(cfg, "auto_chat_close")},
            },
            "Item Usage & Buffs": {
                "Auto Pop Buff": {"active": bool(getattr(t, "auto_pop_state", False)), "enabled": True}, # It's a dict of settings so generally enabled
                "Auto Pop Glitched": {"active": det and _cfg_bool(cfg, "auto_pop_glitched"), "enabled": _cfg_bool(cfg, "auto_pop_glitched")},
                "Auto Pop Dreamspace": {"active": det and _cfg_bool(cfg, "auto_pop_dreamspace"), "enabled": _cfg_bool(cfg, "auto_pop_dreamspace")},
                "Auto Pop Cyberspace": {"active": det and _cfg_bool(cfg, "auto_pop_cyberspace"), "enabled": _cfg_bool(cfg, "auto_pop_cyberspace")},
                "Cyberspace Only Warp": {"active": det and _cfg_bool(cfg, "cyberspace_only_warp"), "enabled": _cfg_bool(cfg, "cyberspace_only_warp")},
                "Glitched Buff Enable": {"active": det and _cfg_bool(cfg, "enable_buff_glitched"), "enabled": _cfg_bool(cfg, "enable_buff_glitched")},
                "Biome Randomizer": {"active": bool(getattr(t, "_br_sc_running", False)) and _cfg_bool(cfg, "biome_randomizer"), "enabled": _cfg_bool(cfg, "biome_randomizer")},
                "Strange Controller": {"active": bool(getattr(t, "_br_sc_running", False)) and _cfg_bool(cfg, "strange_controller"), "enabled": _cfg_bool(cfg, "strange_controller")},
                "Float Aura": {"active": det and _cfg_bool(cfg, "use_float_aura"), "enabled": _cfg_bool(cfg, "use_float_aura")},
            },
            "Merchants & Economy": {
                "Auto Merchant": {"active": bool(getattr(t, "on_auto_merchant_state", False)), "enabled": _cfg_bool(cfg, "merchant_teleporter")},
                "Merchant OCR": {"active": det and _cfg_bool(cfg, "merchant_ocr"), "enabled": _cfg_bool(cfg, "merchant_ocr")},
                "Auto Merchant in Limbo": {"active": det and _cfg_bool(cfg, "auto_merchant_in_limbo"), "enabled": _cfg_bool(cfg, "auto_merchant_in_limbo")},
                "Jester Exchange": {"active": bool(getattr(t, "_jester_exchange_running", False)), "enabled": _cfg_bool(cfg, "enable_jester_exchange")},
                "Merchant Pings (Discord)": {"active": det and (_cfg_bool(cfg, "ping_jester") or _cfg_bool(cfg, "ping_mari") or _cfg_bool(cfg, "ping_eden")), "enabled": _cfg_bool(cfg, "ping_jester") or _cfg_bool(cfg, "ping_mari") or _cfg_bool(cfg, "ping_eden")},
                "Daily Quests": {"active": det and _cfg_bool(cfg, "auto_claim_daily_quests"), "enabled": _cfg_bool(cfg, "auto_claim_daily_quests")},
            },
            "Crafting": {
                "Potion Crafting": {"active": bool(getattr(t, "_potion_thread_active", False)), "enabled": _cfg_bool(cfg, "enable_potion_crafting")},
                "Potion Switching": {"active": _cfg_bool(cfg, "enable_potion_switching") and _cfg_bool(cfg, "enable_potion_crafting"), "enabled": _cfg_bool(cfg, "enable_potion_switching")},
            },
            "Recording & Screenshots": {
                "Aura Recording": {"active": det and _cfg_bool(cfg, "enable_aura_record"), "enabled": _cfg_bool(cfg, "enable_aura_record")},
                "Aura Screenshot": {"active": det and _cfg_bool(cfg, "aura_detection_screenshot"), "enabled": _cfg_bool(cfg, "aura_detection_screenshot")},
                "Rare Biome Recording": {"active": det and _cfg_bool(cfg, "record_rare_biome"), "enabled": _cfg_bool(cfg, "record_rare_biome")},
                "Rare Biome Screenshot": {"active": det and _cfg_bool(cfg, "rare_biome_screenshot"), "enabled": _cfg_bool(cfg, "rare_biome_screenshot")},
                "Periodic Aura Screenshot": {"active": det and _cfg_bool(cfg, "periodical_aura_screenshot"), "enabled": _cfg_bool(cfg, "periodical_aura_screenshot")},
                "Periodic Inventory Screenshot": {"active": det and _cfg_bool(cfg, "periodical_inventory_screenshot"), "enabled": _cfg_bool(cfg, "periodical_inventory_screenshot")},
                "Glitch Effect UI": {"active": det and _cfg_bool(cfg, "enable_glitch_effect"), "enabled": _cfg_bool(cfg, "enable_glitch_effect")},
            }
        }
        
        for cat_name, cat_modules in categories.items():
            for mod_name, mod_data in cat_modules.items():
                modules[mod_name] = mod_data
                
        incompatibilities = []
        if _cfg_bool(cfg, "enable_idle_mode"):
            incompatibilities.append("Idle Mode is ON: Most automated actions are paused infinitely.")

        if _cfg_bool(cfg, "multiple_instances_enabled"):
            incompatibilities.extend([
                "Multiple-Instances mode is observation/Anti-AFK only; statistics are disabled.",
                "Mouse actions, OCR, pathing, fishing, merchant, potion crafting, and foreground automation are disabled.",
                "A primary/main window is not supported because focus and pause/resume cannot be proven safe across Roblox windows.",
            ])
        
        if _cfg_bool(cfg, "go_to_eden_spawn") and _cfg_bool(cfg, "fishing_mode"):
            incompatibilities.append("Conflict: Both Eden Path and Fishing Mode are enabled. Fishing will take priority unless blocked.")

        if _cfg_bool(cfg, "enable_potion_crafting") and _cfg_bool(cfg, "fishing_mode"):
            incompatibilities.append("Potion Crafting is enabled: It has the highest priority take over from Fishing Mode and cancels any automated actions.")

        return {
            "modules": modules,
            "incompatibilities": incompatibilities
        }

    def get_runtime_diagnostics(self):
        """Return read-only runtime checks for troubleshooting without changing macro state."""
        t = self._tracker
        cfg = getattr(t, "config", {}) if t else {}
        roblox_processes = []
        try:
            for proc in psutil.process_iter(["pid", "name"]):
                name = str(proc.info.get("name") or "")
                if name.lower() in {"robloxplayerbeta.exe", "windows10universal.exe"}:
                    roblox_processes.append({"pid": int(proc.info["pid"]), "name": name})
        except Exception:
            pass
        log_file = None
        log_count = 0
        try:
            candidates = []
            if t and getattr(t, "logs_dir", None) and os.path.isdir(t.logs_dir):
                candidates = [Path(t.logs_dir) / name for name in os.listdir(t.logs_dir) if name.lower().endswith(".log")]
            candidates = [path for path in candidates if path.is_file()]
            if candidates:
                latest = max(candidates, key=lambda path: path.stat().st_mtime)
                log_file = {"name": latest.name, "size": latest.stat().st_size, "modified": datetime.fromtimestamp(latest.stat().st_mtime).isoformat()}
                with latest.open("r", encoding="utf-8", errors="ignore") as handle:
                    for line in handle:
                        if "Player added:" in line or "Player removed:" in line:
                            log_count += 1
        except Exception:
            pass
        rect = None
        try:
            rect = get_client_rect_screen()
        except Exception:
            pass
        meta = cfg.get("_calibration_meta") if isinstance(cfg, dict) else None
        return {
            "roblox": {"processes": roblox_processes, "window_found": bool(rect), "client_rect": list(rect) if rect else None},
            "macro": {"running": bool(getattr(t, "detection_running", False)) if t else False, "idle_mode": bool(cfg.get("enable_idle_mode", False)) if isinstance(cfg, dict) else False},
            "logs": {"directory": str(getattr(t, "logs_dir", "")) if t else "", "latest": log_file, "player_events": log_count},
            "calibration": {"metadata_count": len(meta) if isinstance(meta, dict) else 0, "runtime_rect": cfg.get("_calibration_runtime_rect") if isinstance(cfg, dict) else None},
        }

    def collect_daily_event_now(self):
        """Manual Daily Rewards claim (test button). Runs via the action scheduler."""
        import time as _time

        tracker = getattr(self, "_tracker", None)
        if tracker is None:
            return {"success": False, "reason": "Macro core is not running yet."}
        if not getattr(tracker, "_action_scheduler", None):
            return {"success": False, "reason": "Action scheduler is not initialized."}
        result_box = {"result": None}

        def _wrapped():
            try:
                result_box["result"] = tracker._claim_daily_event_checkin(manual=True)
            except Exception as exc:
                result_box["result"] = {"success": False, "reason": f"Claim error: {exc}"}

        try:
            tracker._action_scheduler.enqueue_action(
                _wrapped, name="daily_event_checkin_manual", priority=3
            )
        except Exception as exc:
            return {"success": False, "reason": f"Could not enqueue the claim: {exc}"}

        deadline = _time.time() + 45
        while _time.time() < deadline and result_box["result"] is None:
            _time.sleep(0.25)
        return result_box["result"] or {
            "success": False,
            "reason": "Timed out waiting for the claim action (is Roblox running and focused?).",
        }

    def set_remote_access(self, enabled):
        """Start/stop the remote Discord bot from the React panel."""
        tracker = getattr(self, "_tracker", None)
        if tracker is None or not isinstance(getattr(tracker, "config", None), dict):
            return {"success": False, "reason": "Macro core is not running yet."}
        try:
            tracker.config["remote_access_enabled"] = bool(enabled)
            tracker.save_config()
            if enabled:
                token = str(tracker.config.get("remote_bot_token") or "").strip()
                if not token:
                    return {"success": False, "reason": "Bot token is empty — paste it first."}
                tracker.start_remote_bot()
                alive = bool(getattr(tracker, "remote_bot_thread", None) and tracker.remote_bot_thread.is_alive())
                return {"success": True, "running": alive, "reason": "" if alive else "Bot thread did not survive startup — check the log for [Remote] errors."}
            tracker.stop_remote_bot()
            return {"success": True, "running": False}
        except Exception as exc:
            return {"success": False, "reason": f"Remote toggle failed: {exc}"}

    def get_remote_bot_status(self):
        """Live Discord-bot status for the Remote Access page."""
        tracker = getattr(self, "_tracker", None)
        if tracker is None or not hasattr(tracker, "get_remote_bot_status"):
            return {"running": False, "enabled": False, "core": False}
        try:
            status = tracker.get_remote_bot_status()
            status["core"] = True
            return status
        except Exception:
            return {"running": False, "enabled": False, "core": True}

    def restart_remote_bot(self):
        """Force-restart the Discord bot (fresh gateway session)."""
        tracker = getattr(self, "_tracker", None)
        if tracker is None or not hasattr(tracker, "restart_remote_bot"):
            return {"success": False, "reason": "Macro core is not running yet."}
        try:
            token = str((getattr(tracker, "config", {}) or {}).get("remote_bot_token") or "").strip()
            if not token:
                return {"success": False, "reason": "Bot token is empty — paste it first."}
            return tracker.restart_remote_bot()
        except Exception as exc:
            return {"success": False, "reason": f"Restart failed: {exc}"}

    def reset_daily_event_claim(self):
        """Clear the stored claim date so the next 03:00 MSK window re-collects."""
        tracker = getattr(self, "_tracker", None)
        if tracker is None or not isinstance(getattr(tracker, "config", None), dict):
            return {"success": False, "reason": "Macro core is not running yet."}
        try:
            tracker.config["daily_event_claimed_date"] = ""
            tracker.save_config()
            return {
                "success": True,
                "claimed_date": "",
                "message": "Claim date reset — the macro will collect again at the next 03:00 MSK window.",
            }
        except Exception as exc:
            return {"success": False, "reason": f"Reset failed: {exc}"}

    # Keys that survive a full reset: they are connection data (accounts and
    # endpoints), not preferences — retyping them after every reset would be
    # pure friction.
    _RESET_PRESERVED_KEYS = ("webhook_url", "webhook_urls", "remote_bot_token", "remote_allowed_user_id")

    def reset_config_to_defaults(self):
        """Reset the ACTIVE config to app defaults.

        Writes an empty disk config and lets load_config rebuild the full
        default set (same code path as a first launch), so calibration
        positions, toggles, paths — everything goes back to stock. A
        timestamped backup of the previous config is kept next to it.
        """
        tracker = getattr(self, "_tracker", None)
        if tracker is None or not isinstance(getattr(tracker, "config", None), dict):
            return {"success": False, "reason": "Macro core is not running yet."}
        try:
            from biome_tracker import config as core_config
            path = core_config.get_config_file()
            old = {}
            try:
                old = dict(core_config.load_config() or {})
            except Exception:
                old = {}
            backup = ""
            try:
                if path.exists():
                    from datetime import datetime as _dt
                    stamp = _dt.now().strftime("%Y%m%d-%H%M%S")
                    backup_path = path.with_name(f"config.backup-{stamp}.json")
                    shutil.copyfile(str(path), str(backup_path))
                    backup = str(backup_path)
            except Exception:
                backup = ""
            # Empty disk config -> load_config() rebuilds pure defaults.
            # _write_config replaces the file directly (save_config MERGES,
            # which would keep every old value).
            core_config._write_config(path, {})
            fresh = tracker.load_config() or {}
            for key in self._RESET_PRESERVED_KEYS:
                if old.get(key):
                    fresh[key] = old[key]
            tracker.config.clear()
            tracker.config.update(fresh)
            tracker.save_config()
            # Remote access resets to OFF -> bring the bot down if it ran.
            if not tracker.config.get("remote_access_enabled"):
                try:
                    tracker.stop_remote_bot()
                except Exception:
                    pass
            return {
                "success": True,
                "backup": backup,
                "message": ("All settings were reset to defaults."
                            + (f" Previous config saved as {backup}" if backup else "")),
            }
        except Exception as exc:
            return {"success": False, "reason": f"Reset failed: {exc}"}

    def get_macro_logs(self, max_lines=100):
        try:
            log_path = str(LOGS_DIR / "macro_logs.txt")
            if not os.path.exists(log_path):
                return {"lines": []}
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                all_lines = f.readlines()
            tail = all_lines[-max_lines:] if len(all_lines) > max_lines else all_lines
            cleaned = [line.rstrip("\n\r") for line in tail if line.strip()]
            return {"lines": cleaned}
        except Exception as e:
            return {"lines": [f"[Error reading logs: {e}]"]}

    def _is_fishing_mode_enabled(self):
        cfg = getattr(self._tracker, "config", None) if self._tracker else None
        if not isinstance(cfg, dict): return False
        if cfg.get("enable_idle_mode", False): return False
        return bool(cfg.get("fishing_mode", False))

    def _fishing_can_run(self):
        t = self._tracker
        if not t or not getattr(t, "detection_running", False): return False
        if not self._is_fishing_mode_enabled(): return False

        # pause during reconnect, but mark that we need to sell when we come back
        if getattr(t, "reconnecting_state", False):
            self._fishing_runtime_state["rejoin_in_progress"] = True
            return False
        if self._fishing_runtime_state.get("rejoin_in_progress"):
            self._fishing_runtime_state["rejoin_in_progress"] = False
            self._fishing_runtime_state["force_sell_on_next_cycle"] = True

        _STALE_TIMEOUT = 240
        now = time.time()
        blocking_flags = ("auto_pop_state",)
        any_blocking = False

        for flag_name in blocking_flags:
            if getattr(t, flag_name, False):
                ts_key = f"_fishing_block_ts_{flag_name}"
                first_seen = self._fishing_runtime_state.get(ts_key, 0)
                if first_seen == 0:
                    self._fishing_runtime_state[ts_key] = now
                    any_blocking = True
                elif (now - first_seen) >= _STALE_TIMEOUT:
                    setattr(t, flag_name, False)
                    self._fishing_runtime_state[ts_key] = 0
                    try:
                        t.append_log(
                            f"[FishingMode] Force cleared stale '{flag_name}' flag "
                            f"after {_STALE_TIMEOUT}s — was blocking fishing."
                        )
                    except Exception: pass
                else:
                    any_blocking = True
            else:
                ts_key = f"_fishing_block_ts_{flag_name}"
                if self._fishing_runtime_state.get(ts_key, 0): self._fishing_runtime_state[ts_key] = 0

        if any_blocking: return False
        return True

    def _fishing_config_provider(self):
        t = self._tracker
        if t and isinstance(getattr(t, "config", None), dict):
            return dict(t.config)
        return load_config()

    def _on_fishing_failsafe_timeout(self):
        if not self._tracker: return
        biome = str(getattr(self._tracker, "current_biome", "") or "").upper().strip()

        # Don't kill Roblox during a rare biome — wait for it to end
        from biome_tracker.base_support import rare_biomes
        if biome in rare_biomes:
            self._tracker._pending_fishing_failsafe_rejoin = True
            try:
                self._tracker.append_log(f"[FishingMode] Failsafe timed out during {biome}; delaying rejoin.")
                self._tracker.send_webhook_status(
                    f"Fishing failsafe timed out during {biome}. Rejoin delayed until biome ends.",
                    color=0xffcc00,
                )
            except Exception: pass
            return

        try: self._tracker.terminate_roblox_processes()
        except Exception as e: print(f"Fishing failsafe close Roblox failed: {e}")

        if not self._fishing_config_provider().get("auto_reconnect", False):
            self._emit_fishing_failsafe_warning(
                "Fishing failsafe timeout: Roblox closed after 60s with no minigame. "
                "Enable PS reconnect in Misc so it can recover automatically."
            )

    def _run_fishing_br_sc_sequence(self):
        if not self._tracker: return False
        t = self._tracker
        old_override = getattr(t, "_fishing_br_sc_override", False)
        t._fishing_br_sc_override = True
        ran = False
        try:
            try: t.activate_roblox_window()
            except Exception: pass

            try:
                t._use_br_sc_impl("strange controller")
                t.last_sc_time = datetime.now()
                ran = True
            except Exception as e:
                print(f"Fishing SC step failed: {e}")
            try:
                t._use_br_sc_impl("biome randomizer")
                t.last_br_time = datetime.now()
                ran = True
            except Exception as e:
                print(f"Fishing BR step failed: {e}")
        except Exception as e:
            print(f"Fishing BR/SC sequence failed: {e}")
        finally:
            t._fishing_br_sc_override = old_override
        return ran

    def _run_fishing_merchant_sequence(self):
        if not self._tracker: return False
        t = self._tracker
        self._fishing_runtime_state["merchant_requires_reset"] = False
        old_override = getattr(t, "_fishing_br_sc_override", False)
        t._fishing_br_sc_override = True
        ran = False
        try:
            try: t.activate_roblox_window()
            except Exception: pass

            merchant_fn = getattr(t, "_merchant_teleporter_impl", None)
            if not callable(merchant_fn):
                print("Fishing merchant sequence skipped: _merchant_teleporter_impl unavailable")
                return False

            # reuse the same merchant logic so we get buy, webhook, limbo, everything
            merchant_fn()
            ran = bool(getattr(t, "_last_merchant_sequence_ran", False))
            self._fishing_runtime_state["merchant_requires_reset"] = bool(
                getattr(t, "_last_merchant_sequence_requires_reset", False)
            )
            if ran: t.last_mt_time = datetime.now()
        except Exception as e:
            print(f"Fishing merchant sequence failed: {e}")
        finally:
            t._fishing_br_sc_override = old_override
        return ran

    def _start_fishing_worker(self) -> None:
        if not self._tracker:
            return
        with self._fishing_lock:
            if self._fishing_thread and self._fishing_thread.is_alive():
                return
            self._fishing_stop_event.clear()

            def _run_fishing():
                try:
                    from biome_tracker.fishing import run_fishing_loop
                    run_fishing_loop(
                        stop_event=self._fishing_stop_event,
                        can_run_cb=self._fishing_can_run,
                        config_provider=self._fishing_config_provider,
                        log_prefix="[FishingMode]",
                        print_start_stop=True,
                        on_failsafe_timeout=self._on_fishing_failsafe_timeout,
                        run_br_sc_sequence_cb=self._run_fishing_br_sc_sequence,
                        run_merchant_sequence_cb=self._run_fishing_merchant_sequence,
                        activate_roblox_cb=self._tracker.activate_roblox_window,
                        close_chat_fn=self._tracker.close_chat_if_open,
                        runtime_state=self._fishing_runtime_state,
                        set_fishing_busy_cb=lambda busy: setattr(self._tracker, "_fishing_busy", busy),
                        on_f2_pressed_cb=lambda: (self.set_biome_detection(False), self._emit_shortcut("STOP")),
                        merchant_ocr_check_cb=getattr(self._tracker, "_scheduled_merchant_ocr_check", None),
                    )
                except Exception as e:
                    print(f"Fishing worker failed: {e}")

            self._fishing_thread = threading.Thread(target=_run_fishing, daemon=True)
            self._fishing_thread.start()

    def _stop_fishing_worker(self) -> None:
        with self._fishing_lock:
            self._fishing_stop_event.set()
            t = self._fishing_thread
            if t and t.is_alive():
                t.join(timeout=1.0)
            if not t or not t.is_alive():
                self._fishing_thread = None

    def set_biome_detection(self, enabled):
        if not self._tracker: return
        multi_enabled = bool(self._tracker.config.get("multiple_instances_enabled", False))
        if multi_enabled:
            print(f"[MultiInstance] set_biome_detection({enabled}) - multi-instance mode active", flush=True)
            if enabled:
                multi_instance.set_enabled(True, self._tracker)
                self._tracker.detection_running = True
                # Same first-aura rule as start_detection: the aura the user
                # was already wearing must not be announced on launch.
                self._tracker.last_aura_found = None
                self._tracker._aura_webhook_skip_first = True
                multi_instance.start_idle_loop()
            else:
                multi_instance.stop_idle_loop()
                self._tracker.detection_running = False
            self._emit_macro_status()
            return
        if enabled:
            if not self._tracker.detection_running:
                threading.Thread(target=self._tracker.start_detection, daemon=True).start()
            if self._is_fishing_mode_enabled():
                self._start_fishing_worker()
            else:
                self._stop_fishing_worker()
                try: self._tracker.start_potion_crafting()
                except Exception: pass
        else:
            self._stop_fishing_worker()
            self._tracker.stop_detection()
        self._emit_macro_status()

    # --- frontend event emitters (JS bridge) ---

    def _safe_eval_js(self, js_code):
        if not self._window: return
        try:
            self._window.evaluate_js(js_code)
        except Exception: pass

    def _emit_macro_status(self):
        self._safe_eval_js(f'if(window.onMacroStatus) window.onMacroStatus("{self.get_macro_status()}");')

    def _emit_config_update(self):
        self._safe_eval_js('if(window.onConfigUpdated) window.onConfigUpdated();')

    def _emit_stats_update(self):
        self._safe_eval_js('if(window.onStatsUpdated) window.onStatsUpdated();')

    def _emit_biome_update(self, biome):
        self._safe_eval_js(f'if(window.onBiomeUpdate) window.onBiomeUpdate("{biome}");')

    def _emit_shortcut(self, key):
        self._safe_eval_js(f'if(window.onShortcutEvent) window.onShortcutEvent("{key}");')

    def _emit_update_available(self, version, url):
        self._safe_eval_js(f'if(window.onUpdateAvailable) window.onUpdateAvailable("{version}", "{url}");')

    def _emit_update_status(self, status):
        self._safe_eval_js(f'if(window.onUpdateStatus) window.onUpdateStatus("{status}");')

    def _emit_fishing_failsafe_warning(self, msg):
        self._safe_eval_js(f"if(window.onFishingFailsafeWarning) window.onFishingFailsafeWarning({json.dumps(str(msg))});")

    def _request_biome_confirm(self, biome: str):
        self._biome_confirm_evt.clear()
        self._biome_confirm_result = None
        popup_window = None
        try:
            print(f"[BiomeConfirm] Spawning independent popup for biome: {biome}")
            fe = get_frontend_entry()
            popup_w, popup_h = 480, 400
            try:
                screen_w = win32api.GetSystemMetrics(0)
                screen_h = win32api.GetSystemMetrics(1)
                popup_x = (screen_w - popup_w) // 2
                popup_y = (screen_h - popup_h) // 2
            except Exception:
                popup_x, popup_y = 300, 200

            win_kwargs = {
                "title": f"\u26a0\ufe0f Rare Biome Detected \u2014 {biome} \u26a0\ufe0f",
                "js_api": self,
                "width": popup_w,
                "height": popup_h,
                "x": popup_x,
                "y": popup_y,
                "resizable": False,
            }

            if fe and fe.get("url"):
                from urllib.parse import quote as _urlquote
                win_kwargs["url"] = f'{fe["url"]}#window=biome_confirm&biome={_urlquote(str(biome))}'
            elif fe and "html" in fe:
                injected_script = f'''<script>
                const _OrigSearchParams = window.URLSearchParams;
                window.URLSearchParams = class extends _OrigSearchParams {{
                    constructor(init) {{
                        if (init === window.location.search || !init) {{
                            init = "?window=biome_confirm&biome={biome}";
                        }}
                        super(init);
                    }}
                }};
                </script>'''
                if fe.get("url"):
                    base_dir = str(fe["url"]).rsplit("/", 1)[0] + "/"
                    injected_script = f'<base href="{base_dir}">' + injected_script
                html = fe["html"].replace("<head>", f"<head>{injected_script}", 1)
                win_kwargs["html"] = html
            else:
                win_kwargs["url"] = "http://localhost:5173?window=biome_confirm&biome=" + biome

            popup_window = webview.create_window(**win_kwargs)
            threading.Thread(target=_apply_native_window_icon_when_ready, args=(win_kwargs["title"],), daemon=True).start()

            try:
                def _flash():
                    time.sleep(1.0)
                    try:
                        hwnd = win32gui.FindWindow(None, f"⚠️ Rare Biome Detected �� {biome} ⚠️")
                        if hwnd:
                            win32gui.FlashWindowEx(hwnd, win32con.FLASHW_ALL | win32con.FLASHW_TIMERNOFG, 5, 0)
                    except Exception:
                        pass
                threading.Thread(target=_flash, daemon=True).start()
            except Exception:
                pass

        except Exception as e:
            print(f"[BiomeConfirm] Failed to create popup window: {e}")
            return None

        responded = self._biome_confirm_evt.wait(timeout=10)

        # Close the popup window
        try:
            if popup_window:
                popup_window.destroy()
        except Exception:
            pass

        if not responded:
            return None
        return self._biome_confirm_result

    def confirm_biome_response(self, confirmed: bool):
        self._biome_confirm_result = bool(confirmed)
        self._biome_confirm_evt.set()

    def apply_update(self, download_url: str, version: str = ""):
        if self._tracker:
            def _do_update():
                try:
                    self._emit_update_status("downloading")
                    self._tracker.download_and_apply_update(download_url, version=version)
                except Exception as e:
                    self._emit_update_status("failed")
            threading.Thread(target=_do_update, daemon=True).start()
            return True
        return False

    def check_for_updates(self):
        if not self._tracker:
            return False

        def _do_check():
            try:
                self._tracker.check_for_updates()
            except Exception as e:
                print(f"Update check failed: {e}")

        threading.Thread(target=_do_check, daemon=True).start()
        return True

    def get_update_available(self):
        if not self._tracker:
            return None
        try:
            latest_release = self._tracker._fetch_latest_release()
            if not isinstance(latest_release, dict):
                return None

            latest_version = str(latest_release.get("tag_name", "")).strip()
            if not latest_version:
                return None
            if self._tracker._is_same_version(latest_version, current_version):
                return None

            _asset_name, download_url = self._tracker._pick_update_exe_asset(latest_release)
            if not download_url:
                return None

            return {"version": latest_version, "url": download_url}
        except Exception as e:
            print(f"Direct update query failed: {e}")
            return None

    def get_auto_pop_items(self):
        cfg = self.get_config()
        items = []
        if isinstance(cfg, dict):
            direct = cfg.get("custom_auto_pop_buffs", cfg.get("custom_auto_pop_items", []))
            if isinstance(direct, list):
                items.extend(x for x in direct if isinstance(x, str) and x.strip())
            # Recover items created by older builds that stored them only in
            # biome loadouts. This makes existing Shifter entries visible again.
            auto_map = cfg.get("auto_pop_biomes", {})
            if isinstance(auto_map, dict):
                for entry in auto_map.values():
                    if not isinstance(entry, dict):
                        continue
                    buffs = entry.get("buffs", {})
                    if isinstance(buffs, dict):
                        items.extend(x for x in buffs if isinstance(x, str) and x.strip())
        builtin = {"Fortune Potion I", "Fortune Potion II", "Fortune Potion III", "Godlike Potion", "Haste Potion I", "Haste Potion II", "Haste Potion III", "Heavenly Potion", "Lucky Potion", "Oblivion Potion", "Potion of bound", "Rune of Everything", "Speed Potion", "Stella's Candle", "Strange Potion I", "Strange Potion II", "Transcendent Potion", "Warp Potion", "Xyz Potion"}
        items = list(dict.fromkeys(x for x in items if x not in builtin))
        return {"items": items, "custom": items}

    def add_auto_pop_item(self, name):
        name = str(name or "").strip()
        cfg = dict(self.get_config())
        items = cfg.get("custom_auto_pop_buffs", [])
        if not isinstance(items, list): items = []
        if name and name not in items: items.append(name)
        cfg["custom_auto_pop_buffs"] = items
        self.save_config(cfg)
        return {"success": True, "items": items, "custom": items}

    def remove_auto_pop_item(self, name):
        name = str(name or "").strip()
        cfg = dict(self.get_config())
        items = cfg.get("custom_auto_pop_buffs", [])
        items = [x for x in items if x != name] if isinstance(items, list) else []
        cfg["custom_auto_pop_buffs"] = items
        # Remove the custom item from every biome loadout too, without touching
        # built-in items or the rest of the user's configuration.
        auto_map = cfg.get("auto_pop_biomes", {})
        if isinstance(auto_map, dict):
            for entry in auto_map.values():
                if isinstance(entry, dict) and isinstance(entry.get("buffs"), dict):
                    entry["buffs"].pop(name, None)
        self.save_config(cfg)
        return {"success": True, "items": items, "custom": items}

    def get_rare_biome_custom(self):
        cfg = self.get_config()
        base = getattr(self._tracker, "RARE_BIOME_CUSTOM", {}) if self._tracker else {}
        if not isinstance(base, dict) or not base:
            try:
                from biome_tracker.mixin_webhook import WebhookMixin
                base = WebhookMixin.RARE_BIOME_CUSTOM
            except Exception:
                base = {}
        result = dict(base) if isinstance(base, dict) else {}
        overrides = cfg.get("custom_rare_biome_overrides", {}) if isinstance(cfg, dict) else {}
        if isinstance(overrides, dict):
            for name, value in overrides.items():
                if isinstance(value, dict) and isinstance(result.get(name), dict):
                    result[name] = {**result[name], **value}
                elif isinstance(value, dict):
                    result[name] = value
        return result

    def send_webhook(self, *args, **kwargs):
        if self._tracker and hasattr(self._tracker, "send_webhook"):
            return self._tracker.send_webhook(*args, **kwargs)
        return False

    def preview_biome_webhook(self, biome, event_type, custom_title=None,
                              custom_description=None, color_override=None):
        """Build the exact biome webhook message for the customization preview.

        Uses the same builder as the real send path, so the preview matches
        Discord output 1:1, including custom rare copy, admin overrides and
        the Join Server link. Unsaved UI edits are passed as overrides.
        """
        import json as _json
        if not self._tracker or not hasattr(self._tracker, "build_biome_webhook_description"):
            return _json.dumps({"error": "tracker not ready"})
        try:
            # Resolve the message type exactly like handle_biome_detection
            # does, so the preview ping content matches a real send.
            notifier = self._tracker.config.get("biome_notifier", {}) or {}
            message_type = notifier.get(biome, "None")
            from biome_tracker.base_support import rare_biomes, admin_biomes
            meta = (self._tracker.biome_data.get(biome, {}) or {})
            category_norm = str(meta.get("category", "")).strip().lower()
            if biome in rare_biomes:
                message_type = "Ping"
            elif biome in admin_biomes:
                message_type = "Message"
            elif category_norm == "rare":
                message_type = "Ping"
            elif category_norm == "admin":
                message_type = "Message"
            built = self._tracker.build_biome_webhook_description(
                biome,
                "start" if event_type == "start" else "end",
                message_type,
                custom_title=custom_title,
                custom_desc=custom_description,
                color_override=color_override,
            )
            return _json.dumps(built)
        except Exception as e:
            return _json.dumps({"error": str(e)})

    def toggle_idle_monitor(self, enabled):
        # Keep the setting synchronized; the existing lifecycle loop owns the
        # actual auto-start behavior and remains the single source of truth.
        if self._tracker:
            self._tracker.config["auto_start_on_idle"] = bool(enabled)
            self._tracker.save_config()
            if hasattr(self._tracker, "_start_idle_monitor"):
                self._tracker._start_idle_monitor()
        return {"success": True, "enabled": bool(enabled)}

    def export_theme(self):
        # The config is the source of truth. The standalone file is retained
        # as an offline/import compatibility fallback, but must not override a
        # newer theme saved from Panel Customization.
        try:
            cfg = self.get_config()
            saved_theme = cfg.get("custom_theme_data") if isinstance(cfg, dict) else None
            if isinstance(saved_theme, dict) and saved_theme:
                return json.dumps(saved_theme, ensure_ascii=False)
        except Exception:
            pass
        try:
            themes_dir = APPDATA_BASE / "themes"
            theme_path = themes_dir / "endsol-theme.json"
            if theme_path.exists():
                return theme_path.read_text(encoding="utf-8")
        except Exception:
            pass
        return json.dumps({}, ensure_ascii=False)

    def import_theme(self, theme_json):
        """Save a theme only in the current user's EndSolMacro AppData."""
        try:
            theme = json.loads(theme_json) if isinstance(theme_json, str) else theme_json
            if not isinstance(theme, dict):
                return {"success": False, "error": "Theme must be an object"}
            themes_dir = APPDATA_BASE / "themes"
            themes_dir.mkdir(parents=True, exist_ok=True)
            theme_path = themes_dir / "endsol-theme.json"
            theme_path.write_text(json.dumps(theme, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            cfg = dict(self.get_config())
            cfg["custom_theme_data"] = theme
            self.save_config(cfg)
            return {"success": True, "path": str(theme_path), "theme": theme}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_theme_file(self, theme_json):
        """Explicit export/save API; never writes beside the executable."""
        return self.import_theme(theme_json)

    def import_theme_file(self):
        """Open a theme from the user's local EndSolMacro/themes folder."""
        try:
            themes_dir = APPDATA_BASE / "themes"
            themes_dir.mkdir(parents=True, exist_ok=True)
            if not self._window:
                return {"success": False, "error": "Window not available"}
            result = self._window.create_file_dialog(
                webview.FileDialog.OPEN,
                directory=str(themes_dir),
                allow_multiple=False,
                file_types=("Theme JSON (*.json)",),
            )
            if not result:
                return {"success": False, "error": "No theme selected"}
            path = result[0] if isinstance(result, (list, tuple)) else result
            with open(path, "r", encoding="utf-8") as f:
                theme = json.load(f)
            return self.import_theme(theme)
        except json.JSONDecodeError:
            return {"success": False, "error": "Invalid theme JSON file"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def send_webhook_status(self, status: str, color: int):
        if self._tracker and hasattr(self._tracker, 'send_webhook_status'):
            self._tracker.send_webhook_status(status, color)

    def check_winocr_status(self):
        # Availability check must stay fast; importing the Windows OCR bridge
        # can block while Windows initializes its language component.
        try:
            import importlib.util
            import importlib.metadata
            if importlib.util.find_spec("winocr") is None:
                return {"installed": False, "version": None}
            try:
                version = importlib.metadata.version("winocr")
            except Exception:
                version = "unknown"
            return {"installed": True, "version": version}
        except Exception as e:
            return {"installed": False, "version": None, "error": str(e)}

    def test_webhook(self, url):
        """Send a real Discord webhook test and return structured diagnostics."""
        import re
        value = str(url or "").strip()
        if not re.match(r"^https://(?:discord(?:app)?\.com)/api/webhooks/[^/]+/[^/]+$", value, re.I):
            return {"success": False, "error": "Invalid Discord webhook URL"}
        try:
            from biome_tracker.base_support import safe_post
            response = safe_post(value, json={"content": "EndSol Macro webhook test"}, timeout=10)
            if response is None:
                return {"success": False, "error": "Network request failed"}
            if 200 <= response.status_code < 300:
                return {"success": True, "status": response.status_code}
            return {"success": False, "status": response.status_code, "error": "Discord rejected the webhook"}
        except Exception as exc:
            return {"success": False, "error": str(exc)}

    def get_recorder_status(self):
        return getattr(self._tracker, "_is_recording", False) if self._tracker else False

    def start_macro_recording(self):
        if self._tracker:
            self._tracker.start_recording_path()
            return {"ok": True}
        return {"ok": False, "error": "No tracker"}

    def start_macro_recording_potion(self, name: str):
        clean_name = os.path.splitext(os.path.basename(str(name or "").strip()))[0]
        if not clean_name:
            return {"ok": False, "error": "Potion name is required"}
        if self._tracker:
            self._tracker.start_recording_path()
            self._active_potion_recording_name = clean_name
            return {"ok": True, "name": clean_name}
        return {"ok": False, "error": "No tracker"}

    def stop_macro_recording(self):
        if self._tracker: return self._tracker.stop_recording_path("obby", save_dir="paths")
        return "No tracker"

    def stop_macro_recording_potion(self, name: str):
        if self._tracker:
            return self._tracker.stop_recording_path(name, save_dir="crafting_files_do_not_open")
        return "No tracker"

    def _get_frontend_url(self):
        res = get_frontend_entry()
        return res["url"] if res else "http://localhost:5173"

    def _open_recorder(self, mode: str = "obby"):
        fe = get_frontend_entry()
        query = "window=recorder"
        if mode == "potion":
            query += "&mode=potion"
        elif mode == "custom":
            query += "&mode=custom"
        if mode == "potion":
            title = "Potion Recorder"
        elif mode == "custom":
            title = "Custom Path Recorder"
        else:
            title = "Obby Recorder"

        win_kwargs = {
            "title": title,
            "js_api": self,
            "width": 380,
            "height": 320,
            "resizable": True,
            "on_top": True,
        }

        if fe.get("url"):
            # URL fragments survive file:// navigation (queries do not —
            # WebView2 then renders its own "File not found" page). The app
            # reads the window type/mode from the hash as a fallback.
            win_kwargs["url"] = f'{fe["url"]}#{query}'
        else:
            # WebView2 cannot carry a query string on file:// URLs — it then
            # renders its own "File not found" page. Serve the bundled HTML
            # with a <base href> (relative ./assets then resolve) and expose
            # the window type through the URLSearchParams shim instead.
            base_dir = ""
            if fe.get("url"):
                base_dir = str(fe["url"]).rsplit("/", 1)[0] + "/"
            injected_script = (
                f'<base href="{base_dir}">'
                + f'''<script>
                const _OrigSearchParams = window.URLSearchParams;
                window.URLSearchParams = class extends _OrigSearchParams {{
                    constructor(init) {{
                        if (init === window.location.search || !init) {{
                            init = "?{query}";
                        }}
                        super(init);
                    }}
                }};
                </script>'''
            )
            html = fe["html"].replace("<head>", f"<head>{injected_script}", 1)
            win_kwargs["html"] = html

        webview.create_window(**win_kwargs)
        threading.Thread(target=_apply_native_window_icon_when_ready, args=(win_kwargs["title"],), daemon=True).start()

    def open_recorder_window(self):
        self._open_recorder("obby")

    def open_recorder_window_custom(self):
        """Recorder for the Custom Paths tab: keeps events in memory instead
        of overwriting the default Obby path file."""
        self._open_recorder("custom")

    def open_recorder_window_potion(self):
        self._open_recorder("potion")

    def stop_macro_recording_custom(self):
        """Stop a Custom Paths recording WITHOUT writing paths/obby.json.
        The events stay in memory until save_recording_as_custom_path is called."""
        if self._tracker:
            res = self._tracker.stop_recording_path("", save_dir="", save=False)
            events = getattr(self._tracker, "_recorded_events", []) or []
            return {"ok": res == "OK", "events": len(events), "message": res}
        return {"ok": False, "error": "No tracker"}

    def list_potion_files(self):
        try:
            rec_dir = "crafting_files_do_not_open"
            if os.path.isdir(rec_dir):
                return sorted([f for f in os.listdir(rec_dir) if f.lower().endswith(".json")])
        except Exception:
            pass
        return []

    def check_obby_path_exists(self):
        try:
            obby_file = os.path.join(os.getcwd(), "paths", "obby.json")
            if not os.path.isfile(obby_file):
                return False
            with open(obby_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            return bool(data)
        except Exception:
            return False

    def replay_recording(self):
        if self._tracker:
            return self._tracker.replay_path_recording("obby", save_dir="paths")
        return "No tracker"

    def replay_potion_recording(self, name: str):
        if self._tracker:
            return self._tracker.replay_path_recording(name, save_dir="crafting_files_do_not_open")
        return "No tracker"

    def test_aura_keybind(self):
         if self._tracker:
             def test_record():
                 try:
                    keybind = self._tracker.aura_record_keybind_var.get()
                    if not keybind: return
                    keys = [key.strip() for key in keybind.split('+')]
                    time.sleep(2)
                    pyautogui.hotkey(*keys)
                 except Exception as e:
                    print(f"Error testing aura keybind: {e}")
             threading.Thread(target=test_record, daemon=True).start()

    def test_biome_keybind(self):
         if self._tracker:
             def test_record():
                 try:
                    keybind = self._tracker.rarest_biome_keybind_var.get()
                    if not keybind: return
                    keys = [key.strip() for key in keybind.split('+')]
                    time.sleep(2)
                    pyautogui.hotkey(*keys)
                 except Exception as e:
                    print(f"Error testing biome keybind: {e}")
             threading.Thread(target=test_record, daemon=True).start()

    def align_camera(self):
         if self._tracker:
             self._tracker.align_camera()

    def emit_calibration_result(self, data):
         if isinstance(data, dict) and self._tracker and self._pending_calibration_key:
             try:
                 keys = ("x", "y", "w", "h") if self._pending_calibration_mode == "region" else ("x", "y")
                 value = data.get("value")
                 if not isinstance(value, (list, tuple)):
                     value = [data.get(k) for k in keys]
                 if all(isinstance(v, (int, float)) for v in value):
                     self._tracker.config[self._pending_calibration_key] = list(value)
                     save_config(self._tracker.config)
             except Exception as e:
                 print(f"[Calibration] Failed to persist result: {e}")
         if self._window:
             js_data = json.dumps(data)
             self._window.evaluate_js(
                 f"if(window.onCalibrationResult) window.onCalibrationResult({js_data});"
                 f"if(window.onCalibrationResultMisc) window.onCalibrationResultMisc({js_data});"
             )

    def create_calibration_window(self, key="unknown", window_type="point"):
        self._pending_calibration_key = key
        self._pending_calibration_mode = window_type
        self._calib_mgr.request_calibration(config_key=key, window_type=window_type)

    def take_calibration_screenshot(self):
        image = pyautogui.screenshot()
        out_dir = APPDATA_BASE / "images"
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f"calibration_{int(time.time() * 1000)}.png"
        image.save(path)
        return [str(path), int(image.width), int(image.height)]

    def _calibrations_dir(self):
        path = APPDATA_BASE / "Calibrations"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _calibration_payload(self):
        cfg = self.get_config() if callable(getattr(self, "get_config", None)) else (self._tracker.config if self._tracker else {})
        if not isinstance(cfg, dict):
            return {}
        payload = {}
        for key, value in cfg.items():
            if key.startswith("_") or key.startswith("calibration_preset_"):
                continue
            if isinstance(value, (list, tuple)) and len(value) in (2, 4) and all(isinstance(v, (int, float)) for v in value):
                payload[key] = list(value)
        if isinstance(cfg.get("_calibration_meta"), dict):
            payload["_calibration_meta"] = cfg["_calibration_meta"]
        return payload

    def list_calibrations(self):
        """List portable profiles with their target display metadata.

        Files copied into %LOCALAPPDATA%/EndSolMacro/Calibrations are
        automatically discoverable; malformed or incomplete profiles remain
        visible with an invalid status instead of being silently hidden.
        """
        try:
            profiles = []
            for path in sorted(self._calibrations_dir().glob("*.json"), key=lambda item: item.name.lower()):
                item = {"name": path.stem, "resolution": "", "scale": "", "mode": "", "valid": False, "error": ""}
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    values = payload.get("calibrations", {}) if isinstance(payload, dict) else {}
                    _valid, errors = validate_calibration_values(values, allow_incomplete=False)
                    item.update({
                        "resolution": payload.get("resolution", "") if isinstance(payload, dict) else "",
                        "scale": payload.get("scale", "") if isinstance(payload, dict) else "",
                        "mode": payload.get("mode", "") if isinstance(payload, dict) else "",
                        "valid": not errors and bool(_valid),
                        "error": "; ".join(errors[:3]),
                    })
                except Exception as exc:
                    item["error"] = str(exc)
                profiles.append(item)
            return {"success": True, "files": [item["name"] for item in profiles], "profiles": profiles}
        except Exception as e:
            return {"success": False, "error": str(e), "files": [], "profiles": []}

    # ── Custom Paths API ──────────────────────────────────────────────

    def list_custom_paths(self):
        try:
            from biome_tracker.custom_path_manager import list_custom_paths, FEATURE_LABELS
            paths = list_custom_paths()
            return {"success": True, "paths": paths, "features": FEATURE_LABELS}
        except Exception as e:
            return {"success": False, "error": str(e), "paths": [], "features": {}}

    def get_custom_path(self, path_id: str):
        try:
            from biome_tracker.custom_path_manager import get_custom_path
            data = get_custom_path(path_id)
            if data is None:
                return {"success": False, "error": "Path not found"}
            return {"success": True, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_custom_path(self, path_id: str, events: list, feature: str = "", label: str = "", speed_multiplier: float = 1.0):
        try:
            from biome_tracker.custom_path_manager import save_custom_path, get_custom_path
            existing_meta = (get_custom_path(path_id) or {}).get("meta", {})
            # Preserve the original walk-speed stamp when editing an existing
            # path; stamp the current mode only for new paths.
            recorded_nonvip = existing_meta.get("recorded_nonvip", None)
            if recorded_nonvip is None:
                recorded_nonvip = self.get_config().get("non_vip_movement_path", False)
            ok = save_custom_path(
                path_id, events, feature, label, speed_multiplier,
                recorded_nonvip=recorded_nonvip,
                created=existing_meta.get("created", ""),
            )
            return {"success": ok}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def delete_custom_path(self, path_id: str):
        try:
            from biome_tracker.custom_path_manager import delete_custom_path
            ok = delete_custom_path(path_id)
            return {"success": ok}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def assign_custom_path(self, path_id: str, feature: str):
        try:
            from biome_tracker.custom_path_manager import get_custom_path, save_custom_path
            data = get_custom_path(path_id)
            if not data:
                return {"success": False, "error": "Path not found"}
            meta = data.get("meta", {})
            events = data.get("events", [])
            save_custom_path(
                path_id=path_id,
                events=events,
                feature=feature,
                label=meta.get("label", path_id),
                speed_multiplier=meta.get("speed_multiplier", 1.0),
                recorded_nonvip=meta.get("recorded_nonvip", None),
                created=meta.get("created", ""),
            )
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_recording_as_custom_path(self, name: str, feature: str = "", include_mouse: bool = False):
        try:
            from biome_tracker.custom_path_manager import save_recording_as_custom
            events = getattr(self._tracker, "_recorded_events", [])
            if not events:
                return {"success": False, "error": "No recording data available. Record a path in the Recorder first (do not close the panel in between)."}
            if not include_mouse:
                # Movement paths only need the keyboard: WASD, Space, E, etc.
                events = [ev for ev in events if not str(ev.get("type", "")).startswith("mouse")]
            if not events:
                return {"success": False, "error": "Recording contains only mouse actions — nothing to save for a walk path."}
            # Stamp the walk-speed mode that was active while recording, so
            # playback compensates when the Non-VIP setting differs.
            path_id = save_recording_as_custom(
                events, name, feature,
                recorded_nonvip=self.get_config().get("non_vip_movement_path", False),
            )
            return {"success": True, "path_id": path_id}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def save_calibration(self, name: str):
        try:
            clean = re.sub(r"[^A-Za-z0-9 _.-]+", "_", str(name or "")).strip(" .")[:80]
            if not clean:
                return {"success": False, "error": "Enter a calibration name."}
            path = self._calibrations_dir() / f"{clean}.json"
            payload = {
                "name": clean,
                "saved_at": datetime.now(timezone.utc).isoformat(),
                "resolution": self.get_config().get("calibration_preset_resolution", ""),
                "scale": self.get_config().get("calibration_preset_scale", ""),
                "mode": self.get_config().get("calibration_preset_mode", ""),
                "calibrations": self._calibration_payload(),
            }
            path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"success": True, "name": clean, "path": str(path)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def backup_current_calibration(self):
        """Create a timestamped backup before any bulk calibration replacement."""
        try:
            backup_name = f"_backup_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S_%f')[:-3]}"
            result = self.save_calibration(backup_name)
            if result.get("success"):
                return {"success": True, "name": result.get("name"), "path": result.get("path")}
            return result
        except Exception as e:
            return {"success": False, "error": str(e)}

    def load_calibration(self, name: str):
        try:
            clean = re.sub(r"[^A-Za-z0-9 _.-]+", "_", str(name or "")).strip(" .")[:80]
            path = self._calibrations_dir() / f"{clean}.json"
            if not path.exists():
                return {"success": False, "error": "Calibration file not found."}
            payload = json.loads(path.read_text(encoding="utf-8"))
            values = payload.get("calibrations", {}) if isinstance(payload, dict) else {}
            valid, errors = validate_calibration_values(values, allow_incomplete=False)
            if errors:
                return {"success": False, "error": "Invalid calibration profile.", "validation_errors": errors}
            if not valid:
                return {"success": False, "error": "No calibration coordinates found."}
            return {"success": True, "name": clean, "calibrations": valid, "resolution": payload.get("resolution", ""), "scale": payload.get("scale", ""), "mode": payload.get("mode", "")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def export_calibration_file(self):
        try:
            if not self._window: return {"success": False, "error": "Window not available"}
            result = self._window.create_file_dialog(webview.FileDialog.SAVE, directory=str(self._calibrations_dir()), save_filename="EndSol-calibration.json", file_types=("Calibration JSON (*.json)",))
            if not result: return {"success": False, "error": "Export cancelled"}
            path = result[0] if isinstance(result, (list, tuple)) else result
            payload = {"format": "EndSolMacroCalibration", "version": 1, "saved_at": datetime.now(timezone.utc).isoformat(), "calibrations": self._calibration_payload()}
            Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            return {"success": True, "path": str(path)}
        except Exception as e: return {"success": False, "error": str(e)}

    def import_calibration_file(self):
        try:
            if not self._window: return {"success": False, "error": "Window not available"}
            result = self._window.create_file_dialog(webview.FileDialog.OPEN, directory=str(self._calibrations_dir()), allow_multiple=False, file_types=("Calibration JSON (*.json)",))
            if not result: return {"success": False, "error": "Import cancelled"}
            path = result[0] if isinstance(result, (list, tuple)) else result
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
            values = payload.get("calibrations") if isinstance(payload, dict) else None
            if not isinstance(values, dict): return {"success": False, "error": "This is not an EndSol calibration file."}
            valid = {k: v for k, v in values.items() if isinstance(k, str) and isinstance(v, list) and len(v) in (2, 4) and all(isinstance(x, (int, float)) for x in v)}
            if not valid: return {"success": False, "error": "No valid calibration coordinates found."}
            backup = self.backup_current_calibration()
            cfg = dict(self.get_config()); cfg.update(valid); save_config(cfg)
            if self._tracker: self._tracker.config.update(valid)
            return {"success": True, "path": str(path), "count": len(valid), "backup": backup.get("name")}
        except json.JSONDecodeError: return {"success": False, "error": "Invalid calibration JSON file."}
        except Exception as e: return {"success": False, "error": str(e)}

    def display_calibration_on_screen(self, key: str, label: str = "", duration_ms: int = 2500):
        try:
            self._calib_mgr.request_display(
                config_key=key,
                label=label or key,
                duration_ms=duration_ms
            )
            return True
        except Exception:
            return False

    def display_all_fishing_calibrations_on_screen(self, duration_ms: int = 3000):
        try:
            cfg = self.get_config() if callable(getattr(self, "get_config", None)) else {}
            if not isinstance(cfg, dict):
                cfg = {}

            items = [
                {"key": "fishing_detect_pixel", "label": "Fishing Detect Pixel", "value": cfg.get("fishing_detect_pixel", [1176, 836])},
                {"key": "fishing_click_position", "label": "Start Fishing Button", "value": cfg.get("fishing_click_position", [862, 843])},
                {"key": "fishing_midbar_sample_pos", "label": "Mid Bar Sample Position", "value": cfg.get("fishing_midbar_sample_pos", [955, 767])},
                {"key": "fishing_close_button_pos", "label": "Fishing Close Button", "value": cfg.get("fishing_close_button_pos", [1113, 342])},
                {"key": "fishing_bar_region", "label": "Fishing Bar Region", "value": cfg.get("fishing_bar_region", [757, 762, 405, 21])},
                {"key": "fishing_flarg_dialogue_box", "label": "Captain Flarg Dialogue Box", "value": cfg.get("fishing_flarg_dialogue_box", [1046, 782])},
                {"key": "fishing_shop_open_button", "label": "Open Fishing Shop", "value": cfg.get("fishing_shop_open_button", [616, 938])},
                {"key": "fishing_shop_sell_tab", "label": "Fishing Shop Sell Tab", "value": cfg.get("fishing_shop_sell_tab", [1285, 312])},
                {"key": "fishing_shop_close_button", "label": "Close Fishing Shop", "value": cfg.get("fishing_shop_close_button", [1458, 269])},
                {"key": "fishing_shop_first_fish", "label": "First Fish In Shop", "value": cfg.get("fishing_shop_first_fish", [827, 404])},
                {"key": "fishing_shop_sell_all_button", "label": "Sell All Button", "value": cfg.get("fishing_shop_sell_all_button", [662, 799])},
                {"key": "fishing_confirm_sell_all_button", "label": "Confirm Sell All Button", "value": cfg.get("fishing_confirm_sell_all_button", [800, 619])},
            ]
            self._calib_mgr.request_display_many(items=items, duration_ms=duration_ms)
            return True
        except Exception:
            return False


def launch_app(api_class, tracker=None):
    tracker = tracker or BiomeTracker()
    api = api_class(tracker)
    tracker.on_stats_update = api._emit_stats_update
    tracker.on_biome_update = api._emit_biome_update
    tracker.on_update_available = api._emit_update_available
    tracker.on_update_status = api._emit_update_status
    tracker.on_biome_confirm_request = api._request_biome_confirm
    tracker.on_status_change = lambda status: api._emit_macro_status()

    fe = get_frontend_entry()
    win_args = {
        "title": f"EndSol Macro {current_version}",
        "js_api": api,
        "width": 985, "height": 550,
        "min_size": (550, 500),
        "resizable": True, "frameless": False
    }
    # Use the file URL so Vite's relative JS/CSS/assets resolve correctly.
    # Inline HTML uses about:blank as its base and causes a black window.
    if fe and "url" in fe: win_args["url"] = fe["url"]
    elif fe and "html" in fe: win_args["html"] = fe["html"]
    else: win_args["url"] = "http://localhost:5173"

    window = webview.create_window(**win_args)
    threading.Thread(target=_apply_native_window_icon_when_ready, args=(win_args["title"],), daemon=True).start()
    api.set_window(window)

    # F1 = start, F2 = stop
    _VK_F1 = 0x70
    _VK_F2 = 0x71
    _hotkey_stop = threading.Event()
    _user32 = ctypes.windll.user32

    def _hotkey_poll_loop():
        f1_was = False
        f2_was = False
        while not _hotkey_stop.is_set():
            try:
                f1_now = bool(_user32.GetAsyncKeyState(_VK_F1) & 0x8000)
                f2_now = bool(_user32.GetAsyncKeyState(_VK_F2) & 0x8000)

                if f1_now and not f1_was:
                    def _do_start():
                        try:
                            if not api._tracker.detection_running:
                                api.set_biome_detection(True)
                                api._emit_shortcut("START")
                        except Exception:
                            pass
                    threading.Thread(target=_do_start, daemon=True).start()

                if f2_now and not f2_was:
                    def _do_stop():
                        try:
                            if api._tracker.detection_running:
                                api.set_biome_detection(False)
                                api._emit_shortcut("STOP")
                        except Exception:
                            pass
                    threading.Thread(target=_do_stop, daemon=True).start()

                f1_was = f1_now
                f2_was = f2_now
            except Exception:
                pass
            _hotkey_stop.wait(0.05)

    _hotkey_thread = threading.Thread(target=_hotkey_poll_loop, name="HotkeyPoll", daemon=True)
    _hotkey_thread.start()

    class _WvLog(logging.Handler):
        def emit(self, record):
            try: tracker.append_log(f"[pywebview] {record.getMessage()}")
            except Exception: pass
    logging.getLogger("pywebview").addHandler(_WvLog())

    # try edgechromium first, fall back to whatever else is available
    try:
        tracker.append_log("Starting pywebview (edgechromium)")
        webview.start(debug=False, gui="edgechromium", private_mode=False)
    except Exception as e:
        print(f"[Webview] edgechromium failed: {e}")
        tracker.append_log(f"edgechromium failed: {e}, retrying default...")
        try: webview.start(debug=False, private_mode=False)
        except Exception as e2:
            print(f"[Webview] Default backend also failed: {e2}")
            tracker.append_log(f"Default backend also failed: {e2}")

    return tracker

def stop_app(tracker):
    if tracker and getattr(tracker, "detection_running", False): tracker.stop_detection()

def main():
    ensure_workspace_files()
    
    tracker = None
    api = Api(tracker=None)
    api._setup_emergency_server()
    api._setup_emergency_hotkey()
    try:
        fe = get_frontend_entry()
        win_args = {
            "title": f"EndSol Macro {current_version}",
            "js_api": api,
            "width": 985, "height": 550,
            "min_size": (550, 500),
            "resizable": True, "frameless": False,
        }
        # Use the file URL so relative assets resolve in the fallback window.
        if "url" in fe: win_args["url"] = fe["url"]
        else: win_args["html"] = fe["html"]

        window = webview.create_window(**win_args)
        threading.Thread(target=_apply_native_window_icon_when_ready, args=(win_args["title"],), daemon=True).start()
        api._window = window

        def _background_init():
            nonlocal tracker
            try:
                from biome_tracker.core import BiomeTracker
                tracker = BiomeTracker()
                canonical = _read_cli_value("--endsol-target", "EndSolMacro.exe")
                old_pid_raw = _read_cli_value("--endsol-old-pid", "")
                try: old_pid = int(old_pid_raw) if old_pid_raw else None
                except Exception: old_pid = None

                if tracker.maybe_self_rename_to_canonical_exe(canonical, old_pid=old_pid):
                    window.destroy()
                    return

                if _cfg_bool(getattr(tracker, "config", {}), "auto_update_enabled", True):
                    if tracker.apply_startup_auto_update():
                        window.destroy()
                        return

                api._tracker = tracker
                tracker.on_stats_update = api._emit_stats_update
                tracker.on_biome_update = api._emit_biome_update
                tracker.on_update_available = api._emit_update_available
                tracker.on_update_status = api._emit_update_status
                tracker.on_biome_confirm_request = api._request_biome_confirm
                tracker.on_status_change = lambda status: api._emit_macro_status()
                tracker.on_remote_start = lambda: api.set_biome_detection(True)
                tracker.on_remote_stop = lambda: api.set_biome_detection(False)
                api.set_window(window)

            except Exception as exc:
                print(f"Background init error: {exc}")
                traceback.print_exc()

        # ---- F1/F2 hotkeys ----
        _VK_F1 = 0x70
        _VK_F2 = 0x71
        _hotkey_stop = threading.Event()
        _user32 = ctypes.windll.user32

        def _hotkey_poll_loop():
            f1_was = False
            f2_was = False
            while not _hotkey_stop.is_set():
                try:
                    if api._tracker is None:
                        _hotkey_stop.wait(0.2)
                        continue

                    f1_now = bool(_user32.GetAsyncKeyState(_VK_F1) & 0x8000)
                    f2_now = bool(_user32.GetAsyncKeyState(_VK_F2) & 0x8000)

                    if f1_now and not f1_was:
                        def _do_start():
                            try:
                                if not api._tracker.detection_running:
                                    api.set_biome_detection(True)
                                    api._emit_shortcut("START")
                            except Exception:
                                pass
                        threading.Thread(target=_do_start, daemon=True).start()

                    if f2_now and not f2_was:
                        def _do_stop():
                            try:
                                if api._tracker.detection_running:
                                    api.set_biome_detection(False)
                                    api._emit_shortcut("STOP")
                            except Exception:
                                pass
                        threading.Thread(target=_do_stop, daemon=True).start()

                    f1_was = f1_now
                    f2_was = f2_now
                except Exception:
                    pass
                _hotkey_stop.wait(0.05)

        threading.Thread(target=_hotkey_poll_loop, name="HotkeyPoll", daemon=True).start()

        class _WvLog(logging.Handler):
            def emit(self, record):
                try:
                    if tracker: tracker.append_log(f"[pywebview] {record.getMessage()}")
                except Exception: pass
        logging.getLogger("pywebview").addHandler(_WvLog())

        try:
            webview.start(func=_background_init, debug=False, gui="edgechromium", private_mode=False)
        except Exception as e:
            print(f"[Webview] edgechromium failed: {e}")
            try: webview.start(func=_background_init, debug=False, private_mode=False)
            except Exception as e2:
                print(f"[Webview] Default backend also failed: {e2}")

        return 0

    except KeyboardInterrupt:
        print("Exited (Ctrl+C)")
        return 130
    except Exception as exc:
        print(f"Fatal error: {exc}")
        traceback.print_exc()
        return 1
    finally:
        try: stop_app(tracker)
        except Exception: pass
        try: sync_config()
        except Exception: pass
        try: _hotkey_stop.set()
        except Exception: pass


if __name__ == "__main__":
    raise SystemExit(main())
