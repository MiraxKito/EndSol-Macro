import { useEffect, useState } from "react";
import ToggleSwitch from "../components/ToggleSwitch";
import { useConfig } from "../contexts/ConfigContext";

// Mirrors QUEST_TYPES in biome_tracker/mixin_quest_board.py
// NOTE: "Player Hunt" is intentionally absent — the macro always dismisses it
// (killing players can't be automated).
const QUEST_TYPE_LABELS: Record<string, string> = {
  meditation: "Meditation I/II",
  basic_hunt: "Basic Hunt",
  epic_hunt: "Epic Hunt",
  unique_hunt: "Unique Hunt",
  legendary_hunt: "Legendary Hunt",
  mythic_hunt: "Mythic Hunt",
  breakthrough: "Breakthrough (any biome)",
  fishing: "Fishing (Catch X / Angler…)",
  delivery: "Delivery I-V",
  resonance: "Resonance of X (grail offering)",
};

const QUEST_TYPE_DEFAULTS: Record<string, "accept" | "dismiss"> = {
  meditation: "accept",
  basic_hunt: "accept",
  epic_hunt: "accept",
  unique_hunt: "accept",
  legendary_hunt: "accept",
  mythic_hunt: "accept",
  breakthrough: "accept",
  fishing: "dismiss",
  delivery: "dismiss",
  resonance: "dismiss",
};

// Hunt quests complete themselves through normal rolling — no tier picker.
// Tier/variant lists per quest type (mirrors _quest_variant_options in
// biome_tracker/mixin_quest_board.py).
const QUEST_VARIANTS: Record<string, string[]> = {
  delivery: ["I", "II", "III", "IV", "V"],
  meditation: ["I", "II"],
  resonance: ["Wind", "Frost", "Sea", "Sand", "Flame", "Star", "Corruption", "Darkness"],
  breakthrough: ["Windy", "Snowy", "Rainy", "Sandstorm", "Hell", "Starfall", "Corruption", "Null"],
  fishing: ["River Angler", "Minnow Rookie", "Deep-Sea Hunter", "Legendary Fisher"],
};

// Not implemented yet — hidden from the panel until their automations ship.
// The macro keeps dismissing these quests (QUEST_TYPE_DEFAULTS stay "dismiss",
// and the backend forces that too). Delivery keeps its I–V tier picker in the
// config so it comes back ready when the feature lands.
const HIDDEN_QUEST_TYPES = new Set(["fishing", "delivery", "resonance"]);

export default function MiscPage() {
  const { config, saveConfig, error } = useConfig();
  const [calibrationTarget, setCalibrationTarget] = useState<
    "ocr" | "reconnect" | "eden_contract" | null
  >(null);
  const [ocrStatus, setOcrStatus] = useState<{
    installed: boolean;
    version: string | null;
  } | null>(null);
  const [dailyBusy, setDailyBusy] = useState(false);
  const [dailyMsg, setDailyMsg] = useState("");
  const [dailyOk, setDailyOk] = useState(false);
  useEffect(() => {
    (window as any).onCalibrationResultMisc = (data: any) => {
      if (!calibrationTarget || !config) return;

      let nextValue: number[] | null = null;
      if (calibrationTarget === "ocr") {
        if (
          Array.isArray(data?.value) &&
          data?.key === "first_item_slot_ocr_pos"
        ) {
          const candidate = data.value
            .slice(0, 4)
            .map((value: any) => Math.round(Number(value)));
          if (
            candidate.length === 4 &&
            candidate.every((value: number) => Number.isFinite(value)) &&
            candidate[2] > 0 &&
            candidate[3] > 0
          ) {
            nextValue = candidate;
          }
        } else if (data?.w !== undefined) {
          const candidate = [
            Math.round(Number(data.x)),
            Math.round(Number(data.y)),
            Math.round(Number(data.w)),
            Math.round(Number(data.h)),
          ];
          if (
            candidate.every((value) => Number.isFinite(value)) &&
            candidate[2] > 0 &&
            candidate[3] > 0
          ) {
            nextValue = candidate;
          }
        }
      } else if (
        calibrationTarget === "reconnect" ||
        calibrationTarget === "eden_contract"
      ) {
        const targetKey =
          calibrationTarget === "reconnect"
            ? "reconnect_start_button"
            : "eden_contract_button";
        if (Array.isArray(data?.value) && data?.key === targetKey) {
          const candidate = data.value
            .slice(0, 2)
            .map((value: any) => Math.round(Number(value)));
          if (
            candidate.length === 2 &&
            candidate.every((value: number) => Number.isFinite(value))
          ) {
            nextValue = candidate;
          }
        } else if (
          data?.x !== undefined &&
          data?.y !== undefined &&
          data?.w === undefined &&
          data?.h === undefined
        ) {
          const candidate = [
            Math.round(Number(data.x)),
            Math.round(Number(data.y)),
          ];
          if (candidate.every((value) => Number.isFinite(value))) {
            nextValue = candidate;
          }
        }
      }

      if (!nextValue) return;

      if (calibrationTarget === "ocr") {
        saveConfig({ ...config, first_item_slot_ocr_pos: nextValue });
      } else if (calibrationTarget === "reconnect") {
        saveConfig({ ...config, reconnect_start_button: nextValue });
      } else if (calibrationTarget === "eden_contract") {
        saveConfig({ ...config, eden_contract_button: nextValue });
      }

      setCalibrationTarget(null);
    };

    return () => {
      delete (window as any).onCalibrationResultMisc;
    };
  }, [calibrationTarget, config, saveConfig]);

  useEffect(() => {
    let alive = true;
    let retryTimer: number | undefined;
    const checkOcr = async () => {
      if (!window.pywebview?.api?.check_winocr_status) {
        retryTimer = window.setTimeout(checkOcr, 150);
        return;
      }
      try {
        const result = await Promise.race([
          window.pywebview.api.check_winocr_status(),
          new Promise<{
            installed: boolean;
            version: string | null;
            error?: string;
          }>((resolve) =>
            window.setTimeout(
              () =>
                resolve({
                  installed: false,
                  version: null,
                  error: "WinOCR check timed out",
                }),
              3000,
            ),
          ),
        ]);
        if (alive)
          setOcrStatus({
            installed: result?.installed === true,
            version: result?.version ?? null,
          });
      } catch {
        if (alive) setOcrStatus({ installed: false, version: null });
      }
    };
    void checkOcr();
    return () => {
      alive = false;
      if (retryTimer) window.clearTimeout(retryTimer);
    };
  }, []);

  if (error) {
    return (
      <div style={{ padding: "20px", color: "#ef4444" }}>
        <h3>Error Loading Settings</h3>
        <p>{error}</p>
      </div>
    );
  }

  if (!config) {
    return <div style={{ padding: "20px" }}>Loading settings...</div>;
  }

  const updateConfig = (key: string, value: any) => {
    saveConfig({ ...config, [key]: value });
  };

  const runDailyTest = async () => {
    if (!window.pywebview?.api?.collect_daily_event_now) {
      setDailyOk(false);
      setDailyMsg("API bridge is not ready yet.");
      return;
    }
    setDailyBusy(true);
    setDailyMsg("");
    try {
      const res: any = await window.pywebview.api.collect_daily_event_now();
      setDailyOk(!!res?.success);
      setDailyMsg(
        res?.message ||
          res?.reason ||
          (res?.success ? "Daily Rewards claimed." : "Claim failed."),
      );
      if (res?.claimed_date !== undefined) {
        saveConfig({ ...config, daily_event_claimed_date: res.claimed_date });
      }
    } catch (e: any) {
      setDailyOk(false);
      setDailyMsg(String(e));
    } finally {
      setDailyBusy(false);
    }
  };

  const resetDailyClaim = async () => {
    if (!window.pywebview?.api?.reset_daily_event_claim) return;
    setDailyBusy(true);
    setDailyMsg("");
    try {
      const res: any = await window.pywebview.api.reset_daily_event_claim();
      setDailyOk(true);
      setDailyMsg(res?.message || "Claim date reset.");
      saveConfig({ ...config, daily_event_claimed_date: "" });
    } catch (e: any) {
      setDailyOk(false);
      setDailyMsg(String(e));
    } finally {
      setDailyBusy(false);
    }
  };

  const startOCRCalibration = async () => {
    setCalibrationTarget("ocr");
    try {
      if (window.pywebview?.api) {
        await window.pywebview.api.create_calibration_window(
          "first_item_slot_ocr_pos",
          "region",
        );
      }
    } catch (errorValue) {
      console.error("Failed to open calibration window", errorValue);
      alert("Failed to open calibration tool: " + errorValue);
      setCalibrationTarget(null);
    }
  };

  const startReconnectCalibration = async () => {
    setCalibrationTarget("reconnect");
    try {
      if (window.pywebview?.api) {
        await window.pywebview.api.create_calibration_window(
          "reconnect_start_button",
          "point",
        );
      }
    } catch (errorValue) {
      console.error("Failed to open calibration window", errorValue);
      alert("Failed to open calibration tool: " + errorValue);
      setCalibrationTarget(null);
    }
  };

  const startEdenContractCalibration = async () => {
    setCalibrationTarget("eden_contract");
    try {
      if (window.pywebview?.api) {
        await window.pywebview.api.create_calibration_window(
          "eden_contract_button",
          "point",
        );
      }
    } catch (errorValue) {
      console.error("Failed to open calibration window", errorValue);
      alert("Failed to open calibration tool: " + errorValue);
      setCalibrationTarget(null);
    }
  };

  return (
    <>
      <div className="page-header">
        <h2>Automated Actions</h2>
        <p>General automation, recovery, screenshot, and quest settings</p>
      </div>

      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          padding: "8px 14px",
          borderRadius: "var(--radius-md)",
          background: ocrStatus?.installed
            ? "rgba(34, 197, 94, 0.1)"
            : "rgba(239, 68, 68, 0.1)",
          border: `1px solid ${ocrStatus?.installed ? "rgba(34, 197, 94, 0.3)" : "rgba(239, 68, 68, 0.3)"}`,
          marginBottom: "16px",
          fontSize: "12px",
        }}
      >
        <span
          style={{
            width: "8px",
            height: "8px",
            borderRadius: "50%",
            background:
              ocrStatus === null
                ? "var(--text-muted)"
                : ocrStatus.installed
                  ? "#22c55e"
                  : "#ef4444",
            flexShrink: 0,
          }}
        />
        <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>
          WinOCR Status:
        </span>
        <span
          style={{
            color:
              ocrStatus === null
                ? "var(--text-muted)"
                : ocrStatus.installed
                  ? "#22c55e"
                  : "#ef4444",
            fontWeight: 600,
          }}
        >
          {ocrStatus === null
            ? "Checking..."
            : ocrStatus.installed
              ? "Installed"
              : "Not Installed"}
        </span>
        {ocrStatus?.installed &&
          ocrStatus.version &&
          ocrStatus.version !== "unknown" && (
            <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>
              (v{ocrStatus.version})
            </span>
          )}
        {ocrStatus && !ocrStatus.installed && (
          <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>
            — OCR failsafe will not work (if WinOCR haven't installed, ask macro
            helper to assist you about this!)
          </span>
        )}
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-icon">📦</div>
          <div>
            <h3>Item Usage</h3>
            <p>Configure BR, SC, reconnect, and OCR safeguards</p>
          </div>
        </div>

        <ToggleSwitch
          label="OCR failsafe"
          description="Prevent wrong item usage by validating the first inventory slot before clicking Use"
          checked={config.enable_ocr_failsafe || false}
          onChange={(value) => updateConfig("enable_ocr_failsafe", value)}
        />
        {config.enable_ocr_failsafe && (
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "10px",
              marginTop: "6px",
              marginBottom: "14px",
            }}
          >
            <button
              className="btn btn-accent"
              style={{ fontSize: "11px", padding: "6px 12px" }}
              onClick={startOCRCalibration}
            >
              OCR Calibration
            </button>
            <span className="form-hint">
              {JSON.stringify(
                config.first_item_slot_ocr_pos || [797, 410, 98, 97],
              )}
            </span>
          </div>
        )}

        <ToggleSwitch
          label="Biome Randomizer (BR)"
          checked={config.biome_randomizer || false}
          onChange={(value) => updateConfig("biome_randomizer", value)}
        />
        {config.biome_randomizer && (
          <div className="duration-input" style={{ marginBottom: "6px" }}>
            <label className="form-label">Usage Duration (minutes):</label>
            <input
              className="form-input"
              value={config.br_duration || "36"}
              onChange={(event) =>
                updateConfig("br_duration", event.target.value)
              }
              style={{ width: "70px" }}
            />
          </div>
        )}

        <ToggleSwitch
          label="Strange Controller (SC)"
          checked={config.strange_controller || false}
          onChange={(value) => updateConfig("strange_controller", value)}
        />
        {config.strange_controller && (
          <div className="duration-input" style={{ marginBottom: "6px" }}>
            <label className="form-label">Usage Duration (minutes):</label>
            <input
              className="form-input"
              value={config.sc_duration || "21"}
              onChange={(event) =>
                updateConfig("sc_duration", event.target.value)
              }
              style={{ width: "70px" }}
            />
          </div>
        )}

        {(config.biome_randomizer || config.strange_controller) && (
          <div
            style={{
              marginTop: "12px",
              marginBottom: "16px",
              padding: "10px",
              background: "rgba(0,0,0,0.25)",
              borderRadius: "6px",
              border: "1px solid rgba(255,255,255,0.03)",
            }}
          >
            <label
              style={{
                marginBottom: "8px",
                display: "block",
                fontFamily: '"Sarpanch", sans-serif',
                textTransform: "uppercase",
                fontSize: "11px",
                letterSpacing: "0.05em",
                color: "var(--text-secondary)",
              }}
            >
              Do NOT use BR/SC during these biomes:
            </label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
              {[
                "WINDY",
                "RAINY",
                "SNOWY",
                "SAND STORM",
                "HELL",
                "STARFALL",
                "CORRUPTION",
                "NULL",
                "AURORA",
                "HEAVEN",
                "EGGLAND",
                "SINGULARITY",
                "BLAZING SUN",
                "PUMPKIN MOON",
                "GRAVEYARD",
                "BLOOD RAIN",
                "THE HYPERSPACE REALM",
                "\u8d64\u3044\u6e80\u6708",
                "THE NULL'S EXISTENCE",
                "THE CITADEL OF ORDERS",
              ].map((biome) => {
                const isSelected = (
                  config.disabled_biomes_br_sc || []
                ).includes(biome);
                const biomeColors: Record<string, string> = {
                  WINDY: "#F2F6FF",
                  RAINY: "#027cbd",
                  SNOWY: "#Dceff9",
                  "SAND STORM": "#8F7057",
                  HELL: "#ff4719",
                  STARFALL: "#011ab7",
                  CORRUPTION: "#6d32a8",
                  NULL: "#838383",
                  AURORA: "#0047ab",
                  HEAVEN: "#FFE8A0",
                  EGGLAND: "#d4fc8d",
                  SINGULARITY: "#cf4023",
                  "BLAZING SUN": "#FF6B00",
                  "PUMPKIN MOON": "#FF6600",
                  GRAVEYARD: "#4A4A4A",
                  "BLOOD RAIN": "#CC0000",
                  "THE HYPERSPACE REALM": "#9b59b6",
                  "\u8d64\u3044\u6e80\u6708": "#cc0000",
                  "THE NULL'S EXISTENCE": "#1a1a2e",
                  "THE CITADEL OF ORDERS": "#c0a030",
                };
                const color = biomeColors[biome] || "#ffffff";
                const r = parseInt(color.slice(1, 3), 16),
                  g = parseInt(color.slice(3, 5), 16),
                  b = parseInt(color.slice(5, 7), 16);

                return (
                  <button
                    key={biome}
                    onClick={() => {
                      const current = config.disabled_biomes_br_sc || [];
                      updateConfig(
                        "disabled_biomes_br_sc",
                        isSelected
                          ? current.filter((b: string) => b !== biome)
                          : [...current, biome],
                      );
                    }}
                    style={{
                      padding: "3px 6px",
                      fontFamily: '"Sarpanch", sans-serif',
                      fontSize: "11px",
                      fontWeight: 600,
                      letterSpacing: "0.03em",
                      borderRadius: "3px",
                      border: `1px solid ${isSelected ? color : `rgba(${r},${g},${b},0.15)`}`,
                      background: isSelected
                        ? `rgba(${r},${g},${b},0.15)`
                        : "rgba(0,0,0,0.3)",
                      color: isSelected ? color : `rgba(${r},${g},${b},0.5)`,
                      cursor: "pointer",
                      transition: "all 0.15s ease-in-out",
                      textTransform: "uppercase",
                    }}
                    onMouseEnter={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.borderColor = `rgba(${r},${g},${b},0.4)`;
                        e.currentTarget.style.color = `rgba(${r},${g},${b},0.8)`;
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!isSelected) {
                        e.currentTarget.style.borderColor = `rgba(${r},${g},${b},0.15)`;
                        e.currentTarget.style.color = `rgba(${r},${g},${b},0.5)`;
                      }
                    }}
                  >
                    {biome}
                  </button>
                );
              })}
            </div>
            <span
              style={{
                color: "rgba(255,255,255,0.25)",
                fontSize: "10px",
                display: "block",
                marginTop: "8px",
                fontFamily: '"Sarpanch", sans-serif',
                letterSpacing: "0.02em",
              }}
            >
              Note: GLITCHED, DREAMSPACE, CYBERSPACE are always blocked when
              using br/sc :aga:
            </span>
          </div>
        )}

        <ToggleSwitch
          label="Auto reconnect to your PS (experimental)"
          description="When Roblox disconnects, relaunch and rejoin using your private server link."
          checked={config.auto_reconnect || false}
          onChange={(value) => updateConfig("auto_reconnect", value)}
        />
        {config.auto_reconnect && (
          <>
            <div
              className="form-hint"
              style={{ marginTop: "6px", marginBottom: "8px" }}
            >
              Supports both private server code links and Roblox share links
              (for example: /share?code=...&type=Server).
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "10px",
                marginBottom: "8px",
              }}
            >
              <button
                className="btn btn-accent"
                style={{ fontSize: "11px", padding: "6px 12px" }}
                onClick={startReconnectCalibration}
              >
                Join Button in Sol&apos;s RNG Calibration
              </button>
              <span className="form-hint">
                {JSON.stringify(config.reconnect_start_button || [954, 876])}
              </span>
            </div>
          </>
        )}

        <div
          className="form-group"
          style={{
            marginTop: "10px",
            borderTop: "1px solid rgba(255,255,255,0.1)",
            paddingTop: "10px",
          }}
        >
          <label className="form-label">
            Inventory Mouse Click Delay (milliseconds)
          </label>
          <div className="duration-input">
            <input
              className="form-input"
              value={config.inventory_click_delay ?? "0"}
              onChange={(event) =>
                updateConfig("inventory_click_delay", event.target.value)
              }
              style={{ width: "90px" }}
            />
          </div>
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-icon">⚡</div>
          <div>
            <h3>Limbo Item Usage &amp; Eden Detection</h3>
            <p>Configure Eden detection and Limbo teleportation</p>
          </div>
        </div>

        <ToggleSwitch
          label="Teleport to Limbo using Portable Crack"
          checked={config.teleport_portable_crack || false}
          onChange={(value) => updateConfig("teleport_portable_crack", value)}
        />

        {config.teleport_portable_crack && (
          <div style={{ marginTop: "4px" }}>
            <span
              style={{
                color: "var(--text-muted)",
                fontSize: "11px",
                display: "inline-block",
              }}
            >
              Only works if fishing mode, potion crafting, auto obby, auto egg
              pathing is OFF!
            </span>
            <div className="duration-input" style={{ marginTop: "10px" }}>
              <label className="form-label">Usage Interval (minutes):</label>
              <input
                type="number"
                min="1"
                className="form-input"
                value={config.portable_crack_interval || "3"}
                onChange={(event) =>
                  updateConfig("portable_crack_interval", event.target.value)
                }
                onBlur={(event) => {
                  const val = parseInt(event.target.value);
                  if (isNaN(val) || val < 1) {
                    updateConfig("portable_crack_interval", "3");
                  }
                }}
                style={{ width: "70px" }}
              />
            </div>
          </div>
        )}

        <div
          style={{
            marginTop: "14px",
            borderTop: "1px solid rgba(255,255,255,0.1)",
            paddingTop: "14px",
          }}
        >
          <ToggleSwitch
            label="Go to Eden's spawn (experimental)"
            checked={config.go_to_eden_spawn || false}
            onChange={(value) => updateConfig("go_to_eden_spawn", value)}
          />

          {config.go_to_eden_spawn && (
            <div
              style={{
                marginTop: "4px",
                marginBottom: "16px",
                marginLeft: "14px",
                paddingLeft: "14px",
              }}
            >
              <div className="duration-input" style={{ marginBottom: "12px" }}>
                <label className="form-label">
                  Pathing Interval (minutes):
                </label>
                <input
                  type="number"
                  min="1"
                  className="form-input"
                  value={config.eden_path_interval || "35"}
                  onChange={(event) =>
                    updateConfig("eden_path_interval", event.target.value)
                  }
                  style={{ width: "70px" }}
                />
              </div>
            </div>
          )}

          <ToggleSwitch
            label="Auto Eden's contract"
            checked={config.auto_eden_contract || false}
            onChange={(value) => updateConfig("auto_eden_contract", value)}
          />

          {config.auto_eden_contract && (
            <div
              style={{
                marginTop: "4px",
                marginBottom: "16px",
                marginLeft: "14px",
                paddingLeft: "14px",
              }}
            >
              <div className="duration-input" style={{ marginBottom: "12px" }}>
                <label className="form-label">
                  Contract Interval (minutes):
                </label>
                <input
                  type="number"
                  min="1"
                  className="form-input"
                  value={config.eden_contract_interval || "10"}
                  onChange={(event) =>
                    updateConfig("eden_contract_interval", event.target.value)
                  }
                  style={{ width: "70px" }}
                />
              </div>
              <div
                style={{ display: "flex", alignItems: "center", gap: "10px" }}
              >
                <button
                  className="btn btn-accent"
                  style={{ fontSize: "11px", padding: "6px 12px" }}
                  onClick={startEdenContractCalibration}
                >
                  Eden Contract button (calibration)
                </button>
                <span className="form-hint">
                  {JSON.stringify(config.eden_contract_button || [0, 0])}
                </span>
              </div>
            </div>
          )}
        </div>

        <div
          style={{
            marginTop: "14px",
            borderTop: "1px solid rgba(255,255,255,0.1)",
            paddingTop: "14px",
          }}
        >
          <ToggleSwitch
            label="Eden detection using OCR (detect on roblox chat)"
            checked={config.eden_detection || false}
            onChange={(value) => updateConfig("eden_detection", value)}
          />

          {config.eden_detection && (
            <div style={{ marginTop: "8px" }}>
              <div
                className="info-banner"
                style={{
                  background: "rgba(124, 91, 245, 0.1)",
                  border: "1px solid var(--accent)",
                  marginBottom: "12px",
                }}
              >
                <strong>Reminder:</strong> This only detect eden and ping you if
                it found on roblox chat so u gotta get the eden aura by yourself
                <br />
                <span
                  style={{
                    color: "var(--text-muted)",
                    fontSize: "11px",
                    display: "inline-block",
                    marginTop: "4px",
                  }}
                >
                  Only works if fishing, potion crafting, auto obby, auto egg
                  pathing is OFF!
                </span>
                <br />
                <span
                  style={{
                    color: "var(--text-muted)",
                    fontSize: "11px",
                    display: "inline-block",
                    marginTop: "4px",
                  }}
                >
                  Make sure you do the chat, chat OCR tab, chat close, and chat
                  OCR box region calibration in Movements Calibration tab!
                </span>
              </div>

              <div className="duration-input" style={{ marginBottom: "16px" }}>
                <label className="form-label">
                  Checking Interval (minutes):
                </label>
                <input
                  type="number"
                  min="1"
                  className="form-input"
                  value={config.eden_check_interval || "5"}
                  onChange={(event) =>
                    updateConfig("eden_check_interval", event.target.value)
                  }
                  onBlur={(event) => {
                    const val = parseInt(event.target.value);
                    if (isNaN(val) || val < 1) {
                      updateConfig("eden_check_interval", "1");
                    }
                  }}
                  style={{ width: "70px" }}
                />
              </div>

              <div
                style={{
                  background: "rgba(0,0,0,0.2)",
                  padding: "12px",
                  borderRadius: "8px",
                  border: "1px solid rgba(255,255,255,0.05)",
                }}
              >
                <ToggleSwitch
                  label="Ping if Eden found?"
                  description="Custom Ping UserID/RoleID"
                  checked={config.ping_eden || false}
                  onChange={(val) => updateConfig("ping_eden", val)}
                />
                {config.ping_eden && (
                  <div className="form-group" style={{ marginTop: "12px" }}>
                    <label className="form-label">UserID / RoleID</label>
                    <input
                      className="form-input"
                      value={config.eden_user_id || ""}
                      onChange={(e) =>
                        updateConfig("eden_user_id", e.target.value)
                      }
                      placeholder="123456789012345678"
                      style={{ width: "240px" }}
                    />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-icon">🎬</div>
          <div>
            <h3>Biome Recording</h3>
            <p>Auto clip and screenshot rare biome detections</p>
          </div>
        </div>

        <ToggleSwitch
          label="Glitched/Dreamspace/Cyberspace Biome clip keybind"
          description="Require 1 of 2 recorders: Medal, Xbox Gaming Bar"
          checked={config.record_rare_biome || false}
          onChange={(value) => updateConfig("record_rare_biome", value)}
        />

        {config.record_rare_biome && (
          <div className="form-row" style={{ marginTop: "10px" }}>
            <div className="form-group">
              <label className="form-label">Record Keybind</label>
              <div
                style={{ display: "flex", gap: "8px", alignItems: "center" }}
              >
                <input
                  className="form-input"
                  value={config.rare_biome_record_keybind || "F8"}
                  onChange={(event) =>
                    updateConfig(
                      "rare_biome_record_keybind",
                      event.target.value,
                    )
                  }
                  style={{ width: "100px" }}
                />
                <button
                  className="btn btn-accent"
                  onClick={() => {
                    if ((window as any).pywebview) {
                      (window as any).pywebview.api.test_biome_keybind();
                    }
                  }}
                  style={{ padding: "8px 16px", whiteSpace: "nowrap" }}
                >
                  Test Keybind
                </button>
                <small
                  style={{
                    color: "var(--text-muted)",
                    fontSize: "11px",
                    whiteSpace: "nowrap",
                  }}
                >
                  (Fires after 2s delay)
                </small>
              </div>
            </div>
          </div>
        )}

        <ToggleSwitch
          label="Rare Biomes Screenshot"
          description="Automatically send a screenshot in your webhook when Glitched, Dreamspace, or Cyberspace is found"
          checked={config.rare_biome_screenshot !== false}
          onChange={(value) => updateConfig("rare_biome_screenshot", value)}
        />
      </div>

      <div className="card">
        <div className="card-header">
          <div className="card-icon">📸</div>
          <div>
            <h3>Periodical Screenshots &amp; Quests</h3>
            <p>
              Automatically capture screenshots and claim quests on a schedule
            </p>
          </div>
        </div>

        <ToggleSwitch
          label="Periodical Aura Screenshot"
          checked={config.periodical_aura_screenshot || false}
          onChange={(value) =>
            updateConfig("periodical_aura_screenshot", value)
          }
        />
        {config.periodical_aura_screenshot && (
          <div className="duration-input" style={{ marginBottom: "6px" }}>
            <label className="form-label">Interval (minutes):</label>
            <input
              className="form-input"
              value={config.periodical_aura_interval || "25"}
              onChange={(event) =>
                updateConfig("periodical_aura_interval", event.target.value)
              }
              style={{ width: "70px" }}
            />
          </div>
        )}

        <ToggleSwitch
          label="Periodical Inventory Screenshot"
          checked={config.periodical_inventory_screenshot || false}
          onChange={(value) =>
            updateConfig("periodical_inventory_screenshot", value)
          }
        />
        {config.periodical_inventory_screenshot && (
          <div className="duration-input" style={{ marginBottom: "6px" }}>
            <label className="form-label">Inventory Interval (minutes):</label>
            <input
              className="form-input"
              value={config.periodical_inventory_interval || "25"}
              onChange={(event) =>
                updateConfig(
                  "periodical_inventory_interval",
                  event.target.value,
                )
              }
              style={{ width: "70px" }}
            />
          </div>
        )}

        <ToggleSwitch
          label="Collect Daily Event Check-in"
          description="Detect the Daily Event Check-in pop-up, click Check once per day, and close it. Requires all three Daily Event calibrations."
          checked={config.collect_daily_event_checkin || false}
          onChange={(value) => updateConfig("collect_daily_event_checkin", value)}
        />
        {config.collect_daily_event_checkin && (
          <div style={{ margin: "4px 0 16px" }}>
            <p className="form-hint" style={{ margin: "6px 0 10px" }}>Configure Daily Rewards buttons and OCR region in Macro Calibrations.</p>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
              <button
                className="btn btn-accent"
                disabled={dailyBusy || !window.pywebview?.api}
                onClick={runDailyTest}
              >
                {dailyBusy ? "Collecting…" : "Collect now (test)"}
              </button>
              <button className="btn btn-secondary" disabled={dailyBusy} onClick={resetDailyClaim}>
                Reset claimed date
              </button>
              <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                {config.daily_event_claimed_date
                  ? `Last claim: ${config.daily_event_claimed_date}`
                  : "Not claimed yet — auto claim runs at 03:00 MSK"}
              </span>
            </div>
            {dailyMsg && (
              <p className="form-hint" style={{ marginTop: 8, color: dailyOk ? "#22c55e" : "#f87171" }}>
                {dailyMsg}
              </p>
            )}
          </div>
        )}

        <ToggleSwitch
          label="Auto claim daily quests"
          checked={config.auto_claim_daily_quests || false}
          onChange={(value) => updateConfig("auto_claim_daily_quests", value)}
        />
        {config.auto_claim_daily_quests && (
          <div className="duration-input">
            <label className="form-label">Claim Interval (minutes):</label>
            <input
              className="form-input"
              value={config.auto_claim_interval || "30"}
              onChange={(event) =>
                updateConfig("auto_claim_interval", event.target.value)
              }
              style={{ width: "70px" }}
            />
          </div>
        )}
      </div>

      {/* ── MEMORY MATCH ─────────────────────────────────────────────── */}
      <div className="card">
        <div className="card-header"><div className="card-icon">🧠</div><div style={{ flex: 1 }}><h3>Memory Match</h3><p>Detect the 5×4 board, solve pairs, and stop safely when the board is gone.</p></div></div>
        <div style={{ padding: "0 20px 16px", display: "grid", gap: "10px" }}>
          <ToggleSwitch label="Enable Memory Match" description="Runs automatically every 12h when the in-game cooldown ends." checked={config.memory_match_enabled || false} onChange={(value) => updateConfig("memory_match_enabled", value)} />
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <button
              className="btn"
              onClick={async () => {
                setDailyMsg("");
                try {
                  const res = await window.pywebview?.api?.run_memory_match_now?.();
                  if (res?.ok) setDailyMsg("Memory Match run started — watch the log.");
                  else setDailyMsg(`Could not start: ${res?.error || "unknown error"}`);
                } catch (e) {
                  setDailyMsg(`Could not start: ${e}`);
                }
              }}
              title="Play one Memory Match session right now (ignores the 12h cooldown, for testing)"
            >
              ▶ Run now (test)
            </button>
            <span className="form-hint" style={{ margin: 0 }}>Requires the macro to be running.</span>
          </div>
          <ToggleSwitch
            label="Play during fishing mode"
            description="Allow the Memory Match loop to run while fishing mode is active."
            checked={config.memory_match_play_on_fishing !== false}
            onChange={(value) => updateConfig("memory_match_play_on_fishing", value)}
          />
          <div className="duration-input">
            <label className="form-label">Playback speed multiplier:</label>
            <input
              className="form-input"
              value={config.memory_match_playback_multiplier ?? 1}
              onChange={(e) => updateConfig("memory_match_playback_multiplier", e.target.value)}
              style={{ width: 70 }}
            />
          </div>
          <div className="form-hint">Non-VIP accounts: enable "Non-VIP movement path" in the Fishing settings so walks are stretched automatically.</div>
        </div>
      </div>

      {/* ── QUEST BOARD ──────────────────────────────────────────────── */}
      <div className="card">
        <div className="card-header"><div className="card-icon">📜</div><div style={{ flex: 1 }}><h3>Quest Board</h3><p>Read, accept, dismiss, and claim quests using OCR and board controls.</p></div></div>
        <div style={{ padding: "0 20px 16px", display: "grid", gap: "10px" }}>
          <ToggleSwitch label="Enable Quest Board" description="Opening uses keyboard E; mouse clicks are only for the board controls." checked={config.quest_board_enabled || false} onChange={(value) => updateConfig("quest_board_enabled", value)} />
          <div className="duration-input">
            <label className="form-label">Check interval (minutes):</label>
            <input
              className="form-input"
              value={config.quest_board_check_interval_minutes ?? 15}
              onChange={(e) => updateConfig("quest_board_check_interval_minutes", e.target.value)}
              style={{ width: 70 }}
            />
          </div>
          <ToggleSwitch
            label="Auto-accept acceptable quests"
            description="Accept quests the macro can passively complete; others are dismissed."
            checked={config.quest_board_auto_accept !== false}
            onChange={(value) => updateConfig("quest_board_auto_accept", value)}
          />
          <ToggleSwitch
            label="Play during fishing mode"
            description="Allow the Quest Board loop to run while fishing mode is active."
            checked={config.quest_board_play_with_fishing !== false}
            onChange={(value) => updateConfig("quest_board_play_with_fishing", value)}
          />
          <div style={{ display: "grid", gap: 6, marginTop: 4 }}>
            <div className="form-label" style={{ fontWeight: 600 }}>Quest types — take or dismiss:</div>
            {Object.entries(QUEST_TYPE_LABELS).filter(([id]) => !HIDDEN_QUEST_TYPES.has(id)).map(([id, label]) => {
              const prefs = (config.quest_board_quest_preferences || {}) as Record<string, string>;
              const action = prefs[id] || QUEST_TYPE_DEFAULTS[id] || "dismiss";
              const setAction = (v: "accept" | "dismiss") =>
                updateConfig("quest_board_quest_preferences", { ...prefs, [id]: v });
              const variantPrefs = (config.quest_board_variant_prefs || {}) as Record<string, string[]>;
              const enabledVariants = variantPrefs[id] || [];
              const toggleVariant = (v: string) => {
                const cur = new Set(enabledVariants);
                if (cur.has(v)) cur.delete(v); else cur.add(v);
                updateConfig("quest_board_variant_prefs", { ...variantPrefs, [id]: [...cur] });
              };
              const variants = QUEST_VARIANTS[id] || [];
              return (
                <div key={id} style={{ padding: "6px 10px", borderRadius: 8, background: "rgba(255,255,255,.04)", border: "1px solid rgba(255,255,255,.08)", display: "grid", gap: 6 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
                    <span style={{ fontSize: 13 }}>{label}</span>
                    <div style={{ display: "flex", gap: 6 }}>
                      <button className={action === "accept" ? "btn btn-accent btn-sm" : "btn btn-sm"} onClick={() => setAction("accept")}>Take</button>
                      <button className={action === "dismiss" ? "btn btn-accent btn-sm" : "btn btn-sm"} onClick={() => setAction("dismiss")}>Dismiss</button>
                    </div>
                  </div>
                  {variants.length > 0 && action === "accept" && (
                    <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
                      <span style={{ fontSize: 11, color: "var(--text-muted)" }}>Tiers:</span>
                      {variants.map(v => {
                        const on = enabledVariants.includes(v);
                        return (
                          <button key={v}
                            onClick={() => toggleVariant(v)}
                            title={on ? `${v} enabled` : `${v} disabled`}
                            style={{
                              padding: "1px 8px", fontSize: 11, borderRadius: 6, cursor: "pointer",
                              border: on ? "1px solid var(--accent)" : "1px solid var(--border)",
                              background: on ? "rgba(124,108,255,.18)" : "transparent",
                              color: on ? "var(--text-primary)" : "var(--text-muted)",
                            }}>{v}</button>
                        );
                      })}
                      {enabledVariants.length === 0 && (
                        <span style={{ fontSize: 11, color: "var(--text-muted)" }}>(all tiers)</span>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
          <div className="form-hint">Hunt quests have no tier picker — rolling completes them wherever they appear. Player Hunt is always dismissed (cannot be automated). A quest whose tier cannot be read by OCR is dismissed.</div>
          <div className="form-hint">Fishing, Delivery, and Resonance quests are hidden until their automations ship — the macro dismisses them for now.</div>
        </div>
      </div>
    </>
  );
}
