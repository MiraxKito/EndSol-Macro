import { useState, useEffect, useRef, memo } from "react";
import "./App.css";
import { useConfig } from "./contexts/ConfigContext";
import { ToastProvider } from "./contexts/ToastContext";
import { ErrorBoundary } from "./components/ErrorBoundary";
import Sidebar from "./components/Sidebar";
import HeaderBar from "./components/HeaderBar";
import NoticePage from "./pages/NoticePage";
import WebhookPage from "./pages/WebhookPage";
import CalibrationPage from "./pages/CalibrationPage";
import MiscPage from "./pages/MiscPage";
import FishingPage from "./pages/FishingPage";
import MerchantPage from "./pages/MerchantPage";
import AutoPopBuffPage from "./pages/AutoPopBuffPage";
import AurasPage from "./pages/AurasPage";
import PotionCraftPage from "./pages/PotionCraftPage";
import StatusPage from "./pages/StatusPage";
import StatsPage from "./pages/StatsPage";
import SolsBookPage from "./pages/SolsBookPage";
import OtherFeaturesPage from "./pages/OtherFeaturesPage";
import CreditsPage from "./pages/CreditsPage";
import DonationsPage from "./pages/DonationsPage";
import RemoteAccessPage from "./pages/RemoteAccessPage";
import CalibrationOverlay from "./components/CalibrationOverlay";
import GlitchOverlay from "./components/GlitchOverlay";
import UpdateBanner from "./components/UpdateBanner";
import CustomizationPage from "./pages/CustomizationPage";
import PanelCustomizationPage from "./pages/PanelCustomizationPage";
import MovementsPage from "./pages/MovementsPage";
import CustomPathsPage from "./pages/CustomPathsPage";
import RecorderWindow from "./pages/RecorderWindow";
import BiomeConfirmWindow from "./pages/BiomeConfirmWindow";
import MultiInstancePage from "./pages/MultiInstancePage";
import InstructionsPage from "./pages/InstructionsPage";
import { I18nDom } from "./i18n";

// --- Safe Mode (Browser failsafe via HTTP) ---
const isSafeMode = new URLSearchParams(window.location.search).get("safe_mode");
if (isSafeMode && !(window as any).pywebview) {
  console.log(`[SafeMode] Initializing HTTP bridge...`);
  (window as any).isSafeMode = true;

  (window as any).pywebview = {
    api: new Proxy({}, {
      get: (_target, method: string) => {
        return async (...args: any[]) => {
          try {
            const response = await fetch(`/api/${method}`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify(args)
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            return data;
          } catch (err) {
            console.error(`[SafeMode] API Error (${method}):`, err);
            throw err;
          }
        };
      }
    })
  };
}

const pages: Record<string, React.FC> = {
  notice: NoticePage,
  webhook: WebhookPage,
  calibrations: CalibrationPage,
  remoteaccess: RemoteAccessPage,
  misc: MiscPage,
  fishing: FishingPage,
  merchant: MerchantPage,
  autopopbuff: AutoPopBuffPage,
  auras: AurasPage,
  movements: MovementsPage,
  custompaths: CustomPathsPage,
  potioncraft: PotionCraftPage,
  stats: StatsPage,
  solbook: SolsBookPage,
  status: StatusPage,
  otherfeatures: OtherFeaturesPage,
  multiinstances: MultiInstancePage,
  customization: CustomizationPage,
  panelcustomization: PanelCustomizationPage,
  instructions: InstructionsPage,
  credits: CreditsPage,
  donations: DonationsPage,
  // puzzle: PuzzlePage,
};

const PageHost = memo(function PageHost({ component: PageComponent, active }: { component: React.FC; active: boolean }) {
  return (
    <div style={{ display: active ? "block" : "none" }} aria-hidden={!active}>
      <ErrorBoundary><PageComponent /></ErrorBoundary>
    </div>
  );
});

function App() {
  const [activeTab, setActiveTab] = useState("notice");
  const { config, saveConfig, isMacroRunning, setMacroRunning } = useConfig();
  const [isApiReady, setIsApiReady] = useState(new URLSearchParams(window.location.search).get("safe_mode") !== null);
  const [theme, setTheme] = useState("midnight");
  const [isGlitching, setIsGlitching] = useState(false);
  const [macroVersion, setMacroVersion] = useState("v?.?.?");
  const [updateInfo, setUpdateInfo] = useState<{ version: string; url: string } | null>(null);
  const [updateStatus, setUpdateStatus] = useState<string | null>(null);
  const autoUpdateTriggerRef = useRef<string | null>(null);
  const startupUpdateCheckRequestedRef = useRef(false);
  // Auto-update disabled — original EndSol repo URL removed.
  const isAutoUpdateEnabled = false;


  const startMacro = async () => {
    if (!isApiReady || !config || isMacroRunning) return;
    setMacroRunning(true);
    if (document.activeElement instanceof HTMLElement) {
      document.activeElement.blur();
    }
    try {
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.set_biome_detection(true);
      }
    } catch (e) {
      console.error("Failed to start macro api:", e);
    }
  };

  const stopMacro = async () => {
    if (!isApiReady || !config || !isMacroRunning) return;
    setMacroRunning(false);
    try {
      if (window.pywebview && window.pywebview.api) {
        await window.pywebview.api.set_biome_detection(false);
      }
    } catch (e) {
      console.error("Failed to stop macro api:", e);
    }
  };

  const toggleMacro = () => {
    if (isMacroRunning) stopMacro();
    else startMacro();
  };

  // track running state inside event callbacks
  const isRunningRef = useRef(isMacroRunning);
  const processingRef = useRef(false);

  useEffect(() => {
    isRunningRef.current = isMacroRunning;
  }, [isMacroRunning]);

  useEffect(() => {
    const setupListeners = async () => {
      try {
        console.log("Setting up global listeners");

        (window as any).onShortcutEvent = async (key: string) => {
          if (processingRef.current) return;
          processingRef.current = true;

          try {
            if (key === "START") {
              if (!isRunningRef.current) {
                console.log("Start Shortcut (Backend) - Starting");
                setMacroRunning(true);
              }
            } else if (key === "STOP") {
              if (isRunningRef.current) {
                console.log("Stop Shortcut (Backend) - Stopping");
                setMacroRunning(false);
              }
            }
          } finally {
            setTimeout(() => {
              processingRef.current = false;
            }, 300);
          }
        };

        (window as any).onMacroStatus = (status: string) => {
          console.log("Macro Status Event:", status);
          if (status === "RUNNING" || status.includes("RUNNING")) {
            setMacroRunning(true);
          } else {
            setMacroRunning(false);
          }
        };

      } catch (err) {
        console.error("Failed to setup listeners:", err);
      }
    };

    setupListeners();

    // Clean up listener on unmount
    return () => {
      delete (window as any).onShortcutEvent;
      delete (window as any).onMacroStatus;
    };
  }, []);

  useEffect(() => {
    (window as any).onFishingFailsafeWarning = (message: string) => {
      if (message) {
        alert(message);
      }
      setActiveTab("misc");
    };

    return () => {
      delete (window as any).onFishingFailsafeWarning;
    };
  }, []);

  // Biome Listener
  useEffect(() => {
    const setupBiomeListener = async () => {
      (window as any).onBiomeUpdate = (payload: string) => {
        const biome = (payload || "").toUpperCase().trim();
        if ((biome === "GLITCHED") && config?.enable_glitch_effect) {
          setIsGlitching(true);
        } else {
          setIsGlitching(false);
        }
      };
    };

    setupBiomeListener();

    return () => {
      delete (window as any).onBiomeUpdate;
    };
  }, [config]);



  // Check Update Listener
  useEffect(() => {
    (window as any).onUpdateAvailable = (version: string, url: string) => {
      console.log("Update available:", version, url);
      setUpdateInfo({ version, url });
    };

    (window as any).onUpdateStatus = (status: string) => {
      console.log("Update status:", status);
      setUpdateStatus(status);
    };

    return () => {
      delete (window as any).onUpdateAvailable;
      delete (window as any).onUpdateStatus;
    };
  }, []);

  useEffect(() => {
    const shouldAutoUpdate = isAutoUpdateEnabled;
    if (!updateInfo || !shouldAutoUpdate) return;

    const updateKey = `${updateInfo.version}|${updateInfo.url}`;
    if (autoUpdateTriggerRef.current === updateKey) return;
    autoUpdateTriggerRef.current = updateKey;

    const applyAutoUpdate = async () => {
      try {
        setUpdateStatus("downloading");
        if (window.pywebview?.api?.apply_update) {
          await window.pywebview.api.apply_update(updateInfo.url, updateInfo.version);
        }
      } catch (err) {
        console.error("Auto update apply failed:", err);
        setUpdateStatus("failed");
        autoUpdateTriggerRef.current = null;
      }
    };

    void applyAutoUpdate();
  }, [updateInfo, isAutoUpdateEnabled]);

  useEffect(() => {
    if (!config) return;
    if (startupUpdateCheckRequestedRef.current) return;
    startupUpdateCheckRequestedRef.current = true;

    const requestUpdateCheck = async () => {
      // Auto-update disabled — skip update check entirely.
      return;
    };

    const onReady = () => {
      setIsApiReady(true);
      void requestUpdateCheck();
    };

    if (window.pywebview?.api || (window as any).isSafeMode) {
      setIsApiReady(true);
      void requestUpdateCheck();
      return;
    }

    window.addEventListener("pywebviewready", onReady, { once: true });
    return () => {
      window.removeEventListener("pywebviewready", onReady);
    };
  }, [config]);

  useEffect(() => {
    (window as any).onNavigateTab = (tabId: string) => {
      const normalized = String(tabId || "").trim().toLowerCase();
      if (normalized && pages[normalized]) {
        setActiveTab(normalized);
      }
    };
    return () => {
      delete (window as any).onNavigateTab;
    };
  }, []);

  // Load macro version from backend (single source in main.py)
  useEffect(() => {
    let cancelled = false;

    const applyVersion = (value: unknown) => {
      const version = String(value ?? "").trim();
      if (!version) return false;
      if (!cancelled) {
        setMacroVersion(version);
      }
      document.title = `EndSol Macro ${version}`;
      return true;
    };

    const loadMacroVersion = async (): Promise<boolean> => {
      try {
        if (window.pywebview?.api && typeof window.pywebview.api.get_macro_version === "function") {
          const version = await window.pywebview.api.get_macro_version();
          return applyVersion(version);
        }
      } catch (err) {
        console.error("Failed to load macro version:", err);
      }
      return false;
    };

    const tryLoad = async () => {
      for (let i = 0; i < 10 && !cancelled; i++) {
        if (await loadMacroVersion()) return;
        await new Promise(r => setTimeout(r, 500));
      }
    };

    void tryLoad();

    return () => {
      cancelled = true;
    };
  }, []);

  // Local Listener for when App is Focused
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "F1") {
        console.log("Frontend Listener: F1 Pressed");
        startMacro();
      } else if (e.key === "F2") {
        console.log("Frontend Listener: F2 Pressed");
        stopMacro();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isMacroRunning]);

  // Sync theme
  useEffect(() => {
    if (config && config.selected_theme) {
      setTheme(config.selected_theme);
    }
  }, [config]);

  // Apply the built-in theme and every saved Panel Customization surface.
  const customThemeKeysRef = useRef<string[]>([]);
  useEffect(() => {
    document.body.setAttribute("data-theme", theme);
    const root = document.documentElement;
    const body = document.body;
    customThemeKeysRef.current.forEach(key => {
      root.style.removeProperty(key);
      body.style.removeProperty(key);
    });
    const custom = config?.custom_theme_data as any;
    const nextKeys: string[] = [];
    if (custom?.variables && typeof custom.variables === "object") {
      Object.entries(custom.variables).forEach(([key, value]) => {
        if (typeof value === "string" && value) {
          // App.css defines variables on body[data-theme], which wins over
          // inherited :root values. Set both targets for reliable overrides.
          root.style.setProperty(key, value);
          body.style.setProperty(key, value);
          nextKeys.push(key);
        }
      });
    }
    customThemeKeysRef.current = nextKeys;
    const styleId = "endsol-custom-theme-css";
    document.getElementById(styleId)?.remove();
    const css = [custom?.custom_css, custom?.raw_custom_css].filter(Boolean).join("\n");
    if (css) {
      const style = document.createElement("style");
      style.id = styleId;
      style.textContent = css;
      document.head.appendChild(style);
    }
    const fontId = "endsol-custom-theme-font";
    document.getElementById(fontId)?.remove();
    if (custom?.raw_font_url) {
      const link = document.createElement("link");
      link.id = fontId;
      link.rel = "stylesheet";
      link.href = String(custom.raw_font_url);
      document.head.appendChild(link);
    }
    root.style.setProperty("--custom-font-weight", String(custom?.font_weight || "normal"));
    root.style.setProperty("--custom-font-style", String(custom?.font_style || "normal"));
  }, [theme, config?.custom_theme_data]);

  // Do not navigate/reload the inline pywebview document here. A full
  // window.location.reload() can detach the inline HTML document and leave
  // Edge WebView on a black page. ConfigContext already performs the complete
  // startup load; theme/CSS application above is the safe second pass.

  const handleThemeChange = (newTheme: string) => {
    setTheme(newTheme);
    if (config) {
      saveConfig({ ...config, selected_theme: newTheme });
    }
  };



  // Window params may arrive as a URL fragment (file:// windows cannot carry
  // a query string), so read the hash as a fallback.
  const readAppParam = (key: string): string | null => {
    const fromSearch = new URLSearchParams(window.location.search).get(key);
    if (fromSearch !== null) return fromSearch;
    const rawHash = (window.location.hash || "").replace(/^#/, "");
    const hashParams = new URLSearchParams(rawHash.startsWith("?") ? rawHash.slice(1) : rawHash);
    return hashParams.get(key);
  };
  const activePageQuery = (window as any).__INJECTED_OVERLAY__ || readAppParam("overlay");
  const windowType = (window as any).__INJECTED_WINDOW_TYPE__ || readAppParam("window");

  if (windowType === "recorder") {
    return <RecorderWindow />;
  }

  if (windowType === "biome_confirm") {
    return <BiomeConfirmWindow />;
  }

  if (activePageQuery) {
    const mode = activePageQuery === "region" ? "region" : "point";
    return <CalibrationOverlay mode={mode} />;
  }

  const customTheme = config?.custom_theme_data as any;
  const customBackground = customTheme?.bg_type === "image" && customTheme?.custom_bg_url
    ? `url("${String(customTheme.custom_bg_url).replace(/"/g, "")}")`
    : customTheme?.bg_type === "gradient"
      ? `linear-gradient(135deg, ${customTheme.grad1 || "#7c5bf5"}, ${customTheme.grad2 || "#6344d4"}, ${customTheme.grad3 || "#a78bfa"})`
      : (config?.custom_background_image ? `url("file://${config.custom_background_image}")` : undefined);

  const appContent = (
    <div className={`window-frame ${isGlitching ? 'is-glitching' : ''}`} style={{
      backgroundImage: customBackground,
      backgroundSize: "cover",
      backgroundPosition: "center",
      backgroundRepeat: "no-repeat"
    }}>
      <div className="corner-bracket tl" />
      <div className="corner-bracket tr" />
      <div className="corner-bracket bl" />
      <div className="corner-bracket br" />
      <div className="app-layout" style={(!isApiReady || !config) ? { pointerEvents: 'none', opacity: 0.62 } : {}}>
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab} isGlitching={isGlitching} macroVersion={macroVersion} customTheme={config?.custom_theme_data} />
        <div className="main-content" style={{ position: "relative" }}>
          <HeaderBar
            isRunning={isMacroRunning}
            onToggle={toggleMacro}
            theme={theme}
            onThemeChange={handleThemeChange}
            isGlitching={isGlitching}
            setActiveTab={setActiveTab}
          />
          {updateInfo && (
            <UpdateBanner
              version={updateInfo.version}
              downloadUrl={updateInfo.url}
              updateStatus={updateStatus}
              onDismiss={() => setUpdateInfo(null)}
              onDontAskAgain={async () => {
                if (config) {
                  await saveConfig({ ...config, dont_ask_for_update: true });
                }
                setUpdateInfo(null);
              }}
            />
          )}
          <div className="page-content">
            {Object.entries(pages).map(([pageId, PageComponent]) => (
              <PageHost key={pageId} component={PageComponent} active={activeTab === pageId} />
            ))}
          </div>
        </div>
      </div>
      {(!isApiReady || !config) && (
        <div role="status" aria-live="polite" style={{ position: "absolute", inset: 0, zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", background: "rgba(5,5,10,0.94)", color: "var(--text-primary, #fff)" }}>
          <div style={{ textAlign: "center", padding: "28px", minWidth: "260px" }}>
            <div className="loading-spinner" style={{ margin: "0 auto 16px" }} />
            <strong>Loading EndSol Macro</strong>
            <div style={{ marginTop: "8px", color: "var(--text-secondary, #aaa)", fontSize: "13px" }}>Preparing configuration and biome data…</div>
          </div>
        </div>
      )}
      {isGlitching && <GlitchOverlay />}
    </div>
  );

  return (
    <ToastProvider>
      <I18nDom />
      <ErrorBoundary>
        {appContent}
      </ErrorBoundary>
    </ToastProvider>
  );
}

export default App;
