import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useT } from "../i18n";

/*
 * Sol's Sim — a sandbox for rolling Sol's RNG auras inside the panel.
 *
 * Rules of the sandbox (agreed with the owner):
 *  - Lives as a panel page; "Close simulator" stops every timer and shows a
 *    landing card, so closing the mini-game never closes the panel.
 *  - Two modes: HONEST (gauntlets only) and SANDBOX (speed x2/x3/x5, luck
 *    slider, forced biome spawn). No guaranteed-aura cheat.
 *  - Stats + settings live in %LOCALAPPDATA%/EndSolMacro/sim_save.json and
 *    can be reset from the page. Current biome does NOT survive the session.
 *  - Drop alerts are in-page banners; optional Discord embeds are sent with
 *    allowed_mentions: [] (never pings). No Windows notifications.
 */

type Data = Record<string, any>;

type DropLogEntry = { name: string; rarity: number; tier: string; biome: string; ts: number };

type SimStats = {
  rolls: number;
  unique_auras: string[];
  counts: Record<string, number>;
  rarest: { name: string; rarity: number } | null;
  biome_visits: Record<string, number>;
  playtime_s: number;
  log: DropLogEntry[];
};

type SimSettings = {
  mode: "honest" | "sandbox";
  speed: number;
  luck: number;
  auto_roll: boolean;
  notify_aura_min_rarity: number;
  notify_rare_biomes: boolean;
  discord_enabled: boolean;
  discord_webhook_url: string;
};

type SimSave = {
  version: number;
  stats: SimStats;
  settings: SimSettings;
  gauntlets: { left: string | null; right: string | null; pocket: string | null };
};

type PoolAura = { name: string; N: number; tier: string; exclusive: boolean; native: boolean; luckExempt: boolean };

type BiomeRuntime = { name: string; color: string; endsAt: number };

type ClauseEffect = {
  luckPct: number;
  luckMult: number;
  speedPct: number;
  cond: { kind: "phase"; phase: "day" | "night" } | { kind: "biomes"; biomes: string[] } | null;
  text: string;
};

type GauntletFx = {
  biomeMult: Record<string, number>;
  flat: ClauseEffect[];
  conds: ClauseEffect[];
  notes: string[];
};

const fxNum = (s: string) => Number(s.replace(/,/g, ""));

const describeFx = (e: ClauseEffect): string => {
  const parts: string[] = [];
  if (e.luckPct) parts.push(`${e.luckPct > 0 ? "+" : ""}${e.luckPct}% luck`);
  if (e.luckMult !== 1) parts.push(`x${e.luckMult} luck`);
  if (e.speedPct) parts.push(`${e.speedPct > 0 ? "+" : ""}${e.speedPct}% roll speed`);
  return parts.join(", ") || e.text;
};

const condLabel = (c: NonNullable<ClauseEffect["cond"]>): string =>
  c.kind === "phase"
    ? `only during ${c.phase === "day" ? "Daytime" : "Nighttime"}`
    : `only in ${c.biomes.join(" / ")}`;

/** One wiki boost clause -> numbers we can honestly apply, or a note when the
 *  clause is a stacking / periodic / bonus-roll technique. Values come only
 *  from the wiki text — nothing is invented or "approximated". */
const parseClause = (raw: string): { effect: ClauseEffect | null; notes: string[] } => {
  const text = raw.trim().replace(/^Or\s+/i, "").replace(/^\[[^\]]+\]\s*:\s*/i, "").replace(/\.$/, "");
  if (!text) return { effect: null, notes: [] };

  const effect: ClauseEffect = { luckPct: 0, luckMult: 1, speedPct: 0, cond: null, text };
  const notes: string[] = [];
  let any = false;

  const phaseM = text.match(/\bduring\s+(nighttime|daytime)\b/i);
  const biomeM = text.match(/(?:if current biome is|during)\s+([^.;]+?)\s*$/i);
  if (phaseM) {
    effect.cond = { kind: "phase", phase: phaseM[1].toLowerCase() === "daytime" ? "day" : "night" };
  } else if (biomeM && !/nighttime|daytime/i.test(biomeM[1])) {
    const biomes = biomeM[1].split(/\s*,\s*|\s+or\s+/i).map(s => biomeMatchName(s)).filter(Boolean);
    if (biomes.length) effect.cond = { kind: "biomes", biomes };
  }

  // "…Luck and +0.05% Luck per stack…" splits into flat + technique pieces;
  // digit-less tails ("…Halloween Biomes and Glitched") stay with their piece.
  const rawPieces = text.split(/\s+and\s+/i);
  const pieces: string[] = [];
  for (const rp of rawPieces) {
    const p = rp.trim();
    if (!p) continue;
    if (pieces.length && !/\d/.test(p)) pieces[pieces.length - 1] += ` and ${p}`;
    else pieces.push(p);
  }

  for (const p of pieces) {
    if (/per\s+stack|every\s+\d|next\s+\d+\s+rolls|randomized|bonus\s+roll|dark\s+point|duplicate|\bcoins\b|rarity decrease/i.test(p)) {
      notes.push(p);
      continue;
    }
    const before = { l: effect.luckPct, s: effect.speedPct, m: effect.luckMult };
    const multM = p.match(/x\s*([\d.]+)\s*(?:base\s+|basic\s+)?luck/i);
    if (multM) effect.luckMult *= Number(multM[1]);
    const luckRe = /([+-]?[\d,]+(?:\.\d+)?)%\s*(?:base\s+|basic\s+)?luck(?:\s+boost)?/gi;
    let m: RegExpExecArray | null;
    while ((m = luckRe.exec(p)) !== null) effect.luckPct += fxNum(m[1]);
    const speedRe = /([+-]?[\d,]+(?:\.\d+)?)%\s*roll\s*speed/gi;
    while ((m = speedRe.exec(p)) !== null) effect.speedPct += fxNum(m[1]);
    const changed = effect.luckPct !== before.l || effect.speedPct !== before.s || effect.luckMult !== before.m;
    if (changed) {
      any = true;
      continue;
    }
    // Bare "+N% [during ...]" is a luck boost in wiki style ("Or +250% during Starfall").
    const bare = p.match(/^([+-]?[\d,]+(?:\.\d+)?)%\s*(?:during\b.*)?$/i);
    if (bare) {
      effect.luckPct += fxNum(bare[1]);
      any = true;
    } else {
      notes.push(p);
    }
  }
  return { effect: any ? effect : null, notes };
};

/** Wiki boost text -> structured effects. Applied values are parsed straight
 *  from the wiki wording ("+2,200% Base Luck", "-25% Roll Speed", "x1.35
 *  Basic Luck", "2x chance to get Rainy biome"); stacking / periodic /
 *  bonus-roll techniques become notes instead of made-up numbers. */
const parseGauntletFx = (g: Data | null | undefined): GauntletFx => {
  const fx: GauntletFx = { biomeMult: {}, flat: [], conds: [], notes: [] };
  if (!g) return fx;
  let text = String(g.usage || g.raw_info?.["boost(s)"] || "");
  const biomeRe = /(\d+(?:\.\d+)?)x chance (?:to get |of |for )?(?:the )?([a-z][a-z ]*?) biome\.?/gi;
  let m: RegExpExecArray | null;
  while ((m = biomeRe.exec(text)) !== null) {
    const key = biomeMatchName(m[2]);
    const mult = Number(m[1]);
    if (key && Number.isFinite(mult)) fx.biomeMult[key] = (fx.biomeMult[key] || 1) * mult;
  }
  text = text.replace(biomeRe, "");
  // Split on ";" and sentence-ending "." only — never on decimal points
  // ("x1.35 Basic Luck" must stay one clause).
  for (const clause of text.split(/[;]+|\.(?=\s|$)/)) {
    const { effect, notes } = parseClause(clause);
    fx.notes.push(...notes);
    if (effect) {
      if (effect.cond) fx.conds.push(effect);
      else fx.flat.push(effect);
    }
  }
  return fx;
};

const DAY_LENGTH_S = 600; // sandbox approximation of the in-game day cycle

const DEFAULT_SETTINGS: SimSettings = {
  mode: "honest",
  speed: 1,
  luck: 1,
  auto_roll: false,
  notify_aura_min_rarity: 100000,
  notify_rare_biomes: true,
  discord_enabled: false,
  discord_webhook_url: "",
};

const DEFAULT_SAVE: SimSave = {
  version: 1,
  stats: { rolls: 0, unique_auras: [], counts: {}, rarest: null, biome_visits: {}, playtime_s: 0, log: [] },
  settings: { ...DEFAULT_SETTINGS },
  gauntlets: { left: null, right: null, pocket: null },
};

const TIER_COLORS: Record<string, string> = {
  Basic: "#FFFFFF",
  Epic: "#C57ED3",
  Unique: "#BE7418",
  Legendary: "#F7F917",
  Mythic: "#F554EF",
  Exalted: "#3F62D8",
  Glorious: "#C52425",
  Transcendent: "#7EC8FF",
  Event: "#21FF11",
};

const rarityTier = (n: number): string => {
  if (!Number.isFinite(n)) return "Basic";
  if (n >= 1_000_000_000) return "Transcendent";
  if (n >= 100_000_000) return "Glorious";
  if (n >= 10_000_000) return "Exalted";
  if (n >= 1_000_000) return "Mythic";
  if (n >= 100_000) return "Legendary";
  if (n >= 10_000) return "Unique";
  if (n >= 1_000) return "Epic";
  return "Basic";
};

const fmtNum = (n: any) => {
  const num = Number(String(n ?? "").replace(/,/g, ""));
  return Number.isFinite(num) ? num.toLocaleString("en-US") : String(n ?? "");
};

const fmtTime = (s: number) => {
  const total = Math.max(0, Math.floor(s));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const sec = total % 60;
  return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m ${sec}s` : `${sec}s`;
};

/** "1 in 500/s (0.2%/s)" -> 0.002 per second; conditional spawns -> null. */
const parseSpawn = (desc: string): number | null => {
  const s = String(desc || "");
  if (!s) return null;
  if (/via |after |per night|per day|admin|passive|summoned|replace|default|replaces/i.test(s)) return null;
  const num = (raw: string) => Number(raw.replace(/,/g, ""));
  let m = s.match(/1\s*in\s*([\d,]+(?:\.\d+)?)\s*\/\s*s/i);
  if (m) return 1 / num(m[1]);
  m = s.match(/1\s*in\s*([\d,]+(?:\.\d+)?)/i);
  if (m) return 1 / num(m[1]);
  m = s.match(/^1\s*\/\s*([\d,]+(?:\.\d+)?)/);
  if (m) return 1 / num(m[1]);
  return null;
};

/** "3mins 12sec (192s)" -> 192; "2 minutes and 44 seconds (164 seconds)" -> 164. */
const parseDuration = (desc: string): number => {
  const s = String(desc || "").replace(/\(.*?\)/g, " ");
  let total = 0;
  const re = /(\d+)\s*(hours?|hrs?|h\b|minutes?|mins?|min\b|seconds?|secs?|sec\b)/gi;
  let m: RegExpExecArray | null;
  while ((m = re.exec(s)) !== null) {
    const v = Number(m[1]);
    const u = m[2].toLowerCase();
    total += u.startsWith("h") ? v * 3600 : u.startsWith("m") ? v * 60 : v;
  }
  return total > 0 ? total : 300;
};

const biomeMatchName = (raw: string) => String(raw || "").trim().toUpperCase().replace(/\s+/g, " ");

/** Auras that cannot be rolled in the real game right now are never in the
 *  pool: crafted gear auras (also covers the boss drops the owner listed as
 *  craftable), potion/quest rewards, dev/removed/unreleased/unobtainable,
 *  and seasonal event auras (limited) until their season returns. */
const EXCLUDED_FLAGS = new Set(["craftable", "limited", "unobtainable", "dev_exclusive", "unreleased", "removed"]);
const EXCLUDED_TYPES = new Set(["potion", "quest_reward", "unobtainable"]);
const BOSS_AURAS = new Set(["FRAGMENTS_OF_THE_CRIMSON_MOON", "NEFERKHAF"]); // Red Moon Potion / Potion of the Dune

const isSimRollable = (key: string, a: Data): boolean => {
  if (a?.rarity_is_potion) return false;
  const flags: string[] = Array.isArray(a?.flags) ? a.flags : [];
  if (flags.some(f => EXCLUDED_FLAGS.has(String(f).toLowerCase()))) return false;
  if (EXCLUDED_TYPES.has(String(a?.obtainment_type || "").toLowerCase())) return false;
  const base = String(a?.name || key).split("|")[0].trim().toUpperCase().replace(/\s+/g, "_");
  if (BOSS_AURAS.has(base)) return false;
  return true;
};

/** Split wiki biome refs like "RAINY OR GLITCHED" / "NULL OR THE LIMBO". */
const splitBiomeRefs = (raw: any): string[] =>
  String(raw ?? "").split(/\s+OR\s+|,|\/(?!\d)/i)
    .map(s => biomeMatchName(s))
    .filter(s => s && s !== "NONE");

const exclusiveRefs = (a: Data): string[] => {
  const out = new Set<string>();
  const ex1 = a?.exclusive_biome;
  if (Array.isArray(ex1)) splitBiomeRefs(ex1[0]).forEach(r => out.add(r));
  if (Array.isArray(a?.exclusive_biomes)) a.exclusive_biomes.forEach((x: any) => splitBiomeRefs(x).forEach(r => out.add(r)));
  return [...out];
};

const nativeRef = (a: Data): string => {
  const nb = a?.native_biome;
  const refs = Array.isArray(nb) ? splitBiomeRefs(nb[0]) : [];
  return refs[0] || "";
};

/** Eligible aura pool, rarest first. Rebuilt only when the biome changes.
 *  `blocked` = biomes that do not exist in the sim (Limbo dimension, admin
 *  biomes, out-of-season events): an aura obtainable ONLY there is never
 *  rolled anywhere (e.g. "Nothing"/"Raven" are Limbo-only; Prowler is from
 *  the admin Hyperspace Realm). An aura that also drops elsewhere (Empty =
 *  "NULL OR THE LIMBO") stays available in that other biome. */
const buildPool = (auras: Data, biomeName: string | null, blocked: Set<string>): PoolAura[] => {
  const out: PoolAura[] = [];
  const biomeKey = biomeName ? biomeMatchName(biomeName) : null;
  for (const [key, a] of Object.entries(auras)) {
    if (!isSimRollable(key, a)) continue;
    const name = String(a?.name || key);
    const globalN = Number(a?.rarity);
    const nativeN = Number(a?.native_rarity);
    const nativeBiome = nativeRef(a);
    const exclAll = exclusiveRefs(a);
    const rawRefs = [...new Set([...exclAll, ...(nativeBiome ? [nativeBiome] : [])])];
    if (rawRefs.length > 0 && rawRefs.every(r => blocked.has(r))) continue;
    const exclAllowed = exclAll.filter(r => !blocked.has(r));
    const isExcl = !!a?.is_exclusive || exclAll.length > 0;
    let N = Number.isFinite(globalN) && globalN > 0 ? globalN : NaN;
    let native = false;
    if (biomeKey && nativeBiome && nativeBiome === biomeKey
      && Number.isFinite(nativeN) && nativeN > 0) {
      N = nativeN;
      native = true;
    }
    if (isExcl) {
      if (!biomeKey || !exclAllowed.includes(biomeKey)) continue;
      if (!Number.isFinite(N) && Number.isFinite(nativeN) && nativeN > 0) N = nativeN;
    }
    if (!Number.isFinite(N) || N <= 0) continue;
    out.push({
      name,
      N,
      tier: rarityTier(N),
      exclusive: isExcl,
      native,
      luckExempt: !!a?.luck_exempt,
    });
  }
  out.sort((x, y) => y.N - x.N);
  return out;
};

/** The in-game model: every aura rolls independently at 1 in (N / luck) and
 *  the rarest hit wins; a full miss falls back to the commonest aura (the
 *  game always gives one per roll). Luck-exempt auras (Meta, Illusionary,
 *  Cryogenic) ignore the multiplier. */
const rollAura = (pool: PoolAura[], luck: number): PoolAura | null => {
  if (!pool.length) return null;
  for (const a of pool) {
    const l = a.luckExempt ? 1 : luck;
    if (Math.random() < Math.min(1, l / a.N)) return a;
  }
  return pool[pool.length - 1];
};

/* In-game style Roll button (Sol's RNG): black plate, grey cooldown fill
   draining toward the left, white HUD corner brackets above the fill. */
const SIM_ROLL_CSS = `
.sim-roll-btn{position:relative;width:100%;max-width:320px;height:58px;background:#000;border:1px solid #565656;border-radius:0;padding:0;overflow:hidden;display:flex;align-items:center;justify-content:center;cursor:pointer}
.sim-roll-btn:disabled{cursor:not-allowed}
.sim-roll-btn__fill{position:absolute;top:0;left:0;bottom:0;width:0%;background:#373737;z-index:1}
.sim-roll-btn__fill--anim{animation-name:simCooldownDrain;animation-timing-function:linear;animation-fill-mode:forwards}
@keyframes simCooldownDrain{from{width:100%}to{width:0%}}
.sim-roll-btn__corner{position:absolute;width:7px;height:7px;z-index:3;border:0 solid #fff}
.sim-roll-btn__corner--tl{top:3px;left:3px;border-top-width:1.5px;border-left-width:1.5px}
.sim-roll-btn__corner--tr{top:3px;right:3px;border-top-width:1.5px;border-right-width:1.5px}
.sim-roll-btn__corner--bl{bottom:3px;left:3px;border-bottom-width:1.5px;border-left-width:1.5px}
.sim-roll-btn__corner--br{bottom:3px;right:3px;border-bottom-width:1.5px;border-right-width:1.5px}
.sim-roll-btn__text{position:relative;z-index:2;color:#fff;font-weight:800;font-size:25px;line-height:1;user-select:none;font-family:"Segoe UI","Arial Black",system-ui,sans-serif}
.sim-fx{position:fixed;inset:0;pointer-events:none;z-index:9000}
.sim-fx-glitch{background:repeating-linear-gradient(0deg,rgba(255,0,80,.05) 0 2px,transparent 2px 5px);animation:simFxGlitch 1.1s steps(2) infinite;mix-blend-mode:screen}
@keyframes simFxGlitch{0%,100%{transform:translate(0,0)}25%{transform:translate(-2px,1px)}50%{transform:translate(2px,-1px)}75%{transform:translate(-1px,2px)}}
.sim-fx-dream{background:radial-gradient(55% 45% at 18% 12%,rgba(217,70,239,.15),transparent 60%),radial-gradient(50% 40% at 85% 85%,rgba(168,85,247,.13),transparent 60%);animation:simFxDream 9s ease-in-out infinite alternate}
@keyframes simFxDream{from{opacity:.55}to{opacity:1}}
.sim-fx-cyber{background:repeating-linear-gradient(0deg,rgba(34,211,238,.06) 0 1px,transparent 1px 6px),radial-gradient(45% 35% at 50% 0%,rgba(34,211,238,.10),transparent 70%);animation:simFxCyber 4s linear infinite}
@keyframes simFxCyber{from{background-position:0 0,0 0}to{background-position:0 48px,0 0}}
.sim-fx-sing{background:radial-gradient(65% 50% at 50% 18%,rgba(239,68,68,.13),transparent 65%),radial-gradient(35% 28% at 50% 26%,rgba(251,146,60,.10),transparent 60%);animation:simFxSing 5s ease-in-out infinite}
@keyframes simFxSing{0%,100%{opacity:.55}50%{opacity:1}}
`;

export default function SolSimPage({ active }: { active?: boolean }) {
  const visible = active !== false;
  const t = useT();
  const tRef = useRef(t);
  tRef.current = t;
  const [launched, setLaunched] = useState(false);
  const [loading, setLoading] = useState(true);
  const [auras, setAuras] = useState<Data>({});
  const [biomes, setBiomes] = useState<Data>({});
  const [gauntlets, setGauntlets] = useState<Data>({});

  const [settings, setSettings] = useState<SimSettings>({ ...DEFAULT_SETTINGS });
  const [loadout, setLoadout] = useState<SimSave["gauntlets"]>({ left: null, right: null, pocket: null });
  const [statsView, setStatsView] = useState<SimStats>(DEFAULT_SAVE.stats);
  const [lastDrop, setLastDrop] = useState<PoolAura | null>(null);
  const [rollSeq, setRollSeq] = useState(0);
  const [toast, setToast] = useState<{ title: string; body: string; color: string } | null>(null);
  const [world, setWorld] = useState<{ biome: BiomeRuntime | null; phase: "day" | "night"; phaseEndsAt: number }>({
    biome: null, phase: "day", phaseEndsAt: Date.now() / 1000 + DAY_LENGTH_S,
  });
  const [forceBiome, setForceBiome] = useState("");

  const statsRef = useRef<SimStats>(structuredClone(DEFAULT_SAVE.stats));
  const saveTimerRef = useRef(0);
  const discordGateRef = useRef(0);
  const rollAccRef = useRef(0);
  const cooldownUntilRef = useRef(0);
  const cooldownMsRef = useRef(500);
  const lastUiRef = useRef(0);
  const doRollRef = useRef<(fromAuto?: boolean) => void>(() => {});
  const worldRef = useRef(world);
  worldRef.current = world;

  // ── Load datasets + persisted save ────────────────────────────────
  // The tracker that serves aura/biome data boots in a background thread
  // (main.py _background_init), so a single load-on-mount used to get empty
  // data and the sim stayed dead (no rolls, no biome cycle). Retry until the
  // datasets actually arrive; one broken call never kills the others.
  const [dataError, setDataError] = useState<{ code: "retry" | "failed"; attempt: number } | null>(null);
  const loadSeqRef = useRef(0);

  const loadData = useCallback(async () => {
    const seq = ++loadSeqRef.current;
    setLoading(true);
    setDataError(null);
    let saveApplied = false;
    for (let attempt = 0; attempt < 30; attempt++) {
      const [bRes, aRes, gRes, saveRes] = await Promise.allSettled([
        (window.pywebview?.api as any)?.get_full_biome_data?.() ?? Promise.resolve(null),
        (window.pywebview?.api as any)?.get_full_aura_data?.() ?? Promise.resolve(null),
        (window.pywebview?.api as any)?.get_full_gauntlet_data?.() ?? Promise.resolve(null),
        (window.pywebview?.api as any)?.sim_load_save?.() ?? Promise.resolve(null),
      ]);
      if (seq !== loadSeqRef.current) return;
      const val = (r: PromiseSettledResult<any>) => (r.status === "fulfilled" ? r.value : null);
      const b = val(bRes);
      const a = val(aRes);
      const g = val(gRes);
      const saveVal = val(saveRes);
      if (b && typeof b === "object" && Object.keys(b).length) setBiomes(b);
      if (a && typeof a === "object" && Object.keys(a).length) setAuras(a);
      if (g && typeof g === "object" && Object.keys(g).length) setGauntlets(g);
      if (!saveApplied && saveVal?.success && saveVal.data && Object.keys(saveVal.data).length) {
        saveApplied = true;
        const saved = saveVal.data as SimSave;
        const stats: SimStats = { ...DEFAULT_SAVE.stats, ...(saved.stats || {}) };
        stats.unique_auras = Array.isArray(stats.unique_auras) ? stats.unique_auras : [];
        stats.counts = stats.counts && typeof stats.counts === "object" ? stats.counts : {};
        stats.log = Array.isArray(stats.log) ? stats.log : [];
        stats.biome_visits = stats.biome_visits && typeof stats.biome_visits === "object" ? stats.biome_visits : {};
        statsRef.current = stats;
        setStatsView({ ...stats, unique_auras: [...stats.unique_auras], log: [...stats.log] });
        setSettings({ ...DEFAULT_SETTINGS, ...(saved.settings || {}) });
        const gl = saved.gauntlets || {};
        setLoadout({ left: gl.left ?? null, right: gl.right ?? null, pocket: gl.pocket ?? null });
      }
      if (attempt === 0) setLoading(false);
      const ready = a && typeof a === "object" && Object.keys(a).length > 0;
      if (ready) {
        setDataError(null);
        return;
      }
      setDataError({ code: "retry", attempt: attempt + 1 });
      await new Promise(r => window.setTimeout(r, 1500));
    }
    setDataError({ code: "failed", attempt: 30 });
    setLoading(false);
  }, []);

  useEffect(() => {
    void loadData();
    return () => { loadSeqRef.current++; };
  }, [loadData]);

  const persist = useCallback((immediate = false) => {
    const flush = () => {
      saveTimerRef.current = 0;
      const payload: SimSave = {
        version: 1,
        stats: statsRef.current,
        settings,
        gauntlets: loadout,
      };
      void (window.pywebview?.api as any)?.sim_save_state?.(payload);
    };
    if (immediate) {
      if (saveTimerRef.current) { window.clearTimeout(saveTimerRef.current); saveTimerRef.current = 0; }
      flush();
      return;
    }
    if (saveTimerRef.current) return;
    saveTimerRef.current = window.setTimeout(flush, 800);
  }, [settings, loadout]);

  // ── Derived: gauntlet effects, pool, effective rates ──────────────
  const equippedFx = useMemo(() => {
    const merged = {
      biomeMult: {} as Record<string, number>,
      luckPct: 0,
      luckMult: 1,
      speedPct: 0,
      chips: [] as string[],
      notes: [] as string[],
    };
    const apply = (name: string, e: ClauseEffect, suffix: string) => {
      merged.luckPct += e.luckPct;
      merged.luckMult *= e.luckMult;
      merged.speedPct += e.speedPct;
      merged.chips.push(`${name}: ${describeFx(e)}${suffix}`);
    };
    for (const key of ["left", "right", "pocket"] as const) {
      const name = loadout[key];
      if (!name) continue;
      const fx = parseGauntletFx(gauntlets[name]);
      for (const [b, m] of Object.entries(fx.biomeMult)) {
        merged.biomeMult[b] = (merged.biomeMult[b] || 1) * m;
        merged.chips.push(`${name}: ${b} biome x${m}`);
      }
      for (const e of fx.flat) apply(name, e, "");
      for (const e of fx.conds) {
        const c = e.cond!;
        const activeNow = c.kind === "phase"
          ? c.phase === world.phase
          : !!world.biome && c.biomes.includes(biomeMatchName(world.biome.name));
        if (activeNow) {
          apply(name, e, ` — active (${c.kind === "phase" ? (c.phase === "day" ? "Daytime" : "Nighttime") : world.biome!.name})`);
        } else {
          merged.notes.push(`${name}: ${describeFx(e)} — ${condLabel(c)}`);
        }
      }
      merged.notes.push(...fx.notes.map(nt => `${name}: ${nt}`));
    }
    return merged;
  }, [loadout, gauntlets, world.biome, world.phase]);

  const sandbox = settings.mode === "sandbox";
  const gauntletLuck = (1 + equippedFx.luckPct / 100) * equippedFx.luckMult;
  const effLuck = Math.max(1, (sandbox ? settings.luck : 1) * gauntletLuck);
  // Gear roll-speed is honest and unbounded (Singularity Gauntlet is x3);
  // only the Sandbox speed cheat itself is limited to x5 by design.
  const effSpeed = Math.max(0.1, (sandbox ? settings.speed : 1) * (1 + equippedFx.speedPct / 100));

  // Biomes that do not exist in the sim: the Limbo dimension, admin biomes
  // and out-of-season events (they return with their seasons).
  const blockedBiomes = useMemo(() => {
    const set = new Set<string>(["THE LIMBO"]);
    for (const [key, b] of Object.entries(biomes)) {
      const cat = String(b?.category || "");
      if (cat === "event" || cat === "admin") set.add(biomeMatchName(b?.name || key));
    }
    return set;
  }, [biomes]);

  const pool = useMemo(() => buildPool(auras, world.biome ? world.biome.name : null, blockedBiomes), [auras, world.biome, blockedBiomes]);

  // ── Notifications (in-page banner + optional Discord, never pings) ─
  const notify = useCallback((title: string, body: string, color: string, discord: boolean) => {
    setToast({ title, body, color });
    window.setTimeout(() => setToast(null), 5000);
    if (!discord || !settings.discord_enabled || !settings.discord_webhook_url) return;
    const now = Date.now();
    if (now - discordGateRef.current < 5000) return;
    discordGateRef.current = now;
    void (window.pywebview?.api as any)?.sim_notify_discord?.(
      settings.discord_webhook_url, title, body, parseInt(color.replace("#", ""), 16) || 5814783,
    );
  }, [settings.discord_enabled, settings.discord_webhook_url]);

  // ── Roll logic ───────────────────────────────────────────────────
  // Cooldown is the game's roll delay: after a roll the grey fill drains on
  // the button and a manual click is ignored until it is over.
  const cooldownMs = Math.max(60, Math.round(1000 / effSpeed));
  useEffect(() => { cooldownMsRef.current = cooldownMs; });

  const doRoll = useCallback((fromAuto = false) => {
    const now = Date.now();
    if (!fromAuto && now < cooldownUntilRef.current) return;
    if (!pool.length) {
      setToast({ title: tRef.current("No aura data yet"), body: tRef.current("Game data is still loading — try ↻ Reload data."), color: "#f87171" });
      return;
    }
    const aura = rollAura(pool, effLuck);
    if (!aura) return;
    cooldownUntilRef.current = now + cooldownMsRef.current;
    setRollSeq(s => s + 1);
    const st = statsRef.current;
    st.rolls += 1;
    if (!st.unique_auras.includes(aura.name)) st.unique_auras.push(aura.name);
    st.counts[aura.name] = (st.counts[aura.name] || 0) + 1;
    if (!st.rarest || aura.N > st.rarest.rarity) st.rarest = { name: aura.name, rarity: aura.N };
    const entry: DropLogEntry = {
      name: aura.name, rarity: aura.N, tier: aura.tier,
      biome: worldRef.current.biome ? worldRef.current.biome.name : "NORMAL",
      ts: Date.now(),
    };
    st.log = [entry, ...st.log].slice(0, 25);
    if (now - lastUiRef.current > 150) {
      lastUiRef.current = now;
      setLastDrop(aura);
    }
    if (aura.N >= Math.max(1, settings.notify_aura_min_rarity)) {
      notify(
        `✦ ${aura.name}`,
        `1 in ${fmtNum(aura.N)} · ${aura.tier} · ${tRef.current("in")} ${entry.biome} (${tRef.current("simulated drop")})`,
        TIER_COLORS[aura.tier] || "#a78bfa",
        true,
      );
    }
    persist();
  }, [pool, effLuck, settings.notify_aura_min_rarity, notify, persist]);

  useEffect(() => { doRollRef.current = doRoll; });

  // Auto-roll loop: fixed 100ms tick, accumulator turns rate into rolls.
  useEffect(() => {
    if (!launched || !visible || !pool.length) return;
    const rate = settings.auto_roll ? effSpeed : 0;
    if (rate <= 0) return;
    const id = window.setInterval(() => {
      rollAccRef.current += rate / 10;
      while (rollAccRef.current >= 1) {
        rollAccRef.current -= 1;
        doRollRef.current(true);
      }
    }, 100);
    return () => window.clearInterval(id);
  }, [launched, visible, settings.auto_roll, effSpeed, pool.length]);

  // ── World tick: day/night, biome spawns, playtime, stat flush ─────
  useEffect(() => {
    if (!launched || !visible) return;
    const id = window.setInterval(() => {
      const now = Date.now() / 1000;
      const w = { ...worldRef.current };

      if (now >= w.phaseEndsAt) {
        w.phase = w.phase === "day" ? "night" : "day";
        w.phaseEndsAt = now + DAY_LENGTH_S;
        // Seasonal rule: the day/night event biomes (Graveyard, Pumpkin Moon,
        // Blazing Sun) spawn only during their real events. None are active
        // now — Halloween content returns in a later update — so the phase
        // flip is just the clock.
      }

      if (w.biome && now >= w.biome.endsAt) w.biome = null;

      if (!w.biome) {
        for (const [key, b] of Object.entries(biomes)) {
          if (String(b?.category || "") === "event") continue; // seasonal: out of season now
          const base = parseSpawn(String(b.spawn_chance || ""));
          if (!base) continue;
          const mult = equippedFx.biomeMult[biomeMatchName(b.name || key)] || 1;
          if (Math.random() < base * mult) {
            let name = b.name || key;
            if (biomeMatchName(name) === "STARFALL" && Math.random() < 0.01) name = "SINGULARITY";
            const target = biomes[name] || b;
            w.biome = { name, color: String(target.color || "#7c6cff"), endsAt: now + parseDuration(target.duration) };
            const st = statsRef.current;
            st.biome_visits[name] = (st.biome_visits[name] || 0) + 1;
            const cat = String(target.category || "weather");
            if (settings.notify_rare_biomes && cat !== "weather") {
              notify(`☁ ${name}`, `${tRef.current("Simulated biome spawn")} · ${String(target.spawn_chance || "")}`, String(target.color || "#7c6cff"), true);
            }
            break;
          }
        }
      }

      statsRef.current.playtime_s += 1;
      setWorld(w);
      setStatsView({ ...statsRef.current, unique_auras: [...statsRef.current.unique_auras], log: [...statsRef.current.log] });
      if (statsRef.current.playtime_s % 30 === 0) persist(true);
    }, 1000);
    return () => window.clearInterval(id);
  }, [launched, visible, biomes, equippedFx.biomeMult, settings.notify_rare_biomes, notify, persist]);

  // Persist + stop cleanly when the mini-game closes or the tab hides.
  useEffect(() => {
    if (!launched) persist(true);
    else if (!visible) persist(true);
  }, [launched, visible, persist]);
  useEffect(() => () => { persist(true); }, [persist]);

  const spawnBiome = useCallback((name: string) => {
    const b = biomes[name];
    if (!b) return;
    const w = { ...worldRef.current };
    w.biome = { name: b.name || name, color: String(b.color || "#7c6cff"), endsAt: Date.now() / 1000 + parseDuration(b.duration) };
    const st = statsRef.current;
    st.biome_visits[w.biome.name] = (st.biome_visits[w.biome.name] || 0) + 1;
    setWorld(w);
    persist();
  }, [biomes, persist]);

  const resetStats = useCallback(() => {
    statsRef.current = structuredClone(DEFAULT_SAVE.stats);
    setStatsView(structuredClone(DEFAULT_SAVE.stats));
    setLastDrop(null);
    persist(true);
  }, [persist]);

  // ── UI helpers ───────────────────────────────────────────────────
  const gauntletOptions = useMemo(() => {
    const bySlot: Record<string, string[]> = { "Left Hand": [], "Right Hand": [], "Pocket": [] };
    for (const [name, g] of Object.entries(gauntlets)) {
      const slot = String(g?.slot || g?.category || "Pocket");
      const key = slot === "Left Hand" ? "Left Hand" : slot === "Right Hand" ? "Right Hand" : "Pocket";
      bySlot[key].push(name);
    }
    for (const k of Object.keys(bySlot)) bySlot[k].sort((a, b) => a.localeCompare(b));
    return bySlot;
  }, [gauntlets]);

  const biomeList = useMemo(() => Object.entries(biomes)
    .filter(([key, b]) => key !== "NORMAL" && key !== "TIME" && !["event", "admin"].includes(String(b?.category || "")))
    .map(([key, b]) => ({ key, name: String(b.name || key), color: String(b.color || "#7c6cff"), category: String(b.category || "weather") }))
    .sort((a, b) => a.name.localeCompare(b.name)), [biomes]);

  const collected = useMemo(() => Object.entries(statsView.counts)
    .map(([name, count]) => {
      const info = pool.find(p => p.name === name);
      return { name, count, N: info?.N ?? 0, tier: info?.tier ?? "Basic" };
    })
    .sort((a, b) => b.N - a.N || a.name.localeCompare(b.name)),
  [statsView.counts, pool]);

  const worldColor = world.biome ? world.biome.color : "#7c6cff";
  // Rare-biome ambience: subtle page-wide effects while the biome lasts
  // (colors follow each biome's own wiki imagery).
  const fxClass = world.biome ? ({
    GLITCHED: "sim-fx-glitch",
    DREAMSPACE: "sim-fx-dream",
    CYBERSPACE: "sim-fx-cyber",
    SINGULARITY: "sim-fx-sing",
  } as Record<string, string>)[biomeMatchName(world.biome.name)] || "" : "";
  const biomeLeft = world.biome ? Math.max(0, Math.round(world.biome.endsAt - Date.now() / 1000)) : 0;

  if (loading) {
    return <div className="page-container fade-in">
      <style>{SIM_ROLL_CSS}</style>
      <div className="form-hint" style={{ padding: 24 }}>
        {dataError ? <>
          {dataError.code === "failed" ? "Game data failed to load — press ↻ Reload data." : "Game data is not ready — the tracker is still starting, retrying…"} ({dataError.attempt}/30)
        </> : "Loading the sandbox…"}
      </div>
    </div>;
  }

  return (
    <div className="page-container fade-in" style={{ minHeight: "100%" }}>
      <style>{SIM_ROLL_CSS}</style>
      <div className="page-header" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
          <div>
            <h2 style={{ letterSpacing: "0.04em" }}>🎲 Sol’s Sim</h2>
            <p>Sandbox of Sol's RNG — roll auras, watch biomes, wear gauntlets. Stats are saved locally; the biome never survives the session.</p>
            <div className="form-hint" style={{ marginTop: 2 }}>Runs only while this tab is active — switching tabs pauses it. Hiding or minimizing the panel window is fine.</div>
          </div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {launched ? (
              <>
                <button className="btn" onClick={() => { persist(true); setLaunched(false); }}>⏹ Close simulator</button>
                <button className="btn" onClick={() => persist(true)}>💾 Save now</button>
                <button className="btn" onClick={() => void loadData()}>↻ Reload data</button>
              </>
            ) : (
              <>
                <button className="btn btn-accent" onClick={() => { if (!Object.keys(auras).length) void loadData(); setLaunched(true); }}>▶ Launch simulator</button>
                <button className="btn" onClick={() => void loadData()}>↻ Reload data</button>
              </>
            )}
          </div>
        </div>
      </div>

      {dataError && <div className="form-hint" style={{ marginBottom: 12, color: "#f9a8a8" }}>
        ⚠ {dataError.code === "failed" ? "Game data failed to load — press ↻ Reload data." : "Game data is not ready — the tracker is still starting, retrying…"} ({dataError.attempt}/30)
      </div>}

      {!launched ? (
        <div className="card" style={{ padding: 28, textAlign: "center" }}>
          <div style={{ fontSize: 40, marginBottom: 8 }}>🎲</div>
          <h3 style={{ margin: "0 0 6px" }}>The simulator is closed</h3>
          <div className="form-hint" style={{ maxWidth: 460, margin: "0 auto" }}>
            Nothing runs while it is closed — zero load. Press <b>Launch simulator</b> to start a session.
            Biomes reset every session; rolls, unique auras and the drop log are kept.
          </div>
          <div style={{ marginTop: 16, color: "var(--text-secondary)", fontSize: 12, display: "flex", gap: 12, justifyContent: "center", flexWrap: "wrap" }}>
            <span>Saved so far:</span>
            <span><b>{fmtNum(statsView.rolls)}</b> rolls</span>
            <span><b>{fmtNum(statsView.unique_auras.length)}</b> unique auras</span>
            <span>rarest: {statsView.rarest ? `${statsView.rarest.name} (1 in ${fmtNum(statsView.rarest.rarity)})` : "—"}</span>
          </div>
        </div>
      ) : (
        <>
          {/* ── World / biome banner ─────────────────────────────── */}
          <div className="card" style={{
            padding: "14px 18px", marginBottom: 14, position: "relative", overflow: "hidden",
            borderLeft: `4px solid ${worldColor}`,
            background: `linear-gradient(90deg, ${worldColor}14, rgba(15,13,24,0.2))`,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 11, letterSpacing: ".16em", textTransform: "uppercase", color: "var(--text-secondary)" }}>
                  <span>{world.phase === "day" ? "☀ Daytime" : "🌙 Nighttime"}</span> · <span>sandbox clock</span>
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, color: worldColor }}>
                  {world.biome ? `☁ ${world.biome.name}` : "NORMAL — no biome active"}
                </div>
                {world.biome && (
                  <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>
                    <span>simulated biome</span> · {fmtTime(biomeLeft)} <span>left</span> · {fmtNum(statsView.biome_visits[world.biome.name] || 0)} <span>visits</span>
                  </div>
                )}
              </div>
              {sandbox && (
                <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                  <select className="form-input" style={{ maxWidth: 210, borderRadius: 4 }} value={forceBiome}
                    onChange={e => setForceBiome(e.target.value)}>
                    <option value="">Force a biome…</option>
                    {biomeList.map(b => <option key={b.key} value={b.key}>{b.name} ({b.category})</option>)}
                  </select>
                  <button className="btn btn-accent" disabled={!forceBiome} onClick={() => spawnBiome(forceBiome)}>☁ Spawn</button>
                  {world.biome && <button className="btn" onClick={() => setWorld(w => ({ ...w, biome: null }))}>✕ Clear</button>}
                </div>
              )}
            </div>
            {!sandbox && <div className="form-hint" style={{ marginTop: 8 }}>Honest mode: biome spawning happens naturally on wiki odds. Switch to Sandbox to force biomes.</div>}
          </div>

          {/* ── Roll + cheats ───────────────────────────────────── */}
          <div style={{ display: "grid", gridTemplateColumns: "minmax(240px, 1fr) minmax(280px, 1.4fr)", gap: 14, marginBottom: 14 }}>
            <div className="card" style={{ padding: 18, display: "flex", flexDirection: "column", gap: 12, alignItems: "center" }}>
              <div style={{ width: "100%", textAlign: "center" }}>
                <div style={{ fontSize: 10.5, letterSpacing: ".16em", textTransform: "uppercase", color: "var(--text-secondary)" }}>Current luck</div>
                <div style={{ fontSize: 27, fontWeight: 700, color: worldColor, lineHeight: 1.2 }}>×{effLuck.toFixed(2)}</div>
                <div style={{ fontSize: 10.5, color: "var(--text-secondary)" }}>
                  <span>base</span> ×1 · <span>gauntlets</span> ×{gauntletLuck.toFixed(2)}{sandbox ? <> · <span>cheat</span> ×{settings.luck}</> : null}
                </div>
              </div>
              <button
                className="sim-roll-btn"
                onClick={() => doRoll(false)}
                disabled={settings.auto_roll}
                title={settings.auto_roll ? "Disabled while auto-roll is running" : "Roll once"}
              >
                <span key={rollSeq} className={`sim-roll-btn__fill${rollSeq > 0 ? " sim-roll-btn__fill--anim" : ""}`} style={{ animationDuration: `${cooldownMs}ms` }} />
                <span className="sim-roll-btn__corner sim-roll-btn__corner--tl" />
                <span className="sim-roll-btn__corner sim-roll-btn__corner--tr" />
                <span className="sim-roll-btn__corner sim-roll-btn__corner--bl" />
                <span className="sim-roll-btn__corner sim-roll-btn__corner--br" />
                <span className="sim-roll-btn__text">Roll</span>
              </button>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, color: "var(--text-secondary)" }}>
                <input type="checkbox" checked={settings.auto_roll}
                  onChange={e => { setSettings(s => ({ ...s, auto_roll: e.target.checked })); persist(); }} />
                Auto-roll
                {sandbox && (
                  <select className="form-input" style={{ width: 76, borderRadius: 4, padding: "2px 6px" }}
                    value={settings.speed} onChange={e => { setSettings(s => ({ ...s, speed: Number(e.target.value) })); persist(); }}>
                    {[1, 2, 3, 5].map(v => <option key={v} value={v}>×{v}</option>)}
                  </select>
                )}
              </label>
              {sandbox ? (
                <div style={{ width: "100%" }}>
                  <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11.5, color: "var(--text-secondary)", marginBottom: 4 }}>
                    <span>Luck (cheat)</span>
                    <span>×{effLuck.toFixed(2)}</span>
                  </div>
                  <input type="range" min={1} max={100} step={1} value={settings.luck}
                    onChange={e => { setSettings(s => ({ ...s, luck: Number(e.target.value) })); persist(); }}
                    style={{ width: "100%", accentColor: worldColor }} />
                </div>
              ) : (
                <div style={{ width: "100%", fontSize: 11.5, color: "var(--text-secondary)" }}>
                  <span>Luck</span> ×{effLuck.toFixed(2)} — <span>gauntlets only in Honest mode. Enable Sandbox for the luck slider and roll-speed cheats.</span>
                </div>
              )}
              <div style={{ fontSize: 11, color: "var(--text-secondary)", textAlign: "center", lineHeight: 1.5 }}>
                <span>Effective roll speed</span> ×{effSpeed.toFixed(2)} · <span>pool</span> {fmtNum(pool.length)} <span>auras</span>{world.biome ? " (biome-modified)" : ""}
                <br />
                Odds like the game: each aura rolls 1 in (N ÷ luck), the rarest hit wins; a full miss falls back to the commonest aura; luck-exempt auras ignore luck.
              </div>
            </div>

            <div className="card" style={{ padding: 18, display: "flex", gap: 16 }}>
              <div style={{ flex: "0 0 auto" }}>
                <div style={{
                  width: 92, height: 92, borderRadius: 4, display: "grid", placeItems: "center", fontSize: 30,
                  background: lastDrop ? `${TIER_COLORS[lastDrop.tier] || "#a78bfa"}1f` : "rgba(255,255,255,.05)",
                  border: `1px solid ${lastDrop ? `${TIER_COLORS[lastDrop.tier] || "#a78bfa"}55` : "rgba(255,255,255,.1)"}`,
                }}>✧</div>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 11, letterSpacing: ".16em", textTransform: "uppercase", color: "var(--text-secondary)" }}>Last drop</div>
                {lastDrop ? (
                  <>
                    <div style={{ fontSize: 21, fontWeight: 700, color: TIER_COLORS[lastDrop.tier] || "#fff", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{lastDrop.name}</div>
                    <div style={{ fontSize: 12.5, color: "var(--text-secondary)" }}>
                      1 in {fmtNum(lastDrop.N)} · <span style={{ color: TIER_COLORS[lastDrop.tier] || "#a78bfa" }}>{lastDrop.tier}</span>
                      {lastDrop.native && " · native biome odds"}{lastDrop.exclusive && " · biome exclusive"}
                    </div>
                  </>
                ) : (
                  <div className="form-hint">No rolls yet — press ROLL.</div>
                )}
                <div style={{ marginTop: 10, fontSize: 11.5, color: "var(--text-secondary)" }}>
                  {statsView.log.slice(0, 5).map((d, i) => (
                    <div key={`${d.ts}-${i}`} style={{ display: "flex", gap: 8, alignItems: "center", padding: "2px 0" }}>
                      <span style={{ width: 7, height: 7, borderRadius: "50%", background: TIER_COLORS[d.tier] || "#94a3b8", flex: "0 0 auto" }} />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{d.name}</span>
                      <span style={{ marginLeft: "auto", opacity: .7, flex: "0 0 auto" }}>1 in {fmtNum(d.rarity)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* ── Gauntlets + stats + settings ────────────────────── */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: 14 }}>
            <div className="card" style={{ padding: 18 }}>
              <h4 style={{ margin: "0 0 10px", fontSize: 12, letterSpacing: ".12em", textTransform: "uppercase", color: "#a78bfa" }}>🥊 Gauntlets (allowed in Honest too)</h4>
              {(["Left Hand", "Right Hand", "Pocket"] as const).map((slot, i) => {
                const key = (["left", "right", "pocket"] as const)[i];
                return (
                  <label key={slot} style={{ display: "block", marginBottom: 10, fontSize: 12.5 }}>
                    <span style={{ color: "var(--text-secondary)", display: "block", marginBottom: 3 }}>{slot}</span>
                    <select className="form-input" style={{ width: "100%", borderRadius: 4 }} value={loadout[key] || ""}
                      onChange={e => { setLoadout(l => ({ ...l, [key]: e.target.value || null })); persist(); }}>
                      <option value="">— empty —</option>
                      {gauntletOptions[slot].map(n => <option key={n} value={n}>{n}</option>)}
                    </select>
                  </label>
                );
              })}
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {equippedFx.chips.length ? equippedFx.chips.map((c, i) => (
                  <span key={i} className="book-badge" style={{ color: "#38bdf8" }}>{c}</span>
                )) : <span className="form-hint">Equip gear to simulate its luck boosts.</span>}
              </div>
              {equippedFx.notes.length > 0 && (
                <div style={{ marginTop: 8, fontSize: 10.5, color: "var(--text-secondary)", lineHeight: 1.6 }}>
                  <div style={{ textTransform: "uppercase", letterSpacing: ".08em", fontSize: 9.5, opacity: .85 }}>Techniques (shown, not simulated)</div>
                  {equippedFx.notes.map((n, i) => <div key={i}>• {n}</div>)}
                </div>
              )}
            </div>

            <div className="card" style={{ padding: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <h4 style={{ margin: 0, fontSize: 12, letterSpacing: ".12em", textTransform: "uppercase", color: "#a78bfa" }}>📊 Statistics</h4>
                <button className="btn" style={{ padding: "3px 10px", fontSize: 12 }} onClick={resetStats} title="Clear rolls, unique auras, biome visits and the drop log">🗑 Reset</button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 12.5 }}>
                <div><div style={{ color: "var(--text-secondary)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".08em" }}>Rolls</div><b>{fmtNum(statsView.rolls)}</b></div>
                <div><div style={{ color: "var(--text-secondary)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".08em" }}>Unique auras</div><b>{fmtNum(statsView.unique_auras.length)}</b></div>
                <div><div style={{ color: "var(--text-secondary)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".08em" }}>Playtime</div><b>{fmtTime(statsView.playtime_s)}</b></div>
                <div><div style={{ color: "var(--text-secondary)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".08em" }}>Rarest</div>
                  <b style={{ fontSize: 11.5 }}>{statsView.rarest ? `${statsView.rarest.name} (1 in ${fmtNum(statsView.rarest.rarity)})` : "—"}</b></div>
              </div>
              <div style={{ marginTop: 10, fontSize: 11.5, color: "var(--text-secondary)" }}>
                {Object.entries(statsView.biome_visits).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([n, c]) => (
                  <div key={n}>☁ {n}: {fmtNum(c)} <span>visits</span></div>
                ))}
                {!Object.keys(statsView.biome_visits).length && <div>No biome visits yet.</div>}
              </div>
            </div>

            <div className="card" style={{ padding: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <h4 style={{ margin: 0, fontSize: 12, letterSpacing: ".12em", textTransform: "uppercase", color: "#a78bfa" }}>🗂 Collection</h4>
                <span style={{ fontSize: 11.5, color: "var(--text-secondary)" }}>
                  <b style={{ color: "#f8fafc" }}>{fmtNum(collected.length)}</b> / {fmtNum(pool.length)} <span>collected</span>
                </span>
              </div>
              {collected.length ? (
                <div style={{ maxHeight: 220, overflow: "auto", fontSize: 11.5, lineHeight: 1.7 }}>
                  {collected.map(row => (
                    <div key={row.name} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      <span style={{ width: 7, height: 7, borderRadius: "50%", background: TIER_COLORS[row.tier] || "#94a3b8", flex: "0 0 auto" }} />
                      <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{row.name}</span>
                      <span style={{ marginLeft: "auto", opacity: .75, flex: "0 0 auto" }}>×{fmtNum(row.count)}{row.N ? ` · 1 in ${fmtNum(row.N)}` : ""}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="form-hint">Nothing collected yet — press Roll.</div>
              )}
            </div>

            <div className="card" style={{ padding: 18 }}>
              <h4 style={{ margin: "0 0 10px", fontSize: 12, letterSpacing: ".12em", textTransform: "uppercase", color: "#a78bfa" }}>⚙ Mode & drop alerts</h4>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, marginBottom: 10 }}>
                <input type="checkbox" checked={sandbox}
                  onChange={e => { setSettings(s => ({ ...s, mode: e.target.checked ? "sandbox" : "honest" })); persist(); }} />
                Sandbox mode (speed ×2/×3/×5, luck slider, forced biomes)
              </label>
              <label style={{ display: "block", fontSize: 12.5, marginBottom: 8 }}>
                <span style={{ color: "var(--text-secondary)" }}>Alert when aura rarity ≥</span>
                <input className="form-input" style={{ width: "100%", borderRadius: 4, marginTop: 3 }} type="number" min={1}
                  value={settings.notify_aura_min_rarity}
                  onChange={e => { setSettings(s => ({ ...s, notify_aura_min_rarity: Math.max(1, Number(e.target.value) || 1) })); persist(); }} />
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, marginBottom: 10 }}>
                <input type="checkbox" checked={settings.notify_rare_biomes}
                  onChange={e => { setSettings(s => ({ ...s, notify_rare_biomes: e.target.checked })); persist(); }} />
                Banner on rare/event biome spawns
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, marginBottom: 8 }}>
                <input type="checkbox" checked={settings.discord_enabled}
                  onChange={e => { setSettings(s => ({ ...s, discord_enabled: e.target.checked })); persist(); }} />
                Also send to Discord (embed, no pings)
              </label>
              {settings.discord_enabled && (
                <input className="form-input" style={{ width: "100%", borderRadius: 4 }} placeholder="Discord webhook URL"
                  value={settings.discord_webhook_url}
                  onChange={e => { setSettings(s => ({ ...s, discord_webhook_url: e.target.value })); persist(); }} />
              )}
              <div className="form-hint" style={{ marginTop: 8 }}>
                Alerts show as banners inside the panel — no Windows notifications.
              </div>
            </div>
          </div>
        </>
      )}

      {/* Rare-biome ambience */}
      {launched && fxClass && <div className={`sim-fx ${fxClass}`} />}

      {/* In-page drop banner (never a Windows notification) */}
      {toast && (
        <div style={{
          position: "fixed", right: 18, bottom: 18, zIndex: 9500, width: 300, padding: "12px 14px",
          borderRadius: 8, background: "rgba(18,16,28,.94)", border: `1px solid ${toast.color}66`,
          boxShadow: `0 8px 28px ${toast.color}33`,
        }}>
          <div style={{ fontSize: 13.5, fontWeight: 700, color: toast.color, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{toast.title}</div>
          <div style={{ fontSize: 11.5, color: "var(--text-secondary)", marginTop: 3 }}>{toast.body}</div>
        </div>
      )}
    </div>
  );
}
