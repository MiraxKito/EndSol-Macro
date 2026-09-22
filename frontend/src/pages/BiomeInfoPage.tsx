import { useEffect, useState } from "react";

type BiomeInfo = Record<string, any>;

export default function BiomeInfoPage() {
  const [data, setData] = useState<Record<string, BiomeInfo>>({});
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const result = await window.pywebview?.api?.get_full_biome_data?.();
        if (active && result && typeof result === "object") setData(result);
      } catch (err) { if (active) setError(String(err)); }
    };
    void load();
    return () => { active = false; };
  }, []);
  const entries = Object.entries(data).filter(([name]) => name !== "NORMAL").sort(([a], [b]) => a.localeCompare(b));
  return <>
    <div className="page-header"><h2>Biome Information</h2><p>Neutral biome metadata loaded by the detector. Gameplay mechanics are not inferred here.</p></div>
    {error && <div className="info-banner">Unable to load biome data: {error}</div>}
    <div className="card"><div style={{ display: "grid", gap: 8 }}>
      {entries.map(([name, info]) => <div key={name} style={{ border: "1px solid var(--border-color)", padding: "10px 12px", display: "grid", gridTemplateColumns: "1.2fr 1fr 1fr", gap: 12 }}>
        <strong>{name}</strong><span>Spawn/Rarity: {info.spawn_chance || "Unknown"}</span><span>Duration: {info.duration || "Unknown"}</span>
      </div>)}
      {!entries.length && <div className="form-hint">No biome records loaded.</div>}
    </div></div>
  </>;
}
