import { useConfig } from "../contexts/ConfigContext";
import { useState, useEffect, useCallback } from "react";

type ThemeData = {
  theme_name?: string;
  variables?: Record<string, string>;
  custom_css?: string;
  raw_custom_css?: string;
  raw_font_url?: string;
  font_weight?: string;
  font_style?: string;
  custom_labels?: Record<string, string>;
  custom_icons?: Record<string, string>;
  custom_macro_title?: string;
  custom_macro_version?: string;
  bg_type?: "solid" | "gradient" | "image";
  custom_bg_url?: string;
  grad1?: string;
  grad2?: string;
  grad3?: string;
};

const DEFAULT_THEME: ThemeData = {
  theme_name: "Custom Theme",
  variables: {
    "--accent": "#7c5bf5",
    "--accent-dim": "#6344d4",
    "--accent-glow": "rgba(124, 91, 245, 0.15)",
    "--accent-text": "#b8a4fa",
    "--bg-root": "#09090b",
    "--bg-sidebar": "#0f0f14",
    "--bg-main": "#0d0d11",
    "--bg-card": "#15151e",
    "--bg-card-hover": "#1a1a28",
    "--bg-input": "#111119",
    "--bg-input-focus": "#18182a",
    "--success": "#22c55e",
    "--success-dim": "#16a34a",
    "--danger": "#ef4444",
    "--danger-dim": "#dc2626",
    "--warning": "#f59e0b",
    "--text-primary": "#e4e4e7",
    "--text-secondary": "#a1a1aa",
    "--text-muted": "#636370",
    "--border": "#1f1f2e",
    "--border-hover": "#2d2d44",
    "--border-accent": "rgba(124, 91, 245, 0.3)",
    "--radius-sm": "0px",
    "--radius-md": "0px",
    "--radius-lg": "0px",
    "--radius-xl": "0px",
    "--shadow-card": "0 2px 12px rgba(0, 0, 0, 0.3)",
    "--shadow-glow": "0 0 20px rgba(124, 91, 245, 0.08)",
    "--corner-color": "rgba(124, 91, 245, 1)",
    "--ambient-glow": "rgba(124, 91, 245, 0.17)",
    "--sidebar-border-width": "1px",
    "--custom-bg-img": "none",
    "--bg-size": "cover",
    "--bg-animation": "none",
  },
  custom_css: "",
  raw_custom_css: "",
  raw_font_url: "",
  font_weight: "normal",
  font_style: "normal",
  custom_labels: {},
  custom_icons: {},
  custom_macro_title: "EndSol Macro",
  custom_macro_version: "v1.0.6",
  bg_type: "solid",
  custom_bg_url: "",
  grad1: "#7c5bf5",
  grad2: "#6344d4",
  grad3: "#a78bfa",
};

const TABS_LIST = [
  "notice", "webhook", "calibrations", "remoteaccess", "misc",
  "fishing", "merchant", "autopopbuff", "auras", "movements",
  "custompaths", "potioncraft", "stats", "status", "otherfeatures",
  "multiinstances", "customization", "panelcustomization", "solbook",
  "instructions", "credits", "donations"
];

const TAB_DISPLAY_NAMES: Record<string, string> = {
  notice: "Notice",
  webhook: "Webhook",
  calibrations: "Macro Calibrations",
  remoteaccess: "Remote Access",
  misc: "Automated Actions",
  fishing: "Fishing",
  merchant: "Merchant",
  autopopbuff: "Auto Pop Buff",
  auras: "Auras",
  movements: "Movements",
  custompaths: "Custom Paths",
  potioncraft: "Potion Crafting",
  stats: "Stats",
  status: "Status",
  otherfeatures: "Other Features",
  multiinstances: "Multi Instances",
  customization: "Discord Webhook Customization",
  panelcustomization: "Panel Customization",
  solbook: "Sol's Book",
  instructions: "Instructions",
  credits: "Credits",
  donations: "Donations <3",
};

// Friendly names/descriptions for every CSS variable so users don't have to
// guess what "--accent-dim" means. The raw key stays visible in small text.
const COLOR_META: Record<string, { label: string; hint?: string }> = {
  "--accent": { label: "Accent (main)", hint: "Buttons, active tabs, highlights" },
  "--accent-dim": { label: "Accent (pressed / darker)", hint: "Hover & pressed states of accent elements" },
  "--accent-glow": { label: "Accent glow (soft)", hint: "Soft transparent glow, e.g. rgba(124,91,245,0.15)" },
  "--accent-text": { label: "Accent text", hint: "Text tinted with the accent color" },
  "--bg-root": { label: "Main background", hint: "Base color behind everything" },
  "--bg-sidebar": { label: "Sidebar background" },
  "--bg-main": { label: "Content area background" },
  "--bg-card": { label: "Card / panel background" },
  "--bg-card-hover": { label: "Card background (hover)" },
  "--bg-input": { label: "Input field background" },
  "--bg-input-focus": { label: "Input field background (focused)" },
  "--success": { label: "Success / online", hint: "Running indicators, success buttons" },
  "--success-dim": { label: "Success (darker)" },
  "--danger": { label: "Danger / errors" },
  "--danger-dim": { label: "Danger (darker)" },
  "--warning": { label: "Warning color" },
  "--text-primary": { label: "Primary text", hint: "Main readable text" },
  "--text-secondary": { label: "Secondary text", hint: "Descriptions and less important text" },
  "--text-muted": { label: "Muted text", hint: "Least visible text (hints, labels)" },
  "--border": { label: "Borders" },
  "--border-hover": { label: "Borders (hover)" },
  "--border-accent": { label: "Accent border (soft)", hint: "Highlighted borders, e.g. rgba(...,0.3)" },
  "--radius-sm": { label: "Corner radius: small", hint: "Inputs, small buttons (0px = sharp)" },
  "--radius-md": { label: "Corner radius: medium", hint: "Cards and panels" },
  "--radius-lg": { label: "Corner radius: large" },
  "--radius-xl": { label: "Corner radius: extra large", hint: "Popups and windows" },
  "--shadow-card": { label: "Card shadow" },
  "--shadow-glow": { label: "Accent glow shadow" },
  "--corner-color": { label: "Corner accent color", hint: "Decorative corner brackets" },
  "--sidebar-border-width": { label: "Sidebar border width" },
  "--custom-bg-img": { label: "Background image (advanced)", hint: "CSS value, e.g. url(...) — prefer the Background tab" },
  "--bg-size": { label: "Background image size (advanced)", hint: "CSS background-size, e.g. cover" },
  "--bg-animation": { label: "Background animation (advanced)", hint: "CSS animation value" },
};

const sections = [
  { id: "colors", label: "Colors", icon: "🎨" },
  { id: "tabs", label: "Tabs", icon: "🏷️" },
  { id: "background", label: "Background", icon: "🖼️" },
  { id: "fonts", label: "Fonts", icon: "🔤" },
  { id: "advanced", label: "Advanced", icon: "⚙️" },
];

// Logical groups with human-readable names (order = display order).
const colorGroups: { label: string; keys: string[] }[] = [
  { label: "Accent & highlights", keys: ["--accent", "--accent-dim", "--accent-glow", "--border-accent", "--corner-color", "--shadow-glow"] },
  { label: "Backgrounds", keys: ["--bg-root", "--bg-sidebar", "--bg-main", "--bg-card", "--bg-card-hover", "--bg-input", "--bg-input-focus"] },
  { label: "Text", keys: ["--text-primary", "--text-secondary", "--text-muted", "--accent-text"] },
  { label: "Status colors", keys: ["--success", "--success-dim", "--danger", "--danger-dim", "--warning"] },
  { label: "Borders & shadows", keys: ["--border", "--border-hover", "--shadow-card", "--sidebar-border-width"] },
  { label: "Corner radius (0px = sharp, 12px+ = rounded)", keys: ["--radius-sm", "--radius-md", "--radius-lg", "--radius-xl"] },
  { label: "Advanced (background image)", keys: ["--custom-bg-img", "--bg-size", "--bg-animation"] },
];

export default function PanelCustomizationPage() {
  const { config, setConfig } = useConfig();
  const [theme, setTheme] = useState<ThemeData>(DEFAULT_THEME);
  const [activeSection, setActiveSection] = useState<string>("colors");
  const [message, setMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  // Load theme on mount
  useEffect(() => {
    const loadTheme = async () => {
      try {
        if (window.pywebview?.api?.export_theme) {
          const result = await window.pywebview.api.export_theme();
          const parsed = JSON.parse(result);
          if (parsed && !parsed.error) {
            setTheme({ ...DEFAULT_THEME, ...parsed });
          }
        }
      } catch (e) {
        console.warn("Failed to load theme:", e);
      }
    };
    loadTheme();
  }, []);

  const showMessage = (type: "success" | "error", text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 4000);
  };

  const resetToDefaults = () => {
    setTheme({ ...DEFAULT_THEME, variables: { ...DEFAULT_THEME.variables }, custom_labels: {}, custom_icons: {} });
    showMessage("success", "Theme reset to defaults. Save it to keep the change.");
  };

  const updateVariable = (key: string, value: string) => {
    setTheme(prev => ({
      ...prev,
      variables: { ...prev.variables, [key]: value }
    }));
  };

  const updateThemeField = <K extends keyof ThemeData>(field: K, value: ThemeData[K]) => {
    setTheme(prev => ({ ...prev, [field]: value }));
  };

  const updateLabel = (tab: string, value: string) => {
    setTheme(prev => ({
      ...prev,
      custom_labels: { ...prev.custom_labels, [tab]: value }
    }));
  };

  const updateIcon = (tab: string, value: string) => {
    setTheme(prev => ({
      ...prev,
      custom_icons: { ...prev.custom_icons, [tab]: value }
    }));
  };

  const applyThemeLive = useCallback(() => {
    const root = document.documentElement;
    const body = document.body;
    Object.entries(theme.variables || {}).forEach(([key, value]) => {
      if (value) {
        root.style.setProperty(key, value);
        body.style.setProperty(key, value);
      }
    });
    const styleId = "endsol-custom-theme-live-css";
    document.getElementById(styleId)?.remove();
    const css = [theme.custom_css, theme.raw_custom_css].filter(Boolean).join("\n");
    if (css) {
      const style = document.createElement("style");
      style.id = styleId;
      style.textContent = css;
      document.head.appendChild(style);
    }
  }, [theme.variables, theme.custom_css, theme.raw_custom_css]);

  // Live preview
  useEffect(() => {
    applyThemeLive();
  }, [applyThemeLive]);

  const saveTheme = async () => {
    try {
      if (!window.pywebview?.api?.save_theme_file) {
        showMessage("error", "Local theme storage API not available");
        return;
      }
      const json = JSON.stringify(theme, null, 2);
      const result = await window.pywebview.api.save_theme_file(json);
      const parsed = typeof result === "string" ? JSON.parse(result) : result;
      if (parsed.success) {
        if (config) setConfig({ ...config, custom_theme_data: theme });
        showMessage("success", "Theme saved and applied! Changes will persist after restart.");
      } else {
        showMessage("error", parsed.error || "Failed to save theme");
      }
    } catch (e: any) {
      showMessage("error", e?.message || "Failed to save theme");
    }
  };

  const exportTheme = async () => {
    try {
      if (!window.pywebview?.api?.save_theme_file) {
        showMessage("error", "Local theme storage API not available");
        return;
      }
      const result = await window.pywebview.api.save_theme_file(JSON.stringify(theme, null, 2));
      if (result.success) {
        showMessage("success", `Theme exported to the local EndSolMacro folder.`);
      } else {
        showMessage("error", result.error || "Failed to export theme");
      }
    } catch (e: any) {
      showMessage("error", e?.message || "Failed to export theme");
    }
  };

  const importThemeFromLocalFolder = async () => {
    try {
      if (!window.pywebview?.api?.import_theme_file) {
        showMessage("error", "Local theme import API not available");
        return;
      }
      const result = await window.pywebview.api.import_theme_file();
      if (result.success && result.theme) {
        setTheme({ ...DEFAULT_THEME, ...result.theme });
        showMessage("success", "Theme imported from the local EndSolMacro folder.");
      } else if (result.error && result.error !== "No theme selected") {
        showMessage("error", result.error);
      }
    } catch (e: any) {
      showMessage("error", e?.message || "Failed to import theme");
    }
  };

  return (
    <div style={{ minHeight: "100%", padding: "0 4px 24px" }}>
      <div className="page-header">
        <h2>Panel Customization</h2>
        <p>Customize the macro panel appearance, colors, tabs, and fonts</p>
      </div>

      {message && (
        <div style={{
          position: "fixed", top: "80px", right: "24px", zIndex: 1000,
          padding: "12px 20px", borderRadius: "6px", fontSize: "13px", fontWeight: 500,
          background: message.type === "success" ? "rgba(34, 197, 94, 0.9)" : "rgba(239, 68, 68, 0.9)",
          color: "#fff", boxShadow: "0 4px 20px rgba(0,0,0,0.4)", animation: "slideIn 0.3s ease"
        }}>
          {message.text}
        </div>
      )}

      <div style={{ margin: "0 24px 16px", padding: "14px 18px", border: "1px solid var(--border-accent)", borderRadius: "10px", background: "linear-gradient(135deg, var(--accent-glow), rgba(255,255,255,0.02))", display: "flex", alignItems: "center", gap: "12px" }}>
        <div style={{ fontSize: "24px" }}>✨</div>
        <div><strong style={{ color: "var(--accent-text)" }}>Design Studio</strong><div style={{ color: "var(--text-secondary)", fontSize: "12px", marginTop: "3px" }}>Changes preview instantly. Save the theme when your panel looks right; Reset restores the safe defaults.</div></div>
      </div>

      <div style={{ display: "flex", gap: "24px", height: "calc(100% - 170px)", padding: "0 24px 24px" }}>
        {/* Sidebar */}
        <div className="card" style={{ width: "250px", minWidth: "250px", maxHeight: "100%", overflowY: "auto", boxShadow: "0 12px 30px rgba(0,0,0,0.22)" }}>
          <div className="card-header">
            <div className="card-icon">🎨</div>
            <div><h3>Sections</h3></div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "4px", padding: "8px" }}>
            {sections.map(s => (
              <button
                key={s.id}
                onClick={() => setActiveSection(s.id)}
                style={{
                  display: "flex", alignItems: "center", gap: "10px", padding: "10px 12px",
                  border: "none", background: activeSection === s.id ? "var(--accent-glow)" : "transparent",
                  color: activeSection === s.id ? "var(--accent-text)" : "var(--text-secondary)",
                  borderRadius: "8px", cursor: "pointer", fontSize: "13px", fontWeight: 600, borderLeft: activeSection === s.id ? "3px solid var(--accent)" : "3px solid transparent",
                  textAlign: "left", width: "100%", transition: "all 0.15s ease"
                }}
              >
                <span>{s.icon}</span> {s.label}
              </button>
            ))}
          </div>
          <div style={{ padding: "16px", borderTop: "1px solid var(--border)" }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              <button className="btn btn-accent" onClick={saveTheme} style={{ width: "100%", justifyContent: "center" }}>
                💾 Save Theme
              </button>
              <button className="btn btn-secondary" onClick={exportTheme} style={{ width: "100%", justifyContent: "center" }}>
                📤 Export Theme
              </button>
              <button className="btn btn-secondary" onClick={importThemeFromLocalFolder} style={{ width: "100%", justifyContent: "center" }}>
                📥 Import Theme from Local Folder
              </button>
              <button className="btn" onClick={resetToDefaults} style={{ width: "100%", justifyContent: "center", background: "rgba(239,68,68,0.1)", color: "#ef4444", borderColor: "rgba(239,68,68,0.3)" }}>
                ↩️ Reset to Defaults
              </button>
            </div>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, minWidth: 0, display: "flex", flexDirection: "column", gap: "16px" }}>

          {/* Colors Section */}
          {activeSection === "colors" && (
            <div className="card" style={{ flex: 1, overflowY: "auto" }}>
              <div className="card-header">
                <div className="card-icon">🎨</div>
                <div><h3>Color Variables</h3><p>Everything the panel looks like — grouped and with plain names. Hover a name for details; the raw CSS key stays in small text.</p></div>
              </div>
              <div style={{ display: "grid", gap: "16px", padding: "8px" }}>
                {colorGroups.map(group => (
                  <div key={group.label} style={{ background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: "8px", padding: "16px" }}>
                    <h4 style={{ margin: "0 0 12px", fontSize: "12px", fontWeight: 600, color: "var(--text-secondary)", textTransform: "uppercase", letterSpacing: "0.5px" }}>{group.label}</h4>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(230px, 1fr))", gap: "12px" }}>
                      {group.keys.filter(key => theme.variables && key in theme.variables).map(key => {
                        const value = String(theme.variables?.[key] ?? "");
                        const isColor = value.startsWith("#") || value.startsWith("rgba") || value.startsWith("rgb");
                        const meta = COLOR_META[key] || { label: key };
                        return (
                          <div key={key} style={{ display: "flex", flexDirection: "column", gap: "6px" }} title={meta.hint || ""}>
                            <label style={{ fontSize: "12px", color: "var(--text-secondary)", fontWeight: 600 }}>
                              {meta.label}
                              {meta.hint && <span style={{ display: "block", fontSize: "10px", fontWeight: 400, color: "var(--text-muted)" }}>{meta.hint}</span>}
                            </label>
                            <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                              {isColor && (
                                <>
                                <input
                                  type="color"
                                  value={value || "#000000"}
                                  onChange={(e) => updateVariable(key, e.target.value)}
                                  style={{ width: "36px", height: "36px", border: "none", borderRadius: "6px", cursor: "pointer", padding: 0 }}
                                />
                                </>
                            )}
                              <input
                                type="text"
                                className="form-input"
                                value={value}
                                onChange={(e) => updateVariable(key, e.target.value)}
                                style={{ flex: 1, fontFamily: "monospace", fontSize: "12px" }}
                                placeholder={key}
                              />
                            </div>
                            <span style={{ fontSize: "10px", color: "var(--text-muted)", fontFamily: "monospace", opacity: 0.7 }}>{key}</span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Tabs Section */}
          {activeSection === "tabs" && (
            <div className="card" style={{ flex: 1, overflowY: "auto" }}>
              <div className="card-header">
                <div className="card-icon">🏷️</div>
                <div><h3>Tab Labels & Icons</h3><p>Customize sidebar tab names and emoji icons</p></div>
              </div>
              <div style={{ display: "grid", gap: "8px", padding: "8px" }}>
                {TABS_LIST.map(tab => (
                  <div key={tab} style={{ display: "grid", gridTemplateColumns: "36px 1fr 1fr 80px", gap: "10px", alignItems: "center", padding: "10px 12px", background: "rgba(255,255,255,0.02)", border: "1px solid var(--border)", borderRadius: "6px" }}>
                    <span style={{ fontSize: "18px" }}>{theme.custom_icons?.[tab] || "📄"}</span>
                    <input
                      type="text"
                      className="form-input"
                      value={theme.custom_labels?.[tab] || TAB_DISPLAY_NAMES[tab] || tab}
                      onChange={(e) => updateLabel(tab, e.target.value)}
                      placeholder={TAB_DISPLAY_NAMES[tab] || tab}
                      style={{ fontSize: "13px" }}
                    />
                    <input
                      type="text"
                      className="form-input"
                      value={theme.custom_icons?.[tab] || ""}
                      onChange={(e) => updateIcon(tab, e.target.value)}
                      placeholder="Emoji icon"
                      style={{ width: "100%", fontSize: "18px", textAlign: "center" }}
                      maxLength={2}
                    />
                    <span style={{ fontSize: "11px", color: "var(--text-muted)", fontFamily: "monospace" }}>{tab}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Background Section */}
          {activeSection === "background" && (
            <div className="card" style={{ flex: 1, overflowY: "auto" }}>
              <div className="card-header">
                <div className="card-icon">🖼️</div>
                <div><h3>Background</h3><p>Panel background style: solid, gradient, or image</p></div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px" }}>
                <div>
                  <label className="form-label">Background Type</label>
                  <select className="form-input" value={theme.bg_type} onChange={(e) => updateThemeField("bg_type", e.target.value as any)} style={{ width: "200px" }}>
                    <option value="solid">Solid Color</option>
                    <option value="gradient">Gradient</option>
                    <option value="image">Image URL</option>
                  </select>
                </div>

                {theme.bg_type === "solid" && (
                  <div>
                    <label className="form-label">Solid Color (uses --bg-root)</label>
                    <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
                      <input type="color" value={theme.variables?.["--bg-root"] || "#09090b"} onChange={(e) => updateVariable("--bg-root", e.target.value)} style={{ width: "50px", height: "50px", border: "none", borderRadius: "6px", cursor: "pointer" }} />
                      <input type="text" className="form-input" value={theme.variables?.["--bg-root"] || "#09090b"} onChange={(e) => updateVariable("--bg-root", e.target.value)} style={{ flex: 1, fontFamily: "monospace" }} />
                    </div>
                  </div>
                )}

                {theme.bg_type === "gradient" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "12px" }}>
                      {["grad1", "grad2", "grad3"].map((g, i) => (
                        <div key={g} style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                          <label className="form-label">Gradient Color {i + 1}</label>
                          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                            <input type="color" value={theme[g as keyof ThemeData] as string || "#000000"} onChange={(e) => updateThemeField(g as keyof ThemeData, e.target.value)} style={{ width: "50px", height: "50px", border: "none", borderRadius: "6px", cursor: "pointer" }} />
                            <input type="text" className="form-input" value={theme[g as keyof ThemeData] as string || ""} onChange={(e) => updateThemeField(g as keyof ThemeData, e.target.value)} style={{ flex: 1, fontFamily: "monospace" }} />
                          </div>
                        </div>
                      ))}
                    </div>
                    <div style={{ height: "60px", borderRadius: "8px", background: `linear-gradient(135deg, ${theme.grad1}, ${theme.grad2}, ${theme.grad3})`, border: "1px solid var(--border)" }} />
                  </div>
                )}

                {theme.bg_type === "image" && (
                  <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    <div>
                      <label className="form-label">Background Image URL</label>
                      <input type="text" className="form-input" value={theme.custom_bg_url || ""} onChange={(e) => updateThemeField("custom_bg_url", e.target.value)} placeholder="https://..." style={{ width: "100%" }} />
                    </div>
                    <div>
                      <label className="form-label">Background Size</label>
                      <select className="form-input" value={theme.variables?.["--bg-size"] || "cover"} onChange={(e) => updateVariable("--bg-size", e.target.value)} style={{ width: "200px" }}>
                        <option value="cover">Cover</option>
                        <option value="contain">Contain</option>
                        <option value="auto">Auto</option>
                        <option value="100% 100%">Stretch</option>
                      </select>
                    </div>
                    <div>
                      <label className="form-label">Background Animation</label>
                      <select className="form-input" value={theme.variables?.["--bg-animation"] || "none"} onChange={(e) => updateVariable("--bg-animation", e.target.value)} style={{ width: "200px" }}>
                        <option value="none">None</option>
                        <option value="float">Float</option>
                        <option value="pulse">Pulse</option>
                        <option value="slide">Slide</option>
                      </select>
                    </div>
                    {theme.custom_bg_url && (
                      <div style={{ height: "120px", borderRadius: "8px", background: `url(${theme.custom_bg_url}) center/cover`, border: "1px solid var(--border)" }} />
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Fonts & Title Section */}
          {activeSection === "fonts" && (
            <div className="card" style={{ flex: 1, overflowY: "auto" }}>
              <div className="card-header">
                <div className="card-icon">🔤</div>
                <div><h3>Fonts & Window Title</h3><p>Custom font, weight, style, and macro title/version</p></div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px" }}>
                <div>
                  <label className="form-label">Custom Font URL (Google Fonts, etc.)</label>
                  <input type="text" className="form-input" value={theme.raw_font_url || ""} onChange={(e) => updateThemeField("raw_font_url", e.target.value)} placeholder="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" style={{ width: "100%" }} />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div>
                    <label className="form-label">Font Weight</label>
                    <select className="form-input" value={theme.font_weight || "normal"} onChange={(e) => updateThemeField("font_weight", e.target.value)}>
                      <option value="normal">Normal (400)</option>
                      <option value="medium">Medium (500)</option>
                      <option value="600">Semi-bold (600)</option>
                      <option value="bold">Bold (700)</option>
                      <option value="800">Extra-bold (800)</option>
                      <option value="900">Black (900)</option>
                    </select>
                  </div>
                  <div>
                    <label className="form-label">Font Style</label>
                    <select className="form-input" value={theme.font_style || "normal"} onChange={(e) => updateThemeField("font_style", e.target.value)}>
                      <option value="normal">Normal</option>
                      <option value="italic">Italic</option>
                    </select>
                  </div>
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div>
                    <label className="form-label">Window Title</label>
                    <input type="text" className="form-input" value={theme.custom_macro_title || "EndSol Macro"} onChange={(e) => updateThemeField("custom_macro_title", e.target.value)} placeholder="EndSol Macro" />
                  </div>
                  <div>
                    <label className="form-label">Window Version Text</label>
                    <input type="text" className="form-input" value={theme.custom_macro_version || "v1.0.3"} onChange={(e) => updateThemeField("custom_macro_version", e.target.value)} placeholder="v1.0.3" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Advanced Section */}
          {activeSection === "advanced" && (
            <div className="card" style={{ flex: 1, overflowY: "auto" }}>
              <div className="card-header">
                <div className="card-icon">⚙️</div>
                <div><h3>Advanced</h3><p>Custom CSS injection and theme metadata</p></div>
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "16px", padding: "16px" }}>
                <div>
                  <label className="form-label" style={{ display: "flex", justifyContent: "space-between" }}>
                    Custom CSS
                    <span style={{ fontSize: "11px", color: "var(--text-muted)" }}>Injected into panel</span>
                  </label>
                  <textarea
                    className="form-input"
                    value={theme.custom_css || ""}
                    onChange={(e) => updateThemeField("custom_css", e.target.value)}
                    placeholder="/* Custom CSS here */\n.sidebar-item { border-radius: 8px; }"
                    style={{ width: "100%", minHeight: "150px", fontFamily: "monospace", fontSize: "12px", resize: "vertical" }}
                  />
                </div>
                <div>
                  <label className="form-label">Raw Custom CSS (alternative field)</label>
                  <textarea
                    className="form-input"
                    value={theme.raw_custom_css || ""}
                    onChange={(e) => updateThemeField("raw_custom_css", e.target.value)}
                    placeholder="Alternative CSS field"
                    style={{ width: "100%", minHeight: "80px", fontFamily: "monospace", fontSize: "12px", resize: "vertical" }}
                  />
                </div>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                  <div>
                    <label className="form-label">Theme Name</label>
                    <input type="text" className="form-input" value={theme.theme_name || "Custom Theme"} onChange={(e) => updateThemeField("theme_name", e.target.value)} placeholder="My Custom Theme" />
                  </div>
                  <div>
                    <label className="form-label">Theme Version</label>
                    <input type="text" className="form-input" value={theme.custom_macro_version || "v1.0.3"} onChange={(e) => updateThemeField("custom_macro_version", e.target.value)} placeholder="v1.0.0" />
                  </div>
                </div>
              </div>
            </div>
          )}

        </div>
      </div>

      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  );
}