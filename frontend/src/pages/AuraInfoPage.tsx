import { useEffect, useState } from "react";

type AuraInfo = Record<string, any>;

export default function AuraInfoPage() {
  const [data, setData] = useState<Record<string, AuraInfo>>({});
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const result = await window.pywebview?.api?.get_full_aura_data?.();
        if (active && result && typeof result === "object") setData(result);
      } catch (err) { if (active) setError(String(err)); }
    };
    void load();
    return () => { active = false; };
  }, []);
  const entries = Object.entries(data).sort(([a], [b]) => a.localeCompare(b));
  return <>
    <div className="page-header"><h2>Aura Information</h2><p>Loaded rarity and obtainment metadata used by Aura notifications.</p></div>
    {error && <div className="info-banner">Unable to load aura data: {error}</div>}
    <div className="card"><div style={{ display: "grid", gap: 8 }}>
      {entries.map(([name, info]) => <div key={name} style={{ border: "1px solid var(--border-color)", padding: "10px 12px", display: "grid", gridTemplateColumns: "1.4fr 1fr 1.5fr", gap: 12 }}>
        <strong>{name}</strong><span>Rarity: {info.rarity ? `1 in ${info.rarity}` : (info.rarity_name || "Unknown")}</span><span>Source: {info.obtainment || (info.exclusive_biome && info.exclusive_biome[0] !== "None" ? info.exclusive_biome[0] : "Rolling")}</span>
      </div>)}
      {!entries.length && <div className="form-hint">No aura records loaded.</div>}
    </div></div>
  </>;
}
