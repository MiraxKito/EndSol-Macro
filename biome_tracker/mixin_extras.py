"""
Optional extras for EndSol Macro (v1.0.7).

All extra toggles default to OFF and live in the config:
  - dry_run                  -> log actions instead of performing them
  - key_release_failsafe     -> force-release stuck movement keys after reconnect
  - daily_stats_webhook      -> one Discord summary message per day at ~00:05
  - rare_aura_desktop_notify -> Windows toast on Legendary+ auras

Always-available (no config): feature schedule view, config profiles,
clear-logs. See main.py Api for the UI entry points.
"""

import os
import subprocess
import threading
import time
from datetime import datetime, timedelta

import requests

from .base_support import current_ver

_DAILY_KEYS = ("auras", "biomes", "mm_pairs")
_RARE_AURA_THRESHOLD = 100_000  # Legendary and above


class ExtrasMixin:
    # ── session counters ────────────────────────────────────────────────
    def _daily_bump(self, key, n=1):
        try:
            counters = getattr(self, "_daily_counters", None)
            if counters is None:
                counters = {}
                self._daily_counters = counters
            if key in _DAILY_KEYS:
                counters[key] = int(counters.get(key, 0)) + int(n)
        except Exception:
            pass

    def _daily_snapshot(self):
        """Return current counters and reset them (fish handled by snapshot)."""
        counters = dict(getattr(self, "_daily_counters", {}) or {})
        for key in _DAILY_KEYS:
            counters.setdefault(key, 0)
        self._daily_counters = {k: 0 for k in _DAILY_KEYS}
        try:
            state = getattr(self, "_fishing_runtime_state", None) or {}
            current_fish = int(state.get("fish_caught_count", 0) or 0)
            last_fish = int(getattr(self, "_daily_last_fish", 0) or 0)
            counters["fish"] = max(0, current_fish - last_fish)
            self._daily_last_fish = current_fish
        except Exception:
            counters["fish"] = 0
        return counters

    # ── daily stats webhook ─────────────────────────────────────────────
    def start_daily_stats_loop(self):
        if getattr(self, "_daily_stats_thread", None) and self._daily_stats_thread.is_alive():
            return
        self._daily_stats_thread = threading.Thread(
            target=self._daily_stats_loop, name="Daily Stats", daemon=True
        )
        self._daily_stats_thread.start()

    def _daily_stats_loop(self):
        while getattr(self, "detection_running", False):
            try:
                if self.config.get("daily_stats_webhook", False):
                    now = datetime.now()
                    day_key = now.strftime("%Y-%m-%d")
                    if now.hour == 0 and now.minute >= 5 and getattr(self, "_daily_stats_sent_day", None) != day_key:
                        self._daily_stats_sent_day = day_key
                        self.send_daily_stats_webhook()
            except Exception as e:
                self.error_logging(e, "daily stats loop")
            time.sleep(20)

    def send_daily_stats_webhook(self):
        stats = self._daily_snapshot()
        lines = [
            f"**Auras found:** {stats.get('auras', 0)}",
            f"**Biomes detected:** {stats.get('biomes', 0)}",
            f"**Memory Match pairs:** {stats.get('mm_pairs', 0)}",
            f"**Fish caught:** {stats.get('fish', 0)}",
        ]
        embed = {
            "title": "EndSol Macro — daily summary",
            "description": "\n".join(lines),
            "color": 0x7C5BF5,
            "footer": {"text": f"EndSol Macro {current_ver}"},
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
        self.append_log(f"[DailyStats] Summary sent to {sent}/{len(urls)} webhook(s): {stats}")

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

    # ── key-release failsafe ────────────────────────────────────────────
    def release_all_movement_keys(self, reason=""):
        """Force-release W/A/S/D/Space in case a path playback was cut mid-key."""
        try:
            import keyboard as kb
            for key in ("w", "a", "s", "d", "space"):
                try:
                    kb.release(key)
                except Exception:
                    pass
            try:
                import autoit
                for token in ("{w up}", "{a up}", "{s up}", "{d up}", "{SPACE up}"):
                    try:
                        autoit.send(token)
                    except Exception:
                        pass
            except Exception:
                pass
            if reason:
                try:
                    self.append_log(f"[Failsafe] Released all movement keys ({reason})")
                except Exception:
                    pass
        except Exception:
            pass

    def failsafe_release_if_enabled(self, reason):
        try:
            if self.config.get("key_release_failsafe", False):
                self.release_all_movement_keys(reason)
        except Exception:
            pass

    # ── desktop toast (rare aura) ───────────────────────────────────────
    def desktop_notify(self, title, message):
        try:
            if not self.config.get("rare_aura_desktop_notify", False):
                return
            threading.Thread(target=self._windows_toast, args=(title, message), daemon=True).start()
        except Exception:
            pass

    def _windows_toast(self, title, message):
        """Balloon-tip toast via PowerShell - no extra dependencies."""
        try:
            safe_title = str(title).replace("'", "").replace('"', "")
            safe_msg = str(message).replace("'", "").replace('"', "")
            script = (
                "Add-Type -AssemblyName System.Windows.Forms; "
                "$n = New-Object System.Windows.Forms.NotifyIcon; "
                "$n.Icon = [System.Drawing.SystemIcons]::Information; "
                "$n.Visible = $true; "
                f"$n.ShowBalloonTip(8000, '{safe_title}', '{safe_msg}', "
                "[System.Windows.Forms.TooltipIcon]::Info); "
                "Start-Sleep -Seconds 9; $n.Dispose()"
            )
            subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                timeout=15, capture_output=True,
            )
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
            {"name": "Easter Egg Collection", "enabled": bool(cfg.get("collect_easter_egg")),
             "active": bool(getattr(self, "_egg_collecting", False)),
             "next_in_sec": _next_from_last("last_egg_collect_time", "egg_collect_interval_min", 25)},
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
