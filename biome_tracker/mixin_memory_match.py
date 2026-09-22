"""
Memory Match auto-player mixin for EndSol Macro.

Sol's RNG Memory Match (added Eon 1-2, expanded Summer 2026):
  - 5x4 grid of tiles, 10 chances (each chance = 2 tiles flipped)
  - Match identical pairs; matched tiles stay revealed (green)
  - 12 hour cooldown between matches (-3h per ad watched, max 3 ads)
  - Location: near the beach, opposite direction from fishing
  - Rewards: Potions, Void Coin, Rune, Godly/Heavenly/Godlike Potion, etc.

Strategy implemented here (per Fandom wiki "optimal" approach):
  1. Click 2 tiles, OCR them, remember positions
  2. If items match -> pair found, continue
  3. If items don't match -> keep positions/items in memory, try to find
     pair on the next turns
  4. Prioritize high-value items (Godlike, Heavenly, Potion of Bound, etc.)
  5. After 10 turns, close UI and return to original position
"""

import json
import os
import re
import time
from datetime import datetime, timedelta

import autoit

try:
    import keyboard  # character reset (Esc -> R -> Enter)
except Exception:  # pragma: no cover - keyboard is a hard dependency of the macro
    keyboard = None


# Priority list (highest first) for items to try to pair early.
# Match the exact text that the OCR may produce for each item.
# Lowercase, normalized, contains-style matches.
PRIORITY_ITEMS = [
    # Top tier
    "godlike potion",
    "heavenly potion",
    "potion of bound",
    "a random rune",
    # Mid tier
    "rune of everything",
    "godly potion",
    "void coin",
    "fortune potion iii",
    "haste potion iii",
    # Summer 2026 specific
    "tear of the goddess",
    "power battery",
    "hwachae",
    "summer points",
    # Generic
    "fortune potion ii",
    "haste potion ii",
    "fortune potion i",
    "haste potion i",
]


# ---------------------------------------------------------------------------
# Path loading (replay a recorded walk to the Memory Match board)
# ---------------------------------------------------------------------------

_PATHS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "paths")
_MEMORY_MATCH_PATH_FILE = os.path.join(_PATHS_DIR, "memory_match.json")


def _load_path_file(filename: str) -> list:
    """Load a bundled default path file from the project's paths/ directory."""
    try:
        path = os.path.join(_PATHS_DIR, filename)
        if not os.path.exists(path):
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("events", []) if isinstance(data.get("events"), list) else []
        return []
    except Exception:
        return []


def _load_memory_match_path():
    """Load the recorded walk path. Priority: custom_paths/ > paths/."""
    try:
        from .custom_path_manager import load_path_for_feature_meta
        custom, custom_meta = load_path_for_feature_meta("memory_match")
        if custom:
            return custom, custom_meta
    except Exception:
        pass
    return _load_path_file("memory_match.json"), None


def _build_default_memory_match_path(vip: bool = True):
    """
    Hardcoded walk path that takes the user from spawn to the Memory Match
    board next to the beach. VIP (Game Pass) users get a faster walk; non-VIP
    uses a slower cadence so the macro walks in sync with the slower base speed.
    """
    if vip:
        return [
            {"t": 0.0, "type": "key_down", "key": "w"},
            {"t": 4.6, "type": "key_up", "key": "w"},
            {"t": 4.7, "type": "mouse_move", "x": 960, "y": 540},
            {"t": 4.8, "type": "mouse_down", "button": "right"},
            {"t": 4.9, "type": "mouse_move", "x": 960, "y": 615},
            {"t": 5.3, "type": "mouse_up", "button": "right"},
            {"t": 5.4, "type": "key_down", "key": "w"},
            {"t": 5.6, "type": "key_up", "key": "w"},
            {"t": 5.8, "type": "key_down", "key": "e"},
            {"t": 6.0, "type": "key_up", "key": "e"},
        ]
    return [
        {"t": 0.0, "type": "key_down", "key": "w"},
        {"t": 6.6, "type": "key_up", "key": "w"},
        {"t": 6.7, "type": "mouse_move", "x": 960, "y": 540},
        {"t": 6.8, "type": "mouse_down", "button": "right"},
        {"t": 6.9, "type": "mouse_move", "x": 960, "y": 615},
        {"t": 7.3, "type": "mouse_up", "button": "right"},
        {"t": 7.4, "type": "key_down", "key": "w"},
        {"t": 7.6, "type": "key_up", "key": "w"},
        {"t": 7.8, "type": "key_down", "key": "e"},
        {"t": 8.0, "type": "key_up", "key": "e"},
    ]


_MOVEMENT_KEYS = frozenset({"w", "a", "s", "d", "space"})


def _safe_key_down(key: str):
    try:
        autoit.key_down(key)
    except Exception:
        pass


def _safe_key_up(key: str):
    try:
        autoit.key_up(key)
    except Exception:
        pass


def _release_all_keys():
    for k in ("w", "a", "s", "d", "space", "e"):
        _safe_key_up(k)
    time.sleep(0.05)


def _replay_walk_path(events, sleep_interruptible, should_continue, can_run, speed_multiplier=1.0):
    """Replay a recorded walk path.

    This is the SAME mechanism the macro uses for every other path (the
    Eden player, mixin_actions._run_eden_macro): the `keyboard` library's
    press/release with a wall-clock timeline. autoit.key_down proved
    unreliable for walking on some setups, so custom paths must not use it.

    Recordings capture Windows auto-repeat (holding W yields many key_down
    events and one key_up) — a held key is pressed once on its FIRST
    key_down and released on the matching key_up.
    """
    if not events:
        return False
    try:
        import keyboard as _kb  # the same lib the Eden player uses
    except Exception:
        _kb = None
    if _kb is None:
        return False

    _ALLOWED_KEYS = {"w", "a", "s", "d", "space", "e"}
    evs = [
        e for e in events
        if str(e.get("type", "")) in ("key_down", "key_up")
        and str(e.get("key", "")).lower().strip() in _ALLOWED_KEYS
    ]
    if not evs:
        return False
    evs.sort(key=lambda ev: float(ev.get("t", 0.0)))
    base_t = float(evs[0].get("t", 0.0))
    mult = 1.0
    try:
        mult = float(speed_multiplier)
    except Exception:
        mult = 1.0
    if not (mult and mult > 0.0):
        mult = 1.0

    pressed_keys: set[str] = set()
    start_wall = time.time()
    try:
        for ev in evs:
            if not should_continue() or not can_run():
                return False
            ev_t = (float(ev.get("t", base_t)) - base_t) * mult
            target_wall = start_wall + ev_t
            # Wall-clock wait in small chunks so stop stays responsive.
            while True:
                now = time.time()
                if now >= target_wall:
                    break
                if not should_continue() or not can_run():
                    return False
                time.sleep(min(0.05, max(0.0, target_wall - now)))

            typ = str(ev.get("type", ""))
            k = str(ev.get("key", "")).lower().strip()
            if not k:
                continue
            try:
                if typ == "key_down":
                    if k not in pressed_keys:
                        # Windows auto-repeat of an already-held key — the
                        # key is down, skip the duplicate press.
                        _kb.press(k)
                        pressed_keys.add(k)
                elif typ == "key_up":
                    _kb.release(k)
                    pressed_keys.discard(k)
            except Exception:
                pass
        return bool(should_continue() and can_run())
    finally:
        for key_name in list(pressed_keys):
            try:
                _kb.release(key_name)
            except Exception:
                pass
        _release_all_keys()


# ---------------------------------------------------------------------------
# OCR helpers (uses project's winocr if available)
# ---------------------------------------------------------------------------

def _ocr_image(image_path: str) -> str:
    """Run OCR on an image file, return lowercased text. Falls back to '' on error."""
    try:
        import winocr  # type: ignore
        result = winocr.image_to_text(image_path)
        return (result or "").lower().strip()
    except Exception:
        return ""


def _capture_tile_screenshot(x: int, y: int, w: int, h: int, save_path: str) -> bool:
    """Capture a screen region and save to a file. Returns True on success."""
    try:
        import pyautogui
        img = pyautogui.screenshot(region=(x, y, w, h))
        img.save(save_path)
        return True
    except Exception:
        return False


def _tile_signature(img) -> tuple | None:
    """
    Perceptual signature of a tile screenshot.

    Tiles are IMAGES (only the quantity is text), so matching is done on the
    pixels: downscale to 16x16 RGB and subtract the channel means so small
    lighting/antialiasing differences do not shift the signature.
    """
    try:
        small = img.resize((16, 16)).convert("RGB")
        data = list(small.getdata())
        n = max(1, len(data))
        mr = sum(p[0] for p in data) / n
        mg = sum(p[1] for p in data) / n
        mb = sum(p[2] for p in data) / n
        sig = []
        for p in data:
            sig.append(p[0] - mr)
            sig.append(p[1] - mg)
            sig.append(p[2] - mb)
        return tuple(sig)
    except Exception:
        return None


def _tile_similarity(a, b) -> float:
    """1.0 = identical tile art, 0.0 = completely different."""
    if a is None or b is None:
        return 0.0
    try:
        total = 0.0
        for va, vb in zip(a, b):
            total += abs(va - vb)
        max_total = 255.0 * max(1, len(a))
        return max(0.0, 1.0 - (total / max_total))
    except Exception:
        return 0.0


def _center_signature(img) -> tuple | None:
    """
    4x4 grid of mean colors over the tile's CENTRAL area, background-normalized.

    The memory-match cells are SEMI-TRANSPARENT: the game landscape behind
    them differs per cell, so whole-tile pixel signatures never match for
    two copies of the same item. The item icon itself is opaque and drawn
    centered - but real icons are SMALLER than a 36% crop, so background
    leaks in and (with a worst-channel metric) blew identical-item
    distances past 87 in real logs. Two fixes:
      1. tighter central region (24% - safely inside the icon),
      2. background normalization: the mean color of the tile's outer
         border (pure background, no icon) is subtracted from every grid
         value, cancelling the per-cell landscape tint.
    """
    try:
        w, h = img.size
        # background estimate: outer 10% frame of the tile
        bw = max(2, int(w * 0.10))
        bh = max(2, int(h * 0.10))
        frame = img.crop((0, 0, w, bh))
        frame = frame.resize((max(1, frame.width), max(1, frame.height))).convert("RGB")
        fdata = list(frame.getdata())
        n = max(1, len(fdata))
        br = sum(p[0] for p in fdata) / n
        bg = sum(p[1] for p in fdata) / n
        bb = sum(p[2] for p in fdata) / n
        # tight central crop - pure icon even when the art is small
        region = 0.24
        cw = max(8, int(w * region))
        ch = max(8, int(h * region))
        box = img.crop(((w - cw) // 2, (h - ch) // 2, (w + cw) // 2, (h + ch) // 2)).convert("RGB")
        grid_n = 4
        cell_w = max(1, box.width // grid_n)
        cell_h = max(1, box.height // grid_n)
        sig: list[float] = []
        for gy in range(grid_n):
            for gx in range(grid_n):
                cell = box.crop((gx * cell_w, gy * cell_h,
                                 (gx + 1) * cell_w if gx < grid_n - 1 else box.width,
                                 (gy + 1) * cell_h if gy < grid_n - 1 else box.height))
                data = list(cell.getdata())
                n = max(1, len(data))
                sig.append(sum(p[0] for p in data) / n - br)
                sig.append(sum(p[1] for p in data) / n - bg)
                sig.append(sum(p[2] for p in data) / n - bb)
        return tuple(sig)
    except Exception:
        return None


def _center_distance(a, b) -> float:
    """Mean per-channel difference between two center signatures (0 = same).

    A mean metric is robust to a few contaminated grid cells (background
    bleed, glow); the previous worst-channel metric amplified that noise
    and made identical items compare at distance 87+ in real logs.
    """
    if not a or not b:
        return 999.0
    try:
        total = sum(abs(pa - pb) for pa, pb in zip(a, b))
        return total / max(1, len(a))
    except Exception:
        return 999.0


def _fmt_center(c) -> str:
    try:
        if not c:
            return "?"
        return "({},{},{})".format(int(round(c[0])), int(round(c[1])), int(round(c[2])))
    except Exception:
        return "?"


def _ocr_quantity_from_file(image_path: str) -> str | None:
    """
    OCR the quantity ("x10", "x 1,000"...) from a tile screenshot.

    The quantity is the ONLY text on a tile - it lives in the bottom strip.
    Real logs showed Windows OCR returning nothing for the plain 3x bottom
    strip, so several candidates are tried (different strip heights, 4x
    upscale, autocontrast, full tile) and the first quantity-like hit wins.
    Returns None when nothing quantity-like was recognized.
    """
    try:
        from PIL import Image, ImageOps
        img = Image.open(image_path)
        w, h = img.size
        candidates = []
        for top in (0.62, 0.55, 0.70):
            strip = img.crop((0, int(h * top), w, h))
            strip = strip.resize((max(1, strip.width * 4), max(1, strip.height * 4)))
            candidates.append(ImageOps.autocontrast(ImageOps.grayscale(strip)))
        full = img.resize((max(1, w * 3), max(1, h * 3)))
        candidates.append(ImageOps.autocontrast(ImageOps.grayscale(full)))
        for i, cand in enumerate(candidates):
            qty_path = image_path.replace(".png", f"_qty{i}.png")
            cand.save(qty_path)
            try:
                text = _ocr_image(qty_path)
            finally:
                # Temp OCR images are not needed once read - do not litter
                # the logs folder.
                try:
                    os.remove(qty_path)
                except Exception:
                    pass
            m = re.search(r"x\s*([\d,]{1,9})", text or "")
            if m:
                return f"x{m.group(1)}"
        return None
    except Exception:
        return None


def _qty_strip_signature(img) -> tuple | None:
    """
    Binary mask of the quantity text ("x10", "x 1,000") in the tile's bottom
    strip. Deterministic fallback/companion to OCR: two tiles showing the
    SAME quantity produce nearly identical masks, the same item with a
    DIFFERENT quantity produces clearly different masks - no OCR needed.

    The mask keeps only clearly bright pixels (the quantity is drawn as
    bright text over the semi-transparent tile), is cropped to the text
    bounding box and resized to a fixed 48x16 grid, which cancels the
    per-cell background and small position shifts.
    """
    try:
        w, h = img.size
        strip = img.crop((int(w * 0.15), int(h * 0.62), int(w * 0.85), int(h * 0.98))).convert("L")
        mask = strip.point(lambda v: 255 if v >= 190 else 0)
        bbox = mask.getbbox()
        if not bbox:
            return None
        crop = mask.crop(bbox).resize((48, 16))
        return tuple(crop.getdata())
    except Exception:
        return None


def _qty_strip_aspect(img) -> float | None:
    """Width/height of the quantity text bounding box (0 = no text found).

    Different quantities have different digit counts, so a clearly wider
    text box is itself evidence of a different quantity ("x10" vs "x100").
    """
    try:
        w, h = img.size
        strip = img.crop((int(w * 0.15), int(h * 0.62), int(w * 0.85), int(h * 0.98))).convert("L")
        mask = strip.point(lambda v: 255 if v >= 190 else 0)
        bbox = mask.getbbox()
        if not bbox:
            return None
        bw = max(1, bbox[2] - bbox[0])
        bh = max(1, bbox[3] - bbox[1])
        return bw / bh
    except Exception:
        return None


def _qty_mask_distance(a: tuple | None, b: tuple | None) -> float:
    """Mean per-pixel difference between two quantity masks (0..1, 0 = same)."""
    if a is None or b is None:
        return 1.0
    try:
        total = sum(abs(pa - pb) for pa, pb in zip(a, b))
        return total / max(1, len(a) * 255)
    except Exception:
        return 1.0


def _grid_mean_abs_diff(path_a: str, path_b: str) -> float:
    """Mean absolute pixel difference (0..255) between two grid screenshots."""
    try:
        from PIL import Image
        a = Image.open(path_a).convert("L").resize((160, 120))
        b = Image.open(path_b).convert("L").resize((160, 120))
        da = list(a.getdata())
        db = list(b.getdata())
        total = sum(abs(pa - pb) for pa, pb in zip(da, db))
        return total / max(1, len(da))
    except Exception:
        return 0.0


def _normalize_item_name(text: str) -> str:
    """Normalize OCR text to a canonical item name for comparison."""
    t = (text or "").lower().strip()
    # strip common noise (keeps letters, digits, spaces, +, -, x for "x10")
    t = re.sub(r"[^a-z0-9 \+\-]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


# OCR often confuses 0/O, 1/I/l, |/I and !/I. Mapping them onto one
# canonical character makes OCR noise comparable WITHOUT merging real
# quantity differences such as "Fortune Potion I" vs "Fortune Potion II".
_CONFUSABLE_MAP = str.maketrans({"0": "o", "1": "i", "l": "i", "|": "i", "!": "i"})


def _canonical_tokens(normalized: str) -> list[str]:
    toks = normalized.split()
    return [tok.translate(_CONFUSABLE_MAP) for tok in toks]


def _match_priority_score(item_name: str) -> int:
    """Return priority score for an item (higher = more important to find a pair for)."""
    norm = _normalize_item_name(item_name)
    if not norm:
        return 0
    toks = _canonical_tokens(norm)
    for i, prio in enumerate(PRIORITY_ITEMS):
        if norm == prio:
            return len(PRIORITY_ITEMS) - i
        if toks == _canonical_tokens(prio):
            return len(PRIORITY_ITEMS) - i
    return 0


def _items_match(a: str, b: str) -> bool:
    """
    Strictly decide whether two OCR strings are the same item.

    The game shows the quantity on the tile (e.g. "Fortune Potion x10"),
    and there are tiers like "Fortune Potion I / II / III", so substring
    matching is NOT safe: "fortune potion i" is contained inside
    "fortune potion ii" but they are different tiles. Compare exact
    token sequences (order-insensitive) with OCR-confusable characters
    canonicalized — quantity and tier must match exactly.
    """
    na = _normalize_item_name(a)
    nb = _normalize_item_name(b)
    if not na or not nb:
        return False
    ta = _canonical_tokens(na)
    tb = _canonical_tokens(nb)
    if ta == tb or sorted(ta) == sorted(tb):
        return True
    # OCR may join/split words ("fortune potion" vs "fortune  potion")
    if "".join(ta) == "".join(tb):
        return True
    return False


def _items_similarity(a: str, b: str) -> float:
    """0..1 similarity between two OCR item names (used for recovery only)."""
    na = _normalize_item_name(a)
    nb = _normalize_item_name(b)
    if not na or not nb:
        return 0.0
    try:
        from difflib import SequenceMatcher
        return SequenceMatcher(None, na, nb).ratio()
    except Exception:
        return 1.0 if na == nb else 0.0


# ---------------------------------------------------------------------------
# Webhook helpers — download thumbnail locally so Discord renders it
# without depending on the upstream CDN.
# ---------------------------------------------------------------------------

_THUMB_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "thumb_cache")


def _download_thumbnail_to_cache(url: str, biome: str) -> str | None:
    """
    Download a thumbnail URL into a local cache directory and return the file
    path. Returns None on failure (timeout, 4xx/5xx, too big, etc).

    Cached on disk by URL hash so repeat webhook sends don't re-download.
    """
    if not url or not isinstance(url, str):
        return None
    if not (url.startswith("http://") or url.startswith("https://")):
        # Already a local file path or some other scheme — return as-is
        return url if os.path.exists(url) else None
    try:
        import hashlib
        os.makedirs(_THUMB_CACHE_DIR, exist_ok=True)
        cache_key = hashlib.md5(url.encode("utf-8")).hexdigest()[:16]
        ext = os.path.splitext(url.split("?")[0])[-1] or ".png"
        cached = os.path.join(_THUMB_CACHE_DIR, f"{cache_key}{ext}")
        if os.path.exists(cached) and os.path.getsize(cached) > 0:
            return cached
        r = safe_get(url, timeout=10)
        if r is None or not r.ok:
            return None
        content = r.content
        if len(content) > 8 * 1024 * 1024:  # Discord's 8MB attachment cap
            return None
        if not content:
            return None
        with open(cached, "wb") as f:
            f.write(content)
        return cached
    except Exception:
        return None


# ---------------------------------------------------------------------------
# MemoryMatchMixin
# ---------------------------------------------------------------------------

class MemoryMatchMixin:
    """
    Provides Memory Match automation for Sol's RNG.

    Configuration keys (all in config.json):
        memory_match_enabled: bool
        memory_match_play_on_fishing: bool            (also run while fishing)
        memory_match_grid_region: [x, y, w, h]       (calibrated screen rect)
        memory_match_cell_padding: int               (default 4, gap between tiles)
        memory_match_start_button: [x, y]            (calibrated "Start" button)
        memory_match_close_button: [x, y]            (calibrated "Close" button)
        memory_match_skip_on_unknown: bool           (default True)
        memory_match_last_played: ISO timestamp      (cooldown tracking)
    """

    # ---- configuration helpers ----
    def _mm_get(self, key, default=None):
        try:
            cfg = getattr(self, "config", None) or {}
            return cfg.get(key, default)
        except Exception:
            return default

    def _mm_set(self, key, value):
        try:
            self.config[key] = value
        except Exception:
            pass

    def mm_is_enabled(self) -> bool:
        return bool(self._mm_get("memory_match_enabled", False))

    def mm_cooldown_ready(self) -> bool:
        """True if 12h cooldown has passed since last play."""
        last = self._mm_get("memory_match_last_played")
        if not last:
            return True
        try:
            last_dt = datetime.fromisoformat(last)
        except Exception:
            return True
        return datetime.now() - last_dt >= timedelta(hours=12)

    def mm_seconds_until_ready(self) -> int:
        last = self._mm_get("memory_match_last_played")
        if not last:
            return 0
        try:
            last_dt = datetime.fromisoformat(last)
        except Exception:
            return 0
        diff = (datetime.now() - last_dt).total_seconds()
        return max(0, int(12 * 3600 - diff))

    def mm_remaining_human(self) -> str:
        sec = self.mm_seconds_until_ready()
        if sec <= 0:
            return "Ready"
        h = sec // 3600
        m = (sec % 3600) // 60
        return f"{h}h {m}m"

    # ---- main entry point ----
    def play_memory_match(self) -> dict:
        """
        Reset, walk to Memory Match board, click E, play one match.

        Sequence (mirrors the Obby / Eden path prelude so the recorded walk
        always starts from the same deterministic state):
            1. activate Roblox window
            2. reset character (Esc -> R -> Enter, respawn at spawn point)
            3. close chat / leftover collections UI + align camera (blocking)
            4. replay the walk path (custom recorded path > built-in default)
            5. click Start and WAIT until the tiles are actually rendered
            6. play the match with a full 20-tile memory and strict pairing

        Returns:
            {
                "ok": bool,
                "error": str | None,
                "matches": int,   # how many pairs successfully made
                "turns_used": int,
            }
        """
        result = {"ok": False, "error": None, "matches": 0, "turns_used": 0}
        if getattr(self, "_mm_session_active", False):
            result["error"] = "Another Memory Match session is already running"
            return result
        self._mm_session_active = True
        try:
            if not self.detection_running:
                result["error"] = "Macro not running"
                return result

            grid = self._mm_get("memory_match_grid_region")
            start_btn = self._mm_get("memory_match_start_button")
            close_btn = self._mm_get("memory_match_close_button")
            if not grid or len(grid) != 4:
                result["error"] = "Grid region not calibrated (Macro Calibrations → Memory Match)"
                return result
            if not start_btn or len(start_btn) != 2:
                result["error"] = "Start button not calibrated"
                return result

            sleep_interruptible = self._mm_sleep
            should_continue = lambda: bool(getattr(self, "detection_running", False))
            can_run = lambda: True

            # 1-3. Deterministic prelude: activate game, reset character,
            #      close leftover UI and align the camera — same sequence as
            #      the Obby/Eden paths so the walk always starts from spawn.
            if not self._feature_walk_prelude("MemoryMatch"):
                result["error"] = "Cancelled"
                return result

            # 4. Walk to board via replayed path
            events, path_meta = _load_memory_match_path()
            if events:
                self._mm_log(f"[MemoryMatch] Using recorded custom path ({len(events)} events).")
            else:
                # No user-recorded path — fall back to a hardcoded default walk
                # (VIP / non-VIP aware). The user can record their own path via
                # the Custom Paths tab for higher accuracy.
                has_vip = bool(self.config.get("gamepass_vip", False) or
                                self.config.get("has_gamepass", False) or
                                self.config.get("vip", False))
                events = _build_default_memory_match_path(vip=has_vip)
                self._mm_log(
                    f"[MemoryMatch] No recorded path; using built-in default walk "
                    f"(VIP={has_vip})."
                )

            # Non-VIP characters walk slower — stretch movement timing the
            # same way the fishing paths do (non_vip_movement_path x1.22).
            # Custom paths carry a walk-speed stamp: if the path was recorded
            # in the current mode it plays back exactly as recorded; only a
            # mode mismatch stretches/compresses the timing.
            try:
                from .fishing import NON_VIP_WALK_SPEED_MULTIPLIER
                _nv = float(NON_VIP_WALK_SPEED_MULTIPLIER)
            except Exception:
                _nv = 1.22
            non_vip_now = bool(self.config.get("non_vip_movement_path", False))
            if path_meta is not None:
                try:
                    from .custom_path_manager import resolve_walk_multiplier
                    eff = resolve_walk_multiplier(path_meta, non_vip_now)
                except Exception:
                    eff = None
            else:
                eff = None
            walk_mult = eff if eff is not None else (_nv if non_vip_now else 1.0)
            speed = walk_mult * float(self._mm_get("memory_match_playback_multiplier", 1.0))
            _replay_walk_path(events, sleep_interruptible, should_continue, can_run, speed)

            if not should_continue():
                result["error"] = "Cancelled"
                return result

            # The Memory Match dialog opens with E. Custom walk recordings
            # often capture the walk only — if the recording contains no E
            # press, interact once after the walk (same as the default path).
            if not any(str(e.get("key", "")).lower() == "e" for e in events):
                self._mm_log("[MemoryMatch] Path has no E press — interacting (E) to open the game.")
                try:
                    autoit.send("e")
                except Exception:
                    pass

            # 5. Wait for UI to appear, snapshot the empty board, click "Start"
            if not sleep_interruptible(1.2):
                result["error"] = "Cancelled"
                return result
            _tmpdir0 = self._mm_get("memory_match_screenshot_dir") or os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "memory_match")
            try:
                os.makedirs(_tmpdir0, exist_ok=True)
            except Exception:
                pass
            _baseline = os.path.join(_tmpdir0, "grid_baseline.png")
            _capture_tile_screenshot(int(grid[0]), int(grid[1]), int(grid[2]), int(grid[3]), _baseline)
            try:
                autoit.mouse_click("left", int(start_btn[0]), int(start_btn[1]), 1, speed=3)
            except Exception:
                pass
            # The board flip-in animation takes a while (tiles appear one by
            # one) - give it time before the first probe.
            if not sleep_interruptible(2.5):
                result["error"] = "Cancelled"
                return result

            # 5b. The tiles flip in with an animation — never click before
            #     they are actually rendered (compared against the baseline).
            try:
                board_timeout = float(self._mm_get("memory_match_board_timeout", 20.0))
            except Exception:
                board_timeout = 20.0
            tiles_ready = self._mm_wait_for_tiles(grid, baseline_path=_baseline, timeout=board_timeout)
            self._mm_log(
                "[MemoryMatch] Tiles visible, starting to play."
                if tiles_ready else
                "[MemoryMatch] Could not confirm tiles via OCR — proceeding carefully."
            )

            # 6. Play the match (10 turns)
            play_res = self._mm_play_grid(grid, board_confirmed=tiles_ready)
            result["matches"] = play_res.get("matches", 0)
            result["turns_used"] = play_res.get("turns_used", 0)
            result["ok"] = True
            self._mm_log(
                f"[MemoryMatch] Session finished: {result['matches']} pairs "
                f"in {result['turns_used']} turns."
            )

            # 7. Record cooldown — the FULL 12h cooldown only when the board
            #    was actually reached and played. When the game never opened
            #    (path didn't reach it / board not confirmed) retry after
            #    ~30 minutes instead of wasting 12 hours.
            if tiles_ready:
                self._mm_set("memory_match_last_played", datetime.now().isoformat())
            else:
                retry_dt = datetime.now() - timedelta(hours=11, minutes=30)
                self._mm_set("memory_match_last_played", retry_dt.isoformat())
                self._mm_log("[MemoryMatch] Board was not reached — cooldown shortened to ~30 minutes so it can retry.")

            # 8. Attempts are over: the game flips every remaining tile open
            #    (~5s animation) and only THEN shows the Close button.
            self._mm_log("[MemoryMatch] Attempts over — waiting for the reveal-all animation...")
            if not sleep_interruptible(5.0):
                result["error"] = "Cancelled"
                return result
            if close_btn and len(close_btn) == 2:
                for _attempt in range(3):
                    try:
                        autoit.mouse_click("left", int(close_btn[0]), int(close_btn[1]), 1, speed=3)
                    except Exception:
                        pass
                    if not sleep_interruptible(2.0):
                        break
        except Exception as e:
            try:
                self.error_logging(e, "play_memory_match error")
            except Exception:
                pass
            result["error"] = str(e)
        finally:
            self._mm_session_active = False
            _release_all_keys()
        return result

    def _mm_log(self, message: str):
        try:
            self.append_log(message)
        except Exception:
            print(message)

    def _feature_walk_prelude(self, label: str) -> bool:
        """
        Shared deterministic prelude for every feature that walks to a place
        (Memory Match, Quest Board): activate the Roblox window, reset the
        character so the walk starts from spawn, close leftover UI and align
        the camera. Returns False when cancelled (macro stopped).
        """
        # Russian (or any non-EN) layout can make the keyboard library map
        # characters to wrong scan codes — on some laptops that even fired
        # media keys like Fn+F5 (mute). Re-assert English before ANY keys.
        try:
            from .base_support import ensure_english_layout_silent
            ensure_english_layout_silent()
        except Exception:
            pass
        self._mm_log(f"[{label}] Activating Roblox...")
        for _ in range(4):
            if not getattr(self, "detection_running", False):
                return False
            self.activate_roblox_window()
            if not self._mm_sleep(0.15):
                return False
        self._mm_log(f"[{label}] Resetting character...")
        try:
            if keyboard is not None:
                keyboard.press_and_release('esc')
                if not self._mm_sleep(0.3):
                    return False
                keyboard.press_and_release('r')
                if not self._mm_sleep(0.3):
                    return False
                keyboard.press_and_release('enter')
        except Exception:
            pass
        if not self._mm_sleep(7):
            return False
        # Close leftover UI and align the camera (blocking, no races)
        self._mm_prepare_camera_and_ui()
        return self._mm_sleep(0.5)

    def _mm_prepare_camera_and_ui(self):
        """
        Blocking UI/camera prelude shared by the Memory Match prelude:
        close the chat, toggle the collections screen open/closed to dismiss
        any stuck overlay, then right-drag the camera down (the angle the
        default walk was recorded with). Unlike align_camera() this runs
        synchronously so the walk never races the camera thread.
        """
        try:
            self.close_chat_if_open()
        except Exception:
            pass
        if not self._mm_sleep(0.2):
            return
        collections_button = self.config.get("collections_button", [0, 0])
        exit_collections_button = self.config.get("exit_collections_button", [0, 0])
        if collections_button and collections_button[0]:
            try:
                autoit.mouse_click("left", int(collections_button[0]), int(collections_button[1]), 1, speed=3)
            except Exception:
                try:
                    self.Global_MouseClick(collections_button[0], collections_button[1])
                except Exception:
                    pass
            if not self._mm_sleep(0.3):
                return
        if exit_collections_button and exit_collections_button[0]:
            try:
                autoit.mouse_click("left", int(exit_collections_button[0]), int(exit_collections_button[1]), 1, speed=3)
            except Exception:
                try:
                    self.Global_MouseClick(exit_collections_button[0], exit_collections_button[1])
                except Exception:
                    pass
            if not self._mm_sleep(0.3):
                return
        # Camera adjustment: press right mouse button and drag down 75 px
        start_x = int(exit_collections_button[0]) if exit_collections_button and exit_collections_button[0] else 500
        start_y = int(exit_collections_button[1]) if exit_collections_button and exit_collections_button[1] else 500
        try:
            autoit.mouse_move(start_x, start_y, 0)
            autoit.mouse_down("right")
            if not self._mm_sleep(0.1):
                autoit.mouse_up("right")
                return
            autoit.mouse_move(start_x, start_y + 75, 0)
            if not self._mm_sleep(0.1):
                autoit.mouse_up("right")
                return
            autoit.mouse_up("right")
        except Exception:
            pass

    def _mm_wait_for_tiles(self, grid, baseline_path: str | None = None, timeout: float = 8.0) -> bool:
        """
        After pressing Start the tiles flip in one by one. The tiles are
        IMAGES (no item text), so "tiles appeared" is detected by comparing
        the current grid screenshot against the pre-Start baseline: a large
        mean pixel difference means the board changed. Returns False when
        the wait timed out or the macro was stopped.
        """
        try:
            x0, y0, w, h = int(grid[0]), int(grid[1]), int(grid[2]), int(grid[3])
        except Exception:
            return False
        tmpdir = self._mm_get("memory_match_screenshot_dir") or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "memory_match")
        try:
            os.makedirs(tmpdir, exist_ok=True)
        except Exception:
            pass
        probe = os.path.join(tmpdir, "grid_probe.png")
        probe_prev = os.path.join(tmpdir, "grid_probe_prev.png")
        use_baseline = bool(baseline_path and os.path.exists(baseline_path))
        # Give the flip-in animation time to begin before the first probe.
        self._mm_sleep(2.0)
        deadline = time.time() + max(1.0, timeout)
        while time.time() < deadline:
            if not getattr(self, "detection_running", False):
                return False
            try:
                if _capture_tile_screenshot(x0, y0, w, h, probe):
                    confirmed = False
                    if use_baseline:
                        changed = _grid_mean_abs_diff(probe, baseline_path) >= 8.0
                        if changed and os.path.exists(probe_prev):
                            # The game board is STATIC once rendered; a live
                            # world behind an unopened dialog keeps animating.
                            # Require both "changed vs baseline" and "stable
                            # across two frames" before declaring tiles ready.
                            stable = _grid_mean_abs_diff(probe, probe_prev) <= 4.0
                            confirmed = stable
                        elif changed:
                            confirmed = True
                    else:
                        # No baseline: fall back to OCR — the quantity text,
                        # tab labels or any dialog text all count as "rendered".
                        text = _ocr_image(probe)
                        confirmed = len((text or "").strip()) >= 6
                    if confirmed:
                        return True
                    try:
                        os.replace(probe, probe_prev)
                    except Exception:
                        pass
            except Exception:
                pass
            if not self._mm_sleep(0.5):
                return False
        self._mm_log("[MemoryMatch] Board not confirmed before playing (is the game dialog open? Did the walk reach it?)")
        return False

    def _mm_sleep(self, seconds: float, slice_len: float = 0.05) -> bool:
        """Interruptible sleep — returns False if macro stopped."""
        end = time.time() + max(0.0, seconds)
        while time.time() < end:
            if not getattr(self, "detection_running", False):
                return False
            time.sleep(min(slice_len, end - time.time()))
        return True

    # ---- grid logic ----
    def _mm_cell_centers(self, grid):
        """Return list of 20 (x, y) cell centers in row-major order (5 cols x 4 rows)."""
        x0, y0, w, h = int(grid[0]), int(grid[1]), int(grid[2]), int(grid[3])
        pad = int(self._mm_get("memory_match_cell_padding", 4))
        cols, rows = 5, 4
        # divide width into 5 equal columns, height into 4 equal rows
        col_w = w / cols
        row_h = h / rows
        centers = []
        for r in range(rows):
            for c in range(cols):
                cx = int(x0 + col_w * c + col_w / 2)
                cy = int(y0 + row_h * r + row_h / 2)
                centers.append((cx, cy, c, r))
        return centers

    def _mm_play_grid(self, grid, board_confirmed: bool = True) -> dict:
        """
        Play one Memory Match game using the calibrated grid.

        Game rules (verified against the live board):
          - 5x4 grid (20 tiles), 10 chances; one chance = flip 2 tiles.
          - Same item AND same quantity -> the pair stays open (scored).
          - Anything else -> both tiles flip back after a short cooldown.
          - The panel is SEMI-TRANSPARENT, so tiles are identified by the
            opaque item icon in the center (4x4 color grid) plus the OCR'd
            quantity; whole-tile pixels are background-contaminated.

        Turn strategy (memory-first, wastes nothing):
          1. Two remembered tiles form a confirmed pair -> click both, score.
          2. Otherwise reveal ONE unknown tile. If it matches a remembered
             tile -> click that partner as the second flip of THIS turn and
             score immediately (this is the only way pairs and exploration
             both fit into 10 chances: revealing 2 unknowns every turn would
             spend all 10 chances on exploration and score nothing).
          3. Otherwise reveal a second unknown tile; if they match, score.
          4. Every scored pair is VERIFIED after the resolve cooldown: a
             scored pair stays revealed, a failed one flips back - a failed
             verification puts both tiles back into memory instead of
             poisoning it.
        """
        out = {"matches": 0, "turns_used": 0}
        if not board_confirmed:
            self._mm_log(
                "[MemoryMatch] WARNING: the board was NOT confirmed before playing - "
                "if cells come back unreadable, the grid calibration or the "
                "board-confirmation step has drifted (see the diagnostic below)."
            )
        cells = self._mm_cell_centers(grid)
        # tile_state: dict[(c, r)] = {"sig", "center", "qty"} - full 20-tile
        # memory, kept until the tile's pair is scored.
        tile_state: dict[tuple[int, int], dict] = {}
        matched: set[tuple[int, int]] = set()
        # Pairs that were flipped together and did NOT stay open. Typical
        # cause: the same item icon with a DIFFERENT quantity while the
        # quantity OCR failed (qty=?qty? on both tiles), so the matcher
        # cannot tell the two tiles apart up front. Such a pair is never
        # auto-retried: re-testing a known-false pair wastes a whole turn
        # and used to loop the session on the same two tiles.
        failed_pairs: dict[frozenset, int] = {}
        try:
            threshold = float(self._mm_get("memory_match_tile_match_threshold", 0.93))
        except Exception:
            threshold = 0.93
        # Center-grid identity check: the opaque icon's 4x4 color grid must
        # match within a small mean-per-channel tolerance (the signature is
        # background-normalized; 20 separates same items (~0-13) from
        # different ones (30+) in both synthetic and real-log conditions).
        try:
            center_tol = float(self._mm_get("memory_match_center_tolerance", 20.0))
        except Exception:
            center_tol = 20.0
        # Quantity pixel-mask tolerance: mean per-pixel difference (0..1)
        # between the bright-text masks of the quantity strip. Two tiles
        # with the SAME quantity land far below this; a different quantity
        # (different digits) lands well above it.
        try:
            qty_tol = float(self._mm_get("memory_match_qty_tolerance", 0.12))
        except Exception:
            qty_tol = 0.12
        # Full-tile pixel similarity stays only a SOFT secondary guard (the
        # semi-transparent background differs per cell).
        try:
            pixel_floor = float(self._mm_get("memory_match_pixel_floor", 0.55))
        except Exception:
            pixel_floor = 0.55
        tmpdir = self._mm_get("memory_match_screenshot_dir") or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "memory_match")
        try:
            os.makedirs(tmpdir, exist_ok=True)
        except Exception:
            pass

        x0, y0, w, h = int(grid[0]), int(grid[1]), int(grid[2]), int(grid[3])
        cols, rows = 5, 4
        col_w = w / cols
        row_h = h / rows
        park_x = max(2, int(x0) - 30)
        park_y = max(2, int(y0) - 25)

        # Covered-tile reference: the pre-Start baseline screenshot
        # (logs/memory_match/grid_baseline.png, saved by play_memory_match)
        # shows the board BEFORE any tile was flipped. A capture whose
        # center matches that look is a COVERED (not-yet-flipped) tile, not
        # an icon - without this check two covered cells would "match" each
        # other (the cover has its own center signature) and poison the
        # memory with false pairs after a missed click or a slow flip.
        covered_center = None
        baseline_path = os.path.join(tmpdir, "grid_baseline.png")
        if os.path.exists(baseline_path):
            try:
                from PIL import Image
                _pad0 = int(self._mm_get("memory_match_cell_padding", 4))
                _cw0 = max(50, min(int(col_w) - 2 * _pad0, 220))
                _ch0 = max(40, min(int(row_h) - 2 * _pad0, 140))
                _cx0, _cy0, _, _ = cells[0]
                _bx = int(_cx0) - _cw0 // 2 - int(grid[0])
                _by = int(_cy0) - _ch0 // 2 - int(grid[1])
                base_img = Image.open(baseline_path)
                cover_crop = base_img.crop((_bx, _by, _bx + _cw0, _by + _ch0))
                covered_center = _center_signature(cover_crop)
                if covered_center is not None:
                    self._mm_log("[MemoryMatch] Covered-tile reference loaded from grid_baseline.png "
                                 f"(center {_fmt_center(covered_center)}) - covered cells are treated as unreadable.")
            except Exception:
                covered_center = None

        def _click_cell(c, r):
            target = next((t for t in cells if t[2] == c and t[3] == r), None)
            if not target:
                return
            cx, cy, _, _ = target
            try:
                autoit.mouse_click("left", int(cx), int(cy), 1, speed=3)
            except Exception:
                pass

        def _park_mouse():
            try:
                autoit.mouse_move(int(park_x), int(park_y), 0)
            except Exception:
                pass

        def _capture_cell(c, r, retries: int = 3, retry_delay: float = 0.45) -> dict:
            """Screenshot the flipped tile and read it.

            Up to `retries` snapshots (~retry_delay apart) are taken until
            BOTH the icon (center signature) and the quantity are recognized
            - a mid-flip animation or a hover overlay often spoils the first
            frame. Returns {"sig", "center", "qty", "path", "readable"};
            "path" is the last screenshot (always kept for diagnostics).
            """
            target = next((t for t in cells if t[2] == c and t[3] == r), None)
            path = os.path.join(tmpdir, f"cell_{c}_{r}.png")
            if not target:
                return {"sig": None, "center": None, "qty": None, "qty_sig": None,
                        "qty_aspect": None, "path": path, "readable": False}
            cx, cy, _, _ = target
            cw = max(50, min(int(col_w) - 2 * int(self._mm_get("memory_match_cell_padding", 4)), 220))
            ch = max(40, min(int(row_h) - 2 * int(self._mm_get("memory_match_cell_padding", 4)), 140))
            state = {"sig": None, "center": None, "qty": None, "qty_sig": None,
                     "qty_aspect": None, "path": path, "readable": False}
            for attempt in range(1, retries + 1):
                captured = _capture_tile_screenshot(int(cx) - cw // 2, int(cy) - ch // 2, cw, ch, path)
                if captured:
                    try:
                        from PIL import Image
                        tile_img = Image.open(path)
                        state["sig"] = _tile_signature(tile_img)
                        state["center"] = _center_signature(tile_img)
                        # Pixel mask of the quantity text - works even when
                        # Windows OCR cannot read the small translucent text.
                        state["qty_sig"] = _qty_strip_signature(tile_img)
                        state["qty_aspect"] = _qty_strip_aspect(tile_img)
                    except Exception:
                        state["sig"] = None
                        state["center"] = None
                        state["qty_sig"] = None
                        state["qty_aspect"] = None
                    state["qty"] = _ocr_quantity_from_file(path)
                    covered = (
                        covered_center is not None
                        and state["center"] is not None
                        and _center_distance(state["center"], covered_center) <= center_tol
                    )
                    state["readable"] = state["center"] is not None and not covered
                    # icon read -> give qty one extra attempt, then accept
                    # (a tile whose quantity never OCRs is still usable:
                    # identity comes from the center signature)
                    icon_done = state["readable"] and (state["qty"] or attempt >= 2)
                    if icon_done or attempt == retries:
                        icon_state = "ok" if state["readable"] \
                            else ("COVERED" if covered else "UNREADABLE")
                        suffix = "" if state["readable"] else f" ({path})"
                        self._mm_log(
                            f"[MemoryMatch] Cell ({c},{r}): icon={icon_state} "
                            f"qty={state['qty'] or '?qty?'}{suffix}"
                        )
                        break
                else:
                    if attempt == retries:
                        self._mm_log(
                            f"[MemoryMatch] Cell ({c},{r}): screenshot FAILED "
                            f"region=({int(cx) - cw // 2},{int(cy) - ch // 2},{cw}x{ch})"
                        )
                if attempt < retries:
                    if not self._mm_sleep(retry_delay):
                        break
            return state

        def _remember_tile(c, r, state: dict):
            if state and (state.get("center") is not None or state.get("qty")):
                tile_state[(c, r)] = state

        def _tiles_same(a, b) -> bool:
            """Same item pair = identical center icon grid (within tolerance)
            AND equal quantity (when both were readable OR when the pixel
            masks of the quantity text clearly differ)."""
            if not a or not b:
                return False
            if a.get("center") is None or b.get("center") is None:
                return False
            if _center_distance(a.get("center"), b.get("center")) > center_tol:
                return False
            qa, qb = a.get("qty"), b.get("qty")
            if qa and qb and qa != qb:
                # Same art but different quantity -> different tile pair
                return False
            # Pixel-level quantity check (works even when OCR returned
            # nothing for BOTH tiles - the qty=?qty? case that used to
            # create false pairs): the same quantity yields nearly the
            # same bright-text mask; a different quantity changes the
            # digit shapes and usually the text-box width as well.
            qsa, qsb = a.get("qty_sig"), b.get("qty_sig")
            if qsa is not None and qsb is not None:
                wa, wb = a.get("qty_aspect"), b.get("qty_aspect")
                if wa and wb and max(wa, wb) / max(0.01, min(wa, wb)) > 1.35:
                    return False
                if _qty_mask_distance(qsa, qsb) > qty_tol:
                    return False
            return _tile_similarity(a.get("sig"), b.get("sig")) >= pixel_floor

        def _tiles_similarity(a, b) -> float:
            return _tile_similarity((a or {}).get("sig"), (b or {}).get("sig"))

        def _center_of(state):
            return (state or {}).get("center")

        def _reveal(c, r) -> dict:
            """Click one tile, let the flip finish, park the mouse, read it."""
            _click_cell(c, r)
            if not self._mm_sleep(0.6):
                return {"sig": None, "qty": None}
            _park_mouse()
            if not self._mm_sleep(0.15):
                return {"sig": None, "qty": None}
            state = _capture_cell(c, r)
            state["pos"] = (c, r)
            _remember_tile(c, r, state)
            return state

        def _find_partner(state, exclude=()) -> tuple | None:
            """Compare `state` against ALL remembered tiles and return the
            BEST candidate by center-signature distance (None if nothing
            strictly matches). Logged as ONE summary line per reveal."""
            if not state or state.get("center") is None:
                return None
            best_pos = None
            best_dist = 1e9
            second_dist = 1e9
            memory_count = 0
            for pos, st in sorted(tile_state.items()):
                if pos in matched or pos in exclude:
                    continue
                # A pair that already failed the stay-open check is never
                # suggested again - find a different partner for this tile.
                if frozenset((pos, state.get("pos"))) in failed_pairs:
                    continue
                memory_count += 1
                d = _center_distance(state.get("center"), st.get("center"))
                same = _tiles_same(state, st)
                if same:
                    if d < best_dist:
                        second_dist = best_dist
                        best_pos = pos
                        best_dist = d
                    elif d < second_dist:
                        second_dist = d
                elif d < second_dist:
                    second_dist = d
            if memory_count == 0:
                self._mm_log("[MemoryMatch] Memory is empty - no remembered tiles to compare against.")
            else:
                # Accept the best candidate either by the absolute tolerance,
                # or (when the threshold is slightly off for this item) by a
                # CLEAR margin: the best matching tile must be ~1.5x closer
                # than the runner-up. This keeps matching working when the
                # per-item signature noise shifts with the background.
                margin_ok = (
                    best_pos is not None
                    and best_dist <= center_tol * 1.75
                    and second_dist >= best_dist / 0.65
                )
                if best_pos is not None and (best_dist <= center_tol or margin_ok):
                    self._mm_log(
                        f"[MemoryMatch] Cell {state.get('pos')} matches memory {best_pos} "
                        f"(center dist {best_dist:.0f}, runner-up {second_dist:.0f}, tol {center_tol:.0f})"
                    )
                else:
                    if best_pos is not None:
                        # margin not clear enough - do not guess, keep exploring
                        self._mm_log(
                            f"[MemoryMatch] Cell {state.get('pos')}: candidate {best_pos} at "
                            f"{best_dist:.0f} vs runner-up {second_dist:.0f} - margin unclear, no match"
                        )
                        best_pos = None
                    else:
                        self._mm_log(
                            f"[MemoryMatch] Cell {state.get('pos')}: {memory_count} comparisons, "
                            f"best center dist {second_dist:.0f} (tol {center_tol:.0f}) - no match"
                        )
            return best_pos

        _UNREADABLE_ABORT = 3  # consecutive unreadable cells before aborting
        unreadable_streak = 0

        def _note_readability(state) -> bool:
            """Track a run of unreadable cells; log the screenshot path."""
            nonlocal unreadable_streak
            if state and "readable" in state and not state["readable"]:
                unreadable_streak += 1
                self._mm_log(
                    f"[MemoryMatch] Cell {state.get('pos')} UNREADABLE after retries "
                    f"(streak {unreadable_streak}/{_UNREADABLE_ABORT}) - "
                    f"screenshot: {state.get('path')}"
                )
                return False
            unreadable_streak = 0
            return True

        def _diagnose_unreadable_board():
            """Several cells in a row came back unreadable - most likely the
            grid calibration or the board-confirmation step drifted. Save a
            full-board screenshot and log what to check."""
            board_path = os.path.join(tmpdir, "board_debug.png")
            _capture_tile_screenshot(int(grid[0]), int(grid[1]), int(grid[2]), int(grid[3]), board_path)
            pad = int(self._mm_get("memory_match_cell_padding", 4))
            cw = max(50, min(int(col_w) - 2 * pad, 220))
            ch = max(40, min(int(row_h) - 2 * pad, 140))
            self._mm_log(
                "[MemoryMatch] DIAGNOSTIC: cells are unreadable in a row. "
                f"grid region x={int(grid[0])} y={int(grid[1])} w={int(grid[2])} h={int(grid[3])}, "
                f"5x4 grid -> cell capture {cw}x{ch}px, board_confirmed={board_confirmed}. "
                f"Full-board screenshot saved: {board_path}. "
                "Check it: if tiles lie outside the region or the game dialog is not open, "
                "re-calibrate the grid (Macro Calibrations -> Memory Match) and verify the walk "
                "reaches the board and Start is actually clicked."
            )

        def _abort_if_unreadable() -> bool:
            """True -> the game must be aborted (too many unreadable cells)."""
            if unreadable_streak < _UNREADABLE_ABORT:
                return False
            _diagnose_unreadable_board()
            out["aborted"] = "cells unreadable"
            self._mm_log(
                "[MemoryMatch] Aborting the game: cells cannot be read, "
                "further flips would be wasted."
            )
            return True

        def _known_pair():
            """First pair of remembered tiles that match each other exactly."""
            entries = [(pos, st) for pos, st in tile_state.items() if pos not in matched]
            for i in range(len(entries)):
                pos_a, st_a = entries[i]
                for j in range(i + 1, len(entries)):
                    pos_b, st_b = entries[j]
                    if frozenset((pos_a, pos_b)) in failed_pairs:
                        continue
                    if _tiles_same(st_a, st_b):
                        return (pos_a, pos_b)
            return None

        def _best_similarity_pair(min_sim: float = 0.85):
            """Recovery: all tiles known but no pair passed the strict check.
            Pairs that already failed TWICE are never retried; a pair that
            failed once is used only as a last resort (the first failure
            may have been a mistimed click, not a real mismatch)."""
            best_center = None
            best_dist = 1e9
            best_sim_pair = None
            best_ratio = 0.0
            best_center_fails = 99
            best_sim_fails = 99
            entries = [(pos, st) for pos, st in tile_state.items() if pos not in matched]
            for i in range(len(entries)):
                pos_a, st_a = entries[i]
                for j in range(i + 1, len(entries)):
                    pos_b, st_b = entries[j]
                    fails = failed_pairs.get(frozenset((pos_a, pos_b)), 0)
                    if fails >= 2:
                        continue
                    d = _center_distance(st_a.get("center"), st_b.get("center"))
                    if d < best_dist or (d == best_dist and fails < best_center_fails):
                        best_dist = d
                        best_center = (pos_a, pos_b)
                        best_center_fails = fails
                    ratio = _tiles_similarity(st_a, st_b)
                    if ratio > best_ratio or (ratio == best_ratio and fails < best_sim_fails):
                        best_ratio = ratio
                        best_sim_pair = (pos_a, pos_b)
                        best_sim_fails = fails
            if best_center and best_dist <= center_tol + 14:
                return best_center
            if best_sim_pair and best_ratio >= min_sim:
                return best_sim_pair
            return None

        def _qty_label(state) -> str:
            q = (state or {}).get("qty")
            return q if q else "?qty?"

        def _finish_pair(pos_a, pos_b, label: str = "") -> bool:
            """Wait out the resolve cooldown, then VERIFY the pair actually
            scored: a scored pair stays revealed, a failed one flips back.
            On success the tiles leave memory; on failure both stay known."""
            if not self._mm_sleep(1.1):
                return False
            _park_mouse()
            if not self._mm_sleep(0.2):
                return False
            re_a = _capture_cell(*pos_a)
            re_b = _capture_cell(*pos_b)
            ref_a = tile_state.get(pos_a)
            ref_b = tile_state.get(pos_b)
            stayed_open = False
            if ref_a and ref_b and _center_of(re_a) is not None and _center_of(re_b) is not None:
                stayed_open = (
                    _center_distance(_center_of(re_a), _center_of(ref_a)) <= center_tol + 12
                    and _center_distance(_center_of(re_b), _center_of(ref_b)) <= center_tol + 12
                )
            if stayed_open:
                matched.add(pos_a)
                matched.add(pos_b)
                tile_state.pop(pos_a, None)
                tile_state.pop(pos_b, None)
                out["matches"] += 1
                self._mm_log(f"[MemoryMatch] Paired {label} tile {pos_a}+{pos_b} qty={_qty_label(re_a)}")
                return True
            # Not scored (or the read failed) - the tiles flip back. Keep the
            # ORIGINAL remembered signatures: re-membering the re-capture
            # would poison memory with the covered-tile look (a flipped-back
            # tile shows the cover, not its icon).
            for pos, re_st, ref in ((pos_a, re_a, ref_a), (pos_b, re_b, ref_b)):
                if ref is None and re_st and re_st.get("center") is not None:
                    _remember_tile(pos[0], pos[1], re_st)
            # Remember the false pair so the turn loop moves on to new tiles
            # instead of re-flipping the same two cells every turn.
            pair_key = frozenset((pos_a, pos_b))
            failed_pairs[pair_key] = failed_pairs.get(pair_key, 0) + 1
            self._mm_log(
                f"[MemoryMatch] Pair {pos_a}+{pos_b} did NOT stay open "
                f"(fail #{failed_pairs[pair_key]}) - original memory kept, "
                "this pair will not be retried automatically"
            )
            return False

        for turn in range(10):
            if not getattr(self, "detection_running", False):
                break
            out["turns_used"] = turn + 1
            turn_matched = False

            known = _known_pair()
            if known:
                # 1) Confirmed pair in memory - spend this turn to collect it.
                pos_a, pos_b = known
                c_a, r_a = pos_a
                c_b, r_b = pos_b
                _click_cell(c_a, r_a)
                if not self._mm_sleep(0.6):
                    break
                _park_mouse()
                # Safety check: the flipped tile should still look remembered.
                fresh = _capture_cell(c_a, r_a)
                fresh_dist = _center_distance(_center_of(fresh), _center_of(tile_state.get(pos_a)))
                if _center_of(fresh) is not None and fresh_dist > center_tol + 10:
                    # The tile shows something else than remembered (most
                    # likely the click missed and it is still covered).
                    # Keep the ORIGINAL signature - overwriting memory with
                    # the covered look would poison it.
                    self._mm_log(f"[MemoryMatch] Tile {pos_a} changed since memory "
                                 f"(center dist {fresh_dist:.0f}) - original memory kept")
                else:
                    _click_cell(c_b, r_b)
                    if not self._mm_sleep(0.6):
                        break
                    turn_matched = _finish_pair(pos_a, pos_b, label="known")
            else:
                unknowns = [t for t in cells if (t[2], t[3]) not in tile_state and (t[2], t[3]) not in matched]
                unknowns.sort(key=lambda t: (t[3], t[2]))  # top-to-bottom, left-to-right
                if unknowns:
                    # 2) Reveal ONE unknown tile. If it matches memory, bank
                    #    the pair with the partner as this turn's second flip.
                    _, _, c_a, r_a = unknowns[0]
                    st_a = _reveal(c_a, r_a)
                    if not getattr(self, "detection_running", False):
                        break
                    _note_readability(st_a)
                    if _abort_if_unreadable():
                        return out
                    partner = _find_partner(st_a, exclude=((c_a, r_a),))
                    if partner is not None:
                        c_b, r_b = partner
                        _click_cell(c_b, r_b)
                        if not self._mm_sleep(0.6):
                            break
                        turn_matched = _finish_pair((c_a, r_a), partner, label="memory")
                    elif len(unknowns) >= 2:
                        # 3) No partner in memory - spend the second flip on
                        #    new information. The second tile is compared with
                        #    ALL remembered tiles too (including the first one
                        #    revealed this turn), best center-distance wins.
                        _, _, c_b, r_b = unknowns[1]
                        st_b = _reveal(c_b, r_b)
                        if not getattr(self, "detection_running", False):
                            break
                        _note_readability(st_b)
                        if _abort_if_unreadable():
                            return out
                        partner_b = _find_partner(st_b, exclude=((c_b, r_b),))
                        if partner_b is not None:
                            turn_matched = _finish_pair((c_b, r_b), partner_b, label="memory")
                        # no partner: the two per-cell summary lines above
                        # already carry the result - no extra log needed
                    # exactly one unknown left and no partner: nothing to gain,
                    # the recovery branch handles the leftovers.
                else:
                    # 4) All tiles known, no strict pair - noise recovery.
                    recovery = _best_similarity_pair()
                    if not recovery:
                        break
                    pos_a, pos_b = recovery
                    c_a, r_a = pos_a
                    c_b, r_b = pos_b
                    _click_cell(c_a, r_a)
                    if not self._mm_sleep(0.6):
                        break
                    _click_cell(c_b, r_b)
                    if not self._mm_sleep(0.8):
                        break
                    turn_matched = _finish_pair(pos_a, pos_b, label="recovery")

            # The game closes non-matching tiles after a short cooldown -
            # never click the next pair before the board settles.
            gap = 1.2 if turn_matched else 1.7
            if not self._mm_sleep(gap):
                break

        return out

    # ---- periodic loop ----
    def memory_match_loop(self):
        """
        Background thread: runs while macro is active, checks every N minutes
        if Memory Match cooldown is ready, then plays one round.
        """
        try:
            while getattr(self, "detection_running", False):
                try:
                    if not self.mm_is_enabled():
                        time.sleep(10)
                        continue
                    if not self.mm_cooldown_ready():
                        # Log the cooldown state once per hour so silent
                        # waiting is visible in the logs.
                        if (datetime.now() - getattr(self, "_mm_last_cooldown_log", datetime.min)).total_seconds() >= 3600:
                            self._mm_last_cooldown_log = datetime.now()
                            ready_at = datetime.now() + timedelta(seconds=self.mm_seconds_until_ready())
                            self._mm_log(f"[MemoryMatch] On cooldown — next session ready at {ready_at.strftime('%H:%M')}.")
                        time.sleep(60)
                        continue
                    # Don't run if other exclusive features are active
                    if (getattr(self, "_egg_collecting", False) or
                        getattr(self, "_eden_running", False) or
                        getattr(self, "_potion_thread_active", False) or
                        getattr(self, "_obby_running", False) or
                        getattr(self, "_br_sc_running", False)):
                        time.sleep(10)
                        continue
                    # Don't run if fishing is exclusive (user disabled integration)
                    play_with_fishing = bool(self._mm_get("memory_match_play_on_fishing", True))
                    if (not play_with_fishing) and self._is_fishing_active():
                        time.sleep(60)
                        continue
                    # Schedule the play as a one-shot action so it goes through the
                    # action scheduler (similar to periodic quest claim) and doesn't
                    # block the main loop.
                    try:
                        self._action_scheduler.enqueue_action(
                            self._mm_play_via_scheduler,
                            name="memory_match:play",
                            priority=4,
                        )
                    except Exception:
                        pass
                    # No separate check interval: the 12h cooldown (plus the
                    # ~30min retry for failed sessions) IS the schedule. The
                    # loop simply polls every minute until the cooldown ends.
                    slept = 0.0
                    while slept < 60 and getattr(self, "detection_running", False):
                        time.sleep(1)
                        slept += 1
                except Exception as e:
                    try:
                        self.error_logging(e, "memory_match_loop error")
                    except Exception:
                        pass
                    time.sleep(30)
        except Exception:
            pass

    def _mm_play_via_scheduler(self):
        """Wrapper that runs play_memory_match in scheduler context."""
        try:
            res = self.play_memory_match()
            try:
                self.append_log(f"[MemoryMatch] Done: {res.get('matches')}/{res.get('turns_used')} pairs")
            except Exception:
                pass
        except Exception as e:
            try:
                self.error_logging(e, "_mm_play_via_scheduler")
            except Exception:
                pass

    # ---- helpers used by integration points ----
    def _is_fishing_active(self) -> bool:
        try:
            return bool(self.is_fishing_mode_enabled())
        except Exception:
            return False
