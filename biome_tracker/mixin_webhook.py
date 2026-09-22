from .base_support import *

CUSTOM_WEBHOOK_MESSAGE_LIMIT = 300
WEBHOOK_SPECIAL_MESSAGE_BIOMES = set(special_message_biomes) - {"SINGULARITY"}


def _normalize_aura_lookup(value):
    """Normalize log/wiki aura names without losing Unicode characters."""
    import unicodedata
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    return "".join(ch for ch in text if ch.isalnum())


def _parse_rarity_value(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None


_RARITY_FRAGMENT_PATTERNS = (
    re.compile(r"\s*\((?:1\s*/\s*[\d.,]+|1\s+in\s+[\d.,]+)\)", re.IGNORECASE),
    re.compile(r"\b1\s*/\s*[\d.,]+\b"),
    re.compile(r"\b1\s+in\s+[\d.,]+\b", re.IGNORECASE),
)


def _strip_rarity_fragments(text):
    """Remove "1 in N" / "1/N" chance fragments from a source blurb.

    Rarity numbers belong in the Rarity / Native webhook lines only; the
    Source line must describe WHERE an aura comes from, never repeat its
    odds (e.g. "From Oblivion Potion (1 in 100)" -> "From Oblivion Potion").
    """
    out = str(text or "")
    for pattern in _RARITY_FRAGMENT_PATTERNS:
        out = pattern.sub("", out)
    return re.sub(r"\s{2,}", " ", out).strip(" -–—·,;")

def sanitize_custom_webhook_message(value):
    """Remove mentions/control characters while preserving user text verbatim."""
    text = str(value or "")
    text = text.replace("@", "")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b\u200c\u200d\ufeff]", "", text)
    return text[:CUSTOM_WEBHOOK_MESSAGE_LIMIT].strip()

NATIVE_AURA_MULTIPLIERS = {
    "WINDY": "3x", "SNOWY": "3x", "RAINY": "4x",
    "SAND STORM": "4x", "HELL": "6x", "STARFALL": "5x",
    "HEAVEN": "5x", "CORRUPTION": "5x", "NULL": "1000x",
    "CYBERSPACE": "2x", "SINGULARITY": "5x",
    "GLITCHED": "N/A — unique rare-biome rules",
    "DREAMSPACE": "N/A — unique rare-biome rules",
}

def _custom_message_value(entry, phase, field):
    if not isinstance(entry, dict):
        return ""
    value = entry.get(f"{phase}_{field}")
    if value is None and field == "description":
        value = entry.get(phase, "")
    return sanitize_custom_webhook_message(value)

def _biome_metadata_lines(biome, biome_info):
    """Return only neutral metadata loaded for the detected biome.

    Do not expose hard-coded gameplay claims here. In particular, how_to_get
    and multiplier fields may come from legacy/community data and are not
    sufficiently verified to be presented as facts in a webhook.
    """
    # Spawn chance and duration are safe neutral fallback metadata. Gameplay
    # mechanics remain intentionally excluded regardless of source.
    spawn = str(biome_info.get("spawn_chance") or "Unknown")
    duration = str(biome_info.get("duration") or "Unknown")
    return [
        f"> **Biome:** {biome}",
        f"> **Spawn/Rarity:** {spawn}",
        f"> **Duration:** {duration}",
    ]

def _clean_obtainment_text(text) -> str:
    """Trim/collapse an obtainment blurb for webhook display."""
    t = str(text or "").strip()
    t = " ".join(t.split())
    return t


def _aura_source_condition_lines(aura_info, cls_type: str):
    """
    Build complementary Source / Condition webhook lines for an aura.

    Source    = where the aura comes from (biome, workshop, potion, event...).
    Condition = an extra rule that is NOT already stated by the Source line,
                so the two sections never repeat the same phrase.

    Returns (source_text, condition_text); either may be "".
    """
    info = aura_info if isinstance(aura_info, dict) else {}
    obtainment = _clean_obtainment_text(info.get("obtainment"))
    obtain_low = obtainment.lower()
    excl_list = info.get("exclusive_biome") if isinstance(info.get("exclusive_biome"), list) else []
    excl = str(excl_list[0]).strip() if excl_list and excl_list[0] not in (None, "", "None") else ""
    native_list = info.get("native_biome") if isinstance(info.get("native_biome"), list) else []
    native = str(native_list[0]).strip() if native_list and native_list[0] not in (None, "", "None") else ""
    native_rarity = info.get("native_rarity")
    cls_type = str(cls_type or "normal").strip().lower()

    # Legacy raw values like "CYBERSPACE UNAFFECTED BY LUCK": the suffix is a
    # rule, not a place — split it into the Condition line.
    luck_exempt = bool(info.get("luck_exempt"))
    if excl and "UNAFFECTED BY LUCK" in excl.upper():
        luck_exempt = True
        excl = re.sub(r"UNAFFECTED BY LUCK", "", excl, flags=re.IGNORECASE).strip(" -–—")
    if info.get("luck_exempt_note"):
        luck_exempt = True

    # Biome-exclusive: Source names the world. The in-biome chance is
    # reported by the Exclusive Rarity line, never here.
    if excl:
        if luck_exempt:
            return f"🌀 Exclusive to {excl}", "Unaffected by luck boosts"
        if "breakthrough" in obtain_low or " bt" in f" {obtain_low} " or obtain_low.endswith(" bt"):
            return f"🌀 Exclusive to {excl}", "Breakthrough rolls don't apply"
        return f"🌀 Exclusive to {excl}", ""

    # Biome-native: Source names the world only. The boosted chance is
    # reported by the dedicated Native line, never repeated here.
    if native:
        return f"🌐 Native to {native}", ""

    if cls_type == "crafted" or any(k in obtain_low for k in ("craft", "workshop", "jake")):
        return (f"🔨 {_strip_rarity_fragments(obtainment)}" if obtainment else "🔨 Crafted at Jake's Workshop",
                "Cannot be rolled — craft only")

    if cls_type == "potion_required" or "potion" in obtain_low:
        return (f"🧪 {_strip_rarity_fragments(obtainment)}" if obtainment else "🧪 Requires a potion",
                "Only rolls while the potion is active")

    if cls_type == "shop" or any(k in obtain_low for k in ("shop", "buy", "purchase", "merchant")):
        return (f"🏪 {_strip_rarity_fragments(obtainment)}" if obtainment else "🏪 Shop purchase",
                "Purchased, not rolled")

    if cls_type == "quest_reward" or "quest" in obtain_low:
        return (f"🎁 {_strip_rarity_fragments(obtainment)}" if obtainment else "🎁 Quest reward", "")

    if cls_type == "event_exclusive" or "event" in obtain_low or "limited" in obtain_low:
        return (f"👑 {_strip_rarity_fragments(obtainment)}" if obtainment else "👑 Limited event aura",
                "Available only during its event window")

    if cls_type == "limbo" or "limbo" in obtain_low:
        return "🌑 Limbo-exclusive aura", ""

    if cls_type == "breakthrough" or "breakthrough" in obtain_low:
        return "🎲 Any biome (Breakthrough roll)", "Only obtainable through Breakthrough"

    if "standard roll" in obtain_low or "any biome" in obtain_low:
        return "🎲 Any biome (standard roll)", ""

    if obtainment:
        return f"🎲 {_strip_rarity_fragments(obtainment)}", ""

    return "🎲 Natural roll", ""


def _aura_rarity_lines(aura_info, cls_type, rarity_value, rarity_name_field):
    """
    Build the Rarity / Exclusive Rarity / Native webhook lines for an aura.

    Rules (v1.0.5):
      - Numeric rarity is ONLY ever shown in a rarity line, never inside
        Source or Native.
      - Biome-exclusive auras (e.g. Astraios, only in SINGULARITY) report
        their single chance as "Exclusive Rarity" instead of "Rarity".
      - Native auras with both a normal and a boosted chance show the
        normal chance as "Rarity" and the boosted chance on a separate
        "Native" line together with its biome/time requirement.
      - Crafted/potion/... auras without a numeric rarity simply get no
        rarity line; Source still explains how they are obtained.
    """
    info = aura_info if isinstance(aura_info, dict) else {}
    excl_list = info.get("exclusive_biome") if isinstance(info.get("exclusive_biome"), list) else []
    excl = str(excl_list[0]).strip() if excl_list and excl_list[0] not in (None, "", "None") else ""
    native_list = info.get("native_biome") if isinstance(info.get("native_biome"), list) else []
    native = str(native_list[0]).strip() if native_list and native_list[0] not in (None, "", "None") else ""
    native_rarity = _parse_rarity_value(info.get("native_rarity"))
    cls_type = str(cls_type or "normal").strip().lower()
    is_exclusive = bool(excl) or cls_type == "biome_exclusive"

    lines = []
    if rarity_value is not None:
        label = "Exclusive Rarity" if is_exclusive else "Rarity"
        line = f"> **{label}:** 1 in {rarity_value:,}"
        if rarity_name_field and isinstance(rarity_name_field, str) and rarity_name_field.strip():
            line = f"{line} [{rarity_name_field.strip()}]"
        lines.append(line)
    if native and not is_exclusive and native_rarity is not None:
        lines.append(f"> **Native:** {native} · 1 in {native_rarity:,}")
    return lines


class WebhookMixin:
    def _send_screenshot_webhook(self, screenshot_path, title, log_label="screenshot"):
        try:
            urls = self.get_webhook_list()
            if not urls:
                return
            icon_url = "https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png"
            embed = {
                "description": f"> ## {title}",
                "color": 0xffffff,
                "footer": {"text": f"EndSol Macro {current_ver}", "icon_url": icon_url},
                "timestamp": discord_timestamp()
            }
            for webhook_url in urls:
                try:
                    embed_copy = dict(embed)
                    embed_copy["image"] = {"url": f"attachment://{os.path.basename(screenshot_path)}"}
                    with open(screenshot_path, "rb") as image_file:
                        files = {"file": (os.path.basename(screenshot_path), image_file, "image/png")}
                        data = {"payload_json": json.dumps({"content": "", "embeds": [embed_copy]})}
                        safe_post(webhook_url, data=data, files=files, timeout=10)
                except Exception as e:
                    try:
                        self.append_log(f"Failed to send {log_label} to {webhook_url}: {e}")
                    except Exception:
                        pass
        except Exception as e:
            self.error_logging(e, f"Error in send_{log_label}_webhook")

    def send_screen_screenshot_webhook(self, screenshot_path):
        self._send_screenshot_webhook(screenshot_path, "Remote Screenshot", "remote screenshot")

    def send_quest_screenshot_webhook(self, screenshot_path):
        self._send_screenshot_webhook(screenshot_path, "Daily Quests Screenshot", "quest screenshot")

    def send_inventory_screenshot_webhook(self, screenshot_path):
        self._send_screenshot_webhook(screenshot_path, "Periodical Inventory Screenshot", "inventory screenshot")

    def send_aura_screenshot_webhook(self, screenshot_path):
        self._send_screenshot_webhook(screenshot_path, "Periodical Aura Screenshot", "aura screenshot")

    def get_webhook_list(self):
        try:
            res = []
            if hasattr(self, "webhook_urls") and isinstance(self.webhook_urls, list) and self.webhook_urls:
                res = [u for u in self.webhook_urls if isinstance(u, str) and u.strip()]
            else:
                raw = self.config.get("webhook_urls") or self.config.get("webhook_url", "")
                if isinstance(raw, list):
                    res = [u for u in raw if isinstance(u, str) and u.strip()]
                elif isinstance(raw, str):
                    s = raw.strip()
                    if s:
                        try:
                            parsed = json.loads(s)
                            if isinstance(parsed, list):
                                res = [u for u in parsed if isinstance(u, str) and u.strip()]
                            else:
                                res = [s]
                        except Exception:
                            res = [s]
            return res
        except Exception:
            return []

    def _extract_webhook_channel_id(self, payload):
        try:
            if not isinstance(payload, dict):
                return ""
            channel_id = payload.get("channel_id")
            if channel_id is None:
                channel_obj = payload.get("channel")
                if isinstance(channel_obj, dict):
                    channel_id = channel_obj.get("id")
            channel_id_str = str(channel_id).strip() if channel_id is not None else ""
            if channel_id_str.isdigit():
                return channel_id_str
            return ""
        except Exception:
            return ""

    def refresh_active_webhook_channels(self, force=False):
        try:
            urls = self.get_webhook_list()
            normalized_urls = [u.strip() for u in urls if isinstance(u, str) and u.strip()]

            cached_urls = getattr(self, "_active_webhook_channel_lookup_urls", [])
            cached_mentions = getattr(self, "_active_webhook_channel_mentions", [])
            last_resolve = getattr(self, "_webhook_channel_resolve_time", 0)
            cooldown = getattr(self, "_webhook_channel_resolve_cooldown", 60)
            now = time.time()

            if (
                not force
                and isinstance(cached_urls, list)
                and isinstance(cached_mentions, list)
                and normalized_urls == cached_urls
            ):
                return list(cached_mentions)

            if not force and (now - last_resolve) < cooldown:
                return list(cached_mentions)

            mentions = []
            got_429 = False
            for webhook_url in normalized_urls:
                try:
                    response = safe_get(webhook_url, timeout=2)
                    if response.status_code == 429:
                        got_429 = True
                        retry_after = 120
                        try:
                            data = response.json()
                            retry_after = max(int(float(data.get("retry_after", 120))), 30)
                        except Exception:
                            pass
                        self._webhook_channel_resolve_cooldown = retry_after
                        print(f"[Webhook] Rate limited (429), backing off for {retry_after}s")
                        break
                    response.raise_for_status()
                    payload = response.json()
                    channel_id = self._extract_webhook_channel_id(payload)
                    if channel_id:
                        mentions.append(f"<#{channel_id}>")
                    else:
                        print(f"Failed to resolve channel_id from webhook payload: {webhook_url}")
                except requests.exceptions.HTTPError as e:
                    if "429" in str(e):
                        got_429 = True
                        self._webhook_channel_resolve_cooldown = 120
                        print(f"[Webhook] Rate limited (429), backing off for 120s")
                        break
                    print(f"Failed to resolve webhook channel for {webhook_url}: {e}")
                except Exception as e:
                    print(f"Failed to resolve webhook channel for {webhook_url}: {e}")

            self._webhook_channel_resolve_time = now
            if not got_429:
                self._webhook_channel_resolve_cooldown = 60
                self._active_webhook_channel_lookup_urls = normalized_urls
                self._active_webhook_channel_mentions = mentions
            return list(getattr(self, "_active_webhook_channel_mentions", []))
        except Exception:
            return []

    def _build_active_webhook_channels_field_value(self):
        mentions = self.refresh_active_webhook_channels()
        if not mentions:
            return "- (No webhook channels resolved)"
        return "\n".join(f"- {mention}" for mention in mentions)

    # Custom embed messages for rare biomes — unique look & feel per biome
    RARE_BIOME_CUSTOM = {
        "GLITCHED": {
            "color": 0xbfff00,
            "title_start": "⚠️ ANOMALY DETECTED ⚠️",
            "title_end": "⚠️ ANOMALY FADED ⚠️",
            "desc_start": (
                "> ## ⚠️ ERROR BIOME DETECTION. ⚠️\n"
                "> **Spawn:** 1 in 30,000 per biome change (~1 in 11.2M/s)\n"
                "> **Duration:** 2m 44s | **BT:** Native auras ignore Breakthrough\n"
                "> **Exclusive Auras:** FAULT, GLITCH, OPPRESSION *(cannot be rolled outside Glitched)*\n"
                "> \n"
                "> *Glitches and errors all around the server.*"
            ),
            "desc_end": "> ## ⚠️ ANOMALY CONTAINED ⚠️\n> The corruption has been purged. Normalcy restored.",
        },
        "DREAMSPACE": {
            "color": 0xea9dda,
            "title_start": "★ DREAMSPACE MANIFESTED ★",
            "title_end": "★ DREAMSPACE FADED ★",
            "desc_start": (
                "> ## ★ Welcome to the Dreamscape ★\n"
                "> **Spawn:** 1 in 3,500,000/s during Normal biome\n"
                "> **Duration:** 3m 12s | **BT:** No Breakthrough; spawns Heavenly Potions\n"
                "> **Exclusive Auras:** ★, ★★, ★★★, Borealis, Dreammetric\n"
                "> \n"
                "> *Reality bends. Dreams take shape. Roll now — the window is brief.*"
            ),
            "desc_end": "> ## ★ Dreams Fade ★\n> The dreamscape dissolves back into reality.",
        },
        "CYBERSPACE": {
            "color": 0x0A1A3D,
            "title_start": "⟨ CYBERSPACE INITIALIZED ⟩",
            "title_end": "⟨ CYBERSPACE TERMINATED ⟩",
            "desc_start": (
                "> ## ⟨ Welcome to the Digital Realm ⟩\n"
                "> **Source:** Strange Controller / Biome Randomizer (1 in 5,000)\n"
                "> **Duration:** 12 min | **BT:** 2x Breakthrough | **16 unique auras**\n"
                "> **Exclusive Auras:** Forbidden, PLAYER, Player Respawn, Virtual, Metabytes, Illusionary, Virtual: Fatal Error, Matrix, Antivirus, Virtual: Full Control, Virtual: Worldwide, Aegis, Pixelation, Matrix: Overdrive, Matrix: Reality, Cytokinesis\n"
                "> \n"
                "> *The grid is live. 12 minutes to exploit it.*"
            ),
            "desc_end": "> ## ⟨ Connection Closed ⟩\n> Cyberspace has been terminated. Back to analog.",
        },
        "SINGULARITY": {
            "color": 0xcf4023,
            "title_start": "◉ SINGULARITY FORMED ◉",
            "title_end": "◉ SINGULARITY COLLAPSED ◉",
            "desc_start": (
                "> ## ◉ The Void Has Awakened ◉\n"
                "> **Spawn:** 1 in 100 to replace STARFALL\n"
                "> **Duration:** 20 min (or until ASTRAIOS rolled) | **BT:** 5x Breakthrough\n"
                "> **Key Aura:** GARGANTUA (1 in 430,000,000)\n"
                "> \n"
                "> *A gravitational anomaly. 20 minutes — maximize every roll.*"
            ),
            "desc_end": "> ## ◉ Event Horizon Reached ◉\n> The singularity has collapsed. STARFALL may resume.",
        },
        "THE HYPERSPACE REALM": {
            "color": 0x9b59b6,
            "title_start": "◈ HYPERSPACE BREACHED ◈",
            "title_end": "◈ HYPERSPACE SEALED ◈",
            "desc_start": (
                "> ## ◈ Reality Distortion Detected ◈\n"
                "> **Source:** Admin-triggered event biome\n"
                "> **Duration:** Unknown | **Exclusive Auras:** Hyperspace-exclusive\n"
                "> \n"
                "> *The fabric of reality has been torn. Roll while you can.*"
            ),
            "desc_end": "> ## ◈ Dimensional Rift Closed ◈\n> The hyperspace realm has been sealed.",
        },
        "THE NULL'S EXISTENCE": {
            "color": 0x1a1a2e,
            "title_start": "\u26ab NULL'S EXISTENCE MANIFESTS \u26ab",
            "title_end": "\u26ab NULL'S EXISTENCE ENDS \u26ab",
            "desc_start": (
                "> ## \u26ab The Null Breaks Through \u26ab\n"
                "> **Source:** Admin-triggered event biome\n"
                "> **Duration:** Unknown | **Exclusive Auras:** Null-exclusive\n"
                "> \n"
                "> *Reality fractures. The void bleeds through. Roll while you can.*"
            ),
            "desc_end": "> ## \u26ab The Null Seals \u26ab\n> The NULL's Existence has been sealed. Reality stabilizes.",
        },
        "赤い満月": {
            "color": 0xcc0000,
            "title_start": "🌕 RED FULL MOON RISES 🌕",
            "title_end": "🌕 RED FULL MOON SETS 🌕",
            "desc_start": (
                "> ## 🌕 The Blood Moon Hangs Low 🌕\n"
                "> **Source:** Admin-triggered event biome (Red Full Moon)\n"
                "> **Duration:** Unknown | **Rare aura boosts active**\n"
                "> \n"
                "> *The crimson moon illuminates the server. Seize the moment.*"
            ),
            "desc_end": "> ## 🌕 Moonlight Fades 🌕\n> The Red Full Moon has set. Normal skies return.",
        },
        "THE CITADEL OF ORDERS": {
            "color": 0xc0a030,
            "title_start": "⚔ CITADEL OF ORDERS SUMMONED ⚔",
            "title_end": "⚔ CITADEL OF ORDERS DISPELLED ⚔",
            "desc_start": (
                "> ## ⚔ The Citadel Appears ⚔\n"
                "> **Source:** Admin-triggered event biome\n"
                "> **Duration:** Unknown | **Enhanced rolling conditions**\n"
                "> \n"
                "> *Ancient orders convene. The citadel grants its favor to the worthy.*"
            ),
            "desc_end": "> ## ⚔ The Citadel Dissolves ⚔\n> The Citadel of Orders has been dispelled.",
        },
    }

    def build_biome_webhook_description(self, biome, event_type, message_type="Test",
                                        custom_title=None, custom_desc=None,
                                        color_override=None, private_server_link=None,
                                        unix_ts=None):
        """Build the exact biome webhook description, color and ping content.

        Single source of truth shared by send_webhook and the Discord Webhook
        Customization preview, so the preview always matches what Discord
        actually receives. custom_title / custom_desc override the saved
        per-biome custom message for the built phase (unsaved UI edits);
        color_override ("#rrggbb" / "0xrrggbb") overrides the embed color.
        Returns {"description": str, "color": int, "content": str}.
        """
        if private_server_link is None:
            private_server_link = self.config.get("private_server_link", "")
        # Safety check: ensure biome exists in biome_data
        if biome not in self.biome_data:
            self.append_log(f"[Webhook] Biome '{biome}' not found in biome_data, using defaults")
            # Create a minimal default entry
            self.biome_data[biome] = {
                "color": "0xffffff",
                "category": "unknown",
                "spawn_chance": "Unknown",
                "duration": "Unknown",
                "how_to_get": "Unknown"
            }
        
        biome_info = self.biome_data[biome]
        color_str = biome_info.get("color", "0xffffff").replace("#", "")
        biome_color = int(color_str, 16)
        if unix_ts is None:
            unix_ts = int(time.time())
        timestamp_title = f"<t:{unix_ts}:F> (<t:{unix_ts}:R>)"
        content = ""

        # Per-biome individual ping support
        biome_pings = self.config.get("biome_pings", {})
        biome_ping_entry = biome_pings.get(biome, {})
        ping_id = str(biome_ping_entry.get("id", "") or "").strip()
        ping_type = str(biome_ping_entry.get("type", "userid") or "userid").strip().lower()

        # Classify the biome and load all custom fields before building the
        # message. These values must exist for both start and end events.
        biome_meta = self.biome_data.get(biome, {})
        category_norm = str(biome_meta.get("category", "")).strip().lower()
        is_admin = biome in admin_biomes or category_norm == "admin"
        is_rare = biome in rare_biomes or category_norm == "rare"
        is_event = not is_admin and not is_rare and category_norm == "event"
        rarity_text = str(biome_meta.get("spawn_chance") or "").strip()
        source_text = str(biome_meta.get("how_to_get") or "").strip()
        duration_text = str(biome_meta.get("duration") or "").strip()

        custom = self.RARE_BIOME_CUSTOM.get(biome) or {}
        user_rare_overrides = {}
        all_rare_overrides = self.config.get("custom_rare_biome_overrides", {}) or {}
        if isinstance(all_rare_overrides, dict) and isinstance(all_rare_overrides.get(biome), dict):
            user_rare_overrides = all_rare_overrides[biome]
        custom_messages = self.config.get("custom_webhook_messages", {}) or {}
        custom_entry = custom_messages.get(biome, {}) if isinstance(custom_messages, dict) else {}
        phase = "start" if event_type == "start" else "end"
        # Preview overrides: unsaved edits from the customization UI are
        # passed in directly so the preview matches the next real send.
        if custom_title is not None:
            custom_title_value = sanitize_custom_webhook_message(custom_title)
        else:
            custom_title_value = _custom_message_value(custom_entry, phase, "title")
        if custom_desc is not None:
            custom_description_value = sanitize_custom_webhook_message(custom_desc)
        else:
            custom_description_value = _custom_message_value(custom_entry, phase, "description")
        user_color = biome_meta.get("color")

        if is_admin:
            rarity_text = "Admin event (Saturday)"
            source_text = (str(biome_meta.get("how_to_get") or "").strip()
                           or "Forced by an engineer event — no natural spawn chance")
            duration_text = "Variative +-60 min"
        join_section = ""
        if event_type == "start":
            if private_server_link:
                join_section = f"> ### **[Join Server]({private_server_link})**"
            else:
                join_section = ""

        if event_type == "start" and message_type != "Test":
            if biome in {"GLITCHED", "DREAMSPACE", "CYBERSPACE"}:
                content = "@everyone"
            elif ping_id and ping_id.lower() not in ("everyone", "here"):
                content = f"<@&{ping_id}>" if ping_type == "roleid" else f"<@{ping_id}>"

        def _without_duplicate_title(text, title):
            """Keep custom rare copy, but never print its title twice."""
            if not text:
                return ""
            wanted = " ".join(str(title or "").split()).casefold()
            kept = []
            for line in str(text).splitlines():
                raw_line = line.strip()
                normalized = raw_line.lstrip("># -*").strip()
                # Rare descriptions from old customization data sometimes
                # contain their own ## heading. The message already has one
                # canonical title line, so remove all markdown heading lines
                # from the copied body to prevent visual title duplication.
                if raw_line.startswith(("> ##", "##", "> #", "# ")):
                    continue
                if wanted and " ".join(normalized.split()).casefold() == wanted:
                    continue
                kept.append(line)
            return "\n".join(kept).strip()

        def _rarity_obtainment_line():
            """Info summary plus the in-game chat appearance ("[Biome]: phrase")."""
            lines_out = []
            if rarity_text and str(rarity_text).strip().casefold() not in {"unknown", "none", "n/a"}:
                lines_out.append(f"> **Spawn:** {str(rarity_text).strip()}")
            if source_text and str(source_text).strip().casefold() not in {"unknown", "not verified", "none", "n/a"}:
                info_text = str(source_text).strip()
                # The "[Biome]:" insert belongs with the chat phrase line
                # below — never inside the Info sentence itself.
                info_text = re.sub(r"^\s*\[[^\]]{1,40}\]\s*:\s*", "", info_text)
                info_text = re.sub(r"\s+", " ", info_text).strip()
                if info_text:
                    lines_out.append(f"> **Info:** {info_text}")
            flavor = str(biome_meta.get("chat_message") or "").strip()
            if flavor:
                # Mirror the real in-game chat look: "[Biome]: phrase"
                lines_out.append(f"> [{biome}]: {flavor}")
            return "\n".join(lines_out)

        # The legacy layout is intentional: the Discord timestamp is the first
        # line of the message body, followed by one title and the message data.
        # Do not use the embed title field as well, otherwise Discord displays
        # the title twice when custom rare copy also contains a heading.
        if event_type == "start":
            if is_rare or is_admin:
                custom_rare = self.RARE_BIOME_CUSTOM.get(biome) or {}
                unique_title = (user_rare_overrides.get("title_start") if user_rare_overrides else None) or (custom_rare.get("title_start") if custom_rare else None)
                unique_desc = (user_rare_overrides.get("desc_start") if user_rare_overrides else None) or (custom_rare.get("desc_start") if custom_rare else None)

                has_custom = bool(custom_title_value or custom_description_value)

                if has_custom:
                    # User custom message REPLACES the original
                    parts = [timestamp_title]
                    if custom_title_value:
                        parts.append(f"> ## {custom_title_value}")
                    else:
                        parts.append(f"> ## {unique_title}")
                    if custom_description_value:
                        parts.append(f"> {custom_description_value}")
                    # Footer: real biome + rarity
                    real_info = f"> *Real biome: {biome} · {rarity_text}*"
                    parts.append("")
                    parts.append(real_info)
                else:
                    # Original message — use RARE_BIOME_CUSTOM directly
                    parts = [timestamp_title, f"> ## {unique_title}"]
                    if unique_desc:
                        desc_lines = unique_desc.strip().splitlines()
                        heading_lower = " ".join(str(unique_title or "").split()).casefold()
                        for line in desc_lines:
                            raw = line.strip()
                            normalized = raw.lstrip("># -*").strip()
                            if raw.startswith(("> ##", "##")):
                                continue
                            if heading_lower and " ".join(normalized.split()).casefold() == heading_lower:
                                continue
                            parts.append(line)
                    else:
                        rarity_line = _rarity_obtainment_line()
                        if rarity_line:
                            parts.append(rarity_line)
                        if duration_text and str(duration_text).strip().casefold() not in {"unknown", "none", "n/a"}:
                            parts.append(f"> **Duration:** {duration_text}")

                if join_section:
                    parts.append("")
                    parts.append(join_section)

                description = "\n".join(parts)
            elif is_event:
                heading = custom_title_value if custom_title_value else f"Event Biome Started - {biome}"
                parts = [timestamp_title, f"> ## {heading}"]
                rarity_line = _rarity_obtainment_line()
                if rarity_line:
                    parts.append(rarity_line)
                if duration_text and str(duration_text).strip().casefold() not in {"unknown", "none", "n/a"}:
                    parts.append(f"> **Duration:** {duration_text}")
                extra = _without_duplicate_title(custom_description_value, heading)
                if extra:
                    parts.extend(["", extra])
                if join_section:
                    parts.append("")
                    parts.append(join_section)
                description = "\n".join(parts)
            else:
                heading = custom_title_value if custom_title_value else f"Biome Started - {biome}"
                parts = [timestamp_title, f"> ## {heading}"]
                rarity_line = _rarity_obtainment_line()
                if rarity_line:
                    parts.append(rarity_line)
                if duration_text and str(duration_text).strip().casefold() not in {"unknown", "none", "n/a"}:
                    parts.append(f"> **Duration:** {duration_text}")
                if join_section:
                    parts.append(join_section)
                extra = _without_duplicate_title(custom_description_value, heading)
                if extra:
                    parts.extend(["", extra])
                description = "\n".join(parts)
        else:
            if is_rare or is_admin:
                custom_rare = self.RARE_BIOME_CUSTOM.get(biome) or {}
                unique_title = (user_rare_overrides.get("title_end") if user_rare_overrides else None) or (custom_rare.get("title_end") if custom_rare else None)
                unique_desc = (user_rare_overrides.get("desc_end") if user_rare_overrides else None) or (custom_rare.get("desc_end") if custom_rare else None)

                has_custom = bool(custom_title_value or custom_description_value)

                if has_custom:
                    parts = [timestamp_title]
                    if custom_title_value:
                        parts.append(f"> ## {custom_title_value}")
                    else:
                        parts.append(f"> ## {unique_title}")
                    if custom_description_value:
                        parts.append(f"> {custom_description_value}")
                else:
                    parts = [timestamp_title, f"> ## {unique_title}"]
                    if unique_desc:
                        desc_lines = unique_desc.strip().splitlines()
                        heading_lower = " ".join(str(unique_title or "").split()).casefold()
                        for line in desc_lines:
                            raw = line.strip()
                            normalized = raw.lstrip("># -*").strip()
                            if raw.startswith(("> ##", "##")):
                                continue
                            if heading_lower and " ".join(normalized.split()).casefold() == heading_lower:
                                continue
                            parts.append(line)

                description = "\n".join(parts)
            else:
                heading = custom_title_value if custom_title_value else f"Biome Ended - {biome}"
                parts = [timestamp_title, f"> ## {heading}"]
                extra = _without_duplicate_title(custom_description_value, heading)
                if extra:
                    parts.extend(["", extra])
                description = "\n".join(parts)

        embed_color = discord_color(user_color) if user_color else (custom.get("color") if is_rare and custom else biome_color)
        if color_override:
            try:
                embed_color = int(str(color_override).replace("#", "").replace("0x", ""), 16)
            except (TypeError, ValueError):
                pass
        return {"description": description, "color": embed_color, "content": content}

    def send_webhook(self, biome, message_type, event_type, screenshot_path=None):
        urls = self.get_webhook_list()

        private_server_link = self.config.get("private_server_link", "")

        if not urls:
            self.append_log("Webhook URL is missing/not included in the config")
            return

        # Only rare and developer/admin biomes use the special custom embeds.
        # Ordinary weather/event biomes obey their per-biome Message/None setting.
        if message_type == "None" and biome not in WEBHOOK_SPECIAL_MESSAGE_BIOMES:
            return

        # Description/color/ping are built by the shared builder so the
        # customization preview can never drift from the real message.
        built = self.build_biome_webhook_description(
            biome, event_type, message_type, private_server_link=private_server_link
        )
        description = built["description"]
        embed_color = built["color"]
        content = built["content"]
        biome_info = self.biome_data.get(biome, {})
        current_utc_time = discord_timestamp()
        icon_url = "https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png"
        embed = {
            "description": description,
            "color": embed_color,
            "footer": {
                "text": f"""EndSol Macro {current_ver}""",
                "icon_url": icon_url
            },
            "timestamp": current_utc_time
        }
        # Try to download the thumbnail locally and attach it to the webhook
        # instead of relying on Discord fetching an external URL. This
        # guarantees the icon shows up in Discord even if the upstream CDN
        # (e.g. raw.githubusercontent.com) is slow, blocked, or rate-limited.
        thumbnail_attachment_path = None
        if event_type == "start":
            thumb_url = biome_info.get("thumbnail_url", "")
            thumbnail_attachment_path = self._mm_download_thumbnail(thumb_url, biome)
            if thumbnail_attachment_path and os.path.exists(thumbnail_attachment_path):
                embed["thumbnail"] = {"url": f"attachment://{os.path.basename(thumbnail_attachment_path)}"}
            elif thumb_url:
                embed["thumbnail"] = {"url": thumb_url}

        for webhook_url in urls:
            for attempt in range(3):
                try:
                    headers = {}
                    embed_copy = dict(embed)
                    # Build a list of files to attach.
                    # Order matters: Discord assigns index 0, 1, 2, ... to
                    # `attachment://<basename>` URLs. Put the thumbnail first
                    # so it lands as files[0] (the thumbnail field) and the
                    # screenshot second as files[1] (the image field).
                    files = {}
                    file_handles = []
                    if thumbnail_attachment_path and os.path.exists(thumbnail_attachment_path):
                        th_handle = open(thumbnail_attachment_path, "rb")
                        file_handles.append(th_handle)
                        files["file0"] = (os.path.basename(thumbnail_attachment_path), th_handle, "image/png")
                    if screenshot_path and os.path.exists(screenshot_path):
                        ss_handle = open(screenshot_path, "rb")
                        file_handles.append(ss_handle)
                        if "file0" in files:
                            files["file1"] = (os.path.basename(screenshot_path), ss_handle, "image/png")
                            embed_copy["image"] = {"url": f"attachment://{os.path.basename(screenshot_path)}"}
                        else:
                            files["file0"] = (os.path.basename(screenshot_path), ss_handle, "image/png")
                            embed_copy["image"] = {"url": f"attachment://{os.path.basename(screenshot_path)}"}
                    try:
                        if files:
                            data = {"payload_json": json.dumps({"content": content, "embeds": [embed_copy]})}
                            response = safe_post(webhook_url, data=data, files=files, headers=headers, timeout=15)
                        else:
                            payload = {"content": content, "embeds": [embed_copy]}
                            response = safe_post(webhook_url, json=payload, headers=headers, timeout=10)
                        if response is not None and response.status_code < 400:
                            self.append_log(f"Sent {message_type} for {biome} - {event_type} to webhook")
                            break
                        elif response is None:
                            # safe_post failed completely; retry
                            if attempt < 2:
                                import time as _t
                                _t.sleep(2 * (attempt + 1))
                                continue
                            else:
                                self.append_log(f"Failed to send biome webhook after {attempt+1} attempts: no response")
                                break
                        else:
                            response.raise_for_status()
                            self.append_log(f"Sent {message_type} for {biome} - {event_type} to webhook")
                            break
                    finally:
                        for h in file_handles:
                            try:
                                h.close()
                            except Exception:
                                pass
                except requests.exceptions.RequestException as e:
                    if attempt < 2:
                        import time as _t
                        _t.sleep(2 * (attempt + 1))
                    else:
                        self.append_log(f"Failed to send webhook after 3 attempts: {e}")

    def send_merchant_webhook(self, merchant_name, screenshot_path=None, source='ocr'):
        urls = self.get_webhook_list()
        if not urls:
            self.append_log("Webhook URL is missing/not included in the config")
            return
        merchant_thumbnails = {
            "Mari": "https://i.postimg.cc/RZh2pw0j/mari.png ",
            "Jester": "https://i.postimg.cc/7PBVsdTq/jester.png",
            "Rin": "https://i.postimg.cc/j5n9B6Km/rin.png"
        }
        
        # merchant_counts is incremented in Merchant_Handler (mixin_actions.py)
        if hasattr(self, "on_stats_update") and callable(self.on_stats_update):
            try:
                self.on_stats_update()
            except Exception:
                pass
        
        if merchant_name == "Mari":
            ping_id = self.mari_user_id_var.get() if hasattr(self, 'mari_user_id_var') else self.config.get("mari_user_id", "")
            ping_enabled = self.ping_mari_var.get() if hasattr(self, 'ping_mari_var') else self.config.get("ping_mari", False)
        elif merchant_name == "Jester":
            ping_id = self.jester_user_id_var.get() if hasattr(self, 'jester_user_id_var') else self.config.get("jester_user_id", "")
            ping_enabled = self.ping_jester_var.get() if hasattr(self, 'ping_jester_var') else self.config.get("ping_jester", False)
        elif merchant_name == "Rin":
            ping_id = self.rin_user_id_var.get() if hasattr(self, 'rin_user_id_var') else self.config.get("rin_user_id", "")
            ping_enabled = self.ping_rin_var.get() if hasattr(self, 'ping_rin_var') else self.config.get("ping_rin", False)
        else:
            ping_id = ""
            ping_enabled = False
        content = f"<@{ping_id}>" if (source in ('logs', 'ocr') and ping_enabled and ping_id) else ""
        ps_link = self.config.get("private_server_link", "").replace("\n", "")
        icon_url = "https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png"
        current_utc_time = discord_timestamp()
        embed = {
            "description": f"> ## {merchant_name} has arrived!\n> ### [Join Server]({ps_link})",
            "color": 11753 if merchant_name == "Mari" else (16752955 if merchant_name == "Rin" else 8595632),
            "thumbnail": {"url": merchant_thumbnails.get(merchant_name, "")},
            "timestamp": current_utc_time,
            "fields": [
                {"name": "Detection Source", "value": source.upper()}
            ],
            "footer": {
                "text": f"""EndSol Macro {current_ver}""",
                "icon_url": icon_url
            }
        }
        try:
            if screenshot_path and os.path.exists(screenshot_path):
                for webhook_url in urls:
                    embed["image"] = {"url": f"attachment://{os.path.basename(screenshot_path)}"}
                    with open(screenshot_path, "rb") as image_file:
                        files = {"file": (os.path.basename(screenshot_path), image_file, "image/png")}
                        response = safe_post(
                            webhook_url,
                            data={
                                "payload_json": json.dumps({
                                    "content": content,
                                    "embeds": [embed]
                                })
                            },
                            files=files
                        )
                        try:
                            response.raise_for_status()
                            self.append_log(
                                f"Webhook sent successfully for {merchant_name}: {response.status_code}")
                        except requests.exceptions.RequestException as e:
                            self.append_log(f"Failed to send merchant webhook: {e}")
            else:
                payload = {"content": content, "embeds": [embed]}
                for webhook_url in urls:
                    try:
                        response = safe_post(webhook_url, json=payload)
                        response.raise_for_status()
                        self.append_log(f"Webhook sent successfully for {merchant_name}: {response.status_code}")
                    except requests.exceptions.RequestException as e:
                        self.append_log(f"Failed to send merchant webhook: {e}")
        except requests.exceptions.RequestException as e:
            self.append_log(f"Failed to send merchant webhook: {e}")

    def send_aura_webhook(self, aura_name, rarity, biome_message, screenshot_path=None):
        urls = self.get_webhook_list()
        if not urls:
            self.append_log("Webhook URL is missing/not included in the config")
            return
        icon_url = "https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png"
        ping_minimum = int(self.config.get("ping_minimum", "100000"))
        
        force_ping_auras = str(self.config.get("force_ping_auras", "") or "").lower()
        force_ping_list = [x.strip() for x in force_ping_auras.split(",") if x.strip()]
        aura_name_norm = _normalize_aura_lookup(aura_name)
        is_force_ping = bool(force_ping_list) and any(aura_name_norm.startswith(x.replace("_", "").replace(" ", "")) or x.replace("_", "").replace(" ", "") in aura_name_norm for x in force_ping_list)
        
        color = 0xffffff
        aura_info = {}
        if not hasattr(self, "auras_data") or not self.auras_data:
            self.auras_data = self.load_auras_json()
            if hasattr(self, "_webhook_aura_map"):
                delattr(self, "_webhook_aura_map")
        if not hasattr(self, "_webhook_aura_map"):
            self._webhook_aura_map = {
                _normalize_aura_lookup(key): key
                for key in self.auras_data
                if _normalize_aura_lookup(key)
            }
        real_key = self._webhook_aura_map.get(_normalize_aura_lookup(aura_name))
        if real_key:
            aura_info = self.auras_data.get(real_key, {}) or {}
            # Legacy index data is not authoritative for native/exclusive or
            # obtainment semantics. Hydrate the individual Fandom article
            # before using it in a webhook, then keep it in memory for later
            # rolls. Never silently treat an unverified cache as verified.
            if (isinstance(aura_info, dict) and aura_info.get("_metadata_quality") not in {"verified_article_fields", "fandom_verified_reference"} and hasattr(self, "load_fandom_aura_detail")):
                try:
                    detail_cache = getattr(self, "_fandom_aura_detail_cache", {})
                    detail = detail_cache.get(real_key)
                    if detail is None:
                        detail = self.load_fandom_aura_detail(real_key)
                        detail_cache[real_key] = detail
                        self._fandom_aura_detail_cache = detail_cache
                    if isinstance(detail, dict) and not detail.get("error"):
                        aura_info = {**aura_info, **detail}
                        self.auras_data[real_key] = aura_info
                except Exception as detail_error:
                    self.append_log(f"[Aura metadata] Could not hydrate {real_key} from Fandom: {detail_error}")

        obtainment_field = aura_info.get("obtainment") if isinstance(aura_info, dict) else None
        data_rarity = aura_info.get("rarity") if isinstance(aura_info, dict) else None
        rarity_value = _parse_rarity_value(rarity) if rarity is not None else _parse_rarity_value(data_rarity)
        minimum_value = _parse_rarity_value(self.config.get("aura_webhook_minimum_rarity", "0"))
        if minimum_value is None:
            minimum_value = 0

        # Check if this aura has special conditions that always warrant a webhook
        from .aura_classification import classify_aura
        _classification = classify_aura(aura_name, aura_info)
        always_send = bool(_classification.get("always_webhook"))

        # Skip if below minimum rarity — UNLESS the aura is genuinely NOT
        # obtained by rolling. The Fandom refresh now writes an obtainment
        # blurb for EVERY standard roll (e.g. "Any biome (standard roll)"),
        # so the old "obtainment text exists" test wrongly bypassed the
        # user's minimum-rarity threshold for common auras such as Good
        # (1 in 5). Bypass only crafted/potion/shop/quest/limbo types.
        _non_rolling_types = ("crafted", "potion_required", "shop", "quest_reward", "limbo")
        _obtainment_type = str(aura_info.get("obtainment_type", "") or "").strip().lower() if isinstance(aura_info, dict) else ""
        is_non_rolling = _classification.get("type") in _non_rolling_types and _obtainment_type != "standard"
        # v1.0.4 ping policy:
        #   - event/limited auras are announced but NEVER pinged;
        #   - Transcendent / Challenged / Challenged+ bypass the user's
        #     minimum-rarity threshold, but are sent WITHOUT a ping;
        #   - everything else pings only at/above the configured minimum.
        aura_class_name = str(aura_info.get("rarity_name", "") or "").strip().lower() if isinstance(aura_info, dict) else ""
        aura_flags = [str(f).lower() for f in (aura_info.get("flags") or [])] if isinstance(aura_info, dict) else []
        is_event_aura = aura_class_name == "event" or bool(aura_info.get("limited")) or "limited" in aura_flags or "event" in aura_flags
        bypass_class = aura_class_name in ("transcendent", "challenged", "challenged+")
        if rarity_value is not None and not is_non_rolling and not always_send and not bypass_class and rarity_value < minimum_value:
            self.append_log(f"[Aura Webhook] Skipped {aura_name}: rarity 1 in {rarity_value} is below configured minimum 1 in {minimum_value}.")
            return
        elif minimum_value and rarity_value is not None and rarity_value < minimum_value:
            _why = ("non-rolling obtainment" if is_non_rolling
                    else (f"special class '{aura_class_name}'" if bypass_class else "special condition"))
            self.append_log(f"[Aura Webhook] {aura_name} announced despite configured minimum 1 in {minimum_value} ({_why}).")

        rarity_line = ""
        source_line = ""
        condition_line = ""
        if real_key and isinstance(aura_info, dict) and aura_info:
            # Source/condition are computed for every KNOWN aura, regardless
            # of whether a numeric rarity exists: the Fandom refresh leaves
            # rarity null for many special auras (variants, craftables), but
            # they still have a source — previously they fell into the "not
            # enough data" branch and the webhook showed no details at all.
            # Source = where it comes from; Condition = extra rule that is
            # NOT already stated by Source, so the two never duplicate.
            rarity_name_field = aura_info.get("rarity_name") if isinstance(aura_info, dict) else None
            _cls_type = str(_classification.get("type") or "normal")
            source_text, condition_text = _aura_source_condition_lines(aura_info, _cls_type)
            source_line = f"> **Source:** {source_text}" if source_text else ""
            condition_line = f"> **Condition:** 🔒 {condition_text}" if condition_text else ""

            if rarity_value is not None:
                if 99000 <= rarity_value < 1000000:
                    color = 0x3dd3e0
                elif 1000000 <= rarity_value < 10000000:
                    color = 0xff73ec
                elif 10000000 <= rarity_value < 99000000:
                    color = 0x2d30f7
                elif 99000000 <= rarity_value < 1000000000:
                    color = 0xed2f59
                else:
                    color = 0xff9447

            # Rarity lines (v1.0.5): the numeric chance lives ONLY here.
            # Biome-exclusive auras use "Exclusive Rarity"; native auras get
            # a separate "Native" line with biome/time + boosted chance.
            # Crafted/potion/... auras without a numeric rarity simply omit
            # the line — Source already explains their obtainment.
            rarity_lines = _aura_rarity_lines(aura_info, _cls_type, rarity_value, rarity_name_field)

            _detail_parts = [*rarity_lines]
            if source_line:
                _detail_parts.append(source_line)
            if condition_line:
                _detail_parts.append(condition_line)
            description = f"> ## ✨ Aura equipped: {aura_name}\n" + "\n".join(_detail_parts)
            if biome_message:
                description += f" {biome_message}"
        else:
            if is_force_ping:
                color = 0xed2f59
            # Aura not in auras.json — not enough data to determine source
            unknown_source_line = "> **Source:** 🎲 Unknown source (aura not in the local database)"
            if biome_message:
                description = f"> ## ✨ Aura equipped: {aura_name}\n{unknown_source_line} {biome_message}"
            else:
                description = f"> ## ✨ Aura equipped: {aura_name}\n{unknown_source_line}"
        current_utc_time = discord_timestamp()
        embed = {
            "title": "⭐ Aura Detection ⭐",
            "description": description,
            "color": color,
            "footer": {
                "text": f"""EndSol Macro {current_ver}""",
                "icon_url": icon_url
            },
            "timestamp": current_utc_time
        }
        content = ""
        should_ping = False
        if is_event_aura:
            should_ping = False  # event auras are never pinged
        elif bypass_class:
            # Transcendent / Challenged bypass the announce threshold, but
            # they are the rarest rolls in the game and still respect the
            # user's ping_minimum (e.g. Pixelation, 1 in 1,073,741,824).
            should_ping = (rarity_value is not None and rarity_value >= ping_minimum)
        elif always_send:
            should_ping = True
        elif rarity is not None and 'rarity_value' in locals() and rarity_value >= ping_minimum:
            should_ping = True
        if is_force_ping and not is_event_aura:
            should_ping = True
            
        if should_ping:
            aura_user_id = self.config.get("aura_user_id", "")
            if aura_user_id:
                content = f"<@{aura_user_id}>"
        try:
            if screenshot_path and os.path.exists(screenshot_path):
                for webhook_url in urls:
                    embed_copy = dict(embed)
                    embed_copy["image"] = {"url": f"attachment://{os.path.basename(screenshot_path)}"}
                    with open(screenshot_path, "rb") as image_file:
                        files = {"file": (os.path.basename(screenshot_path), image_file, "image/png")}
                        data = {"payload_json": json.dumps({"content": content, "embeds": [embed_copy]})}
                        for att in range(3):
                            try:
                                response = safe_post(webhook_url, data=data, files=files, timeout=15)
                                response.raise_for_status()
                                self.append_log(f"Aura webhook with screenshot sent for {aura_name}")
                                break
                            except requests.exceptions.RequestException as re:
                                if att < 2:
                                    import time as _t
                                    _t.sleep(2 * (att + 1))
                                else:
                                    self.append_log(f"Failed to send aura webhook with screenshot after 3 attempts: {re}")
            else:
                payload = {"content": content, "embeds": [embed]}
                for webhook_url in urls:
                    try:
                        response = safe_post(webhook_url, json=payload, timeout=10)
                        if response is None:
                            self.append_log(f"Failed to send aura webhook: no response from Discord")
                        else:
                            response.raise_for_status()
                            self.append_log(f"Aura webhook sent for {aura_name}")
                    except requests.exceptions.RequestException as e:
                        self.append_log(f"Failed to send aura webhook: {e}")
        except Exception as e:
            self.error_logging(e, "Error in send_aura_webhook")

    def send_webhook_status(self, status, color=None):
        try:
            urls = self.get_webhook_list()
            if not urls:
                self.append_log("Webhook URL is missing/not included in the config")
                return
            default_color = 3066993 if "started" in status.lower() else 15158332
            embed_color = color if color is not None else default_color
            icon_url = "https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png"
            if "started" in status.lower():
                n = len(urls)
                status = f"{status} ({n} webhook{'s' if n != 1 else ''} active)"
            fields = []
            if "started" in status.lower():
                fields.append({
                    "name": "Active webhook channels:",
                    "value": self._build_active_webhook_channels_field_value(),
                    "inline": False
                })
            current_utc_time = discord_timestamp()
            embeds = [{
                "title": "== 🌟 Macro Status 🌟 ==",
                "description": f"> ## {status}",
                "color": embed_color,
                "timestamp": current_utc_time,
                "footer": {
                    "text": f"EndSol Macro {current_ver}",
                    "icon_url": icon_url
                },
                "fields": fields
            }]
            for webhook_url in urls:
                try:
                    response = safe_post(webhook_url, json={"embeds": embeds}, timeout=8)
                    if response is None:
                        self.append_log("Failed to send webhook status: no response from Discord")
                    else:
                        response.raise_for_status()
                except requests.exceptions.RequestException as e:
                    self.append_log(f"Failed to send webhook status: {e}")
        except Exception as e:
            self.error_logging(e, "Error in webhook_status")

    def send_macro_summary(self, last24h_seconds, reason_text="Macro stopped!"):
        try:
            last24h_str = self.format_seconds_to_hhmmss(min(int(last24h_seconds), 86400))
            session_str = self.format_seconds_to_hhmmss(int(self.current_session))
            urls = self.get_webhook_list()
            if not urls:
                return
            icon_url = "https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png"
            current_utc_time = discord_timestamp()
            embed = {
                "title": "== 🌟 Macro Status 🌟 ==",
                "description": f"> ## {reason_text} Here is your session summary:",
                "color": 0xff0000,
                "timestamp": current_utc_time,
                "footer": {
                    "text": f"EndSol Macro {current_ver}",
                    "icon_url": icon_url
                },
                "fields": [
                    {
                        "name": "Session Times:",
                        "value": f"- in the last 24 hours: {last24h_str}\n- in this session: {session_str}",
                        "inline": False
                    }
                ]
            }
            payload = {"embeds": [embed]}
            for webhook_url in urls:
                try:
                    safe_post(webhook_url, json=payload, timeout=5)
                except Exception:
                    pass
        except Exception as e:
            self.error_logging(e, "Error in send_macro_summary")

    def send_egg_ocr_webhook(self, egg_name, aura_rarity, discord_user_id="", screenshot_path=None):
        try:
            urls = self.get_webhook_list()
            if not urls: return
            icon_url = "https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png"
            current_utc_time = discord_timestamp()

            content = f"<@{discord_user_id}>" if discord_user_id else ""

            embed = {
                "title": "🥚 Special Easter Egg Found 🥚",
                "description": f"> ## {egg_name}\n> Possible respective egg aura rarity: **{aura_rarity}**",
                "color": 0xffd700,
                "timestamp": current_utc_time,
                "thumbnail": {"url": "https://i.postimg.cc/FzRsHF7y/eggdoggo.png"},
                "footer": {
                    "text": f"EndSol Macro {current_ver}",
                    "icon_url": icon_url
                }
            }

            if screenshot_path and os.path.isfile(screenshot_path):
                embed["image"] = {"url": f"attachment://{os.path.basename(screenshot_path)}"}

            for webhook_url in urls:
                try:
                    embed_copy = dict(embed)
                    if screenshot_path and os.path.isfile(screenshot_path):
                        with open(screenshot_path, "rb") as img_file:
                            files = {"file": (os.path.basename(screenshot_path), img_file, "image/png")}
                            data = {"payload_json": json.dumps({"content": content, "embeds": [embed_copy]})}
                            response = safe_post(webhook_url, data=data, files=files, timeout=15)
                    else:
                        payload = {"content": content, "embeds": [embed_copy]}
                        response = safe_post(webhook_url, json=payload, timeout=10)
                    response.raise_for_status()
                    self.append_log(f"Egg OCR webhook sent for {egg_name}")
                except requests.exceptions.RequestException as e:
                    self.append_log(f"Failed to send egg OCR webhook: {e}")
        except Exception as e:
            self.error_logging(e, "Error in send_egg_ocr_webhook")

    def send_eden_ocr_webhook(self, discord_user_id="", screenshot_path=None):
        try:
            urls = self.get_webhook_list()
            if not urls: return
            icon_url = "https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png"
            eden_thumbnail = "https://i.postimg.cc/q7jFZVMp/eden.png"
            current_utc_time = discord_timestamp()

            content = f"<@{discord_user_id}>" if discord_user_id else ""

            embed = {
                "description": f"> ## The Devourer of the Void is here...",
                "color": 0x2f3136,
                "timestamp": current_utc_time,
                "thumbnail": {"url": eden_thumbnail},
                "footer": {
                    "text": f"EndSol Macro {current_ver}",
                    "icon_url": icon_url
                }
            }

            if screenshot_path and os.path.isfile(screenshot_path):
                embed["image"] = {"url": f"attachment://{os.path.basename(screenshot_path)}"}

            for webhook_url in urls:
                try:
                    embed_copy = dict(embed)
                    if screenshot_path and os.path.isfile(screenshot_path):
                        with open(screenshot_path, "rb") as img_file:
                            files = {"file": (os.path.basename(screenshot_path), img_file, "image/png")}
                            data = {"payload_json": json.dumps({"content": content, "embeds": [embed_copy]})}
                            response = safe_post(webhook_url, data=data, files=files, timeout=15)
                    else:
                        payload = {"content": content, "embeds": [embed_copy]}
                        response = safe_post(webhook_url, json=payload, timeout=10)
                    response.raise_for_status()
                    self.append_log(f"Eden OCR webhook sent")
                except requests.exceptions.RequestException as e:
                    self.append_log(f"Failed to send Eden OCR webhook: {e}")
        except Exception as e:
            self.error_logging(e, "Error in send_eden_ocr_webhook")

    def _mm_download_thumbnail(self, thumb_url: str, biome: str) -> str | None:
        """
        Download a biome thumbnail from a URL and save it locally.
        Returns the local file path on success, None on failure.
        """
        if not thumb_url or not isinstance(thumb_url, str):
            return None
        try:
            # Use safe_get with timeout to download the thumbnail
            from biome_tracker.base_support import safe_get
            response = safe_get(thumb_url, timeout=10)
            if not response or not response.ok:
                return None
            # Save to a temporary file
            import tempfile
            import os
            ext = os.path.splitext(thumb_url)[1]
            if not ext:
                ext = ".png"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(response.content)
                return tmp.name
        except Exception as e:
            self.append_log(f"Failed to download thumbnail for {biome}: {e}")
            return None
