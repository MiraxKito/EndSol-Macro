import { useConfig } from "../contexts/ConfigContext";
import { useState, useEffect, useRef, type ReactNode } from "react";

const CUSTOM_MESSAGE_LIMIT = 300;
const sanitizeCustomMessage = (value: string) => value
    .replace(/@/g, "")
    .replace(/[\u0000-\u001F\u007F\u200B\u200C\u200D\uFEFF]/g, "")
    .slice(0, CUSTOM_MESSAGE_LIMIT);

type BiomeData = {
    color: string;
    thumbnail_url: string;
    spawn_chance?: string;
    duration?: string;
    how_to_get?: string;
};

type RareCustom = {
    color: string;
    title_start: string;
    title_end: string;
    desc_start: string;
    desc_end: string;
};

export default function CustomizationPage() {
    const { config, saveConfig } = useConfig();
    const [biomes, setBiomes] = useState<Record<string, BiomeData>>({});
    const [rareCustom, setRareCustom] = useState<Record<string, RareCustom>>({});
    const [selectedBiome, setSelectedBiome] = useState<string>("");
    const previewMode = "start";
    const [sendingTest, setSendingTest] = useState(false);
    const [testResult, setTestResult] = useState<{ success: boolean; error?: string } | null>(null);
    const [customMessages, setCustomMessages] = useState<Record<string, { start?: string; end?: string }>>({});
    const selectRef = useRef<HTMLSelectElement>(null);

    useEffect(() => {
        setCustomMessages((config as any)?.custom_webhook_messages || {});
    }, [config]);

    const updateCustomMessage = (biome: string, phase: string, value: string) => {
        if (!config || !biome) return;
        const next = { ...customMessages, [biome]: { ...(customMessages[biome] || {}), [phase]: sanitizeCustomMessage(value) } };
        setCustomMessages(next);
        saveConfig({ ...config, custom_webhook_messages: next } as any);
    };

    const sendTestWebhook = async () => {
        if (!selectedBiome || !window.pywebview?.api?.send_webhook) return;
        setSendingTest(true);
        setTestResult(null);
        try {
            const biomeInfo = biomes[selectedBiome];
            if (!biomeInfo) {
                setTestResult({ success: false, error: "Biome data not loaded" });
                return;
            }
            // Use the backend send_webhook with event_type "start" and no ping
            // The backend send_webhook handles biome start/end events
            await window.pywebview.api.send_webhook(
                selectedBiome, 
                "Test", // message_type - will be used as "Test" instead of ping
                "start", // event_type
                "" // no screenshot
            );
            // The backend returns void, so we'll check if it threw
            setTestResult({ success: true });
        } catch (e: any) {
            setTestResult({ success: false, error: e?.message || "Failed to send test webhook" });
        } finally {
            setSendingTest(false);
        }
    };

    useEffect(() => {
        let isMounted = true;
        const loadData = async () => {
            if (!config) return;
            try {
                let defaultData: Record<string, BiomeData> = {};
                if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_full_biome_data === 'function') {
                    defaultData = await window.pywebview.api.get_full_biome_data() as Record<string, BiomeData>;
                }

                let rareData: Record<string, RareCustom> = {};
                if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_rare_biome_custom === 'function') {
                    rareData = await window.pywebview.api.get_rare_biome_custom() as Record<string, RareCustom>;
                }
                // Keep user overrides authoritative, but ensure the preview
                // still has the backend's real rare templates when the bridge
                // returns an empty response during startup.
                if (!rareData || typeof rareData !== "object") rareData = {};
                const rareOverrides = config.custom_rare_biome_overrides || {};
                rareData = { ...rareData, ...rareOverrides } as Record<string, RareCustom>;

                const overrides = config.custom_biome_overrides || {};
                const merged: Record<string, BiomeData> = {};

                for (const biome of Object.keys(defaultData)) {
                    merged[biome] = {
                        ...defaultData[biome],
                        ...overrides[biome]
                    };
                }
                for (const biome of Object.keys(overrides)) {
                    if (!merged[biome]) merged[biome] = overrides[biome];
                }

                if (isMounted) {
                    setBiomes(merged);
                    setRareCustom(rareData);
                    if (!selectedBiome) {
                        const keys = Object.keys(merged).filter(b => b !== "NORMAL");
                        if (keys.length > 0) setSelectedBiome(keys[0]);
                    }
                }
            } catch (err) {
                console.error("Failed to load biome data", err);
            }
        };
        loadData();
        return () => { isMounted = false; };
    }, [config]);

    const handleBiomeChange = (field: "color" | "thumbnail_url", value: string) => {
        if (!selectedBiome) return;
        setBiomes(prev => ({
            ...prev,
            [selectedBiome]: {
                ...prev[selectedBiome],
                [field]: value
            }
        }));
    };

    const saveBiomes = async () => {
        if (!config) return;
        let defaultData: Record<string, BiomeData> = {};
        if (window.pywebview && window.pywebview.api && typeof window.pywebview.api.get_full_biome_data === 'function') {
            defaultData = await window.pywebview.api.get_full_biome_data() as Record<string, BiomeData>;
        }
        const overridesToSave: Record<string, any> = {};
        for (const [biome, data] of Object.entries(biomes)) {
            const def = defaultData[biome] || {};
            const hasColorDiff = data.color !== def.color && data.color !== undefined;
            const hasThumbDiff = data.thumbnail_url !== def.thumbnail_url && data.thumbnail_url !== undefined;
            if (hasColorDiff || hasThumbDiff) {
                overridesToSave[biome] = {
                    ...(hasColorDiff && { color: data.color }),
                    ...(hasThumbDiff && { thumbnail_url: data.thumbnail_url })
                };
            }
        }
        saveConfig({ ...config, custom_biome_overrides: overridesToSave } as any);
    };

    const biomeKeys = Object.keys(biomes).filter(b => b !== "NORMAL");

    useEffect(() => {
        const el = selectRef.current;
        if (!el) return;
        const handleNativeWheel = (e: WheelEvent) => {
            e.preventDefault();
            if (!biomeKeys.length) return;
            setSelectedBiome(prev => { const i = biomeKeys.indexOf(prev); if (i < 0) return prev; return biomeKeys[(i + (e.deltaY < 0 ? -1 : 1) + biomeKeys.length) % biomeKeys.length]; });
        };
        el.addEventListener("wheel", handleNativeWheel, { passive: false });
        return () => el.removeEventListener("wheel", handleNativeWheel);
    }, [biomeKeys]);

    // Live preview: the backend build_biome_webhook_description() is the single
    // source of truth, so the preview is generated by the exact same code path
    // that sends the webhook — custom rare copy, admin overrides, custom
    // messages and the Join Server link all match 1:1. Unsaved UI edits are
    // passed as overrides so the preview updates while typing.
    const [preview, setPreview] = useState<{ description: string; color: number; content: string } | null>(null);
    useEffect(() => {
        if (!config || !selectedBiome) return;
        const api = (window as any).pywebview?.api;
        if (!api?.preview_biome_webhook) return;
        const phase = previewMode;
        const entry = customMessages[selectedBiome] as any;
        const title = entry?.[`${phase}_title`] ?? "";
        const description = entry?.[`${phase}_description`] ?? entry?.[phase] ?? "";
        const rawColor = typeof biomes[selectedBiome]?.color === "string" ? biomes[selectedBiome].color : String(biomes[selectedBiome]?.color ?? "");
        const colorOverride = rawColor ? (rawColor.startsWith("0x") ? "#" + rawColor.slice(2) : rawColor) : undefined;
        let cancelled = false;
        const timer = setTimeout(async () => {
            try {
                const res = await api.preview_biome_webhook(selectedBiome, phase, title, description, colorOverride);
                if (cancelled) return;
                const parsed = typeof res === "string" ? JSON.parse(res) : res;
                if (parsed && !parsed.error) setPreview(parsed);
            } catch (e) {
                console.error("preview_biome_webhook failed", e);
            }
        }, 200);
        return () => { cancelled = true; clearTimeout(timer); };
    }, [config, selectedBiome, previewMode, customMessages, biomes]);

    if (!config) return <div>Loading...</div>;
    const currentBiomeData = biomes[selectedBiome] || { color: "#ffffff", thumbnail_url: "" };
    const rawColor = typeof currentBiomeData.color === "string" ? currentBiomeData.color : String(currentBiomeData.color ?? "#ffffff");
    const cssColor = rawColor.startsWith("0x") ? "#" + rawColor.slice(2) : rawColor;

    const isRare = selectedBiome && rareCustom[selectedBiome] !== undefined;

    // Render the backend description exactly as Discord will: the first line
    // is the Discord timestamp (shown as the pill above), "> " prefixes and
    // markdown headings/bold/links are resolved.
    const renderInline = (text: string): ReactNode => {
        const parts: ReactNode[] = [];
        const regex = /(\*\*[^*]+\*\*)|(\[[^\]]+\]\([^)\s]+\))/g;
        let last = 0;
        let m: RegExpExecArray | null;
        let key = 0;
        while ((m = regex.exec(text)) !== null) {
            if (m.index > last) parts.push(text.slice(last, m.index));
            if (m[1]) {
                parts.push(<strong key={key++} style={{ fontWeight: 700 }}>{m[1].slice(2, -2)}</strong>);
            } else {
                const lm = m[2].match(/^\[([^\]]+)\]\(([^)]+)\)$/);
                if (lm) parts.push(<a key={key++} href="#" style={{ color: "#00A8FC", textDecoration: "none" }} onClick={e => e.preventDefault()}>{lm[1]}</a>);
                else parts.push(m[2]);
            }
            last = regex.lastIndex;
        }
        if (last < text.length) parts.push(text.slice(last));
        return parts;
    };

    const previewLines: { type: "spacer" | "heading" | "text"; content?: ReactNode }[] = [];
    if (preview?.description) {
        for (const rawLine of String(preview.description).split("\n")) {
            if (/^<t:\d+:F>/.test(rawLine.trim())) continue; // timestamp pill is rendered separately
            const line = rawLine.replace(/^>\s?/, "");
            if (!line.trim()) { previewLines.push({ type: "spacer" }); continue; }
            const heading = line.match(/^#{2,4}\s+(.*)$/);
            if (heading) previewLines.push({ type: "heading", content: renderInline(heading[1]) });
            else previewLines.push({ type: "text", content: renderInline(line) });
        }
    }
    const previewColor = preview && typeof preview.color === "number"
        ? "#" + (preview.color & 0xffffff).toString(16).padStart(6, "0")
        : cssColor;
    const pingContent = preview?.content || "";
    const pingLabel = pingContent === "@everyone" || pingContent === "@here"
        ? pingContent
        : pingContent.startsWith("<@&") ? "@role" : pingContent.startsWith("<@") ? "@user" : "";

    const now = new Date();
    const timeOptions: Intl.DateTimeFormatOptions = {
        weekday: 'long', year: 'numeric', month: 'long', day: 'numeric',
        hour: 'numeric', minute: 'numeric', hour12: true
    };
    const formattedDate = now.toLocaleDateString('en-US', timeOptions);
    const docTitle = typeof document !== 'undefined' ? document.title.replace('EndSol Macro ', '') : '';

    return (
        <div className="page-container fade-in" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
            <div className="page-header">
                <h2>Discord Webhook Customization</h2>
                <p>Dynamically configure what your webhook embeds look like when a biome starts</p>
            </div>

            <div className="card" style={{ maxWidth: "560px", margin: "0 auto 16px" }}>
                <div className="card-header"><div className="card-icon">✉️</div><div><h3>Custom Biome Messages</h3><p>Messages are configured separately for each biome and event.</p></div></div>
                <div style={{ display: "grid", gap: "10px", padding: "0 16px 16px" }}>
                    <select className="form-input" value={selectedBiome} onChange={e => setSelectedBiome(e.target.value)}>
                        {Object.keys(biomes).filter(b => b !== "NORMAL").sort().map(b => <option key={b} value={b}>{b}</option>)}
                    </select>
                    {(["start", "end"] as const).map(phase => {
                        const entry = customMessages[selectedBiome] as any;
                        const titleKey = `${phase}_title`;
                        const descriptionKey = `${phase}_description`;
                        const title = entry?.[titleKey] || "";
                        const description = entry?.[descriptionKey] ?? entry?.[phase] ?? "";
                        return <div key={phase} style={{ display: "grid", gap: "6px" }}>
                            <label className="form-label">{phase === "start" ? "Biome started title" : "Biome ended title"}
                                <input className="form-input" value={title} maxLength={CUSTOM_MESSAGE_LIMIT} onChange={e => updateCustomMessage(selectedBiome, titleKey as any, e.target.value)} placeholder="Optional Discord embed title" />
                            </label>
                            <label className="form-label">{phase === "start" ? "Biome started description" : "Biome ended description"}
                                <textarea className="form-input" value={description} maxLength={CUSTOM_MESSAGE_LIMIT} onChange={e => updateCustomMessage(selectedBiome, descriptionKey as any, e.target.value)} placeholder="Optional custom description" style={{ width: "100%", minHeight: "70px", resize: "vertical" }} />
                                <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>{description.length}/{CUSTOM_MESSAGE_LIMIT}</span>
                            </label>
                        </div>;
                    })}
                </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: "16px", marginTop: "10px", minHeight: "0", maxWidth: "560px", margin: "0 auto", paddingBottom: "30px" }}>

                {/* TOP: Discord Simulator */}
                <div
                    style={{
                        backgroundColor: "#313338",
                        borderRadius: "8px",
                        border: "1px solid rgba(255,255,255,0.05)",
                        padding: "16px",
                        height: "fit-content",
                        overflowY: "auto",
                        display: "flex",
                        fontFamily: "'gg sans', 'Noto Sans', 'Helvetica Neue', Helvetica, Arial, sans-serif"
                    }}
                >
                    <div style={{ display: "flex", gap: "12px", width: "100%" }}>
                        <div style={{
                            width: "40px", height: "40px", borderRadius: "50%",
                            backgroundColor: "#5865F2", flexShrink: 0,
                            backgroundImage: "url('https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png')",
                            backgroundSize: "cover"
                        }}></div>

                        <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
                            <div style={{ display: "flex", alignItems: "baseline", gap: "6px", marginBottom: "2px", flexWrap: "wrap" }}>
                                <span style={{ color: "#F2F3F5", fontSize: "15px", fontWeight: "500", lineHeight: "1.2" }}>EndSol Biome Tracker</span>
                                <span style={{
                                    backgroundColor: "#5865F2", color: "#FFFFFF", fontSize: "9px",
                                    padding: "0 4px", borderRadius: "3px", fontWeight: "600",
                                    lineHeight: "13px", height: "13px", verticalAlign: "middle"
                                }}>APP</span>
                                <span style={{ color: "#949BA4", fontSize: "11px", marginLeft: "2px" }}>Today at {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                            </div>

                            <div style={{
                                backgroundColor: "#2b2d31",
                                borderLeft: `4px solid ${previewColor || '#FFFFFF'}`,
                                borderRadius: "4px",
                                display: "flex",
                                padding: "12px 14px",
                                marginTop: "4px"
                            }}>
                                <div style={{ display: "flex", flexDirection: "column", gap: "6px", flex: 1, minWidth: 0 }}>
                                    <div style={{
                                        color: "#F2F3F5",
                                        fontSize: "14px",
                                        fontWeight: "600",
                                        wordBreak: "break-word",
                                        marginBottom: "2px"
                                    }}>
                                        <span style={{
                                            backgroundColor: "rgba(255,255,255,0.06)",
                                            padding: "2px 4px",
                                            borderRadius: "3px"
                                        }}>
                                            {formattedDate} (just now)
                                        </span>
                                    </div>

                                    <div style={{
                                        fontSize: "13px",
                                        color: "#DBDEE1",
                                        lineHeight: "1.2",
                                        whiteSpace: "pre-wrap"
                                    }}>
                                        <div style={{
                                            borderLeft: "4px solid #4e5058",
                                            padding: "0 10px",
                                            marginLeft: "0"
                                        }}>
                                            {pingLabel && (
                                                <div style={{
                                                    fontSize: "14px",
                                                    fontWeight: "600",
                                                    color: "#DBDEE1",
                                                    backgroundColor: "rgba(88,101,242,0.15)",
                                                    display: "inline-block",
                                                    padding: "1px 5px",
                                                    borderRadius: "3px",
                                                    marginTop: "10px"
                                                }}>
                                                    {pingLabel}
                                                </div>
                                            )}
                                            {previewLines.map((line, i) => {
                                                if (line.type === "spacer") {
                                                    return <div key={i} style={{ height: "8px" }} />;
                                                }
                                                if (line.type === "heading") {
                                                    return <div key={i} style={{
                                                        fontSize: "18px",
                                                        fontWeight: "700",
                                                        color: "#F2F3F5",
                                                        marginTop: "16px",
                                                        marginBottom: "8px",
                                                        lineHeight: "1.4",
                                                        wordBreak: "break-word"
                                                    }}>{line.content}</div>;
                                                }
                                                return <div key={i} style={{
                                                    fontSize: "14px",
                                                    color: "#DBDEE1",
                                                    lineHeight: "1.375",
                                                    whiteSpace: "pre-wrap",
                                                    wordBreak: "break-word"
                                                }}>{line.content}</div>;
                                            })}
                                        </div>
                                    </div>

                                    <div style={{
                                        display: "flex",
                                        alignItems: "center",
                                        gap: "6px",
                                        marginTop: "4px"
                                    }}>
                                        <img src="https://i.postimg.cc/rsXpGncL/Noteab-Biome-Tracker.png" style={{ width: "16px", height: "16px", borderRadius: "50%" }} alt="footer" />
                                        <span style={{ color: "#949BA4", fontSize: "11px", fontWeight: "500" }}>EndSol Macro {docTitle} • Today at {now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                    </div>
                                </div>

                                {currentBiomeData.thumbnail_url && (
                                    <div style={{ marginLeft: "12px", flexShrink: 0 }}>
                                        <img
                                            src={currentBiomeData.thumbnail_url}
                                            style={{ maxWidth: "60px", maxHeight: "60px", borderRadius: "4px", objectFit: "contain" }}
                                            alt="thumbnail"
                                            onError={(e) => {
                                                (e.target as HTMLImageElement).style.display = 'none';
                                            }}
                                            onLoad={(e) => {
                                                (e.target as HTMLImageElement).style.display = 'block';
                                            }}
                                        />
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* MIDDLE: Select Biome */}
                <div className="card" title="Scroll with your mouse wheel here to quickly cycle through biomes!">
                    <label className="form-label" style={{ display: "flex", justifyContent: "space-between" }}>
                        Select Biome
                        <span style={{ fontSize: "0.8em", color: "#64748b", fontWeight: "normal" }}>(Scroll wheel supported)</span>
                    </label>
                    <select
                        ref={selectRef}
                        className="form-input"
                        style={{ width: "100%", padding: "10px", fontSize: "1.1em", cursor: "pointer", appearance: "auto" }}
                        value={selectedBiome}
                        onChange={(e) => setSelectedBiome(e.target.value)}
                    >
                        {biomeKeys.map(b => (
                            <option key={b} value={b}>
                                {b}{rareCustom[b] ? " ⭐" : ""}
                            </option>
                        ))}
                    </select>
                    {isRare && (
                        <div style={{ marginTop: "10px", padding: "8px 12px", backgroundColor: "rgba(99, 102, 241, 0.1)", borderRadius: "6px", fontSize: "12px", color: "#a5b4fc" }}>
                            ⭐ This biome has a custom rare message — preview shows real Discord output.
                        </div>
                    )}
                </div>

                {/* Test Webhook Send */}
                <div className="card" style={{ marginTop: "10px" }}>
                    <div className="card-header">
                        <div className="card-icon">🧪</div>
                        <div>
                            <h3>Test Webhook</h3>
                            <p>Send a test webhook for the selected biome (no ping, marked as test)</p>
                        </div>
                    </div>
                    <div style={{ padding: "16px", display: "flex", gap: "10px", alignItems: "center", flexWrap: "wrap" }}>
                        <button 
                            className="btn btn-accent"
                            onClick={sendTestWebhook}
                            disabled={sendingTest || !selectedBiome}
                            style={{ whiteSpace: "nowrap" }}
                        >
                            {sendingTest ? "Sending..." : "📤 Send Test Webhook"}
                        </button>
                        {testResult && (
                            <span style={{ 
                                color: testResult.success ? "#22c55e" : "#ef4444",
                                fontSize: "13px"
                            }}>
                                {testResult.success ? "✅ Test sent successfully!" : `❌ ${testResult.error}`}
                            </span>
                        )}
                    </div>
                </div>

                {/* BOTTOM: Config Inputs */}
                <div className="card" style={{ display: "flex", flexDirection: "column", gap: "15px" }}>
                    <div>
                        <label className="form-label" style={{ display: "flex", justifyContent: "space-between" }}>
                            Hex Color
                            <a href="#" style={{ color: "#0ea5e9", fontSize: "0.8em", textDecoration: "none" }} onClick={(e) => { e.preventDefault(); if ((window as any).pywebview) (window as any).pywebview.api.open_url("https://htmlcolorcodes.com/"); }}>
                                Get Colors
                            </a>
                        </label>
                        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                            <input
                                type="color"
                                style={{ width: "40px", height: "40px", padding: "0", border: "none", borderRadius: "8px", cursor: "pointer", background: "none" }}
                                value={cssColor}
                                onChange={(e) => handleBiomeChange("color", e.target.value)}
                            />
                            <input
                                type="text"
                                className="form-input"
                                style={{ flex: 1, fontFamily: "monospace" }}
                                value={currentBiomeData.color}
                                onChange={(e) => handleBiomeChange("color", e.target.value)}
                                placeholder="#FFFFFF"
                            />
                        </div>
                    </div>

                    <div>
                        <label className="form-label">Thumbnail URL</label>
                        <input
                            type="text"
                            className="form-input"
                            style={{ width: "100%", fontSize: "0.95em" }}
                            value={currentBiomeData.thumbnail_url}
                            onChange={(e) => handleBiomeChange("thumbnail_url", e.target.value)}
                            placeholder="https://..."
                        />
                        {currentBiomeData.thumbnail_url && (
                            <div style={{ marginTop: "8px", fontSize: "11px", color: currentBiomeData.thumbnail_url.includes("maxstellar") || currentBiomeData.thumbnail_url.includes("fandom") || currentBiomeData.thumbnail_url.includes("wikia") ? "#ef4444" : "#22c55e" }}>
                                {currentBiomeData.thumbnail_url.includes("maxstellar") || currentBiomeData.thumbnail_url.includes("fandom") || currentBiomeData.thumbnail_url.includes("wikia")
                                    ? "⚠ This URL host is known to be broken. Use a working OysterDetector URL instead."
                                    : "✓ URL looks valid (not from a known broken host)"}
                            </div>
                        )}
                    </div>

                    <button className="btn btn-primary" style={{ backgroundColor: "#d97706", marginTop: "10px" }} onClick={saveBiomes}>
                        Save Configuration (reopen the macro to take effect!)
                    </button>
                </div>
            </div>
        </div>
    );
}
