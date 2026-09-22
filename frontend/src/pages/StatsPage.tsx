import { useState, useEffect, useRef, useCallback } from "react";
import { useConfig } from "../contexts/ConfigContext";
import { useToast } from "../contexts/ToastContext";
import { useT } from "../i18n";

const GLITCH_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()[]{}<>?/\\|~`";

// ── Biome categories (matches backend base_support.py) ──
type BiomeCategoryKey = "weather" | "rare" | "event" | "admin" | "other";

const BIOME_CATEGORIES: Record<string, BiomeCategoryKey> = {
    NORMAL: "weather", WINDY: "weather", RAINY: "weather", SNOWY: "weather",
    "SAND STORM": "weather", HELL: "weather", STARFALL: "weather",
    HEAVEN: "weather", CORRUPTION: "weather", NULL: "weather",
    GLITCHED: "rare", DREAMSPACE: "rare", CYBERSPACE: "rare", SINGULARITY: "rare",
    "PUMPKIN MOON": "event", GRAVEYARD: "event", "BLOOD RAIN": "event",
    AURORA: "event", EGGLAND: "event", "BLAZING SUN": "event", INCINERATOR: "event",
    "THE HYPERSPACE REALM": "admin", "\u8d64\u3044\u6e80\u6708": "admin",
    "THE NULL'S EXISTENCE": "admin", "THE CITADEL OF ORDERS": "admin",
};

const CATEGORY_LABELS: Record<BiomeCategoryKey, string> = {
    weather: "Normal (Weather)",
    rare: "Rare",
    event: "Event (Limited)",
    admin: "Admin (Dev Event)",
    other: "Other / Unlisted",
};

const CATEGORY_ORDER: BiomeCategoryKey[] = ["weather", "rare", "event", "admin", "other"];

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

function GlitchText() {
    const [text, setText] = useState("GLITCHED");
    const frameRef = useRef(0);
    const lastUpdateRef = useRef(0);

    const generateGlitchString = useCallback(() => {
        const len = 6 + Math.floor(Math.random() * 12);
        const chars: string[] = [];
        for (let i = 0; i < len; i++) {
            if (i > 0 && i % 4 === 0 && Math.random() > 0.5) {
                chars.push("-");
            } else {
                chars.push(GLITCH_CHARS[Math.floor(Math.random() * GLITCH_CHARS.length)]);
            }
        }
        return `[${chars.join("")}]`;
    }, []);

    useEffect(() => {
        const animate = (timestamp: number) => {
            if (timestamp - lastUpdateRef.current > 35) {
                setText(generateGlitchString());
                lastUpdateRef.current = timestamp;
            }
            frameRef.current = requestAnimationFrame(animate);
        };
        frameRef.current = requestAnimationFrame(animate);
        return () => cancelAnimationFrame(frameRef.current);
    }, [generateGlitchString]);

    return (
        <span className="glitch-text">{text}</span>
    );
}

export default function StatsPage() {
    const { config, error, sessionDuration, lastStartTime, isMacroRunning, biomeColors } = useConfig();
    const { showToast } = useToast();
    const t = useT();
    const [elapsedDisplay, setElapsedDisplay] = useState("00:00:00");
    const [showResetModal, setShowResetModal] = useState(false);
    const [resetCooldown, setResetCooldown] = useState(5);

    // Confirmation button unlocks after a 5s cooldown so it can't be
    // clicked reflexively the moment the dialog appears.
    useEffect(() => {
        if (!showResetModal) return;
        setResetCooldown(5);
        const timer = window.setInterval(() => {
            setResetCooldown(prev => (prev > 0 ? prev - 1 : 0));
        }, 1000);
        return () => window.clearInterval(timer);
    }, [showResetModal]);

    const closeResetModal = () => setShowResetModal(false);

    const doResetStats = async () => {
        if (resetCooldown > 0) return;
        closeResetModal();
        try {
            const api = window.pywebview?.api;
            if (!api?.reset_stats) {
                showToast("Reset is not available in this build.", "error");
                return;
            }
            const result = await api.reset_stats() as { success: boolean; error?: string };
            if (result?.success) showToast("Statistics reset.", "success");
            else showToast(result?.error || "Failed to reset statistics.", "error");
        } catch {
            showToast("Failed to reset statistics.", "error");
        }
    };

    useEffect(() => {
        const updateTimer = () => {
            let totalMs = sessionDuration;
            if (isMacroRunning && lastStartTime) {
                totalMs += (Date.now() - lastStartTime);
            }

            const hours = Math.floor(totalMs / (1000 * 60 * 60));
            const minutes = Math.floor((totalMs % (1000 * 60 * 60)) / (1000 * 60));
            const seconds = Math.floor((totalMs % (1000 * 60)) / 1000);

            const pad = (n: number) => n.toString().padStart(2, "0");
            setElapsedDisplay(`${pad(hours)}:${pad(minutes)}:${pad(seconds)}`);
        };

        updateTimer();
        const interval = setInterval(updateTimer, 1000);
        return () => clearInterval(interval);
    }, [sessionDuration, lastStartTime, isMacroRunning]);

    function getBiomeColor(biome: string): string {
        return biomeColors[biome] || FALLBACK_BIOME_COLORS[biome] || "#9ca3af";
    }

    if (error) return (
        <div style={{ padding: "20px", color: "#ef4444" }}>
            <h3>Error Loading Stats</h3>
            <p>{error}</p>
        </div>
    );

    if (!config) return <div style={{ padding: "20px" }}>Loading stats...</div>;

    const biomeCounts = config.biome_counts || {};
    const totalBiomes = Object.entries(biomeCounts)
        .filter(([key]) => key !== "NORMAL")
        .reduce((a, [, count]) => a + Number(count), 0);

    const merchantCounts = config.merchant_counts || {};
    const totalMerchants = Object.values(merchantCounts).reduce((a, b) => a + Number(b), 0);

    // Group biomes by category — include ALL known biomes from BIOME_CATEGORIES (not just detected ones)
    const allKnownBiomes = new Set([...Object.keys(BIOME_CATEGORIES), ...Object.keys(biomeCounts)]);
    allKnownBiomes.delete("NORMAL");
    const grouped: Record<BiomeCategoryKey, string[]> = { weather: [], rare: [], event: [], admin: [], other: [] };
    for (const biome of allKnownBiomes) {
        const cat = BIOME_CATEGORIES[biome] || "other";
        grouped[cat].push(biome);
    }
    // Sort within each group
    for (const cat of CATEGORY_ORDER) {
        grouped[cat].sort();
    }

    return (
        <>
            <div className="page-header">
                <h2>{t("Stats")}</h2>
                <p>{t("Session statistics and biome encounter history")}</p>
            </div>

            <div className="card">
                <div className="card-header">
                    <div className="card-icon">⏱️</div>
                    <div>
                        <h3>{t("Session Overview")}</h3>
                        <p>{t("Current macro session statistics")}</p>
                    </div>
                    <button
                        className="btn btn-secondary"
                        style={{ marginLeft: "auto" }}
                        title={t("Reset biomes, merchants, auras and session time")}
                        onClick={() => setShowResetModal(true)}
                    >
                        {t("Reset stats")}
                    </button>
                </div>

                <div className="stats-grid">
                    <div className="stat-card accent">
                        <div className="stat-value">{elapsedDisplay}</div>
                        <div className="stat-label">{t("Session Time")}</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-value">{totalBiomes.toLocaleString()}</div>
                        <div className="stat-label">{t("Total Biomes Founds")}</div>
                    </div>
                    <div className="stat-card">
                        <div className="stat-value">{totalMerchants.toLocaleString()}</div>
                        <div className="stat-label">{t("Merchants Found")}</div>
                    </div>
                </div>
            </div>

            {/* ── Biome Counts by Category ── */}
            {CATEGORY_ORDER.map((cat) => {
                const biomes = grouped[cat];
                if (biomes.length === 0) return null;
                return (
                    <div className="card" key={cat}>
                        <div className="card-header">
                            <div className="card-icon">
                                {cat === "weather" ? "🌤️" : cat === "rare" ? "💎" : cat === "event" ? "🎪" : cat === "admin" ? "🔧" : "❓"}
                            </div>
                            <div>
                                <h3>{t(CATEGORY_LABELS[cat])}</h3>
                                <p>{biomes.length} biome{biomes.length !== 1 ? "s" : ""} discovered</p>
                            </div>
                        </div>

                        <div className="stats-grid">
                            {biomes.map((name) => (
                                <div key={name} className="stat-card">
                                    <div className="stat-value">{biomeCounts[name] || 0}</div>
                                    <div className="stat-label" style={{ color: getBiomeColor(name) }}>
                                        {name === "GLITCHED" ? <GlitchText /> : name}
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                );
            })}

            {showResetModal && (
                <div className="biome-confirm-overlay" onClick={closeResetModal}>
                    <div
                        className="biome-confirm-modal"
                        style={{ borderRadius: 0 }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="biome-confirm-icon">⚠️</div>
                        <h3 className="biome-confirm-title">{t("Reset statistics?")}</h3>
                        <p style={{ color: "var(--text-muted, #999)", margin: "0 0 18px" }}>
                            {t("Biome, merchant and aura counters plus session time will be wiped. This cannot be undone.")}
                        </p>
                        <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
                            <button className="btn btn-secondary" onClick={closeResetModal}>{t("Cancel")}</button>
                            <button className="btn btn-stop" disabled={resetCooldown > 0} onClick={doResetStats}>
                                {resetCooldown > 0 ? `Wait ${resetCooldown}s…` : t("Yes, reset everything")}
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}
