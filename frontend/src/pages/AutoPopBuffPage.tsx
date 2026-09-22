import { useState, useEffect, useCallback } from "react";
import { useConfig, type AppConfig } from "../contexts/ConfigContext";

type BuffSelection = [boolean, number];
type BuffConfig = Record<string, BuffSelection>;
type AutoPopBiomeEntry = {
    enabled: boolean;
    buffs: BuffConfig;
    order: string[];
};
type AutoPopBiomeMap = Record<string, AutoPopBiomeEntry>;

const RARE_BIOMES = ["GLITCHED", "DREAMSPACE", "CYBERSPACE", "SINGULARITY"];
const EVENT_BIOMES = ["AURORA", "EGGLAND", "BLAZING SUN", "INCINERATOR", "PUMPKIN MOON", "GRAVEYARD", "BLOOD RAIN"];
const ADMIN_BIOMES = ["THE HYPERSPACE REALM", "\u8d64\u3044\u6e80\u6708", "THE NULL'S EXISTENCE", "THE CITADEL OF ORDERS"];
const DEFAULT_BUFFS = [
    "Fortune Potion I",
    "Fortune Potion II",
    "Fortune Potion III",
    "Godlike Potion",
    "Haste Potion I",
    "Haste Potion II",
    "Haste Potion III",
    "Heavenly Potion",
    "Lucky Potion",
    "Oblivion Potion",
    "Potion of bound",
    "Rune of Everything",
    "Speed Potion",
    "Stella's Candle",
    "Strange Potion I",
    "Strange Potion II",
    "Transcendent Potion",
    "Warp Potion",
    "Xyz Potion",
];
const FALLBACK_BIOME_COLORS: Record<string, string> = {
    WINDY: "#9ae5ff",
    RAINY: "#027cbd",
    SNOWY: "#dceff9",
    "SAND STORM": "#8f7057",
    HELL: "#ff4719",
    STARFALL: "#011ab7",
    CORRUPTION: "#6d32a8",
    NULL: "#838383",
    GLITCHED: "#bfff00",
    DREAMSPACE: "#ea9dda",
    CYBERSPACE: "#0a1a3d",
    AURORA: "#56d6a0",
    HEAVEN: "#dfaf63",
    EGGLAND: "#d4fc8d",
    INCINERATOR: "#3b1f1f",
    SINGULARITY: "#cf4023",
};

function normalizeColor(value: string | undefined): string {
    if (!value) return "#9ca3af";
    return value.startsWith("0x") ? `#${value.slice(2)}` : value;
}

function normalizeBuffConfig(raw: unknown, customItems: string[] = []): BuffConfig {
    const normalized: BuffConfig = {};
    // Include default buffs
    for (const buffName of DEFAULT_BUFFS) {
        normalized[buffName] = [false, 1];
    }
    // Include custom items
    for (const buffName of customItems) {
        if (!normalized[buffName]) {
            normalized[buffName] = [false, 1];
        }
    }

    if (!raw || typeof raw !== "object") {
        return normalized;
    }

    for (const [buffName, buffValue] of Object.entries(raw as Record<string, unknown>)) {
        let enabled = false;
        let amount = 1;

        if (Array.isArray(buffValue)) {
            enabled = Boolean(buffValue[0]);
            amount = Math.max(1, Number(buffValue[1]) || 1);
        }

        normalized[buffName] = [enabled, amount];
    }

    return normalized;
}

function getAutoPopBiomes(config: Record<string, unknown>, customItems: string[] = []): AutoPopBiomeMap {
    const raw = config.auto_pop_biomes;
    if (!raw || typeof raw !== "object") {
        return {};
    }

    const normalized: AutoPopBiomeMap = {};
    for (const [biomeName, entry] of Object.entries(raw as Record<string, unknown>)) {
        const rawEntry = entry && typeof entry === "object" ? entry as Record<string, unknown> : {};
        const buffs = normalizeBuffConfig(rawEntry.buffs, customItems);
        const rawOrder = Array.isArray(rawEntry.order) ? rawEntry.order.filter((item): item is string => typeof item === "string") : [];
        const order = [...rawOrder.filter((item, index) => item in buffs && rawOrder.indexOf(item) === index)];
        for (const item of Object.keys(buffs)) {
            if (!order.includes(item)) order.push(item);
        }
        normalized[biomeName] = {
            enabled: Boolean(rawEntry.enabled),
            buffs,
            order,
        };
    }

    return normalized;
}

function getBiomeNames(config: Record<string, unknown>, autoPopBiomes: AutoPopBiomeMap): string[] {
    const names = new Set<string>();

    for (const biomeName of Object.keys(autoPopBiomes)) {
        if (biomeName && biomeName !== "NORMAL") {
            names.add(biomeName);
        }
    }

    const biomeCounts = config.biome_counts;
    if (biomeCounts && typeof biomeCounts === "object") {
        for (const biomeName of Object.keys(biomeCounts as Record<string, unknown>)) {
            if (biomeName && biomeName !== "NORMAL") {
                names.add(biomeName);
            }
        }
    }

    const biomeNotifier = config.biome_notifier;
    if (biomeNotifier && typeof biomeNotifier === "object") {
        for (const biomeName of Object.keys(biomeNotifier as Record<string, unknown>)) {
            if (biomeName && biomeName !== "NORMAL") {
                names.add(biomeName);
            }
        }
    }

    const orderedRare = RARE_BIOMES.filter((biomeName) => names.has(biomeName));
    const orderedOther = [...names].filter((biomeName) =>
        !RARE_BIOMES.includes(biomeName) && !EVENT_BIOMES.includes(biomeName) && !ADMIN_BIOMES.includes(biomeName)
    ).sort();
    return [...orderedRare, ...orderedOther];
}

function getBiomeEntry(autoPopBiomes: AutoPopBiomeMap, biomeName: string): AutoPopBiomeEntry {
    if (autoPopBiomes[biomeName]) return autoPopBiomes[biomeName];
    const buffs = normalizeBuffConfig(undefined);
    return { enabled: false, buffs, order: Object.keys(buffs) };
}

function countEnabledBuffs(buffs: BuffConfig): number {
    return Object.values(buffs).filter(([enabled]) => enabled).length;
}

function getBiomeColor(config: Record<string, unknown>, biomeName: string, contextColors?: Record<string, string>): string {
    const overrides = config.custom_biome_overrides;
    if (overrides && typeof overrides === "object") {
        const biomeOverride = (overrides as Record<string, { color?: string }>)[biomeName];
        if (biomeOverride?.color) {
            return normalizeColor(biomeOverride.color);
        }
    }

    if (contextColors && contextColors[biomeName]) {
        return contextColors[biomeName];
    }

    return FALLBACK_BIOME_COLORS[biomeName] ?? "#9ca3af";
}

export default function AutoPopBuffPage() {
    const { config, saveConfig, error, biomeColors: contextColors } = useConfig();
    const [selectedBiome, setSelectedBiome] = useState<string | null>(null);
    const [customItems, setCustomItems] = useState<string[]>([]);
    const [newItemName, setNewItemName] = useState("");
    const [itemError, setItemError] = useState("");
    const [itemSuccess, setItemSuccess] = useState("");
    const [draggedBuff, setDraggedBuff] = useState<string | null>(null);

    // Load custom items from backend on mount
    const loadCustomItems = useCallback(async () => {
        try {
            const api = window.pywebview?.api;
            if (api && typeof api.get_auto_pop_items === "function") {
                const result = await api.get_auto_pop_items() as { items: string[]; custom: string[] };
                if (result && Array.isArray(result.custom)) {
                    setCustomItems(result.custom);
                }
            } else {
                // Fallback: read from config
                const typedConfig = (config ?? {}) as Record<string, unknown>;
                const custom = typedConfig.custom_auto_pop_buffs;
                if (Array.isArray(custom)) {
                    setCustomItems(custom.filter((x): x is string => typeof x === "string"));
                }
            }
        } catch {
            // API not available, use config fallback
            const typedConfig = (config ?? {}) as Record<string, unknown>;
            const custom = typedConfig.custom_auto_pop_buffs;
            if (Array.isArray(custom)) {
                setCustomItems(custom.filter((x): x is string => typeof x === "string"));
            }
        }
    }, [config]);

    useEffect(() => {
        loadCustomItems();
    }, [loadCustomItems]);

    const addCustomItem = async () => {
        const name = newItemName.trim();
        if (!name) {
            setItemError("Enter an item name");
            return;
        }
        setItemError("");
        setItemSuccess("");
        try {
            const api = window.pywebview?.api;
            if (api && typeof api.add_auto_pop_item === "function") {
                const result = await api.add_auto_pop_item(name) as { success: boolean; error?: string; custom?: string[]; items?: string[] };
                if (result.success) {
                    // Use whatever backend returned, fall back to merging with current state
                    const returnedItems = Array.isArray(result.custom) ? result.custom : result.items;
                    const updated = Array.isArray(returnedItems) && returnedItems.length > 0
                        ? returnedItems
                        : [...customItems.filter((i) => i !== name), name];
                    setCustomItems(updated);
                    setNewItemName("");
                    setItemSuccess(`Added "${name}"`);
                    return;
                } else {
                    setItemError(result.error ?? "Failed to add item");
                    return;
                }
            }
            // Fallback: update config directly (API missing or no method)
            const typedConfig = (config ?? {}) as Record<string, unknown>;
            const existing = Array.isArray(typedConfig.custom_auto_pop_buffs)
                ? (typedConfig.custom_auto_pop_buffs as string[])
                : [];
            if (DEFAULT_BUFFS.includes(name) || existing.includes(name)) {
                setItemError("Item already exists");
                return;
            }
            const updated = [...existing, name];
            saveConfig({ ...config, custom_auto_pop_buffs: updated } as AppConfig);
            setCustomItems(updated);
            setNewItemName("");
            setItemSuccess(`Added "${name}"`);
        } catch {
            setItemError("Failed to add item");
        }
    };

    const removeCustomItem = async (name: string) => {
        try {
            const api = window.pywebview?.api;
            if (api && typeof api.remove_auto_pop_item === "function") {
                const result = await api.remove_auto_pop_item(name) as { success: boolean; error?: string; custom?: string[]; items?: string[] };
                if (result.success) {
                    setCustomItems(result.custom ?? result.items ?? customItems.filter((i) => i !== name));
                }
            } else {
                const typedConfig = (config ?? {}) as Record<string, unknown>;
                const existing = Array.isArray(typedConfig.custom_auto_pop_buffs)
                    ? (typedConfig.custom_auto_pop_buffs as string[])
                    : [];
                const updated = existing.filter((i) => i !== name);
                saveConfig({ ...config, custom_auto_pop_buffs: updated } as AppConfig);
                setCustomItems(updated);
            }
        } catch {
            // ignore
        }
    };

    if (error) {
        return (
            <div style={{ padding: "20px", color: "#ef4444" }}>
                <h3>Error Loading Settings</h3>
                <p>{error}</p>
            </div>
        );
    }

    if (!config) {
        return <div style={{ padding: "20px" }}>Loading auto pop buff settings...</div>;
    }

    const typedConfig = (config ?? {}) as Record<string, unknown>;
    const autoPopBiomes = getAutoPopBiomes(typedConfig, customItems);
    const biomeNames = getBiomeNames(typedConfig, autoPopBiomes);
    const rareBiomes = biomeNames.filter((biomeName) => RARE_BIOMES.includes(biomeName));
    const eventBiomes = biomeNames.filter((biomeName) => EVENT_BIOMES.includes(biomeName));
    const adminBiomes = biomeNames.filter((biomeName) => ADMIN_BIOMES.includes(biomeName));
    const otherBiomes = biomeNames.filter((biomeName) =>
        !RARE_BIOMES.includes(biomeName) && !EVENT_BIOMES.includes(biomeName) && !ADMIN_BIOMES.includes(biomeName)
    );
    const activeBiomeEntry = selectedBiome ? getBiomeEntry(autoPopBiomes, selectedBiome) : null;

    const saveAutoPopBiomes = (nextBiomes: AutoPopBiomeMap) => {
        saveConfig({
            ...config,
            auto_pop_biomes: nextBiomes,
        });
    };

    const updateBiomeEnabled = (biomeName: string, enabled: boolean) => {
        const currentEntry = getBiomeEntry(autoPopBiomes, biomeName);
        saveAutoPopBiomes({
            ...autoPopBiomes,
            [biomeName]: {
                ...currentEntry,
                enabled,
            },
        });
    };

    const updateBuffSelection = (biomeName: string, buffName: string, field: "enabled" | "amount", value: boolean | string) => {
        const currentEntry = getBiomeEntry(autoPopBiomes, biomeName);
        const nextBuffs = {
            ...currentEntry.buffs,
        };
        const currentBuff = nextBuffs[buffName] ?? [false, 1];
        nextBuffs[buffName] = field === "enabled"
            ? [Boolean(value), currentBuff[1]]
            : [currentBuff[0], Math.max(1, Number(value) || 1)];

        saveAutoPopBiomes({
            ...autoPopBiomes,
            [biomeName]: {
                ...currentEntry,
                buffs: nextBuffs,
            },
        });
    };

    const setBuffOrder = (biomeName: string, buffName: string, targetIndex: number) => {
        const currentEntry = getBiomeEntry(autoPopBiomes, biomeName);
        const order = [...currentEntry.order];
        const sourceIndex = order.indexOf(buffName);
        if (sourceIndex < 0) return;
        const boundedIndex = Math.max(0, Math.min(targetIndex, order.length - 1));
        if (sourceIndex === boundedIndex) return;
        order.splice(sourceIndex, 1);
        order.splice(boundedIndex, 0, buffName);
        saveAutoPopBiomes({
            ...autoPopBiomes,
            [biomeName]: { ...currentEntry, order },
        });
    };

    const handleBuffDrop = (biomeName: string, targetBuffName: string) => {
        if (!draggedBuff || draggedBuff === targetBuffName) return;
        const currentEntry = getBiomeEntry(autoPopBiomes, biomeName);
        const targetIndex = currentEntry.order.indexOf(targetBuffName);
        setBuffOrder(biomeName, draggedBuff, targetIndex);
        setDraggedBuff(null);
    };

    const renderBiomeRows = (title: string, biomes: string[]) => {
        if (!biomes.length) {
            return null;
        }

        return (
            <div className="card">
                <div className="card-header">
                    <div className="card-icon">🧪</div>
                    <div>
                        <h3>{title}</h3>
                        <p>Enable exact biome triggers and configure a separate buff loadout for each one</p>
                    </div>
                </div>

                <div style={{ display: "grid", gap: "10px" }}>
                    {biomes.map((biomeName) => {
                        const biomeEntry = getBiomeEntry(autoPopBiomes, biomeName);
                        const enabledBuffs = countEnabledBuffs(biomeEntry.buffs);
                        const biomeColor = getBiomeColor(typedConfig, biomeName, contextColors);

                        return (
                            <div
                                key={biomeName}
                                style={{
                                    display: "grid",
                                    gridTemplateColumns: "1fr auto auto",
                                    gap: "12px",
                                    alignItems: "center",
                                    padding: "12px 14px",
                                    border: "1px solid var(--border-color)",
                                    background: biomeEntry.enabled ? "rgba(255,255,255,0.04)" : "rgba(255,255,255,0.02)",
                                }}
                            >
                                <div>
                                    <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "4px" }}>
                                        <span style={{ width: "10px", height: "10px", borderRadius: "999px", background: biomeColor }} />
                                        <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>{biomeName}</span>
                                    </div>
                                    <div className="form-hint">
                                        {enabledBuffs > 0 ? `${enabledBuffs} buff${enabledBuffs === 1 ? "" : "s"} selected` : "No buffs selected yet"}
                                    </div>
                                </div>

                                <button
                                    className="btn btn-secondary"
                                    style={{ whiteSpace: "nowrap" }}
                                    onClick={() => setSelectedBiome(biomeName)}
                                >
                                    Buff Selection
                                </button>

                                <label style={{ display: "flex", alignItems: "center", gap: "8px", whiteSpace: "nowrap", color: "var(--text-secondary)" }}>
                                    <input
                                        type="checkbox"
                                        checked={biomeEntry.enabled}
                                        onChange={(event) => updateBiomeEnabled(biomeName, event.target.checked)}
                                        style={{ width: "16px", height: "16px" }}
                                    />
                                    Enable
                                </label>
                            </div>
                        );
                    })}
                </div>
            </div>
        );
    };

    return (
        <>
            {selectedBiome && activeBiomeEntry && (
                <div
                    className="modal-overlay"
                    style={{
                        position: "fixed",
                        top: 0,
                        left: 0,
                        right: 0,
                        bottom: 0,
                        backgroundColor: "rgba(0,0,0,0.72)",
                        zIndex: 1000,
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                    }}
                >
                    <div
                        className="modal-content"
                        style={{
                            backgroundColor: "var(--bg-card)",
                            padding: "22px",
                            width: "760px",
                            maxHeight: "84vh",
                            overflowY: "auto",
                            border: "1px solid var(--border-color)",
                            boxShadow: "0 10px 30px rgba(0,0,0,0.45)",
                        }}
                    >
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "16px", marginBottom: "18px" }}>
                            <div>
                                <h3 style={{ margin: 0 }}>{selectedBiome} Buff Selection</h3>
                                <p style={{ margin: "6px 0 0 0", color: "var(--text-secondary)", fontSize: "13px" }}>
                                    Enabled items are used from top to bottom. Drag an item to another row, or use Top/Bottom for quick rearranging.
                                </p>
                            </div>
                            <button className="btn btn-secondary" onClick={() => setSelectedBiome(null)}>Close</button>
                        </div>

                        <div className="buff-grid">
                            {activeBiomeEntry.order.map((buffName, orderIndex) => {
                                const [enabled, amount] = activeBiomeEntry.buffs[buffName] ?? [false, 1];
                                return (
                                    <div
                                        key={buffName}
                                        className="buff-item"
                                        draggable
                                        onDragStart={(event) => {
                                            setDraggedBuff(buffName);
                                            event.dataTransfer.effectAllowed = "move";
                                            event.dataTransfer.setData("text/plain", buffName);
                                        }}
                                        onDragOver={(event) => event.preventDefault()}
                                        onDrop={(event) => {
                                            event.preventDefault();
                                            handleBuffDrop(selectedBiome, buffName);
                                        }}
                                        onDragEnd={() => setDraggedBuff(null)}
                                        style={{
                                            cursor: "grab",
                                            opacity: draggedBuff === buffName ? 0.55 : 1,
                                        }}
                                    >
                                        <label style={{ display: "flex", alignItems: "center", gap: "8px", flex: 1 }}>
                                            <input
                                                type="checkbox"
                                                checked={enabled}
                                                onChange={(event) => updateBuffSelection(selectedBiome, buffName, "enabled", event.target.checked)}
                                            />
                                            <span className="buff-name">{buffName}</span>
                                        </label>
                                        <span style={{ color: "var(--text-secondary)", fontSize: "12px", minWidth: "22px" }}>#{orderIndex + 1}</span>
                                        <button
                                            type="button"
                                            className="btn btn-secondary"
                                            style={{ padding: "3px 7px", fontSize: "12px" }}
                                            disabled={orderIndex === 0}
                                            onClick={() => setBuffOrder(selectedBiome, buffName, 0)}
                                            title="Move to top"
                                        >Top</button>
                                        <button
                                            type="button"
                                            className="btn btn-secondary"
                                            style={{ padding: "3px 7px", fontSize: "12px" }}
                                            disabled={orderIndex === activeBiomeEntry.order.length - 1}
                                            onClick={() => setBuffOrder(selectedBiome, buffName, activeBiomeEntry.order.length - 1)}
                                            title="Move to bottom"
                                        >Bottom</button>
                                        <input
                                            className="form-input buff-amount"
                                            style={{ width: "65px", padding: "4px 8px" }}
                                            type="number"
                                            min="1"
                                            value={amount}
                                            onChange={(event) => updateBuffSelection(selectedBiome, buffName, "amount", event.target.value)}
                                        />
                                    </div>
                                );
                            })}
                        </div>
                    </div>
                </div>
            )}

            <div className="page-header">
                <h2>Auto Pop Buff</h2>
                <p>Use separate biome-specific buff loadouts instead of the old rare-vs-normal grouping</p>
            </div>

            <div className="info-banner" style={{ marginBottom: "16px" }}>
                Auto Pop Buff uses every enabled item for the exact detected biome, in the order shown in that biome's Buff Selection. Missing or newly added items are appended safely instead of being silently dropped.
            </div>

            {renderBiomeRows("Rare Biomes", rareBiomes)}
            {renderBiomeRows("Event Biomes", eventBiomes)}
            {renderBiomeRows("Admin Biomes", adminBiomes)}
            {renderBiomeRows("Other Biomes", otherBiomes)}

            {/* ── Custom Items Manager ── */}
            <div className="card" style={{ marginTop: "16px" }}>
                <div className="card-header">
                    <div className="card-icon">📦</div>
                    <div>
                        <h3>Custom Items for Auto-Use in Biome</h3>
                        <p>Add your own items to the buff selection list for each biome</p>
                    </div>
                </div>

                <div style={{ display: "flex", gap: "8px", marginBottom: "12px" }}>
                    <input
                        className="form-input"
                        style={{ flex: 1, padding: "8px 12px" }}
                        type="text"
                        placeholder="Enter item name (e.g. 'My Custom Potion')"
                        value={newItemName}
                        onChange={(e) => { setNewItemName(e.target.value); setItemError(""); }}
                        onKeyDown={(e) => { if (e.key === "Enter") addCustomItem(); }}
                    />
                    <button
                        className="btn btn-primary"
                        onClick={addCustomItem}
                    >
                        Add Item
                    </button>
                </div>

                {itemError && (
                    <div style={{ color: "#ef4444", fontSize: "13px", marginBottom: "8px" }}>
                        {itemError}
                    </div>
                )}
                {itemSuccess && (
                    <div style={{ color: "#22c55e", fontSize: "13px", marginBottom: "8px" }}>
                        ✓ {itemSuccess}
                    </div>
                )}

                {customItems.length > 0 ? (
                    <div style={{ display: "grid", gap: "6px" }}>
                        {customItems.map((itemName) => (
                            <div
                                key={itemName}
                                style={{
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "space-between",
                                    padding: "8px 12px",
                                    border: "1px solid var(--border-color)",
                                    background: "rgba(255,255,255,0.02)",
                                }}
                            >
                                <span style={{ color: "var(--text-primary)", fontSize: "14px" }}>
                                    🔹 {itemName}
                                </span>
                                <button
                                    className="btn btn-secondary"
                                    style={{ padding: "4px 10px", fontSize: "12px", color: "#ef4444" }}
                                    onClick={() => removeCustomItem(itemName)}
                                >
                                    Remove
                                </button>
                            </div>
                        ))}
                    </div>
                ) : (
                    <div style={{ color: "var(--text-secondary)", fontSize: "13px", padding: "8px 0" }}>
                        No custom items added yet. Use the input above to add items that aren't in the default list.
                    </div>
                )}
            </div>
        </>
    );
}