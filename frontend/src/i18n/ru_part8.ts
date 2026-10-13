// Sol's Sim (sandbox) page. Keys are EXACT English source strings — the DOM
// auto-translator matches trimmed text nodes, so composed lines in the page
// are split into clean nodes. Game names (auras/biomes/gear) stay in English.

export const RU_P8: Record<string, string> = {
    // ── Header / landing ──
    "Sandbox of Sol's RNG — roll auras, watch biomes, wear gauntlets. Stats are saved locally; the biome never survives the session.":
        "Песочница Sol's RNG — крути ауры, следи за биомами, надевай перчатки. Статистика сохраняется локально; биом не переживает сессию.",
    "Runs only while this tab is active — switching tabs pauses it. Hiding or minimizing the panel window is fine.":
        "Работает только пока эта вкладка активна — переключение вкладок ставит на паузу. Скрывать или сворачивать окно панели можно.",
    "⏹ Close simulator": "⏹ Закрыть симулятор",
    "💾 Save now": "💾 Сохранить",
    "↻ Reload data": "↻ Обновить данные",
    "▶ Launch simulator": "▶ Запустить симулятор",
    "The simulator is closed": "Симулятор закрыт",
    "Nothing runs while it is closed — zero load. Press ": "Пока он закрыт, ничего не работает — нулевая нагрузка. Нажмите ",
    "Launch simulator": "Запустить симулятор",
    " to start a session. Biomes reset every session; rolls, unique auras and the drop log are kept.":
        ", чтобы начать сессию. Биомы обнуляются каждую сессию; роллы, уникальные ауры и лог дропов сохраняются.",
    "Saved so far:": "Сохранено:",
    "rolls": "роллов",
    "unique auras": "уникальных аур",
    "rarest:": "редчайшая:",
    "Loading the sandbox…": "Загрузка песочницы…",
    "Game data is not ready — the tracker is still starting, retrying…":
        "Данные игры ещё не готовы — трекер запускается, повторяем…",
    "Game data failed to load — press ↻ Reload data.":
        "Не удалось загрузить данные — нажмите ↻ Обновить данные.",

    // ── World banner ──
    "☀ Daytime": "☀ День",
    "🌙 Nighttime": "🌙 Ночь",
    "sandbox clock": "часы песочницы",
    "NORMAL — no biome active": "NORMAL — биом не активен",
    "simulated biome": "симулированный биом",
    "left": "осталось",
    "visits": "визитов",
    "Force a biome…": "Принудительно вызвать биом…",
    "☁ Spawn": "☁ Создать",
    "✕ Clear": "✕ Сбросить",
    "Honest mode: biome spawning happens naturally on wiki odds. Switch to Sandbox to force biomes.":
        "Честный режим: биомы появляются естественно по шансам вики. Включите Sandbox, чтобы вызывать биомы принудительно.",

    // ── Roll card ──
    "Current luck": "Текущая удача",
    "base": "база",
    "gauntlets": "перчатки",
    "cheat": "чит",
    "Roll once": "Бросить один раз",
    "Disabled while auto-roll is running": "Отключено, пока работает авто-ролл",
    "Auto-roll": "Авто-ролл",
    "Luck": "Удача",
    "Luck (cheat)": "Удача (чит)",
    "gauntlets only in Honest mode. Enable Sandbox for the luck slider and roll-speed cheats.":
        "перчатки — только в Honest. Включите Sandbox для слайдера удачи и читов скорости.",
    "Effective roll speed": "Итоговая скорость крутки",
    "pool": "пул",
    "auras": "аур",
    "(biome-modified)": "(с учётом биома)",
    "Odds like the game: each aura rolls 1 in (N ÷ luck), the rarest hit wins; a full miss falls back to the commonest aura; luck-exempt auras ignore luck.":
        "Шансы как в игре: каждая аура проверяется как 1 из (N ÷ удача), забирается редчайший хит; полный промах отыгрывает самую обычную ауру; удача не действует на luck-exempt ауры.",

    // ── Last drop ──
    "Last drop": "Последний дроп",
    "No rolls yet — press ROLL.": "Роллов ещё нет — нажмите Roll.",
    "1 in": "1 из",
    "native biome odds": "нативные шансы биома",
    "biome exclusive": "эксклюзив биома",

    // ── Gauntlets ──
    "🥊 Gauntlets (allowed in Honest too)": "🥊 Перчатки (доступны и в Honest)",
    "Left Hand": "Левая рука",
    "Right Hand": "Правая рука",
    "Pocket": "Карман",
    "— empty —": "— пусто —",
    "Equip gear to simulate its luck boosts.": "Наденьте снаряжение, чтобы смоделировать его баффы удачи.",
    "Techniques (shown, not simulated)": "Техники (показаны, не симулируются)",

    // ── Stats ──
    "📊 Statistics": "📊 Статистика",
    "🗑 Reset": "🗑 Сброс",
    "Clear rolls, unique auras, biome visits and the drop log":
        "Очистить роллы, уникальные ауры, визиты биомов и лог дропов",
    "Rolls": "Роллы",
    "Unique auras": "Уникальные ауры",
    "Playtime": "Время игры",
    "Rarest": "Редчайшая",
    "No biome visits yet.": "Визитов биомов пока нет.",

    // ── Collection ──
    "🗂 Collection": "🗂 Коллекция",
    "collected": "собрано",
    "Nothing collected yet — press Roll.": "Коллекция пуста — нажмите Roll.",

    // ── Audio player (Sol's Book) ──
    "Volume": "Громкость",

    // ── Mode & alerts ──
    "⚙ Mode & drop alerts": "⚙ Режим и уведомления о дропах",
    "Sandbox mode (speed ×2/×3/×5, luck slider, forced biomes)":
        "Режим Sandbox (скорость ×2/×3/×5, слайдер удачи, форс биомов)",
    "Alert when aura rarity ≥": "Уведомлять, когда редкость ауры ≥",
    "Banner on rare/event biome spawns": "Баннер при спавне редких/ивентовых биомов",
    "Also send to Discord (embed, no pings)": "Также отправлять в Discord (embed, без пингов)",
    "Discord webhook URL": "URL Discord webhook",
    "Alerts show as banners inside the panel — no Windows notifications.":
        "Уведомления показываются баннерами внутри панели — без уведомлений Windows.",

    // ── Runtime toasts / composed ──
    "No aura data yet": "Данные аур ещё не загружены",
    "Game data is still loading — try ↻ Reload data.":
        "Данные игры ещё грузятся — попробуйте ↻ Обновить данные.",
    "Simulated biome spawn": "Симулированный спавн биома",
    "in": "в",
    "simulated drop": "симулированный дроп",
};
