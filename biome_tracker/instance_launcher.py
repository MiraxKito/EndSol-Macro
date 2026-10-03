"""Built-in multi-instance launcher.

Replaces the external Avaluate MultipleRobloxInstances tool entirely:
  - holds the Roblox singleton mutex so additional clients can start;
  - holds an exclusive lock on RobloxCookies.dat (Error 773 protection);
  - stores per-account .ROBLOSECURITY session tokens encrypted with DPAPI
    (only decryptable under the current Windows user);
  - launches instances via a one-time authentication ticket, so each client
    logs into its own account automatically (flow verified against
    ic3w0lf22's Roblox-Account-Manager and Fleasion's roblox_auth).
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import threading
import time
from typing import Any
from urllib.parse import quote  # used in launch_account for the join URL

_LOCK = threading.RLock()
_TRACKER: Any = None

DEFAULT_PLACE_ID = "15532962292"  # Sol's RNG
_BACKUP_SUFFIX = ".endsol_backup"
_LOGIN_TIMEOUT_SEC = 600.0  # 2FA / Security verification can take a while
_ENTROPY = b"EndSolMacro-InstanceLauncher-v1"

_STATE: dict[str, Any] = {
    "mutex_held": False, "mutex_note": "", "mutex_exists": False,
    "cookie_lock_held": False, "cookie_lock_note": "",
    "login_active": False, "login_status": "", "login_username": "",
    "last_error": "", "last_launched": "", "mint_debug": "", "ps_debug": "",
    "singleton_clean": False, "singleton_note": "", "singleton_last": {},
}
_COOKIE_HANDLE: Any = None
_KERNEL32: Any = None

# one live client per account. A relaunch of the SAME account while its
# client is still running only opens a duplicate window that fights for the
# same session. Two layers:
#   1. live windows whose client log identifies the account (authoritative);
#   2. a TTL lock right after os.startfile — a fresh client's username is not
#      readable from its log for the first seconds, so a double-click on
#      Launch must still be refused.
_LAUNCH_LOCK_TTL = 120.0  # a client takes ~10-20 s to appear and log in
_RUNNING_LOCK: dict[str, float] = {}   # username -> time of the last successful launch
_RUN_SCAN: dict[str, Any] = {"at": 0.0, "map": None}  # window->username scan cache
_LAUNCHED_ACCOUNTS: dict[str, float] = {}  # usernames launched via the panel this app session
# launch-slot bookkeeping. _LAUNCH_CONFIRMED[username] = last time the
# launch watcher SAW the account's client alive; _LAUNCH_GEN[username]
# increments on every launch so a stale watcher can never release a newer
# launch's slot.
_LAUNCH_CONFIRMED: dict[str, float] = {}
_LAUNCH_GEN: dict[str, int] = {}
_NTDLL: Any = None
_AUTH_SESSION: Any = None
_LOGIN_PROC: Any = None
_LOGIN_THREAD: threading.Thread | None = None
_LOGIN_CANCEL = threading.Event()
_SINGLETON_THREAD: threading.Thread | None = None
_SINGLETON_STOP = threading.Event()

_SEC_PATTERNS = (
    r"(?:^|[\t ;\r\n])\.ROBLOSECURITY\s+([^\s;]+)",
    r"(?:^|[\t ;\r\n])\.ROBLOSECURITY=([^\s;]+)",
)


def attach_tracker(tracker: Any) -> None:
    global _TRACKER
    with _LOCK:
        _TRACKER = tracker


def _local_appdata() -> str:
    return os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")


def _launcher_dir() -> str:
    return os.path.join(_local_appdata(), "EndSolMacro", "launcher")


def _accounts_path() -> str:
    return os.path.join(_launcher_dir(), "accounts.json")


def _cookies_dat_path() -> str:
    return os.path.join(_local_appdata(), "Roblox", "LocalStorage", "RobloxCookies.dat")


def _find_client_exe() -> str | None:
    """Latest installed RobloxPlayerBeta.exe across known Versions folders.

    Vanilla Roblox and most Bloxstrap installs keep it under
    %LOCALAPPDATA%\\Roblox\\Versions; newer Bloxstrap setups use
    %LOCALAPPDATA%\\Bloxstrap\\Versions. The newest file wins.
    """
    candidates = []
    for root in ("Roblox", "Bloxstrap"):
        versions_dir = os.path.join(_local_appdata(), root, "Versions")
        try:
            for name in os.listdir(versions_dir):
                if not name.lower().startswith("version-"):
                    continue
                exe = os.path.join(versions_dir, name, "RobloxPlayerBeta.exe")
                if os.path.isfile(exe):
                    candidates.append((os.path.getmtime(exe), exe))
        except Exception:
            continue
    if not candidates:
        return None
    return max(candidates)[1]


# ---- DPAPI token protection -------------------------------------------------

def _dpapi_protect(token: str) -> str:
    try:
        import win32crypt
        blob = win32crypt.CryptProtectData(
            token.encode("utf-8"), "EndSolMacro", _ENTROPY, None, None, 0)
        return base64.b64encode(blob).decode("ascii")
    except ImportError:
        pass
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_char_p)]

    raw = token.encode("utf-8")
    data_in = _Blob(len(raw), ctypes.c_char_p(raw))
    entropy = _Blob(len(_ENTROPY), ctypes.c_char_p(_ENTROPY))
    out = _Blob()
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(out), "EndSolMacro", ctypes.byref(entropy),
        None, None, 0)
    if not ok:
        raise OSError("CryptProtectData failed")
    blob = ctypes.string_at(out.pbData, out.cbData)
    ctypes.windll.kernel32.LocalFree(out.pbData)
    return base64.b64encode(blob).decode("ascii")


def _dpapi_unprotect(blob_b64: str) -> str:
    raw = base64.b64decode(blob_b64)
    try:
        import win32crypt
        _desc, data = win32crypt.CryptUnprotectData(raw, _ENTROPY, None, None, 0)
        return data.decode("utf-8")
    except ImportError:
        pass
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_char_p)]

    data_in = _Blob(len(raw), ctypes.c_char_p(raw))
    entropy = _Blob(len(_ENTROPY), ctypes.c_char_p(_ENTROPY))
    out = _Blob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(out), None, ctypes.byref(entropy), None, None, 0)
    if not ok:
        raise OSError("CryptUnprotectData failed")
    data = ctypes.string_at(out.pbData, out.cbData)
    ctypes.windll.kernel32.LocalFree(out.pbData)
    return data.decode("utf-8")


def _load_accounts() -> list[dict[str, Any]]:
    try:
        with open(_accounts_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_accounts(accounts: list[dict[str, Any]]) -> None:
    os.makedirs(_launcher_dir(), exist_ok=True)
    tmp = _accounts_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(accounts, f, indent=2)
    os.replace(tmp, _accounts_path())


def _public_accounts() -> list[dict[str, Any]]:
    return [{
        "username": a.get("username", ""),
        "userid": a.get("userid", ""),
        "added_at": a.get("added_at", ""),
        "own_server": bool(a.get("own_server", False)),
    } for a in _load_accounts()]


def set_own_server(username: str, enabled: bool) -> dict[str, Any]:
    """Toggle the per-account "Own Server" preference.

    When ON, launching this account ignores the Webhook page link and
    joins the account's OWN private server for the game instead."""
    username = str(username or "").strip().lower()
    accounts = _load_accounts()
    hit = False
    for account in accounts:
        if account.get("username", "").strip().lower() == username:
            account["own_server"] = bool(enabled)
            hit = True
    if not hit:
        return {"success": False, "error": f"Account @{username} is not stored."}
    _save_accounts(accounts)
    return {"success": True, "username": username, "own_server": bool(enabled)}


# ---- login capture ----------------------------------------------------------

def _extract_roblosecurity(text: str) -> str:
    for pattern in _SEC_PATTERNS:
        m = re.search(pattern, text)
        if m:
            return str(m.group(1) or "").strip()
    return ""


def _dpapi_unprotect_raw(raw: bytes) -> bytes:
    """CryptUnprotectData WITHOUT entropy (the format Roblox itself uses)."""
    try:
        import win32crypt
        _desc, data = win32crypt.CryptUnprotectData(raw, None, None, None, 0)
        return data
    except ImportError:
        pass
    import ctypes
    from ctypes import wintypes

    class _Blob(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.c_char_p)]

    data_in = _Blob(len(raw), ctypes.c_char_p(raw))
    out = _Blob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(out), None, None, None, None, 0)
    if not ok:
        raise OSError("CryptUnprotectData failed")
    data = ctypes.string_at(out.pbData, out.cbData)
    ctypes.windll.kernel32.LocalFree(out.pbData)
    return data


def _read_cookie_token_from_dat(path: str) -> str:
    """Pull .ROBLOSECURITY out of the live RobloxCookies.dat.

    The standard client file is JSON {"CookiesData": base64} where the
    decoded blob is DPAPI-encrypted (CurrentUser) cookie text — decrypt it
    locally and parse. Plain-text netscape-style files are also accepted as
    a fallback.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            raw = f.read()
    except Exception:
        return ""
    token = _extract_roblosecurity(raw)
    if token:
        return token
    try:
        payload = json.loads(raw)
        blob = base64.b64decode(str(payload.get("CookiesData", "")))
    except Exception:
        return ""
    if not blob:
        return ""
    if os.name != "nt":
        return ""
    try:
        text = _dpapi_unprotect_raw(blob).decode("utf-8", errors="ignore")
    except Exception:
        return ""
    return _extract_roblosecurity(text)


def _validate_token(token: str) -> tuple[str, str]:
    """(userid, username) for a .ROBLOSECURITY token ('' on failure)."""
    try:
        from .base_support import safe_get
        response = safe_get(
            "https://users.roblox.com/v1/users/authenticated",
            headers={"Cookie": f".ROBLOSECURITY={token}"}, timeout=10)
        if response is not None and getattr(response, "status_code", 0) == 200:
            payload = response.json()
            return str(payload.get("id", "")), str(payload.get("name", "") or "")
    except Exception:
        pass
    return "", ""


def _restore_cookie_backup(had_backup: bool, dat_path: str, backup_path: str) -> None:
    try:
        if had_backup and os.path.isfile(backup_path):
            if os.path.isfile(dat_path):
                os.remove(dat_path)
            os.rename(backup_path, dat_path)
    except Exception:
        pass


def _login_watch_thread(had_backup: bool, dat_path: str, backup_path: str,
                        reacquire_cookie_lock: bool = False) -> None:
    deadline = time.time() + _LOGIN_TIMEOUT_SEC
    captured = False
    death_logged = False
    try:
        while not _LOGIN_CANCEL.is_set() and time.time() < deadline:
            time.sleep(2.0)
            # the login window can be killed by a single-instance
            # takeover when another Roblox client starts (e.g. launched from
            # a browser). Record that explicitly instead of leaving the user
            # staring at a silently dead window.
            if not death_logged and _LOGIN_PROC is not None:
                try:
                    if _LOGIN_PROC.poll() is not None:
                        death_logged = True
                        with _LOCK:
                            if not _STATE["login_username"]:
                                _STATE["login_status"] = ("The login window was closed before a login "
                                                          "was captured — press Add Account and try again.")
                        try:
                            log = getattr(_TRACKER, "append_log", None)
                            if callable(log):
                                log("[Launcher] Login window exited before a login was captured "
                                    "(closed manually or killed by another Roblox client).")
                        except Exception:
                            pass
                except Exception:
                    pass
            token = ""
            try:
                if os.path.isfile(dat_path):
                    token = _read_cookie_token_from_dat(dat_path)
            except Exception:
                token = ""
            if not token:
                continue
            userid, username = _validate_token(token)
            if not username:
                # Stale token read too early / not yet valid: keep waiting.
                continue
            try:
                accounts = [a for a in _load_accounts() if a.get("username") != username.lower()]
                accounts.append({
                    "username": username.lower(),
                    "userid": str(userid),
                    "token_enc": _dpapi_protect(token),
                    "added_at": time.strftime("%Y-%m-%d %H:%M"),
                })
                _save_accounts(accounts)
            except Exception as exc:
                with _LOCK:
                    _STATE["login_status"] = f"Could not save the account: {exc}"
                return
            captured = True
            with _LOCK:
                _STATE["login_username"] = username.lower()
                _STATE["login_status"] = f"Saved @{username.lower()}."
            # immediately prove the stored session can mint a launch
            # ticket — this is the exact operation Launch performs. A failure
            # here means the account can be re-added at once instead of
            # failing later on the Launch button.
            threading.Thread(target=_post_capture_mint_test,
                             args=(token, username.lower()),
                             name="EndSol launch-ticket self-test", daemon=True).start()
            return
        with _LOCK:
            if not _STATE["login_username"]:
                _STATE["login_status"] = "Login capture timed out — log into the Roblox window and try again."
    finally:
        if captured:
            # The fresh client owns the new cookie file now (it is usually
            # still open) — just drop our backup instead of touching the
            # live file; the session is already stored encrypted.
            try:
                if os.path.isfile(backup_path):
                    os.remove(backup_path)
            except Exception:
                pass
        else:
            _restore_cookie_backup(had_backup, dat_path, backup_path)
        if reacquire_cookie_lock:
            # Take back the cookie lock we released for the capture. The
            # singleton mutex stays held the whole time on purpose: with the
            # mutex free, a second Roblox start (e.g. from a browser) KILLS
            # the running login window — exactly what must not happen.
            try:
                _acquire_cookie_lock()
            except Exception:
                pass
        with _LOCK:
            _STATE["login_active"] = False


def _post_capture_mint_test(token: str, username: str) -> None:
    """Mint a throwaway ticket right after capture and report the result."""
    try:
        ticket = _mint_ticket(token)
        with _LOCK:
            detail = str(_STATE.get("mint_debug", "") or "")
        log = getattr(_TRACKER, "append_log", None)
        if callable(log):
            log("[Launcher] Launch-ticket self-test for @" + username + ": "
                + ("OK — the account is ready to launch." if ticket
                   else f"FAILED ({detail}) — re-add the account if Launch fails."))
    except Exception:
        pass


def start_login() -> dict[str, Any]:
    """Open a fresh Roblox window for the user to log into a NEW account."""
    global _LOGIN_THREAD, _LOGIN_PROC
    with _LOCK:
        if _STATE["login_active"]:
            return {"success": False, "error": "A login capture is already running."}
    try:
        from .base_support import roblox_top_windows
        if roblox_top_windows():
            return {"success": False,
                    "error": "Close all Roblox windows first — login capture replaces the shared cookie file."}
    except Exception:
        pass
    exe = _find_client_exe()
    if not exe:
        return {"success": False,
                "error": "RobloxPlayerBeta.exe not found under %LOCALAPPDATA%\\Roblox\\Versions or %LOCALAPPDATA%\\Bloxstrap\\Versions."}
    dat_path = _cookies_dat_path()
    backup_path = dat_path + _BACKUP_SUFFIX
    # The capture must RENAME the shared cookie file — impossible while
    # EndSol itself holds the Error-773 lock on it (Multiple-Instances
    # enabled + macro running). Release ONLY the cookie lock; the singleton
    # mutex MUST stay held, otherwise a second Roblox start (e.g. from a
    # browser) closes the running login window.
    with _LOCK:
        held_cookie_ours = _COOKIE_HANDLE is not None
    if held_cookie_ours:
        _release_cookie_lock()
    had_backup = False
    try:
        os.makedirs(os.path.dirname(dat_path), exist_ok=True)
        if os.path.isfile(dat_path):
            os.rename(dat_path, backup_path)
            had_backup = True
        import subprocess
        _LOGIN_PROC = subprocess.Popen([exe], cwd=os.path.dirname(exe), close_fds=True)
    except Exception as exc:
        _LOGIN_PROC = None
        _restore_cookie_backup(had_backup, dat_path, backup_path)
        if held_cookie_ours:
            try:
                _acquire_cookie_lock()
            except Exception:
                pass
        return {"success": False, "error": f"Failed to start Roblox: {exc}"}
    with _LOCK:
        _STATE.update(login_active=True, login_status="Waiting for login in the new Roblox window…",
                      login_username="", last_error="")
    _LOGIN_CANCEL.clear()
    _LOGIN_THREAD = threading.Thread(
        target=_login_watch_thread, args=(had_backup, dat_path, backup_path, held_cookie_ours),
        name="EndSol account capture", daemon=True)
    _LOGIN_THREAD.start()
    return {"success": True}


def cancel_login() -> dict[str, Any]:
    _LOGIN_CANCEL.set()
    return {"success": True}


def remove_account(username: str) -> dict[str, Any]:
    username = str(username or "").strip().lower()
    accounts = _load_accounts()
    remaining = [a for a in accounts if a.get("username") != username]
    if len(remaining) == len(accounts):
        return {"success": False, "error": f"Account @{username} is not stored."}
    _save_accounts(remaining)
    return {"success": True}


# ---- launch -----------------------------------------------------------------

def _auth_post(url: str, headers: dict[str, str], timeout: float = 15.0,
               json_body: Any = None) -> Any:
    """POST for Roblox auth endpoints on a DEDICATED session.

    base_support's shared session harvests cookies from every other request;
    a jarred cookie for auth.roblox.com could silently override the manual
    Cookie header in PreparedRequest.prepare_cookies. Auth requests get
    their own session (system proxy env still applies). One retry on
    connection-level failures; returns None when unreachable.

    json_body: the ticket endpoint REQUIRES Content-Type application/json
    ( an empty POST got HTTP 415 UnsupportedMediaType),
    so callers pass {}.
    """
    global _AUTH_SESSION
    import requests
    if _AUTH_SESSION is None:
        _AUTH_SESSION = requests.Session()
    last: Any = None
    for attempt in range(2):
        try:
            return _AUTH_SESSION.post(url, headers=headers, json=json_body, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            last = exc
            if attempt == 0:
                time.sleep(0.6)
    try:
        import sys
        print(f"[Launcher] auth POST {url} failed: {last}", file=sys.stderr)
    except Exception:
        pass
    return None


def _auth_get(url: str, headers: dict[str, str], timeout: float = 15.0) -> Any:
    """GET for Roblox pages/APIs that must see the ACCOUNT's cookies.

    Uses a FRESH session per call so cookies set by an earlier resolution
    step can never leak into the next step's request (verified locally:
    requests' cookiejar does NOT override an explicit Cookie header, but a
    fresh session is still the safest hygiene for auth traffic). Returns
    None when unreachable."""
    import requests
    try:
        with requests.Session() as session:
            return session.get(url, headers=headers, timeout=timeout)
    except requests.exceptions.RequestException as exc:
        try:
            import sys
            print(f"[Launcher] auth GET {url} failed: {exc}", file=sys.stderr)
        except Exception:
            pass
        return None


def _debug_snippet(resp: Any) -> str:
    try:
        body = str(getattr(resp, "text", "") or "")[:160].replace("\n", " ")
        return body or "(empty body)"
    except Exception:
        return "(unreadable body)"


def _mint_ticket(token: str) -> str:
    """One-time authentication ticket for a .ROBLOSECURITY token ('' on failure).

    every failure mode is recorded (HTTP status + body snippet) in
    _STATE["mint_debug"] and mirrored into the tracker log — the old version
    swallowed network errors, dead sessions and missing CSRF into a bare ""
    that was always reported as "session expired". Endpoint and flow follow
    the public reference implementations (depthso/Roblox-launcher, QuasarRBX
    API list): POST auth.roblox.com/v1/authentication-ticket with the
    .ROBLOSECURITY cookie, expect 403 + x-csrf-token, retry with the CSRF
    header and read rbx-authentication-ticket. The POST body is {} with
    Content-Type application/json ( an empty POST got
    HTTP 415 UnsupportedMediaType on the ticket step).
    """
    if not token:
        with _LOCK:
            _STATE["mint_debug"] = "no token stored"
        return ""
    url = "https://auth.roblox.com/v1/authentication-ticket"
    headers = {
        "Cookie": f".ROBLOSECURITY={token}",
        "Origin": "https://www.roblox.com",
        "Referer": "https://www.roblox.com/games",
    }
    debug: list[str] = []
    ticket = ""
    try:
        first = _auth_post(url, headers, json_body={})
        csrf = ""
        if first is None:
            debug.append("preflight unreachable (network/TLS/proxy)")
        else:
            code = int(getattr(first, "status_code", 0) or 0)
            csrf = str((getattr(first, "headers", {}) or {}).get("x-csrf-token", "") or "")
            debug.append(f"preflight HTTP {code}"
                         + (" +csrf" if csrf else f"; body: {_debug_snippet(first)}"))
        if csrf:
            second = _auth_post(url, {**headers, "X-CSRF-TOKEN": csrf}, json_body={})
            if second is None:
                debug.append("ticket request unreachable (network)")
            else:
                code = int(getattr(second, "status_code", 0) or 0)
                ticket = str((getattr(second, "headers", {}) or {})
                             .get("rbx-authentication-ticket", "") or "")
                debug.append(f"ticket HTTP {code}" + (" OK" if ticket
                            else f"; body: {_debug_snippet(second)}"))
    except Exception as exc:
        debug.append(f"exception: {exc}")
    text = "; ".join(debug) or "no attempt"
    with _LOCK:
        _STATE["mint_debug"] = text
    try:
        log = getattr(_TRACKER, "append_log", None)
        # log failures only — the success line fired on every launch.
        if callable(log) and not ticket:
            log(f"[Launcher] Auth ticket request FAILED: {text}")
    except Exception:
        pass
    return ticket


def _parse_private_server_link(link: str) -> dict[str, str] | None:
    """Extract placeId + link code from the user's private-server link.

    Accepts the same formats as the reconnect deep-link builder:
      - https://www.roblox.com/games/{placeId}/...?privateServerLinkCode=...
      - https://www.roblox.com/share?code=...&type=Server
      - roblox://placeID=...&linkCode=...
    Returns None when the string holds no usable link code.
    """
    from urllib.parse import parse_qs, urlparse
    raw = str(link or "").strip()
    if not raw:
        return None
    try:
        parsed = urlparse(raw)
        query_ci = {str(k).strip().lower(): v for k, v in parse_qs(parsed.query).items()}
        path_l = (parsed.path or "").lower()
        place_m = re.search(r"/games/(\d+)", path_l) or re.search(r"placeID=(\d+)", raw, flags=re.IGNORECASE)
        place_id = place_m.group(1) if place_m else ""
        link_code = ""
        if query_ci.get("privateserverlinkcode"):
            link_code = str(query_ci["privateserverlinkcode"][0]).strip()
        elif query_ci.get("linkcode"):
            link_code = str(query_ci["linkcode"][0]).strip()
        elif query_ci.get("code"):
            link_type = str(query_ci.get("type", [""])[0]).strip().lower()
            if link_type in ("", "server"):
                link_code = str(query_ci["code"][0]).strip()
        if not link_code:
            m = re.search(r"privateServerLinkCode=([^&\s]+)", raw, flags=re.IGNORECASE)
            if m:
                link_code = m.group(1).strip()
        if not link_code:
            m = re.search(r"linkCode=([^&\s]+)", raw, flags=re.IGNORECASE)
            if m:
                link_code = m.group(1).strip()
        if not link_code:
            m = re.search(r"code=([^&\s]+)", raw, flags=re.IGNORECASE)
            if m and ("navigation/share_links" in raw.lower() or path_l.startswith("/share")):
                link_code = m.group(1).strip()
        if not link_code:
            return None
        is_share = path_l.startswith("/share") or "navigation/share_links" in raw.lower() or "share-links" in raw.lower()
        return {"place_id": place_id or DEFAULT_PLACE_ID, "link_code": link_code,
                "kind": "share" if is_share else "private"}
    except Exception:
        return None


def _resolve_private_api(token: str, place_id: str, link_code: str,
                         debug: list[str]) -> str:
    """resolve the accessCode through the games API — no page scraping.

    GET https://games.roblox.com/v1/games/{placeId}/private-servers with the
    account's .ROBLOSECURITY cookie returns the list of private servers that
    account can join; every entry carries its accessCode (this is exactly
    what the website's server list uses — ServerList.js joins via
    entry.accessCode). The LINK's server is found by MATCHING the entry's
    linkCode field against our privateServerLinkCode.

    WARNING learned the hard way ( every account joined
    its OWN private server): this endpoint has NO linkCode query filter —
    the official docs list only cursor/excludeFriendServers, and an unknown
    query param is silently ignored. Taking data[0] (as LaunchRoblox's
    getAccessCode does) returns an arbitrary server — the account's own
    VIP server. We must scan the list and match linkCode explicitly; if the
    linked server is not in the list, the account has no access and we
    refuse instead of guessing.
    """
    servers = _scan_private_servers(token, place_id, debug)
    if servers is None:
        return ""
    want = str(link_code).strip().lower()
    scanned = len(servers)
    saw_link_field = any(e.get("linkCode") for e in servers if isinstance(e, dict))
    for entry in servers:
        if not isinstance(entry, dict):
            continue
        entry_link = str(entry.get("linkCode") or "").strip().lower()
        if entry_link and entry_link == want:
            access = str(entry.get("accessCode") or "")
            if access:
                return access
    if not saw_link_field:
        debug.append(f"games API: HTTP 200, {scanned} server(s) scanned, "
                     "no entry exposes a linkCode field — cannot match safely")
    elif scanned:
        debug.append(f"games API: HTTP 200, {scanned} server(s) scanned, "
                     "linkCode NOT among them (link not shared with this "
                     "account, or expired)")
    else:
        debug.append("games API: HTTP 200, empty private-server list")
    return ""


def _scan_private_servers(token: str, place_id: str, debug: list[str]) -> list[Any] | None:
    """Fetch EVERY private server the account can join for a place.

    GET https://games.roblox.com/v1/games/{placeId}/private-servers with the
    account cookie, following nextPageCursor. Returns the raw entry list, or
    None on failure (diagnostics already appended). Entries carry accessCode
    per server (the website's server list joins via entry.accessCode) plus
    owner info — this powers BOTH the best-effort linkCode match and the
    "Own Server" launch."""
    url = f"https://games.roblox.com/v1/games/{place_id}/private-servers"
    headers = {"Cookie": f".ROBLOSECURITY={token}"}
    cursor = ""
    entries: list[Any] = []
    for _page in range(6):  # lists are small; 6 pages is a hard safety cap
        page_url = f"{url}?cursor={quote(cursor, safe='')}" if cursor else url
        resp = _auth_get(page_url, headers=headers, timeout=15)
        if resp is None:
            debug.append("games API unreachable (network/TLS/proxy)")
            return None
        code = int(getattr(resp, "status_code", 0) or 0)
        try:
            data = resp.json()
        except Exception:
            data = None
        if code != 200 or not isinstance(data, dict):
            debug.append(f"games API: HTTP {code}, body: {str(data)[:160] or '(no JSON body)'}")
            return None
        rows = data.get("data")
        if not isinstance(rows, list):
            debug.append(f"games API: HTTP {code}, unexpected body: {str(data)[:160]}")
            return None
        entries.extend(rows)
        cursor = str(data.get("nextPageCursor") or "")
        if not cursor:
            break
    return entries


def _entry_owner_id(entry: Any) -> str:
    """Owner user id of a private-server list entry ('' when absent)."""
    if not isinstance(entry, dict):
        return ""
    owner = entry.get("owner")
    if isinstance(owner, dict):
        return str(owner.get("id") or owner.get("userId") or "").strip()
    return str(entry.get("ownerId") or "").strip()


def _resolve_own_server_code(token: str, user_id: str, place_id: str,
                             debug: list[str]) -> str:
    """Own Server: find the account's OWN private server for the game
    and return its accessCode ('' when the account has none)."""
    if not str(user_id or "").strip():
        debug.append("own server: no user id for this account")
        return ""
    servers = _scan_private_servers(token, place_id, debug)
    if servers is None:
        return ""
    want = str(user_id).strip()
    owned = [e for e in servers if isinstance(e, dict) and _entry_owner_id(e) == want]
    if not owned:
        debug.append(f"own server: {len(servers)} server(s) scanned, none owned by "
                     f"user {want} — this account has no private server for the game")
        return ""
    for entry in owned:
        access = str(entry.get("accessCode") or "")
        if access:
            debug.append(f"own server: accessCode resolved for user {want} "
                         f"(vipServerId {entry.get('vipServerId', '?')})")
            return access
    debug.append("own server: found the account's server but it exposes no "
                 "accessCode (maybe not running yet)")
    return ""


_SHARELINKS_API = "https://apis.roblox.com/sharelinks/v1/resolve-link"


def _place_id_for_universe(token: str, universe_id: str, debug: list[str]) -> str:
    """Root place id of a universe ('' when unavailable)."""
    resp = _auth_get(f"https://games.roblox.com/v1/games?universeIds={quote(str(universe_id), safe='')}",
                     headers={"Cookie": f".ROBLOSECURITY={token}"}, timeout=15)
    try:
        data = resp.json() if resp is not None else None
        rows = data.get("data") if isinstance(data, dict) else None
        if isinstance(rows, list) and rows and isinstance(rows[0], dict):
            return str(rows[0].get("rootPlaceId") or "")
    except Exception:
        pass
    debug.append(f"universe {universe_id}: root place lookup failed")
    return ""


def _resolve_share_via_api(token: str, share_code: str, debug: list[str]) -> dict[str, str] | None:
    """resolve a SHARE code through Roblox's own share-links API.

    The share-links page resolves codes with
    POST https://apis.roblox.com/sharelinks/v1/resolve-link
    {"linkId": <code>, "linkType": "Server"} (verified in the site's
    DeeplinkParser bundle: the response's privateServerInviteData carries
    universeId / status Valid|Expired / linkCode, and the site then navigates
    to games/{place}?privateServerLinkCode={linkCode}). Anonymous probes get
    403 "XSRF token invalid", so the account cookie + CSRF token unlock it.
    Returns {"link_code", "place_id", "status"} or None on failure."""
    headers = {"Cookie": f".ROBLOSECURITY={token}",
               "Referer": "https://www.roblox.com/games"}
    body = {"linkId": str(share_code), "linkType": "Server"}
    resp = _auth_post(_SHARELINKS_API, headers, json_body=body)
    if resp is None:
        debug.append("share-links API unreachable (network/TLS/proxy)")
        return None
    code = int(getattr(resp, "status_code", 0) or 0)
    csrf = str((getattr(resp, "headers", {}) or {}).get("x-csrf-token", "") or "")
    if code == 403 and csrf:
        resp = _auth_post(_SHARELINKS_API, {**headers, "X-CSRF-TOKEN": csrf}, json_body=body)
        if resp is None:
            debug.append("share-links API unreachable on the csrf retry")
            return None
        code = int(getattr(resp, "status_code", 0) or 0)
    try:
        data = resp.json()
    except Exception:
        data = None
    invite = None
    if isinstance(data, dict):
        invite = data.get("privateServerInviteData")
        if not isinstance(invite, dict) and isinstance(data.get("data"), dict):
            invite = data["data"].get("privateServerInviteData")
    if not isinstance(invite, dict):
        debug.append(f"share-links API: HTTP {code}, body: {str(data)[:160] or '(no JSON body)'}")
        return None
    status = str(invite.get("status", "") or "")
    link_code = str(invite.get("linkCode", "") or "").strip()
    universe_id = str(invite.get("universeId", "") or "").strip()
    if not link_code:
        debug.append(f"share-links API: HTTP {code}, status {status or 'unknown'}, "
                     "no linkCode in response")
        return None
    place_id = _place_id_for_universe(token, universe_id, debug) if universe_id else ""
    debug.append(f"share-links API: HTTP {code}, status {status or 'unknown'}, linkCode resolved"
                 + (f", place {place_id}" if place_id else ""))
    return {"link_code": link_code, "place_id": place_id or DEFAULT_PLACE_ID, "status": status}


def _resolve_private_access_code(token: str, place_id: str, link_code: str,
                                 kind: str = "private") -> str:
    """Best-effort explicit accessCode for a privateServerLinkCode ('' = none).

    the join itself does NOT need this — PlaceLauncher resolves the
    linkCode server-side (the website joins with accessCode=null + linkCode).
    When the games-API scan DOES find an explicit accessCode we attach it as
    belt-and-braces; a miss is NOT an error. NEVER guess: an earlier build's data[0] guess made
    every account join its OWN VIP server (the endpoint has no linkCode
    filter and its entries do not even expose a linkCode field)."""
    debug: list[str] = []
    try:
        result = _resolve_private_full(token, place_id, link_code, debug)
        _record_ps_debug(debug)
        _log_ps(debug, ok=bool(result), soft=True)
        return result
    except Exception as exc:
        debug.append(f"exception: {exc}")
        _record_ps_debug(debug)
        _log_ps(debug, ok=False, soft=True)
        return ""


def _resolve_private_full(token: str, place_id: str, link_code: str,
                          debug: list[str]) -> str:
    """API-first resolution, legacy page scrape only as the fallback."""
    access = _resolve_private_api(token, place_id, link_code, debug)
    if access:
        return access
    debug.append("falling back to the legacy game-page scrape")
    return _resolve_private_link_code(token, place_id, link_code, debug)


def _resolve_private_link_code(token: str, place_id: str, link_code: str,
                               debug: list[str] | None = None) -> str:
    """LEGACY fallback: game page with ?privateServerLinkCode= embeds the code.

    Dead on current Roblox pages (no joinPrivateGame embed anymore), kept as
    a safety net in case the games API is unreachable or changes."""
    try:
        url = f"https://www.roblox.com/games/{place_id}?privateServerLinkCode={link_code}"
        headers = {"Cookie": f".ROBLOSECURITY={token}",
                   "Referer": "https://www.roblox.com/games"}
        resp = _auth_get(url, headers=headers, timeout=15)
        csrf = ""
        try:
            csrf = str((getattr(resp, "headers", {}) or {}).get("x-csrf-token", "") or "")
        except Exception:
            csrf = ""
        if csrf:
            resp = _auth_get(url, headers={**headers, "X-CSRF-TOKEN": csrf}, timeout=15)
        if resp is None:
            if debug is not None:
                debug.append("game page unreachable (network/TLS/proxy)")
            _record_ps_debug(debug or ["game page unreachable"])
            return ""
        code = int(getattr(resp, "status_code", 0) or 0)
        text = str(getattr(resp, "text", "") or "")
        # UUID-shaped code first (reference regex), then a looser fallback.
        m = re.search(r"Roblox\.GameLauncher\.joinPrivateGame\(\d+,\s*'(\w+-\w+-\w+-\w+-\w+)'", text)
        if not m:
            m = re.search(r"joinPrivateGame\(\d+,\s*['\"]([^'\"]+)['\"]", text)
        access = m.group(1) if m else ""
        if debug is not None:
            debug.append(f"game page: HTTP {code}, {len(text)} chars"
                         + (", access code resolved" if access
                            else ", NO joinPrivateGame script found"))
        _record_ps_debug(debug)
        return access
    except Exception as exc:
        if debug is not None:
            debug.append(f"game page exception: {exc}")
        _record_ps_debug(debug or [f"exception: {exc}"])
        return ""


def _record_ps_debug(debug: list[str] | str) -> None:
    text = "; ".join(debug) if isinstance(debug, list) else str(debug)
    with _LOCK:
        _STATE["ps_debug"] = text


def _log_ps(debug: list[str], ok: bool = True, soft: bool = False) -> None:
    """One combined tracker-log line, FAILURES ONLY (the success line
    fired on every launch and drowned the log; diagnostics stay in
    _STATE["ps_debug"] for the UI either way).

    soft=True: a best-effort miss that does NOT abort the launch —
    PlaceLauncher resolves the linkCode server-side, so wording it as
    "FAILED" scared users whose client joined fine ()."""
    try:
        if ok or not debug:
            return
        prefix = ("[Launcher] Private server: no explicit accessCode matched — joining "
                  "via linkCode (this is normal): " if soft else
                  "[Launcher] Private server resolve FAILED: ")
        log = getattr(_TRACKER, "append_log", None)
        if callable(log):
            log(prefix + "; ".join(debug))
    except Exception:
        pass


def _build_launch_link(ticket: str, join_url: str = "") -> str:
    bid = 130033680605
    link = (f"roblox-player:1+launchmode:play+gameinfo:{ticket}"
            f"+launchtime:{int(time.time() * 1000)}")
    if join_url:
        link += f"+placelauncherurl:{quote(join_url, safe='')}"
    link += f"+browsertrackerid:{bid}+robloxLocale:en_us+gameLocale:en_us+channel:"
    return link


def _running_accounts() -> dict[str, list[int]]:
    """Map account username -> pids of live Roblox windows running it.

    Uses the SAME log->PID mapping and TutorialCursor username reader as the
    multi-instance monitor (one source of truth for "which account is this
    window"). The scan touches the Roblox logs directory, so it is cached for
    a few seconds — the UI polls the state every 2 s and must not re-scan
    logs on every poll. Non-Windows (tests) never scans and returns {}."""
    now = time.time()
    with _LOCK:
        cached = _RUN_SCAN.get("map")
        if cached is not None and now - float(_RUN_SCAN.get("at") or 0.0) < 3.0:
            return dict(cached)
    found: dict[str, list[int]] = {}
    if os.name == "nt":
        try:
            from . import multi_instance as _mi
            pids = [int(w["pid"]) for w in _mi._windows()]
            for pid, path in (_mi._map_logs_to_pids(pids) if pids else {}).items():
                name = str(_mi._log_username(path) or "").strip().lower()
                if name:
                    found.setdefault(name, []).append(int(pid))
        except Exception:
            found = {}
    with _LOCK:
        _RUN_SCAN["at"] = now
        _RUN_SCAN["map"] = dict(found)
    return found


def launcher_launched_accounts() -> set[str]:
    """usernames launched through the built-in launcher this app session.

    terminate_roblox_processes uses this to recognize panel-launched clients
    that must survive a reconnect / failsafe kill even when the
    Multiple-Instances preference is OFF (the launcher intentionally opens an
    extra window in that case — it strips the Roblox singleton handles on
    every launch regardless of the mode)."""
    with _LOCK:
        return set(_LAUNCHED_ACCOUNTS)


# remember HOW each account was last launched, so the multi-instance
# webhook can offer a human "Join Server" link for the same private server.
_JOIN_INFO: dict[str, dict[str, str]] = {}   # username -> {"kind", "place_id", "link_code"}


def _launch_fail(username: str, payload: dict[str, Any]) -> dict[str, Any]:
    """release the early launch slot after a failed launch attempt so
    the user can retry immediately (the slot is claimed at click time,
    before the slow private-server resolve)."""
    with _LOCK:
        _RUNNING_LOCK.pop(username, None)
        _LAUNCH_CONFIRMED.pop(username, None)
    return payload


def _start_launch_watch(username: str, gen: int) -> None:
    """watch the launched client and release the launch slot as soon as
    the client window is gone.

    While the client runs, the watcher refreshes _LAUNCH_CONFIRMED, which
    makes the live scan the single source of truth for the UI's Running
    state — closing the client clears it within one UI poll instead of
    sticking for the rest of the TTL lock."""
    def _work() -> None:
        seen_live = False
        # Never-seen deadline: the client takes ~10-20 s to appear and log
        # in; give it the full TTL plus margin before declaring a dead launch.
        deadline = time.time() + _LAUNCH_LOCK_TTL + 30.0
        while True:
            time.sleep(2.0)
            with _LOCK:
                if int(_LAUNCH_GEN.get(username, 0)) != gen:
                    return  # a newer launch owns this slot now
            live = username in _running_accounts()
            if live:
                seen_live = True
                with _LOCK:
                    _LAUNCH_CONFIRMED[username] = time.time()
                continue
            if seen_live:
                with _LOCK:
                    _RUNNING_LOCK.pop(username, None)
                    _LAUNCH_CONFIRMED.pop(username, None)
                try:
                    log = getattr(_TRACKER, "append_log", None)
                    if callable(log):
                        log(f"[Launcher] @{username}'s client closed — Launch is available again.")
                except Exception:
                    pass
                return
            if time.time() > deadline:
                # The client never showed up (launch died silently) — release.
                with _LOCK:
                    if int(_LAUNCH_GEN.get(username, 0)) == gen:
                        _RUNNING_LOCK.pop(username, None)
                return
    threading.Thread(target=_work, name=f"EndSol launch watch {username}", daemon=True).start()


def launch_account(username: str, ps_link: str = "", own_server: bool | None = None,
                   rejoin: bool = False) -> dict[str, Any]:
    username = str(username or "").strip().lower()
    account = next((a for a in _load_accounts() if a.get("username") == username), None)
    if not account:
        return {"success": False, "error": f"Account @{username} is not stored."}
    # refuse a second client of the SAME account while one is running.
    # a DISCONNECT REJOIN skips these checks — the old client just died
    # (the monitor saw the disconnect line), but its TTL entry and its log
    # mapping can still linger for a few seconds and would wrongly refuse.
    if not rejoin:
        live_pids = (_running_accounts().get(username) or [])
        if live_pids:
            return {"success": False, "locked": True,
                    "error": (f"@{username} already has a running Roblox client (PID {live_pids[0]}) — "
                              "close that window before launching this account again.")}
        with _LOCK:
            # Prune stale TTL entries while we are here (the dict stays tiny).
            now_ts = time.time()
            for key in [k for k, t in _RUNNING_LOCK.items() if now_ts - t > _LAUNCH_LOCK_TTL * 2]:
                _RUNNING_LOCK.pop(key, None)
                _LAUNCH_CONFIRMED.pop(key, None)
            last_launch = float(_RUNNING_LOCK.get(username, 0.0))
            confirmed_at = float(_LAUNCH_CONFIRMED.get(username, 0.0))
        if last_launch and confirmed_at > last_launch:
            # the client was already seen ALIVE after that launch and no
            # live window maps to the account now — it was closed (or it
            # crashed). Release the slot immediately instead of keeping the
            # Launch button stuck on "Running" for the rest of the TTL
            # ( both clients closed, the button stayed
            # Running and Launch was refused although Roblox was closed).
            with _LOCK:
                _RUNNING_LOCK.pop(username, None)
                _LAUNCH_CONFIRMED.pop(username, None)
        else:
            last_launch = float(_RUNNING_LOCK.get(username, 0.0))
            if last_launch and now_ts - last_launch < _LAUNCH_LOCK_TTL:
                wait_left = int(_LAUNCH_LOCK_TTL - (now_ts - last_launch)) + 1
                return {"success": False, "locked": True,
                        "error": (f"@{username} was launched {int(now_ts - last_launch)} s ago and its client "
                                  f"is still starting up — try again in ~{wait_left} s. The lock clears "
                                  "by itself once the client is detected running or the wait expires.")}
    # claim the launch slot IMMEDIATELY — before the private-server
    # resolve, which can spend tens of seconds on HTTP round-trips. The UI
    # polls the launcher state every 2 s, so the button flips to "Running"
    # from the fresh lock long before the slow resolve answers, and a second
    # click during the resolve is refused instead of firing a duplicate
    # client. Every failure path below releases the slot again.
    with _LOCK:
        _RUNNING_LOCK[username] = time.time()
        _LAUNCH_CONFIRMED.pop(username, None)
        _LAUNCH_GEN[username] = int(_LAUNCH_GEN.get(username, 0)) + 1
        _launch_gen = int(_LAUNCH_GEN[username])
    # "Own Server": the per-account preference wins over the Webhook
    # link — the account joins its OWN private server for the game.
    if own_server is None:
        own_server = bool(account.get("own_server", False))
    ps = None if own_server else _parse_private_server_link(ps_link)
    if os.name == "nt":
        # ALWAYS start the singleton stripper before launching, regardless of
        # the Multiple-Instances toggle: the watcher strips the
        # ROBLOX_singletonEvent/Mutex handles out of every running client, so
        # the launched client cannot kill existing instances (and they cannot
        # kill it). The old mutex-hold approach is dead on current clients.
        try:
            ensure_locks()
        except Exception:
            pass
        # Never trust the cached "already stripped" verdict at launch time:
        # a clean scan from the client's first seconds proves nothing (the
        # handles may be created later). Force a full re-scan of every
        # running client NOW, so the takeover cannot kill any of them.
        force_singleton_rescan()
        if not _ensure_singleton_ready(timeout=10.0):
            with _LOCK:
                note = str(_STATE.get("singleton_note") or _STATE.get("mutex_note") or "")
            msg = ("Could not strip the Roblox singleton handles "
                   f"({note or 'unknown error'}) — existing clients could be closed by "
                   "the takeover. Check the log or try again.")
            try:
                log = getattr(_TRACKER, "append_log", None)
                if callable(log):
                    log(f"[Launcher] {msg}")
            except Exception:
                pass
            return _launch_fail(username, {"success": False, "error": msg})
        # the gate passing above means "last strip pass was clean", but a
        # clean pass can also mean the scan never SAW the running client
        # (renamed exe, Microsoft Store version, psutil/AV failure) — in that
        # case the old client is UNPROTECTED and this very launch would kill
        # it (exactly the friend's report: panel launch succeeds, the old
        # window closes as the new one appears). Cross-check: a visible
        # Roblox client window with ZERO matched client processes is a hard
        # refusal, not a clean state.
        try:
            from .base_support import roblox_top_windows
            live_windows = roblox_top_windows()
            live_pids = _roblox_pids()
            if live_windows and not live_pids:
                msg = ("Roblox client windows are visible, but no RobloxPlayerBeta.exe process "
                       "was matched — the singleton stripper cannot protect them (renamed client, "
                       "Microsoft Store version, or psutil failure). Launch refused to protect the "
                       "running window.")
                try:
                    log = getattr(_TRACKER, "append_log", None)
                    if callable(log):
                        log(f"[Launcher] {msg}")
                except Exception:
                    pass
                return _launch_fail(username, {"success": False, "error": msg})
            # one diagnostic line per launch — the strip note tells
            # exactly what the watcher saw ("no singleton handles present"
            # with a client running is the suspicious signature).
            with _LOCK:
                s_note = str(_STATE.get("mutex_note") or "")
            try:
                log = getattr(_TRACKER, "append_log", None)
                if callable(log):
                    log(f"[Launcher] Singleton: {len(live_pids)} client process(es), "
                        f"{len(live_windows)} window(s) — {s_note or 'no strip data yet'}")
            except Exception:
                pass
        except Exception:
            pass
    token = _dpapi_unprotect(str(account.get("token_enc", "")))
    if not token:
        return _launch_fail(username, {"success": False,
                                        "error": f"No stored session for @{username} — press Add Account and log into this account again."})
    ticket = _mint_ticket(token)
    if not ticket:
        # distinguish a dead session from a transient Roblox/network
        # problem instead of always blaming the session.
        _uid, name = _validate_token(token)
        if not name:
            return _launch_fail(username, {"success": False,
                            "error": (f"The stored session for @{username} is no longer valid "
                                      "(Roblox rejects it) — press Add Account and log into this account again.")})
        with _LOCK:
            detail = str(_STATE.get("mint_debug", "") or "")
        return _launch_fail(username, {"success": False,
                        "error": (f"Roblox refused to mint a launch ticket for @{username} "
                                  f"({detail or 'unknown reason'}) — the session itself is alive; "
                                  "try again in a minute.")})
    join_url = ""
    if own_server:
        # join the account's OWN private server — resolve its
        # accessCode from the private-servers list (entries carry
        # accessCode; the website's server list joins the same way).
        debug: list[str] = []
        user_id = str(account.get("userid", "") or "").strip()
        if not user_id:
            _uid, _name = _validate_token(token)
            user_id = str(_uid or "")
        access_code = _resolve_own_server_code(token, user_id, DEFAULT_PLACE_ID, debug)
        _record_ps_debug(debug)
        _log_ps(debug, ok=bool(access_code))
        if not access_code:
            detail = "; ".join(debug) or "unknown"
            return _launch_fail(username, {"success": False,
                            "error": (f"Could not find @{username}'s own private server ({detail}) — "
                                      "create a VIP server for this account or turn Own Server off.")})
        join_url = (f"https://assetgame.roblox.com/game/PlaceLauncher.ashx"
                    f"?request=RequestPrivateGame&placeId={DEFAULT_PLACE_ID}"
                    f"&accessCode={access_code}")
        # remember HOW this account joined, so the multi-instance
        # webhook can offer a "Join Server" link for the same server.
        with _LOCK:
            _JOIN_INFO[username] = {"kind": "own",
                                    "place_id": str(DEFAULT_PLACE_ID),
                                    "link_code": ""}
    elif ps:
        place_id = str(ps["place_id"])
        link_code = str(ps["link_code"])
        kind = str(ps.get("kind", "private"))
        if kind == "share":
            # share codes resolve through Roblox's own share-links API
            # (POST /sharelinks/v1/resolve-link — the SAME endpoint the
            # share-links page uses) into a privateServerLinkCode, which
            # then goes to PlaceLauncher like any private link.
            share_debug: list[str] = []
            resolved = _resolve_share_via_api(token, link_code, share_debug)
            _record_ps_debug(share_debug)
            _log_ps(share_debug, ok=bool(resolved))
            if not resolved:
                with _LOCK:
                    detail = str(_STATE.get("ps_debug", "") or "")
                hint = (" Tip: open the share link in a browser once — when the address turns into "
                        "https://www.roblox.com/games/15532962292/...?privateServerLinkCode=..., "
                        "paste THAT link into the Webhook page — it resolves reliably.")
                return _launch_fail(username, {"success": False,
                                "error": (f"Could not resolve the share link for @{username} "
                                          f"({detail or 'unknown'}) — a share link cannot be joined "
                                          "directly." + hint)})
            place_id = resolved["place_id"] or place_id
            link_code = resolved["link_code"]
        # A privateServerLinkCode goes to PlaceLauncher AS IS —
        # the website joins private servers with accessCode=null +
        # linkCode and PlaceLauncher resolves it server-side for the
        # authenticated user (verified in the GameLaunch bundle:
        # joinPrivateGame(placeId, null, linkCode)). The games-API match
        # below is best-effort ONLY: when it returns an explicit
        # accessCode we attach it, but a miss is NOT an error — an earlier build
        # data[0] guess made every account join its OWN VIP server
        # (the endpoint has no linkCode filter and its entries do not
        # even expose a linkCode field).
        access_code = _resolve_private_access_code(token, place_id, link_code, "private")
        join_url = (f"https://assetgame.roblox.com/game/PlaceLauncher.ashx"
                    f"?request=RequestPrivateGame&placeId={place_id}")
        if access_code:
            join_url += f"&accessCode={access_code}"
        join_url += f"&linkCode={quote(link_code, safe='')}"
        final_place = place_id
        # the resolved linkCode identifies the SAME private server the
        # client just joined — the website opens it via the games page URL.
        with _LOCK:
            _JOIN_INFO[username] = {"kind": str(kind),
                                    "place_id": str(place_id),
                                    "link_code": str(link_code)}
    else:
        final_place = ""
    try:
        os.startfile(_build_launch_link(ticket, join_url))  # type: ignore[attr-defined]
    except Exception as exc:
        return _launch_fail(username, {"success": False, "error": f"Failed to open the launch link: {exc}"})
    with _LOCK:
        _RUNNING_LOCK[username] = time.time()  # one-client-per-account lock
        _LAUNCHED_ACCOUNTS[username] = time.time()  # remember panel launches
        if own_server:
            _STATE["last_launched"] = f"@{username} -> own private server (place {DEFAULT_PLACE_ID})"
        elif ps:
            _STATE["last_launched"] = f"@{username} -> private server (place {final_place})"
        else:
            _STATE["last_launched"] = f"@{username} -> home (no private server link set)"
    _start_launch_watch(username, _launch_gen)  # release the slot when the client closes
    return {"success": True}


def get_join_info(username: str) -> dict[str, str]:
    """how the account was last launched (best-effort, in-memory).
    Keys: kind ('own' | 'private' | 'share'), place_id, link_code."""
    username = str(username or "").strip().lower()
    with _LOCK:
        return dict(_JOIN_INFO.get(username) or {})


def join_server_link(username: str) -> str:
    """Human-clickable URL for the private server the account was launched
    into. '' when nothing shareable is known — Own Server launches
    carry an accessCode only, which has no public join URL."""
    info = get_join_info(username)
    place = str(info.get("place_id") or "").strip()
    link = str(info.get("link_code") or "").strip()
    if not place or not link:
        return ""
    return (f"https://www.roblox.com/games/{place}"
            f"?privateServerLinkCode={quote(link, safe='')}")


# ---- mutex + cookie locks ---------------------------------------------------

def _acquire_cookie_lock() -> None:
    """Open RobloxCookies.dat exclusively (Error 773 protection)."""
    if os.name != "nt":
        return
    import ctypes
    with _LOCK:
        if _COOKIE_HANDLE is not None:
            return
        GENERIC_READ = 0x80000000
        OPEN_EXISTING = 3
        INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
        k32 = _kernel32()
        k32.CreateFileW.restype = ctypes.c_void_p
        handle = k32.CreateFileW(
            _cookies_dat_path(), GENERIC_READ, 0, None, OPEN_EXISTING, 0, None)
        if handle and handle != INVALID_HANDLE_VALUE:
            _COOKIE_HANDLE = handle
            _STATE["cookie_lock_held"] = True
            _STATE["cookie_lock_note"] = "Shared cookie file locked (Error 773 protection)."
        else:
            err = ctypes.get_last_error()
            if err == 32:
                _STATE["cookie_lock_note"] = "Locked by another program (a launcher is already active)."
            elif err == 2:
                _STATE["cookie_lock_note"] = "No cookie file yet — log into Roblox once."
            else:
                _STATE["cookie_lock_note"] = f"Cookie lock failed (code {err})."


def _release_cookie_lock() -> None:
    global _COOKIE_HANDLE
    if os.name != "nt":
        return
    import ctypes
    with _LOCK:
        if _COOKIE_HANDLE is not None:
            try:
                ctypes.windll.kernel32.CloseHandle(ctypes.c_void_p(_COOKIE_HANDLE))
            except Exception:
                pass
            _COOKIE_HANDLE = None
            _STATE["cookie_lock_held"] = False
            _STATE["cookie_lock_note"] = ""


def _kernel32() -> Any:
    """kernel32 bound with use_last_error=True so GetLastError is reliable.

    Reading the thread error through ctypes' own bookkeeping (WinDLL with
    use_last_error) avoids the classic trap where ctypes' internal work
    between the foreign call and GetLastError() resets the value to 0.
    """
    global _KERNEL32
    if _KERNEL32 is None:
        import ctypes
        _KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
    return _KERNEL32


class _HandleEntryEx(ctypes.Structure):
    _fields_ = [
        ("Object", ctypes.c_void_p),
        ("UniqueProcessId", ctypes.c_size_t),
        ("HandleValue", ctypes.c_size_t),
        ("GrantedAccess", ctypes.c_uint32),
        ("CreatorBackTraceIndex", ctypes.c_ushort),
        ("ObjectTypeIndex", ctypes.c_ushort),
        ("HandleAttributes", ctypes.c_uint32),
        ("Reserved", ctypes.c_uint32),
    ]


class _UnicodeString(ctypes.Structure):
    _fields_ = [("Length", ctypes.c_ushort), ("MaximumLength", ctypes.c_ushort),
                ("Buffer", ctypes.c_wchar_p)]


class _ObjectNameInformation(ctypes.Structure):
    _fields_ = [("Name", _UnicodeString)]


class _ObjectBasicInformation(ctypes.Structure):
    _fields_ = [
        ("Attributes", ctypes.c_uint32), ("GrantedAccess", ctypes.c_uint32),
        ("HandleCount", ctypes.c_uint32), ("PointerCount", ctypes.c_uint32),
        ("PagedPoolUsage", ctypes.c_uint32), ("NonPagedPoolUsage", ctypes.c_uint32),
        ("Reserved", ctypes.c_uint32 * 3), ("NameInformationLength", ctypes.c_uint32),
        ("TypeInformationLength", ctypes.c_uint32), ("SecurityDescriptorLength", ctypes.c_uint32),
        ("CreateTime", ctypes.c_int64),
    ]


_STATUS_INFO_LENGTH_MISMATCH = 0xC0000004
_SYSTEM_EXTENDED_HANDLE_INFORMATION = 64
_PROCESS_DUP_HANDLE = 0x0040
_DUPLICATE_SAME_ACCESS = 0x00000002
_DUPLICATE_CLOSE_SOURCE = 0x00000001
# Lowercased names whose handles must not survive inside Roblox clients.
# (reference: dat514/Multi-Roblox-Tab, imdaclassic/MultiBlox, sir49/SingleTonEventCloser)
_SINGLETON_TARGET_NAMES = frozenset({
    r"\sessions\1\basenamedobjects\roblox_singletonevent",
    "roblox_singletonevent",
    "roblox_singletonmutex",
})


def _ntdll() -> Any:
    global _NTDLL
    if _NTDLL is None:
        _NTDLL = ctypes.WinDLL("ntdll")
    return _NTDLL


def _singleton_name_matches(name: str) -> bool:
    try:
        return str(name).strip().lower() in _SINGLETON_TARGET_NAMES
    except Exception:
        return False


def _roblox_pids() -> list[int]:
    """PIDs of running Roblox client processes (best effort).

    also matches the Microsoft Store client (Windows10Universal.exe) —
    it enforces the same named singleton objects, and missing it made the
    strip pass report "no Roblox clients running" while a Store client was
    in fact running, so the launch gate passed with the client UNPROTECTED
    and the next launch killed it. On a vanilla (non-Bloxstrap) client the
    missing singleton protection lets every new client close the previous
    one."""
    try:
        import psutil
        out: list[int] = []
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                info = proc.info or {}
                name = str(info.get("name") or "").lower()
                if "robloxplayerbeta" in name or "windows10universal" in name:
                    out.append(int(info.get("pid")))
            except Exception:
                continue
        return out
    except Exception:
        return []


def _strip_singleton_pass(pids: list[int]) -> dict[str, Any]:
    """Close ROBLOX_singletonEvent / ROBLOX_singletonMutex handles inside the
    given processes. Windows only (ntdll/kernel32). Returns stats.

    Modern Roblox clients enforce single-instance through the named EVENT:
    while the object exists, a new launch signals it and the running client
    exits. Stripping the handles from every running client removes the object
    entirely, so no launch can kill another client.
    """
    if os.name != "nt":
        return {"ok": False, "note": "Windows only", "closed": 0, "pids": []}
    ntdll = _ntdll()
    k32 = _kernel32()
    closed = 0
    touched: list[int] = []
    errors: list[str] = []
    # System-wide handle table (grows until it fits).
    size = 0x100000
    entries = None
    for _ in range(20):
        buf = ctypes.create_string_buffer(size)
        ret = ctypes.c_ulong()
        status = ntdll.NtQuerySystemInformation(
            _SYSTEM_EXTENDED_HANDLE_INFORMATION, buf, size, ctypes.byref(ret))
        status &= 0xFFFFFFFF
        if status == 0:
            hdr = ctypes.cast(buf, ctypes.POINTER(ctypes.c_size_t * 2)).contents
            count = int(hdr[0])
            if count <= 0:
                entries = []
            else:
                arr = ctypes.cast(ctypes.byref(hdr, 16),
                                  ctypes.POINTER(_HandleEntryEx * count)).contents
                entries = list(arr)
            break
        if status == _STATUS_INFO_LENGTH_MISMATCH:
            size = max(size * 2, int(ret.value or 0) + 0x10000)
            continue
        return {"ok": False, "note": f"NtQuerySystemInformation failed (0x{status:X})",
                "closed": 0, "pids": []}
    if entries is None:
        return {"ok": False, "note": "handle table unavailable", "closed": 0, "pids": []}
    want = set(int(p) for p in pids if p)
    if not want:
        return {"ok": True, "note": "no Roblox clients running", "closed": 0, "pids": []}
    for pid in want:
        # NtQueryObject can block forever on a few exotic handle types; run
        # each client's scan in its own thread and abandon it on timeout so
        # the watcher loop never freezes (the reference tools do the same
        # scan synchronously; we add the timeout as a safety net).
        result: dict[str, Any] = {}
        worker = threading.Thread(target=lambda r=result, p=pid: r.update(_strip_one_pid(p, entries)),
                                  name=f"EndSol singleton scan {pid}", daemon=True)
        worker.start()
        worker.join(5.0)
        if worker.is_alive():
            errors.append(f"PID {pid}: handle scan timed out (skipped)")
            continue
        closed += int(result.get("closed", 0))
        if result.get("closed"):
            touched.append(pid)
        if result.get("error"):
            errors.append(str(result["error"]))
    note = (f"stripped {closed} singleton handle(s) in {len(touched)} client(s)"
            if closed else "no singleton handles present")
    if errors:
        note += "; " + "; ".join(errors[:3])
    return {"ok": not errors, "note": note, "closed": closed, "pids": touched,
            "errors": errors}


def _strip_one_pid(pid: int, entries: list[Any]) -> dict[str, Any]:
    """Scan one process's handles and close the singleton ones (Windows only)."""
    closed = 0
    k32 = _kernel32()
    ntdll = _ntdll()
    src = k32.OpenProcess(_PROCESS_DUP_HANDLE, False, pid)
    if not src:
        return {"closed": 0, "error": f"PID {pid}: OpenProcess failed (error {ctypes.get_last_error()})"}
    cur = ctypes.c_void_p(-1)  # pseudo handle: current process
    try:
        for entry in entries:
            if entry.UniqueProcessId != pid:
                continue
            source_handle = ctypes.c_void_p(entry.HandleValue & 0xFFFFFFFFFFFFFFFF)
            dup = ctypes.c_void_p()
            if not k32.DuplicateHandle(src, source_handle, cur, ctypes.byref(dup),
                                       0, False, _DUPLICATE_SAME_ACCESS):
                continue
            try:
                basic = _ObjectBasicInformation()
                retlen = ctypes.c_ulong()
                st = ntdll.NtQueryObject(dup, 0, ctypes.byref(basic),
                                         ctypes.sizeof(basic), ctypes.byref(retlen))
                st &= 0xFFFFFFFF
                if st != 0 or basic.NameInformationLength <= 0:
                    continue
                nbuf = ctypes.create_string_buffer(basic.NameInformationLength
                                                   + ctypes.sizeof(_UnicodeString))
                st = ntdll.NtQueryObject(dup, 1, nbuf, len(nbuf), ctypes.byref(retlen))
                st &= 0xFFFFFFFF
                if st != 0:
                    continue
                name = ctypes.cast(nbuf, ctypes.POINTER(_ObjectNameInformation)
                                   ).contents.Name.Buffer
                if name and _singleton_name_matches(name):
                    tmp = ctypes.c_void_p()
                    if k32.DuplicateHandle(src, source_handle, cur, ctypes.byref(tmp),
                                           0, False, _DUPLICATE_CLOSE_SOURCE):
                        k32.CloseHandle(tmp)
                        closed += 1
            finally:
                k32.CloseHandle(dup)
    finally:
        k32.CloseHandle(src)
    return {"closed": closed}


# pids already handled by the stripper, plus how many consecutive clean
# scans each had. A pid is DONE after ONE scan that closed handles, or after
# _PID_CLEAN_SCANS_REQUIRED consecutive scans that found nothing to close —
# a fresh client creates its singleton handles shortly after spawn, so
# marking a just-spawned pid done after a single empty scan could race the
# handle creation and leave the client unprotected.
#
# This turns the steady state (no launches happening) into a ZERO-cost loop:
# the old version re-enumerated the WHOLE system handle table and ran
# NtQueryObject over every handle of every Roblox client EVERY second, which
# is heavy enough to stutter the game on the same machine. Handles are
# created once at client startup and never recreated, so one successful scan
# per client is sufficient — exactly what the reference tools do.
_STRIPPED_PIDS: set[int] = set()
_PID_CLEAN_SCANS: dict[int, int] = {}
_PID_CLEAN_SCANS_REQUIRED = 3
# A freshly spawned client may create its singleton handles SECONDS after
# the process shows up (after anti-tamper init). Clean scans during that
# window prove nothing, so a young pid is never marked done on clean scans
# alone - it keeps being scanned until it is at least this old.
_PID_FIRST_SEEN: dict[int, float] = {}
_PID_CLEAN_DONE_MIN_AGE = 60.0


def _singleton_loop() -> None:
    while not _SINGLETON_STOP.is_set():
        # Tighter cadence while a login capture is open: a client started in
        # that window must not get a chance to kill the login window.
        try:
            with _LOCK:
                capturing = bool(_STATE.get("login_active"))
            _SINGLETON_STOP.wait(0.3 if capturing else 1.0)
        except Exception:
            time.sleep(1.0)
        if _SINGLETON_STOP.is_set():
            break
        try:
            pids = _roblox_pids()
            now_ts = time.time()
            with _LOCK:
                # Prune dead pids every pass (self-heals Windows pid reuse).
                _STRIPPED_PIDS.intersection_update(pids)
                for stale in [p for p in _PID_CLEAN_SCANS if p not in pids]:
                    _PID_CLEAN_SCANS.pop(stale, None)
                for stale in [p for p in _PID_FIRST_SEEN if p not in pids]:
                    _PID_CLEAN_SCANS.pop(stale, None)
                    _PID_FIRST_SEEN.pop(stale, None)
                for p in pids:
                    _PID_FIRST_SEEN.setdefault(p, now_ts)
                pending = [p for p in pids if p not in _STRIPPED_PIDS]
            if not pending:
                # Steady-state fast path: nothing new to strip — skip the
                # whole handle-table enumeration entirely.
                with _LOCK:
                    _STATE["singleton_last"] = {"ok": True, "note": (
                        f"watcher active — {len(pids)} client(s) already stripped"
                        if pids else "watcher active — no Roblox clients"),
                        "closed": 0, "pids": []}
                    _STATE["singleton_clean"] = True
                    _STATE["mutex_exists"] = True
                    _STATE["mutex_held"] = True
                    _STATE["mutex_note"] = str(_STATE["singleton_last"]["note"])
                continue
            stats = _strip_singleton_pass(pending)
            closed_pids = set(int(p) for p in (stats.get("pids") or []))
            ok = bool(stats.get("ok"))
            with _LOCK:
                _STATE["singleton_last"] = stats
                _STATE["mutex_exists"] = True
                if ok:
                    for p in pending:
                        if p in closed_pids:
                            # Handles were found and closed - fully done.
                            _STRIPPED_PIDS.add(p)
                            _PID_CLEAN_SCANS.pop(p, None)
                            continue
                        # Clean scans only count for a client old enough:
                        # a just-spawned pid may not have created its
                        # singleton handles yet, and marking it done now
                        # would leave it unprotected forever (the next
                        # launch would kill it through the takeover).
                        age = now_ts - float(_PID_FIRST_SEEN.get(p, now_ts))
                        if age < _PID_CLEAN_DONE_MIN_AGE:
                            _PID_CLEAN_SCANS.pop(p, None)
                            continue
                        n = int(_PID_CLEAN_SCANS.get(p, 0)) + 1
                        if n >= _PID_CLEAN_SCANS_REQUIRED:
                            _STRIPPED_PIDS.add(p)
                            _PID_CLEAN_SCANS.pop(p, None)
                        else:
                            _PID_CLEAN_SCANS[p] = n
                _STATE["singleton_clean"] = bool(ok)
                _STATE["mutex_held"] = _STATE["singleton_clean"]
                _STATE["mutex_note"] = str(stats.get("note") or "")
        except Exception as exc:
            stats = {"ok": False, "note": f"exception: {exc}", "closed": 0, "pids": []}
            with _LOCK:
                _STATE["singleton_last"] = stats
                _STATE["singleton_clean"] = False
                _STATE["mutex_held"] = False
                _STATE["mutex_note"] = str(stats.get("note") or "")
        # per-strip success logging removed (fired on every launch);
        # failures surface through the launch gate's error message and
        # _STATE["singleton_note"].
        # strip activity note is visible in the launch-time diagnostic
        # line ("[Launcher] Singleton: ...") and the Locks line.


def _start_singleton_watcher() -> None:
    global _SINGLETON_THREAD
    if os.name != "nt":
        return
    with _LOCK:
        if _SINGLETON_THREAD and _SINGLETON_THREAD.is_alive():
            return
    _SINGLETON_STOP.clear()
    with _LOCK:
        _STATE["mutex_exists"] = True
        if not _STATE.get("mutex_note"):
            _STATE["mutex_note"] = "singleton watcher starting..."
    _SINGLETON_THREAD = threading.Thread(target=_singleton_loop,
                                         name="EndSol singleton stripper", daemon=True)
    _SINGLETON_THREAD.start()


def force_singleton_rescan() -> None:
    """Drop the per-pid done-cache so the next watcher pass re-strips EVERY
    running client. Called right before a launch: the takeover kills every
    client that still holds singleton handles, so the pre-launch state must
    be verified by a fresh scan, never by a cached verdict."""
    if os.name != "nt":
        return
    _start_singleton_watcher()
    with _LOCK:
        _STRIPPED_PIDS.clear()
        _PID_CLEAN_SCANS.clear()
        _STATE["singleton_clean"] = False


def _ensure_singleton_ready(timeout: float = 5.0) -> bool:
    """Start the stripper (if needed) and wait for one clean scan pass."""
    if os.name != "nt":
        return True
    _start_singleton_watcher()
    deadline = time.time() + timeout
    while time.time() < deadline:
        with _LOCK:
            if _STATE.get("singleton_clean"):
                return True
        time.sleep(0.15)
    return False


def ensure_locks() -> dict[str, Any]:
    """Hold the shared cookie file and keep the singleton stripper running.

    the old "pre-hold ROBLOX_singletonMutex" trick is DEAD on current
    clients — the takeover goes through ROBLOX_singletonEvent, which holding
    the mutex does NOT prevent ( a browser-launched
    client killed the login window while EndSol held the mutex; every 2025+
    reference tool — MultiBlox, Multi-Roblox-Tab, SingleTonEventCloser —
    instead CLOSES the singleton event/mutex handles inside running clients
    via NtQuerySystemInformation + DuplicateHandle(DUPLICATE_CLOSE_SOURCE)).
    Holding our own handle would keep the named object alive and feed the
    takeover path, so we no longer hold it at all.
    """
    _acquire_cookie_lock()
    _start_singleton_watcher()
    with _LOCK:
        return {"success": True,
                "mutex_held": _STATE["mutex_held"], "mutex_note": _STATE["mutex_note"],
                "mutex_exists": _STATE.get("mutex_exists", False),
                "singleton_clean": bool(_STATE.get("singleton_clean")),
                "singleton_note": str(_STATE.get("singleton_note") or ""),
                "cookie_lock_held": _STATE["cookie_lock_held"], "cookie_lock_note": _STATE["cookie_lock_note"]}


def release_locks() -> None:
    """Release the cookie file lock only.

    the singleton STRIPPER keeps running after this on purpose — it
    protects every running Roblox client from the takeover regardless of
    the Multiple-Instances preference (set_enabled(False) used to drop the
    protection together with the cookie lock; that is no longer wanted).
    """
    if os.name != "nt":
        return
    _release_cookie_lock()


def get_state() -> dict[str, Any]:
    with _LOCK:
        snapshot = {k: _STATE[k] for k in (
            "mutex_held", "mutex_note", "cookie_lock_held", "cookie_lock_note",
            "login_active", "login_status", "login_username",
            "last_error", "last_launched", "mint_debug", "ps_debug",
            "singleton_clean", "singleton_note")}
    snapshot["accounts"] = _public_accounts()
    # accounts with a live client (or inside the post-launch TTL lock) —
    # the UI disables their Launch buttons.
    running_now = _running_accounts()
    with _LOCK:
        now_ts = time.time()
        # a fresh lock means "client starting up" only until the launch
        # watcher CONFIRMS the client alive. After that the live scan above
        # is the source of truth, so a closed client clears the Running
        # state within one UI poll instead of sticking for the whole TTL.
        recent = [u for u, t in _RUNNING_LOCK.items()
                  if now_ts - t < _LAUNCH_LOCK_TTL and _LAUNCH_CONFIRMED.get(u, 0.0) <= t]
    snapshot["running_accounts"] = sorted(set(running_now) | set(recent))
    snapshot["mutex_exists"] = bool(_STATE.get("mutex_exists", False))
    if not snapshot["mutex_note"]:
        # Keep the Locks line informative at app start (before the watcher's
        # first pass or when the mode was never enabled this session).
        snapshot["mutex_note"] = ("singleton watcher not running yet "
                                  "(starts on first Launch or when Multiple-Instances turns on)")
    return snapshot
