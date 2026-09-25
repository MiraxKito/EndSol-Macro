import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";

type Entry = Record<string, any>;
type MapData = Record<string, Entry>;

const normColor = (value: any) => {
  const raw = String(value ?? "#8b7cff");
  return raw.startsWith("0x") ? `#${raw.slice(2)}` : raw.startsWith("#") ? raw : `#${raw}`;
};

const rarityClass = (value: any) => {
  const n = Number(String(value ?? "").replace(/,/g, ""));
  if (!Number.isFinite(n)) return "UNKNOWN";
  if (n >= 1_000_000_000) return "TRANSCENDENT";
  if (n >= 100_000_000) return "GLORIOUS";
  if (n >= 10_000_000) return "EXALTED";
  if (n >= 1_000_000) return "MYTHIC";
  if (n >= 100_000) return "LEGENDARY";
  if (n >= 10_000) return "UNIQUE";
  if (n >= 1_000) return "EPIC";
  return "BASIC";
};

/**
 * Accent color per aura rarity type. Colors mirror the in-game inventory
 * display, sourced from the wiki's Module:Rarity/data.
 */
const RARITY_COLORS: Record<string, string> = {
  "Basic": "#FFFFFF",
  "Epic": "#C57ED3",
  "Unique": "#BE7418",
  "Legendary": "#F7F917",
  "Mythic": "#F554EF",
  "Exalted": "#3F62D8",
  "Glorious": "#C52425",
  "Transcendent": "#7EC8FF",
  "Challenged": "#E8E8E8",
  "Challenged+": "#E8E8E8",
  "Event": "#21FF11",
  "Dev Exclusive": "#5B2AA8",
  "Right Hand": "#818cf8",
  "Left Hand": "#c084fc",
  "Pocket Lantern": "#facc15",
  "Talisman": "#38bdf8",
  "Potions": "#ec4899",
  "Runes": "#a855f7",
  "Tools": "#06b6d4",
  "Materials": "#eab308",
  "Chests": "#f97316",
  "Other": "#94a3b8",
};

/** Shimmer/gradient text class for the rarity label (App.css). */
const rarityTextClass = (type: string) =>
  type === "Challenged" || type === "Challenged+" ? "rarity-text rarity-text--challenged"
  : type === "Transcendent" ? "rarity-text rarity-text--transcendent"
  : type === "Glorious" ? "rarity-text rarity-text--glorious"
  : type === "Dev Exclusive" ? "rarity-text rarity-text--dev"
  : "";

const entryAccent = (info: Entry | undefined | null, section: string) => {
  if (section === "biomes") return normColor(info?.color || "#7c6cff");
  if (!info) return "#94a3b8";
  if (info.color) return normColor(info.color);
  const type = entryRarityType(info);
  if (type === "Event" && isEventAura(info)) {
    const tier = canonicalRarity(rarityClass(info?.rarity));
    return RARITY_COLORS[tier] || RARITY_COLORS["Event"];
  }
  return RARITY_COLORS[type] || RARITY_COLORS[info?.category] || "#94a3b8";
};

const auraFlags = (e: Entry | null | undefined) => Array.isArray(e?.flags) ? e.flags : [];
const isEventAura = (e: Entry | null | undefined) =>
  !!e && (entryRarityType(e) === "Event" || auraFlags(e).includes("limited") || !!e.limited);
const isCraftableAura = (e: Entry | null | undefined) =>
  !!e && auraFlags(e).includes("craftable") && !e.rarity_is_potion;
const isPotionAura = (e: Entry | null | undefined) => !!e && !!e.rarity_is_potion;

const RARITY_ORDER = [
  "Basic", "Epic", "Unique", "Legendary", "Mythic", "Exalted", "Glorious",
  "Transcendent", "Challenged", "Challenged+", "Event", "Dev Exclusive",
  "Right Hand", "Left Hand", "Pocket Lantern", "Talisman",
  "Potions", "Runes", "Tools", "Materials", "Chests"
];

const LIMBO_EXCLUSIVE_FALLBACK = [
  "Nothing", "Raven", "Gothic", "Anima", "Empty", "Imaginary",
  "Juxtaposition", "Elude", "Unknown", "Raven Plague",
];
const THE_LIMBO_ENTRY = (exclusiveAuras: string[]): Entry => ({
  name: "THE LIMBO",
  color: "0x5B2AA8",
  category: "Dimension",
  spawn_chance: "Entry dimension (not a weather roll)",
  duration: "Stays until you leave",
  chat_message: "Doesn't post a chat message on spawn",
  thumbnail_url: "https://static.wikia.nocookie.net/sol-rng/images/3/33/LimboEntrance.png/revision/latest?cb=20260503035230",
  description: "A hidden dimension added in the Eon 1-5 Update, captioned \"The Timeless Land\". "
    + "Unlocked through Stella's second quest: the Glass Candle recipe lets you past the Unnamed Entity, "
    + "then four candle quests open the way. Only Limbo-exclusive auras can be rolled here - Overworld auras "
    + "are impossible to obtain, and most Overworld buffs are disabled (gear buffs and Final Luck still work), "
    + "so survival relies on Forbidden Potions and Void Hearts. Four falls into the void are survivable; "
    + "the fifth sends you back to Sol's Island. The Portable Crack allows re-entry. Home of Dave and Eden (NPC).",
  exclusive_auras: exclusiveAuras,
  gallery: [
    { url: "https://static.wikia.nocookie.net/sol-rng/images/3/33/LimboEntrance.png/revision/latest?cb=20260503035230", caption: "The Limbo entrance, guarded by the Unnamed Entity" },
    { url: "https://static.wikia.nocookie.net/sol-rng/images/d/d2/Limbo_Outside.png/revision/latest?cb=20250817144719", caption: "The dark void with floating semi-blue-grey islands" },
    { url: "https://static.wikia.nocookie.net/sol-rng/images/f/f9/Limbo_bridge.png/revision/latest?cb=20250615193902", caption: "Torch-lit pathway between the islands" },
    { url: "https://static.wikia.nocookie.net/sol-rng/images/b/b8/LimboCandles.png/revision/latest?cb=20260306190644", caption: "One of the four candle quests" },
    { url: "https://static.wikia.nocookie.net/sol-rng/images/3/31/Sol%27s_RNG_Limbo_v1.10.png/revision/latest?cb=20260818125121", caption: "Infographic: current Limbo auras (v1.10, by MattPlays607)" },
  ],
  _metadata_source: "fandom",
});

const canonicalRarity = (raw: any) => {
  const value = String(raw ?? "").trim();
  if (!value) return "Other";
  const lower = value.toLowerCase();
  if (lower === "challenged+") return "Challenged+";
  if (lower === "dev exclusive" || lower === "dev-exclusive") return "Dev Exclusive";
  const found = RARITY_ORDER.find(r => r.toLowerCase() === lower);
  if (found) return found;
  if (lower === "unknown") return "Other";
  return value.charAt(0).toUpperCase() + value.slice(1);
};

const entryRarityType = (info: Entry) =>
  canonicalRarity(info?.category || info?.rarity_name || (info?.rarity ? rarityClass(info.rarity) : "Other"));

const obtainmentLabel = (entry: Entry) => {
  if (entry?.obtainment) return String(entry.obtainment);
  const native = entry?.native_biome;
  if (entry?.is_exclusive && Array.isArray(entry.exclusive_biomes) && entry.exclusive_biomes.length) return `Exclusive to ${entry.exclusive_biomes.join(", ")}`;
  if (Array.isArray(native) && native[0] && native[0] !== "None") return `Native to ${native[0]}`;
  const exclusive = entry?.exclusive_biome;
  if (Array.isArray(exclusive) && exclusive[0] && exclusive[0] !== "None") return `Exclusive to ${exclusive[0]}`;
  return "Obtainment details unavailable";
};

const rarityClassFull = (rarityName: string | undefined, value: any) => {
  if (rarityName && rarityName.trim()) return rarityName.trim();
  return rarityClass(value);
};

const fmtNum = (n: any) => {
  const num = Number(String(n ?? "").replace(/,/g, ""));
  return Number.isFinite(num) ? num.toLocaleString("en-US") : String(n ?? "");
};

const prettyName = (key: any) => String(key ?? "").replace(/_/g, " ").trim();

const SOURCE_LABELS: Record<string, string> = {
  fandom: "Sol's RNG Fandom Wiki",
  fandom_article: "Sol's RNG Fandom Wiki",
  fandom_cache: "Sol's RNG Fandom Wiki",
  fandom_snapshot: "Sol's RNG Fandom Wiki",
  fandom_detail: "Sol's RNG Fandom Wiki",
};

const sourceLabel = (value: any) => {
  const key = String(value ?? "");
  return SOURCE_LABELS[key] || "Sol's RNG Fandom Wiki";
};

const auraRarityText = (e: Entry) => {
  if (!e) return "Unknown";
  if (isCraftableAura(e) || isPotionAura(e)) {
    const rn = e.rarity_name ? canonicalRarity(e.rarity_name) : "";
    return `${rn ? rn + " · " : ""}Crafted — see Obtainment`;
  }
  const native = Number(e.native_rarity);
  const global = Number(e.rarity);
  const biome = String(e.native_biome?.[0] ?? "");
  if (e.is_exclusive && !Number.isFinite(native) && !Number.isFinite(global)) return "N/A — exclusive";
  const parts: string[] = [];
  if (Number.isFinite(native) && native > 0) {
    parts.push(`1 in ${fmtNum(native)}${biome && biome !== "None" ? ` in ${prettyName(biome)}` : ""}`);
  }
  if (!e.is_exclusive && Number.isFinite(global) && global > 0 && (!Number.isFinite(native) || global !== native)) {
    parts.push(`1 in ${fmtNum(global)} anywhere`);
  }
  if (!parts.length && Number.isFinite(global) && global > 0) parts.push(`1 in ${fmtNum(global)}`);
  if (e.is_exclusive) parts.push("exclusive");
  return parts.join(" · ") || "Unknown";
};

const searchableText = (name: string, info: Entry) => {
  const bits = [prettyName(name)];
  const excl = Array.isArray(info?.exclusive_biomes) ? info.exclusive_biomes : [];
  if (excl.length) bits.push(...excl.map(prettyName));
  const exclRaw = Array.isArray(info?.exclusive_biome) ? info.exclusive_biome : [];
  if (exclRaw[0] && exclRaw[0] !== "None") bits.push(prettyName(exclRaw[0]));
  const native = Array.isArray(info?.native_biome) ? info.native_biome : [];
  if (native[0] && native[0] !== "None") bits.push(prettyName(native[0]));
  if (info?.obtainment) bits.push(String(info.obtainment));
  if (info?.category) bits.push(String(info.category));
  if (info?.slot) bits.push(String(info.slot));
  return bits.join(" ").toLowerCase();
};

export default function SolsBookPage() {
  const [biomes, setBiomes] = useState<MapData>({});
  const [items, setItems] = useState<MapData>({});
  const [gauntlets, setGauntlets] = useState<MapData>({});
  const [auras, setAuras] = useState<MapData>({});
  const [section, setSection] = useState<"biomes" | "auras" | "items" | "gauntlets">("biomes");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailTab, setDetailTab] = useState<"info" | "media">("info");

  const load = async () => {
    setLoading(true);
    try {
      const [biomeData, auraData, itemData, gauntletData] = await Promise.all([
        window.pywebview?.api?.get_full_biome_data?.(),
        window.pywebview?.api?.get_full_aura_data?.(),
        (window.pywebview?.api as any)?.get_full_item_data?.(),
        (window.pywebview?.api as any)?.get_full_gauntlet_data?.(),
      ]);
      if (biomeData && typeof biomeData === "object") {
        const limboAuras = Object.entries(auraData || {})
          .filter(([, v]) => /limbo/i.test(String((v as any)?.obtainment || ""))
            || /limbo/i.test(JSON.stringify((v as any)?.exclusive_biomes || "")))
          .map(([n]) => prettyName(n));
        setBiomes({ ...biomeData, "THE LIMBO": THE_LIMBO_ENTRY(limboAuras.length ? limboAuras : LIMBO_EXCLUSIVE_FALLBACK) });
      }
      if (auraData && typeof auraData === "object") setAuras(auraData);
      if (itemData && typeof itemData === "object") setItems(itemData);
      if (gauntletData && typeof gauntletData === "object") setGauntlets(gauntletData);
    } finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, []);

  const data = section === "biomes" ? biomes : section === "items" ? items : section === "gauntlets" ? gauntlets : auras;
  const categories = useMemo(() => {
    const set = new Map<string, string>();
    Object.values(data).forEach(item => {
      const value = entryRarityType(item);
      set.set(value.toLowerCase(), value);
    });
    const list = Array.from(set.values());
    list.sort((a, b) => {
      if (a === "Other") return 1;
      if (b === "Other") return -1;
      const ia = RARITY_ORDER.indexOf(a);
      const ib = RARITY_ORDER.indexOf(b);
      if (ia === -1 && ib === -1) return a.localeCompare(b);
      if (ia === -1) return 1;
      if (ib === -1) return -1;
      return ia - ib;
    });
    return list;
  }, [data]);

  const entries = useMemo(() => Object.entries(data)
    .filter(([name, info]) => {
      const q = query.trim().toLowerCase();
      const matchesQuery = !q || searchableText(name, info).includes(q);
      const matchesCategory = category === "all" || entryRarityType(info) === category;
      return matchesQuery && matchesCategory;
    })
    .sort(([a], [b]) => a.localeCompare(b)), [data, query, category]);

  const entry = selected ? data[selected] : null;
  const accent = entryAccent(entry, section);

  const auraImageUrls = useMemo(() => {
    if (section !== "auras" || !entry) return [];
    return Array.from(new Set([
      ...(Array.isArray(entry.image_urls) ? entry.image_urls : []),
      entry.image_collection_url,
      entry.image_ingame_url,
    ].filter((url): url is string => typeof url === "string" && url.length > 0)));
  }, [section, entry]);
  const auraVideoUrl = typeof entry?.video_url === "string" && entry.video_url ? entry.video_url : "";
  const auraVideoKind = typeof entry?.video_kind === "string" ? entry.video_kind : "";
  const auraCutsceneNote = typeof entry?.cutscene_note === "string" ? entry.cutscene_note : "";
  const auraMusicUrl = typeof entry?.music_url === "string" && entry.music_url ? entry.music_url : "";
  const auraMusicFile = typeof entry?.music_file === "string" ? entry.music_file : "";

  const biomeImageUrls = useMemo(() => {
    if (section !== "biomes" || !entry) return [];
    const fromGallery = Array.isArray(entry.gallery)
      ? entry.gallery.map((g: any) => (typeof g?.url === "string" ? g.url : "")).filter(Boolean)
      : [];
    return Array.from(new Set([
      typeof entry.thumbnail_url === "string" ? entry.thumbnail_url : "",
      ...fromGallery,
    ].filter((url): url is string => url.length > 0)));
  }, [section, entry]);
  const biomeMusicUrl = typeof entry?.music_url === "string" && entry.music_url ? entry.music_url : "";
  const biomeMusicFile = typeof entry?.music_file === "string" ? entry.music_file : "";

  useEffect(() => {
    if (!selected || !entries.some(([name]) => name === selected)) {
      setSelected(entries[0]?.[0] || null);
    }
  }, [section, entries, selected]);

  useEffect(() => { setDetailTab("info"); }, [selected, section]);

  useEffect(() => {
    if (section !== "auras" || !selected || !window.pywebview?.api?.get_aura_detail) return;
    let alive = true;
    setDetailLoading(true);
    void window.pywebview.api.get_aura_detail(selected).then((detail: Record<string, any>) => {
      if (!alive || !detail || detail.error) return;
      setAuras(current => ({ ...current, [selected]: { ...current[selected], ...detail } }));
    }).finally(() => { if (alive) setDetailLoading(false); });
    return () => { alive = false; };
  }, [section, selected]);

  useEffect(() => {
    if (section !== "biomes" || !selected || !window.pywebview?.api?.get_biome_detail) return;
    let alive = true;
    void window.pywebview.api.get_biome_detail(selected).then((detail: Record<string, any>) => {
      if (!alive || !detail || detail.error) return;
      setBiomes(current => ({ ...current, [selected]: { ...current[selected], ...detail } }));
    }).catch(() => {});
    return () => { alive = false; };
  }, [section, selected]);

  return <div className="page-container fade-in" data-no-i18n style={{ minHeight: "100%" }}>
    <div className="page-header" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start" }}>
        <div>
          <h2 style={{ letterSpacing: "0.04em" }}>✦ Sol’s Book</h2>
          <p>Official Field Almanac of Sol’s RNG — Biomes, Auras, Items, and Gauntlets straight from the Fandom Wiki.</p>
        </div>
        <button className="btn" onClick={() => void load()} disabled={loading}>{loading ? "Updating…" : "↻ Refresh"}</button>
      </div>
    </div>

    <div className="card" style={{ padding: 0, overflow: "hidden", borderRadius: "6px" }}>
      <div className="book-panel" style={{ padding: "20px 24px", background: "linear-gradient(180deg, rgba(30, 27, 46, 0.7) 0%, rgba(18, 16, 28, 0.9) 100%)" }}>
        <div style={{ color: "#a78bfa", fontSize: 11, letterSpacing: ".18em", textTransform: "uppercase", fontWeight: 600 }}>The EndSol Reference Archive</div>
        <h3 style={{ fontSize: 24, margin: "6px 0 4px", fontWeight: 700 }}>The Almanac of Chance</h3>
        <div style={{ color: "#94a3b8", maxWidth: 760, lineHeight: 1.5, fontSize: 13 }}>Explore comprehensive in-game encyclopedic entries loaded directly from Sol's RNG Fandom Wiki.</div>
        
        <div style={{ display: "flex", gap: 8, marginTop: 16, flexWrap: "wrap" }}>
          <div className="book-chip" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", padding: "5px 12px", borderRadius: "4px", fontSize: 12 }}>
            <b style={{ color: "#a78bfa" }}>{Object.keys(biomes).length}</b> biomes
          </div>
          <div className="book-chip" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", padding: "5px 12px", borderRadius: "4px", fontSize: 12 }}>
            <b style={{ color: "#38bdf8" }}>{Object.keys(auras).length}</b> auras
          </div>
          <div className="book-chip" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", padding: "5px 12px", borderRadius: "4px", fontSize: 12 }}>
            <b style={{ color: "#fbbf24" }}>{Object.keys(items).length}</b> items
          </div>
          <div className="book-chip" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", padding: "5px 12px", borderRadius: "4px", fontSize: 12 }}>
            <b style={{ color: "#ec4899" }}>{Object.keys(gauntlets).length}</b> gauntlets
          </div>
          <div className="book-chip" style={{ background: "rgba(34, 197, 94, 0.1)", border: "1px solid rgba(34, 197, 94, 0.2)", color: "#86efac", padding: "5px 12px", borderRadius: "4px", fontSize: 12 }}>
            ✓ Sol's RNG Fandom Verified
          </div>
        </div>
      </div>

      <div style={{ padding: "12px 18px", borderTop: "1px solid rgba(255,255,255,.08)", borderBottom: "1px solid rgba(255,255,255,.08)", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", background: "rgba(15, 13, 24, 0.5)" }}>
        <button className={`btn ${section === "biomes" ? "btn-accent" : ""}`} style={{ borderRadius: "4px", padding: "6px 14px", fontWeight: 600 }} onClick={() => { setSection("biomes"); setCategory("all"); }}>☁ Biomes</button>
        <button className={`btn ${section === "auras" ? "btn-accent" : ""}`} style={{ borderRadius: "4px", padding: "6px 14px", fontWeight: 600 }} onClick={() => { setSection("auras"); setCategory("all"); }}>✧ Auras</button>
        <button className={`btn ${section === "items" ? "btn-accent" : ""}`} style={{ borderRadius: "4px", padding: "6px 14px", fontWeight: 600 }} onClick={() => { setSection("items"); setCategory("all"); }}>🎒 Items</button>
        <button className={`btn ${section === "gauntlets" ? "btn-accent" : ""}`} style={{ borderRadius: "4px", padding: "6px 14px", fontWeight: 600 }} onClick={() => { setSection("gauntlets"); setCategory("all"); }}>🥊 Gauntlets</button>
        
        <input className="form-input" style={{ minWidth: 200, flex: 1, maxWidth: 340, borderRadius: "4px" }} value={query} onChange={e => setQuery(e.target.value)} placeholder={section === "auras" ? "Search auras…" : section === "biomes" ? "Search biomes…" : section === "items" ? "Search items…" : "Search gauntlets…"} />
        <select className="form-input" style={{ maxWidth: 190, borderRadius: "4px" }} value={category} onChange={e => setCategory(e.target.value)}>
          <option value="all">All categories</option>
          {categories.map(value => <option key={value} value={value}>{value}</option>)}
        </select>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(230px, .9fr) minmax(0, 1.6fr)", minHeight: 480 }}>
        {/* Left List */}
        <div style={{ padding: 12, borderRight: "1px solid rgba(255,255,255,.08)", maxHeight: 620, overflow: "auto" }}>
          {loading && <div className="form-hint" style={{ padding: 18 }}>Opening the archive…</div>}
          {!loading && !entries.length && <div className="form-hint" style={{ padding: 18 }}>No entries match this search.</div>}
          {entries.map(([name, info]) => {
            const active = name === selected;
            const color = entryAccent(info, section);
            const isEvent = (section === "auras" && isEventAura(info)) || (section === "gauntlets" && info.limited);
            const itemStyle = active
              ? ({ "--item-color": color, "--item-bg": `${color}1a`, "--item-border": `${color}66`, borderRadius: "4px" } as React.CSSProperties)
              : isEvent
              ? ({ border: "1px dashed rgba(34,197,94,.4)", borderRadius: "4px" } as React.CSSProperties)
              : { borderRadius: "4px" };
            return <button key={name} onClick={() => setSelected(name)} className={`book-item${active ? " book-item--active" : ""}`} style={itemStyle}>
              {/* Perf: no thumbnails in selection lists — dozens of animated GIFs
                  composited at once were the main source of FPS drops. Lists are
                  text + rarity color dot only; images live in the detail pane. */}
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, boxShadow: `0 0 8px ${color}`, flex: "0 0 auto" }} />
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 13 }}>{prettyName(name)}</span>
            </button>;
          })}
        </div>

        {/* Right Detail Pane */}
        <div style={{ padding: "24px clamp(16px, 3vw, 36px)", background: "rgba(15, 13, 24, 0.4)" }}>
          {!entry && <div className="form-hint">Select an entry from the archive.</div>}
          {entry && <>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 16, borderBottom: `1px solid rgba(255,255,255,0.08)`, paddingBottom: 18, marginBottom: 18 }}>
              <div className="book-panel" style={{ width: 64, height: 64, display: "grid", placeItems: "center", fontSize: 28, flex: "0 0 auto", overflow: "hidden", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "6px" }}>
                {entry.thumbnail_url ? (
                  <CachedThumb url={String(entry.thumbnail_url)} alt={String(selected)} style={{ width: "100%", height: "100%", objectFit: "contain", padding: 4 }} />
                ) : (
                  section === "biomes" ? "☁" : section === "items" ? "🎒" : section === "gauntlets" ? "🥊" : "✧"
                )}
              </div>
              <div style={{ flex: 1 }}>
                <div className={rarityTextClass(entryRarityType(entry))} style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".16em", ...(rarityTextClass(entryRarityType(entry)) ? {} : { color: accent }) }}>
                  {section === "gauntlets" ? (entry.slot || entry.hand || "Gauntlet") : section === "items" ? (entry.category || "Item") : entryRarityType(entry)}
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <h3 style={{ margin: "4px 0 4px", fontSize: 23, fontWeight: 700, color: "#fff" }}>{entry?.name ? String(entry.name) : prettyName(selected)}</h3>
                  {section === "auras" && isEventAura(entry) && <span className="book-badge" style={{ color: "#21FF11" }}>Event</span>}
                  {section === "auras" && isCraftableAura(entry) && <span className="book-badge" style={{ color: "#F7F917" }}>Crafting</span>}
                  {section === "auras" && isPotionAura(entry) && <span className="book-badge" style={{ color: "#F554EF" }}>Potion</span>}
                  {section === "gauntlets" && (entry.slot || entry.hand) && <span className="book-badge" style={{ color: "#a78bfa" }}>{entry.slot || entry.hand}</span>}
                  {section === "gauntlets" && entry.limited && <span className="book-badge" style={{ color: "#21FF11" }}>Event / Limited</span>}
                  {section === "items" && entry.category && <span className="book-badge" style={{ color: "#38bdf8" }}>{entry.category}</span>}
                </div>
                <div style={{ color: "#94a3b8", fontSize: 12 }}>{sourceLabel(entry._metadata_source || entry.metadata_source)}{detailLoading ? " · loading Fandom article…" : ""}</div>
              </div>
            </div>

            {(section === "auras" || section === "biomes") && (
              <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                <button className={`btn ${detailTab === "info" ? "btn-accent" : ""}`} style={{ padding: "6px 16px", borderRadius: "4px" }} onClick={() => setDetailTab("info")}>ℹ Info</button>
                <button className={`btn ${detailTab === "media" ? "btn-accent" : ""}`} style={{ padding: "6px 16px", borderRadius: "4px" }} onClick={() => setDetailTab("media")}>🎞 Media{(() => { const n = section === "auras" ? auraImageUrls.length + (auraVideoUrl ? 1 : 0) : biomeImageUrls.length + (biomeMusicUrl ? 1 : 0); return n ? ` (${n})` : ""; })()}</button>
              </div>
            )}

            {detailTab === "media" && section === "auras" ? (
              <AuraMediaViewer urls={auraImageUrls} videoUrl={auraVideoUrl} videoKind={auraVideoKind} cutsceneNote={auraCutsceneNote} musicUrl={auraMusicUrl} musicFile={auraMusicFile} name={prettyName(selected)} accent={accent} />
            ) : detailTab === "media" && section === "biomes" ? (
              <AuraMediaViewer urls={biomeImageUrls} videoUrl="" videoKind="" cutsceneNote="" musicUrl={biomeMusicUrl} musicFile={biomeMusicFile} name={prettyName(selected)} accent={accent} />
            ) : section === "gauntlets" ? <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10, marginBottom: 16 }}>
                <Fact label="Gear Slot" value={entry.slot || entry.hand || "Right Hand"} />
                <Fact label="Type" value={entry.limited ? "Event / Limited" : "Craftable"} />
                <Fact label="Source" value={entry.raw_info?.source || entry.how_to_get?.split("|")[0]?.trim() || "Jake's Workshop"} />
              </div>
              {entry.usage && (
                <div className="book-card" style={{ marginBottom: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>⚡ Boosts & Effects</h4>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: "#f8fafc", lineHeight: 1.5 }}>{entry.usage}</div>
                </div>
              )}
              {entry.raw_info?.recipe && (
                <div className="book-card" style={{ marginBottom: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>🔨 Crafting Recipe</h4>
                  <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>{entry.raw_info.recipe}</div>
                </div>
              )}
              <div className="book-card" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>📖 Overview</h4>
                <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>{entry.description || "No overview available."}</div>
              </div>
            </> : section === "items" ? <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10, marginBottom: 16 }}>
                <Fact label="Category" value={entry.category || "Item"} />
                <Fact label="Type" value="Consumable / Material" />
              </div>
              {entry.usage && (
                <div className="book-card" style={{ marginBottom: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>⚡ Effect / Usage</h4>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: "#f8fafc", lineHeight: 1.5 }}>{entry.usage}</div>
                </div>
              )}
              {entry.how_to_get && (
                <div className="book-card" style={{ marginBottom: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>🗺 Obtainment / Crafting</h4>
                  <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>{entry.how_to_get}</div>
                </div>
              )}
              <div className="book-card" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>📝 Description</h4>
                <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>{entry.description || "No description provided."}</div>
              </div>
            </> : section === "biomes" ? <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10, marginBottom: 18 }}>
                <Fact label="Rarity / spawn" value={entry.spawn_chance || "Unknown"} />
                <Fact label="Duration" value={entry.duration || "Unknown"} />
                <Fact label="Biome Message" value={entry.chat_message || "Doesn't post a chat message on spawn"} />
              </div>
              <Section title="Chronicle"><p style={{ lineHeight: 1.7, color: "var(--text-secondary)", fontSize: 13 }}>{entry.description || entry.how_to_get || "No extended description is available for this entry yet."}</p></Section>
              {entry.thumbnail_url && <Section title="In-game preview"><div><CachedThumb url={String(entry.thumbnail_url)} alt={String(selected)} style={{ maxWidth: "100%", maxHeight: 170, objectFit: "contain", background: "rgba(255,255,255,.04)", borderRadius: 4 }} /></div></Section>}
              {Array.isArray((entry as any).gallery) && (entry as any).gallery.length > 0 && <Section title="Gallery">
                <div style={{ display: "grid", gap: 12 }}>
                  {(entry as any).gallery.map((g: any, i: number) => (
                    <div key={i}>
                      <CachedThumb url={String(g?.url || "")} alt={String(g?.caption || `Gallery ${i + 1}`)} style={{ maxWidth: "100%", maxHeight: 200, objectFit: "contain", background: "rgba(255,255,255,.04)", borderRadius: 4 }} />
                      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>{String(g?.caption || "")}</div>
                    </div>
                  ))}
                </div>
              </Section>}
              {entry.music_url && <Section title="🎵 Theme music"><CachedAudio url={String(entry.music_url)} /></Section>}
              {entry.exclusive_auras && <Section title="Exclusive auras"><p style={{ color: "var(--text-secondary)", fontSize: 13 }}>{Array.isArray(entry.exclusive_auras) ? entry.exclusive_auras.join(", ") : String(entry.exclusive_auras)}</p></Section>}
            </> : <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10, marginBottom: 18 }}>
                <Fact label="Rarity class" value={rarityClassFull(entry.rarity_name, entry.rarity)} />
                <Fact label="Rarity" value={auraRarityText(entry)} />
                <Fact label="Obtainment" value={obtainmentLabel(entry)} />
              </div>
              <Section title={entry.is_exclusive ? "Exclusive world" : "Native world"}><p style={{ color: "var(--text-secondary)", lineHeight: 1.7, fontSize: 13 }}>{entry.is_exclusive && entry.exclusive_biomes?.length ? `Exclusive to ${entry.exclusive_biomes.map(prettyName).join(", ")}` : entry.native_biome && entry.native_biome[0] !== "None" ? `${prettyName(entry.native_biome[0])} · native rarity ${entry.native_rarity ? `1 in ${fmtNum(entry.native_rarity)}` : `×${entry.native_biome[1] ?? 1}`}` : "Global / no native biome recorded."}</p></Section>
              <Section title="Archive notes"><p style={{ color: "var(--text-secondary)", lineHeight: 1.7, fontSize: 13 }}>{entry.description || entry.notes || "This aura is catalogued from the available reference data."}</p></Section>
              {(auraImageUrls.length > 0 || auraVideoUrl) && <div className="form-hint" style={{ marginTop: 10 }}>🖼 {auraImageUrls.length + (auraVideoUrl ? 1 : 0)} media file(s) available — open the <b>Media</b> tab to view them without slowing the book down.</div>}
            </>}
          </>}
        </div>
      </div>
    </div>
  </div>;
}

function mediaFileName(url: string): string {
  try {
    const path = url.split("?")[0].split("#")[0];
    const name = decodeURIComponent(path.replace(/\/revision\/latest$/i, "").replace(/\/$/, "").split("/").pop() || "");
    return name || "media";
  } catch { return "media"; }
}

async function saveMedia(url: string, setStatus: (s: string) => void) {
  setStatus("Saving…");
  try {
    const res = await window.pywebview?.api?.download_media?.(url, mediaFileName(url));
    if (res?.success) setStatus(`Saved → ${res.path}`);
    else if (res?.cancelled) setStatus("Save cancelled");
    else setStatus(res?.error || "Save failed");
  } catch (e) { setStatus(`Save failed: ${e}`); }
}

function useCachedMedia(remoteUrl?: string): { src: string; state: "idle" | "loading" | "ready" | "failed" } {
  const [src, setSrc] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "ready" | "failed">("idle");
  useEffect(() => {
    setSrc("");
    if (!remoteUrl) { setState("idle"); return; }
    let alive = true;
    setState("loading");
    window.pywebview?.api?.ensure_media_cached?.(remoteUrl).then((res: Record<string, any>) => {
      if (!alive) return;
      if (res && res.success && res.local_url) { setSrc(String(res.local_url)); setState("ready"); }
      else setState("failed");
    }).catch(() => { if (alive) setState("failed"); });
    return () => { alive = false; };
  }, [remoteUrl]);
  return { src, state };
}

function CachedImage({ url, alt, style, onClick }: { url?: string; alt?: string; style?: React.CSSProperties; onClick?: () => void }) {
  const { src } = useCachedMedia(url || undefined);
  const [failed, setFailed] = useState(false);
  if (!url) return null;
  const effective = (!failed && src) ? src : url;
  return (
    <img
      src={effective}
      alt={alt}
      onClick={onClick}
      loading="lazy"
      decoding="async"
      draggable={false}
      referrerPolicy="no-referrer"
      onError={() => { if (src) setFailed(true); }}
      style={{ display: "block", ...style }}
    />
  );
}

function CachedThumb({ url, alt, style }: { url?: string; alt?: string; style?: React.CSSProperties }) {
  const [previewSrc, setPreviewSrc] = useState<string>("");
  useEffect(() => {
    setPreviewSrc("");
    if (!url) return;
    let alive = true;
    window.pywebview?.api?.ensure_media_thumbnail?.(url).then((res: Record<string, any>) => {
      if (!alive) return;
      if (res && res.success && res.local_url) setPreviewSrc(String(res.local_url));
    }).catch(() => {});
    return () => { alive = false; };
  }, [url]);

  return <CachedImage url={previewSrc || url} alt={alt} style={style} />;
}

function CachedAudio({ url, fileLabel, accent }: { url: string; fileLabel?: string; accent?: string }) {
  const { src, state } = useCachedMedia(url);
  const audioSrc = src || url;
  const [saveState, setSaveState] = useState("");
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, fontSize: 12, color: "var(--text-secondary)" }}>
        <span>{fileLabel ? `🎵 ${prettyName(fileLabel)}` : "🎵 Theme music"}</span>
        <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, opacity: .75 }}>
          {state === "loading" ? "Fetching from wiki…" : state === "ready" ? "✓ Cached" : state === "failed" ? "Wiki stream" : ""}
          {saveState ? <span>{saveState}</span> : null}
          <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => void saveMedia(url, setSaveState)} title="Save file to disk">💾</button>
        </span>
      </div>
      <audio controls src={audioSrc} preload="none" style={{ width: "100%", height: 32, accentColor: accent }} />
    </div>
  );
}

function AuraMediaViewer({ urls, videoUrl, videoKind, cutsceneNote, musicUrl, musicFile, name, accent }: { urls: string[]; videoUrl?: string; videoKind?: string; cutsceneNote?: string; musicUrl?: string; musicFile?: string; name: string; accent: string }) {
  type MediaItem = { kind: "image" | "video"; url: string; remoteUrl?: string };
  const videoCached = useCachedMedia(videoUrl || undefined);
  const [videoFallback, setVideoFallback] = useState(false);
  const videoSrc = (!videoFallback && videoCached.src) ? videoCached.src : (videoUrl || "");
  const items: MediaItem[] = [
    ...urls.map(u => ({ kind: "image" as const, url: u })),
    ...(videoSrc ? [{ kind: "video" as const, url: videoSrc, remoteUrl: videoUrl || "" }] : []),
  ];
  const [idx, setIdx] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isFull, setIsFull] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const listKey = urls.join("|") + "|" + (videoSrc || "");
  const [saveState, setSaveState] = useState("");

  useEffect(() => { setIdx(0); setZoom(1); setPan({ x: 0, y: 0 }); setIsFull(false); setVideoFallback(false); }, [listKey]);

  useEffect(() => {
    if (!isFull) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setIsFull(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isFull]);

  if (!items.length && !musicUrl) {
    return <div className="form-hint" style={{ padding: 18 }}>No media available for this entry.</div>;
  }

  const active = items[Math.min(idx, Math.max(0, items.length - 1))];

  const onWheel = (e: React.WheelEvent) => {
    if (active?.kind !== "image") return;
    e.preventDefault();
    const factor = e.deltaY < 0 ? 1.15 : 0.87;
    setZoom(z => Math.max(0.5, Math.min(4, Number((z * factor).toFixed(2)))));
  };

  const onDragStart = (e: React.MouseEvent) => {
    if (active?.kind !== "image" || zoom <= 1) return;
    setIsDragging(true);
    dragRef.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
  };
  const onDragMove = (e: React.MouseEvent) => {
    if (!isDragging || !dragRef.current) return;
    setPan({
      x: dragRef.current.panX + (e.clientX - dragRef.current.x),
      y: dragRef.current.panY + (e.clientY - dragRef.current.y),
    });
  };
  const endDrag = () => { setIsDragging(false); dragRef.current = null; };

  const mediaEl = () => !active ? null : active.kind === "video" ? (
    <video
      key={active.url}
      src={active.url}
      controls
      preload="metadata"
      onError={() => { if (!videoFallback && videoCached.src) setVideoFallback(true); }}
      style={{ width: "100%", height: "100%", objectFit: "contain", background: "rgba(0,0,0,.4)" }}
    />
  ) : (
    <CachedImage
      key={active.url}
      url={active.url}
      alt={`${name} media ${idx + 1}`}
      style={{
        width: "100%",
        height: "100%",
        objectFit: "contain",
        transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
        transformOrigin: "center center",
        transition: isDragging ? "none" : "transform .12s ease-out",
        userSelect: "none",
      }}
    />
  );

  const controlsRow = (fullscreen: boolean) => (
    <div style={{
      position: "absolute", top: 10, right: 10, display: "flex", gap: 6, zIndex: 10,
      background: "rgba(10,8,20,.72)", padding: "4px 6px", borderRadius: 4, backdropFilter: "blur(4px)",
    }}>
      {active?.kind === "image" && <>
        <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => setZoom(z => Math.max(0.5, Number((z - 0.25).toFixed(2))))}>−</button>
        <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => { setZoom(1); setPan({ x: 0, y: 0 }); }}>{Math.round(zoom * 100)}%</button>
        <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => setZoom(z => Math.min(4, Number((z + 0.25).toFixed(2))))}>+</button>
      </>}
      {active && <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => void saveMedia(active.remoteUrl || active.url, setSaveState)} title="Save file to disk">💾</button>}
      <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => setIsFull(!fullscreen)} title={fullscreen ? "Exit fullscreen" : "Fullscreen"}>
        {fullscreen ? "✕" : "⛶"}
      </button>
    </div>
  );

  const captionRow = () => !items.length ? null : (
    <div style={{
      position: "absolute", bottom: 10, left: 10, right: 10, display: "flex", justifyContent: "space-between",
      alignItems: "center", background: "rgba(10,8,20,.72)", padding: "4px 10px", borderRadius: 4, fontSize: 12,
      backdropFilter: "blur(4px)", color: "var(--text-secondary)", pointerEvents: "auto",
    }}>
      <span>{active.kind === "video" ? (videoKind === "opening" ? "Opening cutscene" : "Cutscene video") : `Image ${idx + 1} of ${items.length}`}</span>
      {items.length > 1 && (
        <div style={{ display: "flex", gap: 6 }}>
          <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => { setIdx((idx - 1 + items.length) % items.length); setZoom(1); setPan({ x: 0, y: 0 }); }}>‹ Prev</button>
          <button className="btn" style={{ padding: "2px 8px", fontSize: 12 }} onClick={() => { setIdx((idx + 1) % items.length); setZoom(1); setPan({ x: 0, y: 0 }); }}>Next ›</button>
        </div>
      )}
    </div>
  );

  return (
    <div>
      <div className="book-panel" style={{ position: "relative", background: "rgba(0,0,0,.35)", overflow: "hidden", height: 340, cursor: active.kind === "image" && zoom > 1 ? "grab" : "default", borderRadius: "6px" } as React.CSSProperties}
        onWheel={onWheel} onMouseDown={onDragStart} onMouseMove={onDragMove} onMouseUp={endDrag} onMouseLeave={endDrag}>
        {mediaEl()}
        {controlsRow(false)}
        {captionRow()}
      </div>

      {videoUrl && (
        <div style={{ marginTop: 6, fontSize: 12, color: "var(--text-secondary)" }}>
          {videoCached.state === "loading" ? "⏳ Preparing the video from the wiki (cached for reliable playback)…"
            : videoCached.state === "ready" ? "✓ Playing from local cache — works offline"
            : videoCached.state === "failed" ? "⚠ Could not cache — playing directly from the wiki"
            : ""}
          {saveState ? ` · ${saveState}` : ""}
        </div>
      )}

      {cutsceneNote && (
        <div style={{ marginTop: 6, fontSize: 12, color: "var(--text-secondary)", lineHeight: 1.5 }}>
          {cutsceneNote}
        </div>
      )}

      {musicUrl && (
        <div className="book-panel" style={{ marginTop: 12, padding: "10px 12px", borderRadius: "6px" } as React.CSSProperties}>
          <CachedAudio url={musicUrl} fileLabel={musicFile} accent={accent} />
        </div>
      )}

      {items.length > 1 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          {items.map((item, i) => (
            <button key={item.kind + item.url} onClick={() => { setIdx(i); setZoom(1); setPan({ x: 0, y: 0 }); }}
              style={{ padding: 0, position: "relative", border: i === idx ? `2px solid ${accent}` : "2px solid transparent", background: "rgba(255,255,255,.06)", cursor: "pointer", lineHeight: 0, borderRadius: "4px", overflow: "hidden" }}>
              <CachedThumb url={item.url} alt={`${name} media ${i + 1}`}
                style={{ width: 64, height: 64, objectFit: "contain", background: "rgba(255,255,255,.05)" }} />
              {item.kind === "video" && (
                <span style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", fontSize: 20, color: "#fff", background: "rgba(0,0,0,.35)" }}>▶</span>
              )}
            </button>
          ))}
        </div>
      )}

      {isFull && (
        <div
          onClick={() => setIsFull(false)}
          style={{ position: "fixed", inset: 0, zIndex: 10000, background: "rgba(0,0,0,.94)", padding: 20 }}
        >
          <div style={{ position: "relative", width: "100%", height: "100%" }} onClick={(e) => e.stopPropagation()}>
            <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}
              onWheel={onWheel} onMouseDown={onDragStart} onMouseMove={onDragMove} onMouseUp={endDrag} onMouseLeave={endDrag}>
              {mediaEl()}
            </div>
            {controlsRow(true)}
            {captionRow()}
          </div>
        </div>
      )}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: any }) {
  return <div className="book-panel" style={{ padding: "10px 12px", background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: "4px" }}>
    <div style={{ color: "#a78bfa", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 4, fontWeight: 600 }}>{label}</div>
    <div style={{ color: "#f8fafc", lineHeight: 1.4, fontSize: 13, fontWeight: 500 }}>{String(value || "Unknown")}</div>
  </div>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <div style={{ marginTop: 16 }}>
    <h4 style={{ color: "#a78bfa", margin: "0 0 6px", letterSpacing: ".06em", fontSize: 12, textTransform: "uppercase", fontWeight: 600 }}>{title}</h4>
    {children}
  </div>;
}
