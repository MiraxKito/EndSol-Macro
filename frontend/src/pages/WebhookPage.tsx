import { useState } from "react";
import { useConfig } from "../contexts/ConfigContext";
import { looksLikeWebhookUrl, getWebhookWarning } from "../utils/webhookGuard";

const FALLBACK_BIOME_COLORS: Record<string, string> = {
    "WINDY": "#9ae5ff",
    "RAINY": "#027cbd",
    "SNOWY": "#Dceff9",
    "SAND STORM": "#8F7057",
    "HELL": "#ff4719",
    "STARFALL": "#011ab7",
    "CORRUPTION": "#6d32a8",
    "NULL": "#838383",
    "GLITCHED": "#bfff00",
    "DREAMSPACE": "#ea9dda",
    "CYBERSPACE": "#0A1A3D",
    "AURORA": "#56d6a0",
    "HEAVEN": "#dfaf63",
    "EGGLAND": "#d4fc8d",
    "SINGULARITY": "#cf4023",
    "PUMPKIN MOON": "#FF6600",
    "GRAVEYARD": "#4A4A4A",
    "BLOOD RAIN": "#CC0000",
    "BLAZING SUN": "#FF6B00",
    "INCINERATOR": "#3b1f1f",
    "THE HYPERSPACE REALM": "#9b59b6",
    "\u8d64\u3044\u6e80\u6708": "#cc0000",
    "THE NULL'S EXISTENCE": "#1a1a2e",
    "THE CITADEL OF ORDERS": "#c0a030",
};

const RARE_BIOMES = new Set(["GLITCHED", "DREAMSPACE", "CYBERSPACE"]);
const ADMIN_BIOMES = new Set(["THE HYPERSPACE REALM", "赤い満月", "THE NULL'S EXISTENCE", "THE CITADEL OF ORDERS"]);
const SPECIAL_MESSAGE_BIOMES = new Set([...RARE_BIOMES, ...ADMIN_BIOMES]);
const FORCED_EVERYONE_BIOMES = new Set(["GLITCHED", "DREAMSPACE", "CYBERSPACE"]);

type BiomePingEntry = { id: string; type: "userid" | "roleid" };

export default function WebhookPage() {
    const { config, saveConfig, error, biomeColors } = useConfig();
    const [testing, setTesting] = useState(false);
    const [visible, setVisible] = useState<Record<number, boolean>>({});

    if (error) return (
        <div style={{ padding: "20px", color: "#ef4444" }}>
            <h3>Error Loading Config</h3>
            <p>{error}</p>
        </div>
    );

    if (!config) return <div style={{ padding: "20px" }}>Loading config...</div>;

    const urls = (config.webhook_url && config.webhook_url.length > 0) ? config.webhook_url : [""];
    const biomes = config.biome_notifier || {};
    const biomePings: Record<string, BiomePingEntry> = config.biome_pings || {};

    // Build ordered biome list from biome_notifier keys (excluding NORMAL)
    const knownBiomeNames = [
        "WINDY", "RAINY", "SNOWY", "SAND STORM", "HELL", "STARFALL", "CORRUPTION", "NULL",
        "AURORA", "HEAVEN", "EGGLAND", "BLAZING SUN", "INCINERATOR", "PUMPKIN MOON", "GRAVEYARD", "BLOOD RAIN",
        "GLITCHED", "DREAMSPACE", "CYBERSPACE", "SINGULARITY", "THE HYPERSPACE REALM", "赤い満月",
        "THE NULL'S EXISTENCE", "THE CITADEL OF ORDERS"
    ];
    const allBiomeNames = Array.from(new Set([...knownBiomeNames, ...Object.keys(biomes), ...Object.keys(biomeColors)]))
        .filter(b => b !== "NORMAL")
        .sort((a, b) => {
            const knownOrder = [
                "GLITCHED", "DREAMSPACE", "CYBERSPACE", "SINGULARITY",
                "WINDY", "RAINY", "SNOWY", "SAND STORM",
                "HELL", "STARFALL", "CORRUPTION", "NULL",
                "AURORA", "HEAVEN", "EGGLAND", "BLAZING SUN", "INCINERATOR",
                "PUMPKIN MOON", "GRAVEYARD", "BLOOD RAIN",
                "THE HYPERSPACE REALM", "\u8d64\u3044\u6e80\u6708",
                "THE NULL'S EXISTENCE", "THE CITADEL OF ORDERS"
            ];
            const ai = knownOrder.indexOf(a);
            const bi = knownOrder.indexOf(b);
            if (ai !== -1 && bi !== -1) return ai - bi;
            if (ai !== -1) return -1;
            if (bi !== -1) return 1;
            return a.localeCompare(b);
        });

    const otherBiomeNames = allBiomeNames.filter(b => !RARE_BIOMES.has(b));

    function getBiomeColor(biome: string): string {
        return biomeColors[biome] || FALLBACK_BIOME_COLORS[biome] || "#9ca3af";
    }

    const updateUrls = (newUrls: string[]) => {
        saveConfig({ ...config, webhook_url: newUrls });
    };

    const addUrl = () => updateUrls([...urls, ""]);
    const removeUrl = (i: number) => {
        setVisible(prev => {
            const next = { ...prev };
            delete next[i];
            return next;
        });
        updateUrls(urls.filter((_: string, idx: number) => idx !== i));
    };

    const updateUrl = (i: number, val: string) => {
        const next = [...urls];
        next[i] = val;
        updateUrls(next);
    };

    const toggleVisible = (i: number) => {
        setVisible(prev => ({ ...prev, [i]: !prev[i] }));
    };

    const updateBiomeSetting = (biome: string, value: string) => {
        const newNotifier = { ...biomes, [biome]: value };
        saveConfig({ ...config, biome_notifier: newNotifier });
    };

    const updateBiomePing = (biome: string, field: "id" | "type", value: string) => {
        const current = biomePings[biome] || { id: "", type: "userid" };
        if (field === "id") {
            const normalized = value.trim().toLowerCase();
            if ((normalized === "everyone" || normalized === "here") && !FORCED_EVERYONE_BIOMES.has(biome)) {
                alert(
                    `⚠️ Warning: @${normalized} is reserved for GLITCHED, DREAMSPACE, and CYBERSPACE.\n\n` +
                    `This ping will be silently ignored for ${biome}. Use a User ID or Role ID instead.`
                );
                return;
            }
        }

        const updated = { ...biomePings, [biome]: { ...current, [field]: value } };
        saveConfig({ ...config, biome_pings: updated });
    };

    const handleRobloxUsernameChange = (val: string) => {
        if (looksLikeWebhookUrl(val)) {
            alert(getWebhookWarning(val, "Roblox Username"));
            return;
        }
        saveConfig({ ...config, roblox_username: val });
    };

    const handlePrivateServerLinkChange = (val: string) => {
        if (looksLikeWebhookUrl(val)) {
            alert(getWebhookWarning(val, "Private Server Link"));
            return;
        }
        saveConfig({ ...config, private_server_link: val });
    };

    const handleTestWebhooks = async () => {
        if (testing) return;
        setTesting(true);
        try {
            if (window.pywebview && window.pywebview.api) {
                await window.pywebview.api.send_webhook_status("Webhook Sent Successfully!", 5814783);
            }
        } catch (e) {
            alert("Failed to send test: " + e);
        } finally {
            setTesting(false);
        }
    };

    const renderBiomeRow = (biome: string) => {
        const pingEntry = biomePings[biome] || { id: "", type: "userid" };
        const isSpecial = SPECIAL_MESSAGE_BIOMES.has(biome);
        const isForcedEveryone = FORCED_EVERYONE_BIOMES.has(biome);
        const color = getBiomeColor(biome);

        return (
            <div
                key={biome}
                style={{
                    display: "grid",
                    gridTemplateColumns: "130px 1fr",
                    gap: "10px",
                    alignItems: "center",
                    padding: "10px 12px",
                    borderBottom: "1px solid var(--border-color)",
                }}
            >
                {/* Biome label + message dropdown */}
                <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                    <span
                        style={{
                            width: "8px",
                            height: "8px",
                            borderRadius: "999px",
                            background: color,
                            flexShrink: 0,
                        }}
                    />
                    <span
                        style={{
                            fontWeight: 600,
                            fontSize: "13px",
                            color,
                            whiteSpace: "nowrap",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                        }}
                    >
                        {biome}
                    </span>
                </div>

                {/* Controls row */}
                <div style={{ display: "flex", gap: "8px", alignItems: "center", flexWrap: "wrap" }}>
                    {!isSpecial && (
                        <select
                            className="form-input"
                            style={{ width: "100px", fontSize: "12px", padding: "4px 6px" }}
                            value={biomes[biome] || "Message"}
                            onChange={(e) => updateBiomeSetting(biome, e.target.value)}
                        >
                            <option value="Message">Message</option>
                            <option value="None">None</option>
                        </select>
                    )}

                    {isForcedEveryone ? (
                        <div style={{ flex: 1, color: "var(--text-muted)", fontSize: "12px", fontStyle: "italic", paddingLeft: "4px" }}>
                            Forced Webhook + <span style={{ color: "#ef4444", fontWeight: 600 }}>@everyone</span>
                        </div>
                    ) : (
                        <>
                            <input
                                className="form-input"
                                style={{
                                    flex: 1,
                                    minWidth: "120px",
                                    fontSize: "12px",
                                    padding: "4px 8px",
                                }}
                                placeholder="User/Role ID"
                                value={pingEntry.id}
                                onChange={(e) => updateBiomePing(biome, "id", e.target.value)}
                            />

                            <select
                                className="form-input"
                                style={{ width: "90px", fontSize: "12px", padding: "4px 6px" }}
                                value={pingEntry.type}
                                onChange={(e) => updateBiomePing(biome, "type", e.target.value as "userid" | "roleid")}
                            >
                                <option value="userid">User ID</option>
                                <option value="roleid">Role ID</option>
                            </select>
                        </>
                    )}
                </div>
            </div>
        );
    };

    return (
        <>
            <div className="page-header">
                <h2>Webhook</h2>
                <p>Configure Discord webhook URLs for notifications</p>
            </div>

            <div className="card">
                <div className="card-header">
                    <div className="card-icon">👤</div>
                    <div>
                        <h3>Your Roblox username</h3>
                        <p>input your Roblox username (case-insensitive) for higher logs accuracy reading</p>
                    </div>
                </div>
                <input
                    className="form-input"
                    placeholder="Enter your Roblox username"
                    style={{ width: "100%" }}
                    value={config.roblox_username || ""}
                    onChange={(e) => handleRobloxUsernameChange(e.target.value)}
                />
            </div>

            <div className="card">
                <div className="card-header">
                    <div className="card-icon">🔗</div>
                    <div>
                        <h3>Discord Webhook URLs</h3>
                        <p>Multiple webhook URLs are supported!</p>
                    </div>
                </div>

                <div className="webhook-list">
                    {urls.map((url: string, i: number) => (
                        <div key={i} className="webhook-entry">
                            <button
                                className="btn-icon"
                                onClick={() => toggleVisible(i)}
                                style={{
                                    marginRight: "8px",
                                    background: "rgba(255,255,255,0.1)",
                                    border: "none",
                                    borderRadius: "4px",
                                    width: "32px",
                                    height: "32px",
                                    cursor: "pointer",
                                    display: "flex",
                                    alignItems: "center",
                                    justifyContent: "center"
                                }}
                                title={visible[i] ? "Hide URL" : "Show URL"}
                            >
                                {visible[i] ? "👁️" : "🔒"}
                            </button>
                            <input
                                type={visible[i] ? "text" : "password"}
                                className="form-input"
                                placeholder={`Webhook URL ${i + 1}`}
                                value={url}
                                onChange={(e) => updateUrl(i, e.target.value)}
                            />
                            <button className="btn-remove" onClick={() => removeUrl(i)}>
                                ×
                            </button>
                        </div>
                    ))}
                </div>

                <div style={{ display: "flex", gap: "8px" }}>
                    <button className="btn btn-secondary" onClick={addUrl}>
                        + Add URL
                    </button>
                    <button
                        className="btn btn-accent"
                        onClick={handleTestWebhooks}
                        disabled={testing}
                        style={{ opacity: testing ? 0.7 : 1 }}
                    >
                        {testing ? "Sending..." : "Test Webhooks"}
                    </button>
                </div>
            </div>

            <div className="card">
                <div className="card-header">
                    <div className="card-icon">🔗</div>
                    <div>
                        <h3>Private Server Link</h3>
                        <p>Your Roblox private server link when there's rare biomes</p>
                    </div>
                </div>
                <input
                    className="form-input"
                    placeholder="https://www.roblox.com/games/..."
                    style={{ width: "100%" }}
                    value={config.private_server_link || ""}
                    onChange={(e) => handlePrivateServerLinkChange(e.target.value)}
                />
            </div>

            {/* Other Biomes */}
            <div className="card">
                <div className="card-header">
                    <div className="card-icon">⚙️</div>
                    <div>
                        <h3>Biome Configuration</h3>
                        <p>Configure notifications and individual pings per biome</p>
                    </div>
                </div>

                <div style={{ fontSize: "11px", color: "var(--text-muted)", marginBottom: "10px", padding: "0 12px" }}>
                    Each biome can ping a specific User ID or Role ID. <span style={{ color: "#ef4444" }}>@everyone / @here are NOT allowed</span> for non-rare biomes.
                </div>

                <div style={{
                    color: "#ef4444",
                    fontSize: "13px",
                    marginBottom: "16px",
                    textAlign: "center",
                    fontWeight: 600
                }}>
                    Built-in @everyone is reserved for GLITCHED, DREAMSPACE, and CYBERSPACE. Admin biomes use the ping setting you choose.
                </div>

                <div>
                    {otherBiomeNames.map(renderBiomeRow)}
                </div>
            </div>
        </>
    );
}