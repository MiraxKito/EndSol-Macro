import { useEffect } from "react";
import { useConfig } from "../contexts/ConfigContext";
import { RU_EXTRA } from "./ru";

export type Lang = "en" | "ru";

/**
 * Panel localization. Dictionary is keyed by the EXACT English source
 * string - any missing key falls back to English, so partial coverage is
 * always safe. Logs and Fandom data (Sol's Book) stay English by design.
 */
const RU: Record<string, string> = {
    ...RU_EXTRA,
    // ── Sidebar ──
    "Notice": "Новости",
    "Webhook": "Вебхук",
    "Stats": "Статистика",
    "Status": "Статус",
    "Automated Actions": "Автодействия",
    "Macro Calibrations": "Калибровки",
    "Remote Control": "Удалённое управление",
    "Fishing": "Рыбалка",
    "Merchant": "Мерчант",
    "Auto Pop Buff": "Авто-баффы",
    "Auras": "Ауры",
    "Movements": "Перемещения",
    "Custom Paths": "Свои пути",
    "Potion Crafting": "Крафт зелий",
    "Other Features": "Прочее",
    "Multiple-Instances": "Мульти-окна",
    "BUILT-IN MULTI-INSTANCE": "ВСТРОЕННЫЙ МУЛЬТИ-ИНСТАНС",
    "Launch and monitor every Roblox window directly from the panel — no external tool needed.": "Запуск и мониторинг всех окон Roblox прямо из панели — без внешних программ.",
    "Accounts are stored only on this PC, encrypted with Windows DPAPI. EndSol never sends your session tokens anywhere.": "Аккаунты хранятся только на этом ПК в шифрованном виде (Windows DPAPI). EndSol никуда не отправляет ваши токены сессий.",
    "SETUP": "НАСТРОЙКА",
    "Enable Multiple-Instances": "Включить мульти-инстанс",
    "Turns on the window monitor and takes the Roblox singleton lock so several clients can run.": "Включает мониторинг окон и блокировку singleton Roblox, чтобы клиенты работали параллельно.",
    "Add your accounts once": "Один раз добавьте аккаунты",
    "Use Add account below — a Roblox window opens, you log in, and the session is stored encrypted.": "Нажмите «Добавить аккаунт» — откроется окно Roblox, войдите в аккаунт, сессия сохранится в шифрованном виде.",
    "Launch instances from the panel": "Запускайте окна из панели",
    "Each launched client signs into its own account automatically and joins the game.": "Каждое запущенное окно автоматически входит в свой аккаунт и заходит в игру.",
    "Runs the full detector on the selected main window; secondary windows get ordered Anti-AFK and log-based alerts.": "Полный детектор работает на выбранном главном окне; остальные получают Anti-AFK по очереди и алерты из логов.",
    "Full instructions": "Полная инструкция",
    "ACCOUNT LAUNCHER": "ЗАПУСК АККАУНТОВ",
    "Accounts": "Аккаунты",
    "Launch a Roblox window signed into a stored account. Each client keeps its own session.": "Запуск окна Roblox под сохранённым аккаунтом. У каждого окна своя сессия.",
    "Launches join the private server link from the Webhook page. Without it the client opens at the home screen.": "Запуск использует ссылку на приватный сервер со страницы Вебхук. Без неё клиент откроется на домашнем экране.",
    "No accounts stored yet — add one below.": "Аккаунтов пока нет — добавьте ниже.",
    "Added": "Добавлен",
    "Launch": "Запустить",
    "Remove the stored session": "Удалить сохранённую сессию",
    "Add account": "Добавить аккаунт",
    "Waiting for login…": "Ожидание входа…",
    "Roblox singleton lock active": "singleton-блокировка Roblox активна",
    "cookie file locked": "файл куки заблокирован",
    "Locks": "Блокировки",
    "Last launch": "Последний запуск",
    "Launched": "Запущено",
    "The client logs into its own account automatically.": "Клиент автоматически войдёт в свой аккаунт.",
    "Failed to remove the account.": "Не удалось удалить аккаунт.",
    "Launch failed.": "Не удалось запустить.",
    "Closing…": "Закрывается…",
    "Roblox client closed": "Клиент Roblox закрыт",
    "forced after the grace period": "принудительно после таймаута",
    "Close this Roblox window (the client exits like the X button; a hung client is terminated)": "Закрыть это окно Roblox (клиент завершится как по крестику; зависший клиент будет принудительно закрыт)",
    "Failed to close the instance.": "Не удалось закрыть инстанс.",
    "Could not start the login capture.": "Не удалось начать захват входа.",
    "No Roblox windows detected. Launch an instance above or start Roblox manually.": "Окна Roblox не найдены. Запустите окно выше или вручную.",
    "Multiple-Instances — Instructions": "Мульти-окна — Инструкция",
    "One-time setup": "Разовая настройка",
    "Enable Multiple-Instances on this page. While it is on, EndSol holds the Roblox singleton lock — this is what allows several clients to run at the same time.": "Включите мульти-инстанс на этой странице. Пока режим включён, EndSol держит singleton-блокировку Roblox — именно она позволяет запускать несколько клиентов.",
    "Click Add account. A fresh Roblox window opens; log into that account inside it. EndSol saves the session encrypted (Windows DPAPI, this PC only) and closes the loop.": "Нажмите «Добавить аккаунт». Откроется чистое окно Roblox — войдите в нужный аккаунт. EndSol сохранит сессию шифрованной (Windows DPAPI, только этот ПК).",
    "Repeat for every account you want to run.": "Повторите для каждого аккаунта.",
    "Daily use": "Ежедневное использование",
    "Press Launch next to an account — a client opens already signed into that account and joins the private server link from the Webhook page (or opens at home when no link is set).": "Нажмите «Запустить» у аккаунта — окно откроется уже с этим аккаунтом и зайдёт по ссылке приватного сервера со страницы Вебхук (или откроется на домашнем экране, если ссылка не задана).",
    "Pick the main window (or leave it automatic) and start the macro. Secondary windows get ordered Anti-AFK and log alerts.": "Выберите главное окно (или оставьте «Авто») и запустите макрос. Вторые окна получат Anti-AFK по очереди и алерты.",
    "If a stored session expires (logout, password change), Remove it and add the account again.": "Если сессия истекла (выход, смена пароля) — удалите аккаунт и добавьте заново.",
    "Notes": "Примечания",
    "Bloxstrap users: launches go through your installed Bloxstrap protocol handler automatically; FastFlags apply as usual.": "Для Bloxstrap: запуск идёт через установленный обработчик протокола Bloxstrap, FastFlags применяются как обычно.",
    "If another multi-instance launcher is already running, EndSol detects it and keeps monitoring without taking the lock.": "Если уже запущен другой мульти-инстанс лаунчер, EndSol заметит это и продолжит мониторинг, не перехватывая блокировку.",
    "Roblox may still close additional windows on its own — no launcher can prevent that.": "Roblox может сам закрывать лишние окна — ни один лаунчер этого не предотвращает.",
    "Session tokens are stored only on this PC, encrypted with Windows DPAPI. They are never sent anywhere except Roblox's own authentication API.": "Токены сессий хранятся только на этом ПК в шифрованном виде и никуда не отправляются, кроме API аутентификации Roblox.",
    "API bridge is not ready yet — wait a second and try again.": "API ещё не готов — подождите секунду и попробуйте снова.",
    "Failed to toggle mode.": "Не удалось переключить режим.",
    "Mode enabled. The full detector runs on the main window; secondary windows get Anti-AFK and alerts while the macro is active.": "Режим включён. Полный детектор работает на главном окне; вторые окна получают Anti-AFK и алерты, пока макрос активен.",
    "Mode disabled. Normal single-window macro is available again.": "Режим выключен. Снова доступен обычный режим одного окна.",
    "Toggle failed": "Ошибка переключения",
    "Failed to set the main window.": "Не удалось выбрать главное окно.",
    "Main window set to PID": "Главное окно: PID",
    "Main window set to automatic.": "Главное окно — автоматически.",
    "Failed to set the main window": "Не удалось выбрать главное окно",
    "Waiting for login in the new Roblox window…": "Ожидание входа в новом окне Roblox…",
    "Discord Webhook Customization": "Кастомизация вебхуков",
    "Panel Customization": "Кастомизация панели",
    "Instructions": "Инструкции",
    "Credits": "Авторы",
    "Donations <3": "Донаты <3",

    // ── Common ──
    "Cancel": "Отмена",
    "Close": "Закрыть",
    "Open Folder": "Открыть папку",
    "Reset stats": "Сброс статистики",
    "Yes, reset everything": "Да, сбросить всё",
    "Reset statistics?": "Сбросить статистику?",
    "Biome, merchant and aura counters plus session time will be wiped. This cannot be undone.":
        "Счётчики биомов, мерчантов и аур, а также время сессии будут обнулены. Действие необратимо.",
    "Statistics reset.": "Статистика сброшена.",
    "Failed to reset statistics.": "Не удалось сбросить статистику.",
    "Reset is not available in this build.": "Сброс недоступен в этой сборке.",
    "Reset biomes, merchants, auras and session time": "Сбросить счётчики биомов, аур, мерчантов и время сессии",

    // ── Stats ──
    "Session statistics and biome encounter history": "Статистика сессии и история встреч с биомами",
    "Session Overview": "Обзор сессии",
    "Current macro session statistics": "Текущая статистика макроса",
    "Session Time": "Время сессии",
    "Total Biomes Founds": "Всего биомов",
    "Merchants Found": "Мерчантов найдено",
    "Normal (Weather)": "Обычные (погода)",
    "Rare": "Редкие",
    "Event (Limited)": "Ивентовые (лимитка)",
    "Admin (Dev Event)": "Админские (ивент разработчиков)",
    "Other / Unlisted": "Другие / неучтённые",

    // ── Remote Access ──
    "Remote Access": "Удалённое управление",
    "Control your macro remotely via a Discord bot": "Управляйте макросом удалённо через Discord-бота",
    "Remote Access — Help": "Удалённое управление — помощь",
    "Setup": "Настройка",
    "Commands (slash commands in Discord)": "Команды (слэш-команды в Discord)",
    "Start the macro": "Запустить макрос",
    "Stop the macro": "Остановить макрос",
    "Status, biome, session time, biome counts": "Статус, биом, время сессии, счётчики биомов",
    "Use an item remotely": "Использовать предмет удалённо",
    "Equip an aura by name": "Надеть ауру по названию",
    "Teleport to the merchant and check it": "Телепорт к мерчанту и его проверка",
    "Screenshot to your webhooks": "Скриншот в ваши вебхуки",
    "Reroll a daily quest": "Перевыбрать дневной квест",
    "Close Roblox to force a rejoin (Auto Reconnect needed)": "Закрыть Roblox для переподключения (нужен Auto Reconnect)",
    "Kill Roblox and stop the macro": "Убить Roblox и остановить макрос",
    "This list in Discord": "Этот список в Discord",
    "Commands only work from the Allowed User ID. Some actions are blocked while the macro is in an uninterruptible mode (e.g. Fishing).":
        "Команды работают только с ID из Allowed User ID. Часть действий недоступна в непрерываемых режимах (например, рыбалка).",
    "Enable Remote Access Control": "Включить удалённое управление",
    "Turns the Discord bot online/offline immediately (bot must be started with the macro running).":
        "Включает/выключает Discord-бота (бот работает вместе с макросом).",
    "Discord Bot Token:": "Токен Discord-бота:",
    "Allowed User ID:": "Разрешённый User ID:",
    "Enter your Discord bot token": "Введите токен Discord-бота",
    "Setup tutorial": "Видео-инструкция",

    // ── Multiple-Instances ──
    "EXTERNAL WINDOW MONITOR": "ВНЕШНИЙ МОНИТОР ОКОН",
    "Support for windows launched via Avaluate MultipleRobloxInstances.":
        "Поддержка окон, запущенных через Avaluate MultipleRobloxInstances.",
    "Enabled": "Включено",
    "Disabled": "Выключено",
    "Roblox windows": "окон Roblox",
    "Important": "Важно",
    "SUPPORTED WORKFLOW": "ПОРЯДОК ЗАПУСКА",
    "How to launch multiple accounts": "Как запустить несколько аккаунтов",
    "DETECTED WINDOWS": "ОБНАРУЖЕННЫЕ ОКНА",
    "Roblox Windows": "Окна Roblox",
    "No windows found. Open Roblox via Avaluate and click refresh.":
        "Окна не найдены. Откройте Roblox через Avaluate и обновите страницу.",
    "RUNTIME POLICY": "ОГРАНИЧЕНИЯ РЕЖИМА",
    "Mode Restrictions": "Ограничения режима",
    "Ordered Anti-AFK — one window at a time": "Anti-AFK по очереди — по одному окну",
    "Statistics and recording — disabled": "Статистика и запись — отключены",
    "Main window": "Основное окно",
    "Auto (window of the configured account)": "Авто (окно настроенного аккаунта)",
    "Resolved main window": "Определённое основное окно",
    "All full macro features run on the main window.": "Все полноценные функции макроса работают на основном окне.",
    "How the mode works": "Как работает режим",
    "Full detector, fishing and all actions — on the main window": "Полный детектор, рыбалка и все действия — на основном окне",
    "Ordered Anti-AFK on secondary windows — one at a time": "Anti-AFK на второстепенных окнах — по одному за раз",
    "Biome, aura and disconnect alerts from every secondary window": "Алерты биомов, аур и дисконнектов с каждого второстепенного окна",
    "Anti-AFK on secondary windows waits for a free window of the main cycle — no bite, no sale, no scheduled action.":
        "Anti-AFK второстепенных окон ждёт свободного окна основного цикла — нет поклёвки, продажи и запланированных действий.",
    "Alerts from other windows": "Алерты с других окон",
    "Alerts use your normal Discord webhook list. Threshold 0 = every aura roll.": "Алерты идут в ваш обычный список Discord-вебхуков. Порог 0 = каждая выпавшая аура.",
    "MULTI-INSTANCE WEBHOOK": "ВЕБХУК МУЛЬТИ-ИНСТАНСА",
    "Dedicated Discord webhook": "Отдельный Discord-вебхук",
    "A separate webhook for multi-instance status: when the mode is running and how many windows it tracks (start, windows opened/closed, stop). Leave empty to reuse your main webhook list.":
        "Отдельный вебхук для статуса мульти-инстанса: когда режим запущен и сколько окон он отслеживает (старт, открытие/закрытие окон, остановка). Оставьте пустым, чтобы использовать основной список вебхуков.",
    "Webhook URL": "URL вебхука",
    "ANTI-AFK TIMING": "ТАЙМИНГ ANTI-AFK",
    "Jump timing": "Тайминг прыжков",
    "Wait after focusing a secondary window and after each jump. Raise both on weak hardware / low FPS so jumps are not dropped.":
        "Пауза после фокусировки второстепенного окна и после каждого прыжка. Увеличьте оба значения на слабом железе / низком FPS, чтобы прыжки не терялись.",
    "Focus wait (seconds)": "Ожидание фокуса (сек)",
    "Jump settle wait (seconds)": "Ожидание после прыжка (сек)",
    "INSTANCE ALERTS": "АЛЕРТЫ ИНСТАНСОВ",
    "Instance alerts": "Алерты инстансов",
    "Rare biomes + auras above the rarity threshold + disconnects, per window.": "Редкие биомы + ауры выше порога редкости + дисконнекты, по каждому окну.",
    "Rare biomes only": "Только редкие биомы",
    "This account already has a running client": "У этого аккаунта уже запущен клиент",
    "Running": "Запущен",
    "running": "запущен",
    "Aura rarity threshold": "Порог редкости аур",
    "Reads every window's own Roblox log and sends biome, aura and disconnect alerts to your webhooks. The main instance is covered by the main detector.":
        "Читает собственный лог каждого окна и шлёт алерты биомов, аур и дисконнектов в ваши вебхуки. Основной инстанс покрыт основным детектором.",
    "main instance": "основное окно",

    // ── Remote access (bot) ──
    "Bot status: unknown": "Статус бота: неизвестен",
    "Bot status: online": "Статус бота: онлайн",
    "Bot status: offline": "Статус бота: офлайн",
    "Restart bot": "Перезапустить бота",
    "Stops the bot and starts a fresh Discord session": "Останавливает бота и запускает новую Discord-сессию",
    "Restarting the bot…": "Перезапускаю бота…",
    "Bot restarted — connecting to Discord…": "Бот перезапущен — подключаюсь к Discord…",
    "Bot thread did not survive startup — check the logs": "Поток бота не пережил запуск — проверьте логи",
    "Restart failed": "Не удалось перезапустить",

    // ── Reset settings ──
    "Reset All Settings": "Сбросить все настройки",
    "Reset settings": "Сбросить настройки",
    "Click again to confirm": "Нажмите ещё раз для подтверждения",
    "Reset failed": "Сброс не удался",
    "All settings were reset to defaults": "Все настройки сброшены к значениям по умолчанию",
    "Resets every setting of the active config to defaults. Webhooks and the bot token are kept; a backup of the old config is saved. The panel reloads after the reset.":
        "Сбрасывает все настройки активного конфига к значениям по умолчанию. Вебхуки и токен бота сохраняются; старый конфиг остаётся в бэкапе. Панель перезагрузится после сброса.",
    "LIVE": "АКТИВНО",
    "The queue is sorted by launch order. If a window closes or can't be focused, it is skipped and the rest continue.":
        "Окна обрабатываются по порядку запуска. Если окно закрыто или его нельзя сфокусировать — оно пропускается, остальные продолжают.",

    // ── Other Features / System Settings ──
    "Application-wide preferences": "Общие настройки приложения",
    "System Settings": "Настройки системы",
    "Open AppData Folder": "Открыть папку AppData",
    "Opens the folder where logs, config, and macro data are stored":
        "Открывает папку с логами, конфигом и данными макроса",
    "Language": "Язык",
    "Panel interface language": "Язык интерфейса панели",
    "Anti-AFK": "Anti-AFK",
    "Prevents Roblox disconnection even when Roblox isn't focused":
        "Защищает от дисконнекта Roblox, даже когда окно не в фокусе",
    "Panel language": "Язык панели",
    "English": "English",
    "Russian": "Русский",
    "Change language?": "Сменить язык?",
    "Switching the language resets your custom tab names (panel customization), because custom labels take priority over translated defaults.":
        "При смене языка кастомные названия вкладок будут сброшены — кастомизация имеет приоритет над переводом.",
    "Switch language": "Сменить язык",

    "Additional macro capabilities and experimental options": "Дополнительные возможности макроса и экспериментальные опции",

    // ── Notice ──
    "Current EndSol Macro changes": "Изменения EndSol Macro",

    // ── Update banner (Notice page) ──
    "Update": "Обновить",
    "Retry Update": "Повторить обновление",
    "Don't notify again": "Не уведомлять больше",
    "New EndSol Macro version is available": "Доступна новая версия EndSol Macro",
    "Downloading update...": "Скачивание обновления...",
    "Updated!": "Обновлено!",
    "Restarting": "Перезапуск",
    "Update failed. Please try downloading again.": "Не удалось обновить. Попробуйте скачать ещё раз.",

    // ── Config Profiles ──
    "Select a profile…": "Выберите профиль…",
    "No saved profiles": "Нет сохранённых профилей",
    "Failed to delete profile": "Не удалось удалить профиль",
    "Enter a profile name first": "Сначала введите имя профиля",
    "Failed to load profile": "Не удалось загрузить профиль",

    // ── Other Features descriptions ──
    "Automatically check for, download and install new releases on startup (EXE builds only). When OFF, the panel still checks on startup and shows an update notice on the Notice page.":
        "Автоматически проверять, скачивать и устанавливать новые релизы при запуске (только EXE-сборка). Когда выключено — панель всё равно проверяет обновления при старте и показывает уведомление на странице «Новости».",
    "Panel GPU acceleration": "GPU-ускорение панели",
    "Lets the panel use your graphics card for rendering instead of the CPU. Can noticeably improve FPS in Sol's Book and heavy pages. If the panel shows glitches or a black screen, turn this off again. Takes effect after a restart.":
        "Позволяет панели использовать видеокарту для рендеринга вместо процессора. Может заметно поднять FPS в Sol's Book и на тяжёлых страницах. Если панель начнёт глючить или покажет чёрный экран — выключите обратно. Вступает в силу после перезапуска.",

    // ── Memory Match log strings shown in the Status/log panel ──
    "Session statistics and biome encounter history ": "Статистика сессии и история встреч с биомами",
};

export function translate(text: string, lang?: string | null): string {
    if (lang === "ru") {
        return RU[text] ?? text;
    }
    return text;
}

export function normalizeLang(raw: unknown): Lang {
    return String(raw ?? "").toLowerCase().startsWith("ru") ? "ru" : "en";
}

export function usePanelLang(): Lang {
    const { config } = useConfig();
    return normalizeLang((config as Record<string, unknown> | null)?.panel_language);
}

/** Translate a static UI string according to the current panel language. */
export function useT() {
    const lang = usePanelLang();
    return (text: string) => translate(text, lang);
}

// ─────────────────────────────────────────────────────────────────────────
// DOM auto-translation: applies the dictionary to text nodes and common
// attributes (placeholder / title / aria-label) at runtime, so UI strings
// do not have to be wrapped with t() in every component. Sol's Book
// (data-no-i18n) and constantly-mutating glitch text are skipped; the
// original English is stored so switching back to EN restores it.
// ─────────────────────────────────────────────────────────────────────────
const I18N_ORIG = "__i18nOrig";
const SKIP_TAGS = new Set(["SCRIPT", "STYLE", "CODE", "PRE", "TEXTAREA", "NOSCRIPT"]);

function shouldSkip(el: Element | null): boolean {
    return !!(el && (el.closest("[data-no-i18n]") || el.closest(".glitch-text") || SKIP_TAGS.has(el.tagName)));
}

export function applyDomTranslations(root: ParentNode = document.body) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    while ((node = walker.nextNode())) {
        const parent = node.parentElement;
        if (!parent || shouldSkip(parent)) continue;
        const text = node.nodeValue || "";
        const trimmed = text.trim();
        if (!trimmed) continue;
        // Multi-line JSX text nodes keep internal newlines/indentation; fall
        // back to a whitespace-collapsed lookup so long paragraphs translate.
        const collapsed = trimmed.replace(/\s+/g, " ");
        const ru = RU[trimmed] ?? (trimmed !== collapsed ? RU[collapsed] : undefined);
        if (ru && ru !== trimmed) {
            const anyNode = node as unknown as Record<string, unknown>;
            if (anyNode[I18N_ORIG] === undefined) anyNode[I18N_ORIG] = text;
            node.nodeValue = text.replace(trimmed, ru);
        }
    }
    root.querySelectorAll?.("[placeholder], [title], [aria-label]").forEach((el) => {
        if (shouldSkip(el)) return;
        for (const attr of ["placeholder", "title", "aria-label"] as const) {
            const val = el.getAttribute(attr);
            if (!val) continue;
            const t = val.trim();
            const tc = t.replace(/\s+/g, " ");
            const ru = RU[t] ?? (t !== tc ? RU[tc] : undefined);
            if (ru && ru !== val.trim()) {
                const store = `data-i18n-orig-${attr}`;
                if (!el.hasAttribute(store)) el.setAttribute(store, val);
                el.setAttribute(attr, ru);
            }
        }
    });
}

export function restoreDomTranslations(root: ParentNode = document.body) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
    let node: Node | null;
    while ((node = walker.nextNode())) {
        const anyNode = node as unknown as Record<string, unknown>;
        const orig = anyNode[I18N_ORIG];
        if (typeof orig === "string") {
            node.nodeValue = orig;
            delete anyNode[I18N_ORIG];
        }
    }
    root.querySelectorAll?.("[data-i18n-orig-placeholder], [data-i18n-orig-title], [data-i18n-orig-aria-label]").forEach((el) => {
        for (const attr of ["placeholder", "title", "aria-label"] as const) {
            const store = `data-i18n-orig-${attr}`;
            const orig = el.getAttribute(store);
            if (orig !== null) {
                el.setAttribute(attr, orig);
                el.removeAttribute(store);
            }
        }
    });
}

let i18nObserver: MutationObserver | null = null;
let i18nDebounce = 0;
/** True only while the panel language is "ru". A stale debounced
 * applyDomTranslations() must never run after a switch back to EN. */
let i18nRuActive = false;

function i18nStopWatcher() {
    if (i18nObserver) { i18nObserver.disconnect(); i18nObserver = null; }
    window.clearTimeout(i18nDebounce);
    i18nDebounce = 0;
}

/** Mount once inside App: re-applies DOM translation whenever it changes. */
export function I18nDom() {
    const lang = usePanelLang();
    useEffect(() => {
        if (lang !== "ru") {
            i18nRuActive = false;
            i18nStopWatcher();
            restoreDomTranslations();
            return;
        }
        i18nRuActive = true;
        applyDomTranslations();
        i18nStopWatcher();
        i18nObserver = new MutationObserver(() => {
            window.clearTimeout(i18nDebounce);
            i18nDebounce = window.setTimeout(() => {
                if (i18nRuActive) applyDomTranslations();
            }, 120);
        });
        i18nObserver.observe(document.body, { childList: true, subtree: true, characterData: true });
        return () => {
            i18nRuActive = false;
            i18nStopWatcher();
        };
    }, [lang]);
    return null;
}
