import { useState, useEffect, useRef } from "react";
import ToggleSwitch from "../components/ToggleSwitch";

export default function PotionCraftPage() {
    // State
    const [enableCrafting, setEnableCrafting] = useState(false);
    const [selectedPotion, setSelectedPotion] = useState("");
    const [potionFiles, setPotionFiles] = useState<string[]>([]);

    // Switching Logic
    const [enableSwitching, setEnableSwitching] = useState(false);
    const [switchInterval, setSwitchInterval] = useState(60);
    const [potion1, setPotion1] = useState("");
    const [potion2, setPotion2] = useState("");
    const [potion3, setPotion3] = useState("");

    // Simple mode / occupancy / Auto-state management
    const [craftMode, setCraftMode] = useState("recording");
    const [potionName, setPotionName] = useState("");
    const [occupancy, setOccupancy] = useState("full");
    const [partialInterval, setPartialInterval] = useState(60);
    const [partialDuration, setPartialDuration] = useState(10);
    const [autoTarget, setAutoTarget] = useState("on");
    const [autoStateInfo, setAutoStateInfo] = useState<string>("");
    const saveQueueRef = useRef<Promise<void>>(Promise.resolve());
    const configSnapshotRef = useRef<any>(null);

    useEffect(() => {
        refreshFiles();
        loadConfig();
    }, []);

    const refreshFiles = async () => {
        try {
            if (window.pywebview?.api?.list_potion_files) {
                const files = await window.pywebview.api.list_potion_files() as string[];
                setPotionFiles(files);
            }
        } catch (e) {
            console.error("Failed to list files:", e);
        }
    };

    const loadConfig = async () => {
        try {
            if (window.pywebview && window.pywebview.api) {
                const config: any = await window.pywebview.api.get_config();
                if (config) {
                    configSnapshotRef.current = config;
                    if (typeof config.enable_potion_crafting === 'boolean') setEnableCrafting(config.enable_potion_crafting);
                    setSelectedPotion(config.selected_potion_file ?? "");
                    if (typeof config.enable_potion_switching === 'boolean') setEnableSwitching(config.enable_potion_switching);
                    setSwitchInterval(Number(config.potion_switch_interval ?? 60));
                    setPotion1(config.potion_file_1 ?? "");
                    setPotion2(config.potion_file_2 ?? "");
                    setPotion3(config.potion_file_3 ?? "");
                    setCraftMode(config.potion_craft_mode === "simple" ? "simple" : "recording");
                    setPotionName(config.potion_simple_name ?? "");
                    setOccupancy(config.potion_occupancy === "partial" ? "partial" : "full");
                    setPartialInterval(Number(config.potion_partial_interval_min ?? 60));
                    setPartialDuration(Number(config.potion_partial_duration_min ?? 10));
                    setAutoTarget(config.potion_auto_target_state === "on_craft" ? "on_craft" : "on");
                }
            }
        } catch (e) {
            console.error("Failed to load config:", e);
        }
    };

    const saveConfig = (key: string, value: any) => {
        saveQueueRef.current = saveQueueRef.current
            .then(async () => {
                if (window.pywebview && window.pywebview.api) {
                    const baseConfig: any = configSnapshotRef.current ?? await window.pywebview.api.get_config();
                    const newConfig = { ...(baseConfig || {}), [key]: value };
                    configSnapshotRef.current = newConfig;
                    await window.pywebview.api.save_config(newConfig);
                }
            })
            .catch((e) => {
                console.error("Failed to save config:", e);
            });
    };

    // Generic handler to update state and save config
    const handleNumberChange = (val: string) => {
        const num = parseInt(val) || 0;
        setSwitchInterval(num);
        saveConfig("potion_switch_interval", num);
    };

    const openRecorder = async () => {
        try {
            if (window.pywebview?.api) {
                await window.pywebview.api.open_recorder_window_potion();
            }
        } catch (e) {
            console.error(e);
        }
    };

    // Helpers: Auto-state live check
    const checkAutoState = async () => {
        try {
            if (!window.pywebview?.api?.check_potion_auto_state) return;
            const res: any = await window.pywebview.api.check_potion_auto_state();
            if (res?.ok) {
                const st = res.state ?? "UNKNOWN";
                setAutoStateInfo(`Current Auto state: ${st}${res.color ? ` (RGB ${res.color.join(", ")})` : ""}`);
            } else {
                setAutoStateInfo(`Check failed: ${res?.error ?? "unknown error"}`);
            }
        } catch (e) {
            console.error(e);
        }
    };

    // UI Helpers
    const PotionDropdown = ({ value, onChange, placeholder }: any) => (
        <div style={{ position: "relative", width: "100%" }}>
            <select
                className="form-input"
                style={{ width: "100%" }}
                value={value}
                onChange={(e) => onChange(e.target.value)}
            >
                <option value="">{placeholder}</option>
                {potionFiles.map(f => (
                    <option key={f} value={f}>{f}</option>
                ))}
            </select>
        </div>
    );

    return (
        <div className="animate-fade-in">
            <div className="page-header">
                <h2>Potion Crafting</h2>
                <p>Record and replay Stella's potion crafting sequences</p>
            </div>

            {/* Corner Borders container style similar to Obby */}
            <div style={{ position: "relative", border: "1px solid var(--border-color)", padding: "20px", marginBottom: "20px", background: "var(--card-bg)" }}>
                <div className="corner-bracket tl"></div>
                <div className="corner-bracket tr"></div>
                <div className="corner-bracket bl"></div>
                <div className="corner-bracket br"></div>

                <div className="card-header">
                    <div className="card-icon">🧪</div>
                    <div>
                        <h3>Auto Craft</h3>
                        <p>Automatically craft potions using recorded recipes</p>
                    </div>
                </div>

                <div style={{ marginBottom: "15px" }}>
                    <ToggleSwitch
                        label="Enable Auto Craft"
                        description="Run selected recipe on a loop when macro is running (THIS WILL CANCEL ALL OTHERS MACRO ACTIONS FOR POTION CRAFTING)"
                        checked={enableCrafting}
                        onChange={(v) => {
                            if (v && craftMode === "simple" && !potionName.trim()) {
                                alert("No potion name entered!\n\nEnter the potion name to craft before enabling Auto Craft in Simple mode.");
                                return;
                            }
                            if (v && craftMode === "recording" && !selectedPotion) {
                                alert("No potion recipe selected!\n\nPlease select a potion recipe file before enabling Auto Craft.");
                                return;
                            }
                            setEnableCrafting(v);
                            saveConfig("enable_potion_crafting", v);
                        }}
                    />
                </div>

                <ToggleSwitch
                    label="Simple crafting mode"
                    description="ON: craft with the calibrated Add Everything + Craft buttons — they are identical for every potion, so only the potion name (for the crafting search bar) is needed. OFF: replay a recorded recipe file."
                    checked={craftMode === "simple"}
                    onChange={(v) => {
                        const mode = v ? "simple" : "recording";
                        setCraftMode(mode);
                        saveConfig("potion_craft_mode", mode);
                    }}
                />

                {craftMode === "simple" ? (
                    <div className="form-group" style={{ marginTop: "12px" }}>
                        <label className="form-label">Potion name (searched in the crafting list)</label>
                        <input
                            className="form-input"
                            value={potionName}
                            placeholder="e.g. Lucky Potion"
                            onChange={(e) => { setPotionName(e.target.value); saveConfig("potion_simple_name", e.target.value); }}
                        />
                        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 6 }}>
                            The macro types this name into the crafting search bar and selects the potion — no recipe file required.
                        </p>
                    </div>
                ) : (
                    <div className="form-group" style={{ marginTop: "12px" }}>
                        <label className="form-label">Selected Recipe</label>
                        <PotionDropdown
                            value={selectedPotion}
                            onChange={(v: string) => { setSelectedPotion(v); saveConfig("selected_potion_file", v); }}
                            placeholder="— Select a recipe file —"
                        />
                    </div>
                )}

                <div className="form-group">
                    <label className="form-label">Crafting occupancy</label>
                    <select
                        className="form-input"
                        value={occupancy}
                        onChange={(e) => { setOccupancy(e.target.value); saveConfig("potion_occupancy", e.target.value); }}
                    >
                        <option value="full">Full — craft non-stop while the macro runs</option>
                        <option value="partial">Scheduled — walk to the station and craft on a timer</option>
                    </select>
                </div>

                {occupancy === "partial" && (
                    <div style={{ display: "flex", gap: "12px" }}>
                        <div className="form-group" style={{ flex: 1 }}>
                            <label className="form-label">Session interval (minutes)</label>
                            <input
                                type="number"
                                className="form-input"
                                value={partialInterval}
                                onChange={(e) => { const n = parseInt(e.target.value) || 60; setPartialInterval(n); saveConfig("potion_partial_interval_min", n); }}
                            />
                        </div>
                        <div className="form-group" style={{ flex: 1 }}>
                            <label className="form-label">Crafting time per session (minutes)</label>
                            <input
                                type="number"
                                className="form-input"
                                value={partialDuration}
                                onChange={(e) => { const n = parseInt(e.target.value) || 10; setPartialDuration(n); saveConfig("potion_partial_duration_min", n); }}
                            />
                        </div>
                    </div>
                )}
                {occupancy === "partial" && (
                    <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: -6 }}>
                        Requires a walk path to the station: paths/potion_station.json (to Stella) or a custom path assigned to
                        "Potion Crafting Station" in Custom Paths. Without a path file the session is skipped. After crafting
                        the character is reset (back to spawn).
                    </p>
                )}

                {craftMode === "recording" && (
                <div style={{ display: "flex", gap: "8px", alignItems: "center", marginBottom: "12px" }}>
                    <button className="btn btn-accent" onClick={openRecorder} style={{ fontSize: "12px", padding: "6px 12px" }}>
                        ⏺ Open Potion Recorder
                    </button>
                    <button className="btn" onClick={refreshFiles} style={{ fontSize: "12px", padding: "6px 12px", backgroundColor: "#374151", color: "white", border: "1px solid var(--border-color)" }}>
                        🔄 Refresh Files
                    </button>
                </div>
                )}

                {craftMode === "simple" && (
                    <div style={{ border: "1px solid var(--border-color)", borderRadius: 6, padding: "12px", marginBottom: "12px" }}>
                        <label className="form-label">Auto button management (cycle: auto-add → auto-add + auto craft → off)</label>
                        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 4 }}>
                            The macro reads the Auto button state from its calibrated region (green = auto-add,
                            dark turquoise = auto-add + auto craft, dark = off) and only clicks the missing steps
                            towards the target state — it never clicks blindly, so your Auto setting cannot be
                            toggled off by accident. Auto works on ONE selected potion at a time; the macro
                            re-checks it after every potion selection.
                        </p>
                        <select
                            className="form-input"
                            style={{ marginTop: 8 }}
                            value={autoTarget}
                            onChange={(e) => { setAutoTarget(e.target.value); saveConfig("potion_auto_target_state", e.target.value); }}
                        >
                            <option value="on">Target: auto-add only (ON, green)</option>
                            <option value="on_craft">Target: auto-add + AUTO CRAFT (dark turquoise)</option>
                        </select>
                        <div style={{ display: "flex", gap: "8px", marginTop: 10, flexWrap: "wrap" }}>
                            <button className="btn" onClick={checkAutoState} style={{ fontSize: "12px", padding: "6px 10px", backgroundColor: "#374151", color: "white", border: "1px solid var(--border-color)" }}>
                                🔍 Check current state
                            </button>
                        </div>
                        {autoStateInfo && (
                            <p style={{ fontSize: "0.8rem", color: "var(--text-bright)", marginTop: 8 }}>{autoStateInfo}</p>
                        )}
                        <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 8 }}>
                            State detection works out of the box: the macro reads the button colors from the calibrated
                            region and matches them against the standard crafting Auto button colors (green = auto-add,
                            dark turquoise = auto-add + auto craft, dark = off). The button region itself is calibrated on
                            the Calibration page → Potion Crafting → Auto Button State Region.
                        </p>
                    </div>
                )}

            </div>

            {/* Switching Section */}
            <div style={{ position: "relative", border: "1px solid var(--border-color)", padding: "20px", background: "var(--card-bg)" }}>
                <div className="corner-bracket tl"></div>
                <div className="corner-bracket tr"></div>
                <div className="corner-bracket bl"></div>
                <div className="corner-bracket br"></div>

                <div className="card-header">
                    <div className="card-icon">🔄</div>
                    <div>
                        <h3>Potion Switching</h3>
                        <p>Automatically switch between different potion recipes</p>
                    </div>
                </div>

                <ToggleSwitch
                    label="Enable potion switching"
                    description="Switch to next potion after interval"
                    checked={enableSwitching}
                    onChange={(v) => { setEnableSwitching(v); saveConfig("enable_potion_switching", v); }}
                />

                {craftMode === "simple" && enableSwitching && (
                    <p style={{ fontSize: "0.8rem", color: "var(--text-muted)", marginTop: 6 }}>
                        Simple crafting mode is ON: enter potion NAMES below — the macro searches each one
                        in the crafting list and crafts it with Add Everything + Craft, then moves to the next name.
                    </p>
                )}

                {enableSwitching && <>
                <div className="form-group" style={{ marginTop: "15px" }}>
                    <label className="form-label">Switch interval (seconds)</label>
                    <input
                        type="number"
                        className="form-input"
                        value={switchInterval}
                        onChange={(e) => handleNumberChange(e.target.value)}
                    />
                </div>

                <div className="form-group">
                    <label className="form-label">{craftMode === "simple" ? ("Potion name #1") : ("Select potion #1")}</label>
                    {craftMode === "simple" ? (
                        <input
                            className="form-input"
                            value={potion1}
                            placeholder="e.g. Lucky Potion"
                            onChange={(e) => { setPotion1(e.target.value); saveConfig("potion_file_1", e.target.value); }}
                        />
                    ) : (
                        <PotionDropdown
                            value={potion1}
                            onChange={(v: string) => { setPotion1(v); saveConfig("potion_file_1", v); }}
                            placeholder="— None —"
                        />
                    )}
                </div>

                <div className="form-group">
                    <label className="form-label">{craftMode === "simple" ? ("Potion name #2") : ("Select potion #2")}</label>
                    {craftMode === "simple" ? (
                        <input
                            className="form-input"
                            value={potion2}
                            placeholder="e.g. Lucky Potion"
                            onChange={(e) => { setPotion2(e.target.value); saveConfig("potion_file_2", e.target.value); }}
                        />
                    ) : (
                        <PotionDropdown
                            value={potion2}
                            onChange={(v: string) => { setPotion2(v); saveConfig("potion_file_2", v); }}
                            placeholder="— None —"
                        />
                    )}
                </div>

                <div className="form-group">
                    <label className="form-label">{craftMode === "simple" ? ("Potion name #3") : ("Select potion #3")}</label>
                    {craftMode === "simple" ? (
                        <input
                            className="form-input"
                            value={potion3}
                            placeholder="e.g. Lucky Potion"
                            onChange={(e) => { setPotion3(e.target.value); saveConfig("potion_file_3", e.target.value); }}
                        />
                    ) : (
                        <PotionDropdown
                            value={potion3}
                            onChange={(v: string) => { setPotion3(v); saveConfig("potion_file_3", v); }}
                            placeholder="— None —"
                        />
                    )}
                </div>
                </>}

            </div>
        </div>
    );
}