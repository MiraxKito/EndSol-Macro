
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any
import os as _os
import tempfile as _tempfile
import threading as _threading

_config_lock = _threading.Lock()

def get_base_path() -> Path:
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent.parent

BASE_PATH = get_base_path()
EXE_CONFIG = BASE_PATH / "config.json"
DEV_CONFIG_DIR = BASE_PATH / "config_folder"
DEV_CONFIG = DEV_CONFIG_DIR / "config.json"

APPDATA_BASE = Path(_os.environ.get("LOCALAPPDATA", _os.path.expanduser("~"))) / "EndSolMacro"
APPDATA_CONFIG = APPDATA_BASE / "config.json"

# ── Project GitHub repo (single source of truth for all remote URLs) ─────
# Releases drive the in-app updater: tag = version ("v1.0.6" ...),
# release asset = EndSolMacro.exe. All gameplay data comes from the Sol's
# RNG Fandom wiki (plus the bundled offline snapshot) — nothing else is
# fetched. Optional files under assets/ in this repo:
#   - macro_calibs_preset.json  → community calibration presets shown in
#     the Calibration page ({"presets": [...]}; absent = built-ins only)
#   - noticetabcontents.txt / appreciation_list.txt → legacy UI notice tab
#     and the Donations page supporters list (both optional)
GITHUB_REPO = "MiraxKito/EndSol-Macro"
GITHUB_URL = f"https://github.com/{GITHUB_REPO}"
GITHUB_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main"
GITHUB_RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_PAGE = f"{GITHUB_URL}/releases/latest"

# These keys belonged exclusively to the removed multi-instance prototype.
# They are safe to remove; all other unknown keys are preserved deliberately.
RETIRED_CONFIG_KEYS = frozenset({
    "multi_instance_mode", "multi_instance_max",
    "multi_instance_auto_reconnect", "multi_accounts",
    "multi_managed_windows", "multi_instance_custom_paths",
})

def _remove_retired_config_keys(data: dict[str, Any]) -> bool:
    if not isinstance(data, dict):
        return False
    changed = False
    for key in RETIRED_CONFIG_KEYS:
        if key in data:
            del data[key]
            changed = True
    return changed

DEFAULT_AUTO_POP_BUFFS = [
    "Fortune Potion I",
    "Fortune Potion II",
    "Fortune Potion III",
    "Godlike Potion",
    "Haste Potion I",
    "Haste Potion II",
    "Haste Potion III",
    "Heavenly Potion",
    "Lucky Potion",
    "Oblivion Potion",
    "Potion of bound",
    "Rune of Everything",
    "Speed Potion",
    "Stella's Candle",
    "Strange Potion I",
    "Strange Potion II",
    "Transcendent Potion",
    "Warp Potion",
    "Xyz Potion",
]

DEFAULT_AUTO_POP_BIOMES = [
    "WINDY",
    "RAINY",
    "SNOWY",
    "SAND STORM",
    "HELL",
    "STARFALL",
    "CORRUPTION",
    "NULL",
    "GLITCHED",
    "DREAMSPACE",
    "CYBERSPACE",
    "AURORA",
    "HEAVEN",
    "EGGLAND",
    "SINGULARITY",
]

RARE_BIOMES = {"GLITCHED", "DREAMSPACE", "CYBERSPACE"}


def _coerce_auto_pop_amount(value: Any) -> int:
    try:
        return max(1, int(value))
    except Exception:
        return 1


def _normalize_auto_pop_buff_map(raw: Any) -> dict[str, list[Any]]:
    normalized: dict[str, list[Any]] = {
        buff_name: [False, 1] for buff_name in DEFAULT_AUTO_POP_BUFFS
    }
    if not isinstance(raw, dict):
        return normalized

    for buff_name, buff_value in raw.items():
        if not isinstance(buff_name, str) or not buff_name.strip():
            continue

        enabled = False
        amount = 1
        if isinstance(buff_value, (list, tuple)):
            if len(buff_value) >= 1:
                enabled = bool(buff_value[0])
            if len(buff_value) >= 2:
                amount = _coerce_auto_pop_amount(buff_value[1])
        elif isinstance(buff_value, dict):
            enabled = bool(buff_value.get("enabled", False))
            amount = _coerce_auto_pop_amount(buff_value.get("amount", 1))
        else:
            enabled = bool(buff_value)

        # Auto-register custom items not in DEFAULT_AUTO_POP_BUFFS
        if buff_name not in normalized:
            normalized[buff_name] = [False, 1]

        normalized[buff_name] = [enabled, amount]

    return normalized


def _normalize_auto_pop_order(raw_order: Any, buffs: dict[str, list[Any]]) -> list[str]:
    """Return a unique, complete item order while preserving manual choices."""
    order = []
    if isinstance(raw_order, list):
        for name in raw_order:
            if isinstance(name, str) and name in buffs and name not in order:
                order.append(name)
    for name in buffs:
        if isinstance(name, str) and name not in order:
            order.append(name)
    return order


def normalize_auto_pop_biomes(
    config_data: dict[str, Any],
    biome_names: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    names: list[str] = []
    seen: set[str] = set()

    if biome_names:
        for biome_name in biome_names:
            if isinstance(biome_name, str) and biome_name and biome_name != "NORMAL" and biome_name not in seen:
                seen.add(biome_name)
                names.append(biome_name)

    biome_counts = config_data.get("biome_counts", {})
    if isinstance(biome_counts, dict):
        for biome_name in biome_counts.keys():
            if isinstance(biome_name, str) and biome_name and biome_name != "NORMAL" and biome_name not in seen:
                seen.add(biome_name)
                names.append(biome_name)

    biome_notifier = config_data.get("biome_notifier", {})
    if isinstance(biome_notifier, dict):
        for biome_name in biome_notifier.keys():
            if isinstance(biome_name, str) and biome_name and biome_name != "NORMAL" and biome_name not in seen:
                seen.add(biome_name)
                names.append(biome_name)

    for biome_name in DEFAULT_AUTO_POP_BIOMES:
        if biome_name not in seen:
            seen.add(biome_name)
            names.append(biome_name)

    raw_auto_pop_biomes = config_data.get("auto_pop_biomes", {})
    if isinstance(raw_auto_pop_biomes, dict) and raw_auto_pop_biomes:
        normalized: dict[str, dict[str, Any]] = {}
        for biome_name in names:
            entry = raw_auto_pop_biomes.get(biome_name, {})
            if not isinstance(entry, dict):
                entry = {}
            buffs = _normalize_auto_pop_buff_map(entry.get("buffs", {}))
            normalized[biome_name] = {
                "enabled": bool(entry.get("enabled", False)),
                "buffs": buffs,
                "order": _normalize_auto_pop_order(entry.get("order"), buffs),
            }
        for biome_name, entry in raw_auto_pop_biomes.items():
            if (
                isinstance(biome_name, str)
                and biome_name
                and biome_name != "NORMAL"
                and biome_name not in normalized
            ):
                if not isinstance(entry, dict):
                    entry = {}
                buffs = _normalize_auto_pop_buff_map(entry.get("buffs", {}))
                normalized[biome_name] = {
                    "enabled": bool(entry.get("enabled", False)),
                    "buffs": buffs,
                    "order": _normalize_auto_pop_order(entry.get("order"), buffs),
                }
        return normalized

    rare_template = _normalize_auto_pop_buff_map(config_data.get("auto_buff_glitched", {}))
    non_rare_template = _normalize_auto_pop_buff_map(config_data.get("auto_buff_individual_biome", {}))
    non_rare_enabled = bool(config_data.get("auto_pop_individual_biomes", False))
    non_rare_list = config_data.get("individual_biome_pop_list", {})
    if not isinstance(non_rare_list, dict):
        non_rare_list = {}

    normalized: dict[str, dict[str, Any]] = {}
    for biome_name in names:
        if biome_name in RARE_BIOMES:
            enabled = bool(config_data.get(f"auto_pop_{biome_name.lower()}", False))
            buffs = copy.deepcopy(rare_template)
            if biome_name == "CYBERSPACE" and bool(config_data.get("cyberspace_only_warp", False)):
                for buff_name in list(buffs.keys()):
                    if buff_name not in {"Warp Potion", "Transcendent Potion"}:
                        buffs[buff_name][0] = False
        else:
            enabled = non_rare_enabled and bool(non_rare_list.get(biome_name, False))
            buffs = copy.deepcopy(non_rare_template)

        normalized[biome_name] = {
            "enabled": enabled,
            "buffs": buffs,
            "order": _normalize_auto_pop_order(None, buffs),
        }

    return normalized

def get_config_file() -> Path:
    return APPDATA_CONFIG


# Backup file priority order (first existing with content wins during recovery)
BACKUP_FILENAMES = (
    "config.json.bak2",
    "config.json.bak",
    "config.json.before_restore",
    "config.json.migration_backup",
)


def _try_read_json_lenient(path: Path) -> dict | None:
    """Read JSON file, deduplicating keys (last wins). Returns None on any error."""
    if not path or not path.exists():
        return None
    try:
        raw = path.read_text(encoding="utf-8-sig").strip()
        if not raw:
            return None
        decoder = json.JSONDecoder()
        obj, _ = decoder.raw_decode(raw)
        if isinstance(obj, dict):
            return obj
        return None
    except Exception:
        return None


def _looks_like_user_data(cfg: dict) -> bool:
    """Heuristic: does this config have any user-customized values worth preserving?"""
    if not isinstance(cfg, dict):
        return False
    # Personal data keys that strongly indicate "this is a real user config"
    for key in ("private_server_link", "webhook_urls", "roblox_username", "user_id"):
        v = cfg.get(key)
        if v and v != [] and v != "" and v != {}:
            return True
    return False


def _safe_backup(path: Path, suffix: str = ".preserve") -> None:
    """Move a file to a backup name without overwriting anything."""
    if not path or not path.exists():
        return
    target = path.with_name(path.name + suffix)
    if target.exists():
        # Don't overwrite an existing backup
        return
    try:
        path.rename(target)
    except Exception:
        try:
            import shutil
            shutil.copy2(path, target)
            path.unlink()
        except Exception:
            pass


def _merge_user_data_into_defaults(old_cfg: dict, new_cfg: dict, defaults: dict) -> dict:
    """
    Merge user data from old config into new config while preserving new structure.

    Rules:
      - personal data (webhook_urls, private_server_link, etc.): only restore if NEW is empty
      - booleans: only restore if user explicitly enabled
      - short lists (<= 20 items, e.g. calibration coords): restore if NEW is default/empty
      - biome_notifier: restore per-biome non-default notification modes
      - biome_pings: restore per-biome Discord pings
      - Stats / counters / timestamps: always restore from OLD (they are user data, never defaults)
    """
    personal_data_keys = (
        "webhook_urls", "private_server_link", "user_id", "roblox_username",
    )
    # Numeric/JSON stat keys that are runtime state, never defaults
    stat_keys = (
        "session_time", "session_window_start", "macro_last_start",
        "merchant_counts", "jester_exchange_count", "last_jester_exchange_time",
        "last_merchant_visit", "last_fishing_session_at", "last_eden_at",
        "total_fish_caught", "total_auras_detected", "total_biomes_found",
        "biome_counts", "aura_counts", "merchants_found",
        "last_anti_afk", "last_anti_afk_at", "last_disconnect_at",
        "last_aura_roll_time", "last_biome_change_time",
    )
    out = dict(new_cfg)
    for k, old_v in old_cfg.items():
        if k not in out:
            continue
        new_v = out.get(k)
        default_v = defaults.get(k)
        # Stats/runtime: always restore
        if k in stat_keys:
            if old_v and (not new_v or new_v == default_v or new_v == 0 or new_v == "" or new_v == {}):
                out[k] = old_v
            continue
        if k in personal_data_keys:
            if (not new_v or new_v == default_v) and old_v:
                out[k] = old_v
            continue
        # Strings: restore non-default non-empty values (force_ping_auras, selected_potion_file, etc.)
        if k in defaults and isinstance(default_v, str):
            if old_v and old_v != default_v and (not new_v or new_v == default_v):
                out[k] = old_v
            continue
        if k in defaults and isinstance(default_v, bool):
            if old_v is True and new_v is False:
                out[k] = old_v
            continue
        if k in defaults and isinstance(default_v, list):
            if (not new_v or new_v == default_v) and old_v and len(old_v) > 0:
                if len(old_v) <= 20:
                    out[k] = old_v
            continue
        if k in defaults and isinstance(default_v, (int, float)):
            # Numeric tuning: restore if OLD is meaningfully different from default
            try:
                if float(old_v) != float(default_v) and (float(new_v) == float(default_v) or not new_v):
                    out[k] = old_v
            except (TypeError, ValueError):
                pass
            continue
    # Special: biome_notifier per-biome modes
    old_bn = old_cfg.get("biome_notifier", {})
    new_bn = out.get("biome_notifier", {})
    default_bn = defaults.get("biome_notifier", {})
    if isinstance(old_bn, dict) and isinstance(new_bn, dict):
        for biome, mode in old_bn.items():
            if biome in new_bn and mode != "Message" and mode != default_bn.get(biome):
                new_bn[biome] = mode
    # Special: biome_pings
    old_pings = old_cfg.get("biome_pings", {})
    if isinstance(old_pings, dict):
        new_pings = out.get("biome_pings", {})
        if not isinstance(new_pings, dict):
            new_pings = {}
            out["biome_pings"] = new_pings
        for biome, ping_cfg in old_pings.items():
            if isinstance(ping_cfg, dict) and (biome not in new_pings or not new_pings[biome].get("id")):
                new_pings[biome] = ping_cfg
    return out


def _write_config(path: Path, cfg: dict) -> None:
    path.write_text(
        json.dumps(cfg, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def ensure_workspace_files() -> None:
    (APPDATA_BASE / "resources").mkdir(exist_ok=True)
    (APPDATA_BASE / "paths").mkdir(exist_ok=True)
    (APPDATA_BASE / "logs").mkdir(exist_ok=True)
    (APPDATA_BASE / "images").mkdir(exist_ok=True)

    if not getattr(sys, 'frozen', False):
        DEV_CONFIG_DIR.mkdir(exist_ok=True)

    APPDATA_BASE.mkdir(parents=True, exist_ok=True)
    config_file = get_config_file()

    # Step 1: Migrate local config to AppData (only if local has user data
    # and AppData has no config yet). This handles first-run on a new PC.
    if EXE_CONFIG.exists() and not config_file.exists():
        try:
            local_data = _try_read_json_lenient(EXE_CONFIG)
            # Only migrate if local has user data; otherwise it's a stale
            # default from an old build and we should start fresh.
            if local_data and _looks_like_user_data(local_data):
                import shutil
                shutil.copy2(EXE_CONFIG, config_file)
        except Exception as e:
            print(f"Failed to migrate config.json to AppData: {e}")

    # Step 2: First-time setup — write default config (no user data).
    if not config_file.exists():
        try:
            from .defaults import get_default_config
            default = get_default_config()
        except Exception:
            default = {}
        config_file.parent.mkdir(parents=True, exist_ok=True)
        _write_config(config_file, default)


def sync_config() -> dict[str, Any]:
    """Normalize and persist the current configuration instead of being a no-op."""
    data = load_config()
    if not isinstance(data, dict):
        data = {}
    save_config(data)
    return data


def load_config() -> dict[str, Any]:
    """
    Load config with multi-step recovery to protect against data loss.

    Order of operations:
      1. If AppData config exists and is valid, load it (then backfill defaults).
      2. If AppData config is missing/empty/broken, try backups in priority order.
      3. For each backup with user data, merge it with defaults and the
         current config (if any), then write back as primary config.
      4. Never silently overwrite an existing primary config with empty
         defaults — always preserve user data.
    """
    ensure_workspace_files()
    with _config_lock:
        config_file = get_config_file()

        # Try primary config first
        current = _try_read_json_lenient(config_file)

        # If primary is valid and has user data, use it (with backfill)
        if current and _looks_like_user_data(current):
            return _backfill_and_normalize(current)

        # If primary is missing/empty/invalid → try to recover from backups
        # BEFORE doing anything that might overwrite them.
        recovered = None
        for backup_name in BACKUP_FILENAMES:
            backup_path = APPDATA_BASE / backup_name
            bak_data = _try_read_json_lenient(backup_path)
            if bak_data and _looks_like_user_data(bak_data):
                recovered = bak_data
                break

        # Get defaults
        try:
            from .defaults import get_default_config
            defaults = get_default_config()
        except Exception:
            defaults = {}

        # Case A: no primary config, but found a backup with user data
        if current is None and recovered is not None:
            merged = _merge_user_data_into_defaults(recovered, defaults, defaults)
            # Preserve backup files; only write primary
            _safe_backup(config_file, ".recovered_from_backup")
            _write_config(config_file, merged)
            return _backfill_and_normalize(merged)

        # Case B: primary is empty/broken but exists, AND we have a backup
        if current is not None and recovered is not None:
            # Save the current (broken/empty) as a safety net
            _safe_backup(config_file, ".broken_preserved")
            merged = _merge_user_data_into_defaults(recovered, current, defaults)
            _write_config(config_file, merged)
            return _backfill_and_normalize(merged)

        # Case C: no primary, no backup with user data → use defaults
        if current is None and recovered is None:
            return defaults

        # Case D: primary exists but is empty (no user data), no backup
        # — this is a fresh install or after manual reset. Use defaults.
        if not _looks_like_user_data(current):
            return _backfill_and_normalize(defaults)

        # Fallback: should not reach here
        return _backfill_and_normalize(current if current else defaults)


def _backfill_and_normalize(data: dict) -> dict:
    """Add missing defaults while preserving legacy user settings."""
    if not isinstance(data, dict):
        return {}
    retired_removed = _remove_retired_config_keys(data)
    # A fresh/legacy config with zero coordinates is upgraded to the selected
    # built-in windowed template. Existing normalized calibrations are sacred.
    try:
        from .defaults import get_default_config
        safe_defaults = get_default_config()
        if not isinstance(data.get("_calibration_meta"), dict):
            for _key, _value in safe_defaults.items():
                if not (_key in data and isinstance(_value, list) and isinstance(data.get(_key), list)):
                    continue
                if len(_value) != len(data[_key]) or not all(float(x or 0) == 0 for x in data[_key]):
                    continue
                if any(float(x or 0) != 0 for x in _value):
                    data[_key] = copy.deepcopy(_value)
                    retired_removed = True
    except Exception:
        pass
    # Migrate the old singular webhook key in memory. The original file is
    # never deleted or rewritten solely because of this migration.
    if "webhook_urls" not in data and "webhook_url" in data:
        data["webhook_urls"] = data.get("webhook_url")
    if "webhook_url" not in data and "webhook_urls" in data:
        data["webhook_url"] = data.get("webhook_urls")
    try:
        from .defaults import get_default_config
        defaults = get_default_config()
        for k, v in defaults.items():
            if k not in data:
                data[k] = v
    except Exception:
        pass
    try:
        data["auto_pop_biomes"] = normalize_auto_pop_biomes(data)
    except Exception:
        pass
    try:
        _merge_new_biome_notifier_entries(data)
    except Exception:
        pass
    if retired_removed:
        try:
            _write_config(get_config_file(), data)
        except Exception:
            pass
    return data


# Default biome notifier entries — all biomes the macro knows about.
# New entries added here will be auto-merged into existing user configs.
_DEFAULT_BIOME_NOTIFIER_ENTRIES: dict[str, str] = {
    "CORRUPTION": "Message", "CYBERSPACE": "Message", "DREAMSPACE": "Message",
    "GLITCHED": "Message", "HELL": "Message", "NORMAL": "Message", "NULL": "Message",
    "RAINY": "Message", "SAND STORM": "Message", "SNOWY": "Message",
    "STARFALL": "Message", "WINDY": "Message", "HEAVEN": "Message",
    "AURORA": "Message", "EGGLAND": "Message", "BLAZING SUN": "Message",
    "PUMPKIN MOON": "Message", "GRAVEYARD": "Message", "BLOOD RAIN": "Message",
    "SINGULARITY": "Message",
    "THE HYPERSPACE REALM": "Message", "\u8d64\u3044\u6e80\u6708": "Message",
    "THE NULL'S EXISTENCE": "Message", "THE CITADEL OF ORDERS": "Message",
}


def _merge_new_biome_notifier_entries(data: dict) -> None:
    """Add any biomes from the default list that are missing in the user's biome_notifier."""
    biome_notifier = data.get("biome_notifier")
    if not isinstance(biome_notifier, dict):
        biome_notifier = {}
        data["biome_notifier"] = biome_notifier
    changed = False
    for biome_name, mode in _DEFAULT_BIOME_NOTIFIER_ENTRIES.items():
        if biome_name not in biome_notifier:
            biome_notifier[biome_name] = mode
            changed = True
    if changed:
        # Persist the updated config so the user sees the new biomes next time
        try:
            config_file = get_config_file()
            config_file.write_text(json.dumps(data, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")
        except Exception:
            pass

def save_config(config_data: dict[str, Any]) -> None:
    with _config_lock:
        try:
            config_file = get_config_file()
            current_config = {}
            if config_file.exists():
                try:
                    raw = config_file.read_text(encoding="utf-8").strip()
                    if raw:
                        parsed = json.loads(raw)
                        if isinstance(parsed, dict):
                            current_config = parsed
                except Exception:
                    pass

            current_config.update(config_data)
            _remove_retired_config_keys(current_config)
            current_config["auto_pop_biomes"] = normalize_auto_pop_biomes(current_config)
            tmp_fd, tmp_path = _tempfile.mkstemp(
                dir=str(config_file.parent), suffix=".tmp", prefix="config_"
            )
            try:
                with _os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                    json.dump(current_config, f, indent=4)
                    f.write("\n")
                    f.flush()
                    _os.fsync(f.fileno())
                _os.replace(tmp_path, str(config_file))
            except Exception:
                try:
                    _os.unlink(tmp_path)
                except Exception:
                    pass
                raise
        except Exception as e:
            print(f"Failed to save config: {e}")