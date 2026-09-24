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
 * display, sourced from the wiki's Module:Rarity/data (verified 2026-09-21).
 * Dev Exclusive is dark purple per owner request. Shimmer/gradient text
 * classes live in App.css (.rarity-text--*).
 */
const RARITY_COLORS: Record<string, string> = {
  "Basic": "#FFFFFF",          // white, black outline (inventory)
  "Epic": "#C57ED3",           // orchid
  "Unique": "#BE7418",         // bronze
  "Legendary": "#F7F917",      // yellow
  "Mythic": "#F554EF",         // magenta
  "Exalted": "#3F62D8",        // blue
  "Glorious": "#C52425",       // red gradient in inventory (#C52425->#9D1514)
  "Transcendent": "#7EC8FF",   // blue shimmer
  "Challenged": "#E8E8E8",     // black/white shimmer
  "Challenged+": "#E8E8E8",    // black/white shimmer
  "Event": "#21FF11",          // green
  "Dev Exclusive": "#5B2AA8",  // dark purple (owner request)
  "Other": "#8d88a8",          // muted
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
  if (!info) return "#8d88a8";
  if (info.color) return normColor(info.color);
  const type = entryRarityType(info);
  // Event auras are colored by their actual numeric tier (like the
  // inventory); the EVENT badge marks them as event on top.
  if (type === "Event" && isEventAura(info)) {
    const tier = canonicalRarity(rarityClass(info?.rarity));
    return RARITY_COLORS[tier] || RARITY_COLORS["Event"];
  }
  return RARITY_COLORS[type] || "#8d88a8";
};

const auraFlags = (e: Entry | null | undefined) => Array.isArray(e?.flags) ? e.flags : [];
/** Event auras: wiki "Event" rarity class, the limited flag, or the field. */
const isEventAura = (e: Entry | null | undefined) =>
  !!e && (entryRarityType(e) === "Event" || auraFlags(e).includes("limited") || !!e.limited);
/** Crafted auras: real Workshop recipes (craftable flag, not potion-only). */
const isCraftableAura = (e: Entry | null | undefined) =>
  !!e && auraFlags(e).includes("craftable") && !e.rarity_is_potion;
/** Potion-only auras: obtained by drinking a potion, not by crafting. */
const isPotionAura = (e: Entry | null | undefined) => !!e && !!e.rarity_is_potion;

/** Canonical display order for aura rarity types (rare → special, Other last). */
const RARITY_ORDER = [
  "Basic", "Epic", "Unique", "Legendary", "Mythic", "Exalted", "Glorious",
  "Transcendent", "Challenged", "Challenged+", "Event", "Dev Exclusive",
];

/**
 * THE LIMBO is a dimension, not a weather biome, but it hosts its own auras
 * and mechanics - shown inside the Biomes chapter as its own entry. Images
 * are live Fandom files (loaded through the media cache) with captions.
 */
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

/** Normalize rarity/type names: dedupes UNIQUE/Unique, CHALLENGED/Challenged… */
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

/** Effective rarity type for an entry (wiki name first, numeric fallback). */
const entryRarityType = (info: Entry) =>
  canonicalRarity(info?.category || info?.rarity_name || rarityClass(info?.rarity));

/**
 * Full rarity class name including condition-based classes.
 * Challenged/Challenged+ are not tied to a number — they're tied to
 * obtainment conditions (specific challenge requirements).
 * Use this when the wiki provides rarity_name.
 */
const obtainmentLabel = (entry: Entry) => {
  if (entry?.obtainment) return String(entry.obtainment);
  const native = entry?.native_biome;
  if (entry?.is_exclusive && Array.isArray(entry.exclusive_biomes) && entry.exclusive_biomes.length) return `Exclusive to ${entry.exclusive_biomes.join(", ")} (obtainment not verified)`;
  if (Array.isArray(native) && native[0] && native[0] !== "None") return `Native to ${native[0]} (obtainment not verified)`;
  const exclusive = entry?.exclusive_biome;
  if (Array.isArray(exclusive) && exclusive[0] && exclusive[0] !== "None") return `Exclusive to ${exclusive[0]} (obtainment not verified)`;
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

/** Wiki keys use underscores for spaces/colons — show human names. */
const prettyName = (key: any) => String(key ?? "").replace(/_/g, " ").trim();

const SOURCE_LABELS: Record<string, string> = {
  fandom: "Fandom wiki (live)",
  fandom_article: "Fandom article (verified)",
  fandom_cache: "Fandom wiki (cached)",
  fandom_snapshot: "Fandom wiki (offline snapshot)",
  fandom_detail: "Fandom article",
};

const sourceLabel = (value: any) => {
  const key = String(value ?? "");
  return SOURCE_LABELS[key] || key || "Project reference data";
};

/** Human rarity line: native chance first (the banner number), then global. */
const auraRarityText = (e: Entry) => {
  if (!e) return "Unknown";
  // Crafted/potion auras: the stored number is the potion chance, never a
  // global roll chance — "1 in 1000 anywhere" would mislead. Obtainment
  // already lists every potion source with its exact chance.
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
  // Exclusive auras cannot be rolled "anywhere" — never show a global chance.
  if (!e.is_exclusive && Number.isFinite(global) && global > 0 && (!Number.isFinite(native) || global !== native)) {
    parts.push(`1 in ${fmtNum(global)} anywhere`);
  }
  if (!parts.length && Number.isFinite(global) && global > 0) parts.push(`1 in ${fmtNum(global)}`);
  if (e.is_exclusive) parts.push("exclusive");
  return parts.join(" · ") || "Unknown";
};

/**
 * Searchable text for an entry: ONLY the name and the biome associations
 * (exclusive/native worlds + the short obtainment line, which names its
 * biome). Descriptions are intentionally excluded so searching "Glitched"
 * doesn't return auras that merely mention "glitch" in their lore text.
 */
const searchableText = (name: string, info: Entry) => {
  const bits = [prettyName(name)];
  const excl = Array.isArray(info?.exclusive_biomes) ? info.exclusive_biomes : [];
  if (excl.length) bits.push(...excl.map(prettyName));
  const exclRaw = Array.isArray(info?.exclusive_biome) ? info.exclusive_biome : [];
  if (exclRaw[0] && exclRaw[0] !== "None") bits.push(prettyName(exclRaw[0]));
  const native = Array.isArray(info?.native_biome) ? info.native_biome : [];
  if (native[0] && native[0] !== "None") bits.push(prettyName(native[0]));
  if (info?.obtainment) bits.push(String(info.obtainment));
  return bits.join(" ").toLowerCase();
};

export default function SolsBookPage() {
  const [biomes, setBiomes] = useState<MapData>({});
  const [auras, setAuras] = useState<MapData>({});
  const [section, setSection] = useState<"biomes" | "auras">("biomes");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [sourceStatus, setSourceStatus] = useState<any>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  // Inner detail tabs for auras: Media is lazy — nothing is loaded until opened
  const [detailTab, setDetailTab] = useState<"info" | "media">("info");

  const load = async () => {
    setLoading(true);
    try {
      const [biomeData, auraData, sourceData] = await Promise.all([
        window.pywebview?.api?.get_full_biome_data?.(),
        window.pywebview?.api?.get_full_aura_data?.(),
        window.pywebview?.api?.get_data_source_status?.(),
      ]);
      if (biomeData && typeof biomeData === "object") {
        // THE LIMBO is a dimension, not a weather biome - synthesize its
        // entry in the Biomes chapter, collecting its exclusive auras from
        // the loaded aura data (static fallback keeps it useful offline).
        const limboAuras = Object.entries(auraData || {})
          .filter(([, v]) => /limbo/i.test(String((v as any)?.obtainment || ""))
            || /limbo/i.test(JSON.stringify((v as any)?.exclusive_biomes || "")))
          .map(([n]) => prettyName(n));
        setBiomes({ ...biomeData, "THE LIMBO": THE_LIMBO_ENTRY(limboAuras.length ? limboAuras : LIMBO_EXCLUSIVE_FALLBACK) });
      }
      if (auraData && typeof auraData === "object") setAuras(auraData);
      if (sourceData && typeof sourceData === "object") setSourceStatus(sourceData);
    } finally { setLoading(false); }
  };

  useEffect(() => { void load(); }, []);

  const data = section === "biomes" ? biomes : auras;
  const categories = useMemo(() => {
    const set = new Map<string, string>();
    Object.values(data).forEach(item => {
      const value = entryRarityType(item);
      set.set(value.toLowerCase(), value);
    });
    const list = Array.from(set.values());
    // Rarity order (rare → special); everything unknown goes last as "Other"
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
  // Aura media is ONLY touched inside the Media tab (lazy → no preload lag)
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

  // Biome media mirrors the aura pipeline: Fandom gallery images (fetched
  // lazily per selection) + the biome theme music, rendered by the same
  // zoomable viewer. THE LIMBO keeps its hardcoded gallery — the detail
  // fetch only merges on success.
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

  // Reset the detail tab whenever the entry or the section changes
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
          <p>Field almanac of Sol’s RNG — biomes, aura classes, native worlds, and the stories behind every roll.</p>
        </div>
        <button className="btn" onClick={() => void load()} disabled={loading}>{loading ? "Updating…" : "↻ Refresh"}</button>
      </div>
    </div>

    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <div className="book-panel" style={{ padding: "24px 26px" }}>
        <div style={{ color: "#c9c2ff", fontSize: 11, letterSpacing: ".18em", textTransform: "uppercase" }}>The EndSol reference archive</div>
        <h3 style={{ fontSize: 26, margin: "8px 0 4px" }}>The Almanac of Chance</h3>
        <div style={{ color: "#a9a5c5", maxWidth: 760, lineHeight: 1.55 }}>Explore the weather that shapes every roll and the auras hidden inside it. Entries are loaded from the project’s Fandom-compatible knowledge source and marked when local fallback data is being used.</div>
        {sourceStatus && <div className="book-panel" style={{ marginTop: 12, display: "grid", gap: 6, padding: "9px 12px", fontSize: 12 }}><div style={{ color: sourceStatus.biome?.error ? "#fca5a5" : "#bbf7d0" }}>Biomes: <b>{sourceStatus.biome?.source || "unknown"}</b>{sourceStatus.biome?.error ? ` — ${sourceStatus.biome.error}` : ""}</div><div style={{ color: sourceStatus.aura?.error ? "#fca5a5" : "#bbf7d0" }}>Auras: <b>{sourceStatus.aura?.source || "unknown"}</b>{sourceStatus.aura?.error ? ` — ${sourceStatus.aura.error}` : ""}</div></div>}
        <div style={{ display: "flex", gap: 10, marginTop: 18, flexWrap: "wrap" }}>
          <div className="book-chip"><b>{Object.keys(biomes).length}</b> biomes</div>
          <div className="book-chip"><b>{Object.keys(auras).length}</b> auras</div>
          <div className="book-chip">Source-aware entries</div>
        </div>
      </div>

      <div style={{ padding: "14px 18px", borderTop: "1px solid rgba(255,255,255,.08)", borderBottom: "1px solid rgba(255,255,255,.08)", display: "flex", gap: 10, flexWrap: "wrap", alignItems: "center" }}>
        <button className={`btn ${section === "biomes" ? "btn-accent" : ""}`} onClick={() => { setSection("biomes"); setCategory("all"); }}>☁ Biomes</button>
        <button className={`btn ${section === "auras" ? "btn-accent" : ""}`} onClick={() => { setSection("auras"); setCategory("all"); }}>✧ Auras</button>
        <input className="form-input" style={{ minWidth: 220, flex: 1, maxWidth: 360 }} value={query} onChange={e => setQuery(e.target.value)} placeholder={section === "auras" ? "Search aura or biome name (e.g. Glitched)…" : "Search biomes…"} />
        <select className="form-input" style={{ maxWidth: 190 }} value={category} onChange={e => setCategory(e.target.value)}>
          <option value="all">All chapters</option>
          {categories.map(value => <option key={value} value={value}>{value}</option>)}
        </select>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(230px, .9fr) minmax(0, 1.6fr)", minHeight: 480 }}>
        <div style={{ padding: 14, borderRight: "1px solid rgba(255,255,255,.08)", maxHeight: 620, overflow: "auto" }}>
          {loading && <div className="form-hint" style={{ padding: 18 }}>Opening the archive…</div>}
          {!loading && !entries.length && <div className="form-hint" style={{ padding: 18 }}>No entries match this search.</div>}
          {entries.map(([name, info]) => {
            const active = name === selected;
            const color = entryAccent(info, section);
            const isEvent = section === "auras" && isEventAura(info);
            const itemStyle = active
              ? ({ "--item-color": color, "--item-bg": `${color}1f`, "--item-border": `${color}8c` } as React.CSSProperties)
              : isEvent
              ? ({ border: "1px dashed rgba(33,255,17,.4)" } as React.CSSProperties)
              : undefined;
            return <button key={name} onClick={() => setSelected(name)} className={`book-item${active ? " book-item--active" : ""}`} style={itemStyle}>
              <span style={{ width: 10, height: 10, borderRadius: "50%", background: color, boxShadow: `0 0 12px ${color}`, flex: "0 0 auto" }} />
              <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{prettyName(name)}</span>
            </button>;
          })}
        </div>

        <div style={{ padding: "28px clamp(18px, 4vw, 44px)", background: "rgba(255,255,255,.018)" }}>
          {!entry && <div className="form-hint">Select an entry from the archive.</div>}
          {entry && <>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 16, borderBottom: `1px solid ${accent}66`, paddingBottom: 18, marginBottom: 18 }}>
              <div className="book-panel" style={{ width: 58, height: 58, display: "grid", placeItems: "center", fontSize: 28, flex: "0 0 auto", "--panel-corner": accent } as React.CSSProperties}>{section === "biomes" ? "☁" : "✧"}</div>
              <div style={{ flex: 1 }}>
                <div className={rarityTextClass(entryRarityType(entry))} style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".16em", ...(rarityTextClass(entryRarityType(entry)) ? {} : { color: accent }) }}>{entryRarityType(entry)}</div>
                <div style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
                  <h3 style={{ margin: "5px 0 4px", fontSize: 25 }}>{entry?.name ? String(entry.name) : prettyName(selected)}</h3>
                  {section === "auras" && isEventAura(entry) && <span className="book-badge" style={{ color: "#21FF11" }}>Event</span>}
                  {section === "auras" && isCraftableAura(entry) && <span className="book-badge" style={{ color: "#F7F917" }}>Crafting</span>}
                  {section === "auras" && isPotionAura(entry) && <span className="book-badge" style={{ color: "#F554EF" }}>Potion</span>}
                </div>
                <div style={{ color: "#9d99b8", fontSize: 12 }}>{sourceLabel(entry._metadata_source || entry.metadata_source)}{detailLoading ? " · loading Fandom article…" : ""}</div>
              </div>
            </div>

            {(
              <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                <button className={`btn ${detailTab === "info" ? "btn-accent" : ""}`} style={{ padding: "6px 16px" }} onClick={() => setDetailTab("info")}>ℹ Info</button>
                <button className={`btn ${detailTab === "media" ? "btn-accent" : ""}`} style={{ padding: "6px 16px" }} onClick={() => setDetailTab("media")}>🎞 Media{(() => { const n = section === "auras" ? auraImageUrls.length + (auraVideoUrl ? 1 : 0) : biomeImageUrls.length + (biomeMusicUrl ? 1 : 0); return n ? ` (${n})` : ""; })()}</button>
              </div>
            )}

            {detailTab === "media" && section === "auras" ? (
              <AuraMediaViewer urls={auraImageUrls} videoUrl={auraVideoUrl} videoKind={auraVideoKind} cutsceneNote={auraCutsceneNote} musicUrl={auraMusicUrl} musicFile={auraMusicFile} name={prettyName(selected)} accent={accent} />
            ) : detailTab === "media" && section === "biomes" ? (
              <AuraMediaViewer urls={biomeImageUrls} videoUrl="" videoKind="" cutsceneNote="" musicUrl={biomeMusicUrl} musicFile={biomeMusicFile} name={prettyName(selected)} accent={accent} />
            ) : section === "biomes" ? <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 10, marginBottom: 18 }}>
                <Fact label="Rarity / spawn" value={entry.spawn_chance || "Unknown"} />
                <Fact label="Duration" value={entry.duration || "Unknown"} />
                <Fact label="Biome Message" value={entry.chat_message || "Doesn't post a chat message on spawn"} />
              </div>
              <Section title="Chronicle"><p style={{ lineHeight: 1.7, color: "var(--text-secondary)" }}>{entry.description || entry.how_to_get || "No extended description is available for this entry yet."}</p></Section>
              {entry.thumbnail_url && <Section title="In-game preview"><div><CachedThumb url={String(entry.thumbnail_url)} alt={String(selected)} style={{ maxWidth: "100%", maxHeight: 170, objectFit: "contain", background: "rgba(255,255,255,.06)" }} /></div></Section>}
              {Array.isArray((entry as any).gallery) && (entry as any).gallery.length > 0 && <Section title="Gallery">
                <div style={{ display: "grid", gap: 12 }}>
                  {(entry as any).gallery.map((g: any, i: number) => (
                    <div key={i}>
                      <CachedThumb url={String(g?.url || "")} alt={String(g?.caption || `Gallery ${i + 1}`)} style={{ maxWidth: "100%", maxHeight: 200, objectFit: "contain", background: "rgba(255,255,255,.06)" }} />
                      <div style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 4 }}>{String(g?.caption || "")}</div>
                    </div>
                  ))}
                </div>
              </Section>}
              {entry.music_url && <Section title="🎵 Theme music"><CachedAudio url={String(entry.music_url)} /></Section>}
              {entry.exclusive_auras && <Section title="Exclusive auras"><p style={{ color: "var(--text-secondary)" }}>{Array.isArray(entry.exclusive_auras) ? entry.exclusive_auras.join(", ") : String(entry.exclusive_auras)}</p></Section>}
            </> : <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(150px,1fr))", gap: 10, marginBottom: 18 }}>
                <Fact label="Rarity class" value={rarityClassFull(entry.rarity_name, entry.rarity)} />
                <Fact label="Rarity" value={auraRarityText(entry)} />
                <Fact label="Obtainment" value={obtainmentLabel(entry)} />
              </div>
              <Section title={entry.is_exclusive ? "Exclusive world" : "Native world"}><p style={{ color: "var(--text-secondary)", lineHeight: 1.7 }}>{entry.is_exclusive && entry.exclusive_biomes?.length ? `Exclusive to ${entry.exclusive_biomes.map(prettyName).join(", ")}` : entry.native_biome && entry.native_biome[0] !== "None" ? `${prettyName(entry.native_biome[0])} · native rarity ${entry.native_rarity ? `1 in ${fmtNum(entry.native_rarity)}` : `×${entry.native_biome[1] ?? 1}`}` : "Global / no native biome recorded."}</p></Section>
              <Section title="Archive notes"><p style={{ color: "var(--text-secondary)", lineHeight: 1.7 }}>{entry.description || entry.notes || "This aura is catalogued from the available reference data."}</p></Section>
              {(auraImageUrls.length > 0 || auraVideoUrl) && <div className="form-hint" style={{ marginTop: 10 }}>🖼 {auraImageUrls.length + (auraVideoUrl ? 1 : 0)} media file(s) available — open the <b>Media</b> tab to view them without slowing the book down.</div>}
            </>}
          </>}
        </div>
      </div>
    </div>
  </div>;
}

/** Extract a human file name from a Fandom media URL (for Save-As). */
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

/**
 * Media source backed by the Python media cache. Fandom's CDN 403-challenges
 * the WebView's own <video>/<audio> requests (a file:// page cannot send a
 * Referer), so the file is fetched by Python (browser headers, paced, retried)
 * and played back as a local file. Falls back to the remote URL on failure.
 */
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

/** Image that loads through the Python media cache. The Fandom CDN
 * (Cloudflare) 403-challenges image requests without a Referer, and a
 * file:// page cannot send one — so aura GIFs never loaded directly from
 * the wiki. Python downloads them with browser headers (paced, retried,
 * 4 GB LRU cache) and the img plays back from a local file. Falls back to
 * the remote URL if caching fails. */
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
      style={style}
    />
  );
}

/**
 * Thumbnail source backed by the Python media cache. Lists/grids/galleries
 * get a small STATIC preview (first frame for GIFs) — rendering a wall of
 * full obtainment GIFs at once was eating GPU/CPU and dropping FPS. The
 * full animation is only loaded in the main viewer.
 */
function useCachedThumbnail(remoteUrl?: string): { src: string; state: "idle" | "loading" | "ready" | "failed" } {
  const [src, setSrc] = useState("");
  const [state, setState] = useState<"idle" | "loading" | "ready" | "failed">("idle");
  useEffect(() => {
    setSrc("");
    if (!remoteUrl) { setState("idle"); return; }
    let alive = true;
    setState("loading");
    const api = window.pywebview?.api;
    const req = api?.ensure_media_thumbnail
      ? api.ensure_media_thumbnail(remoteUrl)
      : api?.ensure_media_cached?.(remoteUrl);
    Promise.resolve(req).then((res: Record<string, any>) => {
      if (!alive) return;
      if (res && res.success && res.local_url) { setSrc(String(res.local_url)); setState("ready"); }
      else setState("failed");
    }).catch(() => { if (alive) setState("failed"); });
    return () => { alive = false; };
  }, [remoteUrl]);
  return { src, state };
}

/** Static-preview image for lists/galleries (falls back to the full file). */
function CachedThumb({ url, alt, style, onClick }: { url?: string; alt?: string; style?: React.CSSProperties; onClick?: () => void }) {
  const { src } = useCachedThumbnail(url || undefined);
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
      style={style}
    />
  );
}

/** Audio box with cache-backed playback and a working Save button. */function CachedAudio({ url, fileLabel }: { url?: string; fileLabel?: string; accent?: string }) {
  const { src, state } = useCachedMedia(url || undefined);
  const [saveState, setSaveState] = useState("");
  if (!url) return null;
  const effective = src || url;
  return (
    <div>
      {fileLabel ? (
        <div style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".08em", color: "#9994b8", marginBottom: 6 }}>🎵 Theme music{fileLabel ? ` — ${fileLabel}` : ""}</div>
      ) : null}
      <audio key={effective} src={effective} controls preload="none" style={{ width: "100%", maxWidth: 520, display: "block" }} />
      <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
        <button className="btn" style={{ padding: "4px 10px", fontSize: 12 }} onClick={() => void saveMedia(url, setSaveState)}>⬇ Save</button>
        <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
          {state === "loading" ? "⏳ Loading from the wiki…"
            : state === "ready" ? "✓ Playing from local cache"
            : state === "failed" ? "⚠ Cache failed — playing from the wiki directly"
            : ""}
          {saveState ? ` · ${saveState}` : ""}
        </span>
      </div>
    </div>
  );
}

/** Zoomable media viewer for an aura: cutscene video, theme music, gallery. */
function AuraMediaViewer({ urls, videoUrl, videoKind, cutsceneNote, musicUrl, musicFile, name, accent }: { urls: string[]; videoUrl?: string; videoKind?: string; cutsceneNote?: string; musicUrl?: string; musicFile?: string; name: string; accent: string }) {
  type MediaItem = { kind: "image" | "video"; url: string };
  const videoCached = useCachedMedia(videoUrl || undefined);
  const [videoFallback, setVideoFallback] = useState(false);
  const videoSrc = (!videoFallback && videoCached.src) ? videoCached.src : (videoUrl || "");
  const items: MediaItem[] = [
    ...urls.map(u => ({ kind: "image" as const, url: u })),
    ...(videoSrc ? [{ kind: "video" as const, url: videoSrc }] : []),
  ];
  const [idx, setIdx] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isFull, setIsFull] = useState(false);
  const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const listKey = urls.join("|") + "|" + (videoSrc || "");
  const [saveState, setSaveState] = useState("");

  // Reset the viewer whenever the media list changes (entry switch)
  useEffect(() => { setIdx(0); setZoom(1); setPan({ x: 0, y: 0 }); setIsFull(false); setVideoFallback(false); }, [listKey]);

  // Esc closes fullscreen
  useEffect(() => {
    if (!isFull) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setIsFull(false); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isFull]);

  if (!items.length) {
    return <div className="form-hint">No media is available for this aura yet.</div>;
  }

  const setZoomClamped = (z: number) => {
    const next = Math.min(4, Math.max(1, Number(z.toFixed(2))));
    setZoom(next);
    if (next === 1) setPan({ x: 0, y: 0 });
  };

  const active = items[Math.min(idx, items.length - 1)];
  const isAnimated = active.kind === "image" && /\.gif(\?|$)/i.test(active.url);
  // Honest captions: only a wiki-verified Opening Cutscene video is presented
  // as "Opening cutscene" — ability/appearance clips keep their real label.
  const kindLabel = videoKind === "opening" || (!videoKind && cutsceneNote) ? "Opening cutscene"
    : videoKind === "ability" ? "Ability video (wiki)"
    : videoKind === "appearance" ? "Appearance / equip video (wiki)"
    : videoKind === "obtainment" ? "Obtainment video (wiki)"
    : "Video from the wiki";
  const caption = active.kind === "video"
    ? kindLabel
    : isAnimated ? "Obtainment cutscene (collection animation)"
    : (() => {
        // Humanized caption from the wiki file name when it is informative
        // (e.g. "Neferkhaf ingame"), generic label otherwise.
        const human = mediaFileName(active.url).replace(/\.[a-z0-9]+$/i, "").replace(/[_\-]+/g, " ").trim();
        const label = isAnimated ? "obtainment cutscene" : "collection / in-game art";
        return human ? `${human.charAt(0).toUpperCase() + human.slice(1)} — ${label}` : label.charAt(0).toUpperCase() + label.slice(1);
      })();

  const onWheel = (e: React.WheelEvent) => {
    if (active.kind !== "image") return;
    e.preventDefault();
    setZoomClamped(zoom + (e.deltaY < 0 ? 0.25 : -0.25));
  };
  const onDragStart = (e: React.MouseEvent) => {
    if (active.kind !== "image" || zoom <= 1) return;
    dragRef.current = { x: e.clientX, y: e.clientY, panX: pan.x, panY: pan.y };
  };
  const onDragMove = (e: React.MouseEvent) => {
    if (!dragRef.current) return;
    const dx = e.clientX - dragRef.current.x;
    const dy = e.clientY - dragRef.current.y;
    setPan({ x: dragRef.current.panX + dx, y: dragRef.current.panY + dy });
  };
  const endDrag = () => { dragRef.current = null; };
  const openFull = () => { setZoom(1); setPan({ x: 0, y: 0 }); setIsFull(true); };

  const mediaEl = (fullscreen: boolean) => active.kind === "video" ? (
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
      alt={name}
      onClick={fullscreen ? undefined : openFull}
      style={{
        width: "100%", height: "100%", objectFit: "contain",
        transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})`,
        transition: dragRef.current ? "none" : "transform 0.12s ease",
        transformOrigin: "center center",
        cursor: fullscreen ? (zoom > 1 ? "grab" : "default") : "zoom-in",
      }}
    />
  );

  const controlsRow = (fullscreen: boolean) => (
    <div style={{ position: "absolute", top: 8, right: 8, display: "flex", gap: 6 }}>
      {active.kind === "image" && (
        <>
          <button className="btn" style={{ padding: "3px 10px" }} onClick={(e) => { e.stopPropagation(); setZoomClamped(zoom - 0.25); }} disabled={zoom <= 1}>−</button>
          <span style={{ padding: "4px 8px", background: "rgba(0,0,0,.55)", fontSize: 12, color: "#fff", minWidth: 44, textAlign: "center" }}>{Math.round(zoom * 100)}%</span>
          <button className="btn" style={{ padding: "3px 10px" }} onClick={(e) => { e.stopPropagation(); setZoomClamped(zoom + 0.25); }} disabled={zoom >= 4}>+</button>
        </>
      )}
      {active.kind === "video" && videoUrl && (
        <button className="btn" style={{ padding: "3px 10px" }} title="Save the video file" onClick={(e) => { e.stopPropagation(); void saveMedia(videoUrl, setSaveState); }}>⬇ Save</button>
      )}
      {!fullscreen && (
        <button className="btn" style={{ padding: "3px 10px" }} title="Fullscreen" onClick={(e) => { e.stopPropagation(); openFull(); }}>⛶</button>
      )}
      {fullscreen && (
        <button className="btn" style={{ padding: "3px 10px" }} onClick={(e) => { e.stopPropagation(); setIsFull(false); }}>✕ Close</button>
      )}
    </div>
  );

  const captionRow = (fullscreen: boolean) => (
    <div style={{ position: "absolute", bottom: 8, left: 10, fontSize: 11, color: accent, background: "rgba(0,0,0,.5)", padding: "3px 8px", maxWidth: "70%" }}>
      {caption}
      {active.kind === "image" && (zoom > 1 ? " · drag to pan, wheel to zoom" : fullscreen ? " · wheel to zoom" : " · click for fullscreen, wheel to zoom")}
    </div>
  );

  return (
    <div>
      <div className="book-panel" style={{ position: "relative", border: "1px solid var(--border)", background: "rgba(0,0,0,.35)", overflow: "hidden", height: 340, cursor: active.kind === "image" && zoom > 1 ? "grab" : "default", "--panel-corner": accent } as React.CSSProperties}
        onWheel={onWheel} onMouseDown={onDragStart} onMouseMove={onDragMove} onMouseUp={endDrag} onMouseLeave={endDrag}>
        {mediaEl(false)}
        {controlsRow(false)}
        {captionRow(false)}
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

      {active.kind === "video" && (videoKind === "opening" || (!videoKind && cutsceneNote)) && cutsceneNote && (
        <p style={{ color: "var(--text-secondary)", lineHeight: 1.6, marginTop: 10, fontSize: 13 }}>{cutsceneNote}</p>
      )}

      {musicUrl && (
        <div className="book-panel" style={{ marginTop: 12, padding: "10px 12px", "--panel-corner": accent } as React.CSSProperties}>
          <CachedAudio url={musicUrl} fileLabel={musicFile} accent={accent} />
        </div>
      )}

      {items.length > 1 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginTop: 10 }}>
          {items.map((item, i) => (
            <button key={item.kind + item.url} onClick={() => { setIdx(i); setZoom(1); setPan({ x: 0, y: 0 }); }}
              style={{ padding: 0, position: "relative", border: i === idx ? `2px solid ${accent}` : "2px solid transparent", background: "rgba(255,255,255,.06)", cursor: "pointer", lineHeight: 0 }}>
              <CachedThumb url={item.url} alt={`${name} media ${i + 1}`}
                style={{ width: 74, height: 74, objectFit: "contain", background: "rgba(255,255,255,.05)" }} />
              {item.kind === "video" && (
                <span style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", fontSize: 22, color: "#fff", background: "rgba(0,0,0,.35)" }}>▶</span>
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
            {/* Definite-height chain (plain blocks, no grid): the media element
                gets a real 100%x100% box, so objectFit "contain" letterboxes the
                FULL gif/video. The old display:grid overlay left the row height
                indefinite, so tall GIFs rendered at natural size and were
                cropped to their top part. */}
            <div style={{ position: "absolute", inset: 0, overflow: "hidden" }}
              onWheel={onWheel} onMouseDown={onDragStart} onMouseMove={onDragMove} onMouseUp={endDrag} onMouseLeave={endDrag}>
              {mediaEl(true)}
            </div>
            {controlsRow(true)}
            {captionRow(true)}
          </div>
        </div>
      )}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: any }) {
  return <div className="book-panel" style={{ padding: "11px 12px" }}><div style={{ color: "#9994b8", fontSize: 11, textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 5 }}>{label}</div><div style={{ color: "var(--text-primary)", lineHeight: 1.45 }}>{String(value || "Unknown")}</div></div>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <div style={{ marginTop: 16 }}><h4 style={{ color: "#c9c2ff", margin: "0 0 6px", letterSpacing: ".06em" }}>{title}</h4>{children}</div>;
}
