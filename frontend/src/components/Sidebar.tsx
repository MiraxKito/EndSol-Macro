interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
  isGlitching: boolean;
  macroVersion: string;
  customTheme?: any;
}
import GlitchOverlay from "./GlitchOverlay";
import { useGlitchText } from "../hooks/useGlitchText";
import { useEffect, useRef } from "react";
import { useT } from "../i18n";
import endsolIcon from "../assets/endsol-macro.svg";

const SidebarItem = ({
  item,
  isActive,
  onClick,
  isGlitching,
  locked,
}: {
  item: any;
  isActive: boolean;
  onClick: () => void;
  isGlitching: boolean;
  locked?: boolean;
}) => {
  const label = useGlitchText(item.label || "", isGlitching);
  const isDisabled = item.disabled || locked;
  return (
    <div
      data-item-id={item.id}
      className={`sidebar-item ${isActive ? "active" : ""}`}
      onClick={() => !isDisabled && onClick()}
      style={
        isDisabled
          ? { opacity: 0.3, cursor: "not-allowed", pointerEvents: "none" }
          : {}
      }
      title={locked ? "🔒 Locked" : undefined}
    >
      <span className="icon" aria-hidden="true">
{locked ? "🔒" : item.icon}
      </span>
      {label}
      {item.disabled && (
        <span style={{ fontSize: "10px", marginLeft: "auto", opacity: 0.7 }}>
          (WIP)
        </span>
      )}
    </div>
  );
};

const navItems = [
  { section: "General" },
  { id: "notice", label: "Notice", icon: "📋" },
  { id: "webhook", label: "Webhook", icon: "🔗" },
  { id: "stats", label: "Stats", icon: "📊" },
  { id: "status", label: "Status", icon: "⚙️" },
  { section: "Macro Settings" },
  { id: "misc", label: "Automated Actions", icon: "🤖" },
  { id: "calibrations", label: "Macro Calibrations", icon: "🎯" },
  { id: "remoteaccess", label: "Remote Control", icon: "🔑" },
  { section: "Main Features" },
  { id: "fishing", label: "Fishing", icon: "🎣" },
  { id: "merchant", label: "Merchant", icon: "🎭" },
  { id: "autopopbuff", label: "Auto Pop Buff", icon: "🧪" },
  { id: "auras", label: "Auras", icon: "✨" },
  { id: "movements", label: "Movements", icon: "🗺️" },
  { id: "custompaths", label: "Custom Paths", icon: "🛤️" },
  { id: "potioncraft", label: "Potion Crafting", icon: "🧪" },
  { id: "otherfeatures", label: "Other Features", icon: "🔧" },
  { id: "multiinstances", label: "Multiple-Instances", icon: "🖥️", disabled: false },
  { id: "customization", label: "Discord Webhook Customization", icon: "🔧" },
  { id: "panelcustomization", label: "Panel Customization", icon: "🎨" },
  { section: "Others" },
  { id: "solbook", label: "Sol’s Book", icon: "📚" },
  { id: "instructions", label: "Instructions", icon: "📖" },
  { id: "credits", label: "Credits", icon: "💜" },
  { id: "donations", label: "Donations <3", icon: "💎" },
];

export default function Sidebar({
  activeTab,
  onTabChange,
  isGlitching,
  macroVersion,
  customTheme,
}: SidebarProps) {
  const t = useT();
  const labels = customTheme?.custom_labels || {};
  const icons = customTheme?.custom_icons || {};
  const title = useGlitchText(
    customTheme?.custom_macro_title || "EndSol Macro",
    isGlitching,
  );
  const version = useGlitchText(
    customTheme?.custom_macro_version || macroVersion || "v?.?.?",
    isGlitching,
  );
  const navRef = useRef<HTMLDivElement>(null);
  const scrollTopRef = useRef<number>(0);

  // Persist scroll position of sidebar across re-renders
  useEffect(() => {
    const el = navRef.current;
    if (!el) return;
    const onScroll = () => {
      scrollTopRef.current = el.scrollTop;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    // Restore after every render
    if (el.scrollTop !== scrollTopRef.current) {
      el.scrollTop = scrollTopRef.current;
    }
    return () => el.removeEventListener("scroll", onScroll);
  });

  // Also restore after activeTab change (click on a tab)
  useEffect(() => {
    const el = navRef.current;
    if (!el) return;
    // Defer to next frame so DOM has settled
    const id = requestAnimationFrame(() => {
      el.scrollTop = scrollTopRef.current;
    });
    return () => cancelAnimationFrame(id);
  }, [activeTab]);

  return (
    <div className="sidebar" style={{ position: "relative" }}>
      {isGlitching && <GlitchOverlay />}
      <div className="sidebar-brand">
        <img
          src={endsolIcon}
          alt="EndSol Macro"
          style={{
            width: "42px",
            height: "42px",
            borderRadius: "12px",
            flex: "0 0 auto",
            filter: "drop-shadow(0 4px 10px rgba(6, 182, 212, 0.25))",
          }}
        />
        <div>
          <h1>{title}</h1>
          <div className="version">{version}</div>
        </div>
      </div>

      <div className="sidebar-nav" ref={navRef}>
        {navItems.map((item, i) => {
          if ("section" in item && item.section) {
            return (
              <div key={`s-${i}`} className="sidebar-section-label">
                {item.section}
              </div>
            );
          }
          return (
            <SidebarItem
              key={item.id}
              item={{
                ...item,
                label: item.id ? labels[item.id] || t(item.label) : item.label,
                icon: item.id ? icons[item.id] || item.icon : item.icon,
              }}
              isActive={activeTab === item.id}
              onClick={() => item.id && onTabChange(item.id)}
              isGlitching={isGlitching}
            />
          );
        })}
      </div>

      <div className="sidebar-footer">
        <div className="by-line">EndSol Macro — fork of CoteabMacro</div>
      </div>
    </div>
  );
}
