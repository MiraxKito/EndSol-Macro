from .base_support import *
from .config import APPDATA_BASE

class DetectionMixin:
    def load_logs(self):
        log_path = APPDATA_BASE / "logs" / "macro_logs.txt"
        if log_path.exists():
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as file:
                lines = file.read().splitlines()
                return lines
        return []

    def load_biome_data(self):
        self._biome_source_status = {"source": "unknown", "reachable": False, "error": None}
        # Sol's RNG Fandom is the authoritative and ONLY remote data source.
        # Everything else comes from the bundled offline snapshot.
        fandom_urls = [
            "https://sol-rng.fandom.com/api.php?action=query&prop=revisions&titles=Biomes&rvprop=content&rvslots=main&format=json&formatversion=2",
            "https://sol-rng.fandom.com/api.php?action=parse&page=Biomes&prop=wikitext&format=json",
            "https://sol-rng.fandom.com/wiki/Biomes?action=raw",
        ]

        # Bundled Fandom snapshot: real wiki data captured offline. This is the
        # offline baseline only — live Fandom (or the last verified cache)
        # always takes precedence over it.
        default_biome_data = {}
        try:
            _snap_path = os.path.join(os.path.dirname(__file__), "biomes_fandom.json")
            with open(_snap_path, "r", encoding="utf-8") as _f:
                _raw_snapshot = json.load(_f)
            for _bn, _bm in _raw_snapshot.items():
                if not isinstance(_bm, dict):
                    continue
                default_biome_data[_bn] = {
                    "color": _bm.get("color", ""),
                    "thumbnail_url": _bm.get("thumbnail_url", ""),
                    "category": _bm.get("category", "weather"),
                    "spawn_chance": _bm.get("spawn_chance", ""),
                    "duration": _bm.get("duration", ""),
                    "chat_message": _bm.get("chat_message", ""),
                    "how_to_get": _bm.get("how_to_get", ""),
                    "description": _bm.get("description", ""),
                }
        except Exception as exc:
            print(f"Could not load bundled Fandom biome snapshot: {exc}")

        auto_update = self.config.get("auto_update_biome_data", True) if hasattr(self, "config") and isinstance(self.config, dict) else True

        metadata_source = "fallback"
        biome_cache_path = APPDATA_BASE / "cache" / "biomes_fandom.json"
        fandom_http_ok = False
        fandom_error = None
        fandom_wikitext = ""
        if auto_update:
            # Fandom first: its Biomes page is authoritative. The parser
            # accepts the common infobox/template form used by the wiki.
            data = {}
            try:
                import re as _re
                for fandom_url in fandom_urls:
                    fandom_response = fandom_get(fandom_url, timeout=15)
                    if fandom_response is None or not fandom_response.ok:
                        continue
                    fandom_http_ok = True
                    raw_text = fandom_response.text or ""
                    wikitext = raw_text
                    try:
                        raw = fandom_response.json()
                        # MediaWiki query responses use either a list or a
                        # keyed pages object, depending on formatversion.
                        pages = raw.get("query", {}).get("pages", []) if isinstance(raw, dict) else []
                        if isinstance(pages, dict):
                            pages = list(pages.values())
                        if pages and isinstance(pages[0], dict):
                            revisions = pages[0].get("revisions", [])
                            if isinstance(revisions, dict):
                                revisions = list(revisions.values())
                            slots = revisions[0].get("slots", {}) if revisions else {}
                            main = slots.get("main", {}) if isinstance(slots, dict) else {}
                            wikitext = (main.get("content", "") or main.get("*", "")) if isinstance(main, dict) else ""
                        # Always retry the action=parse shape if the query
                        # shape produced no text or left a JSON envelope.
                        if not wikitext or not isinstance(wikitext, str) or wikitext.lstrip().startswith("{"):
                            parsed = ((raw.get("parse") or {}).get("wikitext") or {}) if isinstance(raw, dict) else {}
                            wikitext = parsed.get("*", "") if isinstance(parsed, dict) else ""
                    except (ValueError, TypeError, AttributeError):
                        # Keep a successful response available for the partial
                        # name parser instead of discarding it.
                        wikitext = raw_text
                    if not isinstance(wikitext, str) or not wikitext.strip():
                        continue
                    fandom_wikitext = wikitext
                    try:
                        data = self._parse_fandom_biomes_page(wikitext)
                    except Exception as parse_exc:
                        print(f"Fandom biome page parse failed: {parse_exc}")
                        data = {}
                    # A valid parse must yield records with real values, not
                    # just names.
                    if data and len(data) >= 3 and any(
                        (rec.get("spawn_chance") or rec.get("color")) for rec in data.values()
                    ):
                        self._fandom_biome_wikitext = wikitext
                        break
            except Exception as e:
                print(f"Fandom biome data fetch failed; trying compatibility feed: {e}")
            # Compatibility feed is only used when Fandom is unavailable or
            # its markup changes; it is not merged into the user's config.
            if data:
                metadata_source = "fandom"
                self._biome_source_status = {"source": "fandom", "reachable": True, "error": None}
                self._fandom_biome_wikitext = wikitext
                try:
                    biome_cache_path.parent.mkdir(parents=True, exist_ok=True)
                    biome_cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                except Exception as exc:
                    print(f"Could not save Fandom biome cache: {exc}")
            else:
                # A reachable Fandom response with an unparsable page is not
                # source unavailability. Prefer the last verified Fandom cache.
                if fandom_http_ok:
                    # The Biomes page has changed from Biome templates to
                    # heading/table prose. Recover the names from the live
                    # response instead of declaring the cache invalid.
                    # Gameplay values remain explicitly marked as fallback
                    # until their individual article fields are parsed.
                    source_text = fandom_wikitext or ""
                    partial = {}
                    for biome_name, defaults in default_biome_data.items():
                        escaped = _re.escape(biome_name)
                        heading = _re.search(r"(?im)^\s*(?:#{2,6}|={2,6})\s*(?:\*\*)?" + escaped + r"(?:\*\*)?\s*(?:#{2,6}|={2,6})?\s*$", source_text)
                        name_seen = _re.search(r"(?i)(?<![A-Z])" + escaped.replace(r"\ ", r"[ _-]+") + r"(?![A-Z])", source_text)
                        if heading or name_seen:
                            partial[biome_name] = {**defaults, "_metadata_source": "fandom_partial", "_metadata_quality": "name_verified_only"}
                    if len(partial) >= 3:
                        data = partial
                        metadata_source = "fandom_partial"
                        self._biome_source_status = {"source": "fandom_partial", "reachable": True, "error": None, "record_count": len(data)}
                        try:
                            biome_cache_path.parent.mkdir(parents=True, exist_ok=True)
                            biome_cache_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                        except Exception as exc:
                            print(f"Could not save partial Fandom biome cache: {exc}")
                    else:
                        self._biome_source_status = {"source": "fandom_parser_error", "reachable": True, "error": "Fandom responded but no biome records could be parsed"}
                        try:
                            biome_cache_path.parent.mkdir(parents=True, exist_ok=True)
                            cached = json.loads(biome_cache_path.read_text(encoding="utf-8"))
                            if isinstance(cached, dict) and len(cached) >= 3 and all(isinstance(v, dict) for v in cached.values()):
                                data = cached
                                metadata_source = "fandom_cache"
                        except Exception:
                            fandom_error = "Fandom responded but no valid biome cache is installed"
                # No non-Fandom feed: fall back to the last verified Fandom
                # cache, then to the bundled Fandom snapshot.
                if not data and not fandom_http_ok:
                    try:
                        cached = json.loads(biome_cache_path.read_text(encoding="utf-8"))
                        if isinstance(cached, dict) and len(cached) >= 3 and all(isinstance(v, dict) for v in cached.values()):
                            data = cached
                            metadata_source = "fandom_cache"
                            self._biome_source_status = {
                                "source": "fandom_cache",
                                "reachable": False,
                                "error": "Fandom unavailable — using the last verified Fandom cache",
                            }
                            print(f"[Fandom] Offline: using last verified biome cache ({len(data)} records)")
                    except Exception:
                        pass
                if not data:
                    data = default_biome_data
                    metadata_source = "fandom_snapshot"
                    self._biome_source_status = {
                        "source": "fandom_snapshot",
                        "reachable": False,
                        "error": fandom_error or "Fandom unavailable — using the bundled Fandom snapshot",
                    }
            if metadata_source == "fandom":
                print(f"[Fandom] Loaded {len(data)} biome records at startup")

            # Seasonal event flags are fixed locally; no remote kill-switch.
            events = {"april_fools": False}
        else:
            data = default_biome_data
            events = {"april_fools": False}
            metadata_source = "fandom_snapshot"
            self._biome_source_status = {"source": "fandom_snapshot", "reachable": False, "error": "Live Fandom data disabled in settings"}

        if events.get("april_fools"):
            glitched = data.get("GLITCHED", {})
            for biome in data:
                data[biome]["color"] = glitched.get("color", data[biome]["color"])
                data[biome]["thumbnail_url"] = glitched.get("thumbnail_url", data[biome]["thumbnail_url"])

        # Mark provenance so webhook output can refuse to present fallback
        # gameplay metadata as verified facts.
        for meta in data.values():
            if isinstance(meta, dict):
                meta["_metadata_source"] = metadata_source

        # Ensure all biomes have required metadata (spawn_chance, category, duration, how_to_get)
        for biome_name, meta in data.items():
            if biome_name in default_biome_data:
                for key in ["color", "thumbnail_url", "spawn_chance", "category", "duration", "how_to_get", "chat_message"]:
                    if key not in meta or not meta.get(key):
                        meta[key] = default_biome_data[biome_name].get(key, "")

        custom_overrides = self.config.get("custom_biome_overrides", {})
        if isinstance(custom_overrides, dict):
            for biome_name, overrides in custom_overrides.items():
                try:
                    if biome_name in data and isinstance(overrides, dict):
                        for key in ["color", "thumbnail_url", "spawn_chance", "category", "duration", "how_to_get", "start_description", "end_description"]:
                            if key in overrides and overrides[key]:
                                data[biome_name][key] = overrides[key]
                except Exception:
                    pass

        # Ensure ALL biomes from default_biome_data are present in data
        # This handles cases where GitHub data is missing newer biomes
        added_count = 0
        for biome_name, default_meta in default_biome_data.items():
            if biome_name not in data:
                data[biome_name] = default_meta.copy()
                data[biome_name]["_metadata_source"] = "fandom_snapshot"
                added_count += 1
            else:
                # Backfill missing metadata from defaults
                for key in ["color", "thumbnail_url", "spawn_chance", "category", "duration", "how_to_get", "chat_message"]:
                    if key not in data[biome_name] or not data[biome_name].get(key):
                        data[biome_name][key] = default_biome_data[biome_name].get(key, "")
        
        # Only log if we actually added missing biomes (not just backfilled)
        # Missing remote entries are compatibility fallbacks, not a migration.
        # Do not append the same "added missing biomes" message on every startup.

        # Hidden biomes (passive mechanics like TIME) never reach the UI,
        # stats, or webhooks — they stay in the parse output for aura links.
        # The name check also covers stale caches written before the flag.
        data = {
            k: v for k, v in data.items()
            if not (isinstance(v, dict) and (v.get("hidden") or k.strip().upper() == "TIME"))
        }
        return data

    def error_logging(self, exception, custom_message=None, max_log_size=3 * 1024 * 1024):
        log_file = APPDATA_BASE / "logs" / "error_logs.txt"
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        error_type = type(exception).__name__
        error_message = str(exception)
        stack_trace = traceback.format_exc()

        with self._log_lock:
            if not log_file.exists():
                log_file.parent.mkdir(parents=True, exist_ok=True)
                with open(log_file, "w", encoding="utf-8") as log:
                    log.write("Error Log File Created\n")
                    log.write("-" * 40 + "\n")

            if log_file.exists() and log_file.stat().st_size > max_log_size:
                with open(log_file, "r", encoding="utf-8") as log:
                    lines = log.readlines()
                with open(log_file, "w", encoding="utf-8") as log:
                    log.writelines(lines[-1000:])

            with open(log_file, "a", encoding="utf-8") as log:
                log.write(f"\n[{timestamp}] ERROR LOG\n")
                log.write(f"Error Type: {error_type}\n")
                log.write(f"Error Message: {error_message}\n")
                if custom_message:
                    log.write(f"Custom Message: {custom_message}\n")
                log.write(f"Traceback:\n{stack_trace}\n")
                log.write("-" * 40 + "\n")

    def save_logs(self):
        log_file_path = APPDATA_BASE / "logs" / "macro_logs.txt"
        with self._log_lock:
            if log_file_path.exists() and log_file_path.stat().st_size > 10 * 1024 * 1024:
                backup = log_file_path.with_suffix(".txt.bak")
                try:
                    if backup.exists():
                        backup.unlink()
                    log_file_path.rename(backup)
                except Exception:
                    pass

    def take_aura_screenshot_now(self, force=False):
        try:
            if not force:
                if not getattr(self, "periodical_aura_var", None) or not self.periodical_aura_var.get():
                    return
                if self.config.get("enable_idle_mode", False):
                    return
            if not self.check_roblox_procs():
                return
            if (getattr(self, "_egg_collecting", False) or getattr(self, "_eden_running", False) or getattr(self, "_potion_thread_active", False)):
                return

            for _ in range(4):
                self.activate_roblox_window()
                time.sleep(0.35)

            aura_menu = self.config.get("aura_menu", [0, 0])
            search_bar = self.config.get(
                "aura_search_bar",
                self.config.get("search_bar", [834, 364]),
            )
            inventory_close_button = self.config.get("inventory_close_button", [1418, 298])
            if aura_menu and aura_menu[0]:
                try:
                    autoit.mouse_click("left", aura_menu[0], aura_menu[1], 1, speed=3)
                    time.sleep(0.67)
                    autoit.mouse_click("left", search_bar[0], search_bar[1], 1, speed=3)
                except Exception:
                    try:
                        self.Global_MouseClick(aura_menu[0], aura_menu[1])
                    except Exception:
                        pass
                time.sleep(0.67)
                try:
                    screenshot_dir = os.path.join(os.getcwd(), "images")
                    os.makedirs(screenshot_dir, exist_ok=True)
                    filename = os.path.join(screenshot_dir, f"aura_screenshot_{int(time.time())}.png")
                    sent = False
                    if not self.is_roblox_focused():
                        self.append_log("[Aura Screenshot] Roblox not focused, skipping screenshot")
                    else:
                        img = pyautogui.screenshot()
                        img.save(filename)
                        sent = True
                    if sent and filename and os.path.exists(filename):
                        self.send_aura_screenshot_webhook(filename)
                        self.last_aura_screenshot_time = datetime.now()
                    autoit.mouse_click("left", inventory_close_button[0], inventory_close_button[1], 1, speed=3)
                    time.sleep(0.67)
                except Exception as e:
                    self.error_logging(e, "Error taking/sending forced aura screenshot")
        except Exception as e:
            self.error_logging(e, "Error in take_aura_screenshot_now")

    def open_customize_biome_embed(self):
        # Seasonal event flags are fixed locally; no remote kill-switch.
        events = {"april_fools": False}
        if events.get("april_fools"):
            messagebox.showinfo("April Fools Active", "Embed customization is disabled while the April Fools event is active.")
            return
        win = ttk.Toplevel(self.root)
        win.title("Customize Biome Embed")
        win.geometry("760x560")
        container = ttk.Frame(win)
        container.pack(fill="both", expand=True, padx=8, pady=8)
        canvas = ttk.Canvas(container)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        scrollbar.pack(side="right", fill="y")
        canvas.configure(yscrollcommand=scrollbar.set)
        inner = ttk.Frame(canvas)
        canvas.create_window((0, 0), window=inner, anchor="nw")
        def on_config(e):
            try:
                canvas.configure(scrollregion=canvas.bbox("all"))
            except Exception:
                pass
        inner.bind("<Configure>", on_config)
        vars_map = {}
        for i, biome in enumerate(self.biome_data.keys()):
            ttk.Label(inner, text=biome).grid(row=i, column=0, sticky="w", padx=6, pady=6)
            color_val = self.biome_data.get(biome, {}).get("color", "")
            thumb_val = self.biome_data.get(biome, {}).get("thumbnail_url", "")
            cvar = ttk.StringVar(value=color_val)
            tvar = ttk.StringVar(value=thumb_val)
            vars_map[biome] = (cvar, tvar)
            ttk.Entry(inner, textvariable=cvar, width=20).grid(row=i, column=1, padx=6, pady=6)
            ttk.Entry(inner, textvariable=tvar, width=60).grid(row=i, column=2, padx=6, pady=6)
        link = "https://www.rapidtables.com/convert/color/index.html"
        link_label = ttk.Label(win, text="Click here to get colour code", foreground="royalblue", cursor="hand2")
        link_label.configure(font=('Segoe UI', 9, 'underline'))
        link_label.pack(side="bottom", pady=8)
        link_label.bind("<Button-1>", lambda e: webbrowser.open_new(link))
        def save_and_close():
            overrides = {}
            for biome, (cvar, tvar) in vars_map.items():
                color_val = cvar.get().strip()
                thumb_val = tvar.get().strip()
                overrides[biome] = {"color": color_val, "thumbnail_url": thumb_val}
                try:
                    if biome in self.biome_data:
                        if color_val:
                            self.biome_data[biome]["color"] = color_val
                        if thumb_val:
                            self.biome_data[biome]["thumbnail_url"] = thumb_val
                except Exception:
                    pass
            try:
                from .config import get_config_file
                config_path = get_config_file()
                cfg = {}
                if config_path.exists():
                    with open(config_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                
                cfg["custom_biome_overrides"] = overrides
                
                # Write back safely via tmp file just to be clean, or directly
                with open(config_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=4)
                    
            except Exception as e:
                print(f"Error saving custom_biome_overrides to config: {e}")

            self.config["custom_biome_overrides"] = overrides
            messagebox.showinfo("Saved", "Biome embed customizations saved.")
            win.destroy()
        ttk.Button(win, text="Save & Close", command=save_and_close).pack(side="bottom", pady=6)

    def confirm_biome_popup(self, biome):
        cb = getattr(self, "on_biome_confirm_request", None)
        if callable(cb):
            try:
                result = cb(biome)
                if result is None:
                    return None
                result = bool(result)
                return result
            except Exception as e:
                self.error_logging(e, "Error in confirm_biome_popup callback")
                return None
        return None


    def get_total_session_time(self):
        try:
            now = datetime.now()
            if self.start_time:
                elapsed_time = int((now - self.start_time).total_seconds())
                total_seconds = self.saved_session + elapsed_time
                self.current_session += 1
            else:
                total_seconds = self.saved_session

            if total_seconds >= 86400:
                overflow = total_seconds - 86400
                self.session_window_start = datetime.now()
                self.saved_session = overflow
                if self.start_time:
                    self.start_time = datetime.now()
                self._session_window_reset_performed = True
                total_seconds = overflow

            if total_seconds >= 86400:
                return self.format_seconds_to_hhmmss(86400)

            return self.format_seconds_to_hhmmss(total_seconds)

        except Exception as e:
            self.error_logging(e, "Error in get_total_session_time function.")
            return "00:00:00"

    def parse_session_time(self, session_time_str):
        try:
            if not isinstance(session_time_str, str): session_time_str = str(session_time_str)
            parts = session_time_str.split(":")
            if len(parts) == 3:  # Format: hours:minutes:seconds
                hours, minutes, seconds = map(int, parts)
                return hours * 3600 + minutes * 60 + seconds
            return 0
        except Exception as e:
            self.error_logging(e, "Error parsing session time.")
            return 0  # Return default value in case of error

    def update_session_time(self):
        try:
            session_str = self.get_total_session_time()
            if hasattr(self, "session_label"):
                self.session_label.config(text=f"Running Session: {session_str}")
            if getattr(self, "_session_window_reset_performed", False):
                try:
                    self.save_config()
                except Exception:
                    pass
                self._session_window_reset_performed = False
        except Exception as e:
            self.error_logging(e, "Error in update_session_time function.")

    def display_logs(self, logs=None):
        if not hasattr(self, "logs_text"):
            return
        self.logs_text.config(state="normal")
        self.logs_text.delete(1.0, ttk.END)

        if logs is None:
            logs = self.logs

        last_logs = logs[-10:]

        for log in last_logs:
            self.logs_text.insert(ttk.END, log + "\n")
        self.logs_text.config(state="disabled")

    def filter_logs(self, keyword):
        filtered_logs = [log for log in self.logs if keyword.lower() in log.lower()]
        self.display_logs(filtered_logs)

    def append_log(self, message):
        timestamp = datetime.now().strftime("%d/%m/%y %H:%M:%S")
        stamped = f"[{timestamp}] {message}"
        self.logs.append(stamped)
        try:
            print(f"[log] {stamped}")
        except (UnicodeEncodeError, UnicodeDecodeError):
            print(f"[log] {stamped.encode('ascii', 'replace').decode('ascii')}")
        self._schedule_log_save()
        if hasattr(self, "logs_text"):
            self.display_logs()
            self.logs_text.see(ttk.END)

    def _schedule_log_save(self):
        if self._log_timer is not None:
            self._log_timer.cancel()
        self._log_timer = threading.Timer(2.0, self._flush_log_save)
        self._log_timer.daemon = True
        self._log_timer.start()

    def _flush_log_save(self):
        log_file_path = APPDATA_BASE / "logs" / "macro_logs.txt"
        with self._log_lock:
            log_file_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file_path, "a", encoding="utf-8") as f:
                if self.logs:
                    f.write(self.logs[-1] + "\n")
            if log_file_path.exists() and log_file_path.stat().st_size > 10 * 1024 * 1024:
                backup = log_file_path.with_suffix(".txt.bak")
                try:
                    if backup.exists():
                        backup.unlink()
                    log_file_path.rename(backup)
                except Exception:
                    pass

    def show_reconnect_info(self):
        messagebox.showinfo(
            "Auto Reconnect Info",
            "(?) This feature only able to reconnect if:\n \n"
            "(1) Your private server link is valid. Supported formats include:\n"
            "    - Private server code links (privateServerLinkCode=...)\n"
            "    - Share links (https://www.roblox.com/share?code=...&type=Server)\n \n"
            "(2) Make sure to calibrate mouse click for 'Start' button in 'Assign Inventory Click' \n \n"
            "(3) If reconnect fails, try a different link format (share link or private server code link). \n \n"
            "(Note: This reconnect feature still on experimental phase, there's a chance it gonna be failed to reconnect back to your server!)"
        )

    def start_detection(self):
        with getattr(self, "lock", threading.Lock()):
            if self.detection_running: return
            now = datetime.now()
            self.detection_running = True
            # The first aura detected right after startup is the aura the
            # user was ALREADY wearing before pressing Start — announcing it
            # would spam Discord with stale info. Ignore that first
            # detection; every later aura change is detected normally.
            self.last_aura_found = None
            self._aura_webhook_skip_first = True

        # ── Auto-switch to an English keyboard layout ──
        # Every macro action that types a literal symbol (chat commands like
        # "/aura", button hotkeys, OCR-trusted input) needs the English layout
        # active; on a Cyrillic/RU layout the same keystrokes would produce
        # the wrong characters. If no English layout is installed on the
        # machine we abort before any background threads spin up, so the
        # user sees a clear explanation instead of silent misclicks.
        kb_result = switch_to_english_layout()
        if not kb_result.get("english_available"):
            err = kb_result.get("error") or "no English layout installed"
            try:
                messagebox.showerror(
                    "EndSol Macro — Keyboard Layout Required",
                    "No English (US/UK/...) keyboard layout is installed on this system.\n\n"
                    "EndSol Macro types literal characters for in-game actions and chat commands, "
                    "which only work correctly under an English layout. Without one, every action "
                    "would send the wrong key.\n\n"
                    "Add an English layout in Windows Settings → Time & Language → Language, "
                    "then restart the macro.\n\n"
                    f"Details: {err}"
                )
            except Exception:
                print(f"[start_detection] Cannot start — {err}")
            self.detection_running = False
            try:
                self.set_title_threadsafe(f"EndSol Macro {current_ver} (Stopped — English keyboard layout required)")
            except Exception:
                pass
            return
        if not kb_result.get("ok") and not kb_result.get("already_english"):
            # English layout exists but we couldn't activate it. Don't block
            # the user entirely, but log a loud warning so they can see it.
            err = kb_result.get("error") or "ActivateKeyboardLayout failed"
            try:
                self.append_log(f"[WARN] Could not switch to English keyboard layout: {err}")
            except Exception:
                print(f"[start_detection] KB switch warning: {err}")

        self._start_player_logger_thread()
        self.start_time = now
        self.current_session = 0
        self.has_started_once = True
        self._session_window_reset_performed = False
        self.stop_sent = False
        self.last_egg_collect_time = datetime.min

        # reset disconnect tracking so the macro doesnt log old disconnect 
        self._disconnect_log_file = None
        self._last_position_disconnect = 0
        self._last_disconnect_time = 0
        self._disconnect_handled = False
        self.has_sent_disconnected_message = False
        self._roblox_fullscreened = False
        self._roblox_fullscreen_last_try = 0.0

        # Force fullscreen attempt on macro start if enabled
        if self.config.get("auto_roblox_fullscreen", False):
            self._force_roblox_fullscreen()

        if not self.session_window_start:
            self.session_window_start = now
            self.saved_session = 0
        else:
            try:
                if (now - self.session_window_start).total_seconds() >= 86400:
                    self.session_window_start = now
                    self.saved_session = 0
            except Exception:
                self.session_window_start = now
                self.saved_session = 0

        self.config["session_window_start"] = self.session_window_start.isoformat()
        self.config["macro_last_start"] = now.isoformat()
        self.save_config()
        self.set_title_threadsafe(f"""EndSol Macro {current_ver} (Running)""")
        self.send_webhook_status("Macro started!", color=0x64ff5e)

        # Item usage (Strange Controller, Biome Randomizer, portable crack)
        # is due IMMEDIATELY on every cycle start; the configured intervals
        # apply from this first use onwards.
        # IMPORTANT: this block must run BEFORE the background threads below
        # are started. Otherwise the item loop can tick before the startup
        # gate exists (firing SC/BR while the window is still settling) and
        # the timer reset below would wipe the cooldown that first fire just
        # set — causing a double fire of the same item seconds apart.
        # Never replay historical log entries: starting the macro must not
        # re-detect auras/biomes that were rolled before it was running
        # (this is how a stale "Celestial" could be announced at startup).
        try:
            _latest_log = self.get_latest_log_file()
            if _latest_log and os.path.exists(_latest_log):
                self.last_position = os.path.getsize(_latest_log)
                self.last_position_aura = os.path.getsize(_latest_log)
                self._last_read_log_file_main = _latest_log
                self._last_read_log_file_last_position_aura = _latest_log
        except Exception:
            self.last_position = 0
            self.last_position_aura = 0
        self.last_br_time = datetime.min
        self.last_sc_time = datetime.min
        self.last_crack_time = datetime.min
        # Give fullscreen/focus ~10s to settle before the first item usage.
        self._items_startup_gate = datetime.now() + timedelta(seconds=10)
        self._item_usage_lock = threading.Lock()

        threads = [
            (self.check_disconnect_loop, "Disconnect Check"),
            (self.biome_loop_check, "Biome Check"),
            (self.biome_itemchange_loop, "Item Change"),
            (self.aura_loop_check, "Aura Check"),
            (self.anti_afk_loop, "Anti-AFK"),
            (self.quest_claim_loop, "Quest Claim"),
            (self.daily_event_check_loop, "Daily Event Check-in"),
            (self.quest_board_loop, "Quest Board"),
            (self.obby_path_loop, "Obby Path"),
            (self.eden_ocr_check_loop, "Eden OCR Check"),
            (self.merchant_ocr_check_loop, "Merchant OCR Check"),
            (self.eden_contract_loop, "Eden Contract"),
            (self.memory_match_loop, "Memory Match"),
            (self.start_daily_stats_loop, "Daily Stats"),
        ]

        for thread_func, name in threads:
            thread = threading.Thread(target=thread_func, name=name, daemon=True)
            thread.start()

        # Fire one anti-AFK cycle immediately in background so users
        # do not need to wait the first 268s interval.
        try:
            threading.Thread(
                target=self.perform_anti_afk_action,
                name="Anti-AFK Initial",
                daemon=True,
            ).start()
        except Exception:
            pass

        # Auto-start the remote Discord bot when it is configured.
        try:
            if self.config.get("remote_access_enabled") and str(self.remote_bot_token_var.get() or "").strip():
                if not (getattr(self, "remote_bot_thread", None) and self.remote_bot_thread.is_alive()):
                    self.start_remote_bot()
        except Exception as e:
            try:
                self.error_logging(e, "remote autostart failed")
            except Exception:
                pass

        print("Biome detection started.")

    def stop_detection(self):
        with getattr(self, "lock", threading.Lock()):
            if not getattr(self, "detection_running", False): return
            self.detection_running = False
            
        # Reset fullscreen flag so it can be re-attempted on next start
        self._roblox_fullscreened = False
        self._roblox_fullscreen_last_try = 0.0
            
        if hasattr(self, "on_status_change") and callable(self.on_status_change):
            try:
                self.on_status_change("IDLE")
            except Exception:
                pass

        caller_stack = traceback.extract_stack()
        if len(caller_stack) >= 2:
            caller = caller_stack[-2]
            stop_reason = f"[TRACEBACK] Macro stopped by {caller.filename}:{caller.lineno} in {caller.name}()"
        else:
            stop_reason = "[TRACEBACK] Macro stopped (unknown caller)"
        try:
            self.append_log(stop_reason)
        except Exception: pass
        print(stop_reason)

        now = datetime.now()
        self._stop_player_logger_thread()
        if getattr(self, "timer_paused_by_disconnect", False):
            elapsed_time = 0
            self.timer_paused_by_disconnect = False
        else:
            if self.start_time:
                elapsed_time = int((now - self.start_time).total_seconds())
            else:
                elapsed_time = 0

        session_seconds = elapsed_time

        if self.session_window_start and (now - self.session_window_start).total_seconds() >= 86400:
            last24h_seconds = session_seconds
        else:
            last24h_seconds = self.saved_session + elapsed_time
            if last24h_seconds > 86400:
                last24h_seconds = 86400

        self.saved_session += elapsed_time
        self.start_time = None
        self.stop_sent = True
        self.set_title_threadsafe(f"EndSol Macro {current_ver} (Stopped)")
        self.send_macro_summary(last24h_seconds)
        print("closed", self.current_session)
        self.save_config()
        print("Biome detection stopped.")

    def get_latest_log_file(self):
        files = [os.path.join(self.logs_dir, f) for f in os.listdir(self.logs_dir) if f.endswith('.log')]
        latest_file = None
        latest_mtime = -1
        for f in files:
            try:
                mt = os.path.getmtime(f)
                if mt > latest_mtime:
                    latest_mtime = mt
                    latest_file = f
            except (FileNotFoundError, OSError):
                continue
        if latest_file is None:
            raise FileNotFoundError("No valid Roblox log files found")
        return latest_file

    def _get_target_roblox_username(self):
        try:
            raw = self.config.get("roblox_username", "")
            if raw is None:
                return ""
            return str(raw).strip().lower()
        except Exception:
            return ""

    def _extract_tutorial_cursor_username(self, line):
        try:
            if not line:
                return ""
            if "TutorialCursor" not in line or "Infinite yield possible" not in line or "Players." not in line:
                return ""
            match = re.search(
                r"Players\.([^.']+)\.PlayerGui:WaitForChild\((?:\"|\\\")TutorialCursor(?:\"|\\\")\)",
                line,
                re.IGNORECASE,
            )
            if not match:
                return ""
            return str(match.group(1) or "").strip().lower()
        except Exception:
            return ""

    def _consume_log_username_validation(self, log_file_path, lines=None):
        try:
            target_username = self._get_target_roblox_username()
            if not target_username:
                return True
            if not log_file_path:
                return False

            state_map = getattr(self, "_log_username_state_map", None)
            if not isinstance(state_map, dict):
                state_map = {}
                self._log_username_state_map = state_map
            
            last_guard_username = getattr(self, "_log_username_state_target", None)
            if last_guard_username != target_username:
                state_map.clear()
                self._log_username_state_target = target_username

            state = state_map.get(log_file_path)
            if state == "rejected":
                return False
            if state == "accepted":
                return True
            if state is None:
                state_map[log_file_path] = "pending"

            # While this file is pending, keep scanning the entire file until
            # the TutorialCursor line appears and we can accept/reject it.
            lines_to_scan = lines
            if lines_to_scan is None:
                try:
                    with open(log_file_path, "r", encoding="utf-8", errors="ignore") as f:
                        lines_to_scan = f.readlines()
                except Exception:
                    lines_to_scan = []

            for line in (lines_to_scan or []):
                found_username = self._extract_tutorial_cursor_username(line)
                if not found_username:
                    continue
                if found_username == target_username:
                    state_map[log_file_path] = "accepted"
                    return True

                state_map[log_file_path] = "rejected"
                try:
                    self.append_log(
                        f"[Log Guard] Ignoring log file due to TutorialCursor username mismatch. "
                        f"Expected '{target_username}', got '{found_username}'."
                    )
                except Exception:
                    pass
                return False

            if len(state_map) > 200:
                state_map.clear()
                state_map[log_file_path] = "pending"
            return True
        except Exception as e:
            self.error_logging(e, "Error validating log username guard")
            return True

    def read_log_file(self, log_file_path):
        if not os.path.exists(log_file_path):
            print(f"Log file not found: {log_file_path}")
            return []

        def is_chat_log(line):
            if "ExpChat" in line or "mountClientApp" in line or "Time record" in line or "[Server]" in line:
                excluded_phrases = [
                    "[Merchant]: Mari has arrived on the island...",
                    "[Merchant]: Jester has arrived on the island!!"
                ]
                return not any(phrase in line for phrase in excluded_phrases)
            return False

        if getattr(self, "_last_read_log_file_main", None) != log_file_path:
            self._last_read_log_file_main = log_file_path
            self.last_position = 0

        # Line-safe incremental read (binary): the offset is only advanced
        # past COMPLETE "\n"-terminated lines. A text-mode
        # readlines()+tell() could land mid-line while Roblox is still
        # flushing, splitting a line across two reads - a split silently
        # broke the [BloxstrapRPC] biome regex and detection was lost.
        pos = max(0, int(self.last_position or 0))
        try:
            size = os.path.getsize(log_file_path)
        except OSError:
            size = 0
        if pos > size:
            pos = 0

        with open(log_file_path, 'rb') as file:
            file.seek(pos)
            data = file.read()

        cut = data.rfind(b"\n")
        if cut == -1:
            # No complete line yet - do not advance the offset.
            if not self._consume_log_username_validation(log_file_path):
                return []
            return []
        consumed = data[:cut + 1]
        self.last_position = pos + cut + 1
        lines = consumed.decode("utf-8", errors="ignore").splitlines()

        if not self._consume_log_username_validation(log_file_path):
            return []
        return [line for line in lines if not is_chat_log(line)]

    def read_log_file_for_detector(self, log_file_path, pos_attr='last_position', filter_chat=False):
        if not os.path.exists(log_file_path):
            return []

        try:
            if getattr(self, f"_last_read_log_file_{pos_attr}", None) != log_file_path:
                setattr(self, f"_last_read_log_file_{pos_attr}", log_file_path)
                setattr(self, pos_attr, 0)
                
            pos = max(0, int(getattr(self, pos_attr, 0) or 0))
            try:
                size = os.path.getsize(log_file_path)
            except OSError:
                size = 0
            if pos > size:
                pos = 0

            # Line-safe incremental read (binary): only consume COMPLETE
            # "\n"-terminated lines. readlines()+tell() could land mid-line
            # while Roblox was still flushing a long line, splitting it
            # across two reads - a split silently broke the
            # "state":"Equipped" aura regex and detection was lost until
            # the next roll. The partial tail stays unconsumed and is read
            # whole on the next poll.
            with open(log_file_path, 'rb') as f:
                f.seek(pos)
                data = f.read()

            cut = data.rfind(b"\n")
            if cut == -1:
                # No complete line yet - keep the offset and wait.
                if not self._consume_log_username_validation(log_file_path):
                    return []
                return []
            setattr(self, pos_attr, pos + cut + 1)
            lines = data[:cut + 1].decode("utf-8", errors="ignore").splitlines()

            if not self._consume_log_username_validation(log_file_path):
                return []

            if filter_chat:
                def is_chat_log(line):
                    if "ExpChat" in line or "mountClientApp" in line:
                        excluded_phrases = [
                            "[Merchant]: Mari has arrived on the island...",
                            "[Merchant]: Jester has arrived on the island!!"
                        ]
                        return not any(phrase in line for phrase in excluded_phrases)
                    return False

                return [line for line in lines if not is_chat_log(line)]

            return lines

        except Exception as e:
            self.error_logging(e, f"read_log_file_for_detector error ({pos_attr})")
            return []

    def read_full_log_file(self, log_file_path):
        if not os.path.exists(log_file_path):
            print(f"Log file not found: {log_file_path}")
            return []

        with open(log_file_path, 'r', encoding='utf-8', errors='ignore') as file:
            lines = file.readlines()
            if not self._consume_log_username_validation(log_file_path, lines):
                return []
            return lines

    def _merge_aura_media(self, data):
        """
        Merge cutscene/music media from the bundled audit snapshot into the
        live-parsed aura data. The main Auras wiki page does NOT embed the
        per-aura cutscene files (those live on each aura's own page), so the
        live parse alone never carries video/music — the audit pass fills
        them in (video_url, music_url, cutscene_note, _fandom_title).
        """
        try:
            snapshot = self._get_default_auras_data()
            if not isinstance(snapshot, dict):
                return data
            merged = 0
            for key, entry in (data or {}).items():
                if not isinstance(entry, dict):
                    continue
                src = snapshot.get(key)
                if not isinstance(src, dict):
                    continue
                touched = False
                for field in ("video_url", "video_file", "video_kind", "music_url", "music_file", "cutscene_note"):
                    val = src.get(field)
                    if val and not entry.get(field):
                        entry[field] = val
                        touched = True
                override = str(src.get("_fandom_title") or "").strip()
                if override:
                    entry["_fandom_title"] = override
                    if src.get("fandom_page"):
                        entry["fandom_page"] = src["fandom_page"]
                    touched = True
                if touched:
                    merged += 1
            if merged:
                print(f"[Fandom] Merged cutscene/music media for {merged} auras from the audit snapshot")
        except Exception as e:
            print(f"Aura media merge skipped: {e}")
        return data

    def load_auras_json(self):
        self._aura_source_status = {"source": "unknown", "reachable": False, "error": None}
        """Load aura data from Sol's RNG Fandom wiki (primary) or local cache (fallback)."""
        fandom_urls = [
            "https://sol-rng.fandom.com/api.php?action=query&prop=revisions&titles=Auras&rvprop=content&rvslots=main&format=json&formatversion=2",
            "https://sol-rng.fandom.com/api.php?action=parse&page=Auras&prop=wikitext&format=json",
            "https://sol-rng.fandom.com/wiki/Auras?action=raw",
        ]
        local_cache_path = os.path.join(os.path.dirname(__file__), "auras_cache.json")

        auto_update = self.config.get("auto_update_biome_aura_data", True) if hasattr(self, "config") and isinstance(self.config, dict) else True

        fandom_http_ok = False
        if auto_update:
            try:
                for fandom_url in fandom_urls:
                    r = fandom_get(fandom_url, timeout=15)
                    if r is None or not r.ok:
                        continue
                    fandom_http_ok = True
                    wikitext = r.text or ""
                    try:
                        raw = r.json()
                        pages = raw.get("query", {}).get("pages", []) if isinstance(raw, dict) else []
                        if pages and isinstance(pages[0], dict):
                            revisions = pages[0].get("revisions", [])
                            slots = revisions[0].get("slots", {}) if revisions else {}
                            main = slots.get("main", {}) if isinstance(slots, dict) else {}
                            wikitext = main.get("content", "") if isinstance(main, dict) else ""
                        if not wikitext or wikitext.startswith("{"):
                            wikitext = r.json().get("parse", {}).get("wikitext", {}).get("*", "")
                    except (ValueError, TypeError, AttributeError):
                        pass
                    if not wikitext:
                        continue
                    data = self._parse_fandom_auras(wikitext)
                    # Cross-enrich aura biome links from the Biomes page so
                    # native/exclusive mapping is complete, not guessed.
                    try:
                        biome_wiki = getattr(self, "_fandom_biome_wikitext", "")
                        if not biome_wiki:
                            _rr = fandom_get(
                                "https://sol-rng.fandom.com/api.php?action=parse&page=Biomes&prop=wikitext&format=json",
                                timeout=10,
                            )
                            if _rr is not None and _rr.ok:
                                biome_wiki = _rr.text or ""
                                try:
                                    biome_wiki = _rr.json().get("parse", {}).get("wikitext", {}).get("*", "") or biome_wiki
                                except (ValueError, AttributeError):
                                    pass
                        if biome_wiki:
                            self._fandom_biome_wikitext = biome_wiki
                            self._enrich_auras_from_biomes(data, self._parse_fandom_biomes_page(biome_wiki))
                    except Exception as enrich_exc:
                        print(f"Aura/biome enrichment skipped: {enrich_exc}")
                    if data:
                        try:
                            data = self._merge_aura_media(data)
                            with open(local_cache_path, "w", encoding="utf-8") as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                        except Exception:
                            pass
                        data = self._repair_known_aura_metadata(data)
                        self._aura_source_status = {"source": "fandom", "reachable": True, "error": None}
                        print(f"[Fandom] Loaded {len(data)} aura records at startup")
                        return data
            except Exception as e:
                print(f"Fandom aura fetch failed: {e}")

        # Fallback: load from local cache
        if os.path.exists(local_cache_path):
            try:
                with open(local_cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and data:
                        data = self._merge_aura_media(data)
                        data = self._repair_known_aura_metadata(data)
                        self._aura_source_status = {"source": "fandom_cache", "reachable": fandom_http_ok, "error": "Fandom responded but its aura data could not be parsed" if fandom_http_ok else "Fandom unavailable"}
                        for item in data.values():
                            if isinstance(item, dict): item.setdefault("_metadata_source", "fandom_cache")
                        return data
            except Exception:
                pass

        # Last resort: hardcoded minimal set
        self._aura_source_status = {"source": "fandom_snapshot", "reachable": fandom_http_ok, "error": "Fandom responded but no valid aura records were parsed — using bundled Fandom snapshot" if fandom_http_ok else "Fandom unavailable — using bundled Fandom snapshot"}
        data = self._get_default_auras_data()
        for item in data.values():
            if isinstance(item, dict): item.setdefault("_metadata_source", "fandom_snapshot")
        return data

    @staticmethod
    def _repair_known_aura_metadata(data):
        """Normalize legacy cache records without inventing rare details."""
        if not isinstance(data, dict):
            return data
        # Known parser artifact: the Fandom Auras page names some gallery
        # images with variant suffixes, so ▣ PIXELATION ▣ got keyed under
        # "PixelationStatic" (from its collection image) instead of the real
        # aura name — lookups for "Pixelation" then missed entirely (no
        # rarity/source in the webhook, no ping). The record IS the base
        # aura: 1 in 1,073,741,824 (Transcendent), 1 in 536,870,912 in
        # Cyberspace. Repair the key and its native biome so lookups hit.
        _pixelation = data.pop("PixelationStatic", None)
        if isinstance(_pixelation, dict):
            _base = data.get("Pixelation")
            if not isinstance(_base, dict):
                _pixelation["native_biome"] = ["CYBERSPACE", 2]
                data["Pixelation"] = _pixelation
            else:
                for _field in ("rarity", "rarity_name", "obtainment", "obtainment_type"):
                    if not _base.get(_field) and _pixelation.get(_field):
                        _base[_field] = _pixelation[_field]
        # More parser artifacts. Record keys must match the name the game
        # actually writes into the Roblox log ("state":"Equipped \"...\"");
        # an audit of real logs found exactly two more mismatches:
        #   - the crafted mutation is written as "Atlas_A.T.L.A.S." — the
        #     wiki gallery image name added a bogus "Static" suffix;
        #   - the Easter 2026 aura is written as "Aegis_EGGIS" — the wiki
        #     page lists it as just "Eggis".
        # ("Static"-suffixed records can never be matched by log names, so
        # they are harmless dead weight — but these two had NO reachable
        # record under the real game name at all.)
        _atlas_mut = data.pop("Atlas_A.T.L.A.S.Static", None)
        if isinstance(_atlas_mut, dict) and not isinstance(data.get("Atlas_A.T.L.A.S."), dict):
            data["Atlas_A.T.L.A.S."] = _atlas_mut
        _eggis = data.pop("Eggis", None)
        if isinstance(_eggis, dict) and not isinstance(data.get("Aegis_EGGIS"), dict):
            data["Aegis_EGGIS"] = _eggis
        for item in data.values():
            if not isinstance(item, dict):
                continue
            # A legacy cache cannot distinguish native from exclusive: the
            # old parser put every biome mention in exclusive_biome. Never
            # silently reinterpret it. Keep it as an unverified hint until
            # the individual Fandom page is parsed.
            if "native_biome" not in item:
                item["native_biome"] = ["None", 1]
            if item.get("exclusive_biome") and item["exclusive_biome"][0] != "None":
                item["_metadata_quality"] = "legacy_biome_unverified"
            native = item.get("native_biome")
            exclusive = item.get("exclusive_biome")
            if not item.get("obtainment"):
                if isinstance(exclusive, list) and exclusive and exclusive[0] != "None":
                    item["obtainment"] = f"Exclusive to {exclusive[0]} (obtainment not verified)"
                    item["obtainment_type"] = "exclusive_unverified"
                elif isinstance(native, list) and native and native[0] != "None":
                    item["obtainment"] = f"Native to {native[0]} (obtainment not verified)"
                    item["obtainment_type"] = "native_unverified"
                else:
                    item["obtainment"] = "Obtainment details unavailable in cached index"
                    item["obtainment_type"] = "unknown"
        # These fixed-rarity DREAMSPACE auras are listed in the Fandom
        # reference table but older local caches omitted their biome field.
        known = {"★": (100, "UNIQUE"), "★★": (1000, "LEGENDARY"), "★★★": (10000, "MYTHIC")}
        for name, (rarity, tier) in known.items():
            if name in data and isinstance(data[name], dict):
                data[name]["rarity"] = rarity
                data[name]["is_exclusive"] = True
                data[name]["exclusive_biome"] = ["DREAMSPACE", 1]
                data[name]["native_biome"] = ["None", 1]
                data[name]["native_rarity"] = rarity
                data[name]["exclusive_biomes"] = ["DREAMSPACE"]
                data[name]["obtainment_type"] = "exclusive_unverified"
                data[name]["rarity_name"] = tier
                data[name]["obtainment"] = "Exclusive to DREAMSPACE (obtainment not verified)"
        return data

    @staticmethod
    def _old_repair_known_aura_metadata(data):
        # These fixed-rarity DREAMSPACE auras are listed in the Fandom
        # reference table but older local caches omitted their biome field.
        known = {
            "★": (100, "MYTHIC"),
            "★★": (1000, "MYTHIC"),
            "★★★": (10000, "MYTHIC"),
        }
        if isinstance(data, dict):
            for name, (rarity, tier) in known.items():
                if name in data and isinstance(data[name], dict):
                    data[name]["rarity"] = rarity
                    data[name]["native_biome"] = ["DREAMSPACE", 1]
                    data[name]["exclusive_biome"] = ["None", 1]
                    data[name]["rarity_name"] = tier
        return data

    def _parse_fandom_aura_page(self, wikitext, aura_name):
        """Parse one aura article ({{Aura Infobox}} + Profile section).

        The wiki distinguishes:
          - aura_rarity   -> global rolling chance (the index number)
          - native_rarity -> chance inside the required biome
          - rarity_name   -> wiki rarity class ({{Rarity|X}}), never number-derived
          - required      -> native/required biome
        Everything returned is clean human-readable text (no raw markup).
        """
        import re
        text = str(wikitext or "")

        def clean(value):
            v = re.sub(r"<gallery[^>]*>.*?</gallery>", " ", str(value or ""), flags=re.S | re.I)
            # HTML comments hide legacy/hidden chances (e.g. Glitched's
            # commented-out "1 in 366,303,300,000") - never parse them.
            v = re.sub(r"<!--.*?-->", " ", v, flags=re.S)
            v = re.sub(r"<ref[^>]*/>", "", v)
            v = re.sub(r"<ref[^>]*>.*?</ref>", "", v, flags=re.S)
            v = re.sub(r"\[\[File:[^\]]*\]\]", " ", v, flags=re.I)
            v = re.sub(r"\[\[Image:[^\]]*\]\]", " ", v, flags=re.I)
            v = re.sub(r"<[^>]+>", " ", v)
            v = re.sub(r"https?://\S+", "", v)
            v = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", v)
            v = re.sub(r"\[\[([^\]]+)\]\]", r"\1", v)
            v = re.sub(r"\{\{Rarity\|([^{}|]+)\}\}", r"\1", v)
            v = re.sub(r"\{\{Biome\|([^{}|]+)\}\}", r"\1", v)
            v = re.sub(r"\{\{Aura\|([^{}|]+)\}\}", r"\1", v)
            v = re.sub(r"\{\{User\|([^{}|]+)(?:\|[^{}]*)?\}\}", r"\1", v)
            v = re.sub(r"\{\{[^{}]*\}\}", " ", v)
            v = v.replace("'''", "").replace("''", "")
            return re.sub(r"\s+", " ", v).strip()

        def find_template(name):
            low = text.lower()
            begin = low.find("{{" + name.lower())
            if begin < 0:
                begin = low.find("{{" + name.lower().replace(" ", "_"))
            if begin < 0:
                return None
            depth = 0
            i = begin
            while i < len(text) - 1:
                token = text[i:i + 2]
                if token == "{{":
                    depth += 1; i += 2; continue
                if token == "}}":
                    depth -= 1; i += 2
                    if depth == 0:
                        return text[begin:i]
                    continue
                i += 1
            return None

        def protect_pipes(body):
            """Hide | separators inside [[wikilinks]] and <gallery> blocks so
            they are not mistaken for template parameter separators."""
            out = []
            i = 0
            low = body.lower()
            while i < len(body):
                if body[i:i + 2] == "[[":
                    j = body.find("]]", i)
                    if j < 0:
                        out.append(body[i:])
                        break
                    out.append(body[i:j + 2].replace("|", "\x00"))
                    i = j + 2
                    continue
                if low.startswith("<gallery", i):
                    j = low.find("</gallery>", i)
                    if j < 0:
                        out.append(body[i:])
                        break
                    out.append(body[i:j + 10].replace("|", "\x00"))
                    i = j + 10
                    continue
                out.append(body[i])
                i += 1
            return "".join(out)

        def split_params(body):
            body = protect_pipes(body)
            parts, current, depth, i = [], [], 0, 0
            while i < len(body):
                token = body[i:i + 2]
                if token == "{{":
                    depth += 1; current.append(token); i += 2; continue
                if token == "}}":
                    depth = max(0, depth - 1); current.append(token); i += 2; continue
                if body[i] == "|" and depth == 0:
                    parts.append("".join(current)); current = []; i += 1; continue
                current.append(body[i]); i += 1
            parts.append("".join(current))
            return [part.replace("\x00", "|") for part in parts]

        info = {}
        box = find_template("Aura Infobox")
        fields = {}
        if box:
            for part in split_params(box[2:-2]):
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key.strip().lower().replace(" ", "_")] = value.strip()
        else:
            for m in re.finditer(
                r"\|\s*(title1?|aura_rarity|native_rarity|rarity_name|required|native_biome)\s*=\s*([^\n|]+)",
                text[:6000], re.I,
            ):
                fields.setdefault(m.group(1).strip().lower(), m.group(2).strip())

        title = clean(fields.get("title1") or fields.get("title") or "")
        if title:
            info["name"] = title

        def parse_chance(value):
            v = clean(value)
            m = re.search(r"1\s*in\s*([\d,]+)", v, re.I)
            if m:
                return int(m.group(1).replace(",", ""))
            return None

        global_r = parse_chance(fields.get("aura_rarity", ""))
        native_r = parse_chance(fields.get("native_rarity", ""))
        aura_note = clean(fields.get("aura_rarity", ""))

        # Potion / item sources: "1 in 1000 from [[Red Moon Potions#Red_Moon_Potion_I|…]]".
        # Only segments naming an explicit source count as potion sources -
        # a bare "1 in 900" chance is a normal roll, not a craft.
        potion_sources = []
        for seg in re.split(r"<br>|<abbr", str(fields.get("aura_rarity", ""))):
            if ">" in seg:
                seg = seg.split(">", 1)[1]
            m_ch = re.search(r"1\s*in\s*([\d,]+)", seg, re.I)
            if not m_ch:
                continue
            m_src = re.search(r"from\s+\[\[([^\]|#]+)(?:#([^\]|]+))?", seg, re.I)
            if not m_src and not re.search(r"\{\{Items\|", seg, re.I):
                continue  # plain roll chance - keep out of potion_sources
            chance_n = int(m_ch.group(1).replace(",", ""))
            if m_src:
                src_name = (m_src.group(2) or m_src.group(1)).replace("_", " ").strip()
                src_name = re.sub(r"\s+", " ", src_name)
            else:
                m_it = re.search(r"\{\{Items\|([^|}]+)", seg)
                src_name = clean(m_it.group(1)) if m_it else ""
            potion_sources.append((chance_n, src_name))
        # "(Fixed)" chances belong to potions/crafts (Memory, Oblivion), not
        # rolls. The marker lives in the <abbr title="..."> attribute, which
        # clean() strips - match on the RAW field.
        fixed_chance = bool(re.search(r"\(\s*Fixed", str(fields.get("aura_rarity", "")), re.I))
        required_raw = fields.get("required") or fields.get("native_biome") or ""
        rarity_name = clean(fields.get("rarity_name", ""))
        if rarity_name and len(rarity_name) < 24:
            info["rarity_name"] = rarity_name

        info["global_rarity"] = global_r
        info["native_rarity"] = native_r
        if global_r is not None and ((potion_sources and all(src for _n, src in potion_sources)) or fixed_chance):
            info["rarity_is_potion"] = True
        # The advertised number: wiki's aura_rarity (index number); the native
        # chance is kept separately and surfaced in the UI next to it.
        info["rarity"] = global_r if global_r is not None else native_r

        required_biome = re.sub(r"\s+", " ", clean(required_raw)).upper().replace("SANDSTORM", "SAND STORM")
        exclusive = bool(re.search(r"\bN/A\b", aura_note, re.I)) or (global_r is None and native_r is not None)
        # Trust the catalogue: auras locked to one world (e.g. Limbo auras
        # like Anima) must not be described as obtainable "anywhere".
        try:
            auras_index = getattr(self, "auras_data", None)
            if isinstance(auras_index, dict) and auras_index:
                idx_key = str(aura_name or "").strip()
                idx_entry = auras_index.get(idx_key) or auras_index.get(idx_key.replace(" ", "_"))
                if isinstance(idx_entry, dict) and idx_entry.get("is_exclusive"):
                    exclusive = True
                    eb = idx_entry.get("exclusive_biome") or ["None", 1]
                    if eb[0] != "None" and (not required_biome or required_biome in ("NONE", "N/A", "")):
                        required_biome = str(eb[0])
        except Exception:
            pass
        if required_biome and required_biome not in ("NONE", "N/A", ""):
            if exclusive:
                info["is_exclusive"] = True
                info["exclusive_biome"] = [required_biome, 1]
                info["exclusive_biomes"] = [required_biome]
                info["native_biome"] = ["None", 1]
                info["obtainment_type"] = "exclusive"
            else:
                info["is_exclusive"] = False
                info["native_biome"] = [required_biome, (global_r / native_r) if (global_r and native_r) else 1]
                info["exclusive_biome"] = ["None", 1]
                info["obtainment_type"] = "native"
        elif exclusive:
            info["is_exclusive"] = True
            info["obtainment_type"] = "exclusive"

        profile = re.search(r"(?m)^=+\s*Profile\s*=+\s*\n(.*?)(?=\n=+\s*[^=\n]+\s*=+|\Z)", text, re.I | re.S)
        desc = clean(profile.group(1)) if profile else ""
        if desc:
            info["description"] = desc[:1200]

        if potion_sources or fixed_chance or "crafted" in aura_note.lower():
            info["potion_sources"] = [{"chance": n, "source": s} for n, s in potion_sources]
            if potion_sources:
                info["obtainment"] = " · ".join(
                    f"From {s} (1 in {n:,})" if s else f"1 in {n:,}"
                    for n, s in potion_sources
                )
            info["obtainment_type"] = "craftable"
            if global_r is not None and all(src for _n, src in potion_sources):
                # The stored number is the potion chance, not a roll chance.
                info["rarity_is_potion"] = True

        notice = find_template("Aura Notice")
        if notice:
            nparams = {}
            for part in split_params(notice[2:-2]):
                if "=" in part:
                    k, v = part.split("=", 1)
                    nparams[k.strip().lower()] = v.strip()
            reason = clean(nparams.get("reason", ""))
            date = clean(nparams.get("date", ""))
            ntype = clean(nparams.get("type", "")) or "Unobtainable"
            msg = f"{ntype} (since {date})" if date else ntype
            if reason:
                msg += f" — {reason}"
            info["obtainment"] = msg[:600]
            info["obtainment_type"] = info.get("obtainment_type") or "unobtainable"
        if not info.get("obtainment"):
            if exclusive and required_biome:
                chance = f"1 in {native_r:,}" if native_r else "N/A"
                info["obtainment"] = f"Exclusive to {required_biome} ({chance}); cannot be rolled via breakthrough elsewhere."
            elif global_r and native_r and required_biome:
                info["obtainment"] = f"1 in {global_r:,} anywhere (breakthrough) · 1 in {native_r:,} in {required_biome}."
            elif global_r and info.get("rarity_is_potion"):
                info["obtainment"] = f"1 in {global_r:,} (fixed chance - from a potion/craft, not a normal roll)."
            elif global_r:
                info["obtainment"] = f"1 in {global_r:,} (any biome, standard roll)."
            elif aura_note:
                info["obtainment"] = aura_note[:400]
        if info.get("obtainment"):
            info["obtainment"] = str(info["obtainment"])[:600]

        video_ext = (".mp4", ".webm", ".ogg", ".wav", ".mp3")
        gallery_files = [f.strip() for f in re.findall(r"\[\[File:([^|\]]+)", text)]
        collection = None
        for m3 in re.finditer(r"\[\[File:([^|\]]+)\|([^\]]*)\]\]", text):
            cap = (m3.group(2) or "").lower()
            name = m3.group(1).strip()
            if "collection" in cap or "collection" in name.lower():
                if not name.lower().endswith(video_ext):
                    collection = name
                    break
        if collection is None:
            for name in gallery_files:
                if not name.lower().endswith(video_ext):
                    collection = name
                    break

        # "Opening Cutscene" videos: [[File:DreamcatcherCutscene.mp4]] —
        # resolved via Special:FilePath (follows the wiki redirect to the CDN
        # static.wikia.nocookie.net URL, so the frontend can stream it).
        # The cutscene video is taken ONLY from the page's "Opening Cutscene"
        # section (or a cutscene/opening-named file) — never "the first video
        # on the page", which used to pick Ability-showcase videos and label
        # them as cutscenes.
        video_file = None
        cs_sec = re.search(
            r"(?m)^=+[^\n=]*?Opening Cutscene[^\n=]*?=+\s*\n(.*?)(?=\n=+[^\n=]+=+|\Z)",
            text, re.I | re.S,
        )
        if cs_sec:
            sec_text = cs_sec.group(1)
            cs_vid = re.search(r"\[\[File:([^|\]]+\.(?:mp4|webm|mov|ogv))(?:\|([^\]]*))?\]\]", sec_text, re.I)
            if cs_vid:
                video_file = cs_vid.group(1).strip()
            if video_file is None:
                cs_gif = re.search(r"\[\[File:([^|\]]+\.gif)(?:\|([^\]]*))?\]\]", sec_text, re.I)
                if cs_gif:
                    video_file = cs_gif.group(1).strip()
        if video_file is None:
            for m4 in re.finditer(r"\[\[File:([^|\]]+\.(?:mp4|webm))(?:\|([^\]]*))?\]\]", text, re.I):
                vname = m4.group(1).strip()
                vcap = (m4.group(2) or "").lower()
                if "cutscene" in vname.lower() or "cutscene" in vcap or "opening" in vcap:
                    video_file = vname
                    break
        # NOTE: deliberately NO "first video in the gallery" fallback — that
        # picked Ability videos. When no confirmed cutscene video exists,
        # video_url stays unset and the verified snapshot
        # (auras_fandom.json) fills it in via _merge_aura_media.
        if video_file:
            info["video_url"] = "https://sol-rng.fandom.com/wiki/Special:FilePath/" + video_file.replace(" ", "_")
            info["video_file"] = video_file
            info["video_kind"] = "opening"

        # Theme music: most special auras embed an audio file
        # ([[File:Treasures_Within_The_AbominationUPD.mp3|300px]]) — plain
        # commons usually have none. Resolved via Special:FilePath as well.
        for name in gallery_files:
            if name.lower().endswith((".ogg", ".oga", ".mp3", ".wav")):
                info["music_url"] = "https://sol-rng.fandom.com/wiki/Special:FilePath/" + name.replace(" ", "_")
                info["music_file"] = name
                break

        # Cutscene section text — the heading is often a wikilink:
        # "=== [[Opening Cutscenes|Opening Cutscene]] ===" (cs_sec was already
        # captured above for the video selection).
        if cs_sec:
            note = clean(cs_sec.group(1))
            if note and note.lower() != "none":
                info["cutscene_note"] = note[:400]

        urls = []
        if collection:
            urls.append("https://sol-rng.fandom.com/wiki/Special:FilePath/" + collection.replace(" ", "_"))
        for u in re.findall(r"https?://static\.wikia\.nocookie\.net/[^\s\)\]\|]+", text):
            # Raw video URLs belong to the player, not the image gallery.
            # Only used when the page has NO Opening Cutscene section at all,
            # so an Ability clip can never pose as a cutscene.
            if re.search(r"\.(?:mp4|webm|ogg|mov)(?:\?|$)", u, re.I):
                if not info.get("video_url") and cs_sec is None:
                    info["video_url"] = u
                continue
            if u not in urls:
                urls.append(u)
        if urls:
            info["image_urls"] = urls[:8]
        info["fandom_page"] = "https://sol-rng.fandom.com/wiki/" + str(aura_name or "").replace("_", " ").replace(" ", "_")
        info["_metadata_source"] = "fandom_article"
        info["_metadata_quality"] = "verified_article_fields"
        return info

    def load_fandom_aura_detail(self, aura_name):
        from urllib.parse import quote
        name = str(aura_name or "").strip()
        if not name: return {}
        spaced = name.replace("_", " ")
        page_names = [spaced]
        if "_" in name:
            page_names.append(name.replace("_", " : "))
        # Known title overrides discovered by the media audit (e.g. the aura
        # "Breakthrough" lives on "Breakthrough (Aura)") — stored in
        # auras_fandom.json as `_fandom_title`.
        try:
            override = ""
            src = getattr(self, "auras_data", None)
            if not isinstance(src, dict) or not src:
                try:
                    src = self._get_default_auras_data()
                except Exception:
                    src = {}
            entry = (src or {}).get(name) or {}
            override = str(entry.get("_fandom_title") or "").strip()
            if override and override not in page_names:
                page_names.insert(0, override)
        except Exception:
            pass
        detail_cache = getattr(self, "_fandom_aura_detail_cache", None)
        if not isinstance(detail_cache, dict):
            detail_cache = {}
        cached = detail_cache.get(name)
        if isinstance(cached, dict) and cached and not cached.get("error"):
            return cached
        last_error = "Fandom aura page unavailable"
        for page_name in dict.fromkeys(page_names):
            url = "https://sol-rng.fandom.com/api.php?action=parse&page=" + quote(page_name) + "&prop=wikitext&format=json"
            try:
                response = fandom_get(url, timeout=20)
                if response is None or not response.ok:
                    continue
                raw = response.json()
                wikitext = (((raw.get("parse") or {}).get("wikitext") or {}).get("*") if isinstance(raw, dict) else "")
                data = self._parse_fandom_aura_page(wikitext, name)
                try:
                    # Point the wiki link at the page that was ACTUALLY used
                    # (title overrides like "Breakthrough (Aura)").
                    data["fandom_page"] = "https://sol-rng.fandom.com/wiki/" + page_name.replace(" ", "_")
                except Exception:
                    pass
                if data.get("rarity") is not None or data.get("is_exclusive") or data.get("native_rarity") is not None:
                    detail_cache[name] = data
                    self._fandom_aura_detail_cache = detail_cache
                    return data
                last_error = "Fandom aura page has no parseable Information table"
            except Exception:
                last_error = "Fandom aura page could not be parsed"
        return {"error": last_error}

    def load_fandom_biome_detail(self, biome_name):
        """Collect a biome's real wiki images as a gallery (like THE LIMBO).

        The wiki has NO per-biome pages — every biome lives on the big
        "Biomes" page. Its layout is consistent (verified against the live
        page): a biome's images sit in the zone right BEFORE its
        ==={{Biome|X}}=== heading (the same rule the thumbnail parser uses),
        and the biome's own theme music is embedded inside its section body.
        """
        name = str(biome_name or "").strip()
        if not name:
            return {"error": "Empty biome name"}
        src = getattr(self, "biome_data", None)
        if not isinstance(src, dict) or not src:
            try:
                src = self.load_biome_data() or {}
            except Exception:
                src = {}
        entry = dict((src or {}).get(name) or {})
        cache = getattr(self, "_fandom_biome_detail_cache", None)
        if not isinstance(cache, dict):
            cache = {}
        if name in cache:
            return cache[name]
        text = self._get_fandom_biomes_wikitext()
        if not text:
            return {"error": "Fandom Biomes page unavailable"}

        pattern = re.compile(r"(?m)^=+\s*([^=].*?)\s*=+\s*$")
        matches = list(pattern.finditer(text))
        heads = [(m.group(1).strip(), m.start(), m.end()) for m in matches]

        def _canon(s):
            return re.sub(r"[^a-z0-9]", "", str(s or "").lower())

        def _heading_biome(raw):
            if "{{Biome" not in raw:
                return None
            inner = raw.replace("{{", "").replace("}}", "")
            parts = [p.strip() for p in inner.split("|") if p.strip()]
            if len(parts) >= 2 and parts[0].lower() == "biome":
                return parts[1]
            return parts[0] if parts else None

        target = _canon(name)
        if not target:
            return {"error": "Biome name is not matchable"}
        idx = None
        for i, (raw_head, _s, _e) in enumerate(heads):
            bn = _heading_biome(raw_head)
            if bn and _canon(bn) and _canon(bn) == target:
                idx = i
                break
        if idx is None:
            # NORMAL has no {{Biome|...}} template on the wiki — its section
            # is a plain "Normal" heading. TIME is hidden and never requested.
            if target == "normal":
                for i, (raw_head, _s, _e) in enumerate(heads):
                    if "{{Biome" not in raw_head and _canon(raw_head) == "normal":
                        idx = i
                        break
        if idx is None:
            return {"error": "Biome section not found on the Fandom Biomes page"}

        # Images live right before the heading; limit the look-back window so
        # the previous biome's body text stays out of the gallery.
        prev_end = heads[idx - 1][2] if idx > 0 else 0
        zone = text[max(prev_end, heads[idx][1] - 2600):heads[idx][1]]
        # The biome's own theme music sits inside its section body.
        next_start = heads[idx + 1][1] if idx + 1 < len(heads) else len(text)
        body = text[heads[idx][2]:next_start]

        gallery, seen = [], set()

        def _add(raw_file, caption=""):
            base = str(raw_file or "").split("|")[0].strip()
            if not base or base.lower() in seen:
                return
            # Galleries are images only; audio/video handled separately.
            if re.search(r"\.(?:mp4|webm|mov|ogv|ogg|oga|mp3|wav)(?:\?|$)", base, re.I):
                return
            seen.add(base.lower())
            human = re.sub(r"\.[a-z0-9]+$", "", base, flags=re.I)
            human = re.sub(r"[_\-]+", " ", human)
            human = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", human).strip()
            gallery.append({
                "url": self._FANDOM_WIKI_URL + "Special:FilePath/" + base.replace(" ", "_"),
                "file": base,
                "caption": (caption or "").strip() or (human[:80] if human else base),
            })

        for m in re.finditer(r"\[\[File:([^\]\]]+)\]\]", zone):
            _add(m.group(1))

        if not entry.get("music_url"):
            m_audio = re.search(r"\[\[File:([^\]\]]+\.(?:ogg|oga|mp3|wav))", body, re.I)
            if m_audio:
                audio = m_audio.group(1).strip()
                entry["music_url"] = self._FANDOM_WIKI_URL + "Special:FilePath/" + audio.replace(" ", "_")
                entry["music_file"] = audio

        entry["gallery"] = gallery[:8]
        entry["_metadata_source"] = "fandom_article"
        if not entry.get("fandom_page"):
            entry["fandom_page"] = self._FANDOM_WIKI_URL + "Biomes"
        cache[name] = entry
        self._fandom_biome_detail_cache = cache
        return entry

    def _get_fandom_biomes_wikitext(self):
        """Raw wikitext of the Biomes page, fetched once per session."""
        text = getattr(self, "_fandom_biomes_wikitext_cache", "")
        if text:
            return text
        try:
            response = fandom_get(
                "https://sol-rng.fandom.com/api.php?action=parse&page=Biomes&prop=wikitext&format=json",
                timeout=30,
            )
            if response is None or not response.ok:
                return ""
            raw = response.json()
            text = (((raw.get("parse") or {}).get("wikitext") or {}).get("*")
                    if isinstance(raw, dict) else "") or ""
            if text:
                self._fandom_biomes_wikitext_cache = text
            return text
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Fandom Biomes page parser (prose format: ==={{Biome|X}}=== sections)
    # ------------------------------------------------------------------
    _FANDOM_WIKI_URL = "https://sol-rng.fandom.com/wiki/"

    _BIOME_NAME_OVERRIDES = {
        "Sandstorm": "SAND STORM",
        "Pumpkin Moon": "PUMPKIN MOON",
        "Blazing Sun": "BLAZING SUN",
        "Blood Rain": "BLOOD RAIN",
        "The Hyperspace Realm": "THE HYPERSPACE REALM",
        "The Null's Existence": "THE NULL'S EXISTENCE",
        "The Citadel Of Orders": "THE CITADEL OF ORDERS",
    }

    _BIOME_CATEGORY_SETS = {
        "admin": {"THE NULL'S EXISTENCE", "THE HYPERSPACE REALM", "赤い満月", "THE CITADEL OF ORDERS"},
        "rare": {"GLITCHED", "DREAMSPACE", "CYBERSPACE", "SINGULARITY"},
        "event": {"AURORA", "EGGLAND", "INCINERATOR", "BLAZING SUN", "PUMPKIN MOON", "GRAVEYARD", "BLOOD RAIN"},
    }

    @classmethod
    def _biome_canonical_name(cls, raw):
        raw = (raw or "").strip()
        if raw in cls._BIOME_NAME_OVERRIDES:
            return cls._BIOME_NAME_OVERRIDES[raw]
        return re.sub(r"\s+", " ", raw).upper()

    @classmethod
    def _biome_category_for(cls, canonical):
        for cat, names in cls._BIOME_CATEGORY_SETS.items():
            if canonical in names:
                return cat
        return "weather"

    @staticmethod
    def _biome_clean_text(value):
        v = re.sub(r"<gallery[^>]*>.*?</gallery>", " ", value or "", flags=re.S | re.I)
        v = re.sub(r"<ref[^>]*/>", "", v)
        v = re.sub(r"<ref[^>]*>.*?</ref>", "", v, flags=re.S)
        v = re.sub(r"\[\[File:[^\]]*\]\]", " ", v, flags=re.I)
        v = re.sub(r"\[\[Image:[^\]]*\]\]", " ", v, flags=re.I)
        v = re.sub(r"<[^>]+>", "", v)
        v = re.sub(r"https?://\S+", "", v)
        v = re.sub(r"\[\[([^\]|]*\|)?([^\]]+)\]\]", r"\2", v)
        v = re.sub(r"\{\{[^|{}]+\|([^{}]+)\}\}", r"\1", v)
        v = re.sub(r"\{\{Biome\|([^{}|]+)\}\}", r"\1", v)
        v = re.sub(r"\{\{Aura\|([^{}|]+)\}\}", r"\1", v)
        v = re.sub(r"\{\{Items\|([^{}|]+)\}\}", r"\1", v)
        v = re.sub(r"\{\{[^{}]*\}\}", "", v)
        v = v.replace("'''", "").replace("''", "")
        return re.sub(r"\s+", " ", v).strip()

    def _parse_fandom_biomes_page(self, wikitext):
        """Parse the live Biomes page (heading + prose format).

        Each biome is a ==={{Biome|Name}}=== section with the chat color,
        spawn rate, duration, Breakthrough Multiplier, description and the
        full list of native/limited auras with exact chances.
        """
        text = str(wikitext or "")
        results = {}
        pattern = re.compile(r"(?m)^=+\s*([^=].*?)\s*=+\s*$")
        matches = list(pattern.finditer(text))
        sections = []
        for i, mm in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            sections.append((mm.group(1).strip(), text[mm.end():end]))

        def extract_heading_name(raw):
            if "{{Biome" in raw:
                inner = raw.replace("{{", "").replace("}}", "").strip()
                parts = [p.strip() for p in inner.split("|") if p.strip()]
                if len(parts) >= 2 and parts[0].lower() == "biome":
                    return parts[1]
                if parts:
                    return parts[0]
            return raw

        def is_biome_heading(raw):
            return raw in ("Normal", "Time") or "{{Biome" in raw

        def parse_number(s):
            return int(s.replace(",", ""))

        def parse_section(name_canon, body, image_tail):
            entry = {
                "name": name_canon,
                "color": "",
                "chat_message": "",
                "category": self._biome_category_for(name_canon),
                "spawn_chance": "",
                "duration": "",
                "how_to_get": "",
                "description": "",
                "breakthrough_multiplier": None,
                "native_auras": [],
                "image_file": "",
                "fandom_page": self._FANDOM_WIKI_URL + name_canon.replace(" ", "_"),
            }
            chat = re.search(r'<font[^>]*color="#([0-9a-fA-F]{6})"[^>]*>\s*\[([^\]]+)\]:\s*(.*?)</font>', body, re.S)
            if chat:
                entry["color"] = "#" + chat.group(1).upper()
                entry["chat_message"] = self._biome_clean_text(chat.group(3))
            else:
                span = re.search(r"color[:=]\s*#([0-9a-fA-F]{6})", body[:350])
                if span:
                    entry["color"] = "#" + span.group(1).upper()

            imgs = re.findall(r"\[\[File:([^|\]]+)", image_tail)
            if imgs:
                entry["image_file"] = imgs[-1].strip()
                entry["thumbnail_url"] = self._FANDOM_WIKI_URL + "Special:FilePath/" + entry["image_file"].replace(" ", "_")

            def mechanics_sentence():
                idx = -1
                for kw in ("spawn rate of", "summoned by using", "replaces the normal", "spawn"):
                    idx = body.lower().find(kw)
                    if idx >= 0:
                        break
                if idx < 0:
                    return ""
                start = body.rfind("{{Biome", 0, idx)
                if start < 0:
                    start = body.rfind(". ", 0, idx) + 2
                end = body.find(".", idx)
                if end < 0:
                    end = min(len(body), idx + 400)
                return self._biome_clean_text(body[start:end + 1])

            m = re.search(r"spawn rate of 1 in ([\d,]+)/s", body, re.I)
            if m:
                entry["spawn_chance"] = f"1 in {m.group(1)}/s"
            else:
                m = re.search(r"1 in ([\d,]+)/s", body)
                if m:
                    entry["spawn_chance"] = f"1 in {m.group(1)}/s"
                else:
                    m = re.search(r"chance of 1 in ([\d,]+)\s*(\(?[^.,)]*(?:second|/s)[^.,)]*)?", body, re.I)
                    if m and m.group(1):
                        suffix = ""
                        ctx = (m.group(2) or "").lower()
                        if "second" in ctx or ctx == "/s":
                            suffix = "/s"
                        entry["spawn_chance"] = f"1 in {m.group(1)}{suffix}"
                    else:
                        m = re.search(r"1/([\d,]+) \([^)]*\) chance to appear", body, re.I)
                        if m:
                            entry["spawn_chance"] = f"1/{m.group(1)} (via Strange Controller / Biome Randomizer)"
                        else:
                            m = re.search(r"1/([\d,]+) \([^)]*\) chance to replace", body, re.I)
                            if m:
                                entry["spawn_chance"] = f"1/{m.group(1)} to replace STARFALL"
                            else:
                                m = re.search(r"1 in (\d+) \(\d+%\) chance of spawning", body, re.I)
                                if m:
                                    entry["spawn_chance"] = f"1 in {m.group(1)} per Daytime transition"
                                else:
                                    m = re.search(r"spawn(?:s)? at a 1/([\d,]+)", body, re.I)
                                    if m:
                                        entry["spawn_chance"] = f"1/{m.group(1)} (can spawn after Event Turret)"
            if name_canon in self._BIOME_CATEGORY_SETS["admin"] and not entry["spawn_chance"]:
                entry["spawn_chance"] = "Admin-only"
            if name_canon == "NORMAL" and not entry["spawn_chance"]:
                entry["spawn_chance"] = "Default biome (always available)"
            if name_canon == "TIME" and not entry["spawn_chance"]:
                entry["spawn_chance"] = "Passive — cycles between Daytime and Nighttime"
            if not entry["spawn_chance"]:
                mech = mechanics_sentence()
                if mech:
                    entry["spawn_chance"] = mech[:260]

            def trim_duration(t):
                for cut_kw in (" and is summoned", " and is", " and can", " and will", " which is", ", the ", ", then "):
                    i = t.find(cut_kw)
                    if i > 0:
                        t = t[:i]
                return t.strip()

            m = re.search(r"duration of ([^.]+)", body, re.I)
            if m:
                entry["duration"] = trim_duration(self._biome_clean_text(m.group(1)))
            else:
                m = re.search(r"lasting for ([^.,]+)", body, re.I)
                if m:
                    entry["duration"] = trim_duration(self._biome_clean_text(m.group(1)))
                else:
                    m = re.search(r"lasts for ([^.]+)", body, re.I)
                    if m:
                        entry["duration"] = trim_duration(self._biome_clean_text(m.group(1)))
                    else:
                        m = re.search(r"lasts until ([^.,]+)", body, re.I)
                        if m:
                            entry["duration"] = "Until " + self._biome_clean_text(m.group(1))
            if name_canon in self._BIOME_CATEGORY_SETS["admin"] and not entry["duration"]:
                entry["duration"] = "Admin-controlled"
            if name_canon == "TIME" and not entry["duration"]:
                entry["duration"] = "Passive"

            m = re.search(r"Breakthrough Multiplier of (\d+)x", body, re.I)
            if m:
                entry["breakthrough_multiplier"] = int(m.group(1))

            # Theme song of the biome: [[File:Analysis.mp3]] style links live
            # in the section body (usually right after "The song used ...").
            for _song in re.findall(r"\[\[File:([^\]|]+\.(?:ogg|oga|mp3|wav))", body, re.I):
                _song = _song.strip()
                entry["music_file"] = _song
                entry["music_url"] = self._FANDOM_WIKI_URL + "Special:FilePath/" + _song.replace(" ", "_")
                break

            prose = re.split(r"(?:\n\*|It also spawns|The song used|Limited Auras)", body)[0]
            # The chat line "<font ...>[Starfall]: ...</font>" must never leak
            # into the description/how_to_get text.
            prose = re.sub(r"<font[^>]*>.*?</font>", " ", prose, flags=re.S)
            prose = self._biome_clean_text(prose)
            # Defensive: strip any residual in-game chat prefix "[Name]:".
            prose = re.sub(r"\[[^\]\[]{1,40}\]:", " ", prose)
            if entry["chat_message"]:
                prose = prose.replace(entry["chat_message"], "").strip(" .:-")
            entry["description"] = prose
            if entry["description"]:
                first = re.split(r"(?<=[.!?])\s", entry["description"])[0]
                entry["how_to_get"] = first[:220]

            in_limited = False
            for line in body.splitlines():
                stripped = line.strip()
                if re.match(r"'''(?:\d+\s+)?Limited Auras'''", stripped):
                    in_limited = True
                    continue
                if re.match(r"^=+", stripped):
                    in_limited = False
                if not re.match(r"^\s*\*+\s*\[\[", line):
                    continue
                link = re.match(r"^\s*\*+\s*\[\[([^\]|]+)\|", line)
                if not link:
                    continue
                aura = link.group(1).strip()
                nums = re.findall(r"1\s*/\s*([\d,]+)", line)
                if not nums:
                    nums = re.findall(r"1 in ([\d,]+)", line, re.I)
                exclusive_only = bool(re.search(r"cannot be (?:rolled|obtained) through", line, re.I)) \
                    or bool(re.search(r"with no \[BREAKTHROUGH\]", line, re.I))
                limited_now = in_limited or bool(re.search(r"(?i)only obtainable during", body[line.find(aura): line.find(aura) + 600]))
                native_r = parse_number(nums[0]) if nums else None
                breakthrough_r = parse_number(nums[1]) if (len(nums) > 1 and not exclusive_only) else None
                if native_r is None:
                    native_r = parse_number(nums[-1]) if nums else None
                entry["native_auras"].append({
                    "name": aura,
                    "native_rarity": native_r,
                    "breakthrough_rarity": breakthrough_r,
                    "exclusive_only": exclusive_only,
                    "limited": limited_now,
                })
            return entry

        for i, (raw_head, body) in enumerate(sections):
            if not is_biome_heading(raw_head):
                continue
            name = self._biome_canonical_name(extract_heading_name(raw_head))
            tail = sections[i - 1][1][-600:] if i > 0 else ""
            parsed = parse_section(name, body, tail)
            if name in results:
                first = results[name]
                for key in ("color", "chat_message", "spawn_chance", "duration", "breakthrough_multiplier"):
                    if not first.get(key) and parsed.get(key):
                        first[key] = parsed[key]
                have = {a["name"] for a in first["native_auras"]}
                for a in parsed["native_auras"]:
                    if a["name"] not in have:
                        first["native_auras"].append(a)
                if not first.get("image_file") and parsed.get("image_file"):
                    first["image_file"] = parsed["image_file"]
                    first["thumbnail_url"] = parsed.get("thumbnail_url", "")
                first["description"] = (first.get("description", "") + " " + parsed.get("description", "")).strip()
            else:
                results[name] = parsed

        # second pass: biomes whose image sits before an earlier non-biome heading
        for i, (raw_head, _body) in enumerate(sections):
            if not is_biome_heading(raw_head):
                continue
            name = self._biome_canonical_name(extract_heading_name(raw_head))
            if not results.get(name, {}).get("image_file"):
                for j in range(i - 1, -1, -1):
                    if is_biome_heading(sections[j][0]):
                        break
                    tail = sections[j][1][-600:]
                    imgs = re.findall(r"\[\[File:([^|\]]+)", tail)
                    if imgs:
                        results[name]["image_file"] = imgs[-1].strip()
                        results[name]["thumbnail_url"] = self._FANDOM_WIKI_URL + "Special:FilePath/" + imgs[-1].strip().replace(" ", "_")
                        break
        # TIME is a passive day/night cycle, not a detectable biome — never
        # surface it in biome lists, stats, or webhooks.
        if "TIME" in results:
            results["TIME"]["hidden"] = True
        return results

    def _enrich_auras_from_biomes(self, auras, biome_data):
        """Fill native/exclusive biome links for auras from the Biomes page."""
        if not isinstance(auras, dict) or not isinstance(biome_data, dict):
            return 0

        def norm_key(name):
            key = re.sub(r"\s*:\s*", "_", (name or "").strip())
            key = key.replace(" ", "_")
            return re.sub(r"_+", "_", key)

        enriched = 0
        for biome_name, biome in biome_data.items():
            for a in biome.get("native_auras", []):
                e = auras.get(norm_key(a["name"]))
                if e is None:
                    continue
                mult = 1
                if e.get("rarity") and a.get("native_rarity"):
                    mult = max(1, round(e["rarity"] / a["native_rarity"]))
                if a["exclusive_only"]:
                    if e.get("exclusive_biome", ["None", 1])[0] == "None":
                        e["exclusive_biome"] = [biome_name, a["native_rarity"] or 1]
                    e.setdefault("exclusive_biomes", [])
                    if biome_name not in e["exclusive_biomes"]:
                        e["exclusive_biomes"].append(biome_name)
                else:
                    if a.get("breakthrough_rarity") and a.get("native_rarity"):
                        mult = max(1, round(a["breakthrough_rarity"] / a["native_rarity"]))
                    e["native_biome"] = [biome_name, a["native_rarity"] or 1]
                    if a.get("native_rarity"):
                        e["native_rarity"] = a["native_rarity"]
                    e.setdefault("native_from_biomes", [])
                    if biome_name not in e["native_from_biomes"]:
                        e["native_from_biomes"].append(biome_name)
                if a["limited"]:
                    e["limited"] = True
                e["is_exclusive"] = bool(a["exclusive_only"]) or (e.get("exclusive_biome", ["None", 1])[0] != "None")
                enriched += 1

        # Derive human-readable obtainment + rarity tier from the verified links.
        tier_map = [
            (2, "Common"), (16, "Basic"), (999, "Uncommon"), (9999, "Epic"),
            (39999, "Legendary"), (99999, "Unique"), (999999, "Mythic"),
            (50_000_000, "Exalted"), (999_999_999, "Transcendent"),
        ]
        for e in auras.values():
            if not e.get("obtainment"):
                native = e.get("native_biome") or ["None", 1]
                exclusive = e.get("exclusive_biome") or ["None", 1]
                flags = e.get("flags") or []
                if native[0] != "None":
                    e["obtainment"] = f"Native to {native[0]} (1/{native[1]:,})"
                    e["obtainment_type"] = "native"
                elif exclusive[0] != "None":
                    e["obtainment"] = f"Exclusive to {exclusive[0]} (cannot be rolled through breakthrough)"
                    e["obtainment_type"] = "exclusive"
                elif "craftable" in flags:
                    e["obtainment"] = "Craftable (recipe at the Workshop)"
                    e["obtainment_type"] = "craftable"
                elif "limited" in flags:
                    e["obtainment"] = "Limited event aura (currently unavailable)"
                    e["obtainment_type"] = "limited"
                else:
                    e["obtainment"] = "Any biome (standard roll)"
                    e["obtainment_type"] = "standard"
            if not e.get("rarity_name") and e.get("rarity"):
                for cap, label in tier_map:
                    if e["rarity"] <= cap:
                        e["rarity_name"] = label
                        break
        return enriched

    def _parse_fandom_auras(self, wikitext):
        """Parse nested Aura Box templates without relying on parameter order.

        Includes Limited / Craftable / Unobtainable / Dev-Exclusive auras
        (flagged instead of dropped) so the catalogue has no gaps.
        """
        import re

        def blocks(text, wanted):
            out = []
            pos = 0
            needle = "{{" + wanted.lower()
            while pos < len(text):
                begin = text.lower().find(needle, pos)
                if begin < 0:
                    break
                depth = 0
                i = begin
                end = None
                while i < len(text) - 1:
                    token = text[i:i + 2]
                    if token == "{{":
                        depth += 1; i += 2; continue
                    if token == "}}":
                        depth -= 1; i += 2
                        if depth == 0:
                            end = i; break
                        continue
                    i += 1
                if end is None:
                    break
                out.append(text[begin:end])
                pos = end
            return out

        def split_top_level(body):
            parts, current, depth, i = [], [], 0, 0
            while i < len(body):
                token = body[i:i + 2]
                if token == "{{":
                    depth += 1; current.append(token); i += 2; continue
                if token == "}}":
                    depth = max(0, depth - 1); current.append(token); i += 2; continue
                if body[i] == "|" and depth == 0:
                    parts.append("".join(current)); current = []; i += 1; continue
                current.append(body[i]); i += 1
            parts.append("".join(current))
            return parts

        def clean(value):
            value = re.sub(r"<[^>]+>", "", str(value or ""))
            value = re.sub(r"\[\[([^\]|]+\|)?([^\]]+)\]\]", r"\2", value)
            value = re.sub(r"\{\{[^|{}]+\|([^{}]+)\}\}", r"\1", value)
            return re.sub(r"\s+", " ", value).strip()

        def normalize_name(name):
            name = clean(name)
            if not name.startswith(":"):
                name = re.sub(r"\s*:\s*", "_", name)
            name = name.replace(" ", "_")
            return re.sub(r"_+", "_", name)

        # Track ==={{Rarity|X}} Auras=== sections so every aura inherits the
        # wiki's own rarity class instead of a number-derived guess.
        wiki_text = str(wikitext or "")
        section_ranges = []
        for m in re.finditer(r"(?m)^=+\s*([^=].*?)\s*=+\s*$", wiki_text):
            head = m.group(1).strip()
            if "Auras" not in head:
                continue
            cls = None
            cm = re.search(r"\{\{Rarity\|([^{}|]+)\}\}", head)
            if cm:
                cls = cm.group(1).strip()
            lowered = head.lower()
            if cls is None and "craftable" in lowered:
                cls = None  # craftable flag, no class
            section_ranges.append((m.start(), m.end(), cls, head))

        def section_for(pos):
            cls, head = None, ""
            for s, e, c, h in section_ranges:
                if s <= pos:
                    cls, head = c, h
                else:
                    break
            return cls, head

        results = {}
        block_cursor = 0
        for block in blocks(wiki_text, "Aura Box"):
            block_start = wiki_text.find(block, block_cursor)
            if block_start >= 0:
                block_cursor = block_start + 1
            sec_cls, sec_head = section_for(block_start if block_start >= 0 else 0)
            fields = {}
            raw_fields = {}
            for part in split_top_level(block[2:-2]):
                if "=" in part:
                    key, value = part.split("=", 1)
                    fields[key.strip().lower()] = clean(value)
                    raw_fields[key.strip().lower()] = value.strip()
            aura_name = fields.get("aura") or fields.get("name") or fields.get("title")
            chance = fields.get("chance", "")
            if not aura_name:
                continue
            if "{{" in aura_name:  # broken nested-template artifact
                continue
            combined = f"{chance} {fields.get('obtainment', '')}".strip()
            lowered = combined.lower()

            rarity_match = re.search(r"1\s*/\s*([\d,]+)", combined)
            rarity = int(rarity_match.group(1).replace(",", "")) if rarity_match else None
            unobtainable = "unobtainable" in lowered
            dev_exclusive = "dev-exclusive" in lowered or "dev exclusive" in lowered
            removed = "removed" in lowered
            unreleased = "unreleased" in lowered
            limited = "limited" in lowered
            craftable = bool(re.search(r"\(craftable\)", lowered)) or "crafted" in lowered \
                or "workshop" in lowered or "potion" in lowered
            if rarity is None and not (craftable or limited or unobtainable or dev_exclusive or removed or unreleased):
                continue

            biome_match = re.search(r"\{\{Biome\s*\|\s*([^}|]+)", combined, re.I)
            biome_raw = clean(biome_match.group(1)) if biome_match else clean(fields.get("biome"))
            only_in = "only in" in lowered
            # "(in X)" with a single chance number = the aura is locked to
            # that world (e.g. Limbo auras like Anima): no outside rolling.
            paren = re.search(r"\(([^)]*)\)", combined)
            paren_text = clean(paren.group(1)).lower() if paren else ""
            if not biome_raw and paren_text:
                m_b = re.match(r"^(?:only\s+in|in)\s+(.+)$", paren_text)
                if m_b:
                    biome_raw = m_b.group(1).strip()
            locked_only = bool(biome_raw) and bool(re.match(r"^(only\s+in|in)\b", paren_text))
            native = not (only_in or locked_only) and not any(word in lowered for word in ("exclusive", "cannot be"))
            multiplier = 1
            native_rarity = re.search(r"1\s*/\s*([\d,]+)\s+in", combined)
            if native and native_rarity and rarity:
                nr = int(native_rarity.group(1).replace(",", ""))
                multiplier = max(1, round(rarity / nr)) if nr else 1
            if fields.get("multiplier"):
                try: multiplier = float(fields["multiplier"])
                except ValueError: pass

            biome = biome_raw.upper().replace("SANDSTORM", "SAND STORM") if biome_raw else None
            obtainment = clean(fields.get("obtainment", "")) or None
            if not obtainment:
                if unobtainable:
                    obtainment = "Unobtainable (dev/tester only)"
                elif dev_exclusive:
                    obtainment = "Dev-exclusive"
                elif limited:
                    obtainment = "Limited (" + clean(chance) + ")"
                elif craftable and rarity is not None:
                    raw_ch = str(raw_fields.get("chance", ""))
                    p_names = re.findall(r"\{\{Items\|([^|}]+)", raw_ch)
                    p_nums = re.findall(r"1/([\d,]+)", raw_ch)
                    pairs = []
                    for i2, num in enumerate(p_nums):
                        name = clean(p_names[i2]) if i2 < len(p_names) else ""
                        pairs.append((name, int(num.replace(",", ""))))
                    if pairs:
                        obtainment = " · ".join(
                            f"From {n} (1 in {v:,})" if n else f"1 in {v:,}"
                            for n, v in pairs
                        )
                    else:
                        crafted = re.search(r"(Crafted at[^|;]+)", combined, re.I)
                        obtainment = clean(crafted.group(1)) if crafted else "Craftable (recipe at the Workshop)"
                elif craftable:
                    crafted = re.search(r"(Crafted at[^|;]+)", combined, re.I)
                    obtainment = clean(crafted.group(1)) if crafted else "Craftable (recipe at the Workshop)"
            key = normalize_name(aura_name)
            entry = {
                "rarity": rarity,
                "exclusive_biome": [biome, multiplier] if biome and not native else ["None", 1],
                "native_biome": [biome, multiplier] if biome and native else ["None", 1],
                "limited": limited or "limited" in lowered,
                "obtainment": obtainment,
                "rarity_name": clean(fields.get("rarity_name", "")) or None,
                "description": clean(fields.get("description", "")),
                "flags": [f for f, on in (
                    ("unobtainable", unobtainable),
                    ("dev_exclusive", dev_exclusive),
                    ("removed", removed),
                    ("unreleased", unreleased),
                    ("limited", limited),
                    ("craftable", craftable),
                ) if on],
                "_metadata_source": "fandom",
            }
            # Inherit the wiki rarity class from the section heading.
            if sec_cls and not entry.get("rarity_name"):
                entry["rarity_name"] = sec_cls
            low_head = (sec_head or "").lower()
            flags = entry.setdefault("flags", [])
            if "craftable" in low_head and "craftable" not in flags:
                flags.append("craftable")
            if ("event" in low_head and sec_cls is None) and "limited" not in flags:
                flags.append("limited")
                entry["limited"] = True
            if ("dev exclusive" in low_head or "unobtainable" in low_head):
                for flag in ("dev_exclusive", "unobtainable"):
                    if flag not in flags:
                        flags.append(flag)
            if "removed" in low_head and "removed" not in flags:
                flags.append("removed")
            if locked_only and biome and entry["exclusive_biome"][0] == "None":
                entry["exclusive_biome"] = [biome, 1]
            box_image = clean(fields.get("image", ""))
            if box_image:
                entry["image_collection_url"] = "https://sol-rng.fandom.com/wiki/Special:FilePath/" + box_image.replace(" ", "_")
            results[key] = entry
        return results

    def _get_default_auras_data(self):
        """Bundled Fandom snapshot fallback (real wiki data captured offline)."""
        path = os.path.join(os.path.dirname(__file__), "auras_fandom.json")
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and data:
                for item in data.values():
                    if isinstance(item, dict):
                        item.setdefault("_metadata_source", "fandom_snapshot")
                return data
        except Exception as exc:
            print(f"Could not load bundled Fandom aura snapshot: {exc}")
        return {}

    def check_aura_in_logs(self, log_file_path):
        try:
            if self.reconnecting_state: return

            if not hasattr(self, 'last_aura_found'):
                self.last_aura_found = None
                
            if not hasattr(self, 'auras_data') or not self.auras_data:
                self.auras_data = self.load_auras_json()
                if hasattr(self, '_auras_data_lower_map'):
                    delattr(self, '_auras_data_lower_map')

            # Self-heal (v1.0.6 behavior, throttled to once per 60s): a full
            # reverse scan of the log guarantees that no equip line can be
            # permanently missed. Announcing is idempotent - it only fires
            # when the latest equipped aura differs from last_aura_found -
            # so the rescan cannot double-announce what the incremental
            # read already saw.
            log_lines = None
            now_ts = time.time()
            if now_ts - float(getattr(self, "_aura_last_full_rescan_ts", 0.0) or 0.0) >= 60.0:
                self._aura_last_full_rescan_ts = now_ts
                try:
                    log_lines = self.read_full_log_file(log_file_path)
                except Exception:
                    log_lines = None
            if log_lines is None:
                log_lines = self.read_log_file_for_detector(log_file_path, pos_attr='last_position_aura', filter_chat=True)

            for line in reversed(log_lines):
                try:
                    match = re.search(r'"state":"Equipped \\"(.*?)\\"', line)
                    if match:
                        aura = match.group(1)
                        if not hasattr(self, "_auras_data_lower_map"):
                            self._auras_data_lower_map = {k.lower(): k for k in self.auras_data.keys()}
                            self._auras_data_norm_map = {k.lower().replace("_", "").replace(" ", "").replace(":", ""): k for k in self.auras_data.keys()}

                        aura_lower = aura.lower()
                        aura_norm = aura_lower.replace("_", "").replace(" ", "").replace(":", "")
                        if aura_lower in self._auras_data_lower_map:
                            real_aura_key = self._auras_data_lower_map[aura_lower]
                        elif aura_norm in self._auras_data_norm_map:
                            real_aura_key = self._auras_data_norm_map[aura_norm]
                        else:
                            real_aura_key = None

                        if real_aura_key:
                            aura_info = self.auras_data[real_aura_key]
                            parsed_aura_name = real_aura_key
                            
                            rarity = aura_info.get("rarity", 1)
                            # Some Fandom records carry rarity: null — int(None)
                            # crashed check_aura_in_logs (TypeError in the logs).
                            # 84 of 478 cached auras (craftable/special ones) have
                            # no numeric rarity: treat them as unknown — use 1 for
                            # the multiplier math, but pass None to the webhook so
                            # it falls back to its own lookup instead of showing
                            # a bogus "1 in 1".
                            rarity_is_unknown = rarity is None or not isinstance(rarity, (int, float))
                            if rarity_is_unknown:
                                rarity = 1
                            exclusive_biome_list = aura_info.get("exclusive_biome", ["None", 1])
                            exclusive_biome = exclusive_biome_list[0] if len(exclusive_biome_list) > 0 else "None"
                            multiplier = exclusive_biome_list[1] if len(exclusive_biome_list) > 1 else 1

                            # Check if the current biome is GLITCHED
                            if self.current_biome == "GLITCHED":
                                rarity /= multiplier
                                biome_message = "[From GLITCHED!]"

                            # Check if the current biome is the aura's exclusive biome
                            elif self.current_biome == exclusive_biome:
                                rarity /= multiplier
                                biome_message = f"[From {exclusive_biome}!]"

                            else:
                                biome_message = ""

                            # Format rarity
                            formatted_rarity = None if rarity_is_unknown else f"{int(rarity):,}"

                            if parsed_aura_name != self.last_aura_found:
                                # Ignore the very first detection after the
                                # macro started: it is the aura the user was
                                # already wearing, not a fresh roll. Register
                                # it silently, then detect normally again.
                                if getattr(self, "_aura_webhook_skip_first", False):
                                    self._aura_webhook_skip_first = False
                                    self.last_aura_found = parsed_aura_name
                                    self.append_log(f"[Aura Webhook] First aura after start ignored: {parsed_aura_name}")
                                    return

                                screenshot_path = None
                                try:
                                    if getattr(self, "aura_screenshot_var", None) and self.aura_screenshot_var.get():
                                        if not self.is_fishing_mode_enabled():
                                            for _ in range(2):
                                                self.activate_roblox_window()
                                                time.sleep(0.75)

                                        screenshot_dir = os.path.join(os.getcwd(), "images")
                                        os.makedirs(screenshot_dir, exist_ok=True)
                                        filename = os.path.join(screenshot_dir, f"aura_{int(time.time())}.png")
                                        if not self.is_roblox_focused():
                                            self.append_log("[Aura Screenshot] Roblox not focused, skipping screenshot")
                                        else:
                                            img = pyautogui.screenshot()
                                            img.save(filename)
                                            screenshot_path = filename
                                            self.append_log(f"[Aura Screenshot] Saved to: {screenshot_path}, exists: {os.path.exists(screenshot_path)}")
                                except Exception as e:
                                    self.error_logging(e, "Error taking aura screenshot")

                                self.send_aura_webhook(parsed_aura_name, formatted_rarity, biome_message, screenshot_path=screenshot_path)
                                self.last_aura_found = parsed_aura_name
                                try:
                                    self._daily_bump("auras")
                                    if isinstance(rarity, (int, float)) and rarity >= 100000:
                                        self.desktop_notify("Rare aura!", f"{parsed_aura_name} ({formatted_rarity or 'unknown chance'})")
                                except Exception:
                                    pass

                                force_record_auras = str(self.config.get("force_record_auras", "") or "").lower()
                                force_record_list = [x.strip() for x in force_record_auras.split(",") if x.strip()]
                                is_force_record = bool(force_record_list) and any(aura_norm.startswith(x.replace("_", "").replace(" ", "")) or x.replace("_", "").replace(" ", "") in aura_norm for x in force_record_list)

                                if self.enable_aura_record_var.get():
                                    if rarity >= int(self.aura_record_minimum_var.get()) or is_force_record:
                                        self.trigger_aura_record()
                        else:
                            # Aura not found in auras_data (biomes_data.json)
                            if aura != self.last_aura_found:
                                # Same startup rule for unknown aura names:
                                # the first detection is only registering the
                                # aura the user already wore.
                                if getattr(self, "_aura_webhook_skip_first", False):
                                    self._aura_webhook_skip_first = False
                                    self.last_aura_found = aura
                                    self.append_log(f"[Aura Webhook] First aura after start ignored: {aura}")
                                    return

                                screenshot_path = None
                                try:
                                    if getattr(self, "aura_screenshot_var", None) and self.aura_screenshot_var.get():
                                        if not self.is_fishing_mode_enabled():
                                            for _ in range(5):
                                                self.activate_roblox_window()
                                                time.sleep(0.75)

                                        screenshot_dir = os.path.join(os.getcwd(), "images")
                                        os.makedirs(screenshot_dir, exist_ok=True)
                                        filename = os.path.join(screenshot_dir, f"aura_{int(time.time())}.png")
                                        if not self.is_roblox_focused():
                                            self.append_log("[Aura Screenshot] Roblox not focused, skipping screenshot")
                                        else:
                                            img = pyautogui.screenshot()
                                            img.save(filename)
                                            screenshot_path = filename
                                            self.append_log(f"[Aura Screenshot] Saved to: {screenshot_path}, exists: {os.path.exists(screenshot_path)}")
                                except Exception as e:
                                    self.error_logging(e, "Error taking aura screenshot")

                                biome_message = f"[From {self.current_biome}!]" if getattr(self, "current_biome", None) and getattr(self, "current_biome") != "NORMAL" else ""
                                self.send_aura_webhook(aura, None, biome_message, screenshot_path=screenshot_path)
                                self.last_aura_found = aura
                                try:
                                    self._daily_bump("auras")
                                except Exception:
                                    pass

                                force_record_auras = str(self.config.get("force_record_auras", "") or "").lower()
                                force_record_list = [x.strip() for x in force_record_auras.split(",") if x.strip()]
                                is_force_record = bool(force_record_list) and any(aura_norm.startswith(x.replace("_", "").replace(" ", "")) or x.replace("_", "").replace(" ", "") in aura_norm for x in force_record_list)

                                if self.enable_aura_record_var.get() and is_force_record:
                                    self.trigger_aura_record()
                        return

                except Exception as e:
                    self.error_logging(e, "Error processing specific aura in check_aura_in_logs.")

        except Exception as e:
            self.error_logging(e, "Error in main check_aura_in_logs function")

    def check_biome_in_logs(self):
        try:
            log_file_path = self.get_latest_log_file()
            log_lines = self.read_log_file(log_file_path)

            for line in reversed(log_lines):
                if "[BloxstrapRPC]" in line and '"largeImage"' in line:
                    match = re.search(r'"largeImage"\s*:\s*\{[^}]*"hoverText"\s*:\s*"([^"]+)"', line)
                    if match:
                        biome = match.group(1).strip().upper()
                        
                        if biome not in self.biome_data:
                            print(f"New unlisted biome detected from RPC: {biome}")
                            try:
                                self.append_log(f"Auto-loaded new unlisted biome: {biome}")
                            except Exception: pass
                            
                            self.biome_data[biome] = {
                                "color": "0xffffff",
                                "thumbnail_url": "https://raw.githubusercontent.com/xVapure/Noteab-Macro/refs/heads/main/images/biome_placeholder.png"
                            }
                            
                        # Set "Message" default for event biome whenever sol dev added to da game 
                        if biome not in self.config["biome_notifier"] and biome not in rare_biomes and biome != "NORMAL":
                            self.config["biome_notifier"][biome] = "Message"
                            try: 
                                self.save_config()
                            except Exception: pass

                        if biome != self.current_biome:
                            last_biome = self.current_biome
                            self.current_biome = biome
                            threading.Thread(target=self.handle_biome_detection, args=(biome, last_biome)).start()
                        return

        except Exception as e:
            self.error_logging(e, "Error in check_biome_in_logs function :skull:")

    def handle_biome_detection(self, biome, last_biome=None):
        try:
            if last_biome is None:
                last_biome = self.current_biome

            if last_biome and last_biome != biome and last_biome != "NORMAL":
                prev_message_type = self.config.get("biome_notifier", {}).get(last_biome, "None")
                if prev_message_type != "None":
                    self.send_webhook(last_biome, prev_message_type, "end")

            # Safety check: ensure biome exists in biome_data
            if biome not in self.biome_data:
                self.append_log(f"[Detection] Biome '{biome}' not found in biome_data, using defaults")
                self.biome_data[biome] = {
                    "color": "0xffffff",
                    "category": "unknown",
                    "spawn_chance": "Unknown",
                    "duration": "Unknown",
                    "how_to_get": "Not verified",
                }
            
            biome_info = self.biome_data[biome]
            now = datetime.now(timezone.utc)    

            print(f"Detected Biome: {biome}, Color: {biome_info['color']}")
            self.append_log(f"Detected Biome: {biome}")

            self.current_biome = biome
            self.last_sent[biome] = now
            try:
                self.biome_history.append((now, biome))
                if len(self.biome_history) > 300:
                    self.biome_history = self.biome_history[-300:]
            except Exception:
                pass
            if biome not in self.biome_counts: self.biome_counts[biome] = 0
            self.biome_counts[biome] += 1
            self.update_stats()

            # son im crine - this is to send the current biome to frontend 
            if hasattr(self, "on_biome_update") and callable(self.on_biome_update):
                self.on_biome_update(biome)

            if (
                last_biome in rare_biomes
                and biome not in rare_biomes
                and bool(getattr(self, "_pending_fishing_failsafe_rejoin", False))
            ):
                self._pending_fishing_failsafe_rejoin = False
                self.append_log(
                    f"[FishingMode] Rare biome ended with deferred failsafe pending. Rejoining from {biome}."
                )
                self.send_webhook_status(
                    "Rare biome ended. Running the delayed fishing failsafe rejoin now.",
                    color=0xffcc00,
                )
                threading.Thread(target=self.terminate_roblox_processes, daemon=True).start()
                return

            message_type = self.config["biome_notifier"].get(biome, "None")

            if biome in rare_biomes:
                message_type = "Ping"
                if self.config.get("record_rare_biome", False):
                    self.trigger_biome_record()
                try:
                    if getattr(self, "reset_on_rare_var", None) and self.reset_on_rare_var.get() and not (self.config.get("enable_idle_mode", False)) and not self.is_fishing_mode_enabled():
                        self._action_scheduler.enqueue_action(self._reset_on_rare_impl, name="reset_rare", priority=0)
                except Exception:
                    pass
            elif biome in admin_biomes:
                # Developer/admin biomes use their dedicated custom embed,
                # but do not inherit the rare-biome @everyone behavior.
                message_type = "Message"

            if biome != "NORMAL":
                popup_window_active = False
                if getattr(self, "just_reconnected", False):
                    deadline = getattr(self, "reconnect_confirm_deadline", None)
                    if isinstance(deadline, (int, float)):
                        popup_window_active = time.monotonic() <= deadline
                    else:
                        popup_window_active = True
                    if not popup_window_active:
                        self.just_reconnected = False
                        self.reconnect_confirm_deadline = None

                if biome in rare_biomes and self.config.get("rare_biome_confirmation_popup", False):
                    try:
                        confirmed = self.confirm_biome_popup(biome)
                    except Exception:
                        confirmed = None
                    if popup_window_active:
                        self.just_reconnected = False
                        self.reconnect_confirm_deadline = None
                    if confirmed is False:
                        self.append_log(f"[BiomeConfirm] User chose to stop macro for {biome}.")
                        self.stop_detection()
                        return

                # rare biome sshot       
                screenshot_path = None
                if biome in rare_biomes and self.config.get("rare_biome_screenshot", False):
                    try:
                        for _ in range(5):
                            self.activate_roblox_window()
                            time.sleep(0.75)
                        screenshot_dir = os.path.join(os.getcwd(), "images")
                        os.makedirs(screenshot_dir, exist_ok=True)
                        screenshot_path = os.path.join(screenshot_dir, f"rare_biome_{biome.lower()}_{int(time.time())}.png")
                        if not self.is_roblox_focused():
                            self.append_log(f"[Rare Biome Screenshot] Roblox not focused, skipping screenshot")
                            screenshot_path = None
                        else:
                            img = pyautogui.screenshot()
                            img.save(screenshot_path)
                            self.append_log(f"[Rare Biome Screenshot] Saved screenshot: {screenshot_path}")
                    except Exception as e:
                        self.error_logging(e, "Error taking rare biome screenshot")
                        screenshot_path = None

                try:
                    self._daily_bump("biomes")
                except Exception:
                    pass
                self.send_webhook(biome, message_type, "start", screenshot_path=screenshot_path)

            if last_biome in rare_biomes and biome not in rare_biomes:
                try:
                    if getattr(self, "teleport_back_to_limbo_var", None) and self.teleport_back_to_limbo_var.get() and not (self.config.get("enable_idle_mode", False)) and not self.is_fishing_mode_enabled():
                        self._action_scheduler.enqueue_action(self._teleport_crack_impl, name="teleport_back", priority=0)
                except Exception:
                    pass

            auto_pop_biomes = self.config.get("auto_pop_biomes", {})
            auto_pop_entry = auto_pop_biomes.get(biome, {}) if isinstance(auto_pop_biomes, dict) else {}
            if isinstance(auto_pop_entry, dict) and bool(auto_pop_entry.get("enabled", False)):
                with self.lock:
                    if not self.config.get("enable_idle_mode", False):
                        self.auto_pop_buffs_for_current_biome(target_biome=biome)

            if biome == "GLITCHED" or biome == "DREAMSPACE":
                with self.lock:
                    if self.config.get("enable_buff_glitched", False) and not self.is_fishing_mode_enabled():
                        threading.Thread(target=self.perform_glitched_enable_buff, daemon=True).start()

        except Exception as e:
            self.error_logging(e,
                               f"Error in handle_biome_detection for biome: {biome}")

    def biome_loop_check(self):
        last_log_file = None

        while self.detection_running:
            try:
                current_log_file = self.get_latest_log_file()
                if current_log_file != last_log_file:
                    self.last_position = 0
                    last_log_file = current_log_file

                self.check_biome_in_logs()
                self.update_session_time()
                time.sleep(1)

            except Exception as e:
                self.error_logging(e, "Error in biome_loop_check function.")

    def aura_loop_check(self):
        last_log_file = None
        while self.detection_running:
            try:
                current_log_file = self.get_latest_log_file()
                if current_log_file != last_log_file:
                    last_log_file = current_log_file

                if self.enable_aura_detection_var.get(): self.check_aura_in_logs(current_log_file)
                time.sleep(0.6)

            except Exception as e:
                self.error_logging(e, "Error in aura_loop_check function.")

    def biome_itemchange_loop(self):
        while self.detection_running:
            try:
                with self.lock:
                    self.auto_biome_change()
                time.sleep(1)

            except Exception as e:
                self.error_logging(e, "Error in biome_itemchange_loop function.")

    def _resume_timer_after_reconnect(self):
        try:
            if getattr(self, "timer_paused_by_disconnect", False):
                self.start_time = datetime.now()
                self.timer_paused_by_disconnect = False
                try:
                    delattr = False
                except Exception:
                    pass
                self.pause_reason = None
            else:
                if not self.start_time:
                    self.start_time = datetime.now()
            self.reconnecting_state = False
            self.has_sent_disconnected_message = False
            self.just_reconnected = True
            self._roblox_fullscreened = False
            self.reconnect_confirm_deadline = time.monotonic() + 60
            self.set_title_threadsafe(f"""EndSol Macro {current_ver} (Running)""")
            self.failsafe_release_if_enabled("after reconnect")
            self.save_config()
        except Exception as e:
            self.error_logging(e, "_resume_timer_after_reconnect")

    def fallback_reconnect(self, current_attempt):
        print(f"Attempting fallback reconnect from attempt {current_attempt}...")
        self.reconnecting_state = True

        self.terminate_roblox_processes()
        self.check_disconnect_loop(current_attempt)
        self.reconnecting_state = False
        self.failsafe_release_if_enabled("after fallback reconnect")

    def _start_player_logger_thread(self):
        if hasattr(self, "player_logger_thread") and self.player_logger_thread and self.player_logger_thread.is_alive():
            return
        self.player_logger_running = True
        self._start_player_log_sender_thread()
        self.player_logger_thread = threading.Thread(target=self._player_logger_loop, daemon=True)
        self.player_logger_thread.start()

    def _stop_player_logger_thread(self):
        self.player_logger_running = False
        self._stop_player_log_sender_thread()

    def _start_player_log_sender_thread(self):
        if hasattr(self,
                   "player_log_sender_thread") and self.player_log_sender_thread and self.player_log_sender_thread.is_alive():
            return
        self.player_log_sender_running = True
        if not hasattr(self, "player_log_queue") or self.player_log_queue is None:
            self.player_log_queue = queue.Queue()
        self.player_log_sender_thread = threading.Thread(target=self._player_log_sender_loop, daemon=True)
        self.player_log_sender_thread.start()

    def _stop_player_log_sender_thread(self):
        self.player_log_sender_running = False
        try:
            if hasattr(self, "player_log_queue"):
                self.player_log_queue.put(None)
        except Exception:
            pass

    def _player_log_sender_loop(self):
        while getattr(self, "player_log_sender_running", False):
            try:
                embed = self.player_log_queue.get(timeout=1)
            except Exception:
                continue
            if embed is None:
                continue
            urls = self.get_webhook_list()
            if not urls:
                continue
            payload = {"embeds": [embed]}
            for webhook_url in urls:
                try:
                    r = safe_post(webhook_url, json=payload, timeout=10)
                    if r is not None and getattr(r, "status_code", None) == 429:
                        retry_after = r.headers.get("Retry-After")
                        try:
                            retry = int(retry_after)
                        except Exception:
                            retry = 5
                        time.sleep(retry)
                        try:
                            safe_post(webhook_url, json=payload, timeout=10)
                        except Exception:
                            pass
                except Exception:
                    pass
            delay = getattr(self, "player_log_send_delay", 2.0)
            start = time.time()
            while (time.time() - start) < delay:
                if not getattr(self, "player_log_sender_running", False):
                    break
                time.sleep(0.1)

    def _find_latest_log_file(self):
        try:
            if not os.path.isdir(self.logs_dir):
                return None
            files = [os.path.join(self.logs_dir, f) for f in os.listdir(self.logs_dir) if
                     f.lower().endswith(".log") and os.path.isfile(os.path.join(self.logs_dir, f))]
            if not files:
                return None
            return max(files, key=os.path.getmtime)
        except:
            return None

    def _biome_at(self, ts):
        try:
            if not hasattr(self, "biome_history") or not self.biome_history:
                return self.current_biome
            try:
                ts_utc = ts.astimezone(timezone.utc)
            except Exception:
                try:
                    ts_utc = ts.replace(tzinfo=timezone.utc)
                except Exception:
                    ts_utc = ts
            last = None
            for bt, b in self.biome_history:
                try:
                    bt_utc = bt.astimezone(timezone.utc)
                except Exception:
                    try:
                        bt_utc = bt.replace(tzinfo=timezone.utc)
                    except Exception:
                        bt_utc = bt
                if bt_utc <= ts_utc:
                    last = b
                else:
                    break
            return last if last is not None else self.current_biome
        except Exception:
            return self.current_biome

    def _player_logger_loop(self):
        last_file = None
        last_pos = 0
        sessions = {}
        while getattr(self, "player_logger_running", False):
            if not getattr(self, "player_logger_var", None) or not self.player_logger_var.get():
                time.sleep(0.5)
                continue
            path = self._find_latest_log_file()
            if not path:
                time.sleep(0.5)
                continue
            if path != last_file:
                last_file = path
                try:
                    last_pos = os.path.getsize(path)
                except:
                    last_pos = 0
            if not self._consume_log_username_validation(path):
                time.sleep(0.3)
                continue
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    f.seek(last_pos)
                    line = f.readline()
                    if not line:
                        time.sleep(0.2)
                        continue
                    last_pos = f.tell()
            except:
                time.sleep(0.5)
                continue
            if not self._consume_log_username_validation(path):
                continue
            # Roblox/Bloxstrap client versions do not always include the
            # historical ExpChat prefix. The player event itself is the
            # stable part, so accept it independently of the subsystem tag.
            if "Player added:" in line or "Player removed:" in line:
                ts_str = line.split(",", 1)[0].strip()
                ts = self._parse_iso_ts(ts_str)
                if "Player added:" in line:
                    m = re.search(r"Player added:\s+(\S+)\s+(\d+)", line)
                    if m:
                        name, pid = m.group(1), m.group(2)
                        join_biome = self._biome_at(ts)
                        sessions[pid] = {"ts": ts, "biome": join_biome}
                        self.logs.append(f"[Player] Joined {name} ({pid})")
                        self.save_logs()
                        ts_iso = ts.astimezone(timezone.utc).isoformat()
                        embed = self._make_player_embed("join", name, pid, ts_iso, None, join_biome)
                        self._enqueue_player_embed(embed)
                elif "Player removed:" in line:
                    m = re.search(r"Player removed:\s+(\S+)\s+(\d+)", line)
                    if m:
                        name, pid = m.group(1), m.group(2)
                        joined = sessions.pop(pid, None)
                        left_biome = self._biome_at(ts)
                        if joined and isinstance(joined, dict) and joined.get("ts"):
                            joined_ts = joined.get("ts")
                            joined_biome = joined.get("biome")
                            secs = int((ts - joined_ts).total_seconds())
                            h = secs // 3600
                            m_ = (secs % 3600) // 60
                            s_ = secs % 60
                            dur = f"{h:02d}:{m_:02d}:{s_:02d}"
                            self.logs.append(f"[Player] Left {name} ({pid}) after {dur}")
                            self.save_logs()
                            ts_iso = ts.astimezone(timezone.utc).isoformat()
                            embed = self._make_player_embed("leave", name, pid, ts_iso, dur, joined_biome, left_biome)
                            self._enqueue_player_embed(embed)
                        else:
                            self.logs.append(f"[Player] Left {name} ({pid})")
                            self.save_logs()
                            ts_iso = ts.astimezone(timezone.utc).isoformat()
                            embed = self._make_player_embed("leave", name, pid, ts_iso, None, None, left_biome)
                            self._enqueue_player_embed(embed)

    def auto_biome_change(self):
        if self.is_fishing_mode_enabled():
            return

        try:
            mt_cooldown = timedelta(minutes=int(self.mt_duration_var.get()) if self.mt_duration_var.get() else 1)
        except ValueError:
            mt_cooldown = timedelta(minutes=1)

        try:
            if (not self.reconnecting_state
                and not (self.config.get("enable_idle_mode", False))
                and not (getattr(self, "enable_potion_crafting_var", None) and self.enable_potion_crafting_var.get())
                and getattr(self, "periodical_aura_var", None) and self.periodical_aura_var.get()):
                try:
                    interval_min = float(self.periodical_aura_interval_var.get())
                except Exception:
                    interval_min = 5.0
                if (datetime.now() - getattr(self, "last_aura_screenshot_time", datetime.min)) >= timedelta(minutes=interval_min):
                    self._action_scheduler.enqueue_action(self.perform_periodic_aura_screenshot_sync, name="periodical:aura", priority=2)
        except Exception:
            pass

        try:
            if (not self.reconnecting_state
                and not (self.config.get("enable_idle_mode", False))
                and not (getattr(self, "enable_potion_crafting_var", None) and self.enable_potion_crafting_var.get())
                and getattr(self, "periodical_inventory_var", None) and self.periodical_inventory_var.get()):
                try:
                    interval_min = float(self.periodical_inventory_interval_var.get())
                except Exception:
                    interval_min = 5.0
                if (datetime.now() - getattr(self, "last_inventory_screenshot_time", datetime.min)) >= timedelta(minutes=interval_min):
                    self._action_scheduler.enqueue_action(self.perform_periodic_inventory_screenshot_sync, name="periodical:inventory", priority=3)
        except Exception:
            pass

        try:
            crack_cooldown = timedelta(minutes=int(self.config.get("portable_crack_interval", "3")))
        except (ValueError, TypeError):
            crack_cooldown = timedelta(minutes=3)

        # Single-flight: both detection loops tick in parallel, so guard the
        # whole item-usage block with a non-blocking lock. This prevents two
        # threads from passing the same cooldown check simultaneously.
        item_lock = getattr(self, "_item_usage_lock", None)
        if item_lock is None:
            item_lock = threading.Lock()
            self._item_usage_lock = item_lock
        if not item_lock.acquire(blocking=False):
            return
        try:
            _startup_gate = getattr(self, "_items_startup_gate", datetime.min)
            if datetime.now() < _startup_gate:
                return

            if self.config.get("teleport_portable_crack") and datetime.now() - getattr(self, 'last_crack_time', datetime.min) >= crack_cooldown and not getattr(self, '_br_sc_running', False) and not getattr(self, '_portable_crack_running', False) and not getattr(self, '_mt_running', False) and not getattr(self, '_remote_running', False) and not (getattr(self, '_egg_collecting', False) or getattr(self, '_eden_running', False) or getattr(self, '_potion_thread_active', False)) and not getattr(self, 'auto_pop_state', False) and datetime.now() >= getattr(self, '_cancel_next_actions_until', datetime.min) and not (self.config.get("enable_idle_mode", False)):
                try:
                    self.use_portable_crack()
                    self.append_log("[Items] Portable Crack fired.")
                finally:
                    self.last_crack_time = datetime.now()

            if self.mt_var.get() and datetime.now() - self.last_mt_time >= mt_cooldown and not getattr(self,
                                                                                                        '_br_sc_running',
                                                                                                        False) and not getattr(self, '_portable_crack_running', False) and not getattr(
                            self, '_mt_running', False) and not getattr(self, '_remote_running', False) and not getattr(
                            self, '_egg_collecting', False) and not getattr(self, 'auto_pop_state', False) and datetime.now() >= getattr(self, '_cancel_next_actions_until',
                                                                                datetime.min) and not (self.config.get("enable_idle_mode", False)):
                try:
                    self.use_merchant_teleporter()
                    self.last_mt_time = datetime.now()
                finally:
                    self.last_mt_time = datetime.now()

            try:
                sc_cooldown = timedelta(minutes=int(self.sc_duration_var.get()) if self.sc_duration_var.get() else 20)
            except ValueError:
                sc_cooldown = timedelta(minutes=20)

            if self.sc_var.get() and datetime.now() - self.last_sc_time >= sc_cooldown and not getattr(self,
                                                                                                        '_br_sc_running',
                                                                                                        False) and not getattr(self, '_portable_crack_running', False) and not getattr(
                            self, '_mt_running', False) and not getattr(self, '_remote_running', False) and not getattr(
                            self, '_egg_collecting', False) and not getattr(self, 'auto_pop_state', False) and datetime.now() >= getattr(self, '_cancel_next_actions_until',
                                                                                    datetime.min) and not (self.config.get("enable_idle_mode", False)):
                    # Pre-check the same conditions the implementation will check
                    # when it runs. If blocked (e.g. disabled biome), do NOT
                    # enqueue and do NOT consume the cooldown — retry on the
                    # next tick instead, so the item is used as soon as the
                    # block clears.
                    _sc_blocked = self.br_sc_blocked_reason()
                    if _sc_blocked:
                        self._log_item_postponed("Strange Controller", _sc_blocked)
                    else:
                        self.use_br_sc('strange controller')
                        self.last_sc_time = datetime.now()
                        self.append_log("[Items] Strange Controller fired; next in "
                                        + str(self.sc_duration_var.get() or 20) + " min.")

            try:
                br_cooldown = timedelta(minutes=int(self.br_duration_var.get()) if self.br_duration_var.get() else 35)
            except ValueError:
                br_cooldown = timedelta(minutes=35)

            if self.br_var.get() and datetime.now() - self.last_br_time >= br_cooldown and not getattr(self,
                                                                                                        '_br_sc_running',
                                                                                                        False) and not getattr(self, '_portable_crack_running', False) and not getattr(
                            self, '_mt_running', False) and not getattr(self, '_remote_running', False) and not getattr(
                            self, '_egg_collecting', False) and not getattr(self, 'auto_pop_state', False) and datetime.now() >= getattr(self, '_cancel_next_actions_until',
                                                                                    datetime.min) and not (self.config.get("enable_idle_mode", False)):
                    _br_blocked = self.br_sc_blocked_reason()
                    if _br_blocked:
                        self._log_item_postponed("Biome Randomizer", _br_blocked)
                    else:
                        self.use_br_sc('biome randomizer')
                        self.last_br_time = datetime.now()
                        self.append_log("[Items] Biome Randomizer fired; next in "
                                        + str(self.br_duration_var.get() or 35) + " min.")
        finally:
            item_lock.release()

    def perform_periodic_aura_screenshot_sync(self):
        if not self.detection_running or self.reconnecting_state: 
            return
        if getattr(self, "enable_potion_crafting_var", None) and self.enable_potion_crafting_var.get():
            return 
        if hasattr(self, "_is_fishing_blocked") and self._is_fishing_blocked():
            return
        inventory_close_button = self.config.get("inventory_close_button", [1418, 298])
        try:
            if self.config.get("enable_idle_mode", False):
                return
            if not getattr(self, "periodical_aura_var", None) or not self.periodical_aura_var.get():
                return
            try:
                interval_min = float(self.periodical_aura_interval_var.get())
            except Exception:
                interval_min = 5.0
            if (datetime.now() - getattr(self, "last_aura_screenshot_time", datetime.min)) < timedelta(minutes=interval_min):
                return
            if not self.check_roblox_procs(): return
            
            for _ in range(4):
                if not self.detection_running or (hasattr(self, "_is_fishing_blocked") and self._is_fishing_blocked()):
                    return
                self.activate_roblox_window()
                time.sleep(0.8)
            
            aura_menu = self.config.get("aura_menu", [0, 0])
            search_bar = self.config.get(
                "aura_search_bar",
                self.config.get("search_bar", [834, 364]),
            )
            if aura_menu and aura_menu[0]:
                try:
                    autoit.mouse_click("left", aura_menu[0], aura_menu[1], 1, speed=3)
                    time.sleep(0.67)
                    autoit.mouse_click("left", search_bar[0], search_bar[1], 1, speed=3)
                except Exception:
                    try:
                        self.Global_MouseClick(aura_menu[0], aura_menu[1])
                        time.sleep(0.67)
                        self.Global_MouseClick(search_bar[0], search_bar[1])
                    except Exception:
                        pass
                time.sleep(0.67)
                try:
                    screenshot_dir = os.path.join(os.getcwd(), "images")
                    os.makedirs(screenshot_dir, exist_ok=True)
                    filename = os.path.join(screenshot_dir, f"aura_screenshot_{int(time.time())}.png")
                    if not self.is_roblox_focused():
                        self.append_log("[Aura Screenshot] Roblox not focused, skipping screenshot")
                    else:
                        img = pyautogui.screenshot()
                        img.save(filename)
                        self.send_aura_screenshot_webhook(filename)
                    self.last_aura_screenshot_time = datetime.now()
                    autoit.mouse_click("left", inventory_close_button[0], inventory_close_button[1], 1, speed=3)
                    time.sleep(0.67)
                except Exception as e:
                    self.error_logging(e, "Error taking/sending aura screenshot")
        except Exception as e:
            self.error_logging(e, "Error in perform_periodic_aura_screenshot_sync")

    def use_merchant_teleporter(self):
        try:
            if self.config.get("enable_idle_mode", False):
                return
            if getattr(self, "enable_potion_crafting_var", None) and self.enable_potion_crafting_var.get(): return
            self._action_scheduler.enqueue_action(self._merchant_teleporter_impl, name="merchant_tele", priority=5)
        except Exception:
            try:
                if self.config.get("enable_idle_mode", False):
                    return
                self._merchant_teleporter_impl()
            except Exception:
                pass

    def _merchant_teleporter_impl(self):
        if getattr(self, '_br_sc_running', False): return
        if (getattr(self, '_egg_collecting', False) or getattr(self, '_eden_running', False) or getattr(self, '_potion_thread_active', False)): return
        if getattr(self, "enable_potion_crafting_var", None) and self.enable_potion_crafting_var.get(): return
        self._last_merchant_sequence_ran = False
        self._last_merchant_sequence_requires_reset = False
        self._mt_running = True
        fishing_override = bool(getattr(self, "_fishing_br_sc_override", False))
        try:
            def _cancelled():
                # When called from fishing.py loop only check
                # ^ truly critical conditions to avoid concurrent state aborts (dev note) ^
                if fishing_override:
                    return (
                        not self.detection_running
                        or self.reconnecting_state
                        or self.current_biome in ("GLITCHED", "DREAMSPACE", "CYBERSPACE")
                    )
                return (
                    not self.detection_running
                    or self.reconnecting_state
                    or self.auto_pop_state
                    or self.on_auto_merchant_state
                    or self.config.get("enable_potion_crafting")
                    or self.current_biome in ("GLITCHED", "DREAMSPACE", "CYBERSPACE")
                )

            if _cancelled(): return

            if hasattr(self, 'last_merchant_interaction') and self.last_merchant_interaction:
                merchant_cooldown_time = 300
                if time.time() - self.last_merchant_interaction < merchant_cooldown_time: return

            time.sleep(0.75)

            inventory_click_delay = int(self.config.get("inventory_click_delay", "0")) / 1000.0
            inventory_menu = self.config.get("inventory_menu", [36, 535])
            items_tab = self.config.get("items_tab", [1272, 329])
            search_bar = self.config.get("search_bar", [855, 358])
            first_item_slot = self.config.get("first_item_inventory_slot_pos", [845, 460])
            amount_box = self.config.get("amount_box", [594, 570])
            use_button = self.config.get("use_button", [710, 573])
            inventory_close_button = self.config.get("inventory_close_button", [1418, 298])

            for _ in range(4):
                if _cancelled(): return
                self.activate_roblox_window()
                time.sleep(0.3)

            current_x, current_y = autoit.mouse_get_pos()
            autoit.mouse_down("right")
            time.sleep(0.1)
            autoit.mouse_move(current_x, current_y + 75, 0)
            time.sleep(0.1)
            autoit.mouse_up("right")
            time.sleep(0.92)

            self.Global_MouseClick(inventory_menu[0], inventory_menu[1])
            time.sleep(0.24 + inventory_click_delay)

            self.Global_MouseClick(items_tab[0], items_tab[1])
            time.sleep(0.23)
            self.Global_MouseClick(items_tab[0], items_tab[1])
            time.sleep(0.23)
            self.Global_MouseClick(items_tab[0], items_tab[1])
            time.sleep(0.24 + inventory_click_delay)
            if _cancelled(): return

            self.Global_MouseClick(search_bar[0], search_bar[1])
            time.sleep(0.23)
            self.Global_MouseClick(search_bar[0], search_bar[1])
            time.sleep(0.23)
            self.Global_MouseClick(search_bar[0], search_bar[1])
            time.sleep(0.27 + inventory_click_delay)
            if _cancelled(): return
            autoit.send("teleport")
            time.sleep(0.4 + inventory_click_delay)
            self.Global_MouseClick(first_item_slot[0], first_item_slot[1])
            time.sleep(0.4 + inventory_click_delay)
            try:
                if not self._ocr_first_slot_matches("teleport"):
                    inventory_close_button = self.config.get("inventory_close_button", [1418, 298])
                    self.Global_MouseClick(inventory_close_button[0], inventory_close_button[1])
                    time.sleep(0.15 + inventory_click_delay)
                    return
            except Exception:
                pass
            self.Global_MouseClick(first_item_slot[0], first_item_slot[1])
            time.sleep(0.4 + inventory_click_delay)
            self.Global_MouseClick(first_item_slot[0], first_item_slot[1])
            time.sleep(0.4 + inventory_click_delay)

            if _cancelled(): return

            time.sleep(0.17 + inventory_click_delay)
            self.Global_MouseClick(amount_box[0], amount_box[1])
            if _cancelled(): return
            autoit.send("^{a}")
            time.sleep(0.15 + inventory_click_delay)
            autoit.send("{BACKSPACE}")
            time.sleep(0.15 + inventory_click_delay)
            autoit.send('1')
            time.sleep(0.14 + inventory_click_delay)
            if _cancelled(): return
            autoit.mouse_click("left", use_button[0], use_button[1], 3)
            time.sleep(0.23 + inventory_click_delay)

            self.Global_MouseClick(inventory_close_button[0], inventory_close_button[1])
            time.sleep(0.23 + inventory_click_delay)
            self._last_merchant_sequence_ran = True
            merchant_completed = bool(self.Merchant_Handler())
            self._last_merchant_sequence_requires_reset = merchant_completed

            if _cancelled(): return

            time.sleep(0.33 + inventory_click_delay)
            self.Global_MouseClick(inventory_menu[0], inventory_menu[1])
            time.sleep(0.33 + inventory_click_delay)
            self.Global_MouseClick(inventory_close_button[0], inventory_close_button[1])
            if getattr(self, "auto_merchant_in_limbo_var", None) and self.auto_merchant_in_limbo_var.get():
                try:
                    time.sleep(0.33 + inventory_click_delay)
                    self.Global_MouseClick(inventory_menu[0], inventory_menu[1])
                    time.sleep(0.24 + inventory_click_delay)
                    self.Global_MouseClick(items_tab[0], items_tab[1])
                    time.sleep(0.23 + inventory_click_delay)
                    self.Global_MouseClick(search_bar[0], search_bar[1])
                    time.sleep(0.23 + inventory_click_delay)
                    self.Global_MouseClick(search_bar[0], search_bar[1])
                    time.sleep(0.15 + inventory_click_delay)
                    self.Global_MouseClick(search_bar[0], search_bar[1])
                    time.sleep(0.15 + inventory_click_delay)
                    autoit.send("crack")
                    time.sleep(0.4 + inventory_click_delay)
                    self.Global_MouseClick(first_item_slot[0], first_item_slot[1])
                    time.sleep(0.4 + inventory_click_delay)
                    self.Global_MouseClick(first_item_slot[0], first_item_slot[1])
                    time.sleep(0.4 + inventory_click_delay)
                    self.Global_MouseClick(first_item_slot[0], first_item_slot[1])
                    time.sleep(0.3 + inventory_click_delay)
                    self.Global_MouseClick(amount_box[0], amount_box[1])
                    time.sleep(0.16 + inventory_click_delay)
                    autoit.send("^{a}")
                    time.sleep(0.13 + inventory_click_delay)
                    autoit.send("{BACKSPACE}")
                    time.sleep(0.13 + inventory_click_delay)
                    autoit.send('1')
                    time.sleep(0.13 + inventory_click_delay)
                    self.Global_MouseClick(use_button[0], use_button[1])
                    time.sleep(0.22 + inventory_click_delay)
                    self.Global_MouseClick(inventory_close_button[0], inventory_close_button[1])
                    time.sleep(0.22 + inventory_click_delay)
                except Exception as e:
                    self.error_logging(e, "Error using portable Crack after merchant teleporter")

        except Exception as e:
            self.error_logging(e, "Error in use_merchant_teleporter function.")
        finally:
            self._mt_running = False
            self._cancel_next_actions_until = datetime.min

    def trigger_aura_record(self):
        def aura_record():
            try:
                # print("hi me running aura record")
                keybind = self.aura_record_keybind_var.get()
                keys = [key.strip() for key in keybind.split('+')]
                time.sleep(30)
                pyautogui.hotkey(*keys)
            except Exception as e:
                self.error_logging(e, "Error in trigger_aura_record")

        threading.Thread(target=aura_record).start()

    def trigger_biome_record(self):
        def record():
            try:
                # print("hi me running biome record")
                keybind = self.rarest_biome_keybind_var.get()
                keys = [key.strip() for key in keybind.split('+')]
                time.sleep(45)
                pyautogui.hotkey(*keys)
            except Exception as e:
                self.error_logging(e, "Error in trigger_biome_record")
        threading.Thread(target=record).start()
