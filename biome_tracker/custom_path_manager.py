"""
Custom path manager for EndSol Macro.

Allows users to record and save custom walk paths that override default paths
for specific features (Quest Board, Memory Match, Eden, Obby, etc.).

Custom paths are stored in custom_paths/ directory and take priority over
the default paths/ directory.
"""

import json
import os
import time
from pathlib import Path
from typing import Any

CUSTOM_PATHS_DIR = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "EndSolMacro" / "custom_paths"


def _default_paths_dir() -> Path:
    """
    Locate the bundled default paths/ directory.

    The exe/launcher chdirs into the app-data folder and copies the bundled
    default path files there at startup (see initialize_paths_and_files), so
    the runtime CWD/paths is checked first; the source tree (biome_tracker/../
    paths) is the fallback for development runs.
    """
    candidates = [
        Path(os.getcwd()) / "paths",
        Path(__file__).resolve().parent.parent / "paths",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


DEFAULT_PATHS_DIR = _default_paths_dir()

# Map of feature keys to their default path filenames
FEATURE_PATH_MAP = {
    "memory_match": "memory_match.json",
    "quest_board": "quest_board.json",
    "obby": "obby.json",
    "eden": "eden.json",
    "snowman": "snowman.json",
    "egg_route1": "egg_route1.json",
    "egg_route2": "egg_route2.json",
    "egg_route3": "egg_route3.json",
}

FEATURE_LABELS = {
    "memory_match": "Memory Match (VIP)",
    "memory_match_nonvip": "Memory Match (Non-VIP)",
    "quest_board": "Quest Board",
    "obby": "Obby",
    "eden": "Eden Path",
    "snowman": "Snowman",
    "egg_route1": "Egg Route 1",
    "egg_route2": "Egg Route 2",
    "egg_route3": "Egg Route 3",
    # No bundled default file: fishing.py falls back to its built-in walk when
    # no custom path is assigned. Recorded from the spawn point (right after
    # the respawn sequence) to the player's own fishing spot — the walk to the
    # fish seller stays built-in on purpose.
    "fishing": "Fishing Spot",
}


def _ensure_dirs():
    CUSTOM_PATHS_DIR.mkdir(parents=True, exist_ok=True)


def list_custom_paths() -> list[dict[str, Any]]:
    """List all custom paths with metadata."""
    _ensure_dirs()
    result = []
    for f in sorted(CUSTOM_PATHS_DIR.glob("*.json")):
        try:
            with open(f, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            meta = data.get("meta", {})
            result.append({
                "id": f.stem,
                "filename": f.name,
                "feature": meta.get("feature", ""),
                "label": meta.get("label", f.stem),
                "created": meta.get("created", ""),
                "event_count": len(data.get("events", [])),
                "speed_multiplier": meta.get("speed_multiplier", 1.0),
                # None = recorded before VIP/non-VIP stamping existed (legacy).
                "recorded_nonvip": meta.get("recorded_nonvip", None),
            })
        except Exception:
            continue
    return result


def get_custom_path(path_id: str) -> dict[str, Any] | None:
    """Load a specific custom path by its ID (stem)."""
    _ensure_dirs()
    filepath = CUSTOM_PATHS_DIR / f"{path_id}.json"
    if not filepath.exists():
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_custom_path(
    path_id: str,
    events: list[dict],
    feature: str = "",
    label: str = "",
    speed_multiplier: float = 1.0,
    recorded_nonvip: bool | None = None,
    created: str = "",
) -> bool:
    """Save a custom path with metadata.

    recorded_nonvip stamps which walk-speed mode (Movements ->
    "Non-VIP movement path") was active while the path was recorded, so
    playback can compensate when the mode differs. None keeps the value
    unset (legacy paths); `created` preserves the original timestamp when
    re-saving an existing path (e.g. on re-assignment).
    """
    _ensure_dirs()
    filepath = CUSTOM_PATHS_DIR / f"{path_id}.json"
    meta = {
        "feature": feature,
        "label": label or path_id,
        "created": created or datetime_now_iso(),
        "speed_multiplier": speed_multiplier,
    }
    if recorded_nonvip is not None:
        meta["recorded_nonvip"] = bool(recorded_nonvip)
    data = {
        "meta": meta,
        "events": events,
    }
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True
    except Exception:
        return False


def delete_custom_path(path_id: str) -> bool:
    """Delete a custom path file."""
    _ensure_dirs()
    filepath = CUSTOM_PATHS_DIR / f"{path_id}.json"
    if filepath.exists():
        try:
            filepath.unlink()
            return True
        except Exception:
            return False
    return False


def load_path_for_feature_meta(feature: str) -> tuple[list[dict], dict | None]:
    """
    Load the path events + meta for a feature, preferring custom paths over
    defaults.

    Priority:
      1. Custom path assigned to this feature (in custom_paths/)
      2. Default path (in paths/)

    For features with VIP variants (memory_match, egg routes), checks the
    tracker's config for non_vip_movement_path to select the right custom path.
    """
    # Determine VIP variant if applicable
    is_vip = True
    try:
        import sys
        # Walk up to find the tracker instance through the module hierarchy
        from . import core as _core
        for obj in vars(_core).values():
            if hasattr(obj, "config") and isinstance(obj.config, dict):
                if obj.config.get("non_vip_movement_path", False):
                    is_vip = False
                break
    except Exception:
        pass

    variant = "" if is_vip else "_nonvip"

    # 1. Check custom paths for one assigned to this feature. Prefer the
    # exact walk-speed variant (feature + "_nonvip") over the plain feature
    # so a VIP-recorded path is not picked while playing non-VIP.
    custom = list_custom_paths()
    for wanted in (f"{feature}{variant}", feature):
        for cp in custom:
            cp_feature = cp.get("feature", "")
            if cp_feature == wanted:
                data = get_custom_path(cp["id"])
                if data and isinstance(data.get("events"), list) and data["events"]:
                    return data["events"], data.get("meta") or {}

    # 2. Fall back to default path
    default_filename = FEATURE_PATH_MAP.get(feature)
    if not default_filename:
        return [], None

    default_file = DEFAULT_PATHS_DIR / default_filename
    if not default_file.exists():
        return [], None

    try:
        with open(default_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            events = data.get("events", []) if isinstance(data.get("events"), list) else []
        else:
            events = []
        return events, None
    except Exception:
        return [], None


def load_path_for_feature(feature: str) -> list[dict]:
    """Load just the path events for a feature (see load_path_for_feature_meta)."""
    events, _meta = load_path_for_feature_meta(feature)
    return events


# Empirical walk-speed ratio between non-VIP and VIP characters. Bundled
# default paths were recorded on a VIP account, so non-VIP playback
# stretches timing by this factor (see fishing.NON_VIP_WALK_SPEED_MULTIPLIER).
NONVIP_STRETCH = 1.22


def resolve_walk_multiplier(meta: dict | None, non_vip_now: bool) -> float | None:
    """
    Timing multiplier to apply to a custom path right now.

    - Path stamped recorded_nonvip == non_vip_now -> 1.0 (as recorded).
    - Recorded on VIP, playing non-VIP -> stretch (1.22).
    - Recorded on non-VIP, playing VIP -> compress (1/1.22).
    - None (legacy path without the stamp) -> callers fall back to the old
      behavior (stretch when non-VIP is on).
    """
    if not isinstance(meta, dict):
        return None
    rec = meta.get("recorded_nonvip", None)
    if rec is None:
        return None
    rec = bool(rec)
    if rec == bool(non_vip_now):
        return 1.0
    return NONVIP_STRETCH if non_vip_now else 1.0 / NONVIP_STRETCH


def current_non_vip_setting() -> bool:
    """Read non_vip_movement_path from the live tracker config, if available."""
    try:
        from . import core as _core
        for obj in vars(_core).values():
            if hasattr(obj, "config") and isinstance(obj.config, dict):
                return bool(obj.config.get("non_vip_movement_path", False))
    except Exception:
        pass
    return False


def load_path_for_feature_with_vip(feature: str, has_vip: bool = True) -> list[dict]:
    """
    Load path with VIP awareness. For features that have separate VIP/default
    paths, this handles the selection. Custom paths always take priority.
    """
    # Custom paths always win
    custom = list_custom_paths()
    for cp in custom:
        if cp.get("feature") == feature:
            data = get_custom_path(cp["id"])
            if data and isinstance(data.get("events"), list) and data["events"]:
                return data["events"]

    # Fall back to default
    default_filename = FEATURE_PATH_MAP.get(feature)
    if not default_filename:
        return []

    default_file = DEFAULT_PATHS_DIR / default_filename
    if not default_file.exists():
        return []

    try:
        with open(default_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data.get("events", []) if isinstance(data.get("events"), list) else []
        return []
    except Exception:
        return []


def save_recording_as_custom(
    events: list[dict],
    name: str,
    feature: str = "",
    speed_multiplier: float = 1.0,
    recorded_nonvip: bool | None = None,
) -> str:
    """
    Save a recording as a custom path. Returns the path_id.
    Used by the recorder to save directly to custom_paths/ instead of recorded_files/.
    recorded_nonvip stamps the walk-speed mode that was active while recording.
    """
    path_id = _sanitize_id(name)
    save_custom_path(
        path_id=path_id,
        events=events,
        feature=feature,
        label=name,
        speed_multiplier=speed_multiplier,
        recorded_nonvip=recorded_nonvip,
    )
    return path_id


def _sanitize_id(name: str) -> str:
    """Sanitize a name to be a safe filename."""
    import re
    s = re.sub(r"[^a-zA-Z0-9_\-]", "_", name.strip())
    s = re.sub(r"_+", "_", s).strip("_")
    return s.lower() or f"path_{int(time.time())}"


def datetime_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
