import { useCallback, useEffect, useState } from "react";

type CustomPath = {
  id: string;
  filename: string;
  feature: string;
  label: string;
  created: string;
  event_count: number;
  speed_multiplier: number;
  recorded_nonvip?: boolean | null;
  trigger?: { enabled?: boolean; interval_min?: number; biome?: string } | null;
};

type Trigger = { enabled: boolean; interval_min: number; biome: string };

type FeatureLabels = Record<string, string>;

export default function CustomPathsPage() {
  const [paths, setPaths] = useState<CustomPath[]>([]);
  const [features, setFeatures] = useState<FeatureLabels>({});
  const [includeMouse, setIncludeMouse] = useState(false);
  const [message, setMessage] = useState("");
  const [recordingName, setRecordingName] = useState("");
  const [recordingFeature, setRecordingFeature] = useState("");
  const api = window.pywebview?.api;

  const refresh = useCallback(async () => {
    try {
      const res = await api?.list_custom_paths();
      if (res?.success) {
        setPaths(res.paths || []);
        setFeatures(res.features || {});
      }
    } catch (e) { setMessage(String(e)); }
  }, [api]);

  useEffect(() => { void refresh(); }, [refresh]);

  const assignFeature = async (pathId: string, feature: string) => {
    try {
      const res = await api?.assign_custom_path(pathId, feature);
      if (res?.success) { setMessage(`Assigned to ${features[feature] || feature}`); await refresh(); }
      else setMessage(res?.error || "Failed");
    } catch (e) { setMessage(String(e)); }
  };

  const deletePath = async (pathId: string) => {
    try {
      const res = await api?.delete_custom_path(pathId);
      if (res?.success) { setMessage("Deleted."); await refresh(); }
      else setMessage(res?.error || "Failed");
    } catch (e) { setMessage(String(e)); }
  };

  const saveRecording = async () => {
    if (!recordingName.trim()) { setMessage("Enter a name."); return; }
    try {
      const res = await api?.save_recording_as_custom_path(recordingName.trim(), recordingFeature, includeMouse);
      if (res?.success) { setMessage(`Saved as ${res.path_id}`); setRecordingName(""); setRecordingFeature(""); await refresh(); }
      else setMessage(res?.error || "Failed to save");
    } catch (e) { setMessage(String(e)); }
  };

  const featureOptions = Object.entries(features);

  // auto-trigger editing for FREE (unassigned) paths.
  const [trigEdits, setTrigEdits] = useState<Record<string, Trigger>>({});
  const trigFor = (p: CustomPath): Trigger => trigEdits[p.id] ?? {
    enabled: !!p.trigger?.enabled,
    interval_min: Number(p.trigger?.interval_min ?? 0) || 0,
    biome: String(p.trigger?.biome ?? ""),
  };
  const setTrig = (p: CustomPath, patch: Partial<Trigger>) =>
    setTrigEdits((prev) => ({ ...prev, [p.id]: { ...trigFor(p), ...patch } }));

  const saveTrigger = async (p: CustomPath) => {
    const t = trigFor(p);
    if (t.enabled && !(Number(t.interval_min) > 0) && !t.biome.trim()) {
      setMessage("Set an interval (minutes) or a biome — otherwise the trigger never fires.");
      return;
    }
    try {
      const res = await api?.custom_paths_set_trigger?.(p.id, t.enabled, Number(t.interval_min) || 0, t.biome.trim());
      if (res?.success) { setMessage("Trigger saved."); setTrigEdits((prev) => { const n = { ...prev }; delete n[p.id]; return n; }); await refresh(); }
      else setMessage(res?.error || "Failed to save the trigger");
    } catch (e) { setMessage(`Could not save the trigger: ${e}`); }
  };

  const runNow = async (p: CustomPath) => {
    try {
      const res = await api?.custom_paths_run_now?.(p.id);
      if (res?.success) setMessage("Path queued — it will run when the current action finishes.");
      else setMessage(res?.error || "Failed to queue the path");
    } catch (e) { setMessage(`Could not queue the path: ${e}`); }
  };

  const openRecorder = async () => {
    try {
      await api?.open_recorder_window_custom?.();
      setMessage("Recorder opened. Record the walk, press Stop there, then save it below.");
    } catch (e) {
      setMessage(`Could not open the recorder: ${e}`);
    }
  };

  return (
    <main style={{ padding: 24, color: "var(--text-primary)" }}>
      <h2 style={{ marginBottom: 8 }}>Custom Paths</h2>
      <p style={{ opacity: 0.7, marginBottom: 16, fontSize: 13 }}>
        Record custom walk paths and assign them to features. Custom paths take priority over default paths.
        A path saved as <b>Unassigned</b> can also run on its own trigger — every N minutes and/or when a chosen biome starts.
      </p>

      {/* How the recorder works — step-by-step */}
      <div className="card" style={{ marginBottom: 20, fontSize: 13, lineHeight: 1.7, borderRadius: "4px" }}>
        <h3 style={{ marginTop: 0, marginBottom: 8, fontSize: 14 }}>How to record a path (4 steps)</h3>
        <ol style={{ margin: 0, paddingLeft: 20 }}>
          <li>Click <b>Record new path</b> below — the Custom Path Recorder window opens.</li>
          <li>Press <b>Start</b> in the recorder, switch to Roblox and walk from the spawn point to the target (walk only — WASD/Space/E are recorded).</li>
          <li>Press <b>Stop &amp; Save</b> in the recorder. The recording stays in memory — it is not written to any default path.</li>
          <li>Return here, enter a <b>name</b>, pick the <b>feature</b> the path is for (e.g. Memory Match or Quest Board) and click <b>Save</b>.</li>
        </ol>
        <p style={{ margin: "10px 0 0", fontSize: 12.5, opacity: 0.8 }}>
          🎣 <b>Fishing Spot</b>: record the walk from the spawn point (right after the respawn sequence) to YOUR fishing spot.
          Everyone on the same server can pick a different spot so you won't get in each other's way.
          The walk to the fish seller stays built-in and is not recorded.
        </p>
        <p style={{ margin: "10px 0 0", fontSize: 12.5, opacity: 0.8 }}>
          🧪 <b>Potion Crafting Station</b>: used by Partial crafting occupancy — the macro walks to the crafting station, crafts for the scheduled duration, then resets the character (back to spawn — no return walk needed).
          Record the walk from the spawn point to the station and assign it to <b>Potion Crafting Station</b>.
        </p>
      </div>

      {/* Save recording section */}
      <div className="card" style={{ marginBottom: 24, borderRadius: "4px" }}>
        <h3 style={{ marginTop: 0, marginBottom: 12 }}>Save Current Recording as Custom Path</h3>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginBottom: 14 }}>
          <button
            className="btn btn-accent"
            onClick={() => void openRecorder()}
            style={{ padding: "8px 18px", borderRadius: "4px", fontWeight: 600, cursor: "pointer" }}
          >
            Record new path (open Recorder)
          </button>
          <label style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 13 }}>
            <input type="checkbox" checked={includeMouse} onChange={(e) => setIncludeMouse(e.target.checked)} />
            Include mouse actions
          </label>
          <span style={{ fontSize: 12, opacity: 0.7 }}>
            By default only keyboard actions are saved (walk paths). Stop the recording in the Recorder window first, then save here.
            <br />
            Paths remember whether they were recorded with Non-VIP movement mode (Movements). Playback auto-adjusts (x1.22) when the playback mode differs.
          </span>
        </div>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="text"
            className="form-input"
            placeholder="Path name (e.g. walk_to_quest_board)"
            value={recordingName}
            onChange={(e) => setRecordingName(e.target.value)}
            style={{ flex: 1, minWidth: 200, borderRadius: "4px" }}
          />
          <select
            className="form-input"
            value={recordingFeature}
            onChange={(e) => setRecordingFeature(e.target.value)}
            style={{ borderRadius: "4px" }}
          >
            <option value="">No feature (generic)</option>
            {featureOptions.map(([key, label]) => (
              <option key={key} value={key}>{label}</option>
            ))}
          </select>
          <button
            className="btn btn-primary"
            onClick={() => void saveRecording()}
            style={{ padding: "8px 18px", borderRadius: "4px", fontWeight: 600, cursor: "pointer" }}
          >
            Save Recording
          </button>
        </div>
      </div>

      {/* Existing custom paths */}
      <div className="card" style={{ borderRadius: "4px" }}>
        <h3 style={{ marginTop: 0, marginBottom: 12 }}>Saved Custom Paths ({paths.length})</h3>
        {paths.length === 0 ? (
          <p style={{ opacity: 0.5 }}>No custom paths recorded yet. Use the Recorder to capture a path, then save it above.</p>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {paths.map((p) => {
              const t = trigFor(p);
              const free = !p.feature;
              return (
                <div key={p.id} style={{
                  padding: "12px 16px",
                  background: "var(--surface-hover, rgba(255,255,255,0.04))", borderRadius: "4px",
                  border: p.feature ? "1px solid rgba(34,197,94,0.3)" : "1px solid var(--border)"
                }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600 }}>
                        {p.label}
                        {p.trigger?.enabled && <span style={{ marginLeft: 8, fontSize: 11, color: "#22c55e", border: "1px solid rgba(34,197,94,0.4)", padding: "1px 6px" }}>AUTO</span>}
                      </div>
                      <div style={{ fontSize: 12, opacity: 0.6 }}>
                        {p.event_count} events · {p.speed_multiplier}x speed
                        {p.recorded_nonvip === true && <> · <span style={{ color: "#f59e0b" }}>recorded on Non-VIP</span></>}
                        {p.recorded_nonvip === false && <> · <span style={{ color: "#22c55e" }}>recorded on VIP</span></>}
                        {p.feature && <> · Assigned to <b>{features[p.feature] || p.feature}</b></>}
                      </div>
                      {p.created && <div style={{ fontSize: 11, opacity: 0.4 }}>{new Date(p.created).toLocaleString()}</div>}
                    </div>
                    <select
                      className="form-input"
                      value={p.feature}
                      onChange={(e) => void assignFeature(p.id, e.target.value)}
                      style={{ padding: "6px 10px", borderRadius: "4px", fontSize: 13 }}
                    >
                      <option value="">Unassigned</option>
                      {featureOptions.map(([key, label]) => (
                        <option key={key} value={key}>{label}</option>
                      ))}
                    </select>
                    <button
                      className="btn"
                      onClick={() => void runNow(p)}
                      style={{ padding: "6px 12px", borderRadius: "4px", cursor: "pointer", fontSize: 13 }}
                    >
                      Run now
                    </button>
                    <button
                      className="btn"
                      onClick={() => void deletePath(p.id)}
                      style={{ padding: "6px 12px", borderRadius: "4px", border: "1px solid var(--border)", background: "transparent", color: "#f87171", cursor: "pointer", fontSize: 13 }}
                    >
                      Delete
                    </button>
                  </div>
                  {free && (
                    <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap", marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border)", fontSize: 13 }}>
                      <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
                        <input
                          type="checkbox"
                          checked={t.enabled}
                          onChange={(e) => setTrig(p, { enabled: e.target.checked })}
                        />
                        Auto-trigger
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: 6, opacity: 0.85 }}>
                        Every
                        <input
                          type="number"
                          className="form-input"
                          min={1}
                          max={720}
                          step={1}
                          value={t.interval_min || ""}
                          placeholder="min"
                          onChange={(e) => setTrig(p, { interval_min: Number(e.target.value) || 0 })}
                          style={{ width: 70, padding: "4px 8px", borderRadius: "4px" }}
                        />
                        min
                      </label>
                      <label style={{ display: "flex", alignItems: "center", gap: 6, opacity: 0.85 }}>
                        On biome
                        <input
                          type="text"
                          className="form-input"
                          value={t.biome}
                          placeholder="e.g. GLITCHED"
                          onChange={(e) => setTrig(p, { biome: e.target.value.toUpperCase() })}
                          style={{ width: 150, padding: "4px 8px", borderRadius: "4px" }}
                        />
                      </label>
                      <button
                        className="btn btn-primary"
                        onClick={() => void saveTrigger(p)}
                        style={{ padding: "5px 14px", borderRadius: "4px", fontWeight: 600, cursor: "pointer", fontSize: 12.5 }}
                      >
                        Save trigger
                      </button>
                      <span style={{ fontSize: 11.5, opacity: 0.55 }}>
                        Runs on its own while the macro is running — waits until fishing, potion, Eden, obby etc. are idle.
                      </span>
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>

      {message && (
        <div style={{ marginTop: 16, padding: "8px 12px", borderRadius: "4px", background: "rgba(59,130,246,0.1)", color: "#60a5fa", fontSize: 13 }}>
          {message}
        </div>
      )}
    </main>
  );
}
