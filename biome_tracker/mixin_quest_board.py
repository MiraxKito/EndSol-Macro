"""
Quest Board auto-claim/auto-accept mixin for EndSol Macro.

Sol's RNG Quest Board (added Eon 1-4.5, May 2025):
  - 5 quests on the board, 3 active at once
  - New quest appears every hour automatically
  - Quest categories: Basic, Uncommon, Epic, Legendary, Mythic, Tutorial, Special, Fishing, Resonance
  - 8 quest types (rolls, fish, kill, etc)

This module focuses on SELF-SUFFICIENT quests that complete automatically through
the macro's normal activity (rolling, biome changes, breakthrough). It does NOT
handle quests that require special actions (going to NPC, killing players, fishing,
delivering items, etc.) — those need additional automation not in scope here.

Self-sufficient quest types we accept:
  - Meditation I/II           (just play for 10/30 min — natural via rolling)
  - Basic/Epic/Unique/Legendary/Mythic Hunt (roll a specific aura tier — natural)
  - Windy/Snowy/Rainy Breakthrough (roll a breakthrough during that biome)
  - Sandstorm/Hell/Starfall Breakthrough (same)
  - Corruption/Null Breakthrough (same)

The board itself has fixed positions for its 5 quest slots; this module relies
on the user calibrating those positions in Macro Calibrations.
"""

import time
import re
import os
import json
from datetime import datetime, timedelta

import autoit


# Quest type registry. Each group maps to a config preference key stored in
# quest_board_quest_preferences: {"meditation": "accept"|"dismiss", ...}.
# Groups not present in the config use DEFAULT_QUEST_ACTIONS, which reproduces
# the original hardcoded accept/deny behaviour.
QUEST_TYPES = [
    {
        "id": "meditation",
        "label": "Meditation (I/II)",
        "patterns": [r"\bmeditation\b"],
        "deny_if_plain": r"\bmeditation\b(?!.*\b(i|ii|1|2)\b)",  # only I/II
    },
    {"id": "basic_hunt", "label": "Basic Hunt", "patterns": [r"\bbasic\s*hunt\b"]},
    {"id": "epic_hunt", "label": "Epic Hunt", "patterns": [r"\bepic\s*hunt\b"]},
    {"id": "unique_hunt", "label": "Unique Hunt", "patterns": [r"\bunique\s*hunt\b"]},
    {"id": "legendary_hunt", "label": "Legendary Hunt", "patterns": [r"\blegendary\s*hunt\b"]},
    {"id": "mythic_hunt", "label": "Mythic Hunt", "patterns": [r"\bmythic\s*hunt\b"]},
    {"id": "breakthrough", "label": "Breakthrough (any biome)", "patterns": [
        r"\b\w+\s*breakthrough\b",      # "Windy Breakthrough" (clean read)
        r"\bbreak\s*through\b",         # OCR split the word
        r"\bbreakth\w*",                # OCR truncated: "Breakthrou", "Breakthru"
        r"\bbreak\w*",                  # worst-case truncation: "Break…"
        r"\bbrea?[a-z0-9<>|!\.\[\]()_\-]{0,4}through\b",
        # OCR heavily damaged the middle of "breakthrough" ("breol<through",
        # "brekthrough", "breolthrough") - match bre + a few junk chars + through
    ]},
    # Fishing quests (require the fishing automation to complete)
    {"id": "fishing", "label": "Fishing (Catch X / Angler / Fisher)", "patterns": [
        r"\bcatch\s*\d+\b", r"\bcatch\s*5\b", r"\briver\s*angler\b",
        r"\bminnow\s*rookie\b", r"\bdeep[\s\-]?sea\s*hunter\b", r"\blegendary\s*fisher\b",
    ]},
    # NOTE: "Player Hunt" is intentionally NOT a configurable type — it can
    # never be automated (requires killing players) and is always dismissed
    # (hard rule in _qb_quest_action + DENY_PATTERNS below).
    {"id": "delivery", "label": "Delivery I-V (give items to NPC)", "patterns": [r"\bdelivery\b"]},
    {"id": "resonance", "label": "Resonance of X (grail offering)", "patterns": [r"\bresonance\s*of\b"]},
    {"id": "npc_visit", "label": "NPC / Location visits", "patterns": [
        r"\bfinding\s*a\s*person\b", r"\bto\s*the\s*temple\b", r"\bhidden\s*cave\b",
        r"\brumors?\s*about\s*a\s*witch\b",
    ]},
    {"id": "tutorial", "label": "Tutorial / First-time quests", "patterns": [
        r"\btutorial\b", r"\byour\s*(first|second)\b", r"\byou.?re\s*rollin\b",
        r"\brumors?\b", r"\brare\s*auras\b", r"\bpotion\s*craft\b", r"\baura\s*filters\b",
        r"\brolling\s*in\s*the\s*deep\b", r"\bsymbol\s*of\s*luck\b",
    ]},
]

# Quest tier/variant helpers. Quests on the board are the same TYPE in
# different tiers/variants (Delivery I-V, Resonance of X, Windy Breakthrough,
# River Angler, ...) and they appear in RANDOM slots — the slot position is
# meaningless. The user selects which TIERS they want instead.
_ROMAN = {"I": 1, "II": 2, "III": 3, "IV": 4, "V": 5}


def _quest_variant(qtype: str, name: str) -> str:
    """Extract the tier/variant key from an OCR'd quest name ("Delivery IV" -> "IV")."""
    n = (name or "").lower().strip()
    try:
        if qtype == "delivery":
            m = re.search(r"\bdelivery\s*([ivx]{1,6})\b", n)
            if m:
                rom = m.group(1).upper()
                return rom if rom in _ROMAN else ""
            return ""
        if qtype == "meditation":
            m = re.search(r"\bmeditation\s*([ivx]{1,6})\b", n)
            if m:
                rom = m.group(1).upper()
                return rom if rom in _ROMAN else ""
            return ""
        if qtype == "resonance":
            m = re.search(r"\bresonance\s*of\s*([a-z][a-z ]{2,20})", n)
            return m.group(1).strip().title() if m else ""
        if qtype == "breakthrough":
            # Quest names differ per biome ("Windy Breakthrough", "Corruption
            # Breakthrough", sometimes "Breakthrough in Rainy" after an OCR
            # line-wrap), so scan the WHOLE name for a known biome word —
            # fuzzily, because OCR garbles them ("vvindy", "sand storn").
            import difflib

            squeeze = re.sub(r"[^a-z]", "", n)
            best_key, best_ratio = "", 0.0
            for biome_key in BREAKTHROUGH_BIOMES:
                probe = biome_key.replace(" ", "")
                if not probe:
                    continue
                if probe in squeeze:
                    return biome_key.title() if biome_key != "sand storm" else "Sandstorm"
                # windowed fuzzy compare against each word and word pairs
                words = n.split()
                for i in range(len(words)):
                    for j in (i, i + 1):
                        window = " ".join(words[i:j + 1])
                        ratio = difflib.SequenceMatcher(None, window, biome_key).ratio()
                        if ratio > best_ratio:
                            best_key, best_ratio = biome_key, ratio
            if best_ratio >= 0.72:
                return best_key.title() if best_key != "sand storm" else "Sandstorm"
            # Fallbacks for exotic layouts: biome word(s) before "break…"
            m = re.search(r"\b([a-z][a-z ]{2,20}?)\s*break", n)
            if m:
                return m.group(1).strip().title()
            m = re.search(r"\b([a-z]{3,20}?)break", n)
            if m:
                return m.group(1).title()
            return ""
        if qtype == "fishing":
            if re.search(r"\briver\s*angler\b", n):
                return "River Angler"
            if re.search(r"\bminnow\s*rookie\b", n):
                return "Minnow Rookie"
            if re.search(r"\bdeep[\s\-]?sea\s*hunter\b", n):
                return "Deep-Sea Hunter"
            if re.search(r"\blegendary\s*fisher\b", n):
                return "Legendary Fisher"
            return ""
    except Exception:
        return ""
    return ""


def _quest_variant_options(qtype: str) -> list:
    """The canonical variant list offered in the UI for a quest type."""
    return {
        "delivery": ["I", "II", "III", "IV", "V"],
        "meditation": ["I", "II"],
        "resonance": ["Wind", "Frost", "Sea", "Sand", "Flame", "Star", "Corruption", "Darkness"],
        "breakthrough": ["Windy", "Snowy", "Rainy", "Sandstorm", "Hell", "Starfall", "Corruption", "Null"],
        "fishing": ["River Angler", "Minnow Rookie", "Deep-Sea Hunter", "Legendary Fisher"],
    }.get(qtype, [])

# Default action per quest type when the user preference is not set
# (explicit — no fragile list-index slicing).
DEFAULT_QUEST_ACTIONS = {
    "meditation": "accept",     # playtime — completes itself while AFK
    "basic_hunt": "accept",     # aura hunts — the macro's rolling completes them
    "epic_hunt": "accept",
    "unique_hunt": "accept",
    "legendary_hunt": "accept",
    "mythic_hunt": "accept",
    "breakthrough": "accept",   # biome breakthrough — completed by rolling
    "fishing": "dismiss",       # enable together with the fishing automation
    "delivery": "dismiss",      # needs item delivery (path + items)
    "resonance": "dismiss",     # needs a Grail offering (path + item)
    "npc_visit": "dismiss",     # one-time story quests
    "tutorial": "dismiss",
}

# Kept for backwards compatibility (used by tests / external callers).
ACCEPTABLE_QUEST_PATTERNS = [pat for qt in QUEST_TYPES if DEFAULT_QUEST_ACTIONS[qt["id"]] == "accept" for pat in qt["patterns"]]

# Automations that do not exist yet. Quests of these types are ALWAYS dismissed,
# regardless of stored prefs (protects against stale configs with accept).
# Remove a type from this set when its automation ships — the MiscPage row
# (HIDDEN_QUEST_TYPES) is unhidden at the same time. Delivery keeps its I–V
# tier picker wired in the config, so it starts applying the moment this
# set is emptied.
NOT_IMPLEMENTED_QUEST_TYPES = {"fishing", "delivery", "resonance"}

DENY_PATTERNS = [
    r"\bplayer\s*hunt\b",          # requires killing players
    r"\bdelivery\b",                # requires giving items to NPC
    r"\bresonance\s*of\b",          # requires grail offering
    r"\bfinding\s*a\s*person\b",   # requires talking to specific NPC
    r"\bcatch\s*\d+\b",             # fishing quests
    r"\bcatch\s*5\b",
    r"\briver\s*angler\b",
    r"\bminnow\s*rookie\b",
    r"\bdeep[\s\-]?sea\s*hunter\b",
    r"\blegendary\s*fisher\b",
    r"\bmeditation\b(?!.*\b(i|ii|1|2)\b)",  # only allow I/II
    r"\btutorial\b",
    r"\bto\s*the\s*temple\b",
    r"\byour\s*(first|second)\b",
    r"\bhidden\s*cave\b",
    r"\byou.?re\s*rollin\b",
    r"\brumors?\b",
    r"\brare\s*auras\b",
    r"\bpotion\s*craft\b",
    r"\baura\s*filters\b",
    r"\brolling\s*in\s*the\s*deep\b",
    r"\bsymbol\s*of\s*luck\b",
]


def _match_quest_type(name: str) -> str:
    """Return the quest type id that matches the OCR'd name, or "" if unknown."""
    if not name:
        return ""
    for qt in QUEST_TYPES:
        for pat in qt["patterns"]:
            if re.search(pat, name):
                return qt["id"]
    return ""


def _is_acceptable_quest(name: str) -> bool:
    """Return True if this quest is one we can passively complete (no prefs)."""
    if not name:
        return False
    n = name.lower()
    # Deny first (more specific)
    for pat in DENY_PATTERNS:
        if re.search(pat, n):
            return False
    # Then check acceptable
    for pat in ACCEPTABLE_QUEST_PATTERNS:
        if re.search(pat, n):
            return True
    return False


# Breakthrough biomes the macro can check for quest progress
BREAKTHROUGH_BIOMES = {
    "windy":  "windy breakthrough",
    "snowy":  "snowy breakthrough",
    "rainy":  "rainy breakthrough",
    "sand storm": "sandstorm breakthrough",
    "sandstorm": "sandstorm breakthrough",
    "hell":   "hell breakthrough",
    "starfall": "starfall breakthrough",
    "corruption": "corruption breakthrough",
    "null":   "null breakthrough",
}


class QuestBoardMixin:
    """
    Provides periodic Quest Board processing for Sol's RNG.

    Configuration keys (all in config.json):
        quest_board_enabled: bool
        quest_board_check_interval_minutes: float   (default 15)
        quest_board_auto_accept: bool               (default True)
        quest_board_play_with_fishing: bool         (default True)
        quest_board_5_slots: [[x,y], [x,y], [x,y], [x,y], [x,y]]   (5 quest slots)
        quest_board_claim_button: [x, y]            (post-completion Claim btn)
        quest_board_accept_button: [x, y]           (Accept btn on each quest)
        quest_board_quest_state: {quest_name: "active"|"completed"|"claimed"}
    """

    # ---- config helpers ----
    def _qb_get(self, key, default=None):
        try:
            cfg = getattr(self, "config", None) or {}
            return cfg.get(key, default)
        except Exception:
            return default

    def _qb_set(self, key, value):
        try:
            self.config[key] = value
            try:
                self.save_config()
            except Exception:
                pass
        except Exception:
            pass

    def qb_is_enabled(self) -> bool:
        return bool(self._qb_get("quest_board_enabled", False))

    def _qb_quest_action(self, quest_name: str) -> str:
        """
        Decide what to do with an OCR'd quest name: "accept" or "dismiss".

        Resolution order:
          1. Hard rule: "Player Hunt" is ALWAYS dismissed — it requires
             killing players and cannot be automated.
          2. quest_board_quest_preferences config: {quest_type_id: "accept"|"dismiss"}
          3. DEFAULT_QUEST_ACTIONS (explicit defaults, see above)
          4. Tier selection: for tiered types the user picks WHICH tiers are
             allowed via quest_board_variant_prefs ({type_id: ["I","II",...]});
             a quest whose tier is not selected (or whose tier OCR failed to
             read) is dismissed. Quests without a tier list take any tier.
          5. Unknown quests are dismissed.
        The plain "Meditation" (without I/II) tier stays dismiss-by-default even
        though it matches the meditation group.
        """
        try:
            n = (quest_name or "").lower()
            if not n:
                return "dismiss"
            if "player hunt" in n:
                return "dismiss"
            prefs = self._qb_get("quest_board_quest_preferences") or {}
            if not isinstance(prefs, dict):
                prefs = {}

            qtype = _match_quest_type(n)
            if qtype in NOT_IMPLEMENTED_QUEST_TYPES:
                # Fishing / Delivery / Resonance automations do not exist yet:
                # accepting such a quest would just block a board slot.
                return "dismiss"
            if qtype == "meditation":
                # Meditation III+ (plain "Meditation") was never acceptable.
                plain_med = re.search(r"\bmeditation\b(?!.*\b(i|ii|1|2)\b)", n)
                if plain_med and prefs.get("meditation") != "accept":
                    return "dismiss"

            if qtype in ("tutorial", "npc_visit"):
                # One-time story/tutorial quests must be done by the player
                # themselves; they cannot be enabled for automation.
                return "dismiss"
            if qtype:
                action = prefs.get(qtype)
                if action not in ("accept", "dismiss"):
                    action = DEFAULT_QUEST_ACTIONS.get(qtype, "dismiss")
                if action != "accept":
                    return "dismiss"
                # Tier selection: when the user narrowed the tiers for this
                # type, only the selected tiers are taken. OCR often garbles
                # the variant word ("vvindy", "sand storn", "windi"), so the
                # comparison is fuzzy (difflib) plus space-insensitive; a
                # variant that survives neither is dismissed WITH a log line
                # so a bad calibration is visible in the macro log.
                var_options = _quest_variant_options(qtype)
                if var_options:
                    var_prefs = self._qb_get("quest_board_variant_prefs") or {}
                    allowed = (var_prefs or {}).get(qtype)
                    if isinstance(allowed, (list, tuple)) and allowed:
                        allowed_norm = [str(v).strip().lower() for v in allowed]
                        variant = _quest_variant(qtype, n)
                        ok = False
                        if variant:
                            v = variant.lower()
                            if v in allowed_norm or v.replace(" ", "") in [a.replace(" ", "") for a in allowed_norm]:
                                ok = True
                            else:
                                import difflib
                                squeeze = [a.replace(" ", "") for a in allowed_norm]
                                close = difflib.get_close_matches(v, allowed_norm, n=1, cutoff=0.72) \
                                    or difflib.get_close_matches(v.replace(" ", ""), squeeze, n=1, cutoff=0.72)
                                ok = bool(close)
                        if not ok:
                            try:
                                self.append_log(
                                    f"[QuestBoard] {quest_name!r}: variant {variant!r} is not among "
                                    f"selected {allowed_norm} — dismissed (check the OCR region if the "
                                    f"quest type is correct)")
                            except Exception:
                                pass
                            return "dismiss"
                return "accept"

            # Unknown quest name — fall back to the built-in deny list, then dismiss.
            if _is_acceptable_quest(n):
                return "accept"
            return "dismiss"
        except Exception:
            # On any failure keep the original behaviour.
            return "accept" if _is_acceptable_quest(quest_name or "") else "dismiss"

    # ---- main periodic loop ----
    def quest_board_loop(self):
        """Background thread: periodically scan the Quest Board and process quests."""
        try:
            last_check: datetime = datetime.min
            while getattr(self, "detection_running", False):
                try:
                    if not self.qb_is_enabled():
                        time.sleep(10)
                        continue
                    try:
                        interval = float(self._qb_get("quest_board_check_interval_minutes", 15))
                    except Exception:
                        interval = 15.0
                    if (datetime.now() - last_check) < timedelta(minutes=interval):
                        time.sleep(5)
                        continue
                    # Respect fishing integration
                    play_with_fishing = bool(self._qb_get("quest_board_play_with_fishing", True))
                    if (not play_with_fishing) and self._is_fishing_active():
                        time.sleep(30)
                        continue
                    # Don't run if other exclusive features are active
                    if (getattr(self, "_egg_collecting", False) or
                        getattr(self, "_eden_running", False) or
                        getattr(self, "_potion_thread_active", False) or
                        getattr(self, "_obby_running", False) or
                        getattr(self, "_br_sc_running", False)):
                        time.sleep(10)
                        continue
                    if not getattr(self, "detection_running", False):
                        break
                    # Schedule the processing via action scheduler
                    try:
                        self._action_scheduler.enqueue_action(
                            self._qb_process_via_scheduler,
                            name="quest_board:process",
                            priority=4,
                        )
                    except Exception:
                        pass
                    last_check = datetime.now()
                except Exception as e:
                    try:
                        self.error_logging(e, "quest_board_loop error")
                    except Exception:
                        pass
                    time.sleep(30)
        except Exception:
            pass

    def _qb_process_via_scheduler(self):
        """Wrapper that runs the board processing in scheduler context."""
        try:
            res = self.process_quest_board()
            try:
                if isinstance(res, dict) and res.get("action"):
                    self.append_log(f"[QuestBoard] {res.get('action')}: {res.get('detail', '')}")
            except Exception:
                pass
        except Exception as e:
            try:
                self.error_logging(e, "_qb_process_via_scheduler")
            except Exception:
                pass

    def process_quest_board(self) -> dict:
        """
        One pass over the Quest Board:
          1. Walk to the board (if path configured) and press E to open it.
          2. For each of the 5 quest slots (navigate via left/right arrows):
             a. OCR the quest name region.
             b. If quest is completed (Claim visible): click Claim button.
             c. If quest is unwanted: click Dismiss button.
             d. If quest is acceptable and auto_accept is on: click Accept button.
          3. Close the board.
        """
        out = {"action": "ok", "detail": "", "claimed": 0, "accepted": 0, "dismissed": 0}
        if not getattr(self, "detection_running", False):
            out["action"] = "skipped"
            return out

        ocr_region = self._qb_get("quest_board_ocr_region")
        accept_btn = self._qb_get("quest_board_accept_button")
        claim_btn = self._qb_get("quest_board_claim_button")
        dismiss_btn = self._qb_get("quest_board_dismiss_button")
        left_arrow = self._qb_get("quest_board_left_arrow")
        right_arrow = self._qb_get("quest_board_right_arrow")

        if not ocr_region or len(ocr_region) != 4:
            out["action"] = "skipped"
            out["detail"] = "OCR region not calibrated"
            return out
        if not accept_btn or not claim_btn or not dismiss_btn:
            out["action"] = "skipped"
            out["detail"] = "Accept/Claim/Dismiss buttons not calibrated"
            return out

        # 0. Deterministic prelude (blocking): activate Roblox, RESET the
        #    character, close leftover UI and align the camera — the exact
        #    same sequence Memory Match uses before walking, so the recorded
        #    path always starts from the same spawn state.
        try:
            if not self._feature_walk_prelude("QuestBoard"):
                out["action"] = "aborted"
                out["detail"] = "cancelled during prelude (macro stopped)"
                return out
        except Exception as e:
            try:
                self.error_logging(e, "QuestBoard prelude failed")
            except Exception:
                pass

        # 1. Walk to board + open it
        walk_ok = self._qb_walk_to_board()
        if not walk_ok:
            out["action"] = "aborted"
            out["detail"] = "could not walk to board"
            return out

        auto_accept = bool(self._qb_get("quest_board_auto_accept", True))
        active_count = 0

        try:
            # 2. Process each of 5 slots
            for slot_idx in range(5):
                if not getattr(self, "detection_running", False):
                    break

                # OCR the quest name
                quest_name = self._qb_ocr_quest_name(ocr_region)
                if not quest_name:
                    # Can't read quest — skip this slot (visible in the log so
                    # an empty/misplaced OCR calibration region is detectable)
                    try:
                        self.append_log(f"[QuestBoard] Slot {slot_idx + 1}: OCR read nothing — skipped")
                    except Exception:
                        pass
                    self._qb_click_arrow(right_arrow)
                    if not self._qb_sleep(0.6):
                        break
                    continue

                # Visible diagnostic: what the OCR actually read for this slot
                try:
                    self.append_log(f"[QuestBoard] Slot {slot_idx + 1} read: {quest_name!r}")
                except Exception:
                    pass

                # Check if this is a completed quest (has "Claim" or "Complete" text)
                is_completed = self._qb_check_claim_visible(ocr_region)
                if is_completed and claim_btn and claim_btn[0]:
                    try:
                        autoit.mouse_click("left", int(claim_btn[0]), int(claim_btn[1]), 1, speed=3)
                    except Exception:
                        pass
                    out["claimed"] += 1
                    try:
                        self.append_log(f"[QuestBoard] Claimed: {quest_name}")
                    except Exception:
                        pass
                    if not self._qb_sleep(0.8):
                        break
                    self._qb_click_arrow(right_arrow)
                    if not self._qb_sleep(0.6):
                        break
                    continue

                # Decide accept/dismiss from per-type user preferences and
                # the tier selection (Delivery I-V etc.); Player Hunt is
                # always dismissed.
                if self._qb_quest_action(quest_name) != "accept":
                    try:
                        autoit.mouse_click("left", int(dismiss_btn[0]), int(dismiss_btn[1]), 1, speed=3)
                    except Exception:
                        pass
                    out["dismissed"] += 1
                    try:
                        self.append_log(f"[QuestBoard] Dismissed: {quest_name}")
                    except Exception:
                        pass
                    if not self._qb_sleep(0.8):
                        break
                    self._qb_click_arrow(right_arrow)
                    if not self._qb_sleep(0.6):
                        break
                    continue

                # Check if quest is acceptable
                if auto_accept and active_count < 3:
                    try:
                        autoit.mouse_click("left", int(accept_btn[0]), int(accept_btn[1]), 1, speed=3)
                    except Exception:
                        pass
                    out["accepted"] += 1
                    active_count += 1
                    try:
                        self.append_log(f"[QuestBoard] Accepted: {quest_name}")
                    except Exception:
                        pass
                    if not self._qb_sleep(0.8):
                        break
                elif auto_accept:
                    # Acceptable quest but the macro already holds 3 — leave it
                    try:
                        self.append_log(f"[QuestBoard] Accept skipped (3 active slots): {quest_name}")
                    except Exception:
                        pass

                # Move to next slot
                self._qb_click_arrow(right_arrow)
                if not self._qb_sleep(0.6):
                    break

        finally:
            # 3. Close board
            self._qb_close_board()

        out["detail"] = f"accepted={out['accepted']}, dismissed={out['dismissed']}, claimed={out['claimed']}"
        return out

    # ---- movement / open / close helpers ----
    def _qb_walk_to_board(self) -> bool:
        """Walk to the Quest Board: custom path > bundled default path > E in place."""
        # Non-VIP characters walk slower — stretch movement timing the same
        # way the fishing paths do (non_vip_movement_path x1.22).
        try:
            from .fishing import NON_VIP_WALK_SPEED_MULTIPLIER
            _nv = float(NON_VIP_WALK_SPEED_MULTIPLIER)
        except Exception:
            _nv = 1.22
        try:
            walk_mult = _nv if bool(self.config.get("non_vip_movement_path", False)) else 1.0
        except Exception:
            walk_mult = 1.0

        # Try custom path first, then the bundled default path.
        events = []
        events_source = ""
        path_meta = None
        try:
            from .custom_path_manager import load_path_for_feature_meta
            events, path_meta = load_path_for_feature_meta("quest_board")
            if events:
                events_source = "custom path"
        except Exception:
            events = []
        if not events:
            try:
                from .mixin_memory_match import _load_path_file
                events = _load_path_file("quest_board.json") or []
                if events:
                    events_source = "default path"
            except Exception:
                events = []
        if events:
            try:
                from .mixin_memory_match import _replay_walk_path
                # Walk-speed stamp aware: custom paths recorded in the current
                # mode play as-is; legacy custom paths keep the old stretch.
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
                self.append_log(f"[QuestBoard] Walking to board via {events_source} "
                                f"({len(events)} events{', non-VIP speed' if walk_mult > 1.0 else ''})...")
                self.activate_roblox_window()
                if not self._qb_sleep(0.3):
                    return False
                should_continue = lambda: bool(getattr(self, "detection_running", False))
                can_run = lambda: True
                _replay_walk_path(events, self._qb_sleep, should_continue, can_run, walk_mult)
                if not should_continue():
                    return False
                # Press E after walking
                try:
                    autoit.send("e")
                except Exception:
                    pass
                if not self._qb_sleep(1.0):
                    return False
                return True
            except Exception:
                pass

        # No path at all — open the board through the game interaction key.
        # Press E is intentionally not a mouse calibration: it is keyboard input.
        self.activate_roblox_window()
        if not self._qb_sleep(0.3):
            return False
        try:
            autoit.send("e")
        except Exception:
            return False
        if not self._qb_sleep(1.0):
            return False
        return True

    def _qb_ocr_quest_name(self, ocr_region: list) -> str:
        """OCR the quest name from the calibrated region. Returns lowercased text."""
        try:
            x, y, w, h = int(ocr_region[0]), int(ocr_region[1]), int(ocr_region[2]), int(ocr_region[3])
            text = self.extract_text_winocr((x, y, w, h))
            # WinOCR splits names across lines ("Windy\nBreakthrough") —
            # collapse all whitespace so word-boundary matching works.
            return re.sub(r"\s+", " ", (text or "")).strip().lower()
        except Exception:
            return ""

    def _qb_check_claim_visible(self, ocr_region: list) -> bool:
        """Check if 'Claim' or 'Complete' text is visible near the quest (indicates quest is done)."""
        try:
            x, y, w, h = int(ocr_region[0]), int(ocr_region[1]), int(ocr_region[2]), int(ocr_region[3])
            # Extend OCR region downward to catch the Claim button area
            extended = (x, y + h - 20, w, 40)
            text = self.extract_text_winocr(extended)
            text = (text or "").strip().lower()
            return "claim" in text or "complete" in text or "completed" in text
        except Exception:
            return False

    def _qb_click_arrow(self, arrow_pos: list) -> None:
        """Click a navigation arrow (left or right) to switch quest view."""
        if not arrow_pos or len(arrow_pos) != 2 or not arrow_pos[0]:
            return
        try:
            autoit.mouse_click("left", int(arrow_pos[0]), int(arrow_pos[1]), 1, speed=3)
        except Exception:
            pass

    def _qb_close_board(self) -> None:
        try:
            close_btn = self._qb_get("quest_board_close_button")
            if close_btn and len(close_btn) == 2:
                autoit.mouse_click("left", int(close_btn[0]), int(close_btn[1]), 1, speed=3)
                self._qb_sleep(0.4)
        except Exception:
            pass

    def _qb_sleep(self, seconds: float, slice_len: float = 0.05) -> bool:
        end = time.time() + max(0.0, seconds)
        while time.time() < end:
            if not getattr(self, "detection_running", False):
                return False
            time.sleep(min(slice_len, end - time.time()))
        return True

    # ---- progress tracking helpers (called by other modules) ----
    def qb_notify_roll(self, aura_name: str = "", aura_rarity: int = 0):
        """
        Called after a successful roll. Used to advance quest progress for
        Hunt-style quests (Basic/Epic/Unique/Legendary/Mythic). Stores the
        last roll's tier in config so the quest board pass can verify a
        matching quest is likely completed.
        """
        try:
            self._qb_set("quest_board_last_roll_rarity", int(aura_rarity))
        except Exception:
            pass

    def qb_notify_breakthrough(self, biome: str = ""):
        """Called when a breakthrough roll is detected. Records the biome."""
        try:
            self._qb_set("quest_board_last_breakthrough_biome", str(biome))
        except Exception:
            pass

    def qb_notify_session_minutes(self, minutes: float):
        """Called by the meditation-like passive timer. Increments accumulator."""
        try:
            cur = float(self._qb_get("quest_board_session_minutes", 0.0))
            self._qb_set("quest_board_session_minutes", cur + float(minutes))
        except Exception:
            pass

    def _is_fishing_active(self) -> bool:
        try:
            return bool(self.is_fishing_mode_enabled())
        except Exception:
            return False


# Static helper for use in detection / actions modules
def is_breakthrough_biome(biome: str) -> bool:
    if not biome:
        return False
    return biome.lower() in BREAKTHROUGH_BIOMES
