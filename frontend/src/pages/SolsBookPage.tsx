import { memo, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useMusicPlayer } from "../contexts/MusicPlayerContext";
import { claimAudio, onAudioOwnerChange, releaseAudio } from "../utils/audioLock";

// Owners of the single audio slot. Every sound source claims it when it
// starts, so nothing ever plays on top of anything else.
const VIDEO_OWNER = "solbook-video";
const BOOK_MUSIC_OWNER = "solbook-music";

type Entry = Record<string, any>;
type MapData = Record<string, Entry>;
type ImageItem = { url: string; caption?: string };
type MediaRole = "art" | "ingame" | "collection" | "cutscene" | "opening" | "music";

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
  if (section === "achievements") return "#fbbf24";
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

/** Numbers that already sit on the dedicated Rarity line (the global odds and
 *  the in-biome odds) are stripped from prose so the same figure never shows
 *  up twice — but potion/craftable per-source odds are kept whole, those only
 *  live in the prose. */
const stripShownRarities = (s: string, e: Entry) => {
  const forms = new Set<string>();
  const g = Number(e?.rarity);
  if (Number.isFinite(g) && g > 0) { forms.add(fmtNum(g)); forms.add(String(g)); }
  const nr = Number(e?.native_rarity);
  if (Number.isFinite(nr) && nr > 0) { forms.add(fmtNum(nr)); forms.add(String(nr)); }
  let out = String(s || "");
  for (const form of forms) {
    const esc = form.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    out = out.replace(new RegExp(`\\(?\\s*1\\s*(?:in|/)\\s*${esc}\\s*\\)?`, "gi"), "");
  }
  return out
    .replace(/\(\s*\)/g, "")
    .replace(/\s{2,}/g, " ")
    .replace(/\s+([,.;:])/g, "$1")
    .replace(/^[\s,.;:]+/, "")
    .trim();
};

/** Deterministic variant picker — the same aura always reads the same way,
 *  while different auras don't all repeat one template sentence. */
const hashName = (s: string) => {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  return Math.abs(h);
};
const pick = <T,>(variants: T[], seed: string): T => variants[hashName(seed) % variants.length];

/** "How to get it" — the condition prose. Numbers already shown on the
 *  Rarity line or in the biome sentence are stripped; crafted/potion auras
 *  keep every number because their per-source odds only exist here. The
 *  biome detail itself is left to biomeStory() so the two never repeat. */
const obtainmentProse = (e: Entry, name: string) => {
  const raw = String(e?.obtainment || "").trim();
  if (isCraftableAura(e) || isPotionAura(e) || e?.rarity_is_potion) {
    return raw || (isCraftableAura(e) ? "Crafted at Jake's Workshop — not rolled." : "Fixed-chance potion roll — luck does not touch it.");
  }
  const lower = raw.toLowerCase();
  if (lower.startsWith("limited") || (/\bevent\b/.test(lower) && !lower.startsWith("exclusive to"))) {
    const detail = stripShownRarities(raw, e)
      .replace(/\(limited\)/gi, "")
      .replace(/^limited\s*[:—-]?\s*/i, "")
      .replace(/^\(+/, "").replace(/\)+$/, "")
      .replace(/\(\s*\)/g, " ")
      .replace(/\s{2,}/g, " ")
      .trim();
    return pick([
      `A limited event aura — ${detail || "available only while its event runs"}.`,
      `Event gear — ${detail || "it only drops during its season"}.`,
    ], name);
  }
  if (lower.startsWith("exclusive to") || (Array.isArray(e?.exclusive_biome) && e.exclusive_biome[0] && e.exclusive_biome[0] !== "None")) {
    return pick([
      "Not a global roll — it belongs to one world.",
      "A biome-bound roll, not a global one.",
      "This one does not travel: its drop is tied to a single place.",
    ], name);
  }
  if (lower.startsWith("native to") || (Array.isArray(e?.native_biome) && e.native_biome[0] && e.native_biome[0] !== "None")) {
    return pick([
      "A standard roll anywhere — its home biome just answers better.",
      "Ordinary rolling luck produces it; the home biome improves the odds.",
      "Rolled like any aura, with a clear favourite place to stand.",
    ], name);
  }
  if (!raw || lower.includes("obtainment details unavailable") || lower.includes("obtainment not verified")) {
    return pick([
      "A plain roll — no ritual, no requirement.",
      "Just rolling: nothing unlocks it besides luck.",
      "It comes from the roll button like most auras — no special condition.",
    ], name);
  }
  if (lower.includes("standard roll") || lower.includes("any biome")) {
    return pick([
      "A standard roll — any biome, any time.",
      "No conditions attached: every roll can hit it.",
      "Rolled like any common aura, wherever you stand.",
    ], name);
  }
  if (lower.includes("effect is active") || lower.includes("only rolls while")) {
    return stripShownRarities(raw, e) || raw;
  }
  const cleaned = stripShownRarities(raw, e);
  return cleaned || raw;
};

/** The biome sentence — the one place the in-biome odds are allowed to show. */
const biomeStory = (e: Entry, name: string) => {
  const nb = Array.isArray(e?.native_biome) ? e.native_biome : null;
  const nativeName = nb && nb[0] && nb[0] !== "None" ? prettyName(nb[0]) : "";
  const exclList = Array.isArray(e?.exclusive_biomes) && e.exclusive_biomes.length ? e.exclusive_biomes.map(prettyName) : [];
  const exclRaw = Array.isArray(e?.exclusive_biome) && e.exclusive_biome[0] && e.exclusive_biome[0] !== "None" ? prettyName(e.exclusive_biome[0]) : "";
  const worlds = exclList.length ? exclList : (exclRaw ? [exclRaw] : []);
  const globalN = Number(e?.rarity);
  const nativeN = Number(e?.native_rarity);
  if (worlds.length) {
    const where = worlds.length > 1 ? `${worlds.slice(0, -1).join(", ")} and ${worlds[worlds.length - 1]}` : worlds[0];
    const btLocked = /breakthrough/i.test(String(e?.obtainment || ""));
    return pick([
      btLocked
        ? `Its only home is ${where} — Breakthrough will not smuggle it out.`
        : `Its only home is ${where}; elsewhere it needs a Breakthrough roll to appear.`,
      btLocked
        ? `Find ${where} or find nothing: outside it the aura simply never drops.`
        : `Listed as ${where}-bound — outside those walls only Breakthrough can reach it.`,
    ], name);
  }
  if (nativeName) {
    const nativeTxt = Number.isFinite(nativeN) && nativeN > 0 ? `1 in ${fmtNum(nativeN)}` : `×${nb![1] ?? 1} luck`;
    const anywhere = Number.isFinite(globalN) && globalN > 0 ? `1 in ${fmtNum(globalN)}` : "";
    return pick([
      anywhere
        ? `${nativeName} is its home biome — the roll tightens to ${nativeTxt} there, against ${anywhere} anywhere else.`
        : `${nativeName} is its home biome, with odds of ${nativeTxt}.`,
      anywhere
        ? `Anywhere it takes ${anywhere}; stand in ${nativeName} and the hunt shrinks to ${nativeTxt}.`
        : `${nativeName} boosts it to ${nativeTxt}.`,
      anywhere
        ? `Global rolls pay ${anywhere} — but ${nativeName} answers better, at ${nativeTxt}.`
        : `${nativeName} is where this one thrives: ${nativeTxt}.`,
    ], name);
  }
  return pick([
    "No biome holds special rights to it — it rolls anywhere.",
    "It is a global roll: any biome, any time.",
    "No home biome recorded, so every roll counts the same.",
  ], name);
};

/** Archive notes fallback — honest and varied instead of one canned line. */
const archiveNotes = (e: Entry, name: string) =>
  String(e?.description || e?.notes || "").trim() || pick([
    "Nothing has been written about this one yet — the numbers above are all that is known.",
    "No notes so far. The rarity and the source are all that is confirmed.",
    "No description yet — it will appear here as soon as one is written.",
  ], name);

const rarityClassFull = (rarityName: string | undefined, value: any) => {
  if (rarityName && rarityName.trim()) return rarityName.trim();
  return rarityClass(value);
};

const fmtNum = (n: any) => {
  const num = Number(String(n ?? "").replace(/,/g, ""));
  return Number.isFinite(num) ? num.toLocaleString("en-US") : String(n ?? "");
};

const prettyName = (key: any) => String(key ?? "").replace(/_/g, " ").trim();

/** Display name for a dataset entry: a repaired record may carry its real
 *  wiki name (e.g. the "Fragments_of_the_Crimson_Moon|紅月の災厄" key is the
 *  separate craftable aura "Calamity of the Crimson Moon"). */
const entryDisplayName = (key: any, info: Entry | null | undefined) => {
  const named = String((info as any)?.name ?? "").trim();
  return named || prettyName(key);
};

const SOURCE_LABELS: Record<string, string> = {
  fandom: "Wiki",
  fandom_article: "Wiki",
  fandom_cache: "Cached",
  fandom_snapshot: "Offline copy",
  fandom_detail: "Wiki",
};

const sourceLabel = (value: any) => {
  const key = String(value ?? "");
  return SOURCE_LABELS[key] || "Wiki";
};

/** Rarity fact: the GLOBAL odds only. The in-biome odds live in the biome
 *  sentence ("How to get it"), and per-source odds of crafted/potion auras
 *  live in their own prose — nothing is ever printed twice. */
const auraRarityText = (e: Entry) => {
  if (!e) return "Unknown";
  if (isCraftableAura(e) || isPotionAura(e)) {
    const rn = e.rarity_name ? canonicalRarity(e.rarity_name) : "";
    // Potion auras roll with a FIXED chance (luck does not apply) — they
    // are not crafted, so keep the wording honest for each badge.
    const kind = isCraftableAura(e) ? "Crafted — see How to get it" : "Fixed chance — see How to get it";
    return `${rn ? rn + " · " : ""}${kind}`;
  }
  const global = Number(e.rarity);
  if (e.is_exclusive && !Number.isFinite(global)) return "N/A — exclusive";
  if (Number.isFinite(global) && global > 0) return `1 in ${fmtNum(global)}`;
  return "Unknown";
};

const searchableText = (name: string, info: Entry) => {
  const bits = [prettyName(name)];
  const named = String(info?.name ?? "").trim();
  if (named) bits.push(named.toLowerCase());
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

export default function SolsBookPage({ active }: { active?: boolean }) {
  const [biomes, setBiomes] = useState<MapData>({});
  const [items, setItems] = useState<MapData>({});
  const [gauntlets, setGauntlets] = useState<MapData>({});
  const [auras, setAuras] = useState<MapData>({});
  const [achievements, setAchievements] = useState<MapData>({});
  const [section, setSection] = useState<"biomes" | "auras" | "items" | "gauntlets" | "achievements">("biomes");
  const [queryInput, setQueryInput] = useState("");
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<string | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailTab, setDetailTab] = useState<"info" | "media">("info");
  // Live wiki detail is merged into a SEPARATE override store instead of the
  // big dataset maps: mutating `auras`/`biomes` recreated the whole map and
  // re-filtered/re-rendered the entire 479-row list on every detail load.
  const [auraDetailOverrides, setAuraDetailOverrides] = useState<MapData>({});
  const [biomeDetailOverrides, setBiomeDetailOverrides] = useState<MapData>({});

  // Search stays responsive on huge datasets: the input updates instantly,
  // the actual filter runs debounced.
  useEffect(() => {
    const t = window.setTimeout(() => setQuery(queryInput), 150);
    return () => window.clearTimeout(t);
  }, [queryInput]);

  const load = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const [biomeData, auraData, itemData, gauntletData, achievementData] = await Promise.all([
        window.pywebview?.api?.get_full_biome_data?.(),
        window.pywebview?.api?.get_full_aura_data?.(),
        (window.pywebview?.api as any)?.get_full_item_data?.(),
        (window.pywebview?.api as any)?.get_full_gauntlet_data?.(),
        (window.pywebview?.api as any)?.get_full_achievement_data?.(),
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
      if (achievementData && typeof achievementData === "object") setAchievements(achievementData);
    } finally { if (!silent) setLoading(false); }
  };

  useEffect(() => { void load(); }, []);

  // The book must never show stale data: the background fandom refresh can
  // land new auras/items/achievements while another tab is open. Re-pull the
  // datasets every time the book becomes active — silently, without the
  // loading flash and without reloading the page.
  const wasActive = useRef(true);
  useEffect(() => {
    if (active !== false && !wasActive.current) void load(true);
    wasActive.current = active !== false;
  }, [active]);

  const data = section === "biomes" ? biomes : section === "items" ? items : section === "gauntlets" ? gauntlets : section === "achievements" ? achievements : auras;
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

  const entryBase = selected ? data[selected] : null;
  const entryOverride = selected
    ? (section === "auras" ? auraDetailOverrides[selected] : section === "biomes" ? biomeDetailOverrides[selected] : undefined)
    : undefined;
  const entry = entryBase ? { ...entryBase, ...(entryOverride || {}) } : null;
  const accent = entryAccent(entry, section);
  const selectEntry = useCallback((name: string) => setSelected(name), []);

  const auraImages = useMemo<ImageItem[]>(() => {
    if (section !== "auras" || !entry) return [];
    const out: ImageItem[] = [];
    const push = (url: any, caption?: string) => {
      if (typeof url === "string" && url.length > 0) out.push({ url, caption });
    };
    // The wiki's own pictures of the aura come first: the collection icon
    // is the aura's face, the in-game shot is the second best preview.
    // Everything else (gallery art) follows.
    push(entry.image_collection_url, "Collection icon");
    push(entry.image_ingame_url, "In-game preview");
    if (Array.isArray(entry.image_urls)) {
      entry.image_urls.forEach((item: any) => {
        if (typeof item === "string") push(item);
        else if (item && typeof item.url === "string") push(item.url, typeof item.caption === "string" ? item.caption : undefined);
      });
    }
    const seen = new Set<string>();
    return out.filter(item => {
      // One file can arrive through several URLs — dedupe by file name so the
      // gallery never shows the same picture twice.
      const key = mediaFileName(item.url).toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [section, entry]);
  const auraVideoUrl = typeof entry?.video_url === "string" && entry.video_url ? entry.video_url : "";
  const auraVideoKind = typeof entry?.video_kind === "string" ? entry.video_kind : "";
  const auraCutsceneNote = typeof entry?.cutscene_note === "string" ? entry.cutscene_note : "";
  const auraMusicUrl = typeof entry?.music_url === "string" && entry.music_url ? entry.music_url : "";
  const auraMusicFile = (typeof entry?.music_name === "string" && entry.music_name) ? entry.music_name : (typeof entry?.music_file === "string" ? entry.music_file : "");

  const biomeImages = useMemo<ImageItem[]>(() => {
    if (section !== "biomes" || !entry) return [];
    const isImageFile = (u: string) => /\.(png|jpe?g|gif|webp)(\/|$|\?)/i.test(u);
    const out: ImageItem[] = [];
    const push = (url: any, caption?: string) => {
      if (typeof url === "string" && url.length > 0 && isImageFile(url)) out.push({ url, caption });
    };
    // Info-page preview: the rectangular in-game biome view (preview_url).
    // thumbnail_url is the square spawn icon — it must NEVER double as the
    // preview; when the wiki has no scene yet, the preview area stays empty.
    push(entry.preview_url, "In-game view");
    if (Array.isArray(entry.gallery)) {
      entry.gallery.forEach((g: any) => push(g?.url, typeof g?.caption === "string" ? g.caption : undefined));
    }
    const seen = new Set<string>();
    return out.filter(item => {
      // One file can arrive through several URLs (the CDN /revision/latest
      // form and the Special:FilePath form) — dedupe by file name, or the
      // media gallery shows every picture twice.
      const key = mediaFileName(item.url).toLowerCase();
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
  }, [section, entry]);
  const biomeMusicUrl = typeof entry?.music_url === "string" && entry.music_url ? entry.music_url : "";
  const biomeMusicFile = (typeof entry?.music_name === "string" && entry.music_name) ? entry.music_name : (typeof entry?.music_file === "string" ? entry.music_file : "");
  const biomeVideoUrl = typeof entry?.video_url === "string" && entry.video_url ? entry.video_url : "";
  const biomeVideoKind = typeof entry?.video_kind === "string" ? entry.video_kind : "";
  const biomeCutsceneNote = typeof entry?.cutscene_note === "string" ? entry.cutscene_note : "";

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
      setAuraDetailOverrides(current => ({ ...current, [selected]: { ...current[selected], ...detail } }));
    }).finally(() => { if (alive) setDetailLoading(false); });
    return () => { alive = false; };
  }, [section, selected]);

  useEffect(() => {
    if (section !== "biomes" || !selected || !window.pywebview?.api?.get_biome_detail) return;
    let alive = true;
    void window.pywebview.api.get_biome_detail(selected).then((detail: Record<string, any>) => {
      if (!alive || !detail || detail.error) return;
      setBiomeDetailOverrides(current => ({ ...current, [selected]: { ...current[selected], ...detail } }));
    }).catch(() => {});
    return () => { alive = false; };
  }, [section, selected]);

  return <div className="page-container fade-in" data-no-i18n style={{ minHeight: "100%" }}>
    <div className="page-header" style={{ marginBottom: 18 }}>
      <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start" }}>
        <div>
          <h2 style={{ letterSpacing: "0.04em" }}>✦ Sol’s Book</h2>
          <p>Every biome, aura and relic of Sol’s RNG.</p>
        </div>
        <button className="btn" onClick={() => void load()} disabled={loading}>{loading ? "Updating…" : "↻ Refresh"}</button>
      </div>
    </div>

    <div className="book-tome">
      <div className="book-tome__page">
      <div className="book-panel book-titlepage" style={{ padding: "22px 26px", background: "linear-gradient(180deg, rgba(30, 27, 46, 0.7) 0%, rgba(18, 16, 28, 0.9) 100%)" }}>
        <div style={{ color: "#a78bfa", fontSize: 11, letterSpacing: ".18em", textTransform: "uppercase", fontWeight: 600 }}>The EndSol Reference Archive</div>
        <h3 style={{ fontSize: 24, margin: "6px 0 4px", fontWeight: 700 }}>The Almanac of Chance</h3>
        <div style={{ color: "#94a3b8", maxWidth: 760, lineHeight: 1.6, fontSize: 13 }}>
          Biomes, auras, items and gauntlets — everything the RNG has rolled into the world.
        </div>
        
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
          <div className="book-chip" style={{ background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.08)", padding: "5px 12px", borderRadius: "4px", fontSize: 12 }}>
            <b style={{ color: "#fbbf24" }}>{Object.keys(achievements).length}</b> achievements
          </div>
          <div className="book-chip" style={{ background: "rgba(34, 197, 94, 0.1)", border: "1px solid rgba(34, 197, 94, 0.2)", color: "#86efac", padding: "5px 12px", borderRadius: "4px", fontSize: 12 }}>
            ✓ Verified data
          </div>
        </div>
      </div>

      <div style={{ padding: "12px 18px", borderTop: "1px solid rgba(255,255,255,.08)", borderBottom: "1px solid rgba(255,255,255,.08)", display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", background: "rgba(15, 13, 24, 0.5)" }}>
        <button className={`btn ${section === "biomes" ? "btn-accent" : ""}`} style={{ borderRadius: "4px", padding: "6px 14px", fontWeight: 600 }} onClick={() => { setSection("biomes"); setCategory("all"); }}>☁ Biomes</button>
        <button className={`btn ${section === "auras" ? "btn-accent" : ""}`} style={{ borderRadius: "4px", padding: "6px 14px", fontWeight: 600 }} onClick={() => { setSection("auras"); setCategory("all"); }}>✧ Auras</button>
        <button className={`btn ${section === "items" ? "btn-accent" : ""}`} style={{ borderRadius: "4px", padding: "6px 14px", fontWeight: 600 }} onClick={() => { setSection("items"); setCategory("all"); }}>🎒 Items</button>
        <button className={`btn ${section === "gauntlets" ? "btn-accent" : ""}`} style={{ borderRadius: "4px", padding: "6px 14px", fontWeight: 600 }} onClick={() => { setSection("gauntlets"); setCategory("all"); }}>🥊 Gauntlets</button>
        <button className={`btn ${section === "achievements" ? "btn-accent" : ""}`} style={{ borderRadius: "4px", padding: "6px 14px", fontWeight: 600 }} onClick={() => { setSection("achievements"); setCategory("all"); }}>🏆 Achievements</button>

        <input className="form-input" style={{ minWidth: 200, flex: 1, maxWidth: 340, borderRadius: "4px" }} value={queryInput} onChange={e => setQueryInput(e.target.value)} placeholder={section === "auras" ? "Search auras…" : section === "biomes" ? "Search biomes…" : section === "items" ? "Search items…" : section === "achievements" ? "Search achievements…" : "Search gauntlets…"} />
        <select className="form-input" style={{ maxWidth: 190, borderRadius: "4px" }} value={category} onChange={e => setCategory(e.target.value)}>
          <option value="all">All categories</option>
          {categories.map(value => <option key={value} value={value}>{value}</option>)}
        </select>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "minmax(230px, .9fr) minmax(0, 1.6fr)", minHeight: 480 }}>
        {/* Left List — virtualized: only visible rows exist in the DOM */}
        <BookList entries={entries} section={section} selected={selected} onSelect={selectEntry} loading={loading} />

        {/* Right Detail Pane */}
        <div style={{ padding: "24px clamp(16px, 3vw, 36px)", background: "rgba(15, 13, 24, 0.4)" }}>
          {!entry && <div className="form-hint">Select an entry from the archive.</div>}
          {entry && <>
            <div style={{ display: "flex", alignItems: "flex-start", gap: 16, borderBottom: `1px solid rgba(255,255,255,0.08)`, paddingBottom: 18, marginBottom: 18 }}>
              <div className="book-panel" style={{ width: 64, height: 64, display: "grid", placeItems: "center", fontSize: 28, flex: "0 0 auto", overflow: "hidden" }}>
                {entry.thumbnail_url ? (
                  <CachedThumb url={String(entry.thumbnail_url)} alt={String(selected)} style={{ width: "100%", height: "100%", objectFit: "contain", padding: 4 }}
                    placeholder={<span style={{ fontSize: 28 }}>{section === "biomes" ? "☁" : section === "items" ? "🎒" : section === "gauntlets" ? "🥊" : section === "achievements" ? "🏆" : "✧"}</span>} />
                ) : (
                  section === "biomes" ? "☁" : section === "items" ? "🎒" : section === "gauntlets" ? "🥊" : section === "achievements" ? "🏆" : "✧"
                )}
              </div>
              <div style={{ flex: 1 }}>
                <div className={rarityTextClass(entryRarityType(entry))} style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: ".16em", ...(rarityTextClass(entryRarityType(entry)) ? {} : { color: accent }) }}>
                  {section === "gauntlets" ? (entry.slot || entry.hand || "Gauntlet") : section === "items" ? (entry.category || "Item") : section === "achievements" ? (entry.category || "Achievement") : entryRarityType(entry)}
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
                <div style={{ color: "#94a3b8", fontSize: 12 }}>{sourceLabel(entry._metadata_source || entry.metadata_source)}{detailLoading ? " · loading…" : ""}</div>
              </div>
            </div>

            {(section === "auras" || section === "biomes") && (
              <div style={{ display: "flex", gap: 8, marginBottom: 16 }}>
                <button className={`btn ${detailTab === "info" ? "btn-accent" : ""}`} style={{ padding: "6px 16px", borderRadius: "4px" }} onClick={() => setDetailTab("info")}>ℹ Info</button>
                <button className={`btn ${detailTab === "media" ? "btn-accent" : ""}`} style={{ padding: "6px 16px", borderRadius: "4px" }} onClick={() => setDetailTab("media")}>🎞 Media{(() => { const n = section === "auras" ? auraImages.length + (auraVideoUrl ? 1 : 0) + (auraMusicUrl ? 1 : 0) : biomeImages.length + (biomeMusicUrl ? 1 : 0); return n ? ` (${n})` : ""; })()}</button>
              </div>
            )}

            {detailTab === "media" && section === "auras" ? (
              <AuraMediaViewer images={auraImages} videoUrl={auraVideoUrl} videoKind={auraVideoKind} cutsceneNote={auraCutsceneNote} musicUrl={auraMusicUrl} musicFile={auraMusicFile} name={entryDisplayName(selected, entry)} accent={accent} source="aura" />
            ) : detailTab === "media" && section === "biomes" ? (
              <AuraMediaViewer images={biomeImages} videoUrl={biomeVideoUrl} videoKind={biomeVideoKind} cutsceneNote={biomeCutsceneNote} musicUrl={biomeMusicUrl} musicFile={biomeMusicFile} name={entryDisplayName(selected, entry)} accent={accent} source="biome" />
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
              {entry.effects && entry.effects !== entry.usage && (
                <div className="book-card" style={{ marginBottom: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>✨ Effect</h4>
                  <div style={{ fontSize: 13.5, fontWeight: 600, color: "#f8fafc", lineHeight: 1.5 }}>{entry.effects}</div>
                </div>
              )}
              {entry.drops && (
                <div className="book-card" style={{ marginBottom: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>📦 Drops / Contents</h4>
                  <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>
                    {String(entry.drops).split("; ").map((line: string, i: number) => (
                      <div key={i}>{line}</div>
                    ))}
                  </div>
                </div>
              )}
              {entry.how_to_get && (
                <div className="book-card" style={{ marginBottom: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>🗺 Obtainment / Crafting</h4>
                  <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>{entry.how_to_get}</div>
                </div>
              )}
              {(Array.isArray((entry as any).recipe_lines) && (entry as any).recipe_lines.length > 0) || (entry as any).recipe ? (
                <div className="book-card" style={{ marginBottom: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                  <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>🛠 Crafting recipe</h4>
                  {Array.isArray((entry as any).recipe_lines) && (entry as any).recipe_lines.length > 0 ? (
                    <ul style={{ margin: 0, paddingLeft: 18, listStyle: "disc", fontSize: 13, color: "#cbd5e1", lineHeight: 1.8 }}>
                      {(entry as any).recipe_lines.map((line: string, i: number) => <li key={i}>{line}</li>)}
                    </ul>
                  ) : (
                    <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>{String((entry as any).recipe)}</div>
                  )}
                </div>
              ) : null}
              <div className="book-card" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>📝 Description</h4>
                <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>{entry.description || "The reference carries no flavour text for this item — the mechanics above are everything verified."}</div>
              </div>
            </> : section === "biomes" ? <>
              {biomeImages.length > 0 && <BiomePreview item={biomeImages[0]} />}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10, marginBottom: 18 }}>
                <Fact label="Rarity / spawn" value={entry.spawn_chance || "Unknown"} />
                <Fact label="Duration" value={entry.duration || "Unknown"} />
                <Fact label="Biome Message" value={entry.chat_message || "Doesn't post a chat message on spawn"} />
              </div>
              <Section title="Chronicle"><p style={{ lineHeight: 1.7, color: "var(--text-secondary)", fontSize: 13 }}>{entry.description || entry.how_to_get || pick([
                "No story has been written for this biome yet — the spawn odds and the chat line above are everything there is.",
                "No lore so far. What is known: how it spawns, how long it stays, and what it says when it arrives.",
                "Beyond the mechanics above, nothing has been written down yet.",
              ], String(entry.name || entry.spawn_chance || "biome"))}</p></Section>
              {/* Full media (GIFs, videos, music) lives in the Media tab; the Info
                  page carries only the one hero banner above — inline GIF galleries
                  here used to fail loading and kept the page heavy. */}
              {entry.music_url && <Section title="🎵 Theme music"><AudioPlayer url={String(entry.music_url)} accent={accent} source="biome" sourceName={String(entry.name || selected || "")} /></Section>}
              {entry.exclusive_auras && <Section title="Exclusive auras"><p style={{ color: "var(--text-secondary)", fontSize: 13 }}>{Array.isArray(entry.exclusive_auras) ? entry.exclusive_auras.join(", ") : String(entry.exclusive_auras)}</p></Section>}
            </> : section === "achievements" ? <>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10, marginBottom: 18 }}>
                <Fact label="Category" value={entry.category || "Achievement"} />
                <Fact label="Reward" value={entry.reward || "None"} />
              </div>
              <div className="book-card" style={{ marginBottom: 12, background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>✅ How to obtain</h4>
                <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>{entry.obtainment || "No obtainment details available."}</div>
              </div>
              <div className="book-card" style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, padding: "12px 16px" }}>
                <h4 style={{ margin: "0 0 6px", fontSize: 11, color: "#a78bfa", textTransform: "uppercase", letterSpacing: "0.08em" }}>📖 Description</h4>
                <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.6 }}>{entry.description || pick([
                  "No description has been written for this achievement yet.",
                  "The reference data lists the reward but no flavour text — it will show up here once documented.",
                ], String(entry.category || entry.reward || "achievement"))}</div>
              </div>
            </> : <>
              {auraImages.length > 0 && <HeroMedia item={auraImages[0]} />}
              {entry.lore && (
                <div style={{
                  marginBottom: 14, padding: "10px 16px", borderLeft: "2px solid rgba(167,139,250,0.5)",
                  background: "linear-gradient(90deg, rgba(124,58,237,0.10), rgba(56,189,248,0.04) 60%, transparent)",
                  color: "#c4b5fd", fontSize: 13.5, fontStyle: "italic", lineHeight: 1.6,
                }}>
                  “{String(entry.lore)}”
                </div>
              )}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit,minmax(140px,1fr))", gap: 10, marginBottom: 18 }}>
                <Fact label="Rarity class" value={rarityClassFull(entry.rarity_name, entry.rarity)} />
                <Fact label="Rarity" value={auraRarityText(entry)} />
              </div>
              <Section title="How to get it">
                <p style={{ color: "var(--text-secondary)", lineHeight: 1.7, fontSize: 13 }}>
                  {obtainmentProse(entry, entryDisplayName(selected, entry))} {biomeStory(entry, entryDisplayName(selected, entry))}
                </p>
              </Section>
              <Section title="Archive notes"><p style={{ color: "var(--text-secondary)", lineHeight: 1.7, fontSize: 13 }}>{archiveNotes(entry, entryDisplayName(selected, entry))}</p></Section>
              {entry.appearance && (
                <Section title="Appearance">
                  <p style={{ color: "var(--text-secondary)", lineHeight: 1.7, fontSize: 13 }}>{String(entry.appearance)}</p>
                </Section>
              )}
              {entry.ability && (
                <Section title="Abilities">
                  <p style={{ color: "var(--text-secondary)", lineHeight: 1.7, fontSize: 13 }}>{String(entry.ability)}</p>
                </Section>
              )}
              {(auraImages.length > 0 || auraVideoUrl) && <div className="form-hint" style={{ marginTop: 10 }}>🖼 {auraImages.length + (auraVideoUrl ? 1 : 0)} media file(s) available — open the <b>Media</b> tab to view them without slowing the book down.</div>}
            </>}
          </>}
        </div>
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

/** What kind of media a Fandom file is — guessed from its file name + video_kind. */
function mediaRole(url: string, videoKind?: string): MediaRole {
  const name = mediaFileName(url).toLowerCase();
  if (videoKind === "opening" || name.includes("opening")) return "opening";
  if (name.includes("ingame") || name.includes("in_game") || name.includes("in-game")) return "ingame";
  if (name.includes("collection")) return "collection";
  if (name.includes("cutscene")) return "cutscene";
  return "art";
}

const ROLE_LABELS: Record<MediaRole, string> = {
  art: "Artwork",
  ingame: "In-game",
  collection: "Collection icon",
  cutscene: "Cutscene",
  opening: "Opening cutscene",
  music: "Theme music",
};

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

function CachedImage({ url, alt, style, onClick, placeholder }: { url?: string; alt?: string; style?: React.CSSProperties; onClick?: () => void; placeholder?: React.ReactNode }) {
  const { src, state } = useCachedMedia(url || undefined);
  // Deterministic source order: the local cache FIRST, the raw wiki URL only
  // after the cache resolved or failed, then the placeholder. The old flow
  // rendered the direct CDN URL while the cache call was still in flight —
  // Cloudflare rejected it instantly and the image was declared dead before
  // the good local copy could ever appear (why full GIFs "never loaded" while
  // thumbnails, whose URL swap arrives later, worked fine).
  const [usedDirect, setUsedDirect] = useState(false);
  const [dead, setDead] = useState(false);
  useEffect(() => { setUsedDirect(false); setDead(false); }, [url]);
  const fallback = placeholder ?? (
    <div style={{
      ...style, display: "grid", placeItems: "center", minHeight: 48,
      background: "rgba(255,255,255,.05)", color: "rgba(226,232,240,.5)", fontSize: 18, lineHeight: 1,
    }}>✧</div>
  );
  if (!url || dead) return <>{fallback}</>;
  const usingDirect = usedDirect || state === "failed";
  const effective = usingDirect ? url : src;
  if (!effective) return <>{fallback}</>; // cache still resolving — hold
  return (
    <img
      src={effective}
      alt={alt}
      onClick={onClick}
      loading="lazy"
      decoding="async"
      draggable={false}
      referrerPolicy="no-referrer"
      onError={() => { if (!usingDirect) setUsedDirect(true); else setDead(true); }}
      style={{ display: "block", ...style }}
    />
  );
}

function CachedThumb({ url, alt, style, placeholder }: { url?: string; alt?: string; style?: React.CSSProperties; placeholder?: React.ReactNode }) {  const [previewSrc, setPreviewSrc] = useState<string>("");
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

  return <CachedImage url={previewSrc || url} alt={alt} style={style} placeholder={placeholder} />;
}

/* Volume slider styled like the seek bar (flat track, small angular thumb)
   so the player uses one visual language instead of native red knobs. */
const AUDIO_VOL_CSS = `
.audio-vol{-webkit-appearance:none;appearance:none;width:72px;height:6px;border-radius:4px;background:rgba(255,255,255,.10);border:1px solid rgba(255,255,255,.12);outline:none;cursor:pointer}
.audio-vol::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:10px;height:12px;border-radius:2px;background:var(--audio-accent,#a78bfa);border:none;cursor:pointer}
.audio-vol::-moz-range-thumb{width:10px;height:12px;border-radius:2px;background:var(--audio-accent,#a78bfa);border:none;cursor:pointer}
`;

function AudioPlayer({ url, fileLabel, accent, source, sourceName }: {
  url: string;
  fileLabel?: string;
  accent?: string;
  source?: string;
  sourceName?: string;
}) {
  const { src, state } = useCachedMedia(url);
  const audioSrc = src || url;
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [current, setCurrent] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [loop, setLoop] = useState(false);
  const [saveState, setSaveState] = useState("");
  // Track title: the wiki file name when the entry carries none — the player
  // used to show an empty header whenever music_file was missing.
  const title = fileLabel ? prettyName(fileLabel) : prettyName(mediaFileName(url));
  // The built-in player: the track can be added to it from here.
  const player = useMusicPlayer();
  const ownerId = `${BOOK_MUSIC_OWNER}:${url}`;

  // A tab/entry switch swaps the src under the same element: the browser
  // silently stops playback while the old "playing" flag survived, so the
  // button kept lying (and the first click seemed dead). Reset on track
  // change and keep the icon in sync with the real element state.
  useEffect(() => {
    setPlaying(false);
    setCurrent(0);
    setDuration(0);
  }, [url]);

  useEffect(() => {
    if (audioRef.current) audioRef.current.loop = loop;
  }, [loop]);

  const fmtTime = (t: number) => {
    if (!Number.isFinite(t) || t < 0) return "0:00";
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60);
    return `${m}:${String(s).padStart(2, "0")}`;
  };
  const toggle = () => {
    const el = audioRef.current;
    if (!el) return;
    if (el.paused) void el.play().catch(() => {});
    else el.pause();
  };
  const seek = (e: React.MouseEvent<HTMLDivElement>) => {
    const el = audioRef.current;
    if (!el || !Number.isFinite(el.duration) || el.duration <= 0) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width));
    el.currentTime = ratio * el.duration;
    setCurrent(el.currentTime);
  };
  const progress = duration > 0 ? Math.min(100, (current / duration) * 100) : 0;

  // Only one sound at a time: when the built-in player starts, this one
  // stops — otherwise the book music and the player music overlap.
  useEffect(() => onAudioOwnerChange((id) => {
    if (!id || id === ownerId) return;
    const el = audioRef.current;
    if (el && !el.paused) {
      try { el.pause(); } catch { /* ignore */ }
    }
    setPlaying(false);
  }), []);

  useEffect(() => {
    if (audioRef.current) audioRef.current.volume = volume;
  }, [volume]);

  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8, fontSize: 12, color: "var(--text-secondary)" }}>
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", maxWidth: "55%" }}>🎵 {title}</span>
        <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 11, opacity: .75 }}>
          {state === "loading" ? "Fetching…" : state === "ready" ? "✓ Cached" : state === "failed" ? "Streaming" : ""}
          {saveState ? <span>{saveState}</span> : null}
          <button
            className="btn"
            style={{ padding: "3px 10px", fontSize: 12, borderRadius: "4px" }}
            onClick={() => {
              const id = fileLabel || url;
              if (player.isFavorite(id)) {
                setSaveState("Already in the player");
              } else {
                player.addTrack({ id, title: title || fileLabel || url, url, source, source_name: sourceName });
                setSaveState("Added to the player");
              }
              setTimeout(() => setSaveState(""), 2500);
            }}
            title="Add this track to the music player"
          >
            ＋
          </button>
          <button className="btn" style={{ padding: "3px 10px", fontSize: 12, borderRadius: "4px" }} onClick={() => void saveMedia(url, setSaveState)} title="Save music to disk">💾</button>
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button
          className="btn btn-accent"
          onClick={toggle}
          title={playing ? "Pause" : "Play"}
          style={{ borderRadius: "4px", padding: "5px 14px", fontWeight: 600, minWidth: 50, flex: "0 0 auto" }}
        >
          {playing ? "❚❚" : "▶"}
        </button>
        <button
          className="btn"
          onClick={() => setLoop(v => !v)}
          title={loop ? "Repeat: on" : "Repeat: off"}
          style={{
            borderRadius: "4px", padding: "5px 10px", flex: "0 0 auto", fontWeight: 600,
            opacity: loop ? 1 : 0.55,
            borderColor: loop ? (accent || "#a78bfa") : undefined,
            color: loop ? (accent || "#a78bfa") : undefined,
          }}
        >
          🔁
        </button>
        <div onClick={seek} title="Seek" style={{ flex: 1, height: 8, borderRadius: 4, background: "rgba(255,255,255,.10)", border: "1px solid rgba(255,255,255,.12)", cursor: "pointer", position: "relative", overflow: "hidden" }}>
          <div style={{ position: "absolute", top: 0, left: 0, bottom: 0, width: `${progress}%`, background: accent || "#a78bfa", transition: "width .12s linear" }} />
        </div>
        <div style={{ fontSize: 11, color: "var(--text-secondary)", fontVariantNumeric: "tabular-nums", minWidth: 78, textAlign: "right", flex: "0 0 auto" }}>
          {fmtTime(current)} / {duration > 0 ? fmtTime(duration) : "-:--"}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 5, flex: "0 0 auto" }} title="Volume">
          <style>{AUDIO_VOL_CSS}</style>
          <span style={{ fontSize: 12 }}>{volume === 0 ? "🔇" : "🔊"}</span>
          <input
            className="audio-vol"
            type="range" min={0} max={100} step={1}
            value={Math.round(volume * 100)}
            onChange={(e) => {
              const v = Number(e.target.value) / 100;
              setVolume(v);
              if (audioRef.current) audioRef.current.volume = v;
            }}
            style={{ ["--audio-accent" as string]: accent || "#a78bfa" } as React.CSSProperties}
          />
        </div>
      </div>
      <audio
        ref={audioRef}
        src={audioSrc}
        preload="metadata"
        onPlay={() => { setPlaying(true); claimAudio(ownerId); }}
        onPause={() => { setPlaying(false); releaseAudio(ownerId); }}
        onEnded={() => { setPlaying(false); setCurrent(0); releaseAudio(ownerId); }}
        onTimeUpdate={(e) => {
          setCurrent(e.currentTarget.currentTime);
          if (e.currentTarget.duration && Number.isFinite(e.currentTarget.duration)) setDuration(e.currentTarget.duration);
        }}
        onLoadedMetadata={(e) => setDuration(e.currentTarget.duration || 0)}
        onDurationChange={(e) => setDuration(e.currentTarget.duration || 0)}
        style={{ display: "none" }}
      />
    </div>
  );
}

/** Small banner shown at the top of the Info tab — one cached still per entry.
 *  `contain` keeps the full biome scene visible (cover used to crop wide
 *  in-game shots into abstract close-ups). */
function HeroMedia({ item }: { item: ImageItem }) {
  return (
    <div className="book-panel" style={{ position: "relative", height: 200, borderRadius: 0, overflow: "hidden", marginBottom: 16, background: "rgba(0,0,0,.35)" }}>
      <CachedImage url={item.url} alt={item.caption || ""} style={{ width: "100%", height: "100%", objectFit: "contain", objectPosition: "center" }} />
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(0,0,0,0) 45%, rgba(10,8,20,.82) 100%)" }} />
      {item.caption && (
        <div style={{ position: "absolute", bottom: 8, left: 12, right: 12, fontSize: 11, color: "#e2e8f0", letterSpacing: ".03em", textShadow: "0 1px 3px rgba(0,0,0,.7)" }}>
          {item.caption}
        </div>
      )}
    </div>
  );
}

/** Biome preview: a wide cinematic strip (the in-game screenshot cropped to
 *  a letterbox) with softly blurred top/bottom edges. Hold the mouse still on
 *  it for 2 seconds and it unfolds until the whole image fits; move the mouse
 *  away and 2 seconds later it folds back. */
function BiomePreview({ item }: { item: ImageItem }) {
  const [expanded, setExpanded] = useState(false);
  const holdTimer = useRef(0);
  const clearHold = () => {
    if (holdTimer.current) { window.clearTimeout(holdTimer.current); holdTimer.current = 0; }
  };
  useEffect(() => () => clearHold(), []);
  return (
    <div
      className="book-panel"
      onMouseEnter={() => { clearHold(); holdTimer.current = window.setTimeout(() => setExpanded(true), 2000); }}
      onMouseLeave={() => { clearHold(); holdTimer.current = window.setTimeout(() => setExpanded(false), 2000); }}
      style={{ position: "relative", borderRadius: 0, overflow: "hidden", marginBottom: 16, background: "rgba(0,0,0,.35)", cursor: "pointer" }}
    >
      <CachedImage
        url={item.url}
        alt={item.caption || ""}
        placeholder={<div style={{ width: "100%", height: expanded ? 420 : 150, display: "grid", placeItems: "center", background: "rgba(255,255,255,.04)", color: "rgba(226,232,240,.55)", fontSize: 22, transition: "height .45s ease" }}>☁</div>}
        style={{
          width: "100%",
          height: expanded ? 420 : 150,
          objectFit: expanded ? "contain" : "cover",
          objectPosition: "center",
          display: "block",
          transition: "height .45s ease",
        }}
      />
      {/* soft dark gradient on the top and bottom edges while folded */}
      <div style={{
        position: "absolute", left: 0, right: 0, top: 0, height: expanded ? 0 : 46, pointerEvents: "none",
        background: "linear-gradient(to bottom, rgba(8,8,14,.55), rgba(8,8,14,0))",
        transition: "height .45s ease",
      }} />
      <div style={{
        position: "absolute", left: 0, right: 0, bottom: 26, height: expanded ? 0 : 46, pointerEvents: "none",
        background: "linear-gradient(to top, rgba(8,8,14,.55), rgba(8,8,14,0))",
        transition: "height .45s ease",
      }} />
      <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, rgba(0,0,0,0) 45%, rgba(10,8,20,.82) 100%)", pointerEvents: "none" }} />
      {item.caption && (
        <div style={{ position: "absolute", bottom: 8, left: 12, right: 12, fontSize: 11, color: "#e2e8f0", letterSpacing: ".03em", textShadow: "0 1px 3px rgba(0,0,0,.7)" }}>
          {item.caption}
        </div>
      )}
    </div>
  );
}

function AuraMediaViewer({ images, videoUrl, videoKind, cutsceneNote, musicUrl, musicFile, name, accent, source }: { images: ImageItem[]; videoUrl?: string; videoKind?: string; cutsceneNote?: string; musicUrl?: string; musicFile?: string; name: string; accent: string; source?: string }) {
  type MediaItem = { kind: "image" | "video"; url: string; remoteUrl?: string; role: MediaRole; caption: string };
  const videoCached = useCachedMedia(videoUrl || undefined);
  const [videoFallback, setVideoFallback] = useState(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const videoSrc = (!videoFallback && videoCached.src) ? videoCached.src : (videoUrl || "");

  // The cutscene takes the single audio slot: when it starts, the music
  // player of the book and the built-in player stop.
  useEffect(() => onAudioOwnerChange((id) => {
    if (!id || id === VIDEO_OWNER) return;
    const el = videoRef.current;
    if (el && !el.paused) {
      try { el.pause(); } catch { /* ignore */ }
    }
  }), []);
  const items: MediaItem[] = [
    ...images.map(im => {
      const role = mediaRole(im.url);
      return { kind: "image" as const, url: im.url, role, caption: im.caption || ROLE_LABELS[role] };
    }),
    ...(videoSrc ? [{
      kind: "video" as const,
      url: videoSrc,
      remoteUrl: videoUrl || "",
      role: mediaRole(videoUrl || "", videoKind),
      caption: videoKind === "opening" ? "Opening cutscene" : "Cutscene video",
    }] : []),
  ];
  const [idx, setIdx] = useState(0);
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [isFull, setIsFull] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  const dragRef = useRef<{ x: number; y: number; panX: number; panY: number } | null>(null);
  const listKey = images.map(im => im.url).join("|") + "|" + (videoSrc || "");
  const [saveState, setSaveState] = useState("");

  useEffect(() => { setIdx(0); setZoom(1); setPan({ x: 0, y: 0 }); setIsFull(false); setVideoFallback(false); }, [listKey]);

  // Keyboard: ←/→ cycle the media, Esc closes fullscreen. Keys typed into
  // form fields (the search box, selects) are never stolen.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      const tag = target?.tagName;
      const typing = tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || !!target?.isContentEditable;
      if (e.key === "Escape") { setIsFull(false); return; }
      if (typing || items.length < 2) return;
      if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
        e.preventDefault();
        setIdx(i => e.key === "ArrowLeft" ? (i - 1 + items.length) % items.length : (i + 1) % items.length);
        setZoom(1);
        setPan({ x: 0, y: 0 });
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [items.length]);

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
      ref={(el) => { videoRef.current = el; }}
      onPlay={() => { claimAudio(VIDEO_OWNER); }}
      onPause={() => { releaseAudio(VIDEO_OWNER); }}
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
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        <b style={{ color: accent }}>{ROLE_LABELS[active.role]}</b>
        {active.caption && active.caption !== ROLE_LABELS[active.role] ? ` · ${active.caption}` : ""}
        {` · ${idx + 1} of ${items.length}`}
      </span>
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
      {items.length > 0 && (
        <div className="book-panel" style={{ position: "relative", background: "rgba(0,0,0,.35)", overflow: "hidden", height: 340, cursor: active.kind === "image" && zoom > 1 ? "grab" : "default", borderRadius: 0 } as React.CSSProperties}
          onWheel={onWheel} onMouseDown={onDragStart} onMouseMove={onDragMove} onMouseUp={endDrag} onMouseLeave={endDrag}>
          {mediaEl()}
          {controlsRow(false)}
          {captionRow()}
        </div>
      )}

      {videoUrl && (
        <div style={{ marginTop: 6, fontSize: 12, color: "var(--text-secondary)" }}>
          {videoCached.state === "loading" ? "⏳ Preparing the video (cached for reliable playback)…"
            : videoCached.state === "ready" ? "✓ Playing from the local cache — works offline"
            : videoCached.state === "failed" ? "⚠ Could not cache — playing directly"
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
        <div className="book-panel" style={{ marginTop: 12, padding: "10px 12px", borderRadius: 0 } as React.CSSProperties}>
          <AudioPlayer url={musicUrl} fileLabel={musicFile} accent={accent} source={source} sourceName={String(name || "")} />
        </div>
      )}

      {items.length > 1 && (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(136px, 1fr))", gap: 8, marginTop: 12 }}>
          {items.map((item, i) => (
            <button
              key={item.kind + item.url}
              onClick={() => { setIdx(i); setZoom(1); setPan({ x: 0, y: 0 }); }}
              onDoubleClick={() => { setIdx(i); setZoom(1); setPan({ x: 0, y: 0 }); setIsFull(true); }}
              title={item.caption}
              style={{ padding: 0, position: "relative", border: i === idx ? `2px solid ${accent}` : "2px solid transparent", background: "rgba(255,255,255,.06)", cursor: "pointer", lineHeight: 0, borderRadius: "4px", overflow: "hidden" }}
            >
              <CachedThumb url={item.url} alt={item.caption}
                placeholder={<div style={{ width: "100%", height: 84, background: "rgba(0,0,0,.55)" }} />}
                style={{ width: "100%", height: 84, objectFit: "cover", background: "rgba(255,255,255,.05)" }} />
              <span style={{ position: "absolute", top: 3, left: 3, fontSize: 8.5, letterSpacing: ".05em", textTransform: "uppercase", padding: "1px 5px", borderRadius: 3, background: "rgba(10,8,20,.78)", color: accent, fontWeight: 600, lineHeight: 1.5 }}>
                {ROLE_LABELS[item.role]}
              </span>
              {item.kind === "video" && (
                <span style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", fontSize: 20, color: "#fff", background: "rgba(0,0,0,.35)" }}>▶</span>
              )}
              <span style={{ position: "absolute", bottom: 0, left: 0, right: 0, fontSize: 9.5, padding: "2px 5px", background: "rgba(10,8,20,.72)", color: "#cbd5e1", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", lineHeight: 1.5 }}>
                {item.caption}
              </span>
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

// ── Virtualized entry list ────────────────────────────────────────────
// Sol's Book renders up to 479 aura entries. Rendering them all as live DOM
// rows (plus re-rendering on every keystroke/scroll) is a real FPS cost on
// software-composited WebView2 — so the list is windowed: only the visible
// rows (+ overscan) exist in the DOM, and each row is memoized so scrolling
// never rebuilds already-rendered entries.
const LIST_ROW_HEIGHT = 42; // 38px row (border-box) + 4px margin-bottom
const LIST_VIEWPORT = 620;  // matches the container's maxHeight
const LIST_OVERSCAN = 6;

const BookRow = memo(function BookRow({ name, info, active, section, onSelect }: {
  name: string; info: Entry; active: boolean; section: string; onSelect: (name: string) => void;
}) {
  const color = entryAccent(info, section);
  const isEvent = (section === "auras" && isEventAura(info)) || (section === "gauntlets" && !!info.limited);
  const itemStyle = active
    ? ({ "--item-color": color, "--item-bg": `${color}1a`, "--item-border": `${color}66`, borderRadius: "4px", height: "100%" } as React.CSSProperties)
    : isEvent
    ? ({ border: "1px dashed rgba(34,197,94,.4)", borderRadius: "4px", height: "100%" } as React.CSSProperties)
    : ({ borderRadius: "4px", height: "100%" } as React.CSSProperties);
  return (
    <button onClick={() => onSelect(name)} className={`book-item${active ? " book-item--active" : ""}`} style={itemStyle}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, boxShadow: `0 0 8px ${color}`, flex: "0 0 auto" }} />
      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontSize: 13 }}>{entryDisplayName(name, info)}</span>
    </button>
  );
});

function BookList({ entries, section, selected, onSelect, loading }: {
  entries: [string, Entry][]; section: string; selected: string | null; onSelect: (name: string) => void; loading?: boolean;
}) {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [scrollTop, setScrollTop] = useState(0);
  const scrollRaf = useRef(0);

  const onScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    const value = e.currentTarget.scrollTop;
    if (scrollRaf.current) return;
    scrollRaf.current = window.requestAnimationFrame(() => {
      scrollRaf.current = 0;
      setScrollTop(value);
    });
  }, []);
  useEffect(() => () => { if (scrollRaf.current) window.cancelAnimationFrame(scrollRaf.current); }, []);

  // A new filtered dataset (section / search / category change) resets the
  // scroll position so the window math starts from the top.
  useEffect(() => {
    setScrollTop(0);
    if (scrollRef.current) scrollRef.current.scrollTop = 0;
  }, [section, entries]);

  const total = entries.length;
  const startIdx = Math.max(0, Math.floor(scrollTop / LIST_ROW_HEIGHT) - LIST_OVERSCAN);
  const endIdx = Math.min(total, Math.ceil((scrollTop + LIST_VIEWPORT) / LIST_ROW_HEIGHT) + LIST_OVERSCAN);
  const visible = entries.slice(startIdx, endIdx);

  return (
    <div ref={scrollRef} onScroll={onScroll} style={{ padding: 12, borderRight: "1px solid rgba(255,255,255,.08)", maxHeight: LIST_VIEWPORT, overflow: "auto" }}>
      {loading && <div className="form-hint" style={{ padding: 18 }}>Opening the archive…</div>}
      {total === 0 && !loading && <div className="form-hint" style={{ padding: 18 }}>No entries match this search.</div>}
      {total > 0 && (
        <>
          <div style={{ height: startIdx * LIST_ROW_HEIGHT }} aria-hidden="true" />
          {visible.map(([name, info]) => (
            <div key={name} style={{ height: LIST_ROW_HEIGHT - 4, marginBottom: 4 }}>
              <BookRow name={name} info={info} active={name === selected} section={section} onSelect={onSelect} />
            </div>
          ))}
          <div style={{ height: Math.max(0, (total - endIdx)) * LIST_ROW_HEIGHT }} aria-hidden="true" />
        </>
      )}
    </div>
  );
}

function Fact({ label, value }: { label: string; value: any }) {  // No inline background/borderRadius: .book-panel draws the panel's own
  // sharp corners and bracket accents — rounded overrides used to hide them.
  return <div className="book-panel" style={{ padding: "10px 12px" }}>
    <div style={{ color: "#a78bfa", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 4, fontWeight: 600 }}>{label}</div>
    <div style={{ color: "#f8fafc", lineHeight: 1.4, fontSize: 13, fontWeight: 500 }}>{String(value || "Unknown")}</div>
  </div>;
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return <div style={{ marginTop: 16 }}>
    <h4 style={{ color: "#a78bfa", margin: "0 0 6px", letterSpacing: ".06em", fontSize: 12, textTransform: "uppercase", fontWeight: 600 }}>{title}</h4>
    <div className="book-panel" style={{ padding: "12px 14px" }}>{children}</div>
  </div>;
}
