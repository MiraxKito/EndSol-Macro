import { useState } from "react";
import { useT } from "../i18n";
import { useConfig } from "../contexts/ConfigContext";
import ToggleSwitch from "../components/ToggleSwitch";
import { looksLikeWebhookUrl, getWebhookWarning } from "../utils/webhookGuard";

export default function RemoteAccessPage() {
    const { config, saveConfig, error } = useConfig();
    const t = useT();
    const [showHelp, setShowHelp] = useState(false);

    if (error) return <div style={{ padding: "20px", color: "red" }}>Error: {error}</div>;
    if (!config) return <div style={{ padding: "20px" }}>Loading...</div>;

    const updateConfig = (key: string, value: any) => {
        saveConfig({ ...config, [key]: value });
    };

    const handleBotTokenChange = (val: string) => {
        if (looksLikeWebhookUrl(val)) {
            alert(getWebhookWarning(val, "Discord Bot Token"));
            return;
        }
        updateConfig("remote_bot_token", val);
    };

    const handleUserIdChange = (val: string) => {
        if (looksLikeWebhookUrl(val)) {
            alert(getWebhookWarning(val, "Allowed User ID"));
            return;
        }
        updateConfig("remote_allowed_user_id", val);
    };

    return (
        <>
            <div className="page-header" style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ flex: 1 }}>
                    <h2>{t("Remote Access")}</h2>
                    <p>{t("Control your macro remotely via a Discord bot")}</p>
                </div>
                <button
                    className="btn btn-secondary"
                    title="How to set up the Discord bot and its commands"
                    onClick={() => setShowHelp(true)}
                >
                    ?
                </button>
            </div>

            <div className="card">
                <div className="card-header">
                    <div className="card-icon">🔑</div>
                    <div>
                        <h3>Remote Access Control</h3>
                        <p>Enable and configure remote macro control</p>
                    </div>
                </div>

                <ToggleSwitch
                    label={t("Enable Remote Access Control")}
                    description={t("Turns the Discord bot online/offline immediately (bot must be started with the macro running).")}
                    checked={config.remote_access_enabled || false}
                    onChange={async (val) => {
                        updateConfig("remote_access_enabled", val);
                        try {
                            await window.pywebview?.api?.set_remote_access?.(val);
                        } catch (e) {
                            console.error("set_remote_access failed:", e);
                        }
                    }}
                />

                {config.remote_access_enabled && (
                    <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "12px" }}>
                        <div className="form-group">
                            <label className="form-label">{t("Discord Bot Token:")}</label>
                            <input
                                className="form-input"
                                type="password"
                                value={config.remote_bot_token || ""}
                                onChange={(e) => handleBotTokenChange(e.target.value)}
                                placeholder={t("Enter your Discord bot token")}
                                style={{ width: "100%", maxWidth: "440px" }}
                            />
                        </div>

                        <div className="form-group">
                            <label className="form-label">{t("Allowed User ID:")}</label>
                            <input
                                className="form-input"
                                value={config.remote_allowed_user_id || ""}
                                onChange={(e) => handleUserIdChange(e.target.value)}
                                placeholder="123456789012345678"
                                style={{ width: "220px" }}
                            />
                        </div>

                        <div>
                            <a
                                href="https://www.youtube.com/watch?v=dZzQytUMlCE"
                                target="_blank"
                                rel="noreferrer"
                                style={{
                                    color: "royalblue",
                                    textDecoration: "underline",
                                    cursor: "pointer",
                                    fontSize: "13px",
                                }}
                            >
                                Setup tutorial
                            </a>
                        </div>
                    </div>
                )}
            </div>

            {showHelp && (
                <div className="biome-confirm-overlay" onClick={() => setShowHelp(false)}>
                    <div
                        className="biome-confirm-modal"
                        style={{ borderRadius: 0, maxWidth: 560, textAlign: "left", maxHeight: "80vh", overflowY: "auto" }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <h3 style={{ marginTop: 0, color: "var(--text, #eee)" }}>{t("Remote Access — Help")}</h3>

                        <p style={{ fontWeight: 700, margin: "12px 0 6px" }}>{t("Setup")}</p>
                        <ol style={{ margin: 0, paddingLeft: 20, lineHeight: 1.7 }}>
                            <li>Open the <b>Discord Developer Portal</b> → New Application → tab <b>Bot</b> → copy the token and paste it into <b>Bot Token</b> below.</li>
                            <li>In Discord enable <b>Settings → Advanced → Developer Mode</b>, right-click your own name → <b>Copy User ID</b> → paste into <b>Allowed User ID</b> (only this user can send commands).</li>
                            <li>Invite the bot to your server: Developer Portal → <b>OAuth2 → URL Generator</b> → check scopes <b>bot</b> + <b>applications.commands</b> → open the generated URL.</li>
                            <li>Turn on <b>Enable Remote Access Control</b>. The bot comes online together with the macro.</li>
                        </ol>

                        <p style={{ fontWeight: 700, margin: "14px 0 6px" }}>{t("Commands (slash commands in Discord)")}</p>
                        <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 13 }}>
                            <tbody>
                                {[
                                    ["/start", "Start the macro"],
                                    ["/stop", "Stop the macro"],
                                    ["/status", "Status, biome, session time, biome counts"],
                                    ["/use <item> [amount]", "Use an item remotely"],
                                    ["/equip_aura <name>", "Equip an aura by name"],
                                    ["/check_merchant", "Teleport to the merchant and check it"],
                                    ["/screenshot", "Screenshot to your webhooks"],
                                    ["/reroll_quest", "Reroll a daily quest"],
                                    ["/rejoin", "Close Roblox to force a rejoin (Auto Reconnect needed)"],
                                    ["/close_roblox_and_stop_macro", "Kill Roblox and stop the macro"],
                                    ["/help", "This list in Discord"],
                                ].map(([cmd, desc]) => (
                                    <tr key={cmd}>
                                        <td style={{ padding: "3px 8px 3px 0", whiteSpace: "nowrap", color: "#7db4ff", fontFamily: "monospace" }}>{cmd}</td>
                                        <td style={{ padding: "3px 0", color: "var(--text-muted, #aaa)" }}>{t(desc)}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>

                        <p style={{ color: "var(--text-muted, #999)", fontSize: 12, marginTop: 12 }}>
                            {t("Commands only work from the Allowed User ID. Some actions are blocked while the macro is in an uninterruptible mode (e.g. Fishing).")}
                        </p>

                        <div style={{ textAlign: "center", marginTop: 14 }}>
                            <button className="btn btn-secondary" onClick={() => setShowHelp(false)}>{t("Close")}</button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
