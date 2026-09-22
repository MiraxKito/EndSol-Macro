import { useCallback, useEffect, useState } from "react";
import { useConfig } from "../contexts/ConfigContext";
import { useT } from "../i18n";
import ToggleSwitch from "../components/ToggleSwitch";
import "./MultiInstancePage.css";

type RobloxWindow = { hwnd: number; pid: number; title: string; rect?: number[]; visible: boolean };
type MultiState = {
  enabled: boolean;
  provider: string;
  windows: RobloxWindow[];
  window_count: number;
  last_action?: { status?: string; reason?: string; pid?: number; at?: number } | null;
  statistics_enabled: boolean;
  capabilities: Record<string, boolean>;
  warning?: string;
};

const initial: MultiState = { enabled: false, provider: "Avaluate/MultipleRobloxInstances", windows: [], window_count: 0, statistics_enabled: true, capabilities: {} };

export default function MultiInstancePage() {
  const { config, saveConfig } = useConfig();
  const t = useT();
  const [state, setState] = useState<MultiState>(initial);
  const [message, setMessage] = useState("");
  const api = window.pywebview?.api;
  const refresh = useCallback(async () => {
    try { if (api?.get_multi_instance_state) setState(await api.get_multi_instance_state() as MultiState); }
    catch (error) { setMessage(String(error)); }
  }, [api]);
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 2000); return () => window.clearInterval(timer); }, [refresh]);
  const toggle = async (enabled: boolean) => {
    if (!api?.set_multi_instance_enabled) return;
    const result = await api.set_multi_instance_enabled(enabled);
    if (!result?.success) { setMessage(result?.error || "Failed to toggle mode."); return; }
    if (config) await saveConfig({ ...config, multiple_instances_enabled: enabled });
    setMessage(enabled ? "Mode enabled. Open your Roblox windows via Avaluate, then start the macro - the monitor runs while it is active." : "Mode disabled. Normal macro is available again.");
    await refresh();
  };
  const time = state.last_action?.at ? new Date(state.last_action.at * 1000).toLocaleTimeString() : "—";
  return <main className="multi-page">
    <header className="multi-hero"><div><div className="eyebrow">{t("EXTERNAL WINDOW MONITOR")}</div><h2>{t("Multiple-Instances")}</h2><p>{t("Support for windows launched via Avaluate MultipleRobloxInstances.")}</p></div><div className={`multi-status ${state.enabled ? "is-on" : "is-off"}`}><span className="status-dot" />{state.enabled ? t("Enabled") : t("Disabled")}<small>{state.window_count} {t("Roblox windows")}</small></div></header>
    <section className="multi-notice"><strong>{t("Important")}</strong><span>{state.warning || "EndSol never opens Roblox or touches your accounts - you launch them via Avaluate MultipleRobloxInstances, EndSol just keeps every window active."}</span></section>
    <section className="multi-card setup-card"><div className="section-kicker">{t("SUPPORTED WORKFLOW")}</div><h3>{t("How to launch multiple accounts")}</h3><ol className="steps"><li><b>Launch Avaluate MultipleRobloxInstances</b><span>Use the official build and log into your accounts as usual.</span></li><li><b>Open Roblox windows manually</b><span>Wait for the first window to fully load, then open the next ones.</span></li><li><b>Enable the mode and start the macro</b><span>EndSol detects the windows and sends Anti-AFK to one window at a time in order. The monitor only runs while the macro is active.</span></li></ol><ToggleSwitch label="Enable Multiple-Instances" description="Stops the normal detector and statistics; keeps only observation and ordered Anti-AFK." checked={state.enabled} onChange={toggle} /></section>
    <section className="multi-grid"><div className="multi-card"><div className="section-kicker">{t("DETECTED WINDOWS")}</div><h3>{t("Roblox Windows")}</h3>{state.windows.length ? <div className="window-list">{state.windows.map((item, index) => <div className="window-row" key={item.hwnd}><span className="window-order">{index + 1}</span><div><b>{item.title || "Roblox"}</b><small>PID {item.pid}</small></div><span className="window-live">{t("LIVE")}</span></div>)}</div> : <div className="empty-state">{t("No windows found. Open Roblox via Avaluate and click refresh.")}</div>}</div><div className="multi-card"><div className="section-kicker">{t("RUNTIME POLICY")}</div><h3>{t("Mode Restrictions")}</h3><div className="policy allowed">✓ {t("Ordered Anti-AFK — one window at a time")}</div><div className="policy blocked">× {t("Statistics and recording — disabled")}</div><div className="policy blocked">× Mouse, OCR, pathing, fishing, merchant, potion crafting</div><div className="policy blocked">× Main instance and pause/resume cycle</div><p className="muted">One window at a time keeps focus and input safe - the macro itself stays in the main window.</p></div></section>
    <section className="multi-card diagnostics"><div className="section-kicker">LAST ACTION</div><h3>Queue Status</h3><p className="runtime-line">Last action: <b>{state.last_action?.status || "none yet"}</b> · reason: {state.last_action?.reason || "—"} · time: {time}</p><p className="muted">Windows are processed in launch order. If one is closed or can't be focused, it's skipped and the rest continue.</p></section>
    {message && <div className="multi-message">{message}</div>}
  </main>;
}
