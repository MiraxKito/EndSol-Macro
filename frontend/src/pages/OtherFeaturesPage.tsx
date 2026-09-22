import { useState } from "react";
import { useConfig } from "../contexts/ConfigContext";
import ToggleSwitch from "../components/ToggleSwitch";
import { useT, usePanelLang, type Lang } from "../i18n";

export default function OtherFeaturesPage() {
    const { config, saveConfig, error } = useConfig();
    const t = useT();
    const panelLang = usePanelLang();
    const [pendingLang, setPendingLang] = useState<Lang | null>(null);

    if (error) return <div style={{ padding: "20px", color: "red" }}>Error: {error}</div>;
    if (!config) return <div style={{ padding: "20px" }}>Loading...</div>;

    const updateConfig = (key: string, value: any) => {
        saveConfig({ ...config, [key]: value });
    };

    // Language switch. Custom tab labels (panel customization) take priority
    // over translated defaults, so they must be reset on language change -
    // with the user's confirmation when any custom label exists.
    const changeLanguage = (lang: Lang) => {
        if (lang === panelLang) return;
        const customTheme: any = (config as any).custom_theme_data || {};
        const labels = customTheme.custom_labels || {};
        const hasCustom = Object.values(labels).some(v => v && String(v).trim());
        if (hasCustom) {
            setPendingLang(lang);
        } else {
            updateConfig("panel_language", lang);
        }
    };

    const confirmLanguageChange = () => {
        if (!pendingLang) return;
        const customTheme: any = (config as any).custom_theme_data || {};
        saveConfig({
            ...config,
            panel_language: pendingLang,
            custom_theme_data: { ...customTheme, custom_labels: {} },
        });
        setPendingLang(null);
    };

    return (
        <>
            <div className="page-header">
                <h2>{t("Other Features")}</h2>
                <p>{t("Additional macro capabilities and experimental options")}</p>
            </div>

            <div className="card">
                <div className="card-header">
                    <div className="card-icon">⚡</div>
                    <div>
                        <h3>Rare Biome Actions</h3>
                        <p>Actions to take when a rare biome is detected</p>
                    </div>
                </div>

                <ToggleSwitch
                    label="Enable buff when Glitched/Dreamspace"
                    description="ONLY use this feature when you have your buffs DISABLED while hunting for Glitched/Dreamspace"
                    checked={config.enable_buff_glitched || false}
                    onChange={(val) => updateConfig("enable_buff_glitched", val)}
                />

                <ToggleSwitch
                    label="Reset character when there's a rare biome"
                    description="Reset character to Sol's Main Island during GLITCHED/DREAMSPACE/CYBERSPACE"
                    checked={config.reset_on_rare || false}
                    onChange={(val) => updateConfig("reset_on_rare", val)}
                />

                <ToggleSwitch
                    label="Teleport back to Limbo when rare biome ends"
                    description="Return to limbo automatically when rare biome ended"
                    checked={config.teleport_back_to_limbo || false}
                    onChange={(val) => updateConfig("teleport_back_to_limbo", val)}
                />
            </div>

            <div className="card">
                <div className="card-header">
                    <div className="card-icon">👥</div>
                    <div>
                        <h3>Player Logger</h3>
                        <p>Track players joining and leaving the current server</p>
                    </div>
                </div>

                <ToggleSwitch
                    label="Player Logger"
                    description="Reads Roblox logs, records join/leave events and sends player embeds to the configured Discord webhook"
                    checked={config.player_logger !== false}
                    onChange={(val) => updateConfig("player_logger", val)}
                    disabled={true}
                />
                <p className="form-hint" style={{ padding: "0 20px 14px", color: "#f87171" }}>
                    ⚠️ Deprecated: this feature relies on legacy Roblox log entries that no longer exist in the current game. It cannot be improved anymore and is kept non-interactive for compatibility.
                </p>
            </div>

            <div className="card">
                <div className="card-header">
                    <div className="card-icon">🛠️</div>
                    <div>
                        <h3>System Settings</h3>
                        <p>Application-wide preferences</p>
                    </div>
                </div>

                <div className="setting-row" style={{ padding: '15px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <div style={{ fontWeight: 600, color: 'var(--text-bright)' }}>{t("Language")}</div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>{t("Panel interface language")}</div>
                    </div>
                    <select
                        className="form-input"
                        value={panelLang}
                        onChange={(e) => changeLanguage(e.target.value as Lang)}
                        style={{ padding: '8px 12px', cursor: 'pointer', backgroundColor: 'var(--bg-card)', color: 'var(--text)', border: '1px solid var(--border)', width: 'auto' }}
                    >
                        <option value="en">{t("English")}</option>
                        <option value="ru">{t("Russian")}</option>
                    </select>
                </div>

                <div className="setting-row" style={{ padding: '15px 20px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                        <div style={{ fontWeight: 600, color: 'var(--text-bright)' }}>Open AppData Folder</div>
                        <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Opens the folder where logs, config, and macro data are stored</div>
                    </div>
                    <button 
                        className="btn primary" 
                        onClick={() => window.pywebview?.api?.open_appdata()}
                        style={{ padding: '8px 16px', borderRadius: '4px', cursor: 'pointer', backgroundColor: 'var(--primary)', color: 'white', border: 'none', fontWeight: 600 }}
                    >
                        Open Folder
                    </button>
                </div>

                <ToggleSwitch
                    label="GLITCHED visual effect on macro UI when GLITCHED biome is found (to look cool ofc)"
                    description={<span style={{ color: "red", fontWeight: "bold" }}>ONLY USE THIS IF YOU ARE NON PHOTOSENSITIVE</span>}
                    checked={config.enable_glitch_effect || false}
                    onChange={(val) => updateConfig("enable_glitch_effect", val)}
                />

                <ToggleSwitch
                    label="Anti-AFK"
                    description="Prevents Roblox disconnection even when Roblox isn't focused"
                    checked={config.anti_afk || false}
                    onChange={(val) => updateConfig("anti_afk", val)}
                />

                <div className="setting-row" style={{ padding: '0 20px 20px 20px', display: 'flex', alignItems: 'center', gap: '15px' }}>
                    <span style={{ fontSize: '0.9rem', color: 'var(--text-muted)' }}>Usage Duration (minutes):</span>
                    <input 
                        type="number" 
                        className="form-input" 
                        style={{ width: '80px', textAlign: 'center' }}
                        value={config.anti_afk_interval || "5"}
                        min="1"
                        max="20"
                        onChange={(e) => updateConfig("anti_afk_interval", e.target.value)}
                    />
                </div>

                <ToggleSwitch
                    label="Auto Update (Startup)"
                    description="⚠️ Disabled — auto-update points to original EndSol repo. Do not enable until repo is changed."
                    checked={false}
                    onChange={() => {}}
                    disabled={true}
                />

                <ToggleSwitch
                    label="Auto Update Biome/Aura Data"
                    description="Automatically fetch latest biome/aura data from remote sources on startup"
                    checked={config.auto_update_biome_aura_data !== false}
                    onChange={(val) => updateConfig("auto_update_biome_aura_data", val)}
                />

                <ToggleSwitch
                    label="Auto-Start Macro After Inactivity"
                    description={`Automatically start only the safe Idle Mode cycle after ${config.auto_start_idle_minutes || 15} min of user inactivity. Requires the EndSol app and Roblox to already be running; it does not rejoin or start Roblox.`}
                    checked={config.auto_start_on_idle || false}
                    onChange={async (val) => {
                        await updateConfig("auto_start_on_idle", val);
                        try {
                            if (window.pywebview?.api?.toggle_idle_monitor) {
                                await window.pywebview.api.toggle_idle_monitor(val);
                            }
                        } catch (e) {
                            console.error("Failed to toggle idle monitor:", e);
                        }
                    }}
                />

                {config.auto_start_on_idle && (
                    <div style={{ display: "flex", alignItems: "center", gap: "12px", padding: "8px 16px" }}>
                        <label style={{ color: "var(--text-secondary)", fontSize: "13px", whiteSpace: "nowrap" }}>
                            Idle timeout (minutes):
                        </label>
                        <input
                            className="form-input"
                            type="number"
                            min="5"
                            max="60"
                            style={{ width: "80px", padding: "6px 10px" }}
                            value={config.auto_start_idle_minutes || 15}
                            onChange={(e) => updateConfig("auto_start_idle_minutes", parseInt(e.target.value) || 15)}
                        />
                    </div>
                )}

                <ToggleSwitch
                    label="Enable Idle Mode"
                    description="Disable all automated actions except biome/aura detection and anti-afk."
                    checked={config.enable_idle_mode || false}
                    onChange={(val) => updateConfig("enable_idle_mode", val)}
                />

                <ToggleSwitch
                    label="Make Roblox instance on fullscreen"
                    description="Automatically fullscreen Roblox window when macro starts"
                    checked={config.auto_roblox_fullscreen || false}
                    onChange={(val) => updateConfig("auto_roblox_fullscreen", val)}
                />

                <ToggleSwitch
                    label="AZERTY Keyboard Mode (experimental)"
                    description="Enable this if you currently using AZERTY keyboard layout :aga:"
                    checked={config.azerty_mode || false}
                    onChange={(val) => updateConfig("azerty_mode", val)}
                />
            </div>

            {pendingLang && (
                <div className="biome-confirm-overlay" onClick={() => setPendingLang(null)}>
                    <div
                        className="biome-confirm-modal"
                        style={{ borderRadius: 0, maxWidth: 460, textAlign: "center" }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="biome-confirm-icon">🌐</div>
                        <h3 className="biome-confirm-title">{t("Change language?")}</h3>
                        <p style={{ color: "var(--text-muted, #999)", margin: "0 0 18px", lineHeight: 1.6 }}>
                            {t("Switching the language resets your custom tab names (panel customization), because custom labels take priority over translated defaults.")}
                        </p>
                        <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
                            <button className="btn btn-secondary" onClick={() => setPendingLang(null)}>{t("Cancel")}</button>
                            <button className="btn btn-stop" onClick={confirmLanguageChange}>{t("Switch language")}</button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
