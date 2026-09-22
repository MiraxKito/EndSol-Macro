"""
EndSol Macro — single source of truth for default configuration.

This module defines every configurable parameter with a sensible, working
default value. When a user runs the macro for the first time, this dict
is copied verbatim to %LOCALAPPDATA%/EndSolMacro/config.json and becomes
the user's local config. The user can then modify anything through the
panel; only the local file is mutated.

Rules:
- webhook_urls, private_server_link, user_id, accounts, cookies, roblox_username
  start EMPTY (must be filled by the user). They are personal data.
- Everything else has a working default that runs the macro out of the box
  (within Roblox coordinate calibration that the user still must do).
- Coordinates default to 0/0; the macro will warn until the user calibrates.
"""

# Master default config. Keep in sync with ConfigVar definitions in
# mixin_lifecycle.py / mixin_config.py / mixin_legacy_ui_fallback.py.
DEFAULT_CONFIG: dict = {
    # ── Webhook / Private server (user must fill) ────────────────────
    "webhook_urls": [],                 # list[str] — Discord webhook URLs
    "webhook_url": [],                  # legacy alias; preserved for old configs
    "private_server_link": "",          # str — Sol's RNG private server invite
    "roblox_username": "",              # str — main account username (filter)
    "user_id": "",                      # str — Discord user ID for pings
    "ping_minimum": "100000",        # minimum rarity to ping

    # ── Anti-AFK ──────────────────────────────────────────────────────
    "anti_afk": True,
    "anti_afk_interval": "5",
    "auto_roblox_fullscreen": False,
    "rare_biome_confirmation_popup": False,
    "auto_chat_close": True,

    # ── Auto-pop buffs (Glitched/Dreamspace) ─────────────────────────
    "enable_buff_glitched": False,
    "auto_pop_glitched": False,
    "auto_pop_biomes": {},              # filled at runtime
    # ── Biome randomizer / Strange controller ────────────────────────
    "biome_randomizer": False,
    "br_duration": "30",
    "strange_controller": False,
    "sc_duration": "15",
    "disabled_biomes_br_sc": [],

    # ── Rare biome actions ───────────────────────────────────────────
    "reset_on_rare": False,
    "teleport_back_to_limbo": False,

    # ── Auto-reconnect ──────────────────────────────────────────────
    "auto_reconnect": False,
    # Panel UI language ("en" | "ru") - set from Other Features -> System Settings.
    "panel_language": "en",
    # Silent-disconnect watchdog threshold (seconds of Roblox log silence).
    "auto_reconnect_interval": "30",

    # ── Idle mode / Auto-start ───────────────────────────────────────
    "enable_idle_mode": False,
    "auto_start_on_idle": False,
    "auto_start_idle_minutes": 15,

    # ── Quest reroll / claim ─────────────────────────────────────────
    "auto_claim_interval": "30",
    # ── Obby pathing ─────────────────────────────────────────────────
    "enable_obby_path": False,
    "obby_claim_interval": "15",
    "non_vip_movement_path": False,

    # ── Eden / Eden OCR / Eden contract ──────────────────────────────
    "eden_user_id": "",
    "eden_check_interval": "2",
    "eden_path_interval": "35",
    "go_to_eden_spawn": False,
    "auto_eden_contract": False,
    "eden_contract_button": [746, 931],
    "eden_contract_interval": "3",

    # ── Merchant ─────────────────────────────────────────────────────
    "ping_jester": False,
    "ping_mari": False,
    "ping_eden": False,
    "jester_user_id": "",
    "jester_exchange_button": [638, 660],
    "jester_exchange_count": 0,
    "enable_jester_exchange": False,
    "jester_exchange_threshold": "3",
    "jester_exchange_scroll_amount": 6,
    "Jester_Exchange_Items": {},

    # ── Fishing ──────────────────────────────────────────────────────
    "fishing_mode": False,
    "fishing_ui_nav_close": False,
    "fishing_sell_after_x_fish": "30",
    "fishing_sell_how_many_fish": "1",
    "fishing_use_merchant_every_x_fish": False,
    "fishing_merchant_every_x_fish": "30",
    "fishing_use_br_sc_every_x_fish": False,
    "fishing_br_sc_every_x_fish": "30",
    "fishing_actions_delay_ms": "100",
    "fishing_playback_multiplier": 1.0,
    "fishing_equip_aura_before_movement": False,
    "fishing_movement_aura_name": "",
    "fishing_failsafe_rejoin": False,
    "fishing_enable_selling": False,
    "merchant_teleporter": False,
    "mt_duration": "1",
    # ── Egg collect ──────────────────────────────────────────────────
    "collect_easter_egg": False,
    "egg_collect_interval_min": "30",
    "egg_playback_multiplier": 1.0,
    "egg_ocr_detect_special": False,
    "egg_ocr_discord_userid": "",

    # ── Potion crafting / switching ─────────────────────────────────
    "enable_potion_crafting": False,
    "enable_potion_switching": False,
    "potion_switch_interval": "60",
    "potion_last_file": "",
    "potion_file_1": "",
    "potion_file_2": "",
    "potion_file_3": "",

    # ── Aura detection / record ─────────────────────────────────────
    "enable_aura_detection": False,
    "enable_aura_record": False,
    "aura_record_keybind": "shift + F8",
    "aura_record_minimum": "200000",
    "aura_webhook_minimum_rarity": "0",
    "aura_menu": [28, 401],
    "aura_search_bar": [809, 361],
    "aura_user_id": "",
    "force_ping_auras": "",
    "gamepass_vip": False,
    "force_record_auras": "",
    "equip_aura_button": [623, 637],
    "first_aura_slot_pos": [821, 437],
    "first_item_inventory_slot_pos": [846, 480],
    "first_item_merchant_slot_pos": [952, 719],
    "first_item_slot_ocr_pos": [805, 433, 87, 89],
    "item_name_ocr_pos": [1104, 368, 369, 35],
    "inventory_click_delay": "0",
    "inventory_close_button": [1413, 301],
    "inventory_menu": [32, 515],
    "items_tab": [1272, 337],
    # ── Misc toggles ────────────────────────────────────────────────
    "enable_ocr_failsafe": False,
    "enable_glitch_effect": False,
    "azerty_mode": False,

    # ── Periodic screenshots ─────────────────────────────────────────
    "aura_detection_screenshot": False,
    "periodical_aura_interval": "25",
    "periodical_aura_screenshot": False,
    "periodical_inventory_interval": "25",
    "periodical_inventory_screenshot": False,
    "auto_claim_interval": "30",

    # ── Multiple-Instances (opt-in) ───────────────────────────────────
    "multiple_instances_enabled": False,
    "custom_webhook_messages": {},

    # ── Selected safe built-in calibration template ───────────────────
    "calibration_preset_resolution": "1920x1080",
    "calibration_preset_scale": "100%",
    "calibration_preset_mode": "Fullscreen",

    # ── Coordinates (calibrated for 1920x1080, 100% scale, fullscreen Roblox) ──
    "amount_box": [566, 577],
    "claim_quest_button": [618, 770],
    "collections_button": [35, 463],
    "exit_collections_button": [386, 126],
    "chat_hover_pos": [70, 192],
    "chat_tab_ocr_pos": [242, 62, 241, 40],
    "chat_close_button": [140, 35],
    "chat_box_ocr_pos": [8, 101, 474, 269],
    "rare_biome_record_keybind": "shift + F8",
    "player_logger": True,

    # ── Fishing calibration (calibrated for 1920x1080) ─────────────────
    "fishing_bar_region": [757, 762, 405, 21],
    "fishing_detect_pixel": [1176, 836],
    "fishing_click_position": [862, 843],
    "fishing_midbar_sample_pos": [955, 767],
    "fishing_close_button_pos": [1113, 342],
    "fishing_flarg_dialogue_box": [1046, 782],
    "fishing_shop_open_button": [616, 938],
    "fishing_shop_sell_tab": [1285, 312],
    "fishing_shop_close_button": [1458, 269],
    "fishing_shop_first_fish": [827, 404],
    "fishing_shop_sell_all_button": [662, 799],
    "fishing_confirm_sell_all_button": [800, 619],
    # ── Memory Match (Eon 1-2+; Summer 2026 active) ──────────────────
    "memory_match_enabled": False,
    "memory_match_play_on_fishing": True,
    "memory_match_cell_padding": 4,
    "memory_match_grid_region": [779, 322, 534, 461],
    "memory_match_start_button": [963, 608],
    "memory_match_close_button": [946, 817],
    "memory_match_playback_multiplier": 1.0,
    "memory_match_last_played": "",

    # ── Quest Board (passive self-sufficient quests) ─────────────────
    "quest_board_enabled": False,
    "quest_board_check_interval_minutes": 15,
    "quest_board_auto_accept": True,
    "quest_board_play_with_fishing": True,
    "quest_board_close_button": [959, 935],
    "quest_board_dismiss_button": [1781, 820],
    "quest_board_last_roll_rarity": 0,
    "quest_board_last_breakthrough_biome": "",
    "quest_board_session_minutes": 0.0,

    # ── Rare-biome screenshot (recording) — OFF by default ───────────
    "record_rare_biome": False,
    "rare_biome_screenshot": False,
    "rare_biome_screenshot_path": "",
    # ── Biome notifier (all 24 biomes default to "Message") ─────────
    "biome_notifier": {
        "CORRUPTION": "Message", "CYBERSPACE": "Message", "DREAMSPACE": "Message",
        "GLITCHED": "Message", "HELL": "Message", "NORMAL": "Message", "NULL": "Message",
        "RAINY": "Message", "SAND STORM": "Message", "SNOWY": "Message",
        "STARFALL": "Message", "WINDY": "Message", "HEAVEN": "Message",
        "AURORA": "Message", "EGGLAND": "Message", "BLAZING SUN": "Message",
        "PUMPKIN MOON": "Message", "GRAVEYARD": "Message", "BLOOD RAIN": "Message",
        "SINGULARITY": "Message",
        "THE HYPERSPACE REALM": "Message", "\u8d64\u3044\u6e80\u6708": "Message",
        "THE NULL'S EXISTENCE": "Message", "THE CITADEL OF ORDERS": "Message",
    },
    "biome_pings": {
        "GLITCHED": {"id": "everyone", "type": "userid"},
        "DREAMSPACE": {"id": "everyone", "type": "userid"},
        "CYBERSPACE": {"id": "everyone", "type": "userid"},
    },

    # ── Merchant (Mari / Jester / Rin items) ─────────────────────────
    "Mari_Items": {
        "Gear A": [False, 1, False],
        "Gear B": [False, 1, False],
        "Lucky Penny": [False, 1, False],
        "Lucky Potion": [False, 1, False],
        "Lucky Potion L": [False, 1, False],
        "Lucky Potion XL": [False, 1, False],
        "Mixed Potion": [False, 1, False],
        "Speed Potion": [False, 1, False],
        "Speed Potion L": [False, 1, False],
        "Speed Potion XL": [False, 1, False],
        "Void Coin": [False, 1, False],
    },
    "Jester_Items": {
        "Heavenly Potion": [False, 1, False],
        "Lucky Potion": [False, 1, False],
        "Oblivion Potion": [False, 1, False],
        "Potion of bound": [False, 1, False],
        "Random Potion Sack": [False, 1, False],
        "Rune Of Corruption": [False, 1, False],
        "Rune Of Hell": [False, 1, False],
        "Rune of Dust": [False, 1, False],
        "Rune of Everything": [False, 1, False],
        "Rune of Frost": [False, 1, False],
        "Rune of Galaxy": [False, 1, False],
        "Rune of Nothing": [False, 1, False],
        "Rune of Rainstorm": [False, 1, False],
        "Rune of Wind": [False, 1, False],
        "Speed Potion": [False, 1, False],
        "Stella's Candle": [False, 1, False],
        "Strange Potion": [False, 1, False],
    },
    "Rin_Items": {
        "Day and Night Talisman": [False, 1, False],
        "Moonstone Talisman": [False, 1, False],
        "Overtime Talisman": [False, 1, False],
        "Soul Collector's Talisman": [False, 1, False],
        "Soul Master's Talisman": [False, 1, False],
        "Sunstone Talisman": [False, 1, False],
    },
    "auto_buff_glitched": {
        "Fortune Potion I": [False, 1],
        "Fortune Potion II": [False, 1],
        "Fortune Potion III": [False, 1],
        "Godlike Potion": [False, 1],
        "Haste Potion I": [False, 1],
        "Haste Potion II": [False, 1],
        "Haste Potion III": [False, 1],
        "Heavenly Potion": [False, 1],
        "Lucky Potion": [False, 1],
        "Oblivion Potion": [False, 1],
        "Potion of bound": [False, 1],
        "Speed Potion": [False, 1],
        "Stella's Candle": [False, 1],
        "Strange Potion I": [False, 1],
        "Strange Potion II": [False, 1],
        "Transcendent Potion": [False, 1],
        "Warp Potion": [False, 1],
        "Xyz Potion": [False, 1],
    },

    # ── Auto-update flags ────────────────────────────────────────────
    "auto_update_enabled": False,
    "auto_update_biome_data": True,
    "auto_update_biome_aura_data": True,
    "custom_auto_pop_buffs": [],   # user-added buff item names for auto-pop
    "dont_ask_for_update": True,

    # ── Memory / tick rate ───────────────────────────────────────────
    "merchant_dialogue_box": [768, 836],
    "merchant_name_ocr_pos": [730, 683, 276, 52],
    "merchant_open_button": [654, 946],
    "merchant_counts": {"Jester": 0, "Mari": 0, "Rin": 0},
    "merchant_extra_slot": "0",
    "jester_exchange_count": 0,
    "last_jester_exchange_time": "",
    "last_merchant_visit": "",
    "last_fishing_session_at": "",

    # ── Stats / runtime counters (initially empty / zero) ────────────
    "session_time": "00:00:00",
    "session_window_start": "",
    "macro_last_start": "",
    "biome_counts": {},
    "aura_counts": {},
    "merchants_found": {},
    "total_fish_caught": 0,
    "total_auras_detected": 0,
    "total_biomes_found": 0,
    "last_anti_afk": "",
    "last_anti_afk_at": "",
    "last_disconnect_at": "",
    "last_aura_roll_time": "",
    "last_biome_change_time": "",
    "last_eden_at": "",

    # ── Window size / resolution hint (informational) ────────────────
    # ── Rune biome-native auras toggle ───────────────────────────────
    # ── Daily (event) Rewards ─────────────────────────────────────────
    "collect_daily_event_checkin": False,
    "daily_event_check_button": [959, 665],
    "daily_event_close_button": [1417, 396],
    "daily_event_popup_region": [867, 384, 187, 25],
    "daily_event_claimed_date": "",
    "auto_claim_daily_quests": False,

    # ── Item usage / limbo helpers ────────────────────────────────────
    "teleport_portable_crack": False,
    "portable_crack_interval": "3",
    "eden_detection": False,
    "reconnect_start_button": [244, 1003],
    "macro_idle_mode": False,

    # ── Merchants ─────────────────────────────────────────────────────
    "merchant_ocr": False,
    "merchant_ocr_interval": "60",
    "auto_merchant_in_limbo": False,
    "mari_user_id": "",
    "rin_user_id": "",
    "ping_rin": False,
    "autobuy_set_to_max_button": [1000, 446],
    "jester_exchange_set_to_max_button": [1220, 445],
    "first_item_merchant_slot_pos": [952, 719],
    "merchant_close_button": [1809, 346],
    # ── Inventory / items calibrations ────────────────────────────────
    "search_bar": [828, 369],
    "first_item_inventory_slot_pos": [846, 480],
    "amount_box": [566, 577],
    "use_button": [687, 581],
    "glitched_menu_button": [37, 674],
    "glitched_settings_button": [951, 584],
    "glitched_buff_enable_button": [927, 654],
    # ── Quests (daily quest claim + reroll + Quest Board controls) ────
    "claim_quest_button": [618, 770],
    "quest_menu": [38, 624],
    "quest1_button": [1100, 524],
    "quest2_button": [1104, 595],
    "quest3_button": [1101, 677],
    "quest_reroll_button": [623, 585],
    "quest_board_ocr_region": [1513, 267, 354, 55],
    "quest_board_accept_button": [1587, 822],
    "quest_board_claim_button": [1604, 817],
    "quest_board_left_arrow": [565, 544],
    "quest_board_right_arrow": [1362, 541],
    "quest_board_quest_preferences": {},

    # ── Remote access (Discord bot) ───────────────────────────────────
    "remote_access_enabled": False,
    "remote_allowed_user_id": "",
    "remote_bot_token": "",

    # ── Customization ─────────────────────────────────────────────────
    "selected_theme": "solar",
    "custom_background_image": "",
    "custom_rare_biome_overrides": {},

    # ── Auto Pop (dreamspace/cyberspace variants) ─────────────────────
    "auto_pop_dreamspace": False,
    "auto_pop_cyberspace": False,
    "cyberspace_only_warp": False,

    # ── Potions ───────────────────────────────────────────────────────
    "selected_potion_file": "",
    "potion_items_tab": [1507, 227],
    "potion_search_bar": [1448, 264],
    "potion_first_potion_slot_pos": [1512, 332],
    "potion_recipe_button": [200, 815],
    "potion_auto_button": [424, 821],
    "potion_auto_add_button": [426, 813],
    # ── Platform flags ────────────────────────────────────────────────
    "vip": False,
    "has_gamepass": False,

    # ── Movement features ─────────────────────────────────────────────
    "enable_snowman_path": False,
    "snowman_claim_interval": "15",
    "use_float_aura": False,
    "float_aura_name": "",

    # ── Fishing tunables (Fandom-index independent) ───────────────────
    "fishing_use_merchant_ocr_every_x_fish": False,
    "fishing_merchant_ocr_every_x_fish_amt": "30",
    "fishing_movement_aura_delay_seconds": "0.67",
    "fishing_click_burst": 2,
    "fishing_reel_loop_sleep": 0.004,
    "fishing_idle_poll_sleep": 0.004,
    "fishing_pre_reel_wait": 0.18,
    "fishing_bar_color_tolerance": 12,
    "fishing_bar_scan_height": 3,

    # ── Egg collection extras ─────────────────────────────────────────
    "egg_click_failsafe": [],
    "egg_collect_aura_name": "",
    "equip_aura_before_egg_collect": False,

    # ── OCR / misc internals ──────────────────────────────────────────
    "ocr_failsafe_match_threshold": 0.7,
    "player_log_send_delay": 2.0,
    "auto_update_biome_data": True,
    "auto_update_biome_aura_data": True,
    "custom_biome_overrides": {},
    "purchase_amount_button": [1044, 611],
    "purchase_button": [982, 666],
    "potion_file2": "",
    "potion_file3": "",
    "merchant_close_button_pos": [1811, 325],
}


def get_default_config() -> dict:
    """Return a deep copy of the default config so callers can't mutate it."""
    import copy
    return copy.deepcopy(DEFAULT_CONFIG)
