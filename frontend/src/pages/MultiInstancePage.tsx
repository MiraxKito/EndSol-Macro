import { useCallback, useEffect, useState } from "react";
import { useConfig } from "../contexts/ConfigContext";
import { useT } from "../i18n";
import ToggleSwitch from "../components/ToggleSwitch";
import "./MultiInstancePage.css";

type RobloxWindow = { hwnd: number; pid: number; title: string; rect?: number[]; visible: boolean };
type InstanceInfo = {
  pid: number;
  title: string;
  username?: string | null;
  main?: boolean;
  log_mapped?: boolean;
  exe?: string | null;
  biome?: string | null;
  aura?: string | null;
  last_event?: string | null;
};
type MultiState = {
  enabled: boolean;
  provider: string;
  windows: RobloxWindow[];
  window_count: number;
  main_pid?: number | null;
  last_action?: { status?: string; reason?: string; pid?: number; at?: number } | null;
  statistics_enabled: boolean;
  capabilities: Record<string, boolean>;
  warning?: string;
  alerts_enabled?: boolean;
  instances?: InstanceInfo[];
};
type LauncherAccount = { username: string; userid: string; added_at?: string; own_server?: boolean };
type LauncherState = {
  accounts?: LauncherAccount[];
  mutex_held?: boolean;
  mutex_note?: string;
  cookie_lock_held?: boolean;
  cookie_lock_note?: string;
  login_active?: boolean;
  login_status?: string;
  login_username?: string;
  last_error?: string;
  last_launched?: string;
  running_accounts?: string[];
};

const initial: MultiState = { enabled: false, provider: "EndSol built-in", windows: [], window_count: 0, statistics_enabled: true, capabilities: {} };

export default function MultiInstancePage() {
  const { config, saveConfig } = useConfig();
  const t = useT();
  const [state, setState] = useState<MultiState>(initial);
  const [launcher, setLauncher] = useState<LauncherState>({});
  const [message, setMessage] = useState("");
  // v41: a Launch click disables THAT account's button immediately; it stays
  // disabled until the poll reports the account as running (button turns
  // into an accent "Running") or for at most 60 s (click lost / launch
  // refused -> the button becomes clickable again).
  const [launchingAt, setLaunchingAt] = useState<Record<string, number>>({});
  const api = window.pywebview?.api;
  const refresh = useCallback(async () => {
    try { if (api?.get_multi_instance_state) setState(await api.get_multi_instance_state() as MultiState); }
    catch (error) { setMessage(String(error)); }
    try { if (api?.launcher_get_state) setLauncher(await api.launcher_get_state() as LauncherState); }
    catch { /* launcher state is best-effort */ }
  }, [api]);
  useEffect(() => { void refresh(); const timer = window.setInterval(() => void refresh(), 2000); return () => window.clearInterval(timer); }, [refresh]);
  const toggle = async (enabled: boolean) => {
    try {
      if (!api?.set_multi_instance_enabled) { setMessage(t("API bridge is not ready yet — wait a second and try again.")); return; }
      const result = await api.set_multi_instance_enabled(enabled);
      if (!result?.success) { setMessage(result?.error || t("Failed to toggle mode.")); return; }
      setState((prev) => ({ ...prev, enabled }));
      if (config) await saveConfig({ ...config, multiple_instances_enabled: enabled });
      setMessage(enabled ? t("Mode enabled. The full detector runs on the main window; secondary windows get Anti-AFK and alerts while the macro is active.") : t("Mode disabled. Normal single-window macro is available again."));
      await refresh();
    } catch (error) {
      setMessage(t("Toggle failed") + ": " + String(error));
    }
  };
  const setMain = async (pid: number) => {
    try {
      if (!api?.set_multi_instance_main) { setMessage(t("API bridge is not ready yet — wait a second and try again.")); return; }
      const result = await api.set_multi_instance_main(pid);
      if (!result?.success) { setMessage(result?.error || t("Failed to set the main window.")); return; }
      if (config) await saveConfig({ ...config, multi_instance_main_pid: pid });
      setMessage(pid ? t("Main window set to PID") + " " + pid + "." : t("Main window set to automatic."));
      await refresh();
    } catch (error) {
      setMessage(t("Failed to set the main window") + ": " + String(error));
    }
  };
  const startLogin = async () => {
    try {
      const res = await api?.launcher_start_login?.();
      if (!res?.success) setMessage(res?.error || t("Could not start the login capture."));
      else await refresh();
    } catch (error) { setMessage(String(error)); }
  };
  const cancelLogin = async () => {
    try { await api?.launcher_cancel_login?.(); await refresh(); } catch (error) { setMessage(String(error)); }
  };
  const launchAccount = async (username: string) => {
    setLaunchingAt((prev) => ({ ...prev, [username]: Date.now() }));
    try {
      const res = await api?.launcher_launch_account?.(username);
      if (!res?.success) {
        setMessage(res?.error || t("Launch failed."));
        setLaunchingAt((prev) => { const next = { ...prev }; delete next[username]; return next; });
      } else {
        setMessage(t("Launched") + " @" + username + ". " + t("The client logs into its own account automatically."));
      }
      await refresh();
    } catch (error) {
      setMessage(String(error));
      setLaunchingAt((prev) => { const next = { ...prev }; delete next[username]; return next; });
    }
  };
  const removeAccount = async (username: string) => {
    try {
      const res = await api?.launcher_remove_account?.(username);
      if (!res?.success) setMessage(res?.error || t("Failed to remove the account."));
      await refresh();
    } catch (error) { setMessage(String(error)); }
  };
  const setOwnServer = async (username: string, enabled: boolean) => {
    try {
      const res = await api?.launcher_set_own_server?.(username, enabled);
      if (!res?.success) setMessage(res?.error || t("Failed to update the account."));
      await refresh();
    } catch (error) { setMessage(String(error)); }
  };
  const time = state.last_action?.at ? new Date(state.last_action.at * 1000).toLocaleTimeString() : "—";
  // Re-render every second while a launch is pending so the 60 s timeout
  // re-enables the button on time.
  useEffect(() => {
    if (Object.keys(launchingAt).length === 0) return;
    const timer = window.setInterval(() => setLaunchingAt((prev) => ({ ...prev })), 1000);
    return () => window.clearInterval(timer);
  }, [launchingAt]);
  const updateConfig = (key: string, value: unknown) => {
    if (config) void saveConfig({ ...config, [key]: value });
  };
  const instanceFor = (pid: number) => state.instances?.find((i) => i.pid === pid);
  const accounts = launcher.accounts || [];
  const runningAccounts = new Set(launcher.running_accounts || []);  return <main className="multi-page">
    <div className="page-header">
      <h2>{t("Multiple-Instances")}</h2>
      <p>{t("Launch and monitor every Roblox window directly from the panel — no external tool needed.")}</p>
    </div>
    <div className="card">
      <div className="card-header">
        <div className="card-icon">🪟</div>
        <div>
          <h3>{t("Mode")}</h3>
          <p>{t("Runs the full detector on the selected main window; secondary windows get ordered Anti-AFK and log-based alerts.")}</p>
        </div>
        <div className={`multi-status ${state.enabled ? "is-on" : "is-off"}`}><span className="status-dot" />{state.enabled ? t("Enabled") : t("Disabled")}</div>
      </div>
      <ToggleSwitch label={t("Enable Multiple-Instances")} description={t("While it is on, EndSol holds the Roblox singleton watcher and the shared cookie lock so several clients can run.")} checked={state.enabled} onChange={toggle} />
      <p className="muted">{t("Locks")}: {launcher.mutex_held ? "✓ " + t("Roblox singleton lock active") : (launcher.mutex_note || "—")} · {launcher.cookie_lock_held ? "✓ " + t("cookie file locked") : (launcher.cookie_lock_note || "—")}</p>
      {message && <p className="form-hint" style={{ color: "#fca5a5", margin: "6px 0 0" }}>{message}</p>}
    </div>
    <div className="multi-notice"><strong>{t("Important")}</strong><span>{state.warning || t("Accounts are stored only on this PC, encrypted with Windows DPAPI. EndSol never sends your session tokens anywhere.")}</span></div>
    <div className="multi-grid">
      <div className="card">
        <div className="card-header">
          <div className="card-icon">👥</div>
          <div>
            <h3>{t("Accounts")}</h3>
            <p>{t("Launch a Roblox window signed into a stored account. Each client keeps its own session.")}</p>
          </div>
        </div>
        {accounts.length ? <div className="window-list">{accounts.map((acc) => { const isRunning = runningAccounts.has(acc.username); const launchTs = launchingAt[acc.username]; const isLaunching = !!launchTs && Date.now() - launchTs < 60000 && !isRunning; const busy = isRunning || isLaunching; return <div className="window-row" key={acc.username}><span className="window-order">@</span><div><b>{acc.username}</b><small>{acc.added_at ? t("Added") + " " + acc.added_at : ""}{isRunning ? " · " + t("running") : ""}</small></div><div className="account-actions"><label className="own-server-toggle" title={t("Launch this account into its own private server instead of the Webhook link")}><input type="checkbox" checked={!!acc.own_server} onChange={(e) => void setOwnServer(acc.username, e.target.checked)} />{t("Own Server")}</label><button className={"btn" + (isRunning ? " btn-accent" : "")} disabled={busy} title={isRunning ? t("This account already has a running client") : undefined} onClick={() => void launchAccount(acc.username)}>{isRunning ? t("Running") : t("Launch")}</button><button className="account-remove" onClick={() => void removeAccount(acc.username)} title={t("Remove the stored session")}>✕</button></div></div>; })}</div> : <div className="empty-state">{t("No accounts stored yet — add one below.")}</div>}
        <div className="alert-config-row" style={{ alignItems: "center" }}>
          {launcher.login_active
            ? <><span className="form-hint" style={{ margin: 0 }}>{launcher.login_status || t("Waiting for login…")}</span><button className="btn btn-secondary" onClick={() => void cancelLogin()}>{t("Cancel")}</button></>
            : <button className="btn" onClick={() => void startLogin()}>{t("Add account")}</button>}
        </div>
        {launcher.login_status && !launcher.login_active && <p className="form-hint">{launcher.login_status}</p>}
        <p className="muted">{t("Launches join the private server link from the Webhook page. Without it the client opens at the home screen.")}</p>
        {launcher.last_launched && <p className="form-hint">{t("Last launch")}: {launcher.last_launched}</p>}
      </div>
      <div className="card">
        <div className="card-header">
          <div className="card-icon">🔍</div>
          <div>
            <h3>{t("Roblox Windows")}</h3>
            <p>{t("Main window")}</p>
          </div>
        </div>
        <div className="alert-config-row"><label><span>{t("Main window")}</span><select value={Number(config?.multi_instance_main_pid ?? 0)} onChange={(e) => void setMain(Number(e.target.value))}>
          <option value={0}>{t("Auto (window of the configured account)")}</option>
          {state.windows.map((item) => { const inst = instanceFor(item.pid); const uname = inst?.username; return <option key={item.pid} value={item.pid}>{(item.title || "Roblox") + " — PID " + item.pid + (uname ? " (" + uname + ")" : "")}</option>; })}
        </select></label>
        <p className="muted">{t("All full macro features run on the main window.")}{state.main_pid ? " " + t("Resolved main window") + ": PID " + state.main_pid : ""}</p></div>
        {state.windows.length ? <div className="window-list">{state.windows.map((item, index) => { const inst = instanceFor(item.pid); const uname = inst?.username; const exe = inst?.exe || ""; const unusualExe = exe && !/^robloxplayerbeta(\.exe)?$/i.test(exe) && !/^windows10universal(\.exe)?$/i.test(exe); return <div className="window-row" key={item.hwnd}><span className="window-order">{index + 1}</span><div><b>{item.title || "Roblox"}</b><small>PID {item.pid}{uname ? " · " + uname : ""}{inst?.main ? " · " + t("main instance") : ""}{unusualExe ? " · " + exe : ""}</small>{(() => { const inst2 = instanceFor(item.pid); if (!inst2 || inst2.main || (!inst2.biome && !inst2.aura && !inst2.last_event)) return null; return <small className="window-events">{inst2.biome ? <>Biome: <b>{inst2.biome}</b></> : null}{inst2.aura ? <> · Aura: <b>{inst2.aura}</b></> : null}{inst2.last_event ? <> · {inst2.last_event}</> : null}</small>; })()}</div><span className="window-live">{t("LIVE")}</span></div>; })}</div> : <div className="empty-state">{t("No Roblox windows detected. Launch an instance above or start Roblox manually.")}</div>}
      </div>
    </div>
    <div className="card">
      <div className="card-header">
        <div className="card-icon">🧩</div>
        <div>
          <h3>{t("How the mode works")}</h3>
          <p>{t("Anti-AFK on secondary windows waits for a free window of the main cycle — no bite, no sale, no scheduled action.")}</p>
        </div>
      </div>
      <div className="policy allowed">✓ {t("Full detector, fishing and all actions — on the main window")}</div>
      <div className="policy allowed">✓ {t("Ordered Anti-AFK on secondary windows — one at a time")}</div>
      <div className="policy allowed">✓ {t("Biome, aura and disconnect alerts from every secondary window")}</div>
    </div>
    <div className="card">
      <div className="card-header">
        <div className="card-icon">📨</div>
        <div>
          <h3>{t("Dedicated Discord webhook")}</h3>
          <p>{t("A separate webhook for multi-instance status: when the mode is running and how many windows it tracks (start, windows opened/closed, stop). Leave empty to reuse your main webhook list.")}</p>
        </div>
      </div>
      <div className="alert-config-row"><label><span>{t("Webhook URL")}</span><input type="text" placeholder="https://discord.com/api/webhooks/..." value={config?.multi_instance_webhook_url ?? ""} onChange={(e) => updateConfig("multi_instance_webhook_url", e.target.value)} /></label></div>
    </div>
    <div className="card">
      <div className="card-header">
        <div className="card-icon">⏱️</div>
        <div>
          <h3>{t("Jump timing")}</h3>
          <p>{t("Wait after focusing a secondary window and after each jump. Raise both on weak hardware / low FPS so jumps are not dropped.")}</p>
        </div>
      </div>
      <div className="alert-config-row"><label><span>{t("Focus wait (seconds)")}</span><input type="number" min={0.2} max={5} step={0.1} value={Number(config?.multi_instance_jump_focus_wait ?? 1.0)} onChange={(e) => updateConfig("multi_instance_jump_focus_wait", Math.min(5, Math.max(0.2, Number(e.target.value) || 1.0)))} /></label><label><span>{t("Jump settle wait (seconds)")}</span><input type="number" min={0.2} max={5} step={0.1} value={Number(config?.multi_instance_jump_settle_wait ?? 1.0)} onChange={(e) => updateConfig("multi_instance_jump_settle_wait", Math.min(5, Math.max(0.2, Number(e.target.value) || 1.0)))} /></label></div>
    </div>
    <div className="card">
      <div className="card-header">
        <div className="card-icon">🔔</div>
        <div>
          <h3>{t("Alerts from other windows")}</h3>
          <p>{t("Reads every window's own Roblox log and sends biome, aura and disconnect alerts to your webhooks. The main instance is covered by the main detector.")}</p>
        </div>
      </div>
      <ToggleSwitch label={t("Instance alerts")} description={t("Rare biomes + auras above the rarity threshold + disconnects, per window.")} checked={!!config?.multi_instance_alerts} onChange={(value) => updateConfig("multi_instance_alerts", value)} />{config?.multi_instance_alerts && <><div className="alert-config-row"><label><span>{t("Aura rarity threshold")}</span><input type="number" min={0} step={1000} value={Number(config?.multi_instance_aura_min_rarity ?? 100000)} onChange={(e) => updateConfig("multi_instance_aura_min_rarity", Number(e.target.value) || 0)} /></label><label className="inline-toggle"><input type="checkbox" checked={config?.multi_instance_alert_rare_biomes_only !== false} onChange={(e) => updateConfig("multi_instance_alert_rare_biomes_only", e.target.checked)} />{t("Rare biomes only")}</label></div><p className="muted">{t("Alerts use your normal Discord webhook list. Threshold 0 = every aura roll.")}</p></>}
      <ToggleSwitch label={t("Auto rejoin secondary accounts")} description={t("When a secondary window disconnects, relaunch the same account automatically. Turn it off to use those accounts yourself.")} checked={config?.multi_instance_rejoin_enabled !== false} onChange={(value) => updateConfig("multi_instance_rejoin_enabled", value)} />
    </div>
    <div className="card">
      <div className="card-header">
        <div className="card-icon">🧾</div>
        <div>
          <h3>Queue Status</h3>
          <p>{t("Secondary windows are processed in launch order. If one is closed or can't be focused, it's skipped and the rest continue.")}</p>
        </div>
      </div>
      <p className="runtime-line">Last action: <b>{state.last_action?.status || "none yet"}</b> · reason: {state.last_action?.reason || "—"} · time: {time}</p>
    </div>
    <div className="multi-message">{message}</div>
  </main>;
}
