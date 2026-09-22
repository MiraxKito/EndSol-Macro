import { useConfig, type AppConfig } from "../contexts/ConfigContext";
import { useState, useEffect } from "react";
import { BUILTIN_CALIBRATION_PRESETS } from "../data/calibrationPresets";

type CalibrationField = {
    key: string;
    label: string;
    isRegion?: boolean;
};

type CalibrationGroup = {
    id: string;
    label: string;
    color: string;
    fields: CalibrationField[];
};

type MouseActionRequirement = {
    feature: string;
    page: string;
    calibrations: string[];
};

const CALIBRATION_GROUPS: CalibrationGroup[] = [
    {
        id: "movements",
        label: "Movements Calibration",
        color: "#d4a843",
        fields: [
            { key: "collections_button", label: "Collection Menu" },
            { key: "exit_collections_button", label: "Exit Collection" },
            { key: "chat_hover_pos", label: "Roblox Chat Box" },
            { key: "chat_tab_ocr_pos", label: "Chat Tab OCR Region (either 'General' or 'Server Message')", isRegion: true },
            { key: "chat_close_button", label: "Roblox Chat Icon (to close chat box)" },
            { key: "chat_box_ocr_pos", label: "Chat Box OCR Region (to reads text inside Roblox chat)", isRegion: true },

        ]
    },
    {
        id: "quest",
        label: "Quest Claim Calibration",
        color: "#d4a843",
        fields: [
            { key: "quest_menu", label: "Quest Menu Button" },
            { key: "quest1_button", label: "Quest 1 Position" },
            { key: "quest2_button", label: "Quest 2 Position" },
            { key: "quest3_button", label: "Quest 3 Position" },
            { key: "claim_quest_button", label: "Claim Button" },
            { key: "quest_reroll_button", label: "Reroll Button" },
        ]
    },
    {
        id: "merchant",
        label: "Merchant Calibrations",
        color: "#7c5bf5",
        fields: [
            { key: "merchant_open_button", label: "Open Button" },
            { key: "jester_exchange_button", label: "Jester Exchange Button" },
            { key: "merchant_dialogue_box", label: "Dialogue Box" },
            { key: "purchase_amount_button", label: "Amount Input" },
            { key: "purchase_button", label: "Purchase Button" },
            { key: "autobuy_set_to_max_button", label: "Autobuy - Set to Max" },
            { key: "jester_exchange_set_to_max_button", label: "Jester Exchange - Set to Max" },
            { key: "first_item_merchant_slot_pos", label: "First Item Slot" },
            { key: "merchant_close_button", label: "Sell Menu Close Button" },
            { key: "merchant_name_ocr_pos", label: "Merchant Name OCR Region", isRegion: true },
            { key: "item_name_ocr_pos", label: "Item Name OCR Region", isRegion: true },
        ]
    },
    {
        id: "buff",
        label: "Enable Buff Calibration",
        color: "#ef4444",
        fields: [
            { key: "glitched_menu_button", label: "Menu Button" },
            { key: "glitched_settings_button", label: "Settings Button" },
            { key: "glitched_buff_enable_button", label: "Buff Toggle" },
        ]
    },
    {
        id: "automated",
        label: "Automated Actions Calibration",
        color: "#f59e0b",
        fields: [
            { key: "memory_match_grid_region", label: "Memory Match Grid Region (drag the 5×4 area)", isRegion: true },
            { key: "memory_match_start_button", label: "Memory Match Start Button" },
            { key: "memory_match_close_button", label: "Memory Match Close Button" },
            { key: "daily_event_check_button", label: "Daily Event Check Button" },
            { key: "daily_event_close_button", label: "Daily Event Pop-up Close Button" },
            { key: "daily_event_popup_region", label: "Daily Event Pop-up OCR Region", isRegion: true },
            { key: "quest_board_ocr_region", label: "Quest Board Quest Name OCR Region", isRegion: true },
            { key: "quest_board_accept_button", label: "Quest Board Accept Button" },
            { key: "quest_board_dismiss_button", label: "Quest Board Dismiss Button" },
            { key: "quest_board_claim_button", label: "Quest Board Claim Button" },
            { key: "quest_board_left_arrow", label: "Quest Board Left Arrow" },
            { key: "quest_board_right_arrow", label: "Quest Board Right Arrow" },
            { key: "quest_board_close_button", label: "Quest Board Close Button" },
        ]
    },
    {
        id: "aura",
        label: "Equip Aura Calibration",
        color: "#ec4899",
        fields: [
            { key: "aura_menu", label: "Aura Menu" },
            { key: "aura_search_bar", label: "Aura Search Bar Calibration (X,Y)" },
            { key: "first_aura_slot_pos", label: "First Aura Slot" },
            { key: "equip_aura_button", label: "Equip Aura Button" },
        ]
    },
    {
        id: "inventory",
        label: "Inventory Click Calibration",
        color: "#22c55e",
        fields: [
            { key: "inventory_menu", label: "Inventory Menu" },
            { key: "items_tab", label: "Items Tab" },
            { key: "search_bar", label: "Search Bar" },
            { key: "first_item_inventory_slot_pos", label: "First Inventory Item Slot" },
            { key: "amount_box", label: "Amount Box" },
            { key: "use_button", label: "Use Button" },
            { key: "inventory_close_button", label: "Inventory Close Button" },
            { key: "reconnect_start_button", label: "Join Button in Sol's RNG" },
            { key: "first_item_slot_ocr_pos", label: "First Item Slot OCR Region", isRegion: true },
        ]
    },
    {
        id: "potion",
        label: "Potion Crafting Calibration",
        color: "#0ea5e9",
        fields: [
            { key: "potion_items_tab", label: "Stella's Items Tab" },
            { key: "potion_search_bar", label: "Stella's Search Bar" },
            { key: "potion_first_potion_slot_pos", label: "First Potion Slot" },
            { key: "potion_recipe_button", label: "Open Recipe Button" },
            { key: "potion_auto_add_button", label: "Auto Add button" },
        ]
    },
    {
        id: "fishing",
        label: "Fishing Calibration",
        color: "#06b6d4",
        fields: [
            { key: "fishing_bar_region", label: "Fishing Bar Region", isRegion: true },
            { key: "fishing_detect_pixel", label: "Fish Indicator Pixel" },
            { key: "fishing_click_position", label: "Start fishing button" },
            { key: "fishing_midbar_sample_pos", label: "Mid Bar Color Sample" },
            { key: "fishing_close_button_pos", label: "Close Button" },
            { key: "fishing_flarg_dialogue_box", label: "Captain Flarg Dialogue Box" },
            { key: "fishing_shop_open_button", label: "Open Fishing Shop" },
            { key: "fishing_shop_sell_tab", label: "Fishing Shop Sell Tab" },
            { key: "fishing_shop_close_button", label: "Close Fishing Shop" },
            { key: "fishing_shop_first_fish", label: "First Fish In Shop" },
            { key: "fishing_shop_sell_all_button", label: "Sell All Button" },
            { key: "fishing_confirm_sell_all_button", label: "Confirm Sell All Button" },
        ]
    }
];

const CALIBRATION_MODE_BY_KEY = CALIBRATION_GROUPS.reduce((acc, group) => {
    group.fields.forEach((field) => {
        acc[field.key] = field.isRegion ? "region" : "point";
    });
    return acc;
}, {} as Record<string, "point" | "region">);

const MOUSE_ACTION_REQUIREMENTS: MouseActionRequirement[] = [
    { page: "Fishing", feature: "Fishing Mode Core Loop", calibrations: ["Fishing Calibration"] },
    { page: "Fishing", feature: "Fishing Auto Sell", calibrations: ["Fishing Calibration"] },
    { page: "Fishing", feature: "Fishing Auto Merchant Every X Fish", calibrations: ["Inventory Click Calibration", "Merchant Calibrations"] },
    { page: "Fishing", feature: "Fishing BR/SC Every X Fish", calibrations: ["Inventory Click Calibration"] },

    { page: "Merchant", feature: "Auto Merchant Teleporter", calibrations: ["Inventory Click Calibration", "Merchant Calibrations"] },
    { page: "Merchant", feature: "Auto Merchant in Limbo", calibrations: ["Inventory Click Calibration", "Merchant Calibrations"] },

    { page: "Misc", feature: "Biome Randomizer (BR)", calibrations: ["Inventory Click Calibration"] },
    { page: "Misc", feature: "Strange Controller (SC)", calibrations: ["Inventory Click Calibration"] },
    { page: "Auto Pop Buff", feature: "Auto Pop Buffs", calibrations: ["Inventory Click Calibration"] },
    { page: "Misc", feature: "Auto Reconnect (Join Button in Sol's RNG)", calibrations: ["Inventory Click Calibration"] },
    { page: "Misc", feature: "Periodical Aura Screenshot", calibrations: ["Equip Aura Calibration", "Inventory Click Calibration"] },
    { page: "Misc", feature: "Periodical Inventory Screenshot", calibrations: ["Inventory Click Calibration"] },
    { page: "Misc", feature: "Auto Claim Daily Quests", calibrations: ["Quest Claim Calibration"] },
    { page: "Misc", feature: "OCR Failsafe", calibrations: ["Inventory Click Calibration"] },

    { page: "Other Features", feature: "Enable Buff in Glitched/Dreamspace", calibrations: ["Enable Buff Calibration"] },
    { page: "Other Features", feature: "Teleport Back to Limbo", calibrations: ["Inventory Click Calibration"] },

    { page: "Movements", feature: "Auto Complete Basic Obby", calibrations: ["Movements Calibration"] },
    { page: "Movements", feature: "Use Float Aura", calibrations: ["Equip Aura Calibration", "Inventory Click Calibration"] },
    { page: "Movements", feature: "Easter Egg Collection", calibrations: ["Movements Calibration"] },
    { page: "Movements", feature: "Easter Egg OCR Special Detection", calibrations: ["Movements Calibration"] },

    { page: "Potion Craft", feature: "Potion Auto Craft / Switching", calibrations: ["Potion Crafting Calibration"] },

    { page: "Remote", feature: "Remote check_merchant command", calibrations: ["Inventory Click Calibration", "Merchant Calibrations"] },
    { page: "Remote", feature: "Remote use item command", calibrations: ["Inventory Click Calibration"] },
];

function normalizeCalibrationData(data: any, expectedMode: "point" | "region"): number[] | null {
    let value: unknown = data?.value;

    if (!Array.isArray(value)) {
        if (expectedMode === "region" && data && data.x !== undefined && data.y !== undefined && data.w !== undefined && data.h !== undefined) {
            value = [data.x, data.y, data.w, data.h];
        } else if (expectedMode === "point" && data && data.x !== undefined && data.y !== undefined) {
            value = [data.x, data.y];
        } else {
            return null;
        }
    }

    const arr = value as unknown[];
    const expectedLength = expectedMode === "region" ? 4 : 2;
    if (arr.length < expectedLength) return null;

    const normalized = arr.slice(0, expectedLength).map((v: any) => Math.round(Number(v)));
    if (normalized.some((n) => !Number.isFinite(n))) return null;

    if (expectedMode === "region" && (normalized[2] <= 0 || normalized[3] <= 0)) return null;
    return normalized;
}

// Helper component for coordinate inputs
function CoordInput({ label, value, onChange, isRegion = false, onCalibrate }: {
    label: string,
    value: number[],
    onChange: (val: number[]) => void,
    isRegion?: boolean,
    onCalibrate: () => void
}) {
    const vals = value || (isRegion ? [0, 0, 0, 0] : [0, 0]);

    const update = (idx: number, val: string) => {
        const num = parseInt(val) || 0;
        const next = [...vals];
        next[idx] = num;
        onChange(next);
    };

    return (
        <div className="coord-input-group" style={{ marginBottom: "12px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                    <label style={{ fontSize: "13px", color: "var(--text-secondary)", fontWeight: 500 }}>
                        {label}
                    </label>
                </div>
                <button
                    className="btn btn-sm"
                    style={{
                        fontSize: "10px",
                        padding: "2px 8px",
                        background: "var(--accent)",
                        color: "white",
                        opacity: 0.9,
                        border: "none",
                        borderRadius: "2px",
                        letterSpacing: "0.5px",
                        boxShadow: "0 2px 4px rgba(0,0,0,0.2)",
                        height: "20px",
                        display: "flex",
                        alignItems: "center",
                        cursor: "pointer"
                    }}
                    onClick={onCalibrate}
                >
                    {isRegion ? "SELECT REGION" : "SELECT POS"}
                </button>
            </div>
            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                {/* X */}
                <div className="coord-box">
                    <span className="coord-label">X</span>
                    <input className="coord-input" type="number" value={vals[0]} onChange={(e) => update(0, e.target.value)} />
                </div>
                {/* Y */}
                <div className="coord-box">
                    <span className="coord-label">Y</span>
                    <input className="coord-input" type="number" value={vals[1]} onChange={(e) => update(1, e.target.value)} />
                </div>
                {/* W/H if region */}
                {isRegion && (
                    <>
                        <div className="coord-box">
                            <span className="coord-label">W</span>
                            <input className="coord-input" type="number" value={vals[2]} onChange={(e) => update(2, e.target.value)} />
                        </div>
                        <div className="coord-box">
                            <span className="coord-label">H</span>
                            <input className="coord-input" type="number" value={vals[3]} onChange={(e) => update(3, e.target.value)} />
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}

export default function CalibrationPage() {
    const { config, setConfig, saveConfig, error } = useConfig();
    const [expandedSection, setExpandedSection] = useState<string | null>(null);
    const [showRequirements, setShowRequirements] = useState(false);
    const [presets, setPresets] = useState<any[]>([]);
    const [selectedRes, setSelectedRes] = useState("1920x1080");
    const [selectedScale, setSelectedScale] = useState("100%");
    const [selectedMode, setSelectedMode] = useState("Windowed");
    const [showPresetModal, setShowPresetModal] = useState(false);
    const [pendingPreset, setPendingPreset] = useState<any>(null);
    const [presetStatus, setPresetStatus] = useState<string>("");
    const [calibrationName, setCalibrationName] = useState("");
    const [savedCalibrations, setSavedCalibrations] = useState<string[]>([]);
    const [savedCalibrationProfiles, setSavedCalibrationProfiles] = useState<any[]>([]);
    const [calibrationStatus, setCalibrationStatus] = useState("");


    useEffect(() => {
        (window as any).onCalibrationResult = async (data: any) => {
            if (!data || typeof data.key !== "string") return;

            const expectedMode = CALIBRATION_MODE_BY_KEY[data.key] || "point";
            const value = normalizeCalibrationData(data, expectedMode);
            if (!value) {
                console.warn("Ignored invalid calibration payload:", data);
                return;
            }

            try {
                if (window.pywebview?.api?.get_config) {
                    const latestConfig = await window.pywebview.api.get_config() as AppConfig;
                    if (latestConfig && typeof latestConfig === "object") {
                        setConfig({ ...latestConfig, [data.key]: value });
                        return;
                    }
                }
            } catch (err) {
                console.warn("Failed to refresh config after calibration:", err);
            }

            if (config) {
                setConfig({ ...config, [data.key]: value });
            }
        };

        return () => {
            delete (window as any).onCalibrationResult;
        };
    }, [config, setConfig]);

    const refreshSavedCalibrations = async () => {
        const result = await (window.pywebview?.api as any)?.list_calibrations?.();
        if (result?.success) {
            setSavedCalibrations(result.files || []);
            setSavedCalibrationProfiles(result.profiles || []);
        }
    };

    useEffect(() => { void refreshSavedCalibrations(); }, []);

    const saveNamedCalibration = async () => {
        const name = calibrationName.trim();
        if (!name) { setCalibrationStatus("Enter a calibration name first."); return; }
        const result = await (window.pywebview?.api as any)?.save_calibration?.(name);
        setCalibrationStatus(result?.success ? `Saved to Calibrations as ${result.name}.` : (result?.error || "Could not save calibration."));
        if (result?.success) { setCalibrationName(result.name); await refreshSavedCalibrations(); }
    };

    const createCalibrationBackup = async () => {
        const result = await (window.pywebview?.api as any)?.backup_current_calibration?.();
        if (!result?.success) {
            throw new Error(result?.error || "Could not create a calibration backup.");
        }
    };

    const exportCalibrationFile = async () => {
        const result = await (window.pywebview?.api as any)?.export_calibration_file?.();
        const details = result?.validation_errors?.slice?.(0, 5)?.join("; ");
        setCalibrationStatus(result?.success ? `Calibration exported to ${result.path} (${result.count || 0} values).` : ((result?.error || "Export cancelled.") + (details ? ` ${details}` : "")));
    };

    const importCalibrationFile = async () => {
        const result = await (window.pywebview?.api as any)?.import_calibration_file?.();
        const details = result?.validation_errors?.slice?.(0, 5)?.join("; ");
        setCalibrationStatus(result?.success ? `Imported ${result.count} calibration values for ${result.resolution || "the selected profile"}. Backup: ${result.backup || "created"}.` : ((result?.error || "Import cancelled.") + (details ? ` ${details}` : "")));
        if (result?.success) {
            const latest = await window.pywebview?.api?.get_config?.();
            if (latest) setConfig(latest as AppConfig);
            await refreshSavedCalibrations();
        }
    };

    const loadNamedCalibration = async (name: string) => {
        if (!config) { setCalibrationStatus("Configuration is not loaded yet."); return; }
        try {
            await createCalibrationBackup();
            const result = await (window.pywebview?.api as any)?.load_calibration?.(name);
            if (!result?.success || !result.calibrations) {
                const details = result?.validation_errors?.slice?.(0, 5)?.join("; ");
                setCalibrationStatus((result?.error || "Could not load calibration.") + (details ? ` ${details}` : ""));
                return;
            }
            await saveConfig({ ...config, ...result.calibrations, calibration_preset_resolution: result.resolution || config.calibration_preset_resolution, calibration_preset_scale: result.scale || config.calibration_preset_scale, calibration_preset_mode: result.mode || config.calibration_preset_mode } as AppConfig);
            setCalibrationStatus(`Loaded ${name}. Previous values were backed up.`);
        } catch (err) {
            setCalibrationStatus(String(err));
        }
    };

    const startCalibration = async (key: string, isRegion: boolean) => {
        try {
            if (window.pywebview && window.pywebview.api) {
                await window.pywebview.api.create_calibration_window(key, isRegion ? "region" : "point");
            }
        } catch (e) {
            console.error("Failed to open calibration window", e);
            alert("Failed to open calibration tool: " + e);
        }
    };

    // CSS for compact inputs
    const styles = `
        .coord-box { display: flex; align-items: center; background: var(--bg-input); border: 1px solid var(--border); border-radius: 4px; overflow: hidden; }
        .coord-label { padding: 0 6px; font-size: 11px; color: var(--text-muted); background: rgba(255,255,255,0.05); border-right: 1px solid var(--border); height: 100%; display: flex; align-items: center; }
        .coord-input { border: none; background: transparent; color: var(--text-primary); padding: 4px; width: 45px; font-size: 12px; outline: none; text-align: center; }
        .coord-input::-webkit-inner-spin-button { -webkit-appearance: none; margin: 0; }
    `;


    useEffect(() => {
        let cancelled = false;
        setPresets([...BUILTIN_CALIBRATION_PRESETS] as any[]);
        fetch("https://raw.githubusercontent.com/MiraxKito/EndSol-Macro/main/assets/macro_calibs_preset.json")
            .then(res => res.ok ? res.json() : Promise.reject(new Error(String(res.status))))
            .then(data => {
                if (!cancelled && data && Array.isArray(data.presets)) {
                    const local = [...BUILTIN_CALIBRATION_PRESETS] as any[];
                    const merged = [...local, ...data.presets.filter((remote: any) => !local.some((item: any) => item.resolution === remote.resolution && item.scale === remote.scale && item.mode === remote.mode))];
                    setPresets(merged);
                }
            })
            .catch(err => console.warn("Remote calibration presets unavailable; using built-in templates", err));
        return () => { cancelled = true; };
    }, []);

    useEffect(() => {
        if (!config) return;
        setSelectedRes(String((config as any).calibration_preset_resolution || "1920x1080"));
        setSelectedScale(String((config as any).calibration_preset_scale || "100%"));
        setSelectedMode(String((config as any).calibration_preset_mode || "Fullscreen"));
    }, [config]);

    if (error) return <div style={{ padding: "20px", color: "red" }}>Error: {error}</div>;
    if (!config) return <div style={{ padding: "20px" }}>Loading...</div>;

    const updateConfig = (key: string, value: any) => {
        saveConfig({ ...config, [key]: value } as AppConfig);
    };

    const toggleSection = (section: string) => {
        setExpandedSection(expandedSection === section ? null : section);
    };


    const uniqueResolutions = Array.from(new Set(presets.map(p => p.resolution)));
    const availableScales = Array.from(new Set(presets.filter(p => p.resolution === selectedRes).map(p => p.scale)));
    const availableModes = Array.from(new Set(presets.filter(p => p.resolution === selectedRes && p.scale === selectedScale).map(p => p.mode)));

    const handleApplyClick = () => {
        const preset = presets.find(p => p.resolution === selectedRes && p.scale === selectedScale && p.mode === selectedMode);
        if (!preset || !preset.calibrations) {
            alert("Please select a valid preset (Resolution, Scale, and Mode)");
            return;
        }
        setPendingPreset(preset);
        setShowPresetModal(true);
    };


    const confirmPresetApply = async () => {
        if (pendingPreset && pendingPreset.calibrations) {
            const newConfig = { ...config, ...pendingPreset.calibrations, calibration_preset_resolution: pendingPreset.resolution, calibration_preset_scale: pendingPreset.scale, calibration_preset_mode: pendingPreset.mode };
            try {
                await createCalibrationBackup();
                await saveConfig(newConfig);
                setPresetStatus(`Preset applied: ${pendingPreset.resolution} (${pendingPreset.scale} ${pendingPreset.mode}); previous values backed up.`);
                setTimeout(() => setPresetStatus(""), 5000);
            } catch (err) {
                setPresetStatus("Failed to apply preset: " + String(err));
                setTimeout(() => setPresetStatus(""), 5000);
            }
        }
        setShowPresetModal(false);
        setPendingPreset(null);
    };

    return (
        <>
            <style>{styles}</style>

            {/* Preset Confirm Modal */}
            {showPresetModal && pendingPreset && (
                <div className="biome-confirm-overlay" onClick={() => setShowPresetModal(false)}>
                    <div className="biome-confirm-modal" onClick={e => e.stopPropagation()} style={{ textAlign: "left" }}>
                        <h3 className="biome-confirm-title" style={{ textAlign: "center" }}>Overwrite Calibrations?</h3>
                        <p style={{ color: "var(--text-secondary)", marginBottom: "20px", lineHeight: "1.6", textAlign: "center", fontSize: "14px" }}>
                            This will overwrite your current calibrations with the
                            <br />
                            <strong style={{ color: "var(--text-primary)" }}>{pendingPreset.resolution} ({pendingPreset.scale} {pendingPreset.mode})</strong> preset.
                            <br /><br />
                            <span style={{ color: "var(--text-muted)", fontSize: "0.85em" }}>This action cannot be undone.</span>
                        </p>
                        <div className="biome-confirm-buttons">
                            <button className="biome-confirm-btn confirm" onClick={confirmPresetApply}>Yes, Overwrite</button>
                            <button className="biome-confirm-btn cancel" onClick={() => setShowPresetModal(false)}>Cancel</button>
                        </div>
                    </div>
                </div>
            )}

            <div className="page-header">
                <h2>Macro Calibrations</h2>
                <p>View and manually edit calibration coordinates</p>
            </div>

            <div className="info-banner" style={{ marginBottom: "16px" }}>
                <div>ℹ️ Use "Select Pos" or "Select Region" to launch the calibration overlay :)</div>
                <div style={{ marginTop: "6px" }}>
                    If you have troubles understanding refer to this tutorial:{" "}
                    <a href="https://www.youtube.com/watch?v=dZzQytUMlCE" target="_blank" rel="noreferrer">
                        https://www.youtube.com/watch?v=dZzQytUMlCE
                    </a>
                </div>
            </div>

            {/* Mouse Action Requirements Section*/}
            <div className="card" style={{ padding: "0", marginBottom: "16px" }}>
                <div
                    className="card-header"
                    style={{
                        padding: "16px",
                        cursor: "pointer",
                        borderBottom: showRequirements ? "1px solid var(--border-color)" : "none"
                    }}
                    onClick={() => setShowRequirements(!showRequirements)}
                >
                    <div className="card-icon">🧭</div>
                    <div style={{ flex: 1 }}>
                        <h3>Mouse Action Calibration Requirements</h3>
                        <p>Feature-to-calibration tracking for actions that use mouse inputs</p>
                    </div>
                    <div>{showRequirements ? "▲" : "▼"}</div>
                </div>

                {showRequirements && (
                    <div style={{ padding: "16px" }}>
                        <div className="form-hint" style={{ marginBottom: "8px" }}>
                            Note: Features using OCR failsafe also require calibrating First Item Slot OCR Region under Inventory Click Calibration.
                        </div>
                        <div style={{ display: "grid", gap: "8px" }}>
                            {MOUSE_ACTION_REQUIREMENTS.map((item) => (
                                <div
                                    key={item.feature}
                                    style={{
                                        display: "grid",
                                        gridTemplateColumns: "120px 1fr 1fr",
                                        gap: "10px",
                                        alignItems: "center",
                                        padding: "8px 10px",
                                        border: "1px solid var(--border-color)",
                                        borderRadius: "6px",
                                        background: "rgba(255,255,255,0.02)"
                                    }}
                                >
                                    <div style={{ fontSize: "12px", color: "var(--text-muted)" }}>{item.page}</div>
                                    <div style={{ fontSize: "13px", color: "var(--text-primary)" }}>{item.feature}</div>
                                    <div style={{ fontSize: "12px", color: "var(--text-secondary)" }}>
                                        {item.calibrations.join(" + ")}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </div>

            <div className="card" style={{ marginBottom: "16px" }}>
                <div className="card-header"><div className="card-icon">💾</div><div><h3>Custom Calibrations</h3><p>Export the current coordinates or import a named profile. A backup is created before every import or preset replacement.</p></div></div>
                <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                    <button className="btn btn-accent" onClick={exportCalibrationFile}>Export calibration file</button>
                    <button className="btn" onClick={importCalibrationFile}>Import calibration file</button>
                    <input className="form-input" value={calibrationName} onChange={e => setCalibrationName(e.target.value)} placeholder="Local profile name" style={{ flex: 1, minWidth: "180px" }} />
                    <button className="btn" onClick={saveNamedCalibration}>Save local profile</button>
                </div>
                {savedCalibrations.length > 0 && <div style={{ marginTop: "10px" }}><div className="form-hint">Local profiles (copied JSON files are detected automatically):</div><div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px" }}>{savedCalibrations.filter(name => !name.startsWith("_backup_")).map(name => { const profile = savedCalibrationProfiles.find(item => item.name === name); const target = [profile?.resolution, profile?.scale, profile?.mode].filter(Boolean).join(" · "); const label = target ? `${name} — ${target}` : name; return <button className="btn" key={name} disabled={profile ? profile.valid === false : false} title={profile?.error || ""} onClick={() => void loadNamedCalibration(name)}>{label}{profile?.valid === false ? " (invalid)" : ""}</button>; })}</div></div>}
                {calibrationStatus && <div className="form-hint" style={{ marginTop: "8px" }}>{calibrationStatus}</div>}
            </div>

            {/* Macro Calibrations Preset */}
            <div className="card" style={{ marginBottom: "16px" }}>
                <div className="card-header">
                    <div className="card-icon">⚡</div>
                    <div style={{ flex: 1 }}>
                        <h3>Macro Calibrations Preset</h3>
                        <p>Reference presets only. For Windowed 1920×1080, verify the Roblox client rectangle and use Custom Calibrations for exact values.</p>
                    </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr auto", gap: "10px", alignItems: "end", marginTop: "12px" }}>
                    <div>
                        <label style={{ display: "block", fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px", letterSpacing: "0.5px" }}>RESOLUTION</label>
                        <select
                            className="form-input"
                            style={{ width: "100%", cursor: "pointer" }}
                            value={selectedRes}
                            onChange={(e) => {
                                setSelectedRes(e.target.value);
                                setSelectedScale("");
                                setSelectedMode("");
                            }}
                        >
                            <option value="">Select Resolution</option>
                            {uniqueResolutions.map((res: any) => (
                                <option key={res} value={res}>{res}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label style={{ display: "block", fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px", letterSpacing: "0.5px" }}>DISPLAY SCALE</label>
                        <select
                            className="form-input"
                            style={{ width: "100%", cursor: selectedRes ? "pointer" : "not-allowed", opacity: selectedRes ? 1 : 0.5 }}
                            value={selectedScale}
                            onChange={(e) => {
                                setSelectedScale(e.target.value);
                                setSelectedMode("");
                            }}
                            disabled={!selectedRes}
                        >
                            <option value="">Select Scale</option>
                            {availableScales.map((scale: any) => (
                                <option key={scale} value={scale}>{scale}</option>
                            ))}
                        </select>
                    </div>

                    <div>
                        <label style={{ display: "block", fontSize: "11px", color: "var(--text-muted)", marginBottom: "4px", letterSpacing: "0.5px" }}>WINDOW MODE</label>
                        <select
                            className="form-input"
                            style={{ width: "100%", cursor: selectedScale ? "pointer" : "not-allowed", opacity: selectedScale ? 1 : 0.5 }}
                            value={selectedMode}
                            onChange={(e) => setSelectedMode(e.target.value)}
                            disabled={!selectedScale}
                        >
                            <option value="">Select Mode</option>
                            {availableModes.map((mode: any) => (
                                <option key={mode} value={mode}>{mode}</option>
                            ))}
                        </select>
                    </div>

                    <button
                        className="btn btn-accent"
                        onClick={handleApplyClick}
                        disabled={!selectedRes || !selectedScale || !selectedMode}
                        style={{ height: "36px", whiteSpace: "nowrap" }}
                    >
                        Apply Preset
                    </button>
                </div>
                {presets.length === 0 && (
                    <div style={{ color: "var(--text-muted)", fontSize: "12px", marginTop: "8px" }}>
                        Presets not found on github or failed to fetch.
                    </div>
                )}
                {presetStatus && (
                    <div style={{
                        marginTop: "10px",
                        padding: "8px 14px",
                        borderRadius: "6px",
                        fontSize: "13px",
                        fontWeight: 500,
                        background: presetStatus.startsWith("✅") ? "rgba(34,197,94,0.15)" : "rgba(239,68,68,0.15)",
                        color: presetStatus.startsWith("✅") ? "#22c55e" : "#ef4444",
                        border: `1px solid ${presetStatus.startsWith("✅") ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
                    }}>
                        {presetStatus}
                    </div>
                )}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                {CALIBRATION_GROUPS.map((group) => (
                    <div key={group.id} className="card" style={{ padding: "0" }}>
                        <div
                            className="card-header"
                            style={{
                                padding: "16px",
                                cursor: "pointer",
                                borderBottom: expandedSection === group.id ? "1px solid var(--border-color)" : "none"
                            }}
                            onClick={() => toggleSection(group.id)}
                        >
                            <div className="card-icon" style={{ borderColor: group.color }}>🎯</div>
                            <div style={{ flex: 1 }}>
                                <h3 style={{ color: group.color }}>{group.label}</h3>
                                <p>Click to view/edit coordinates</p>
                            </div>
                            <div>{expandedSection === group.id ? "▲" : "▼"}</div>
                        </div>

                        {expandedSection === group.id && (
                            <div style={{ padding: "16px", background: "rgba(0,0,0,0.2)" }}>
                                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                                    {group.fields.map((field) => (
                                        <CoordInput
                                            key={field.key}
                                            label={field.label}
                                            value={config[field.key]}
                                            onChange={(val) => updateConfig(field.key, val)}
                                            isRegion={field.isRegion}
                                            onCalibrate={() => startCalibration(field.key, field.isRegion || false)}
                                        />
                                    ))}
                                </div>
                            </div>
                        )}
                    </div>
                ))}
            </div>
        </>
    );
}