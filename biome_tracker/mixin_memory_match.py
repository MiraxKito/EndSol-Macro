"""
Memory Match auto-player mixin for EndSol Macro.

Sol's RNG Memory Match (added Eon 1-2, expanded Summer 2026):
  - 5x4 grid of tiles, 10 chances (each chance = 2 tiles flipped)
  - Match identical pairs; matched tiles stay revealed (green)
  - 12 hour cooldown between matches (-3h per ad watched, max 3 ads)
  - Location: near the beach, opposite direction from fishing
  - Rewards: Potions, Void Coin, Rune, Godly/Heavenly/Godlike Potion, etc.

Player logic (2026-09-27 rewrite, image-only - no item-name OCR):
  1. Click Start, wait for the panel to load, wait until tiles render
  2. Each attempt opens exactly 2 tiles (10 attempts per game):
       - a remembered pair (same item art AND same quantity) is collected
         from memory first - never spend attempts blindly;
       - otherwise reveal unknown tiles one by one; every reveal is stored
         in a full 20-tile memory (item art + quantity at that position);
       - a newly revealed tile that matches a remembered tile is paired
         with it immediately (the remembered tile becomes this attempt's
         second flip);
  3. After the second flip the game itself is the arbiter: a scored pair
     stays revealed with a green highlight, a missed pair flips back
     covered. The verdict is read from the board after a configurable
     resolve delay - memory is never "corrected" against the game.
  4. An item type may appear as ONE pair (2 tiles) or TWO pairs (4 tiles),
     never more - identity groups of 2/4 cells handle both.
  5. When all 10 attempts are spent the game reveals every tile and shows
     the Close button (handled by play_memory_match).
"""

import json
import os
import shutil
import time

import numpy as np
from datetime import datetime, timedelta

import autoit

try:
    from .config import APPDATA_BASE
except Exception:  # pragma: no cover - direct-file import fallback
    APPDATA_BASE = None

try:
    import keyboard  # character reset (Esc -> R -> Enter)
except Exception:  # pragma: no cover - keyboard is a hard dependency of the macro
    keyboard = None


# Fixed player timings (seconds), NOT configurable on purpose (owner decision
# 2026-09-27): every action needs its loading window - the panel after Start,
# a tile flip before it can be captured (the owner asked for a capture
# 0.8-1s AFTER the click with the mouse parked away), the second tile must be
# captured BEFORE the game resolves the pair, the pair verdict is POLLED
# (green stay-open vs flip-back), and the end-of-game reveal-all animation
# runs before the Close button appears.
MM_START_DELAY = 4.0            # panel load after Start
MM_REVEAL_DELAY = 1.4           # click -> smooth park -> wait -> capture
MM_SECOND_REVEAL_DELAY = 1.0    # 2nd tile capture, before the game resolves
MM_RESOLVE_TIMEOUT = 8.0        # poll the pair verdict up to this long
MM_RESOLVE_POLL_INTERVAL = 0.6
MM_SETTLE_TIMEOUT = 4.0         # unresolved pair: wait for the flip-back
MM_ATTEMPT_GAP = 1.0
MM_END_REVEAL_DELAY = 8.0
MM_GREEN_FRACTION = 0.2         # matched tiles carry a large green highlight


def _mm_data_dir(sub: str = "memory_match") -> str:
    """Temporary Memory Match data (captures, baselines, debug shots).

    NOTHING is written inside the macro root: all temporary data lives in
    the user's local application-data folder (%LOCALAPPDATA%/EndSolMacro).
    """
    try:
        if APPDATA_BASE is not None:
            return str(APPDATA_BASE / sub)
    except Exception:
        pass
    return os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"),
                        "EndSolMacro", sub)


def _mm_purge_previous_session(tmpdir: str) -> None:
    """v44.2: keep ONLY the latest session's captures (user request).

    Every new Memory Match session wipes the previous session's cell
    captures, cover references, baseline and debug shots from the
    screenshot directory; the new session then rewrites everything it
    needs. The folder can no longer grow without bound across days of
    runs. The separate thumb_cache directory is NOT touched."""
    try:
        d = str(tmpdir or "")
        if not d or not os.path.isdir(d):
            return
        import glob as _glob
        for pattern in ("cell_*.png", "cover_ref*.png", "grid_baseline.png"):
            for f in _glob.glob(os.path.join(d, pattern)):
                try:
                    os.remove(f)
                except Exception:
                    pass
        dbg = os.path.join(d, "debug")
        if os.path.isdir(dbg):
            for f in os.listdir(dbg):
                fp = os.path.join(dbg, f)
                try:
                    if os.path.isfile(fp):
                        os.remove(fp)
                except Exception:
                    pass
    except Exception:
        pass

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


def _tile_bg_color(img) -> tuple | None:
    """Median color of the tile's outer ring = card/background base color."""
    try:
        arr = np.asarray(img.convert("RGB")).astype(float)
        h, w, _ = arr.shape
        k = max(2, int(min(h, w) * 0.10))
        ring = np.concatenate([
            arr[:k].reshape(-1, 3), arr[-k:].reshape(-1, 3),
            arr[:, :k].reshape(-1, 3), arr[:, -k:].reshape(-1, 3),
        ])
        return tuple(np.median(ring, axis=0))
    except Exception:
        return None


# A revealed tile shows real item art (hundreds of content pixels on a live
# capture); a COVERED card or a mid-flip frame has almost none. Any capture
# below this content floor is treated as not-a-tile-item (covered/unreadable)
# and NEVER enters memory - covered cells used to pass as "identical items"
# and made the matcher click random covered pairs forever.
_MIN_ICON_PIXELS = 40

# v41: a revealed tile's OPAQUE art is strongly saturated (live board:
# 7000+ saturated px), a covered card is not (<= ~1200 through the dimming
# translucent panel). The gap between the two decides "is this tile showing
# an item" — see _tile_icon_descriptor. Configurable, since the threshold
# depends on the game's art and the panel's translucency.
_MIN_ART_PIXELS = 2500

# v42.1: DIM ITEMS. Live board 2026-09-29 (user capture cell_0_0.png): a
# muted brown item keeps only ~1.8k saturated px even at saturation > 30 —
# the 2500 gate read a REVEALED tile as "unreadable" forever and the loop
# re-clicked the open cell endlessly. Dim items still draw their WHITE
# QUANTITY BARS in the lower strip of the tile; covered cards have none
# (their gray emblem ends above the strip, the card back is uniform).
# A dim capture therefore passes the gate only with bar evidence.
# v45.1: floor lowered 500 -> 200 — a real-board item measured only 297
# saturated px (cell_2_0.png) with 220 bar pixels; covered detection no
# longer relies on the art gate alone (see the covered-reference diff).
_MIN_ART_PIXELS_DIM = 200


def _strip_mean_diff(img_a, img_b) -> float:
    """Mean per-pixel difference (0..255) between two tile captures over the
    LOWER strip (y 78%..99%, x 8%..92%) — the quantity-bars region.

    Live-board calibration (2026-09-29 user archive): a COVERED card is
    pixel-stable — two frames 0.9 s apart differ by 0.0-0.2 — while a
    revealed dim item differs from its own covered reference by 19-31 in
    that strip. The card back is opaque in practice, so this diff is a
    reliable 'is this tile still showing the covered card' signal."""
    try:
        a = np.asarray(img_a.convert("RGB")).astype(float)
        b_img = img_b
        if b_img.size != img_a.size:
            b_img = b_img.resize(img_a.size)
        b = np.asarray(b_img.convert("RGB")).astype(float)
        h, w, _ = a.shape
        sa = a[int(h * 0.78):int(h * 0.99), int(w * 0.08):int(w * 0.92)]
        sb = b[int(h * 0.78):int(h * 0.99), int(w * 0.08):int(w * 0.92)]
        if sa.size == 0 or sb.size == 0:
            return 999.0
        return float(np.abs(sa - sb).mean())
    except Exception:
        return 999.0


def _tile_has_qty_bars(rgb, h: int, w: int) -> bool:
    """White quantity-bar evidence in the LOWER strip of a revealed tile.

    The strip starts below the covered card's emblem (measured: emblem
    ends at y~0.77 of the tile, the bars sit at y 0.80..0.95) and counts
    pixels that are BOTH clearly brighter than the tile's own background
    ring AND low-saturated — the white bars and quantity digits. Covered
    cards keep this region uniform (nothing differs from the background),
    and a mid-flip frame whose background is uniformly bright differs from
    its own background nowhere, so neither can fake the bars."""
    try:
        ring = np.concatenate([
            rgb[:2].reshape(-1, 3), rgb[-2:].reshape(-1, 3),
            rgb[:, :2].reshape(-1, 3), rgb[:, -2:].reshape(-1, 3)])
        bg = np.median(ring, axis=0)
        strip = rgb[int(h * 0.78):int(h * 0.98), int(w * 0.10):int(w * 0.90)]
        if strip.size == 0:
            return False
        mx = strip.max(axis=2)
        mn = strip.min(axis=2)
        sat = np.where(mx > 0, (mx - mn) * 255 // np.maximum(mx, 1), 0)
        bars = (mx > 170) & (sat < 70) & (np.abs(strip - bg).max(axis=2) > 50)
        return int(bars.sum()) >= 24
    except Exception:
        return False


def _tile_icon_descriptor(img) -> tuple | None:
    """
    Identity descriptor of a revealed tile's ITEM ART (v41 rewrite).

    Why the previous background-subtracted descriptors failed on the live
    board (8-hour session, 2026-09-29 debug archive): the tile cards are
    SEMI-TRANSPARENT, so the game landscape behind them bleeds into every
    capture and changes from frame to frame and cell to cell; captures of the
    same item in different cells are also misaligned by 1-8 px (int rounding
    of the equal-divided grid). Measured consequence: two captures of the SAME
    game-scored pair compared at icon distance 33 (tolerance was 0.9) while
    different items measured 8-78 — the ranges overlapped and the memory
    NEVER matched a single pair in 10 attempts.

    The item art is the only OPAQUE, SATURATED part of a revealed tile:
      1. art mask = HSV pixels with saturation > 90 and value > 60.
         Live board: a revealed item has 7000+ such pixels, a covered card
         at most ~1200 (the dim, desaturated landscape bleed; the covered
         card's own emblem is gray and does not pass the saturation gate);
      2. fewer than _MIN_ART_PIXELS mask pixels = covered card or a
         mid-flip frame -> None (never enters memory as an item). A fully
         desaturated (gray/white) item would also read as covered —
         accepted: it only wastes exploration attempts, never poisons
         the memory, and the game's own verdicts stay correct;
      3. descriptor = the mask's bounding box resized to 16x16 (shape)
         plus the mean RGB inside the mask (color). The bbox self-normalizes
         the position, so a +7 px capture shift changes the distance by ~0.004.

    Measured on the 2026-09-29 archive: same item shape 0.052 / color 0.9,
    different items 0.198 / 10.7 — see _icon_distance for the scale."""
    try:
        from PIL import Image
        img = img.convert("RGB")
        hsv = np.asarray(img.convert("HSV")).astype(float)
        rgb = np.asarray(img).astype(float)
        h = min(hsv.shape[0], rgb.shape[0])
        w = min(hsv.shape[1], rgb.shape[1])
        s = hsv[:h, :w, 1]
        v = hsv[:h, :w, 2]
        mask = (s > 90) & (v > 60)
        if int(mask.sum()) < _MIN_ART_PIXELS:
            # v42.1: dim-item second chance — a muted item keeps its white
            # quantity bars even when the art itself has few saturated
            # pixels; a covered card has neither (see _MIN_ART_PIXELS_DIM).
            n_sat = int(mask.sum())
            if n_sat < _MIN_ART_PIXELS_DIM or not _tile_has_qty_bars(rgb, h, w):
                return None
        ys, xs = np.nonzero(mask)
        pad = 2
        by0, by1 = max(0, int(ys.min()) - pad), min(h, int(ys.max()) + 1 + pad)
        bx0, bx1 = max(0, int(xs.min()) - pad), min(w, int(xs.max()) + 1 + pad)
        m = mask[by0:by1, bx0:bx1].astype(float)
        art = rgb[by0:by1, bx0:bx1] * m[:, :, None]
        color = art.reshape(-1, 3).sum(axis=0) / max(1.0, float(mask.sum()))
        shape = np.asarray(Image.fromarray(
            np.clip(m * 255.0, 0, 255).astype("uint8")
        ).resize((16, 16), Image.BOX)).astype(float) / 255.0
        return tuple(shape.ravel()) + tuple(color)
    except Exception:
        return None


def _icon_distance(a, b) -> float:
    """Distance between two icon descriptors: 50*shape + 1.5*color.

    Live-capture separation (2026-09-29 archive): the same item measures
    ~4.0 (0.052 shape, 0.9 color), different items 26+ (0.198, 10.7) — the
    default identity tolerance (12) sits ~3x above 'same' and ~2x below
    'different'. The old single-scale metric mixed a 0..1 shape with a
    0..255 color and could never separate the two."""
    if a is None or b is None:
        return 999.0
    try:
        shape = sum(abs(pa - pb) for pa, pb in zip(a[:256], b[:256])) / 256.0
        color = sum(abs(pa - pb) for pa, pb in zip(a[256:], b[256:])) / 3.0
        return 50.0 * shape + 1.5 * color
    except Exception:
        return 999.0


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


def _tile_qty_descriptor(img) -> tuple | None:
    """
    Background-invariant image descriptor of the tile's bottom strip (the
    quantity text, plus whatever item art reaches into the strip).

    The pairing rule is "same item AND same quantity", so the quantity is
    part of the tile's identity - but it is compared AS AN IMAGE, never
    OCR'd (OCR on the small translucent text was unreliable and cost ~3s
    per cell). Same recipe as the icon descriptor:
      1. background estimate = median color of the tile's outer ring;
      2. content mask = pixels clearly different from that background;
      3. bounding box of the masked content, resized to a fixed 24x12 grid.

    Two tiles with the same quantity render nearly identical masks
    (distance ~0.0); a different quantity changes the digit shapes and the
    box width. A tile whose strip mask comes out empty on ONE side is
    treated as UNKNOWN, not as "different" - the ambiguous case is deferred
    to the stay-open verification (the game itself is the arbiter).
    """
    try:
        arr = np.asarray(img.convert("RGB")).astype(float)
        h, w, _ = arr.shape
        bg = np.array(_tile_bg_color(img) or (0.0, 0.0, 0.0))
        strip = arr[int(h * 0.58):int(h * 0.98), int(w * 0.08):int(w * 0.92)]
        mask = (np.abs(strip - bg).max(axis=2) > 50).astype(float) * 255.0
        ys, xs = np.nonzero(mask > 0)
        if len(xs) < 6:
            return None
        from PIL import Image
        crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
        small = Image.fromarray(crop.astype(np.uint8)).resize((24, 12), Image.BOX)
        return tuple(np.asarray(small).astype(float).ravel() / 255.0)
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


# ---------------------------------------------------------------------------
# Webhook helpers — download thumbnail locally so Discord renders it
# without depending on the upstream CDN.
# ---------------------------------------------------------------------------

_THUMB_CACHE_DIR = _mm_data_dir("thumb_cache")


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
        from .base_support import safe_get
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
        Fixed player timings (module constants, owner decision 2026-09-27):
            MM_START_DELAY 4.0 (panel load after Start, s)
            MM_REVEAL_DELAY 0.9 (click -> park -> wait -> capture, s)
            MM_SECOND_REVEAL_DELAY 0.8 (2nd tile capture before the game resolves, s)
            MM_RESOLVE_TIMEOUT 6.0 / MM_RESOLVE_POLL_INTERVAL 0.6 (verdict poll)
            MM_SETTLE_TIMEOUT 4.0 (unresolved pair: wait for the flip-back)
            MM_ATTEMPT_GAP 1.0 (pause between attempts, s)
            MM_END_REVEAL_DELAY 8.0 (reveal-all animation wait, s)
        memory_match_tile_match_threshold / _center_tolerance / _icon_tolerance /
            _qty_tolerance / _pixel_floor / _min_icon_pixels / _green_fraction:
            identity tuning (see _mm_play_grid)
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
            # Window check runs ONCE here, at the start of the cycle (the
            # character reset before the walk) - NOT before every tile click
            # (owner request 2026-09-28: no extra load mid-session).
            try:
                self._ensure_main_window_before_action(force=True)
            except Exception:
                pass
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
            _tmpdir0 = self._mm_get("memory_match_screenshot_dir") or _mm_data_dir()
            try:
                os.makedirs(_tmpdir0, exist_ok=True)
            except Exception:
                pass
            # v44.2: only the LATEST session's screenshots are kept —
            # wipe the previous session's captures before this one starts.
            _mm_purge_previous_session(_tmpdir0)
            _baseline = os.path.join(_tmpdir0, "grid_baseline.png")
            _capture_tile_screenshot(int(grid[0]), int(grid[1]), int(grid[2]), int(grid[3]), _baseline)
            try:
                autoit.mouse_click("left", int(start_btn[0]), int(start_btn[1]), 1, speed=3)
            except Exception:
                pass
            # The panel needs time to load after Start: the tiles flip in
            # one by one. Fixed delay first, then the render probe.
            if not sleep_interruptible(MM_START_DELAY):
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
            # Feed the persistent daily stats (mixin_extras).
            try:
                self._daily_bump("mm_pairs", int(result.get("matches", 0) or 0))
            except Exception:
                pass
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
            if not sleep_interruptible(MM_END_REVEAL_DELAY):
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
                # Extra settle between the reset keys: on low-FPS clients
                # the Esc menu / reset prompt renders late and a fast
                # R / Enter lands on nothing.
                keyboard.press_and_release('esc')
                if not self._mm_sleep(0.6):
                    return False
                keyboard.press_and_release('r')
                if not self._mm_sleep(0.6):
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
        tmpdir = self._mm_get("memory_match_screenshot_dir") or _mm_data_dir()
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
        Play one Memory Match game using the calibrated grid (2026-09-27 rewrite).

        Game rules (Sol's RNG, per the Fandom wiki page "Memory Match" and the
        live board):
          - 5x4 grid = 20 covered tiles; 10 attempts; one attempt = 2 flipped
            tiles.
          - Same item AND same quantity -> both tiles stay revealed with a
            GREEN highlight (the pair is scored). Anything else -> both tiles
            flip back covered, and their content never changes: the same item
            stays on the same position, so every reveal is worth remembering.
          - An item type may appear as ONE pair (2 tiles) or TWO pairs
            (4 tiles) - never more.
          - After the 10th attempt the game reveals every remaining tile and
            shows the Close button (handled by play_memory_match).

        Player algorithm (memory-first, never blind):
          memory  : every revealed tile is remembered as (item art, quantity)
                    at its exact position for the whole session;
          groups  : tiles sharing one identity form groups of 2 or 4 cells -
                    ANY two cells of a group are a valid pair for the game;
          attempt : 1) a group holding 2+ unmatched known tiles is collected
                       from memory - no exploration spent on it;
                    2) otherwise reveal the first unknown tile; if it matches
                       a remembered tile, that tile becomes the second flip
                       and the pair is banked immediately;
                    3) otherwise reveal a second unknown tile; a match with
                       the first tile banks a pair, a match with an older
                       tile stays in memory and is collected NEXT attempt;
          verdict : after the second flip the game itself is the arbiter -
                    both tiles are re-read after the resolve delay: still
                    revealed = scored pair (green), covered = flipped back
                    (memory stays). Failed pairs are never auto-retried.
        """
        out = {"matches": 0, "turns_used": 0}
        if not board_confirmed:
            self._mm_log(
                "[MemoryMatch] WARNING: the board was NOT confirmed before playing - "
                "if cells come back unreadable, check the grid calibration "
                "(Macro Calibrations -> Memory Match)."
            )
        cells = self._mm_cell_centers(grid)

        # ---- timings (all interruptible, all configurable) ----
        def _cfg_float(key, default):
            try:
                return float(self._mm_get(key, default))
            except Exception:
                return default

        reveal_delay = MM_REVEAL_DELAY
        second_reveal_delay = MM_SECOND_REVEAL_DELAY
        attempt_gap = MM_ATTEMPT_GAP
        # v41: identity tolerance on the NEW descriptor scale (50*shape +
        # 1.5*color; same item ~4, different items 26+). The old
        # memory_match_icon_tolerance key belonged to the retired descriptor
        # scale and is intentionally no longer read.
        icon_tol = _cfg_float("memory_match_identity_tolerance", 12.0)
        center_tol = _cfg_float("memory_match_center_tolerance", 20.0)
        # v45.1: strip-diff tolerance for the covered-reference check.
        # Real board (user archive 2026-09-29): a covered card differs from
        # its own reference by 0.0-0.2, a revealed dim item by 19-31 —
        # 6.0 sits ~30x above the noise and ~3x below the signal.
        cover_diff_tol = _cfg_float("memory_match_cover_diff_tolerance", 6.0)
        # Dedicated tolerance for COVER detection (real-board calibration,
        # 2026-09-28 debug archive: covered cells sit at center distance
        # 4-16 from their own post-Start reference, revealed items at 55+;
        # the identity tolerance alone misclassified one covered cell).
        cover_center_tol = max(center_tol, 30.0)
        qty_tol = _cfg_float("memory_match_qty_tolerance", 0.12)
        green_threshold = MM_GREEN_FRACTION
        global _MIN_ICON_PIXELS, _MIN_ART_PIXELS
        _MIN_ICON_PIXELS = max(8, int(_cfg_float("memory_match_min_icon_pixels", 40)))
        _MIN_ART_PIXELS = max(200, int(_cfg_float("memory_match_min_art_pixels", 2500)))

        tmpdir = self._mm_get("memory_match_screenshot_dir") or _mm_data_dir()
        try:
            os.makedirs(tmpdir, exist_ok=True)
        except Exception:
            pass

        x0, y0, w, h = int(grid[0]), int(grid[1]), int(grid[2]), int(grid[3])
        cols, rows = 5, 4
        col_w = w / cols
        row_h = h / rows
        # Park WELL outside the grid (the old 30px offset could still hover
        # a tile edge) and move there SMOOTHLY (speed 3, like the clicks).
        # Small screens: if the grid touches the left/top screen edge the
        # naive offset would park INSIDE the grid - fall back to the
        # opposite side so the cursor never hovers a tile.
        park_x = x0 - 60
        park_y = y0 - 45
        if park_x < 2:
            park_x = x0 + w + 40
        if park_y < 2:
            park_y = y0 + h + 40
        park_x = max(2, int(park_x))
        park_y = max(2, int(park_y))

        # Covered-tile references, per cell. REAL-board lesson (2026-09-28
        # debug archive): the pre-Start baseline shows a DIFFERENT screen
        # (start overlay), 30-60 mean pixel distance away from the actual
        # covered board - comparing against it never detected "covered" and
        # every verdict timed out. The truth is the board itself: right
        # after Start EVERY tile is covered, so a full-grid snapshot taken
        # then (and verified stable across two frames) provides the true
        # per-cell cover look. The pre-Start baseline is kept only as a
        # last-resort fallback (and for the "board changed" probe).
        covered_icons: dict[tuple[int, int], tuple | None] = {}
        covered_centers: dict[tuple[int, int], tuple | None] = {}
        # v45.1: per-cell COVERED REFERENCE CROPS. The covered card is
        # pixel-stable while the camera is fixed (two frames 0.9 s apart
        # differ by 0.0-0.2), so the strip diff against this crop decides
        # "covered" far more reliably than the art gate: a revealed DIM
        # item (297 saturated px) differs from its reference by 19-31.
        covered_crops: dict[tuple[int, int], Any] = {}
        baseline_path = os.path.join(tmpdir, "grid_baseline.png")
        if os.path.exists(baseline_path):
            try:
                from PIL import Image
                _pad0 = int(self._mm_get("memory_match_cell_padding", 4))
                _cw0 = max(50, min(int(col_w) - 2 * _pad0, 220))
                _ch0 = max(40, min(int(row_h) - 2 * _pad0, 140))
                base_img = Image.open(baseline_path)
                for _cx, _cy, _cc, _cr in cells:
                    _bx = int(_cx) - _cw0 // 2 - x0
                    _by = int(_cy) - _ch0 // 2 - y0
                    _crop = base_img.crop((_bx, _by, _bx + _cw0, _by + _ch0))
                    _ic = _tile_icon_descriptor(_crop)
                    if _ic is not None:
                        # v44.1: this cell shows a REAL ITEM in the baseline —
                        # the board was NOT fully covered before Start (the
                        # game was already open, e.g. one pair solved). A
                        # revealed tile must never become its own covered
                        # reference: it made the open tile read "covered"
                        # forever and the macro re-clicked it endlessly.
                        covered_icons[(_cc, _cr)] = None
                        covered_centers[(_cc, _cr)] = None
                    else:
                        covered_icons[(_cc, _cr)] = None
                        covered_centers[(_cc, _cr)] = _center_signature(_crop)
                        covered_crops[(_cc, _cr)] = _crop
            except Exception:
                pass

        def _capture_cover_refs() -> bool:
            """Build the REAL per-cell covered references from the board
            itself (all tiles are covered right after Start).

            Two snapshots ~0.9s apart must agree per cell (the world behind
            the semi-transparent panel keeps animating; a stable pair of
            frames means the board is fully rendered and covered). On
            success covered_icons/covered_centers are OVERWRITTEN with the
            post-Start references."""
            try:
                _padc = int(self._mm_get("memory_match_cell_padding", 4))
                _cwc = max(50, min(int(col_w) - 2 * _padc, 220))
                _chc = max(40, min(int(row_h) - 2 * _padc, 140))
                snap_a = os.path.join(tmpdir, "cover_ref.png")
                snap_b = os.path.join(tmpdir, "cover_ref2.png")
                for _try in range(3):
                    if not _capture_tile_screenshot(x0, y0, w, h, snap_a):
                        return False
                    if not self._mm_sleep(0.9):
                        return False
                    if not _capture_tile_screenshot(x0, y0, w, h, snap_b):
                        return False
                    if _grid_mean_abs_diff(snap_a, snap_b) <= 6.0:
                        break
                    if not self._mm_sleep(1.0):
                        return False
                else:
                    self._mm_log(
                        "[MemoryMatch] Board never settled for the cover reference - "
                        "keeping the pre-Start baseline (verdicts may be unreliable).")
                    return False
                from PIL import Image
                grid_img = Image.open(snap_a)
                filled = 0
                for _cx, _cy, _cc, _cr in cells:
                    _bx = int(_cx) - _cwc // 2 - x0
                    _by = int(_cy) - _chc // 2 - y0
                    _crop = grid_img.crop((_bx, _by, _bx + _cwc, _by + _chc))
                    _ic = _tile_icon_descriptor(_crop)
                    if _ic is not None:
                        # v44.1: REVEALED tile in the post-Start snapshot —
                        # the board was not fully covered (a pair was already
                        # solved before this session). Never use a revealed
                        # tile as its own covered reference: the cell would
                        # read "covered" forever and be re-clicked endlessly.
                        covered_icons[(_cc, _cr)] = None
                        covered_centers[(_cc, _cr)] = None
                        filled += 1
                        continue
                    _cs = _center_signature(_crop)
                    if _cs is not None:
                        covered_icons[(_cc, _cr)] = None
                        covered_centers[(_cc, _cr)] = _cs
                        covered_crops[(_cc, _cr)] = _crop
                        filled += 1
                return filled >= len(cells) - 4
            except Exception:
                return False

        # Debug snapshots for post-run analysis (user request 2026-09-28:
        # nothing in the macro root - everything in the local appdata dir).
        def _mm_debug_snapshot(tag: str):
            try:
                dbg = os.path.join(tmpdir, "debug")
                os.makedirs(dbg, exist_ok=True)
                stamp = datetime.now().strftime("%H%M%S")
                _capture_tile_screenshot(x0, y0, w, h, os.path.join(dbg, f"{stamp}_{tag}_grid.png"))
                for _cx, _cy, _cc, _cr in cells:
                    _src = os.path.join(tmpdir, f"cell_{_cc}_{_cr}.png")
                    if os.path.exists(_src):
                        try:
                            shutil.copyfile(_src, os.path.join(dbg, f"{stamp}_{tag}_cell{_cc}{_cr}.png"))
                        except Exception:
                            pass
                _files = sorted(os.listdir(dbg))
                for _old in _files[:-120]:
                    try:
                        os.remove(os.path.join(dbg, _old))
                    except Exception:
                        pass
            except Exception:
                pass

        # ---- session state ----
        tile_state: dict[tuple[int, int], dict] = {}
        # Identity groups: cells whose (item art, quantity) compare as the
        # same tile. The game allows 1 or 2 pairs of one item type, so a
        # group may hold 2 or 4 cells - any two of them form a valid pair.
        groups: list[dict] = []
        matched: set[tuple[int, int]] = set()
        # Pairs that were flipped together and did NOT stay open. Never
        # auto-retried: re-testing a known-false pair wastes a whole attempt.
        failed_pairs: dict[frozenset, int] = {}
        # Pairs whose verdict stayed UNKNOWN (neither green nor covered).
        # A false "failed" poisons the memory, so an unknown pair is retried
        # once before it is given up on.
        unknown_pairs: dict[frozenset, int] = {}
        # Consecutive reveals that never produced a readable tile (missed
        # clicks, wrong calibration, board never opened). Above the limit the
        # session aborts instead of burning every remaining attempt on the
        # same two cells.
        unreadable_streak = 0
        unreadable_limit = max(2, int(_cfg_float("memory_match_unreadable_limit", 4)))

        def _click_cell(c, r):
            target = next((t for t in cells if t[2] == c and t[3] == r), None)
            if not target:
                return
            try:
                autoit.mouse_click("left", int(target[0]), int(target[1]), 1, speed=3)
            except Exception:
                pass

        def _park_mouse():
            try:
                autoit.mouse_move(int(park_x), int(park_y), 3)
            except Exception:
                pass

        def _capture_cell(c, r, retries: int = 3, retry_delay: float = 0.45, samples: int = 1) -> dict:
            """Screenshot a tile and read it (images only, no OCR, silent).

            Up to `retries` snapshots (~retry_delay apart) until the icon is
            recognized - a mid-flip frame spoils the first frame. With
            samples=2 a second snapshot is taken ~0.4s later and stored as
            the ALT identity sample (see _identity_distance). Returns a
            state dict; "readable" is False for covered or unreadable cells."""
            target = next((t for t in cells if t[2] == c and t[3] == r), None)
            path = os.path.join(tmpdir, f"cell_{c}_{r}.png")
            state = {"icon": None, "center": None, "qty_sig": None, "sig": None,
                     "alt_icon": None, "alt_center": None, "alt_qty_sig": None, "alt_sig": None,
                     "green": 0.0, "path": path, "readable": False, "covered": False,
                     "pos": (c, r)}
            if not target:
                return state
            cx, cy = int(target[0]), int(target[1])
            cw = max(50, min(int(col_w) - 2 * int(self._mm_get("memory_match_cell_padding", 4)), 220))
            ch = max(40, min(int(row_h) - 2 * int(self._mm_get("memory_match_cell_padding", 4)), 140))

            def _read_once(suffix: str) -> dict:
                read = {"icon": None, "center": None, "qty_sig": None, "sig": None,
                        "green": 0.0, "covered": False}
                img_path = path if not suffix else path.replace(".png", f"{suffix}.png")
                if not _capture_tile_screenshot(cx - cw // 2, cy - ch // 2, cw, ch, img_path):
                    return read
                try:
                    from PIL import Image
                    tile_img = Image.open(img_path)
                    read["sig"] = _tile_signature(tile_img)
                    read["center"] = _center_signature(tile_img)
                    # Primary identity signal: background-invariant icon
                    # descriptor (the panel background changes constantly,
                    # so raw pixel signatures never match between cells).
                    read["icon"] = _tile_icon_descriptor(tile_img)
                    # Quantity as an image: the bottom-strip mask is part
                    # of the tile identity (same art + same qty = pair).
                    read["qty_sig"] = _tile_qty_descriptor(tile_img)
                    arr = np.asarray(tile_img.convert("RGB")).astype(float)
                    _r, _g, _b = arr[:, :, 0], arr[:, :, 1], arr[:, :, 2]
                    read["green"] = float(((_g > 140) & (_g - _r > 60) & (_g - _b > 60)).sum() / arr.shape[0] / arr.shape[1])
                except Exception:
                    read = {"icon": None, "center": None, "qty_sig": None, "sig": None,
                            "green": 0.0, "covered": False}
                ref_crop = covered_crops.get((c, r))
                if ref_crop is not None:
                    # v45.1: the covered card is pixel-stable while the
                    # camera is fixed, so the strip diff against the cell's
                    # OWN covered reference decides "covered" — a revealed
                    # dim item measures 19-31, a covered card 0.0-0.2
                    # (real-board calibration). This also protects the
                    # dim-art path: a covered card whose bleed produces
                    # "art" pixels still matches its reference.
                    cov = _strip_mean_diff(tile_img, ref_crop) <= cover_diff_tol
                else:
                    # No reference for this cell (it was already revealed at
                    # session start): fall back to the v41 art-gate logic.
                    base_icon = covered_icons.get((c, r))
                    if read["icon"] is None:
                        cov = True
                    else:
                        cov = (base_icon is not None
                               and _icon_distance(read["icon"], base_icon) <= icon_tol)
                read["covered"] = cov
                return read

            for attempt_no in range(1, retries + 1):
                read = _read_once("")
                for k in ("icon", "center", "qty_sig", "sig", "green", "covered"):
                    state[k] = read[k]
                state["readable"] = state["icon"] is not None and not state["covered"]
                if state["readable"] or attempt_no == retries:
                    break
                if not self._mm_sleep(retry_delay):
                    break
            if samples >= 2 and state["readable"]:
                # Stability loop: a mid-reveal (flip/zoom animation) frame
                # yields a garbage identity. Two samples ~0.45 s apart that
                # AGREE mean the tile has settled; while they disagree, the
                # newer frame replaces the main one and sampling continues
                # (max 2 extra samples). A tile that flips back during the
                # loop ends up covered -> not readable -> never remembered.
                for _extra in range(2):
                    if not self._mm_sleep(0.45):
                        break
                    alt = _read_once("_alt")
                    for k in ("icon", "center", "qty_sig", "sig", "green", "covered"):
                        state["alt_" + k] = alt[k]
                    unstable = not (alt["icon"] is not None and state["icon"] is not None
                                    and _icon_distance(state["icon"], alt["icon"]) <= icon_tol)
                    if not unstable:
                        break
                    for k in ("icon", "center", "qty_sig", "sig", "green", "covered"):
                        state[k] = alt[k]
                    state["readable"] = state["icon"] is not None and not state["covered"]
                    if not state["readable"]:
                        break
            return state

        def _reveal_cell(c, r, second: bool = False) -> dict | None:
            """Click a tile, move the mouse away SMOOTHLY, wait out the
            reveal load (the capture happens 0.8-1s after the click with the
            cursor parked outside the grid), then read it.

            The FIRST tile of an attempt stays open until the second flip,
            so it is read after the full reveal delay and captured TWICE
            (two samples give the identity comparison a noise margin), with
            one re-click when it still reads covered.

            The SECOND tile is different: the game checks the pair right
            after it opens and flips a mismatched pair back, so it is
            captured quickly (MM_SECOND_REVEAL_DELAY) and never re-clicked.
            Returns None when the macro was stopped."""
            delay = second_reveal_delay if second else reveal_delay
            _click_cell(c, r)
            _park_mouse()
            if not self._mm_sleep(delay):
                return None
            # BOTH tiles are captured twice (main + alt ~0.4s later): a
            # mid-flip frame yields a garbage identity that never matches
            # anything and silently kills the whole memory (real-board log
            # 2026-09-28: every turn explored, memory never paired). The
            # min-distance over the two samples absorbs one bad frame.
            state = _capture_cell(c, r, samples=2)
            state["pos"] = (c, r)
            if not second and not state["readable"] and state.get("covered"):
                _click_cell(c, r)
                _park_mouse()
                if not self._mm_sleep(delay):
                    return None
                state = _capture_cell(c, r, samples=2)
                state["pos"] = (c, r)
            return state

        def _identity_distance(a, b):
            """Primary identity distance: the background-invariant icon
            descriptor when available on BOTH tiles, else the legacy center
            signature. Each tile may carry TWO samples (main + alt); the
            BEST (minimum) pairwise distance wins, so one noisy frame (a
            mid-flip artifact) no longer breaks a real match.
            Returns (distance, tolerance_used) or (None, None)."""
            best = None
            for ka in ("icon", "alt_icon"):
                for kb in ("icon", "alt_icon"):
                    va, vb = a.get(ka), b.get(kb)
                    if va is not None and vb is not None:
                        d = _icon_distance(va, vb)
                        if best is None or d < best:
                            best = d
            if best is not None:
                return best, icon_tol
            for ka in ("center", "alt_center"):
                for kb in ("center", "alt_center"):
                    va, vb = a.get(ka), b.get(kb)
                    if va is not None and vb is not None:
                        d = _center_distance(va, vb)
                        if best is None or d < best:
                            best = d
            if best is not None:
                return best, center_tol
            return None, None

        def _tiles_same(a, b) -> bool:
            """Same tile = same item art AND same quantity, decided from
            IMAGES only (the panel background changes constantly, so raw
            pixels are never compared). When the quantity mask is missing on
            every sample combination the case is UNKNOWN - the pair is
            attempted and the game's own verdict (green vs flip-back)
            decides."""
            if not a or not b:
                return False
            d, tol_now = _identity_distance(a, b)
            if d is None or d > tol_now:
                return False
            best_q = None
            for ka in ("qty_sig", "alt_qty_sig"):
                for kb in ("qty_sig", "alt_qty_sig"):
                    va, vb = a.get(ka), b.get(kb)
                    if va is not None and vb is not None:
                        qd = _qty_mask_distance(va, vb)
                        if best_q is None or qd < best_q:
                            best_q = qd
            if best_q is not None and best_q > qty_tol:
                return False  # same art, different quantity rendering
            return True

        def _remember(pos, state):
            """Store a revealed tile in memory and in its identity group."""
            if not state or not state.get("readable"):
                return
            if pos in tile_state:
                _forget(pos)  # never let one cell live in two groups
            tile_state[pos] = state
            for g in groups:
                if _tiles_same(g["rep"], state):
                    if pos not in g["cells"]:
                        g["cells"].append(pos)
                    return
            groups.append({"rep": state, "cells": [pos]})

        def _forget(pos):
            tile_state.pop(pos, None)
            for g in groups:
                if pos in g["cells"]:
                    g["cells"].remove(pos)
                    break

        def _partner_from_memory(state, exclude=()) -> tuple | None:
            """Best remembered cell matching `state` (any cell of a matching
            identity group; failed pairs are never suggested)."""
            if not state or not state.get("readable"):
                return None
            best_pos = None
            best_dist = 1e9
            for pos, st in tile_state.items():
                if pos in matched or pos in exclude or pos == state.get("pos"):
                    continue
                if frozenset((pos, state.get("pos"))) in failed_pairs:
                    continue
                d, _tol = _identity_distance(state, st)
                if d is None:
                    continue
                if _tiles_same(state, st) and d < best_dist:
                    best_pos = pos
                    best_dist = d
            return best_pos

        def _pair_from_memory():
            """Two remembered, unmatched cells of the same identity group."""
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

        def _await_pair_verdict(pos_a, pos_b, turn: int = 0) -> str:
            """Poll the board until the GAME resolves the pair.

            The old fixed-delay verdict mis-read the board: a non-matching
            pair is still OPEN a couple of seconds after the second flip, so
            "both tiles readable" was mistaken for a scored pair and the
            memory got poisoned (real capture, 2026-09-27: every pair
            "SCORED" while the game matched none). The board is now POLLED:
            a scored pair turns GREEN (highlight), a missed pair flips back
            COVERED - anything else keeps polling.

            Real-board recovery (2026-09-28 log: every pair "did not resolve
            in time"): the game flips a pair back SIMULTANEOUSLY, so during
            the poll "A open + B covered" can only mean B's flip never
            registered (the click was swallowed). B is re-clicked (max
            twice) and the pair resolves for real instead of timing out.
            If BOTH tiles are still open after the full window, a mismatched
            pair would have flipped back long ago - that is a scored pair
            whose green highlight was missed.

            Returns "scored", "failed" or "timeout"."""
            b_reclicks = 0
            a_open_b_cov_streak = 0

            def _open(st) -> bool:
                return ((st.get("icon") is not None or st.get("center") is not None)
                        and not st.get("covered"))

            def _poll_phase(deadline: float) -> str:
                nonlocal b_reclicks, a_open_b_cov_streak
                while time.time() < deadline:
                    if not getattr(self, "detection_running", False):
                        return "failed"
                    st_a = _capture_cell(*pos_a, retries=1)
                    st_b = _capture_cell(*pos_b, retries=1)
                    # v41: bank the identities while the tiles are OPEN. The
                    # reveal-time capture of the SECOND tile can lose the
                    # race against the game's flip-back (real log 2026-09-29:
                    # the cell silently dropped out of the memory and had to
                    # be re-explored, burning a whole attempt), but the poll
                    # starts while the pair is still open. The sat gate makes
                    # a mid-flip frame unreadable, so only clean reads are
                    # remembered here.
                    if st_a.get("readable"):
                        _remember(pos_a, st_a)
                    if st_b.get("readable"):
                        _remember(pos_b, st_b)
                    if (st_a.get("green", 0.0) >= green_threshold
                            or st_b.get("green", 0.0) >= green_threshold):
                        return "scored"
                    if st_a.get("covered") and st_b.get("covered"):
                        return "failed"
                    if _open(st_a) and st_b.get("covered"):
                        # A is still open while B reads as the covered tile.
                        # A real swallowed click persists, a mid-flip-back
                        # animation frame does not - require it twice in a
                        # row before re-clicking.
                        a_open_b_cov_streak += 1
                        if a_open_b_cov_streak >= 2 and b_reclicks < 2:
                            b_reclicks += 1
                            a_open_b_cov_streak = 0
                            self._mm_log(
                                f"[MemoryMatch] Turn {turn}: second tile {pos_b} "
                                "did not open - re-clicking.")
                            st_fix = _reveal_cell(*pos_b, second=True)
                            if st_fix is None:
                                return "failed"
                            if st_fix.get("readable"):
                                _remember(pos_b, st_fix)
                    else:
                        a_open_b_cov_streak = 0
                    if not self._mm_sleep(MM_RESOLVE_POLL_INTERVAL):
                        return "failed"
                return "pending"

            verdict = _poll_phase(time.time() + MM_RESOLVE_TIMEOUT)
            if verdict == "pending":
                # Still open after the poll window: the game closes a missed
                # pair late, or only on the next flip. Wait for the board to
                # settle so the next attempt never clicks while old tiles are
                # still open.
                verdict = _poll_phase(time.time() + MM_SETTLE_TIMEOUT)
            if verdict == "pending":
                st_a = _capture_cell(*pos_a, retries=2, retry_delay=0.5)
                st_b = _capture_cell(*pos_b, retries=2, retry_delay=0.5)
                if _open(st_a) and _open(st_b):
                    # Insurance against a lingering pair: a mismatched pair
                    # flips back within seconds, so wait a little more and
                    # re-check before declaring a scored pair.
                    if self._mm_sleep(3.0):
                        st_a = _capture_cell(*pos_a, retries=2, retry_delay=0.5)
                        st_b = _capture_cell(*pos_b, retries=2, retry_delay=0.5)
                    if _open(st_a) and _open(st_b):
                        # v41 guard: a mismatched pair can stay open until the
                        # NEXT attempt (the game flips it back late), and
                        # "both still open" was counted as a scored pair —
                        # the 2026-09-29 archive shows two DIFFERENT items
                        # (ring + crystal) banked as a match this way, which
                        # welded wrong tiles into one identity group. The
                        # green-highlight path above is the game's own
                        # verdict and stays trusted; this fallback now also
                        # requires the two captures to read as the same item.
                        if (st_a.get("icon") is not None and st_b.get("icon") is not None
                                and not _tiles_same(st_a, st_b)):
                            verdict = "timeout"
                            self._mm_log(
                                f"[MemoryMatch] Turn {turn}: {pos_a}+{pos_b} both open but "
                                "the tiles read as DIFFERENT items - not counted as matched.")
                        else:
                            verdict = "scored"
                            self._mm_log(
                                f"[MemoryMatch] Turn {turn}: {pos_a}+{pos_b} still open - "
                                "counted as matched (green highlight was not detected).")
                    elif st_a.get("covered") and st_b.get("covered"):
                        verdict = "failed"
                    else:
                        verdict = "timeout"
                else:
                    verdict = ("failed" if (st_a.get("covered") and st_b.get("covered"))
                               else "timeout")
            return verdict

        def _resolve_attempt(pos_a, pos_b, label: str, turn: int = 0,
                             st_a=None, st_b=None) -> None:
            """Let the game deliver the verdict (polled): a scored pair
            stays revealed with the green highlight, a missed pair flips
            back covered. The reveal states are used to bank the verdict
            knowledge into the identity groups."""
            verdict = _await_pair_verdict(pos_a, pos_b, turn)
            try:
                _mm_debug_snapshot(f"turn{turn}_{verdict}")
            except Exception:
                pass
            if verdict == "scored":
                # Bank the identity knowledge: the game just proved the two
                # tiles are identical. Keep the group rep alive for 4-tile
                # item types (remember both, then forget the positions), and
                # force-merge the groups when the descriptors disagreed (one
                # capture was mid-flip garbage).
                if st_a is not None and st_b is not None and \
                        st_a.get("readable") and st_b.get("readable"):
                    _remember(pos_a, st_a)
                    _remember(pos_b, st_b)
                    ga = next((g for g in groups if pos_a in g["cells"]), None)
                    gb = next((g for g in groups if pos_b in g["cells"]), None)
                    if ga is not None and gb is not None and ga is not gb:
                        ga["cells"].extend(gb["cells"])
                        groups.remove(gb)
                matched.add(pos_a)
                matched.add(pos_b)
                _forget(pos_a)
                _forget(pos_b)
                out["matches"] += 1
                self._mm_log(
                    f"[MemoryMatch] Turn {turn}: {pos_a}+{pos_b} matched — "
                    f"pair scored ({out['matches']} total).")
                return
            pair_key = frozenset((pos_a, pos_b))
            if verdict == "timeout":
                # UNKNOWN outcome - the tiles were neither clearly green nor
                # clearly covered. Marking it "failed" could poison the
                # memory (a false failed pair is never retried), so an
                # unknown pair is retried once before it is given up on.
                unknown_pairs[pair_key] = unknown_pairs.get(pair_key, 0) + 1
                if unknown_pairs[pair_key] >= 2:
                    failed_pairs[pair_key] = failed_pairs.get(pair_key, 0) + 1
                self._mm_log(
                    f"[MemoryMatch] Turn {turn}: {pos_a}+{pos_b} state unknown — "
                    "the pair will be re-checked later.")
                return
            failed_pairs[pair_key] = failed_pairs.get(pair_key, 0) + 1
            # The tiles flip back covered - the ORIGINAL memory entries stay
            # (re-captures here show the cover, not the item). If the
            # descriptors had grouped the two tiles together, the game just
            # proved that grouping WRONG: split them so a bad capture does
            # not weld two different items into one identity.
            st_b_mem = tile_state.get(pos_b)
            ga = next((g for g in groups if pos_a in g["cells"]), None)
            gb = next((g for g in groups if pos_b in g["cells"]), None)
            if ga is not None and gb is not None and ga is gb and st_b_mem is not None:
                ga["cells"].remove(pos_b)
                groups.append({"rep": st_b_mem, "cells": [pos_b]})
            self._mm_log(
                f"[MemoryMatch] Turn {turn}: {pos_a}+{pos_b} flipped back — tiles kept in memory.")

        def _recovery_pair() -> tuple | None:
            """Last resort when every tile is known but no pair passed the
            strict check (small signature noise): the closest candidate by
            the icon identity distance, quantity must agree, and a pair that
            already failed once is NEVER retried - re-testing a known-false
            pair wastes a whole attempt."""
            best = None
            best_d = 1e9
            entries = [(pos, st) for pos, st in tile_state.items() if pos not in matched]
            for i in range(len(entries)):
                pos_a, st_a = entries[i]
                for j in range(i + 1, len(entries)):
                    pos_b, st_b = entries[j]
                    if frozenset((pos_a, pos_b)) in failed_pairs:
                        continue
                    d, d_tol = _identity_distance(st_a, st_b)
                    if d is None:
                        continue
                    qsa, qsb = st_a.get("qty_sig"), st_b.get("qty_sig")
                    if qsa is not None and qsb is not None and _qty_mask_distance(qsa, qsb) > qty_tol:
                        continue
                    if d <= d_tol and d < best_d:
                        best_d = d
                        best = (pos_a, pos_b)
            return best

        def _unknown_cells():
            unknowns = [t for t in cells if (t[2], t[3]) not in tile_state and (t[2], t[3]) not in matched]
            unknowns.sort(key=lambda t: (t[3], t[2]))  # top-to-bottom, left-to-right
            return unknowns

        # The board is fully covered right now - build the REAL per-cell
        # covered references from the post-Start board (stability-verified).
        # This is the ground truth for every "covered" verdict in this
        # session; the pre-Start baseline stays only as a fallback.
        if not _capture_cover_refs():
            self._mm_log(
                "[MemoryMatch] Post-Start cover reference failed - relying on the "
                "pre-Start baseline (verdicts may be unreliable).")

        # ---- the 10 attempts ----
        attempt = 0
        while attempt < 10:
            if not getattr(self, "detection_running", False):
                break
            pair = _pair_from_memory()
            if pair is not None:
                # 1) Collect a remembered pair - no exploration needed.
                pos_a, pos_b = pair
                st_a = _reveal_cell(*pos_a)
                if st_a is None:
                    break
                if not st_a["readable"]:
                    # The click did not open the tile (missed / already gone):
                    # no attempt is spent, the memory entry cannot be trusted.
                    self._mm_log(f"[MemoryMatch] Tile {pos_a} did not open - memory entry dropped.")
                    _forget(pos_a)
                    unreadable_streak += 1
                    if unreadable_streak >= unreadable_limit:
                        self._mm_log(
                            f"[MemoryMatch] {unreadable_streak} reveals in a row never opened - "
                            "aborting (check the grid calibration / board state).")
                        break
                    if not self._mm_sleep(attempt_gap):
                        break
                    continue
                if float(st_a.get("green") or 0.0) >= green_threshold:
                    # v44.1: a remembered tile turns out to be ALREADY SOLVED
                    # (green) — possible when the session started on a board
                    # that was not fresh. Drop it from memory, mark matched.
                    matched.add(pos_a)
                    _forget(pos_a)
                    self._mm_log(
                        f"[MemoryMatch] Tile {pos_a} is already solved (green) - skipped.")
                    continue
                unreadable_streak = 0
                d_fresh, tol_fresh = _identity_distance(st_a, tile_state.get(pos_a) or {})
                if d_fresh is not None and d_fresh > tol_fresh * 1.6:
                    # The tile shows something else than remembered - refresh
                    # the memory and salvage this attempt with the fresh read.
                    self._mm_log(
                        f"[MemoryMatch] Tile {pos_a} differs from memory (dist {d_fresh:.2f}) - memory updated.")
                    _forget(pos_a)
                    _remember(pos_a, st_a)
                    partner = _partner_from_memory(st_a, exclude=(pos_a,))
                    if partner is not None:
                        st_p = _reveal_cell(*partner, second=True)
                        if st_p is None:
                            break
                        _remember(partner, st_p)
                        _resolve_attempt(pos_a, partner, "re-paired", turn=attempt + 1, st_a=st_a, st_b=st_p)
                    else:
                        unknowns = [t for t in _unknown_cells() if (t[2], t[3]) != pos_a]
                        if unknowns:
                            _, _, c2, r2 = unknowns[0]
                            st2 = _reveal_cell(c2, r2, second=True)
                            if st2 is None:
                                break
                            _remember((c2, r2), st2)
                            _resolve_attempt(pos_a, (c2, r2), "explore", turn=attempt + 1, st_a=st_a, st_b=st2)
                        else:
                            break  # nothing left to pair with - stop cleanly
                    attempt += 1
                else:
                    st_b = _reveal_cell(*pos_b, second=True)
                    if st_b is None:
                        break
                    _remember(pos_b, st_b)
                    _resolve_attempt(pos_a, pos_b, "memory", turn=attempt + 1, st_a=st_a, st_b=st_b)
                    attempt += 1
            else:
                unknowns = _unknown_cells()
                if unknowns:
                    # 2) Reveal ONE unknown tile; a remembered partner is
                    #    flipped second so the pair is banked this attempt.
                    _, _, c1, r1 = unknowns[0]
                    s1 = _reveal_cell(c1, r1)
                    if s1 is None:
                        break
                    if s1["readable"] and float(s1.get("green") or 0.0) >= green_threshold:
                        # v44.1: the tile is ALREADY SOLVED (green highlight) —
                        # the session started on a board that was not fresh.
                        # Mark it matched and spend no attempt on it.
                        matched.add((c1, r1))
                        _forget((c1, r1))
                        self._mm_log(
                            f"[MemoryMatch] Cell ({c1},{r1}) is already solved "
                            "(green) - skipped.")
                        continue
                    _remember((c1, r1), s1)
                    if not s1["readable"]:
                        # The first flip never opened - do NOT spend the second
                        # flip of this attempt; retry other cells instead.
                        unreadable_streak += 1
                        self._mm_log(
                            f"[MemoryMatch] Cell ({c1},{r1}) unreadable "
                            f"(streak {unreadable_streak}/{unreadable_limit}).")
                        if unreadable_streak >= unreadable_limit:
                            self._mm_log(
                                "[MemoryMatch] Aborting: cells never open - "
                                "check the grid calibration / board state.")
                            break
                        if not self._mm_sleep(attempt_gap):
                            break
                        continue
                    unreadable_streak = 0
                    partner = _partner_from_memory(s1, exclude=((c1, r1),))
                    if partner is not None:
                        st_p = _reveal_cell(*partner, second=True)
                        if st_p is None:
                            break
                        _remember(partner, st_p)
                        _resolve_attempt((c1, r1), partner, "memory", turn=attempt + 1, st_a=s1, st_b=st_p)
                        attempt += 1
                    elif len(unknowns) >= 2:
                        # 3) No partner in memory - spend the second flip on
                        #    new information. If it matches the first tile the
                        #    pair scores; if it matches an OLDER tile the
                        #    group logic collects that pair next attempt.
                        #    v44.1: an ALREADY-SOLVED (green) cell must be
                        #    skipped — flipping it is a no-op and the game
                        #    keeps waiting for the REAL second flip, so the
                        #    green cell would be (falsely) resolved as a
                        #    scored pair with the still-open first tile.
                        candidates = list(unknowns[1:])
                        s2 = None
                        pos_b = None
                        while candidates:
                            _, _, c2, r2 = candidates.pop(0)
                            s2 = _reveal_cell(c2, r2, second=True)
                            if s2 is None:
                                break
                            if s2["readable"] and float(s2.get("green") or 0.0) >= green_threshold:
                                matched.add((c2, r2))
                                _forget((c2, r2))
                                self._mm_log(
                                    f"[MemoryMatch] Cell ({c2},{r2}) is already "
                                    "solved (green) - skipped.")
                                s2 = None
                                continue
                            pos_b = (c2, r2)
                            break
                        if s2 is None:
                            if not getattr(self, "detection_running", False):
                                break
                            continue
                        _remember(pos_b, s2)
                        _resolve_attempt((c1, r1), pos_b, "explore", turn=attempt + 1, st_a=s1, st_b=s2)
                        attempt += 1
                    else:
                        # Exactly one unknown left, no partner: the second
                        # flip is a guess - the memory cell closest to s1.
                        guess = None
                        best_d = 1e9
                        for pos, st in tile_state.items():
                            if pos in matched or pos == (c1, r1):
                                continue
                            if frozenset((pos, (c1, r1))) in failed_pairs:
                                continue
                            d, _tol = _identity_distance(s1, st)
                            if d is not None and d < best_d:
                                best_d = d
                                guess = pos
                        if guess is None:
                            break
                        st_g = _reveal_cell(*guess, second=True)
                        if st_g is None:
                            break
                        _remember(guess, st_g)
                        _resolve_attempt((c1, r1), guess, "guess", turn=attempt + 1, st_a=s1, st_b=st_g)
                        attempt += 1
                else:
                    # 4) All tiles known, no strict pair - noise recovery.
                    recovery = _recovery_pair()
                    if not recovery:
                        break
                    pos_a, pos_b = recovery
                    st_a = _reveal_cell(*pos_a)
                    if st_a is None:
                        break
                    st_b = _reveal_cell(*pos_b, second=True)
                    if st_b is None:
                        break
                    _remember(pos_b, st_b)
                    _resolve_attempt(pos_a, pos_b, "recovery", turn=attempt + 1, st_a=st_a, st_b=st_b)
                    attempt += 1
            if not self._mm_sleep(attempt_gap):
                break

        out["turns_used"] = attempt
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
                    if (getattr(self, "_eden_running", False) or
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
                err = str(res.get("error") or "")
                if "already running" in err:
                    # A second session was rejected by the session guard -
                    # logging its zeros would only duplicate the real result.
                    return
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
