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
