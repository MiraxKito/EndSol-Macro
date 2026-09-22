// Russian UI translations, part 7 — pages and components that were not
// covered by parts 1-6 (Instructions, Notice changelog, Donations, Credits,
// Remote Access, Misc, Merchant, Fishing, Auras, Webhook, Custom Paths,
// Potion Craft, Panel Customization, secondary windows).
// Game item/aura/potion names, technical keywords (OCR, BR/SC, Anti-AFK,
// User ID...) and the Sol's Book tab stay in English on purpose.

export const RU_P7: Record<string, string> = {
    // ── App shell / sidebar / header ──
    "(WIP)": "(в разработке)",
    "Macro Theme:": "Тема:",
    "Loading EndSol Macro": "Загрузка EndSol Macro",
    "Preparing configuration and biome data…": "Подготовка конфигурации и данных о биомах…",
    "⚠️ Something went wrong": "⚠️ Что-то пошло не так",
    "Macro Settings": "Настройки макроса",
    "Main Features": "Основные функции",
    "Others": "Другое",

    // ── Remote Access ──
    "Error:": "Ошибка:",
    "Loading...": "Загрузка…",
    "Remote Access Control": "Управление удалённым доступом",
    "Enable and configure remote macro control": "Включение и настройка удалённого управления макросом",
    "How to set up the Discord bot and its commands": "Как настроить Discord-бота и его команды",
    "Open the": "Откройте",
    "→ New Application → tab": "→ New Application → вкладка",
    "→ copy the token and paste it into": "→ скопируйте токен и вставьте в",
    "below.": "ниже.",
    "In Discord enable": "В Discord включите",
    ", right-click your own name →": ", кликните правой кнопкой по своему имени →",
    "→ paste into": "→ вставьте в",
    "(only this user can send commands).": "(команды может отправлять только этот пользователь).",
    "Invite the bot to your server: Developer Portal →": "Пригласите бота на сервер: Developer Portal →",
    "→ check scopes": "→ отметьте scopes",
    "→ open the generated URL.": "→ откройте сгенерированную ссылку.",
    "Turn on": "Включите",
    ". The bot comes online together with the macro.": ". Бот выйдет в сеть вместе с макросом.",

    // ── Donations ──
    "Donations": "Донаты",
    "Support the development of EndSol Macro": "Поддержите разработку EndSol Macro",
    "Support Us": "Поддержите нас",
    "Help us keep the project alive": "Помогите нам поддерживать проект",
    "Our projects are 100% free to use and you're allowed to recycle any fraction of our code with proper credits. However, if you want to support our team, you can help us by purchasing any of the gamepasses below :)":
        "Наши проекты на 100% бесплатны, и вы можете использовать любую часть нашего кода с указанием авторства. Если хотите поддержать нашу команду — можете купить любой из геймпассов ниже :)",
    "It helps us out a lot mentally, any donations above 100 Robux will get you on the appreciation list below, 500 Robux will give you the permission to leave a special message on the appreciation list (must be sfw though) & 1000 Robux will give you access to early EndSol macro releases (beta vers) :D":
        "Это очень мотивирует: донаты от 100 Robux попадают в список благодарности ниже, 500 Robux дают право оставить отдельное сообщение в списке благодарности (только SFW), а 1000 Robux открывают доступ к ранним сборкам EndSol Macro (бета-версии) :D",
    "Donators Hall of Fame": "Зал славы донатеров",
    "It automatically updates from GitHub": "Обновляется автоматически из GitHub",
    "Loading appreciation list...": "Загрузка списка благодарности…",
    "Unable to load appreciation list.": "Не удалось загрузить список благодарности.",

    // ── Credits ──
    "EndSol Macro development team": "Команда разработки EndSol Macro",
    "EndSol Macro Developer": "Разработчик EndSol Macro",
    "Fork of Coteab Macro — continued development and customization": "Форк Coteab Macro — продолжение разработки и доработки",
    "Coteab Macro — Original Team": "Coteab Macro — оригинальная команда",
    "The creators of the original macro that EndSol is based on": "Создатели оригинального макроса, на котором основан EndSol",
    "— Lead Developer, fullstack": "— ведущий разработчик, fullstack",
    "GitHub: Coteab Macro (original)": "GitHub: Coteab Macro (оригинал)",
    "Biome Macro Creator — Inspiration and biome detection logic": "Автор Biome Macro — вдохновение и логика детекта биомов",
    "YouTube Channel": "YouTube-канал",
    "Extra Credits": "Дополнительные благодарности",
    "Thanks to everyone who contributed": "Спасибо всем, кто помогал",
    "- maxstellar — Inspiration and biome detection logic": "- maxstellar — вдохновение и логика детекта биомов",
    "- Vexthecoder — Icons and assets": "- Vexthecoder — иконки и ассеты",
    "- Cresqnt, Baz & the Scope Team — Anti-AFK inspiration": "- Cresqnt, Baz и команда Scope — вдохновение для Anti-AFK",
    "- rnd.xy, imsomeone — External contributions": "- rnd.xy, imsomeone — внешние доработки",
    "- Finnerinch — Former developer": "- Finnerinch — бывший разработчик",
    "- .ivelchampion249._30053 — Fishing logic inspiration": "- .ivelchampion249._30053 — вдохновение для логики рыбалки",
    "- All the testers who made this possible": "- Все тестировщики, благодаря которым это стало возможным",
    "Rights and License": "Права и лицензия",
    "Free personal use — redistribution is not permitted": "Бесплатное личное использование — распространение запрещено",
    "This software is free for personal, non-commercial use. Copying, republishing, selling, sublicensing, or presenting modified versions as an official release is not permitted without written permission.":
        "Это ПО бесплатно для личного некоммерческого использования. Копирование, повторная публикация, продажа, сублицензирование или выдача изменённых версий за официальный релиз без письменного разрешения запрещены.",
    "Third-party components remain subject to their respective licenses.": "Сторонние компоненты подчиняются своим лицензиям.",

    // ── Instructions ──
    "A practical guide to EndSol Macro, its tabs, settings, and safe operating order":
        "Практический гайд по EndSol Macro: вкладки, настройки и безопасный порядок работы",
    "Getting started": "Начало работы",
    "Merchant and automated actions": "Мерчант и автодействия",
    "Movements and paths": "Перемещения и маршруты",
    "Daily (event) Rewards": "Ежедневные (ивентовые) награды",
    "Auras, Potion Crafting, and Webhook": "Ауры, крафт зелий и вебхук",
    "Multiple-Instances and safety": "Мульти-окна и безопасность",
    "Status, Stats, Notice, Panel Customization, and Credits": "Статус, Статистика, Новости, Кастомизация панели и Авторы",
    "Troubleshooting checklist": "Чек-лист устранения проблем",
    "open": "откройте",
    ", or calibrate individual points with the overlay.": ", или откалибруйте отдельные точки через оверлей.",
    "Configure webhook, username, User ID, and private-server settings only if those features are enabled.":
        "Настройте вебхук, ник, User ID и приватный сервер только если соответствующие функции включены.",
    "Enable the desired feature toggles and press the main macro switch in the header.":
        "Включите нужные переключатели функций и нажмите главный выключатель макроса в шапке.",
    "Use the log panel and": "Используйте панель логов и",
    "page to confirm which worker is active. Avoid enabling conflicting foreground actions together.":
        "чтобы убедиться, какой воркер активен. Не включайте одновременно конфликтующие действия в фокусе.",
    "Fishing opens the fishing UI, detects the indicator, performs the reel clicks, and optionally sells fish or runs merchant/BR-SC flows.":
        "Рыбалка открывает интерфейс рыбалки, находит индикатор, выполняет клики подсечки и опционально продаёт рыбу или запускает мерчанта/BR-SC.",
    "Fishing Mode:": "Режим рыбалки:",
    "the main switch; it pauses most competing mouse actions.": "главный переключатель; он приостанавливает большинство конкурирующих действий мыши.",
    "Auto selling:": "Авто-продажа:",
    "configure the fish threshold and amount before enabling it.": "настройте порог рыбы и количество перед включением.",
    "Playback multiplier:": "Множитель записи:",
    "affects recorded fishing movement timing; keep it at 1.0 for the original route timing.":
        "влияет на тайминги записанного движения рыбалки; держите 1.0 для оригинального тайминга маршрута.",
    "Failsafe rejoin:": "Фейлсейф-реконнект:",
    "requires Auto Reconnect and should be tested with a private server.": "требует Auto Reconnect; тестируйте с приватным сервером.",
    "Auto Pop uses the enabled loadout for the exact detected biome. Each selected item is searched in the inventory, checked by OCR when available, used for its configured amount, and then the next item is processed.":
        "Auto Pop использует включённый набор для конкретного обнаруженного биома. Каждый выбранный предмет ищется в инвентаре, проверяется OCR (если доступно), используется заданное количество раз, затем берётся следующий предмет.",
    "Open a biome's": "Откройте",
    "and enable the required items.": "и включите нужные предметы.",
    "Use the": "Используйте",
    "controls to choose the exact first-to-last order. The order is saved separately for each biome.":
        "чтобы задать точный порядок от первого к последнему. Порядок сохраняется отдельно для каждого биома.",
    "Do not enable Auto Pop while another foreground inventory action is being performed; it waits for blocked workers to finish.":
        "Не включайте Auto Pop, пока выполняется другое действие с инвентарём в фокусе; он ждёт завершения занятых воркеров.",
    "For effects with dependencies or special timing, place the prerequisite potion first and the final/long-duration item last. Test a small amount before using a large amount.":
        "Для эффектов с зависимостями или особым таймингом ставьте подготовительное зелье первым, а финальный/долгий предмет — последним. Проверьте на малом количестве перед большим.",
    "handles teleporter, OCR, exchange, and purchase actions.": "отвечает за телепортёр, OCR, обмен и покупки.",
    "contains quests, reconnect, screenshots, biome randomizer, strange controller, and recovery options.":
        "содержит квесты, реконнект, скриншоты, рандомизатор биомов, strange controller и опции восстановления.",
    "controls saved routes such as Obby, Eden, and egg collection. Paths replay their recorded timestamps and key events; they are not recalculated from a generic speed formula.":
        "управляет сохранёнными маршрутами: Obby, Eden и сбор яиц. Пути воспроизводят записанные тайминги и клавиши; они не пересчитываются по общей формуле скорости.",
    "Use the correct VIP/Non-VIP path option for the account.": "Выбирайте правильный вариант пути VIP/Non-VIP для аккаунта.",
    "Keep Roblox focused and use the same camera alignment as when the route was recorded.":
        "Держите Roblox в фокусе и используйте то же положение камеры, что при записи маршрута.",
    "Do not edit path JSON timestamps unless you intentionally want different timing.":
        "Не правьте тайминги JSON пути без намерения изменить тайминг.",
    "lets you record your own walk routes and assign them to features (Obby, Eden, Memory Match, Quest Board, egg routes). A custom path always overrides the built-in default route for that feature.":
        "позволяет записать свои маршруты и назначить их функциям (Obby, Eden, Memory Match, Quest Board, маршруты яиц). Свой путь всегда переопределяет встроенный маршрут функции.",
    "on the Custom Paths page and perform the route in Roblox.": "на странице Custom Paths и пройдите маршрут в Roblox.",
    "Stop the recording in the Recorder window, then save it on this page with a name and an optional feature.":
        "Остановите запись в окне рекордера, затем сохраните её на этой странице с именем и опциональной функцией.",
    "(empty) to fall back to the default route.": "(пусто), чтобы вернуться к дефолтному маршруту.",
    "Record routes at the same resolution and window mode you play with — path coordinates are resolution-dependent.":
        "Записывайте маршруты в том же разрешении и режиме окна, в котором играете — координаты пути зависят от разрешения.",
    "Memory Match opens the mini-game, detects the 5×4 card grid from the calibrated region, matches pairs by image similarity, and closes the game when the board disappears.":
        "Memory Match открывает мини-игру, находит сетку карт 5×4 в откалиброванной области, сопоставляет пары по схожести изображений и закрывает игру, когда доска исчезает.",
    "Calibrate the grid region, the Start button, and the Close button in": "Откалибруйте область сетки, кнопку Start и кнопку Close в",
    "controls how often the loop attempts a game (default 60 minutes).": "задаёт, как часто цикл пытается сыграть партию (по умолчанию 60 минут).",
    "allows the loop to run alongside fishing; the macro pauses foreground actions safely via the shared scheduler.":
        "разрешает циклу работать во время рыбалки; макрос безопасно приостанавливает действия в фокусе через общий планировщик.",
    "speeds up or slows down the click sequence (1.0 = original timing).": "ускоряет или замедляет последовательность кликов (1.0 = оригинальный тайминг).",
    "Quest Board walks to the board (optional custom path), opens it with": "Квестборд идёт к доске (опционально свой путь), открывает её клавишей",
    ", reads each quest name with OCR, then accepts, dismisses, or claims it depending on your settings.":
        ", читает названия квестов через OCR, затем принимает, отклоняет или забирает их по вашим настройкам.",
    "Calibrate the OCR region, Accept / Claim / Dismiss buttons, the left and right arrows, and the Close button.":
        "Откалибруйте OCR-область, кнопки Accept / Claim / Dismiss, стрелки влево/вправо и кнопку Close.",
    "choose per category which quests the macro accepts (hunts, Meditation I/II, Breakthroughs) and which it dismisses (fishing, player hunts, deliveries, tutorial tasks). Unknown quests are dismissed for safety.":
        "выберите по категориям, какие квесты макрос принимает (охоты, Meditation I/II, Breakthroughs), а какие отклоняет (рыбалка, охоты на игроков, доставки, обучающие). Неизвестные квесты отклоняются для безопасности.",
    "behave like the Memory Match options.": "работают как опции Memory Match.",
    "is the built-in encyclopedia of biomes and auras. Data comes directly from the Sol's RNG Fandom wiki: spawn chances, durations, breakthrough multipliers, chat colors, native and exclusive auras, rarities, and obtainment paths.":
        "— встроенная энциклопедия биомов и аур. Данные берутся напрямую из Fandom-вики Sol's RNG: шансы появления, длительность, множители breakthrough, цвета чата, нативные и эксклюзивные ауры, редкости и способы получения.",
    "While the macro runs it refreshes the data from Fandom automatically; the last verified copy is cached locally for offline use.":
        "Пока макрос запущен, данные обновляются из Fandom автоматически; последняя проверенная копия кэшируется локально для офлайна.",
    "The source badge on the page shows whether you are viewing live Fandom data, the local cache, or the bundled offline snapshot.":
        "Бейдж источника на странице показывает, смотрите ли вы живые данные Fandom, локальный кэш или встроенный офлайн-снапшот.",
    "Biome and aura statistics used by webhooks come from the same dataset.": "Статистика биомов и аур для вебхуков берётся из того же набора данных.",
    "With": "Когда",
    "enabled in": "включены в",
    ", the macro claims the daily check-in automatically at 03:00 MSK. To verify the flow at any time, use the buttons under the toggle:":
        ", макрос забирает ежедневный вход автоматически в 03:00 МСК. Чтобы проверить процесс в любой момент, используйте кнопки под переключателем:",
    "— runs one claim attempt immediately and reports the OCR result (requires the macro to be started and Roblox focused).":
        "— сразу выполняет одну попытку забора и показывает результат OCR (нужен запущенный макрос и Roblox в фокусе).",
    "— clears the stored date so the next window collects again.": "— сбрасывает сохранённую дату, чтобы следующее окно собралось снова.",
    "configures detection, recording, force-ping, and aura equipping.": "настраивает детект, запись, форс-пинг и надевание аур.",
    "records/replays Stella recipes and can switch selected recipes.": "записывает/воспроизводит рецепты Stella и умеет переключать выбранные рецепты.",
    "stores Discord destinations and notification preferences.": "хранит Discord-адреса и настройки уведомлений.",
    "Recordings use the in-game names/files exactly. Check the log after the first run to verify the selected file and target.":
        "Записи используются ровно с игровыми именами/файлами. После первого запуска проверьте в логе выбранный файл и цель.",
    "Multiple-Instances is designed for Roblox windows started by the current Windows user. The first login is manual; saved profiles are runtime records for reconnect. Secondary windows remain passive and do not receive foreground fishing, pathing, OCR, or mouse automation.":
        "Мульти-окна рассчитаны на окна Roblox, запущенные текущим пользователем Windows. Первый вход — вручную; сохранённые профили — записи для реконнекта. Второстепенные окна остаются пассивными и не получают рыбалку, маршруты, OCR или мышь в фокусе.",
    "Never share webhook URLs, cookies, private-server links, or account identifiers. Stop the macro before changing calibration or closing Roblox.":
        "Никогда не делитесь URL вебхуков, куками, ссылками на приватные серверы и идентификаторами аккаунтов. Останавливайте макрос перед изменением калибровок или закрытием Roblox.",
    "shows enabled workers, active workers, and detected conflicts.": "показывает включённые воркеры, активные воркеры и обнаруженные конфликты.",
    "shows session time, biome counts, and history.": "показывает время сессии, счётчики биомов и историю.",
    "contains release notes and important warnings.": "содержит заметки о релизах и важные предупреждения.",
    "changes appearance, labels, icons, font, and background without changing automation logic.":
        "меняет внешний вид, названия, иконки, шрифт и фон, не трогая логику автоматизаций.",
    "contains project attribution and original-author acknowledgement.": "содержит авторство проекта и благодарности оригинальным авторам.",
    "If a route is too slow or too fast, verify the selected VIP/Non-VIP option and playback multiplier.":
        "Если маршрут слишком медленный или быстрый — проверьте выбранный вариант VIP/Non-VIP и множитель записи.",
    "If an item is skipped, check its exact in-game name, OCR visibility, amount, and Auto Pop order.":
        "Если предмет пропущен — проверьте его точное игровое название, видимость для OCR, количество и порядок Auto Pop.",
    "If workers wait indefinitely, open": "Если воркеры ждут бесконечно — откройте",
    "and disable the competing foreground feature.": "и отключите конкурирующую функцию в фокусе.",
    "Always reproduce the issue with one feature enabled before changing several settings at once.":
        "Всегда воспроизводите проблему с одной включённой функцией, прежде чем менять несколько настроек сразу.",
    "Status:": "Статус:",
    "Stats:": "Статистика:",
    "Notice:": "Новости:",
    "Panel Customization:": "Кастомизация панели:",
    "Credits:": "Авторы:",
    "Misc": "Автодействиях",

    // ── Notice (release notes) ──
    "✅ New": "✅ Новое",
    "🛠️ Fixed": "🛠️ Исправлено",
    "✅ Changed": "✅ Изменено",
    "⚠️ Compatibility warning": "⚠️ Предупреждение о совместимости",
    "Supported features": "Поддерживаемые функции",
    "EndSol Macro functionality outside Multiple-Instances mode": "Функциональность EndSol Macro вне режима мульти-окон",
    "v1.0.6 — Memory Match & quality-of-life fixes":
        "v1.0.6 — фиксы Memory Match и мелкие улучшения",
    "Memory Match plays more reliably; Transcendent auras shine blue; media cache stays small":
        "Memory Match играет надёжнее; ауры Transcendent переливаются голубым; медиа-кэш больше не растёт",
    "v1.0.5 — Soft-disconnect reconnect, Memory Match & Quest Board fixes, localization":
        "v1.0.5 — реконнект при тихом дисконнекте, фиксы Memory Match и квестборда, локализация",
    "Reconnects on silent internet drops; smarter Memory Match matching; Quest Board accepts damaged OCR names; EN/RU panel language":
        "Реконнект при тихих обрывах интернета; умнее сопоставление в Memory Match; квестборд принимает повреждённые OCR-названия; язык панели EN/RU",
    "Panel localization (EN / RU):": "Локализация панели (EN / RU):",
    "language switcher in Other Features → System Settings. Missing translations fall back to English; switching the language resets custom tab names (with confirmation) because customization has priority over translated defaults. Sol's Book data stays English (it is parsed live from Fandom).":
        "переключатель языка в Other Features → System Settings. Отсутствующие переводы откатываются к английскому; смена языка сбрасывает кастомные названия вкладок (с подтверждением), так как кастомизация важнее перевода. Данные Sol's Book остаются на английском (они парсятся живьём из Fandom).",
    "Soft-disconnect reconnect:": "Реконнект при тихом дисконнекте:",
    "when the internet drops, Roblox sometimes keeps the window alive without a disconnect event. The macro now watches Roblox log activity (the client writes a heartbeat line every ~20s) — if the log goes silent for ~60s, it counts as a disconnect and the normal reconnect flow kicks in.":
        "при обрыве интернета Roblox иногда продолжает держать окно живым без события дисконнекта. Макрос теперь следит за активностью логов Roblox (клиент пишет строку heartbeat каждые ~20 с) — если лог молчит ~60 с, это считается дисконнектом и запускается обычный реконнект.",
    "Remote Access help (\"?\" button):": "Справка удалённого управления (кнопка «?»):",
    "a help panel with bot setup steps and the full slash-command list.": "панель помощи с шагами настройки бота и полным списком слэш-команд.",
    "Stats reset confirmation:": "Подтверждение сброса статистики:",
    "the reset button now opens a dialog; the confirm button stays locked for 5 seconds so it can't be hit by accident.":
        "кнопка сброса теперь открывает диалог; кнопка подтверждения заблокирована 5 секунд, чтобы не нажать случайно.",
    "Sol's Book rarity colors:": "Цвета редкости в Sol's Book:",
    "aura entries are now colored by their rarity type (Basic → Transcendent, Challenged, Event, Dev Exclusive) instead of a single yellow.":
        "записи аур теперь окрашены по типу редкости (Basic → Transcendent, Challenged, Event, Dev Exclusive), а не одним жёлтым.",
    "Quest Board skipped Breakthrough quests": "Квестборд пропускал квесты Breakthrough",
    "when OCR heavily damaged the word \"breakthrough\" (e.g. \"hell breol<through\" was read as an unknown quest and dismissed even with Hell Breakthrough set to accept). A damaged-word pattern now recognizes bre + junk + through in any layout.":
        "когда OCR сильно повреждал слово \"breakthrough\" (например, \"hell breol<through\" читалось как неизвестный квест и отклонялось, даже если Hell Breakthrough стояло на accept). Шаблон повреждённого слова теперь распознаёт bre + мусор + through в любом виде.",
    "Memory Match scored 0 pairs:": "Memory Match набирала 0 пар:",
    "identical items compared at distance 87+ because the tile signature leaked the semi-transparent background. The signature is now background-normalized (tighter 24% center crop + border subtraction), the distance metric is a mean instead of worst-channel, and the best candidate is accepted by tolerance or by a clear margin over the runner-up.":
        "одинаковые предметы сравнивались с дистанцией 87+, потому что сигнатура плитки захватывала полупрозрачный фон. Теперь сигнатура нормализована по фону (более узкий центр 24% + вычитание рамки), метрика дистанции — среднее вместо худшего канала, а лучший кандидат принимается по допуску или с явным отрывом от второго места.",
    "Memory Match quantity OCR:": "OCR количества в Memory Match:",
    "several OCR candidates (strip heights, 4x upscale, autocontrast, full tile) are tried; the quantity is no longer required for matching — identity comes from the icon signature.":
        "перебирается несколько OCR-вариантов (высоты полос, апскейл 4x, авто-контраст, вся плитка); количество больше не обязательно для сопоставления — идентичность определяется сигнатурой иконки.",
    "Memory Match logs trimmed:": "Логи Memory Match сокращены:",
    "one summary line per cell read and one per comparison round instead of per-attempt spam.":
        "одна итоговая строка на чтение ячейки и одна на раунд сравнения вместо спама на каждую попытку.",
    "v1.0.4 — Fandom data system, recorders, and calibration profiles": "v1.0.4 — система данных Fandom, рекордеры и профили калибровок",
    "Sol's Book now runs on live Fandom data; secondary windows and calibration save/export/import fixed":
        "Sol's Book теперь на живых данных Fandom; исправлены второстепенные окна и сохранение/экспорт/импорт калибровок",
    "Sol's Book on live Fandom data:": "Sol's Book на живых данных Fandom:",
    "biomes and auras (including limited, craftable, unobtainable, and dev-exclusive entries) are parsed directly from the wiki — spawn chances, durations, breakthrough multipliers, chat colors, native/exclusive aura links, and real wiki rarity classes. Offline fallback now uses a bundled Fandom snapshot instead of placeholder data.":
        "биомы и ауры (включая лимитированные, крафтовые, недоступные и dev-эксклюзивные записи) парсятся напрямую из вики — шансы появления, длительности, множители breakthrough, цвета чата, ссылки на нативные/эксклюзивные ауры и реальные классы редкости вики. Офлайн-фолбэк теперь использует встроенный Fandom-снапшот вместо заглушек.",
    "Custom Paths recorder:": "Рекордер Custom Paths:",
    "a \"Record new path\" button opens the generic Recorder directly from the Custom Paths page.":
        "кнопка \"Record new path\" открывает общий рекордер прямо со страницы Custom Paths.",
    "Quest Board quest-type preferences:": "Настройки типов квестов квестборда:",
    "choose per quest type whether the macro accepts or dismisses it (hunts/meditation/breakthrough by default; fishing, player hunts, deliveries, tutorial quests are dismissed).":
        "для каждого типа квеста можно выбрать, принимает ли макрос его или отклоняет (по умолчанию охоты/медитация/breakthrough; рыбалка, охоты на игроков, доставки и обучающие квесты отклоняются).",
    "Memory Match and Quest Board settings": "Настройки Memory Match и квестборда",
    "exposed in Misc: check intervals, play-during-fishing, and playback speed multiplier.":
        "вынесены в Misc: интервалы проверки, работа во время рыбалки и множитель скорости записи.",
    "Daily Rewards manual test:": "Ручной тест Daily Rewards:",
    "\"Collect now (test)\" and \"Reset claimed date\" buttons next to the Daily Rewards toggle.":
        "кнопки \"Collect now (test)\" и \"Reset claimed date\" рядом с переключателем Daily Rewards.",
    "sections for Custom Paths, Memory Match, Quest Board, Sol's Book, and Daily Rewards.":
        "разделы по Custom Paths, Memory Match, квестборду, Sol's Book и Daily Rewards.",
    "Recorder and rare-biome popup windows rendered a black screen": "Окна рекордера и попапа редкого биома показывали чёрный экран",
    "in the packaged app — secondary windows now load through the same file URL as the main window, so assets resolve.":
        "в упакованном приложении — второстепенные окна теперь грузятся через тот же file URL, что и главное окно, поэтому ассеты находятся.",
    "Calibration Save / Load / Export / Import": "Сохранение / загрузка / экспорт / импорт калибровок",
    "crashed on start (missing helper and import). The full profile flow now works: save with resolution/scale/mode metadata, list with validity status, load with automatic backup, export/import JSON files with validation.":
        "падали при старте (отсутствовали хелпер и импорт). Полный цикл профилей теперь работает: сохранение с метаданными разрешения/масштаба/режима, список со статусом валидности, загрузка с автоматическим бэкапом, экспорт/импорт JSON с валидацией.",
    "Obby automation could not be enabled from the new UI (dead config keys); the toggle and interval now use the backend keys.":
        "Авто-обби нельзя было включить из нового UI (мёртвые ключи конфига); переключатель и интервал теперь используют ключи бэкенда.",
    "Aura detail cards showed raw wiki markup; names, obtainment text, and descriptions are now clean, and rarity shows both the native and the global chance.":
        "Карточки аур показывали сырую вики-разметку; названия, текст получения и описания теперь чистые, а редкость показывает и нативный, и глобальный шанс.",
    "Biome descriptions contained leftover image markup (\"thumb…\"); descriptions are now clean prose.":
        "Описания биомов содержали остатки разметки изображений (\"thumb…\"); теперь это чистый текст.",
    "Portable Crack default interval aligned (3 minutes) and the Eden contract interval no longer falls back to a different value.":
        "Дефолтный интервал Portable Crack выровнен (3 минуты), а интервал контракта Eden больше не откатывается к другому значению.",
    "Auto-fullscreen re-verifies the Roblox window once a minute, so a manual exit from fullscreen is restored automatically.":
        "Авто-фуллскрин раз в минуту перепроверяет окно Roblox, так что ручной выход из фуллскрина автоматически исправляется.",
    "Default calibrations for 1920×1080 / 100% / Fullscreen replaced with a verified profile.":
        "Дефолтные калибровки для 1920×1080 / 100% / Fullscreen заменены проверенным профилем.",
    "Recorder windows now render correctly (assets resolve through the bundled page base).":
        "Окна рекордера теперь корректно отображаются (ассеты находятся через базу встроенной страницы).",
    "Aura obtainment for potion-crafted auras (e.g. Fragments of the Crimson Moon) now lists every potion source with its exact chance.":
        "Получение крафтовых аур (напр. Fragments of the Crimson Moon) теперь перечисляет каждый источник зелий с точным шансом.",
    "Limbo-locked auras (Anima and friends) are marked \"Exclusive to THE LIMBO\" instead of \"anywhere\".":
        "Ауры, залоченные за Лимбо (Anima и другие), помечены как \"Exclusive to THE LIMBO\" вместо \"anywhere\".",
    "Webhook ping policy: event auras are never pinged; Transcendent / Challenged / Challenged+ bypass the minimum-rarity threshold but are sent without a ping; other auras ping only at or above the configured minimum.":
        "Политика пингов вебхука: ивентовые ауры никогда не пингуются; Transcendent / Challenged / Challenged+ обходят порог минимальной редкости, но отправляются без пинга; остальные пингуются только при достижении заданного минимума.",
    "Quest Board: tutorial and one-time NPC/location quests can no longer be automated (always dismissed); per-type preferences remain for automatable quests.":
        "Квестборд: обучающие и одноразовые квесты NPC/локаций больше не автоматизируются (всегда отклоняются); настройки по типам остаются для автоматизируемых квестов.",
    "Aura article details are cached per session, reducing repeat Fandom requests.":
        "Детали статей аур кэшируются на сессию, сокращая повторные запросы к Fandom.",
    "v1.0.3 — Multiple-Instances redesign": "v1.0.3 — переработка мульти-окон",
    "External window monitoring through Avaluate MultipleRobloxInstances": "Мониторинг внешних окон через Avaluate MultipleRobloxInstances",
    "Removed the custom account-profile, launcher, persistence, PID ownership, and emergency-stop system.":
        "Удалена система кастомных профилей аккаунтов, лаунчера, персистентности, владения PID и аварийной остановки.",
    "Multiple-Instances now expects the user to launch Roblox windows with Avaluate/MultipleRobloxInstances.":
        "Мульти-окна теперь ожидают, что пользователь запускает окна Roblox через Avaluate/MultipleRobloxInstances.",
    "EndSol only detects visible Roblox windows and processes them in deterministic order for one Anti-AFK action at a time.":
        "EndSol видит только видимые окна Roblox и обрабатывает их в детерминированном порядке, по одному Anti-AFK действию за раз.",
    "Statistics, biome/aura detection, mouse input, OCR, pathing, fishing, merchant, potion crafting, and other foreground automation are disabled while the mode is enabled.":
        "Статистика, детект биомов/аур, ввод мыши, OCR, маршруты, рыбалка, мерчант, крафт зелий и прочая автоматизация в фокусе отключены, пока режим включён.",
    "No built-in scheduler for the main instance - juggling several game windows reliably isn't possible on every PC, so EndSol keeps them active in order instead.":
        "Встроенного планировщика для главного окна нет — надёжно жонглировать несколькими окнами игры можно не на каждом ПК, поэтому EndSol держит их активными по очереди.",
    "Avaluate's own documentation warns that Roblox may close additional windows randomly. EndSol does not bypass or work around that behavior.":
        "Документация Avaluate сама предупреждает, что Roblox может случайно закрывать дополнительные окна. EndSol не обходит и не маскирует это поведение.",
    "Supported workflow: start Avaluate first, load the first Roblox account fully, open additional accounts, then enable this mode in EndSol.":
        "Порядок запуска: сначала запустите Avaluate, полностью загрузите первый аккаунт Roblox, откройте дополнительные аккаунты, затем включите этот режим в EndSol.",
    "If a window closes or cannot be focused, EndSol skips it and continues without touching account data.":
        "Если окно закрылось или его нельзя сфокусировать, EndSol пропускает его и продолжает, не трогая данные аккаунтов.",
    "Biome and aura detection": "Детект биомов и аур",
    "Discord webhook notifications": "Уведомления в Discord-вебхук",
    "Fishing automation and potion crafting": "Автоматизация рыбалки и крафт зелий",
    "Auto-pop buff system per biome": "Система авто-баффов по биомам",
    "Resolution/DPI-aware calibration": "Калибровка с учётом разрешения/DPI",
    "Remote control and screen capture": "Удалённое управление и захват экрана",

    // ── Auras ──
    "(Fires after 2s delay)": "(Срабатывает с задержкой 2 сек)",
    "Aura name to equip": "Название ауры для надевания",
    "Detect and notify about rare auras": "Отслеживать редкие ауры и уведомлять",
    "e.g. Oblivion, Illusionary,... (comma-separated)": "напр. Oblivion, Illusionary, ... (через запятую)",
    "Force aura record even if rarity is not met (otherwise don't put the auras in the box if you don't want the macro to force record)":
        "Принудительно записывать ауру даже без нужной редкости (иначе не кладите ауры в ячейку, если не нужен форс-рекорд)",
    "Pings Discord User ID even if rarity is not met. (otherwise don't put the auras in the box if you don't want the macro to force ping)":
        "Пинговать Discord User ID даже без нужной редкости (иначе не кладите ауры в ячейку, если не нужен форс-пинг)",
    "Record Keybind": "Клавиша записи",
    "Test Keybind": "Тест клавиши",
    "Take a screenshot when you rolled a new aura (Only works if Roblox is focused/Fishing mode is OFF!)":
        "Скриншот при выпадении новой ауры (Работает только если Roblox в фокусе и режим рыбалки ВЫКЛ!)",

    // ── Auto Pop Buff ──
    "Top": "Вверх",
    "Bottom": "Вниз",
    "Loading auto pop buff settings...": "Загрузка настроек авто-баффов…",
    "Use separate biome-specific buff loadouts instead of the old rare-vs-normal grouping":
        "Использовать отдельные наборы баффов для каждого биома вместо старой группировки редкие/обычные",
    "Enter item name (e.g. 'My Custom Potion')": "Введите название предмета (напр. 'Моё кастомное зелье')",

    // ── Calibration ──
    "Cancel (ESC)": "Отмена (ESC)",
    "Taking screenshot... (This shouldn't take long)": "Делаю скриншот... (это не займёт долго)",
    "View and manually edit calibration coordinates": "Просмотр и ручное редактирование координат калибровок",
    "Local profiles (copied JSON files are detected automatically):": "Локальные профили (скопированные JSON-файлы подхватываются автоматически):",
    "Presets not found on github or failed to fetch.": "Пресеты не найдены на GitHub или не удалось их загрузить.",
    "ℹ️ Use \"Select Pos\" or \"Select Region\" to launch the calibration overlay :)":
        "ℹ️ Используйте «Select Pos» или «Select Region», чтобы открыть окно калибровки :)",
    "(invalid)": "(некорректен)",

    // ── Discord Webhook Customization ──
    "APP": "ПРИЛОЖЕНИЕ",
    "Save Configuration (reopen the macro to take effect!)": "Сохранить конфигурацию (переподключите макрос, чтобы применить!)",
    "Send a test webhook for the selected biome (no ping, marked as test)": "Отправить тестовый вебхук для выбранного биома (без пинга, помечен как тест)",
    "(Scroll wheel supported)": "(Поддерживается колесо мыши)",

    // ── Panel Customization ──
    "Cover": "Заполнить",
    "Auto": "Авто",
    "None": "Нет",
    "Float": "Парение",
    "Pulse": "Пульсация",
    "Slide": "Скольжение",
    "Normal (400)": "Обычный (400)",
    "Medium (500)": "Средний (500)",
    "Semi-bold (600)": "Полужирный (600)",
    "Bold (700)": "Жирный (700)",
    "Extra-bold (800)": "Сверхжирный (800)",
    "Black (900)": "Чёрный (900)",
    "Normal": "Обычный",
    "Custom Font URL (Google Fonts, etc.)": "Ссылка на свой шрифт (Google Fonts и т.п.)",
    "Raw Custom CSS (alternative field)": "Свой CSS (альтернативное поле)",
    "Solid Color (uses --bg-root)": "Сплошной цвет (использует --bg-root)",
    "Changes preview instantly. Save the theme when your panel looks right; Reset restores the safe defaults.":
        "Изменения применяются сразу. Сохраните тему, когда панель устраивает; Reset возвращает безопасные значения по умолчанию.",
    "Everything the panel looks like — grouped and with plain names. Hover a name for details; the raw CSS key stays in small text.":
        "Всё, как выглядит панель — сгруппировано и с понятными названиями. Наведите на название для подробностей; ключ CSS показан мелким текстом.",

    // ── Status ──
    "◀ Prev": "◀ Назад",
    "Next ▶": "Вперёд ▶",
    "↓ Scroll to bottom": "↓ Прокрутить вниз",
    "Macro is currently STOPPED. Most modules will appear as Idle or Disabled until you start the macro (F1).":
        "Макрос сейчас ОСТАНОВЛЕН. Большинство модулей будут в статусе Idle или Disabled, пока вы не запустите макрос (F1).",

    // ── Multiple-Instances ──
    "Mouse, OCR, pathing, fishing, merchant, potion crafting": "Мышь, OCR, маршруты, рыбалка, мерчант, зелья",
    "Main instance and pause/resume cycle": "Главное окно и цикл пауза/продолжение",
    "LAST ACTION": "ПОСЛЕДНЕЕ ДЕЙСТВИЕ",
    "Queue Status": "Статус очереди",
    "Last action:": "Последнее действие:",
    "· reason:": "· причина:",
    "· time:": "· время:",
    "none yet": "пока нет",
    "Windows are processed in launch order. If one is closed or can't be focused, it's skipped and the rest continue.":
        "Окна обрабатываются по порядку запуска. Если окно закрыто или его нельзя сфокусировать — оно пропускается, остальные продолжают.",
    "One window at a time keeps focus and input safe - the macro itself stays in the main window.":
        "По одному окну за раз — фокус и ввод в безопасности, сам макрос остаётся в главном окне.",

    // ── Webhook ──
    "Biome Configuration": "Настройка биомов",
    "Forced Webhook +": "Принудительный вебхук +",
    "Your Roblox username": "Ваш ник в Roblox",
    "input your Roblox username (case-insensitive) for higher logs accuracy reading":
        "введите ник в Roblox (без учёта регистра) для более точного чтения логов",

    // ── Misc (Automated Actions) ──
    "Biome Randomizer (BR)": "Рандомизатор биомов (BR)",
    "Interval (minutes):": "Интервал (минуты):",
    "Usage Interval (minutes):": "Интервал использования (минуты):",
    "Usage Duration (minutes):": "Длительность использования (минуты):",
    "Inventory Interval (minutes):": "Интервал инвентаря (минуты):",
    "Inventory Mouse Click Delay (milliseconds)": "Задержка клика в инвентаре (мс)",
    "Claim Interval (minutes):": "Интервал забора (минуты):",
    "Contract Interval (minutes):": "Интервал контракта (минуты):",
    "Pathing Interval (minutes):": "Интервал маршрутов (минуты):",
    "Checking Interval (minutes):": "Интервал проверки (минуты):",
    "Check interval (minutes):": "Интервал проверки (минуты):",
    "Playback speed multiplier:": "Множитель скорости записи:",
    "Take": "Брать",
    "helper to assist you about this!)": "помощник подскажет, как это сделать!)",
    "— OCR failsafe will not work (if WinOCR haven't installed, ask macro helper to assist you about this!)":
        "— OCR-фейлсейф не заработает (если WinOCR не установлен, макро-помощник подскажет, как это сделать!)",
    "Note: GLITCHED, DREAMSPACE, CYBERSPACE are always blocked when using br/sc :aga:":
        "Важно: GLITCHED, DREAMSPACE и CYBERSPACE всегда блокируются при использовании br/sc :aga:",
    "Configure Daily Rewards buttons and OCR region in Macro Calibrations.": "Настройте кнопки Daily Rewards и OCR-область в Macro Calibrations.",
    "Eden Contract button (calibration)": "Кнопка контракта Eden (калибровка)",
    "Eden detection using OCR (detect on roblox chat)": "Детект Eden через OCR (по чату Roblox)",
    "Go to Eden's spawn (experimental)": "Идти к спавну Eden (экспериментально)",
    "Hunt quests have no tier picker — rolling completes them wherever they appear. Player Hunt is always dismissed (cannot be automated). A quest whose tier cannot be read by OCR is dismissed.":
        "У охотничьих квестов нет выбора тира — они выполняются там, где выпадут. Player Hunt всегда отклоняется (не автоматизируется). Квест, тир которого не читается OCR, отклоняется.",
    "Non-VIP accounts: enable \"Non-VIP movement path\" in the Fishing settings so walks are stretched automatically.":
        "Аккаунты без VIP: включите «Non-VIP movement path» в настройках рыбалки, чтобы маршруты растягивались автоматически.",
    "OCR box region calibration in Movements Calibration tab!": "Калибровка OCR-области во вкладке калибровок Movements!",
    "OCR Calibration": "OCR-калибровка",
    "Only works if fishing mode, potion crafting, auto obby, auto egg": "Работает только если режим рыбалки, крафт зелий, авто-обби, авто-яйца",
    "Only works if fishing, potion crafting, auto obby, auto egg": "Работает только если рыбалка, крафт зелий, авто-обби, авто-яйца",
    "pathing is OFF!": "маршруты ВЫКЛ!",
    "Ping if Eden found?": "Пинговать, если найден Eden?",
    "Play one Memory Match session right now (ignores the 12h cooldown, for testing)":
        "Сыграть одну партию Memory Match сейчас (игнорирует кулдаун 12 ч, для теста)",
    "Require 1 of 2 recorders: Medal, Xbox Gaming Bar": "Нужен 1 из 2 рекордеров: Medal, Xbox Gaming Bar",
    "Supports both private server code links and Roblox share links": "Поддерживает и ссылки-коды приватных серверов, и share-ссылки Roblox",
    "This only detect eden and ping you if": "Это только детектит Eden и пингует вас, если",
    "▶ Run now (test)": "▶ Запустить сейчас (тест)",
    "Accept quests the macro can passively complete; others are dismissed.": "Принимает квесты, которые макрос может выполнить пассивно; остальные отклоняются.",
    "Opening uses keyboard E; mouse clicks are only for the board controls.": "Открытие — клавишей E; клики мышью нужны только для кнопок доски.",
    "Join Button in Sol's RNG Calibration": "Кнопка Join в Sol's RNG (калибровка)",
    "(all tiers)": "(все тиры)",
    "Installed": "Установлен",
    "Not Installed": "Не установлен",
    "Make sure you do the chat, chat OCR tab, chat close, and chat": "Убедитесь, что настроены чат, вкладка OCR чата, закрытие чата и",
    "using br/sc :aga:": "используется br/sc :aga:",

    // ── Merchant ──
    "Item Name": "Название предмета",
    "Buy All": "Купить всё",
    "Buy maximum amount (uses Set to Max button)": "Покупать максимум (использует кнопку Set to Max)",
    "Check interval (in secs)": "Интервал проверки (в секундах)",
    "Detect merchant on chat (using OCR)": "Детектить мерчанта в чате (через OCR)",
    "Enable Auto Merchant (requires merchant teleporter)": "Включить авто-мерчанта (нужен телепортёр к мерчанту)",
    "Reminder:": "Напоминание:",
    "This only detects the merchant and pings you if found on Roblox chat, so you have to interact with the merchant yourself.":
        "Это только обнаруживает мерчанта и пингует вас, если он найден в чате Roblox — с мерчантом нужно взаимодействовать самому.",
    "Select Items to Exchange": "Выберите предметы для обмена",
    "Usage Duration:": "Длительность использования:",

    // ── Movements / Pathing ──
    "Interval (min):": "Интервал (мин):",
    "Close Roblox chat before pathing (DO MACRO CALIBRATION - IMPORTANT)": "Закрывать чат Roblox перед маршрутами (СДЕЛАЙТЕ КАЛИБРОВКУ - ВАЖНО)",
    "Slow down to applied movement paths (basic obby, fishing, etc...) to compensate for non-VIP walkspeed":
        "Замедлять применённые маршруты (basic obby, рыбалка и т.д.) для компенсации скорости без VIP",
    "Configure movement paths for automated navigation": "Настройка маршрутов перемещения для авто-навигации",
    "Claim Interval (minutes)": "Интервал забора квестов (минуты)",

    // ── Fishing ──
    "After x fish catches, run BR then SC with the usual OCR failsafe. If multiple flows trigger together, order is: sell -> merchant -> BR/SC.":
        "После x уловов запускает BR, затем SC с обычным OCR-фейлсейфом. Если срабатывают несколько сценариев, порядок: продажа -> мерчант -> BR/SC.",
    "Auto Pop Buff still has priority and will interrupt fishing. Remote Control stays enabled.":
        "Auto Pop Buff сохраняет приоритет и прерывает рыбалку. Удалённое управление остаётся включённым.",
    "Auto reconnect to your PS (experimental)": "Авто-реконнект к приватному серверу (экспериментально)",
    "Check merchant on roblox chat (OCR) every x fishes": "Проверять мерчанта в чате Roblox (OCR) каждые x уловов",
    "Fishing actions delay (in miliseconds)": "Задержка действий рыбалки (в мс)",
    "Fishing failsafe (rejoin if timeout)": "Фейлсейф рыбалки (реконнект по таймауту)",
    "Fishing mode is active. Movements, potion crafting, periodic screenshots, aura screenshots, daily quest claiming, and other non-essential mouse actions are paused. Fishing auto-merchant can still run if enabled above.":
        "Режим рыбалки активен. Перемещения, крафт зелий, периодические скриншоты, скриншоты аур, забор дневных квестов и другие несущественные действия мыши приостановлены. Авто-мерчант рыбалки может работать, если включён выше.",
    "Fishing Path Playback Multiplier (FPS Compensation)": "Множитель скорости рыболовного пути (компенсация FPS)",
    "⚠️ If you set fish path multiplier below 1.0, the macro will automatically default it back to 1.0 :aga:":
        "⚠️ Если задать множитель рыболовного пути ниже 1.0, макрос автоматически вернёт 1.0 :aga:",
    "Edit these in Macro Calibrations > Fishing Calibration": "Измените это в Macro Calibrations > Fishing Calibration",

    // ── Other Features ──
    "Auto Update (Startup)": "Авто-обновление (при запуске)",
    "Auto Update Biome/Aura Data": "Авто-обновление данных биомов/аур",
    "Automatically fetch latest biome/aura data from remote sources on startup":
        "Автоматически загружать свежие данные биомов/аур из внешних источников при запуске",
    "Reset character to Sol's Main Island during GLITCHED/DREAMSPACE/CYBERSPACE":
        "Ресетить персонажа на Sol's Main Island во время GLITCHED/DREAMSPACE/CYBERSPACE",
    "⚠️ Deprecated: this feature relies on legacy Roblox log entries that no longer exist in the current game. It cannot be improved anymore and is kept non-interactive for compatibility.":
        "⚠️ Устарело: функция опирается на старые записи логов Roblox, которых больше нет в текущей игре. Улучшить её нельзя; оставлена неинтерактивной для совместимости.",
    "⚠️ Disabled — auto-update points to original EndSol repo. Do not enable until repo is changed.":
        "⚠️ Отключено — авто-обновление указывает на оригинальный репозиторий EndSol. Не включайте, пока репозиторий не изменён.",

    // ── Custom Paths ──
    "How to record a path (4 steps)": "Как записать путь (4 шага)",
    "Record new path (open Recorder)": "Записать новый путь (открыть рекордер)",
    "Path name (e.g. walk_to_quest_board)": "Название пути (напр. walk_to_quest_board)",
    "Save": "Сохранить",
    "No feature (generic)": "Без функции (общий)",
    "Click": "Нажмите",
    "Press": "Нажмите",
    "name": "название",
    "feature": "функцию",
    "Return here, enter a": "Вернитесь сюда, введите",
    ", pick the": ", выберите",
    "the path is for (e.g. Memory Match or Quest Board) and click": "для которого предназначен путь (напр. Memory Match или Quest Board) и нажмите",
    "below — the Custom Path Recorder window opens.": "ниже — откроется окно рекордера путей.",
    "in the recorder, switch to Roblox and walk from the spawn point to the target (walk only — WASD/Space/E are recorded).":
        "в рекордере, переключитесь в Roblox и пройдите от точки спавна до цели (записывается только ходьба — WASD/Space/E).",
    "in the recorder. The recording stays in memory — it is not written to any default path.":
        "в рекордере. Запись остаётся в памяти — она не пишется ни в один дефолтный путь.",
    "By default only keyboard actions are saved (walk paths). Stop the recording in the Recorder window first, then save here.":
        "По умолчанию сохраняются только действия клавиатуры (маршруты). Сначала остановите запись в окне рекордера, затем сохраните здесь.",
    "Include mouse actions": "Учитывать действия мыши",
    "The walk to the fish seller stays built-in and is not recorded.": "Путь к продавцу рыбы остаётся встроенным и не записывается.",
    "Everyone on the same server can pick a different spot so you won't get in each other's way.":
        "Каждый на сервере может выбрать своё место, чтобы не мешать друг другу.",
    ": record the walk from the spawn point (right after the respawn sequence) to YOUR fishing spot. Everyone on the same server can pick a different spot so you won't get in each other's way. The walk to the fish seller stays built-in and is not recorded.":
        ": запишите маршрут от точки спавна (сразу после респавна) до ВАШЕГО места рыбалки. Каждый на сервере может выбрать своё место, чтобы не мешать друг другу. Путь к продавцу рыбы остаётся встроенным и не записывается.",
    "Fishing Spot": "Место рыбалки",
    "Stop & Save": "Стоп и сохранить",
    "Start": "Старт",
    "Align Camera": "Выровнять камеру",
    "Potion Name (e.g. Heavenly)": "Название зелья (напр. Heavenly)",
    "Opens and closes the Collection and tilts the camera up — same sequence the macro runs before walking":
        "Открывает/закрывает Collection и наклоняет камеру вверх — та же последовательность, что макрос делает перед ходьбой",

    // ── Potion Craft ──
    "Switch interval (seconds)": "Интервал переключения (секунды)",
    "Run selected recipe on a loop when macro is running (THIS WILL CANCEL ALL OTHERS MACRO ACTIONS FOR POTION CRAFTING)":
        "Готовить выбранный рецепт по кругу, пока запущен макрос (ЭТО ОТМЕНИТ ВСЕ ОСТАЛЬНЫЕ ДЕЙСТВИЯ МАКРОСА ДЛЯ КРАФТА ЗЕЛИЙ)",
    "🔄 Refresh Files": "🔄 Обновить файлы",

    // ── Puzzle / Biome confirm / Biome info ──
    "Both puzzles solved": "Обе загадки решены",
    "Please solve the previous puzzle first!": "Сначала решите предыдущую загадку!",
    "Submit": "Отправить",
    "Screenshot this and send it to": "Сделайте скриншот и отправьте его",
    "on EndSol Development discord server to claim your role": "в Discord-сервер EndSol Development, чтобы получить роль",
    "Rare Biome Detected After Rejoin!": "Редкий биом обнаружен после реконнекта!",
    "You just rejoined a server that has a": "Вы только что зашли на сервер, где активен",
    "rare biome": "редкий биом",
    "active.": ".",
    "Did you forget to close the macro before joining?": "Забыли выключить макрос перед входом?",
    "If you forgot, the macro will": "Если забыли, макрос",
    "stop immediately!!": "немедленно остановится!!",
    "✅ Nah. I'm good, keep this tuff macro running 🗣️🔥": "✅ Нет, всё норм, пусть этот крутой макрос работает 🗣️🔥",
    "❌ I forgot to turn the macro off please spare me 😭🥀": "❌ Я забыл выключить макрос, пощадите 😭🥀",
    "Response sent!": "Ответ отправлен!",
    "Neutral biome metadata loaded by the detector. Gameplay mechanics are not inferred here.":
        "Нейтральные метаданные биомов, загружаемые детектором. Игровая механика здесь не выводится.",
    "Paths remember whether they were recorded with Non-VIP movement mode (Movements). Playback auto-adjusts (x1.22) when the playback mode differs.":
        "Пути запоминают, в каком режиме (Non-VIP в Movements) они записаны. При другом режиме проигрывание автоматически подстраивается (x1.22).",
    "recorded on Non-VIP": "записан на Non-VIP",
    "recorded on VIP": "записан на VIP",
};