"""
Optional extras for EndSol Macro (v1.0.9).

All extra toggles default to OFF and live in the config:
  - dry_run                  -> log actions instead of performing them
  - daily_stats_webhook      -> one Discord summary per completed day
                                (00:00 UTC window), stored in a local JSON

Always-available (no config): feature schedule view, config profiles,
clear-logs. See main.py Api for the UI entry points.
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta, timezone

import requests

from .base_support import current_ver
from .config import APPDATA_BASE

_DAILY_KEYS = ("auras", "biomes", "mm_pairs", "fish")
_DAILY_KEEP_DAYS = 14  # prune old day buckets so the JSON store stays small
_RARE_AURA_THRESHOLD = 100_000  # Legendary and above


class ExtrasMixin:
    # ── persistent daily stats ──────────────────────────────────────────
    # Daily stats are stored OUTSIDE the config, in
    # %LOCALAPPDATA%/EndSolMacro/daily_stats.json, so the totals survive
    # restarts instead of describing only the current session. The stats
    # day follows the game's daily reset: 00:00 UTC → 00:00 UTC
    # (00:00:05 UTC is the first second that belongs to the new day).
    # User-facing timestamps are shown in the PC's local timezone.

    def _daily_stats_path(self):
        return APPDATA_BASE / "daily_stats.json"

    def _daily_day_key(self, dt=None):
        dt = dt or datetime.now(timezone.utc)
        return dt.strftime("%Y-%m-%d")

    def _daily_load(self):
        try:
            payload = json.loads(self._daily_stats_path().read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("days"), dict):
                return payload
        except Exception:
            pass
        return {"version": 1, "days": {}}

    def _daily_save(self, payload):
        try:
            path = self._daily_stats_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            payload["version"] = 1
            payload["updated_at"] = datetime.now(timezone.utc).isoformat()
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
            os.replace(str(tmp), str(path))
        except Exception:
            pass

    def _daily_entry(self, payload, day_key):
        days = payload.setdefault("days", {})
        entry = days.get(day_key)
        if not isinstance(entry, dict):
            entry = {}
            days[day_key] = entry
        for key in _DAILY_KEYS:
            if not isinstance(entry.get(key), (int, float)):
                entry[key] = 0
        if not isinstance(entry.get("playtime_seconds"), (int, float)):
            entry["playtime_seconds"] = 0
        return entry

    def _daily_prune(self, payload):
        days = payload.get("days")
        if isinstance(days, dict) and len(days) > _DAILY_KEEP_DAYS:
            for old in sorted(days)[: len(days) - _DAILY_KEEP_DAYS]:
                days.pop(old, None)

    def _daily_add(self, key, n=1):
        try:
            n = int(n)
            if key not in _DAILY_KEYS or n <= 0:
                return
            payload = self._daily_load()
            entry = self._daily_entry(payload, self._daily_day_key())
            entry[key] = int(entry.get(key, 0) or 0) + n
            self._daily_prune(payload)
            self._daily_save(payload)
        except Exception:
            pass

    def _daily_bump(self, key, n=1):
        """Record one event into the persistent daily stats store."""
        self._daily_add(key, n)

    def _flush_daily_fish(self):
        """Move the fishing session counter delta into the daily store."""
        try:
            state = getattr(self, "_fishing_runtime_state", None) or {}
            current_fish = int(state.get("fish_caught_count", 0) or 0)
            last_fish = int(getattr(self, "_daily_last_fish", 0) or 0)
            self._daily_last_fish = current_fish
            delta = current_fish - last_fish
            if delta > 0:
                self._daily_add("fish", delta)
        except Exception:
            pass

    def _flush_daily_playtime(self):
        """Accumulate real macro runtime into today's daily stats entry."""
        try:
            stamp = getattr(self, "_daily_play_stamp", None)
            now = time.time()
            self._daily_play_stamp = now
            if not stamp:
                return
            delta = int(now - stamp)
            if delta <= 0:
                return
            payload = self._daily_load()
            entry = self._daily_entry(payload, self._daily_day_key())
            entry["playtime_seconds"] = int(entry.get("playtime_seconds", 0) or 0) + delta
            self._daily_prune(payload)
            self._daily_save(payload)
        except Exception:
            pass

    # ── daily stats webhook ─────────────────────────────────────────────
    def start_daily_stats_loop(self):
        if getattr(self, "_daily_stats_thread", None) and self._daily_stats_thread.is_alive():
            return
        self._daily_play_stamp = time.time()
        self._daily_stats_thread = threading.Thread(
            target=self._daily_stats_loop, name="Daily Stats", daemon=True
        )
        self._daily_stats_thread.start()

    def _daily_stats_loop(self):
        while getattr(self, "detection_running", False):
            try:
                self._flush_daily_playtime()
                self._flush_daily_fish()
                if self.config.get("daily_stats_webhook", False):
                    now_utc = datetime.now(timezone.utc)
                    day_key = self._daily_day_key(now_utc)
                    # Send once inside the first hour after the 00:00 UTC
                    # reset (= 03:00 MSK). The summary always covers the
                    # day that just finished, not the running session.
                    if now_utc.hour == 0 and getattr(self, "_daily_stats_sent_day", None) != day_key:
                        self._daily_stats_sent_day = day_key
                        self.send_daily_stats_webhook()
            except Exception as e:
                self.error_logging(e, "daily stats loop")
            time.sleep(20)
        # Macro stopped — flush the remaining runtime and fish counters.
        try:
            self._flush_daily_playtime()
            self._flush_daily_fish()
        except Exception:
            pass

    def send_daily_stats_webhook(self):
        """Send the summary of the last completed stats day (00:00 UTC)."""
        try:
            self._flush_daily_playtime()
            self._flush_daily_fish()
        except Exception:
            pass
        day_key = self._daily_day_key(datetime.now(timezone.utc) - timedelta(days=1))
        entry = (self._daily_load().get("days") or {}).get(day_key)
        if not isinstance(entry, dict):
            self.append_log(f"[DailyStats] No data recorded for {day_key} - summary skipped.")
            return
        stats = {key: int(entry.get(key, 0) or 0) for key in _DAILY_KEYS}
        playtime = int(entry.get("playtime_seconds", 0) or 0)
        hours, minutes = divmod(playtime // 60, 60)
        try:
            local_tz = datetime.now().astimezone().tzname() or "local"
        except Exception:
            local_tz = "local"
        lines = [
            f"**Stats day:** {day_key} (00:00-00:00 UTC / {local_tz} local time)",
            f"**Auras found:** {stats.get('auras', 0)}",
            f"**Biomes detected:** {stats.get('biomes', 0)}",
            f"**Memory Match pairs:** {stats.get('mm_pairs', 0)}",
            f"**Fish caught:** {stats.get('fish', 0)}",
            f"**Macro runtime:** {hours}h {minutes}m",
        ]
        # Attribute the summary to the configured player (stats are collected
        # from the MAIN window's detector only — secondary windows never add
        # to them).
        uname = str((getattr(self, "config", {}) or {}).get("roblox_username", "") or "").strip()
        if uname:
            lines.insert(1, f"**Player:** {uname} (main window)")
        embed = {
            "title": "EndSol Macro — daily summary",
            "description": "\n".join(lines),
            "color": 0x7C5BF5,
            "footer": {"text": f"EndSol Macro {current_ver} · main window only · day resets at 00:00 UTC"},
        }
        urls = [u for u in (getattr(self, "webhook_urls", []) or []) if isinstance(u, str) and u.strip()]
        if not urls:
            self.append_log("[DailyStats] No webhook configured - summary skipped.")
            return
        sent = 0
        for url in urls:
            try:
                resp = requests.post(str(url).strip(), json={"embeds": [embed]}, timeout=10)
                if resp is not None and getattr(resp, "status_code", 0) in (200, 204):
                    sent += 1
            except Exception as e:
                self.error_logging(e, "daily stats webhook send")
        self.append_log(f"[DailyStats] Summary for {day_key} sent to {sent}/{len(urls)} webhook(s): {stats}")

    # ── dry-run mode ────────────────────────────────────────────────────
    def dry_run_active(self):
        try:
            return bool(self.config.get("dry_run", False))
        except Exception:
            return False

    def dry_run_log(self, action):
        try:
            self.append_log(f"[DryRun] Would do: {action} (dry-run mode is ON - no action taken)")
        except Exception:
            pass

    # ── feature schedule view ───────────────────────────────────────────
    def feature_schedule(self):
        """Aggregated view of what each feature will do next (read-only)."""
        cfg = self.config if isinstance(getattr(self, "config", None), dict) else {}
        now = datetime.now()
        det = bool(getattr(self, "detection_running", False))

        def _mm_ready_in():
            try:
                return int(self.mm_seconds_until_ready())
            except Exception:
                return None

        def _next_from_last(attr_name, minutes_key, default_minutes):
            try:
                last = getattr(self, attr_name, None)
                if not isinstance(last, datetime) or last == datetime.min:
                    return 0  # eligible now
                interval = float(cfg.get(minutes_key, default_minutes))
                remaining = interval - (now - last).total_seconds() / 60.0
                return max(0, int(remaining * 60))
            except Exception:
                return None

        schedule = [
            {"name": "Biome Randomizer", "enabled": bool(cfg.get("biome_randomizer")),
             "active": bool(getattr(self, "_br_sc_running", False)),
             "next_in_sec": _next_from_last("last_br_time", "br_duration", 30)},
            {"name": "Strange Controller", "enabled": bool(cfg.get("strange_controller")),
             "active": bool(getattr(self, "_br_sc_running", False)),
             "next_in_sec": _next_from_last("last_sc_time", "sc_duration", 30)},
            {"name": "Merchant Teleporter", "enabled": bool(cfg.get("merchant_teleporter")),
             "active": bool(getattr(self, "_mt_running", False)),
             "next_in_sec": _next_from_last("last_mt_time", "merchant_interval_min", 30)},
            {"name": "Eden Path", "enabled": bool(cfg.get("go_to_eden_spawn")),
             "active": bool(getattr(self, "_eden_running", False)),
             "next_in_sec": None},
            {"name": "Memory Match", "enabled": bool(cfg.get("memory_match_enabled")),
             "active": bool(getattr(self, "_mm_session_active", False)),
             "next_in_sec": _mm_ready_in()},
            {"name": "Quest Board", "enabled": bool(cfg.get("quest_board_enabled")),
             "active": False, "next_in_sec": None},
            {"name": "Obby", "enabled": bool(cfg.get("enable_obby_path")),
             "active": bool(getattr(self, "_obby_running", False)), "next_in_sec": None},
        ]
        macro_stopped = not det
        for item in schedule:
            item["note"] = "Macro stopped" if macro_stopped else ""
            if item["next_in_sec"] is not None and not macro_stopped:
                secs = int(item["next_in_sec"])
                if secs <= 0:
                    item["note"] = "Eligible now (waits for a free slot)"
                else:
                    mins, s = divmod(secs, 60)
                    item["note"] = f"Ready in {mins}m {s:02d}s" if mins else f"Ready in {s}s"
        return {"detection_running": det, "features": schedule}
