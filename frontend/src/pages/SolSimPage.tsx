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

type DropLogEntry = { name: string; rarity: number; tier: string; biome: string; ts: number; fx?: string[] };

// How many rolls the luck sparkline keeps.
const LUCK_HISTORY_MAX = 60;

// Biome history only (no aura drops): what the world rolled and when.
type BiomeLogEntry = { name: string; ts: number; forced: boolean };

type SimStats = {
  rolls: number;
  unique_auras: string[];
  counts: Record<string, number>;
  rarest: { name: string; rarity: number } | null;
  biome_visits: Record<string, number>;
  playtime_s: number;
  log: DropLogEntry[];
  biome_log: BiomeLogEntry[];
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
  vip: boolean;
  vip_plus: boolean;
};

type SimSave = {
  version: number;
  stats: SimStats;
  settings: SimSettings;
  gauntlets: { left: string | null; right: string | null; pocket: string | null };
};

type PoolAura = { name: string; N: number; tier: string; exclusive: boolean; native: boolean; luckExempt: boolean; excl: string[] };

type BiomeRuntime = { name: string; color: string; endsAt: number };

type ClauseEffect = {
  luckPct: number;
  luckMult: number;
  speedPct: number;
  // Bonus Roll mechanics (the game's every-Nth-roll double-luck roll):
  bonusCd: number | null;        // "Bonus Roll Countdown ... 10 -> 6"
  bonusMult: number | null;      // "Bonus Roll Multiplier ... 2x -> 3x" (absolute)
  bonusMultFactor: number | null; // "x1.3 Bonus Roll Multiplier" (relative)
  removeBonus: boolean;          // "Removes Bonus Roll"
  // Periodic luck spikes: "5x Luck every 11 rolls", "Next 10 Rolls grant x2.5
  // Luck (Every 20th Roll)", "x14 Basic Luck for every 1000th roll".
  everyN: number | null;
  everyMult: number | null;
  everyWindow: number | null;
  randomPct: number | null;      // "0-30% Luck/Roll Speed (randomized per 10 rolls)"
  stackCap: number | null;       // "per stack up to 200% at 10 stacks" -> cap value
  rarityCut: number | null;      // "20% Rarity Decrease on Halloween Auras"
  bonusAuraBiomes: string[];     // Tide: bonus rolls can hit these auras at native rarity
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
  if (e.bonusCd != null) parts.push(`bonus roll every ${e.bonusCd} rolls`);
  if (e.bonusMult != null) parts.push(`bonus roll x${e.bonusMult}`);
  if (e.bonusMultFactor != null) parts.push(`bonus roll multiplier x${e.bonusMultFactor}`);
  if (e.removeBonus) parts.push("bonus roll removed");
  if (e.everyN != null && e.everyMult != null) {
    parts.push(`x${e.everyMult} luck every ${e.everyN} rolls${e.everyWindow && e.everyWindow > 1 ? ` (for ${e.everyWindow} rolls)` : ""}`);
  }
  if (e.randomPct != null) parts.push(`randomized 0-${e.randomPct}% luck/speed per 10 rolls`);
  if (e.stackCap != null) parts.push(`up to +${e.stackCap}% luck (max stacks)`);
  if (e.rarityCut != null) parts.push(`${e.rarityCut}% rarity cut on matching auras`);
  if (e.bonusAuraBiomes.length) parts.push(`bonus rolls can hit ${e.bonusAuraBiomes.join(" / ")} auras at native rarity`);
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

  const effect: ClauseEffect = {
    luckPct: 0, luckMult: 1, speedPct: 0,
    bonusCd: null, bonusMult: null, bonusMultFactor: null, removeBonus: false,
    everyN: null, everyMult: null, everyWindow: null,
    randomPct: null, stackCap: null, rarityCut: null, bonusAuraBiomes: [],
    cond: null, text,
  };
  const notes: string[] = [];
  let any = false;

  const phaseM = text.match(/\bduring\s+(nighttime|daytime)\b/i);
  const biomeM = text.match(/(?:if current biome is|during)\s+([^.;]+?)\s*$/i);
  if (phaseM) {
    effect.cond = { kind: "phase", phase: phaseM[1].toLowerCase() === "daytime" ? "day" : "night" };
  } else if (biomeM && !/nighttime|daytime/i.test(biomeM[1])) {
    const biomes = biomeM[1].split(/\s*,\s*|\s+or\s+|\s+and\s+/i).map(s => biomeMatchName(s)).filter(Boolean);
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
    // ── Bonus Roll mechanics (a single wiki piece may carry several at once,
    //    e.g. Blessed Tide: "Countdown ... -> 6 rolls, Multiplier ... -> 3x") ──
    if (/bonus\s+roll/i.test(p)) {
      let parsed = false;
      if (/removes?\s+bonus\s+roll/i.test(p)) {
        effect.removeBonus = true;
        parsed = true;
      }
      // "Bonus Roll Countdown is moved from 10 rolls -> 6 rolls"
      let m2 = p.match(/from\s+[\d.]+\s*rolls?\s*(?:->|to)\s*([\d.]+)\s*rolls?/i);
      if (m2 && /countdown|cooldown/i.test(p)) {
        effect.bonusCd = Number(m2[1]);
        parsed = true;
      }
      // "10 -> 5 Bonus Roll Cooldown"
      m2 = p.match(/([\d.]+)\s*(?:->|to)\s*([\d.]+)\s*bonus\s+roll\s*(?:countdown|cooldown)/i);
      if (m2) {
        effect.bonusCd = Number(m2[2]);
        parsed = true;
      }
      if (/multi/i.test(p)) {
        // "x1.3 Bonus Roll Multiplier on Every Roll" — relative factor first
        m2 = p.match(/^x\s*([\d.]+)\s*bonus\s+roll\s*multi\w*/i);
        if (m2) {
          effect.bonusMultFactor = Number(m2[1]);
          parsed = true;
        } else {
          // "Bonus RollMultiplier isupgraded from 2x -> 3x"
          m2 = p.match(/from\s+[\d.]+x?\s*(?:->|to)\s*([\d.]+)x/i);
          if (m2 && /multi/i.test(p)) {
            effect.bonusMult = Number(m2[1]);
            parsed = true;
          }
          // "2x -> 11x Bonus Roll Multiplier"
          m2 = p.match(/([\d.]+)x\s*(?:->|to)\s*([\d.]+)x\s*bonus\s+roll\s*multi\w*/i);
          if (m2) {
            effect.bonusMult = Number(m2[2]);
            parsed = true;
          }
          // "2 -> 6 Bonus Roll Multiply (Every 10th roll)"
          m2 = p.match(/([\d.]+)\s*(?:->|to)\s*([\d.]+)\s*bonus\s+roll\s*multi\w*/i);
          if (m2) {
            effect.bonusMult = Number(m2[2]);
            parsed = true;
          }
        }
      }
      // Tide: "The Bonus Roll allows you to roll Rainy Auras with Native
      // Rarity regardless of current Biome" — pool-level rule, modeled as a
      // bonus-roll-only aura pool at native rarity.
      const rollNative = p.match(/allows?\s+you\s+to\s+roll\s+([a-z][a-z ]*?)\s+auras?\s+with\s+native\s+rarity/i);
      if (rollNative) {
        effect.bonusAuraBiomes.push(biomeMatchName(rollNative[1]));
        parsed = true;
      }
      if (parsed) {
        any = true;
        continue;
      }
      notes.push(p);
      continue;
    }
    // ── Periodic luck spikes ──
    if (/every\s+\d|next\s+\d+\s+rolls/i.test(p)) {
      // "Next 10 Rolls grant x2.5 Luck (Every 20th Roll)" and
      // "Next 100 rolls grant x14 Basic Luck for every 1000th roll"
      let m2 = p.match(/next\s+(\d+)\s+rolls?\s+grant\s+x([\d.]+)(?:\s*(?:base\s+|basic\s+)?luck)?(?:\s*\(?\s*(?:for\s+)?every\s+(\d+)(?:th)?\s*roll\s*\)?)?/i);
      if (m2) {
        effect.everyWindow = Number(m2[1]);
        effect.everyMult = Number(m2[2]);
        const ev = p.match(/every\s+(\d+)(?:th)?\s*roll/i);
        effect.everyN = m2[3] ? Number(m2[3]) : (ev ? Number(ev[1]) : null);
        any = true;
        continue;
      }
      // "x14 Basic Luck for every 1000th roll"
      m2 = p.match(/x([\d.]+)\s*(?:base\s+|basic\s+)?luck(?:\s+for)?\s+every\s+(\d+)(?:th)?\s*roll/i);
      if (m2) {
        effect.everyMult = Number(m2[1]);
        effect.everyN = Number(m2[2]);
        const win = p.match(/next\s+(\d+)\s+rolls?/i);
        effect.everyWindow = win ? Number(win[1]) : 1;
        any = true;
        continue;
      }
      // "5x Luck every 11 rolls" / "4x Luck every 6th roll" — multiplier with
      // a trailing x sits BEFORE the word Luck.
      m2 = p.match(/([\d.]+)x?\s*(?:base\s+|basic\s+)?luck\s+every\s+(\d+)(?:th)?\s+rolls?/i);
      if (m2) {
        effect.everyMult = Number(m2[1]);
        effect.everyN = Number(m2[2]);
        effect.everyWindow = 1;
        any = true;
        continue;
      }
      notes.push(p);
      continue;
    }
    // ── Per-stack caps ("+0.05% Basic Luck per stack up to 250% at 5,000 stacks") ──
    if (/per\s+stack/i.test(p)) {
      const m2 = p.match(/up\s+to\s+([\d.]+)%/i);
      if (m2) {
        effect.stackCap = Number(m2[1]);
        any = true;
        continue;
      }
      notes.push(p);
      continue;
    }
    // ── Randomized boosts ("Granting 0-30% Luck/Roll Speed (randomized per 10 rolls)") ──
    if (/randomized/i.test(p)) {
      const m2 = p.match(/([\d.]+)\s*-\s*([\d.]+)%/);
      if (m2) {
        effect.randomPct = Number(m2[2]);
        any = true;
        continue;
      }
      notes.push(p);
      continue;
    }
    // ── Rarity decrease ("20% Rarity Decrease on Halloween Auras ...") ──
    if (/rarity\s+decrease/i.test(p)) {
      const m2 = p.match(/([\d.]+)%\s*rarity\s+decrease/i);
      if (m2) {
        effect.rarityCut = Number(m2[1]);
        any = true;
        continue;
      }
      notes.push(p);
      continue;
    }
    // Economy-only effects stay descriptive notes.
    if (/dark\s+point|duplicate|\bcoins\b/i.test(p)) {
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
  // Panel aura notifications fire only for drops at/above this rarity.
  // The floor is 99,000,000 on purpose: the panel should not spam about
  // medium drops (the old default was 100,000).
  notify_aura_min_rarity: 99000000,
  notify_rare_biomes: true,
  discord_enabled: false,
  discord_webhook_url: "",
  vip: false,
  vip_plus: false,
};

const DEFAULT_SAVE: SimSave = {
  version: 1,
  stats: { rolls: 0, unique_auras: [], counts: {}, rarest: null, biome_visits: {}, playtime_s: 0, log: [], biome_log: [] },
  settings: { ...DEFAULT_SETTINGS },
  gauntlets: { left: null, right: null, pocket: null },
};

// ── One-roll potions (Sandbox) ─────────────────────────────────────
// Values and mechanics verified on Fandom ("Luck" and "Effects" pages):
// one-roll "special buffs" add FLAT luck AFTER bonus-roll multiplication;
// Oblivion / Pump King's Blood wipe the other buffs first; stacking the
// same potion only extends its DURATION, never the boost; Oblivion cannot
// be used together with a Heavenly Potion (Effects page).
type PotionKey = "heavenly" | "bound" | "dune" | "red_moon_1" | "red_moon_2" | "oblivion" | "pump_king" | "popping" | "godlike";

type PotionDef = {
  key: PotionKey;
  name: string;
  effect: string;          // in-game effect name, shown in logs
  specialLuck: number;     // flat Special Luck (added after the bonus roll)
  gated?: { name: string; N: number }[];  // fixed, luckless aura rolls
  wipesOthers?: boolean;   // disables the other buffs while it lasts
  conflicts?: PotionKey[]; // hard "cannot be used together" pairs
};

const POTIONS: PotionDef[] = [
  { key: "popping", name: "Popping Potion", effect: "Popping Blessing", specialLuck: 10000 },
  { key: "dune", name: "Potion of the Dune", effect: "Burrower's Gift", specialLuck: 10000, gated: [{ name: "Neferkhaf", N: 1000 }] },
  { key: "red_moon_1", name: "Red Moon Potion I", effect: "Fragmented Moonlight", specialLuck: 11000, gated: [{ name: "Fragments of the Crimson Moon", N: 1000 }] },
  { key: "bound", name: "Potion of Bound", effect: "Binding", specialLuck: 50000 },
  { key: "heavenly", name: "Heavenly Potion", effect: "Heavenly", specialLuck: 150000, conflicts: ["oblivion"] },
  { key: "red_moon_2", name: "Red Moon Potion II", effect: "絶滅", specialLuck: 200000, gated: [{ name: "Fragments of the Crimson Moon", N: 100 }] },
  { key: "godlike", name: "Godlike Potion", effect: "Deification", specialLuck: 400000 },
  {
    key: "oblivion", name: "Oblivion Potion", effect: "Oblivion", specialLuck: 600000, wipesOthers: true, conflicts: ["heavenly"],
    gated: [{ name: "Oblivion", N: 2000 }, { name: "Memory", N: 100 }],
  },
  { key: "pump_king", name: "Pump King's Blood", effect: "BLOOD DREAM", specialLuck: 700000, wipesOthers: true },
];

type PotionState = Record<PotionKey, number>; // rolls remaining per effect (stacking = duration)
const EMPTY_POTIONS: PotionState = {
  heavenly: 0, bound: 0, dune: 0, red_moon_1: 0, red_moon_2: 0, oblivion: 0, pump_king: 0,
  popping: 0, godlike: 0,
};

/** Per-roll potion resolution: BLOOD DREAM wins over Oblivion, and either of
 *  those wipes-potions suppresses every other effect for the roll (only gear
 *  and final-luck multipliers survive — VIP stays, per the Oblivion page). */
const resolvePotions = (state: PotionState) => {
  const used: string[] = [];
  const suppressed: string[] = [];
  const gated: { name: string; N: number }[] = [];
  let special = 0;
  const pkb = state.pump_king > 0;
  const oblivion = !pkb && state.oblivion > 0;
  for (const def of POTIONS) {
    if (state[def.key] <= 0) continue;
    if ((pkb && def.key !== "pump_king") || (oblivion && def.key !== "oblivion")) {
      suppressed.push(def.name);
      continue;
    }
    special += def.specialLuck;
    used.push(def.effect);
    for (const g of def.gated || []) gated.push(g);
  }
  // If both Red Moon tiers are up the aura keeps its BEST fixed chance only.
  const bestGate = new Map<string, number>();
  for (const g of gated) bestGate.set(g.name, Math.min(bestGate.get(g.name) ?? Infinity, g.N));
  return {
    special,
    used,
    suppressed,
    gated: [...bestGate.entries()].map(([name, N]) => ({ name, N })),
  };
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
  // The wiki publishes the tier names but not tier colours, so these two are
  // the panel's own shades for the challenged auras.
  Challenged: "#FF4D6D",
  "Challenged+": "#00E5FF",
  Event: "#21FF11",
};

/** GLITCHED's name is never static in-game — shimmer it with random glyphs. */
const GLITCH_GLYPHS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ#$%&@!?<>/\\|0123456789";
const GlitchLabel = ({ text }: { text: string }) => {
  const [shown, setShown] = useState(text);
  useEffect(() => {
    const id = window.setInterval(() => {
      setShown(text.split("").map(ch =>
        ch === " " || Math.random() < 0.78
          ? ch
          : GLITCH_GLYPHS[Math.floor(Math.random() * GLITCH_GLYPHS.length)],
      ).join(""));
    }, 350);
    return () => window.clearInterval(id);
  }, [text]);
  return <>{shown}</>;
};

/** Glitched ambience: small coloured blocks that appear in random places and
 *  are gone again a moment later. */
const GlitchSquares = () => {
    const ref = useRef<HTMLCanvasElement | null>(null);
    useEffect(() => {
        const canvas = ref.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        const COLORS = ["#ff3b6b", "#ffd93d", "#3ddc97", "#4fc3f7", "#c77dff", "#ff8a3d", "#ffffff", "#00ffc8"];
        type Block = { x: number; y: number; w: number; h: number; age: number; life: number; color: string };
        const blocks: Block[] = [];
        let width = 0;
        let height = 0;
        let frame = 0;
        const resize = () => {
            const dpr = Math.min(2, window.devicePixelRatio || 1);
            width = canvas.clientWidth || window.innerWidth;
            height = canvas.clientHeight || window.innerHeight;
            canvas.width = Math.max(1, Math.floor(width * dpr));
            canvas.height = Math.max(1, Math.floor(height * dpr));
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        };
        resize();
        window.addEventListener("resize", resize);
        const spawn = () => {
            const size = 8 + Math.random() * 30;
            const life = 6 + Math.floor(Math.random() * 14);
            blocks.push({
                x: Math.random() * Math.max(1, width - size),
                y: Math.random() * Math.max(1, height - size),
                w: size,
                h: size * (0.35 + Math.random() * 1.3),
                age: 0,
                life,
                color: COLORS[Math.floor(Math.random() * COLORS.length)],
            });
        };
        let raf = 0;
        const tick = () => {
            raf = requestAnimationFrame(tick);
            frame++;
            ctx.clearRect(0, 0, width, height);
            // A handful of blocks, and a new one popping up every few frames.
            const wanted = 10 + Math.floor(Math.random() * 12);
            while (blocks.length < wanted) spawn();
            if (frame % 3 === 0) spawn();
            for (let i = blocks.length - 1; i >= 0; i--) {
                const b = blocks[i];
                b.age++;
                if (b.age >= b.life) { blocks.splice(i, 1); continue; }
                // Fade in and out again - a block that just appears looks
                // like a glitch, a block that grows in and dissolves does not.
                const t = b.age / b.life;
                const fade = t < 0.25 ? t / 0.25 : (1 - (t - 0.25) / 0.75);
                ctx.globalAlpha = 0.55 * Math.max(0, fade);
                ctx.fillStyle = b.color;
                ctx.fillRect(b.x, b.y, b.w, b.h);
            }
            ctx.globalAlpha = 1;
        };
        raf = requestAnimationFrame(tick);
        return () => {
            cancelAnimationFrame(raf);
            window.removeEventListener("resize", resize);
        };
    }, []);
    return <canvas ref={ref} className="sim-fx sim-fx-glitch-squares" />;
};

/** The moon phases of the Radiant Forest, from the new moon to the old one.
 *  illum is the lit part of the disc, waxing tells which side is lit.
 *  The row is mirrored around the full moon: the last three are the
 *  reflections of the first three. */
const RADIANT_MOONS: { illum: number; waxing: boolean }[] = [
    { illum: 0.02, waxing: true },   // new moon
    { illum: 0.25, waxing: true },   // waxing crescent
    { illum: 0.5, waxing: true },    // first quarter
    { illum: 0.98, waxing: true },   // full moon - the middle of the row
    { illum: 0.5, waxing: false },   // last quarter - mirror of the first quarter
    { illum: 0.25, waxing: false },  // waning crescent - mirror of the waxing crescent
    { illum: 0.02, waxing: false },  // old moon - mirror of the new moon
];

/** The Radiant Forest: stars that fall and dissolve at the bottom, and a row
 *  of moon phases from the new moon to the old one. */
const RadiantForest = () => {
    const ref = useRef<HTMLCanvasElement | null>(null);
    useEffect(() => {
        const canvas = ref.current;
        if (!canvas) return;
        const ctx = canvas.getContext("2d");
        if (!ctx) return;
        type Star = { x: number; y: number; r: number; speed: number; bright: number };
        let stars: Star[] = [];
        let width = 0;
        let height = 0;
        const seedStars = () => {
            stars = [];
            const count = Math.max(18, Math.round((width * height) / 22000));
            for (let i = 0; i < count; i++) {
                stars.push({
                    x: Math.random() * width,
                    y: Math.random() * height,
                    r: 0.5 + Math.random() * 1.6,
                    speed: 14 + Math.random() * 40,
                    bright: 0.35 + Math.random() * 0.5,
                });
            }
        };
        const resize = () => {
            const dpr = Math.min(2, window.devicePixelRatio || 1);
            width = canvas.clientWidth || window.innerWidth;
            height = canvas.clientHeight || window.innerHeight;
            canvas.width = Math.max(1, Math.floor(width * dpr));
            canvas.height = Math.max(1, Math.floor(height * dpr));
            ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
            seedStars();
        };
        resize();
        window.addEventListener("resize", resize);

        const NIGHT = "rgba(34, 20, 62, 0.92)";
        const LIT = "rgba(240, 233, 255, 0.92)";
        const drawMoon = (cx: number, cy: number, r: number, illum: number, waxing: boolean) => {
            // The night side.
            ctx.fillStyle = NIGHT;
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, Math.PI * 2);
            ctx.fill();
            // The lit half.
            ctx.fillStyle = LIT;
            ctx.beginPath();
            ctx.arc(cx, cy, r, waxing ? -Math.PI / 2 : Math.PI / 2, waxing ? Math.PI / 2 : Math.PI * 1.5);
            ctx.fill();
            // The terminator: the ellipse carves the crescent out of the lit
            // half, or adds the bulge of a gibbous. It is only skipped when
            // it collapses into a straight line (the quarter phases).
            const a = r * Math.abs(1 - 2 * illum);
            if (a > 0.01) {
                ctx.beginPath();
                ctx.ellipse(cx, cy, a, r, 0, 0, Math.PI * 2);
                ctx.fillStyle = illum <= 0.5 ? NIGHT : LIT;
                ctx.fill();
            }
        };

        let raf = 0;
        let last = performance.now();
        const tick = (now: number) => {
            raf = requestAnimationFrame(tick);
            const dt = Math.min(0.05, (now - last) / 1000);
            last = now;
            ctx.clearRect(0, 0, width, height);

            // The stars fall and dissolve before they reach the bottom, so
            // the reset at the top is never visible.
            for (const s of stars) {
                s.y += s.speed * dt;
                if (s.y > height + 4) {
                    s.y = -4 - Math.random() * 30;
                    s.x = Math.random() * width;
                }
                const fade = Math.min(1, Math.max(0, (height - s.y) / (height * 0.3)));
                const alpha = s.bright * fade;
                if (alpha <= 0.01) continue;
                ctx.fillStyle = `rgba(255, 250, 255, ${alpha.toFixed(3)})`;
                ctx.beginPath();
                ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
                ctx.fill();
            }

            // The row of moons: new moon first, old moon last. A soft band of
            // light travels along the row and wraps around.
            const count = RADIANT_MOONS.length;
            const r = 9;
            const gap = 26;
            const stripW = (count - 1) * gap;
            const cx0 = width / 2 - stripW / 2;
            const cy = 18 + r;
            const bandX = ((now / 4200) % 1) * (width + 240) - 120;
            for (let i = 0; i < count; i++) {
                const phase = RADIANT_MOONS[i];
                const cx = cx0 + i * gap;
                const near = Math.max(0, 1 - Math.abs(cx - bandX) / 150);
                const glow = ctx.createRadialGradient(cx, cy, 0, cx, cy, r * 3.2);
                glow.addColorStop(0, `rgba(214, 170, 255, ${(0.10 + near * 0.30).toFixed(3)})`);
                glow.addColorStop(1, "rgba(214, 170, 255, 0)");
                ctx.fillStyle = glow;
                ctx.beginPath();
                ctx.arc(cx, cy, r * 3.2, 0, Math.PI * 2);
                ctx.fill();
                drawMoon(cx, cy, r, phase.illum, phase.waxing);
            }
        };
        raf = requestAnimationFrame(tick);
        return () => {
            cancelAnimationFrame(raf);
            window.removeEventListener("resize", resize);
        };
    }, []);
    return <canvas ref={ref} className="sim-fx sim-fx-canvas" />;
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

/** The tier names the wiki uses. Everything outside this list is a leftover
 *  label that must not be shown as a tier. */
const KNOWN_TIERS = new Set([
  "basic", "epic", "unique", "legendary", "mythic", "exalted", "glorious",
  "transcendent", "challenged", "challenged+",
]);

/** The tier of an aura. The wiki's own rarity name wins — it is the only
 *  source that knows about the Challenged / Challenged+ tiers, which sit on
 *  top of the normal bands (Monarch, Hellborn, Illusionary, Meta, …). The
 *  numeric bands are the fallback for auras whose entry has no name. */
const auraTier = (a: any, n: number): string => {
  const raw = String(a?.rarity_name || "").trim();
  if (raw) {
    const key = raw.toLowerCase();
    if (KNOWN_TIERS.has(key)) {
      if (key === "challenged+") return "Challenged+";
      return raw.charAt(0).toUpperCase() + raw.slice(1).toLowerCase();
    }
  }
  return rarityTier(n);
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
/** The wiki lists Breakthrough as the one aura that is unobtainable in a
 *  biome — it drops in every biome except Null. */
const NULL_EXCLUDED_AURAS = new Set(["BREAKTHROUGH"]);
// "Halloween Auras" (Vampire Hunter): auras exclusive to the Halloween biomes.
const HALLOWEEN_BIOMES = new Set(["PUMPKIN MOON", "GRAVEYARD", "BLOOD RAIN"]);

/** Rarity names of auras that are not rollable in the current game state.
 *  "Event" covers the seasonal event auras (they only exist while their
 *  event runs), "Dev Exclusive" was never released to players and "Removed"
 *  was taken out again. The flags above already catch most of them, this is
 *  the second line of defence — a new event aura that arrives without the
 *  "limited" flag still must not drop in the simulator.
 *  Flip "event" out of this set when an event is live and its auras should
 *  be rollable again. */
const EXCLUDED_TIERS = new Set(["event", "dev exclusive", "removed"]);

const isSimRollable = (key: string, a: Data): boolean => {
  if (a?.rarity_is_potion) return false;
  const flags: string[] = Array.isArray(a?.flags) ? a.flags : [];
  if (flags.some(f => EXCLUDED_FLAGS.has(String(f).toLowerCase()))) return false;
  if (EXCLUDED_TYPES.has(String(a?.obtainment_type || "").toLowerCase())) return false;
  if (EXCLUDED_TIERS.has(String(a?.rarity_name || "").trim().toLowerCase())) return false;
  // Effect-gated rolls: the aura only rolls while an admin/effect buff is up
  // (Megaphone during "YG Blessing", Astral : Astrald during "Astrald Luck!").
  // Without that effect the sim must never drop them — same rule that keeps
  // seasonal event auras out until their season returns.
  if (/only rolls while\b.*\bis active/i.test(String(a?.obtainment || ""))) return false;
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
    if (biomeKey === "NULL" && NULL_EXCLUDED_AURAS.has(name.trim().toUpperCase().replace(/\s+/g, "_"))) continue;
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
      tier: auraTier(a, N),
      exclusive: isExcl,
      native,
      luckExempt: !!a?.luck_exempt,
      excl: exclAll,
    });
  }
  out.sort((x, y) => y.N - x.N);
  return out;
};

/** The Fandom "Luck Formula" — Sol's RNG's real roll algorithm:
 *    Luck = (((1 + Basic Luck) * Bonus Roll Multiplier) + Special Luck) * VIP
 *    List Value = floor(Base Value / Luck)
 *  The pool is walked RAREST-FIRST; a random number from 1 to the List Value
 *  must come up 1 for the aura to drop. Auras whose List Value is 1 (fully
 *  saturated by luck) leave the walk — the rarest of them is the fallback
 *  when nothing else hits. Fixed-rarity auras (Illusionary, Meta, Cryogenic
 *  and potion-gated drops like Neferkhaf) sit at the START of the list and
 *  roll at their raw 1 in N: luck never touches them. */
const rollByFormula = (
  fixed: PoolAura[],
  pool: PoolAura[],
  luck: number,
  nFactor?: (a: PoolAura) => number,
): PoolAura | null => {
  const hit = (N: number) => Math.floor(Math.random() * Math.max(1, N)) === 0; // random(1..N) == 1
  for (const a of fixed) {
    if (hit(Math.max(1, Math.round(a.N)))) return a;
  }
  const guaranteed: PoolAura[] = [];
  for (const a of pool) {
    const n = Math.max(1, a.N * (nFactor ? Math.max(0.01, nFactor(a)) : 1));
    const listValue = Math.floor(n / Math.max(1, luck));
    if (listValue <= 1) { guaranteed.push(a); continue; }
    if (hit(listValue)) return a;
  }
  return guaranteed[0] ?? pool[pool.length - 1] ?? fixed[0] ?? null;
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
.sim-fx{position:fixed;inset:0;pointer-events:none;z-index:9000;contain:strict}
/* Rare-biome ambience. Every biome gets the look its own wiki entry
   describes (Glitched corrupts the screen, Hell burns from below, The
   Radiant Forest falls with stars and moons). Only gradients and
   transform/opacity are animated, so the panel stays light. */
/* Glitched: the client tears itself apart — small coloured blocks pop up in
   random places and are gone again a moment later. They are drawn on a
   canvas, a repeating background cannot place them. */
.sim-fx-glitch-squares{width:100%;height:100%}
/* Dreamspace: a soft violet haze with slow drifting lights. */
.sim-fx-dream{background:radial-gradient(55% 45% at 18% 12%,rgba(217,70,239,.24),transparent 60%),radial-gradient(50% 40% at 85% 85%,rgba(168,85,247,.20),transparent 60%);animation:simFxDream 9s ease-in-out infinite alternate}
/* Both light layers share one tile size and the drift covers exactly one
   tile, so the loop closes without a jump. */
.sim-fx-dream::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 30% 40%,rgba(255,255,255,.16) 0 2px,transparent 3px),radial-gradient(circle at 70% 65%,rgba(255,255,255,.13) 0 2px,transparent 3px);background-size:200px 200px;animation:simFxDreamB 16s linear infinite}
@keyframes simFxDream{from{opacity:.6}to{opacity:1}}
@keyframes simFxDreamB{from{transform:translateY(0)}to{transform:translateY(-200px)}}
/* Cyberspace: a cyan data grid that scrolls over the panel. */
.sim-fx-cyber{background:repeating-linear-gradient(0deg,rgba(34,211,238,.09) 0 1px,transparent 1px 6px),repeating-linear-gradient(90deg,rgba(34,211,238,.07) 0 1px,transparent 1px 6px),radial-gradient(45% 35% at 50% 0%,rgba(34,211,238,.16),transparent 70%);animation:simFxCyber 4s linear infinite}
@keyframes simFxCyber{from{background-position:0 0,0 0,0 0}to{background-position:0 48px,48px 0,0 0}}
/* Singularity: a real gravitational well — a dark core, a rotating
   accretion disk with a hole in the middle, a bright photon ring on the
   event horizon and a shockwave that falls inward. */
.sim-fx-sing{background:radial-gradient(34% 34% at 50% 44%,rgba(0,0,0,.9) 0 42%,rgba(88,8,8,.42) 68%,transparent 84%),radial-gradient(78% 62% at 50% 48%,rgba(239,68,68,.12),transparent 72%);animation:simFxSing 6.5s ease-in-out infinite}
.sim-fx-sing::before{content:"";position:absolute;left:50%;top:44%;width:min(56vmin,62%);aspect-ratio:1;transform:translate(-50%,-50%);border-radius:50%;background:conic-gradient(from 0deg,rgba(255,196,110,0) 0deg,rgba(255,150,50,.78) 42deg,rgba(196,32,20,.86) 96deg,rgba(255,196,110,0) 160deg,rgba(126,72,255,.34) 226deg,rgba(255,150,50,.7) 300deg,rgba(255,196,110,0) 360deg);-webkit-mask:radial-gradient(circle,transparent 33%,#000 45%,#000 76%,transparent 87%);mask:radial-gradient(circle,transparent 33%,#000 45%,#000 76%,transparent 87%);animation:simFxSingA 7.5s linear infinite}
.sim-fx-sing::after{content:"";position:absolute;left:50%;top:44%;width:min(56vmin,62%);aspect-ratio:1;transform:translate(-50%,-50%);border-radius:50%;background:radial-gradient(circle,transparent 0 20%,rgba(255,228,190,.28) 31%,rgba(255,158,72,.16) 44%,transparent 62%);box-shadow:0 0 0 1px rgba(255,214,160,.45),0 0 26px 6px rgba(255,120,40,.22);animation:simFxSingB 3.6s cubic-bezier(.4,0,.6,1) infinite}
@keyframes simFxSing{0%,100%{opacity:.7}50%{opacity:1}}
@keyframes simFxSingA{from{transform:translate(-50%,-50%) rotate(0deg) scale(1)}to{transform:translate(-50%,-50%) rotate(360deg) scale(1.05)}}
@keyframes simFxSingB{0%{transform:translate(-50%,-50%) scale(1.22);opacity:0}25%{opacity:.95}100%{transform:translate(-50%,-50%) scale(.82);opacity:0}}
/* The Radiant Forest: a violet night. The stars and the row of moon phases
   are drawn on a canvas - they have to fade out and wrap around smoothly. */
.sim-fx-radiant{background:radial-gradient(30% 24% at 50% 6%,rgba(216,110,255,.26),transparent 72%),linear-gradient(180deg,rgba(138,72,168,.26),rgba(26,14,44,.14) 48%,transparent 78%)}
.sim-fx-canvas{width:100%;height:100%}
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
  // Mirror of settings/loadout for persist(): the save callback must never
  // capture a stale render's values (see the persist() implementation).
  const saveStateRef = useRef<{ settings: SimSettings; loadout: SimSave["gauntlets"] }>({ settings, loadout });
  saveStateRef.current = { settings, loadout };
  // One-roll potions armed for the next rolls (Sandbox): each key holds the
  // number of rolls its effect still lasts (stacking = duration, not boost).
  const [potions, setPotions] = useState<PotionState>({ ...EMPTY_POTIONS });
  const potionsRef = useRef<PotionState>({ ...EMPTY_POTIONS });
  potionsRef.current = potions;
  const [statsView, setStatsView] = useState<SimStats>(DEFAULT_SAVE.stats);
  const [lastDrop, setLastDrop] = useState<PoolAura | null>(null);
  const [rollSeq, setRollSeq] = useState(0);
  const [toast, setToast] = useState<{ title: string; body: string; color: string } | null>(null);
  const [world, setWorld] = useState<{ biome: BiomeRuntime | null; phase: "day" | "night"; phaseEndsAt: number }>({
    biome: null, phase: "day", phaseEndsAt: Date.now() / 1000 + DAY_LENGTH_S,
  });
  const [forceBiome, setForceBiome] = useState("");
  const [confirmReset, setConfirmReset] = useState(false);

  const statsRef = useRef<SimStats>(structuredClone(DEFAULT_SAVE.stats));
  const saveTimerRef = useRef(0);
  // Blocks persist() until the previous save file has been READ: the mount
  // effects used to flush DEFAULT settings over sim_save.json before the
  // async sim_load_save arrived, wiping the previous run's settings.
  const hydratedRef = useRef(false);
  const discordGateRef = useRef(0);
  const rollAccRef = useRef(0);
  const cooldownUntilRef = useRef(0);
  const cooldownMsRef = useRef(500);
  const lastUiRef = useRef(0);
  const doRollRef = useRef<(fromAuto?: boolean) => void>(() => {});
  const worldRef = useRef(world);
  worldRef.current = world;
  // Randomized gear value (0..randomPct) and the periodic luck-spike windows
  // ("Next 10 Rolls grant x2.5 Luck (Every 20th Roll)"). Both are mirrored in
  // refs so the math inside doRoll never sees a stale value mid re-render, and
  // several gauntlets can hold overlapping spikes at once.
  const [randFx, setRandFx] = useState(0);
  const randFxRef = useRef(0);
  const spikeRef = useRef<{ until: number; mult: number; label: string }[]>([]);
  // Per-roll technique HUD (bonus-roll countdown, active luck spikes) so the
  // gear abilities are visible in practice, not just in the chips list.
  const [fxHud, setFxHud] = useState<{ bonusIn: number | null; spikeMult: number; spikeLeft: number; spikeLabel: string | null }>({
    bonusIn: null, spikeMult: 1, spikeLeft: 0, spikeLabel: null,
  });
  // Luck history for the sparkline: the effective luck of the last rolls
  // plus the markers of the bonus rolls and the luck spikes.
  const [luckHistory, setLuckHistory] = useState<{ roll: number; luck: number; bonus: boolean; spike: number }[]>([]);

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
      if (!saveApplied && saveVal?.success && saveVal.data && typeof saveVal.data === "object") {
        saveApplied = true;
        hydratedRef.current = true;
        const saved = saveVal.data as SimSave;
        if (Object.keys(saved).length) {
          const stats: SimStats = { ...DEFAULT_SAVE.stats, ...(saved.stats || {}) };
          stats.unique_auras = Array.isArray(stats.unique_auras) ? stats.unique_auras : [];
          stats.counts = stats.counts && typeof stats.counts === "object" ? stats.counts : {};
          stats.log = Array.isArray(stats.log) ? stats.log : [];
          stats.biome_log = Array.isArray(stats.biome_log) ? stats.biome_log : [];
          stats.biome_visits = stats.biome_visits && typeof stats.biome_visits === "object" ? stats.biome_visits : {};
          statsRef.current = stats;
          setStatsView({ ...stats, unique_auras: [...stats.unique_auras], log: [...stats.log] });
          const mergedSettings: SimSettings = { ...DEFAULT_SETTINGS, ...(saved.settings || {}) };
          // Migration: the old default threshold (100,000) means "never set
          // by the user" — move such saves onto the new 99,000,000 floor.
          if (Number(mergedSettings.notify_aura_min_rarity) === 100000) {
            mergedSettings.notify_aura_min_rarity = DEFAULT_SETTINGS.notify_aura_min_rarity;
          }
          setSettings(mergedSettings);
          const gl = saved.gauntlets || {};
          setLoadout({ left: gl.left ?? null, right: gl.right ?? null, pocket: gl.pocket ?? null });
        }
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
      if (!hydratedRef.current) return;
      // Read the LATEST settings/loadout from the mirror ref: a debounced
      // closure would write the values from the render that scheduled it,
      // silently reverting any setting changed after that moment.
      const payload: SimSave = {
        version: 1,
        stats: statsRef.current,
        settings: saveStateRef.current.settings,
        gauntlets: saveStateRef.current.loadout,
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
  }, []);

  // ── Derived: gauntlet effects, pool, effective rates ──────────────
  const equippedFx = useMemo(() => {
    const merged = {
      biomeMult: {} as Record<string, number>,
      luckPct: 0,
      luckMult: 1,
      speedPct: 0,
      bonusCd: null as number | null,
      bonusMult: null as number | null,
      bonusMultFactor: 1,
      removeBonus: false,
      periodic: [] as { everyN: number; everyMult: number; everyWindow: number }[],
      randomPct: 0,
      stackCap: 0,
      rarityCuts: [] as { cut: number; cond: ClauseEffect["cond"] }[],
      bonusAuraBiomes: [] as string[],
      chips: [] as string[],
      notes: [] as string[],
    };
    const apply = (name: string, e: ClauseEffect, suffix: string) => {
      merged.luckPct += e.luckPct;
      merged.luckMult *= e.luckMult;
      merged.speedPct += e.speedPct;
      if (e.bonusCd != null) merged.bonusCd = merged.bonusCd == null ? e.bonusCd : Math.min(merged.bonusCd, e.bonusCd);
      if (e.bonusMult != null) merged.bonusMult = merged.bonusMult == null ? e.bonusMult : Math.max(merged.bonusMult, e.bonusMult);
      if (e.bonusMultFactor != null) merged.bonusMultFactor *= e.bonusMultFactor;
      if (e.removeBonus) merged.removeBonus = true;
      if (e.everyN != null && e.everyMult != null) {
        merged.periodic.push({ everyN: e.everyN, everyMult: e.everyMult, everyWindow: e.everyWindow || 1 });
      }
      if (e.randomPct != null) merged.randomPct = Math.max(merged.randomPct, e.randomPct);
      if (e.stackCap != null) merged.stackCap += e.stackCap;
      if (e.rarityCut != null) merged.rarityCuts.push({ cut: e.rarityCut, cond: e.cond });
      for (const b of e.bonusAuraBiomes) {
        if (!merged.bonusAuraBiomes.includes(b)) merged.bonusAuraBiomes.push(b);
      }
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
  const gauntletLuck = (1 + (equippedFx.luckPct + equippedFx.stackCap) / 100) * equippedFx.luckMult;
  // randFx: "0-30% Luck/Roll Speed (randomized per 10 rolls)" — refreshed in
  // doRoll every 10 rolls and applied to both luck and roll speed.
  // Gear roll-speed is honest and unbounded (Singularity Gauntlet is x3);
  // only the Sandbox speed cheat itself is limited to x5 by design.
  const effSpeed = Math.max(0.1, (sandbox ? settings.speed : 1) * (1 + equippedFx.speedPct / 100) * (1 + randFx / 100));
  // VIP / VIP+ (Fandom "Effects"): multiply the FINAL luck — x1.2 for VIP and
  // x1.2 for VIP+ (x1.3 when VIP is also owned). These are the only buffs that
  // also multiply the bonus roll / special buffs in the real game.
  // VIP final multiplier per Fandom (Effects page): x1.2 alone, VIP+ is
  // x1.2 too and x1.3 when both passes are owned — NOT 1.2 * 1.3.
  const vipMult = settings.vip && settings.vip_plus ? 1.3 : (settings.vip || settings.vip_plus ? 1.2 : 1);
  // The luck the NEXT roll would use before its own bonus roll / spike, per
  // the Fandom formula ((1 + Basic) * Bonus + Special) * VIP — every toggle
  // and every armed potion must visibly move this number.
  const potPreview = sandbox ? resolvePotions(potions) : { special: 0, used: [] as string[], suppressed: [] as string[], gated: [] as { name: string; N: number }[] };
  const rollLuckNow = Math.max(1, ((sandbox ? settings.luck : 1) * gauntletLuck * (1 + randFx / 100) + potPreview.special) * vipMult);

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

  // Auras by their display name — the potion effects hand out auras that are
  // not part of the pool (Neferkhaf, Oblivion, …) and those still need their
  // wiki tier for the log line.
  const auraByName = useMemo(() => {
    const m = new Map<string, any>();
    for (const a of Object.values(auras)) {
      const nm = String((a as any)?.name || "").trim().toLowerCase();
      if (nm) m.set(nm, a);
    }
    return m;
  }, [auras]);

  // Tide (Blessed Tide / Tide Gauntlet): Bonus Rolls can also hit the listed
  // biome-exclusive auras at their native rarity regardless of current biome.
  const tidePool = useMemo(() => {
    const names = new Set(equippedFx.bonusAuraBiomes);
    if (!names.size) return [];
    const out: PoolAura[] = [];
    for (const [key, a] of Object.entries(auras)) {
      if (!isSimRollable(key, a)) continue;
      const excl = exclusiveRefs(a);
      if (!excl.some(x => names.has(x))) continue;
      const nativeN = Number(a?.native_rarity);
      const globalN = Number(a?.rarity);
      const N = Number.isFinite(nativeN) && nativeN > 0 ? nativeN : (Number.isFinite(globalN) && globalN > 0 ? globalN : NaN);
      if (!Number.isFinite(N) || N <= 0) continue;
      out.push({ name: String(a?.name || key), N, tier: auraTier(a, N), exclusive: true, native: true, luckExempt: !!a?.luck_exempt, excl });
    }
    return out;
  }, [auras, equippedFx.bonusAuraBiomes]);

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
    const fx = equippedFx;
    const st = statsRef.current;
    const rollNo = st.rolls + 1;

    // Randomized gear: a fresh value every 10 rolls applies to the next 10.
    if (fx.randomPct > 0 && (rollNo - 1) % 10 === 0) {
      randFxRef.current = Math.random() * fx.randomPct;
      setRandFx(randFxRef.current);
    }

    // Bonus Roll (game mechanic): every Nth roll multiplies luck — by default
    // every 10th roll gives x2. Gauntlets change the cooldown (10 -> 5/6),
    // the multiplier (2x -> 3x/11x, or x1.3 factor) or remove the roll.
    const bonusCd = fx.bonusCd ?? 10;
    const bonusMult = Math.max(1, (fx.bonusMult ?? 2) * fx.bonusMultFactor);
    const onBonus = !fx.removeBonus && bonusCd > 0 && rollNo % bonusCd === 0;

    // Periodic spikes ("5x Luck every 11 rolls", "Next 100 rolls grant x14
    // Basic Luck for every 1000th roll"). Several gauntlets may hold
    // overlapping spikes — keep them all and multiply the active ones.
    const freshSpike: string[] = [];
    for (const s of fx.periodic) {
      if (s.everyN > 0 && rollNo % s.everyN === 0) {
        const label = `⚡ ${s.everyMult}x luck ×${s.everyWindow} roll${s.everyWindow > 1 ? "s" : ""}`;
        spikeRef.current = [...spikeRef.current.filter(sp => rollNo <= sp.until),
          { until: rollNo + Math.max(1, s.everyWindow) - 1, mult: s.everyMult, label }];
        freshSpike.push(label);
      }
    }
    spikeRef.current = spikeRef.current.filter(sp => rollNo <= sp.until);
    const spikeMult = spikeRef.current.reduce((acc, sp) => acc * sp.mult, 1);

    // ── The Fandom Luck Formula ─────────────────────────────────────
    // Luck = (((1 + Basic Luck) * Bonus Roll Multiplier) + Special Luck) * VIP
    // Basic part: base x Sandbox cheat x gauntlets/stacks x randomized gear.
    // Bonus roll and Darkshader-style streaks multiply that part. One-roll
    // potion "Special Luck" is ADDED after the multiplication. VIP then
    // multiplies the total. Oblivion / Pump King's Blood suppress the other
    // potion effects for their roll (gear and VIP survive, per the wiki).
    const pot = sandbox
      ? resolvePotions(potionsRef.current)
      : { special: 0, used: [] as string[], suppressed: [] as string[], gated: [] as { name: string; N: number }[] };
    const liveRand = fx.randomPct > 0 ? randFxRef.current : 0;
    const basicTerm = Math.max(0, (sandbox ? settings.luck : 1) * gauntletLuck * (1 + liveRand / 100));
    const bonusTerm = (onBonus ? bonusMult : 1) * spikeMult;
    const rollLuck = Math.max(1, (basicTerm * bonusTerm + pot.special) * vipMult);

    // Technique markers carried into the drop log, so bonus rolls and luck
    // spikes are visible in practice instead of silent number changes.
    const fxTags: string[] = [];
    if (onBonus) fxTags.push(`🎁 bonus roll ×${bonusMult}`);
    if (spikeMult > 1) fxTags.push(`⚡ spike ×${spikeMult}`);
    for (const label of freshSpike) fxTags.push(label);
    for (const u of pot.used) fxTags.push(`🧪 ${u}`);
    if (pot.suppressed.length) fxTags.push(`🧪 ${pot.suppressed.length} effect${pot.suppressed.length > 1 ? "s" : ""} suppressed`);
    setFxHud({
      bonusIn: fx.removeBonus || bonusCd <= 0 ? null : bonusCd - (rollNo % bonusCd),
      spikeMult,
      spikeLeft: spikeRef.current.length
        ? Math.max(0, Math.min(...spikeRef.current.map(sp => sp.until - rollNo + 1)))
        : 0,
      spikeLabel: spikeRef.current.length ? spikeRef.current.map(sp => sp.label).join(" + ") : null,
    });

    // "20% Rarity Decrease on Halloween Auras" — shrink 1 in N of matching
    // auras while the clause condition (Halloween biomes / Glitched) holds.
    const condActive = (cond: ClauseEffect["cond"]): boolean => {
      if (!cond) return true;
      return cond.kind === "phase"
        ? cond.phase === worldRef.current.phase
        : !!worldRef.current.biome && cond.biomes.includes(biomeMatchName(worldRef.current.biome.name));
    };
    const rollPool = onBonus && tidePool.length
      ? [...pool, ...tidePool.filter(t => !pool.some(p => p.name === t.name))]
      : pool;
    // Fixed-chance list first (Fandom formula): luck-exempt auras plus the
    // auras unlocked by the active one-roll potion effects, rarest-first.
    const fixedList: PoolAura[] = [];
    for (const a of rollPool) if (a.luckExempt) fixedList.push(a);
    for (const g of pot.gated) {
      const rec = auraByName.get(String(g.name || "").trim().toLowerCase());
      fixedList.push({ name: g.name, N: g.N, tier: auraTier(rec, g.N), exclusive: false, native: false, luckExempt: true, excl: [] });
    }
    fixedList.sort((x, y) => y.N - x.N);
    const scaledPool = rollPool.filter(a => !a.luckExempt);
    const aura = rollByFormula(fixedList, scaledPool, rollLuck, fx.rarityCuts.length
      ? (a) => {
          if (!a.excl.some(x => HALLOWEEN_BIOMES.has(x))) return 1;
          let f = 1;
          for (const rc of fx.rarityCuts) {
            if (condActive(rc.cond)) f *= (1 - rc.cut / 100);
          }
          return f;
        }
      : undefined);
    if (!aura) return;
    cooldownUntilRef.current = now + cooldownMsRef.current;
    setRollSeq(s => s + 1);
    st.rolls += 1;
    // One-roll potions: this roll consumed one charge of every armed effect
    // (stacking several potions of a kind extends the duration — never the
    // boost, per the Fandom Effects page).
    if (sandbox && (pot.used.length || pot.suppressed.length)) {
      const next = { ...potionsRef.current };
      for (const key of Object.keys(next) as PotionKey[]) if (next[key] > 0) next[key] -= 1;
      potionsRef.current = next;
      setPotions(next);
    }
    if (!st.unique_auras.includes(aura.name)) st.unique_auras.push(aura.name);
    st.counts[aura.name] = (st.counts[aura.name] || 0) + 1;
    if (!st.rarest || aura.N > st.rarest.rarity) st.rarest = { name: aura.name, rarity: aura.N };
    const entry: DropLogEntry = {
      name: aura.name, rarity: aura.N, tier: aura.tier,
      biome: worldRef.current.biome ? worldRef.current.biome.name : "NORMAL",
      ts: Date.now(),
      fx: fxTags.length ? fxTags : undefined,
    };
    st.log = [entry, ...st.log].slice(0, 25);
    // Luck history: the effective luck of every roll, so the bonus rolls
    // and the luck spikes are visible as a curve instead of a silent
    // number change.
    setLuckHistory(prev => [
      ...prev,
      {
        roll: rollNo,
        luck: rollLuck,
        bonus: onBonus,
        spike: spikeMult > 1 ? spikeMult : 0,
      },
    ].slice(-LUCK_HISTORY_MAX));
    if (now - lastUiRef.current > 150) {
      lastUiRef.current = now;
      setLastDrop(aura);
    }
    if (aura.N >= Math.max(1, settings.notify_aura_min_rarity)) {
      notify(
        `✦ ${aura.name}`,
        `1 in ${fmtNum(aura.N)} · ${aura.tier} · ${tRef.current("in")} ${entry.biome} (${tRef.current("simulated drop")})${fxTags.length ? " · " + fxTags.join(" ") : ""}`,
        TIER_COLORS[aura.tier] || "#a78bfa",
        true,
      );
    }
    persist();
  }, [pool, tidePool, equippedFx, vipMult, gauntletLuck, sandbox, settings.luck, settings.notify_aura_min_rarity, notify, persist, auraByName]);

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
            // Two biomes are not rolled on their own — they replace another
            // one: Singularity takes the place of Starfall, The Radiant
            // Forest takes the place of Lost Forest (1 in 20, so it shows up
            // now and then, never guaranteed).
            if (biomeMatchName(name) === "STARFALL" && Math.random() < 0.01) name = "SINGULARITY";
            if (biomeMatchName(name) === "LOST FOREST" && Math.random() < 1 / 20) name = "THE RADIANT FOREST";
            const target = biomes[name] || b;
            w.biome = { name, color: String(target.color || "#7c6cff"), endsAt: now + parseDuration(target.duration) };
            const st = statsRef.current;
            st.biome_visits[name] = (st.biome_visits[name] || 0) + 1;
            st.biome_log.push({ name, ts: Date.now(), forced: false });
            if (st.biome_log.length > 200) st.biome_log.splice(0, st.biome_log.length - 200);
            const cat = String(target.category || "weather");
            if (settings.notify_rare_biomes && cat !== "weather" && cat !== "biome") {
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

  // Biomes named by aura data but absent from the wiki Biomes page — right
  // after a game update (Lost Forest, The Radiant Forest) the aura rows know
  // them before the biome article is written. Let Sandbox force-spawn them so
  // their native bonuses are testable here.
  const extraBiomeNames = useMemo(() => {
    const out = new Map<string, string>();
    const consider = (raw: any) => {
      for (const r of splitBiomeRefs(raw)) {
        if (r === "NORMAL" || r === "TIME" || r === "DAYTIME" || r === "NIGHTTIME") continue;
        if (biomes[r] || blockedBiomes.has(r)) continue;
        out.set(r, r);
      }
    };
    for (const a of Object.values(auras)) {
      consider(a?.native_biome?.[0]);
      consider(a?.exclusive_biome?.[0]);
      if (Array.isArray(a?.exclusive_biomes)) a.exclusive_biomes.forEach(consider);
    }
    return out;
  }, [auras, biomes, blockedBiomes]);

  const spawnBiome = useCallback((name: string) => {
    const b = biomes[name] as any;
    const rec = b || (extraBiomeNames.has(name) ? { name, color: "#7c6cff", duration: "5 minutes" } : null);
    if (!rec) return;
    const w = { ...worldRef.current };
    w.biome = { name: rec.name || name, color: String(rec.color || "#7c6cff"), endsAt: Date.now() / 1000 + parseDuration(rec.duration) };
    const st = statsRef.current;
    st.biome_visits[w.biome.name] = (st.biome_visits[w.biome.name] || 0) + 1;
    st.biome_log.push({ name: w.biome.name, ts: Date.now(), forced: true });
    if (st.biome_log.length > 200) st.biome_log.splice(0, st.biome_log.length - 200);
    setWorld(w);
    persist();
  }, [biomes, extraBiomeNames, persist]);

  const resetStats = useCallback(() => {
    statsRef.current = structuredClone(DEFAULT_SAVE.stats);
    setStatsView(structuredClone(DEFAULT_SAVE.stats));
    setLastDrop(null);
    persist(true);
  }, [persist]);

  /** Arm/disarm one-roll potions (Sandbox). Count = how many rolls the effect
   *  lasts. Hard conflict per Fandom: Oblivion cannot be used with Heavenly. */
  const applyPotion = useCallback((key: PotionKey, delta: number) => {
    const next = { ...potionsRef.current };
    next[key] = Math.max(0, Math.min(99, (next[key] || 0) + delta));
    if (next[key] > 0 && key === "oblivion") next.heavenly = 0;
    if (next[key] > 0 && key === "heavenly") next.oblivion = 0;
    potionsRef.current = next;
    setPotions(next);
  }, []);

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

  const biomeList = useMemo(() => {
    const rows = Object.entries(biomes)
      .filter(([key, b]) => key !== "NORMAL" && key !== "TIME" && !["event", "admin"].includes(String(b?.category || "")))
      .map(([key, b]) => ({ key, name: String(b.name || key), color: String(b.color || "#7c6cff"), category: String(b.category || "weather") }));
    for (const [key, name] of extraBiomeNames) rows.push({ key, name, color: "#7c6cff", category: "new" });
    return rows.sort((a, b) => a.name.localeCompare(b.name));
  }, [biomes, extraBiomeNames]);

  const collected = useMemo(() => {
    // Look the aura up in the CURRENT pool first; auras locked to another
    // biome (Monarch, Hellborn, Astraios…) and fixed-chance ones (Illusionary)
    // are absent from it — fall back to their global base rarity so the table
    // never shows an empty chance.
    const byName = new Map<string, any>();
    for (const [key, a] of Object.entries(auras)) {
      const n = String(a?.name || key);
      if (!byName.has(n)) byName.set(n, a);
    }
    return Object.entries(statsView.counts)
      .map(([name, count]) => {
        const info = pool.find(p => p.name === name);
        const rec = byName.get(name);
        const base = Number(rec?.rarity);
        const N = info?.N ?? (Number.isFinite(base) && base > 0 ? base : 0);
        const tier = info?.tier ?? (N > 0 ? auraTier(rec, N) : "Basic");
        return { name, count, N, tier, inPool: !!info };
      })
      .sort((a, b) => b.N - a.N || a.name.localeCompare(b.name));
  }, [statsView.counts, pool, auras]);

  const worldColor = world.biome ? world.biome.color : "#7c6cff";
  // Banner art: the biome's Fandom in-game view (preview_url — the rectangular
  // screenshot) with a dark gradient to the side. The square spawn icon
  // (thumbnail_url) is never used here — the banner is not an icon slot.
  const biomeBg = String(
    (world.biome ? ((biomes[world.biome.name] as any)?.preview_url || "") : "") ||
    (biomes["NORMAL"] as any)?.preview_url || ""
  );
  // Banner art must go through the Python media cache: the Fandom CDN 403s
  // direct CSS/img requests without a Referer, which is why e.g. the Snowy
  // banner silently failed while other biomes looked fine.
  const [bannerSrc, setBannerSrc] = useState("");
  useEffect(() => {
    setBannerSrc("");
    if (!biomeBg) return;
    let alive = true;
    (window as any).pywebview?.api?.ensure_media_cached?.(biomeBg).then((res: any) => {
      if (!alive) return;
      if (res && res.success && res.local_url) setBannerSrc(String(res.local_url));
    }).catch(() => {});
    return () => { alive = false; };
  }, [biomeBg]);
  const phaseColor = world.phase === "day" ? "#fbbf24" : "#818cf8";
  // Rare-biome ambience: page-wide effects while the biome lasts. Only the
  // five biomes the wiki groups as "Rare" get one (Glitched, Dreamspace,
  // Cyberspace, Singularity, The Radiant Forest) — each looks the way its
  // own wiki entry describes.
  const biomeKey = world.biome ? biomeMatchName(world.biome.name) : "";
  const fxClass = ({
    DREAMSPACE: "sim-fx-dream",
    CYBERSPACE: "sim-fx-cyber",
    SINGULARITY: "sim-fx-sing",
  } as Record<string, string>)[biomeKey] || "";
  // Glitched and The Radiant Forest are drawn on a canvas instead of using a
  // CSS overlay - they need real positions and smooth fades.
  const isGlitched = biomeKey === "GLITCHED";
  const isRadiant = biomeKey === "THE RADIANT FOREST";
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
            {/* Biome view background (Fandom in-game screenshot) + a dark
                gradient that fades out to the right, so the text stays
                readable while the biome art stays visible. */}
            {biomeBg && (
              <div style={{
                position: "absolute", inset: 0,
                backgroundImage: `url("${bannerSrc || biomeBg}")`,
                backgroundSize: "cover", backgroundPosition: "center 40%",
              }} />
            )}
            <div style={{
              position: "absolute", inset: 0,
              background: "linear-gradient(90deg, rgba(10,9,18,0.92) 0%, rgba(10,9,18,0.78) 38%, rgba(10,9,18,0.35) 72%, rgba(10,9,18,0.05) 100%)",
            }} />
            <div style={{ position: "relative", display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
              <div>
                <div style={{ fontSize: 11, letterSpacing: ".16em", textTransform: "uppercase", color: phaseColor, fontWeight: 600 }}>
                  <span>{world.phase === "day" ? "☀ Daytime" : "🌙 Nighttime"}</span> · <span style={{ color: "var(--text-secondary)", fontWeight: 400 }}>sandbox clock</span>
                </div>
                <div style={{ fontSize: 20, fontWeight: 700, color: worldColor, textShadow: "0 1px 10px rgba(0,0,0,0.7)" }}>
                  {world.biome
                    ? (<>☁ {world.biome.name === "GLITCHED" ? <GlitchLabel text="GLITCHED" /> : world.biome.name}</>)
                    : "NORMAL"}
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
                <div style={{ fontSize: 10.5, letterSpacing: ".16em", textTransform: "uppercase", color: "var(--text-secondary)" }}>Roll luck (next roll)</div>
                <div style={{ fontSize: 27, fontWeight: 700, color: worldColor, lineHeight: 1.2 }}>×{rollLuckNow.toFixed(2)}</div>
                <div style={{ fontSize: 10.5, color: "var(--text-secondary)" }}>
                  <span>base</span> ×1{sandbox ? <> · <span>cheat</span> ×{fmtNum(settings.luck)}</> : null} · <span>gauntlets</span> ×{gauntletLuck.toFixed(2)}{potPreview.special > 0 ? <> · <span>special</span> +{fmtNum(potPreview.special)}</> : null} · <span>VIP</span> ×{vipMult.toFixed(2)}{equippedFx.randomPct > 0 ? <> · <span>random fx</span> ×{(1 + randFx / 100).toFixed(2)}</> : null}
                </div>
                {(fxHud.spikeMult > 1 || fxHud.spikeLabel || fxHud.bonusIn !== null || potPreview.used.length > 0 || potPreview.suppressed.length > 0) && (
                  <div style={{ fontSize: 10.5, marginTop: 3, color: worldColor }}>
                    {(potPreview.used.length > 0 || potPreview.suppressed.length > 0) && (
                      <div>🧪 {potPreview.used.join(" + ")}{potPreview.suppressed.length ? ` · ${potPreview.suppressed.length} effect${potPreview.suppressed.length > 1 ? "s" : ""} suppressed` : ""} · special +{fmtNum(potPreview.special)}</div>
                    )}
                    {fxHud.spikeMult > 1 && <div>⚡ {fxHud.spikeLabel || `spike ×${fxHud.spikeMult}`} — {fxHud.spikeLeft} roll{fxHud.spikeLeft === 1 ? "" : "s"} left</div>}
                    {fxHud.bonusIn !== null && (
                      <div>🎁 bonus roll ×{Math.max(1, (equippedFx.bonusMult ?? 2) * equippedFx.bonusMultFactor)} in {fxHud.bonusIn} roll{fxHud.bonusIn === 1 ? "" : "s"}{fxHud.spikeMult > 1 ? "" : ` · luck will be ×${(rollLuckNow * Math.max(1, (equippedFx.bonusMult ?? 2) * equippedFx.bonusMultFactor)).toFixed(2)} there`}</div>
                    )}
                  </div>
                )}
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
                    <span>Luck (cheat, ×1 – ×100M)</span>
                    <span>final ×{rollLuckNow.toFixed(2)}</span>
                  </div>
                  <input className="form-input" type="number" min={1} max={100000000} step={1}
                    value={settings.luck}
                    onChange={e => {
                      const v = Math.min(100000000, Math.max(1, Math.floor(Number(e.target.value) || 1)));
                      setSettings(s => ({ ...s, luck: v }));
                      persist();
                    }}
                    style={{ width: "100%", borderRadius: 4 }} />
                </div>
              ) : (
                <div style={{ width: "100%", fontSize: 11.5, color: "var(--text-secondary)" }}>
                  <span>Luck</span> ×{rollLuckNow.toFixed(2)} — <span>gauntlets and VIP stack in Honest mode too. Enable Sandbox for the luck input and roll-speed cheats.</span>
                </div>
              )}
              <div style={{ fontSize: 11, color: "var(--text-secondary)", textAlign: "center", lineHeight: 1.5 }}>
                <span>Effective roll speed</span> ×{effSpeed.toFixed(2)} · <span>pool</span> {fmtNum(pool.length)} <span>auras</span>{world.biome ? " (biome-modified)" : ""}
                <br />
                Odds like the game (Fandom Luck Formula): Luck = (((1 + Basic) × Bonus) + Special) × VIP, each aura's List Value is floor(N ÷ luck) and a random 1..List Value must hit 1, rarest first; fixed-chance auras roll at their raw 1 in N before everything else.
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
                      {Array.isArray(d.fx) && d.fx.length > 0 && (
                        <span style={{ flex: "0 0 auto", fontSize: 10, color: worldColor, cursor: "help" }} title={d.fx.join(" · ")}>
                          {d.fx.map(t => t.split(" ")[0]).join(" ")}
                        </span>
                      )}
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
                <h4 style={{ margin: 0, fontSize: 12, letterSpacing: ".12em", textTransform: "uppercase", color: "#a78bfa" }}>📈 Luck history</h4>
                <span style={{ fontSize: 10.5, color: "var(--text-secondary)" }}>
                  {luckHistory.length ? `last ${luckHistory.length} rolls` : "no rolls yet"}
                </span>
              </div>
              {luckHistory.length > 0 ? (
                <>
                  <div style={{ display: "flex", alignItems: "flex-end", gap: 1, height: 74, padding: "6px 0 0", borderBottom: "1px solid rgba(255,255,255,.08)" }}>
                    {luckHistory.map((h, i) => {
                      const maxLuck = Math.max(...luckHistory.map(x => x.luck), 1);
                      const hgt = Math.max(6, Math.round((h.luck / maxLuck) * 100));
                      const color = h.bonus ? "#fbbf24" : h.spike > 1 ? "#a78bfa" : "#38bdf8";
                      return (
                        <div
                          key={`${h.roll}-${i}`}
                          title={`Roll #${h.roll} · luck ×${h.luck.toFixed(2)}${h.bonus ? " · bonus roll" : ""}${h.spike > 1 ? ` · spike ×${h.spike}` : ""}`}
                          style={{
                            flex: "1 1 0", minWidth: 2, height: `${hgt}%`,
                            background: color, opacity: h.bonus || h.spike > 1 ? 1 : 0.55,
                            borderRadius: "1px 1px 0 0", boxShadow: h.bonus ? `0 0 6px ${color}` : "none",
                          }}
                        />
                      );
                    })}
                  </div>
                  <div style={{ display: "flex", gap: 12, marginTop: 8, fontSize: 10.5, color: "var(--text-secondary)", flexWrap: "wrap" }}>
                    <span><i style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#38bdf8", marginRight: 4 }} />normal roll</span>
                    <span><i style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#fbbf24", marginRight: 4 }} />bonus roll</span>
                    <span><i style={{ display: "inline-block", width: 8, height: 8, borderRadius: 2, background: "#a78bfa", marginRight: 4 }} />luck spike</span>
                    <span style={{ marginLeft: "auto" }}>peak ×{Math.max(...luckHistory.map(x => x.luck)).toFixed(2)}</span>
                  </div>
                </>
              ) : (
                <div className="form-hint">The effective luck of every roll appears here — bonus rolls and luck spikes are highlighted.</div>
              )}
            </div>

            <div className="card" style={{ padding: 18 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                <h4 style={{ margin: 0, fontSize: 12, letterSpacing: ".12em", textTransform: "uppercase", color: "#a78bfa" }}>📊 Statistics</h4>
                <button className="btn" style={{ padding: "3px 10px", fontSize: 12 }} onClick={() => setConfirmReset(true)} title="Clear rolls, unique auras, biome visits and the drop log">🗑 Reset</button>
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8, fontSize: 12.5 }}>
                <div><div style={{ color: "var(--text-secondary)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".08em" }}>Rolls</div><b>{fmtNum(statsView.rolls)}</b></div>
                <div><div style={{ color: "var(--text-secondary)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".08em" }}>Unique auras</div><b>{fmtNum(statsView.unique_auras.length)}</b></div>
                <div><div style={{ color: "var(--text-secondary)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".08em" }}>Playtime</div><b>{fmtTime(statsView.playtime_s)}</b></div>
                <div><div style={{ color: "var(--text-secondary)", fontSize: 10.5, textTransform: "uppercase", letterSpacing: ".08em" }}>Rarest</div>
                  <b style={{ fontSize: 11.5 }}>{statsView.rarest ? `${statsView.rarest.name} (1 in ${fmtNum(statsView.rarest.rarity)})` : "—"}</b></div>
              </div>
              <div style={{ marginTop: 10, fontSize: 11.5, color: "var(--text-secondary)" }}>
                <div style={{ maxHeight: 160, overflow: "auto" }}>
                  {Object.entries(statsView.biome_visits).sort((a, b) => b[1] - a[1]).map(([n, c]) => (
                    <div key={n}>☁ {n}: {fmtNum(c)} <span>visits</span></div>
                  ))}
                </div>
                {!Object.keys(statsView.biome_visits).length && <div>No biome visits yet.</div>}
              </div>
              <div style={{ marginTop: 12 }}>
                <div style={{ fontSize: 10.5, letterSpacing: ".08em", textTransform: "uppercase", color: "var(--text-secondary)", marginBottom: 4 }}>
                  📜 Biome log{statsView.biome_log.length ? ` (last ${Math.min(50, statsView.biome_log.length)})` : ""}
                </div>
                <div style={{ maxHeight: 150, overflow: "auto", fontSize: 11, lineHeight: 1.7, color: "var(--text-secondary)" }}>
                  {statsView.biome_log.length ? statsView.biome_log.slice(-50).reverse().map((b, i) => (
                    <div key={`${b.ts}-${i}`}>
                      ☁ <span style={{ color: "#e2e8f0" }}>{b.name}</span>
                      {" · "}{new Date(b.ts).toLocaleTimeString()}{b.forced ? " · forced" : ""}
                    </div>
                  )) : <div>No biome activity yet.</div>}
                </div>
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
                      <span style={{ marginLeft: "auto", opacity: .75, flex: "0 0 auto" }}>×{fmtNum(row.count)}{row.N ? ` · 1 in ${fmtNum(row.N)}` : ""}{!row.inPool && row.N ? " (base odds)" : ""}</span>
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
                Sandbox mode (speed ×2/×3/×5, luck input, forced biomes)
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, marginBottom: 6 }} title="VIP gamepass — x1.2 final luck (also multiplies bonus rolls / special buffs)">
                <input type="checkbox" checked={settings.vip}
                  onChange={e => { setSettings(s => ({ ...s, vip: e.target.checked })); persist(); }} />
                VIP — ×1.2 final luck
              </label>
              <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12.5, marginBottom: 10 }} title="VIP+ gamepass — x1.2 final luck, x1.3 when VIP is also owned (Fandom: Effects)">
                <input type="checkbox" checked={settings.vip_plus}
                  onChange={e => { setSettings(s => ({ ...s, vip_plus: e.target.checked })); persist(); }} />
                VIP+ — ×1.2 final luck (×1.3 with VIP)
              </label>
              {sandbox && (
                <div style={{ margin: "10px 0", padding: "10px 12px", borderRadius: 8, border: "1px solid rgba(167,139,250,.35)", background: "rgba(167,139,250,.06)" }}>
                  <div style={{ fontSize: 11, letterSpacing: ".12em", textTransform: "uppercase", color: "#a78bfa", marginBottom: 8 }}>
                    🧪 One-roll potions
                  </div>
                  {POTIONS.map(def => {
                    const count = potions[def.key] || 0;
                    return (
                      <div key={def.key} style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 12, marginBottom: 6 }}>
                        <span style={{ flex: 1, minWidth: 0 }}>
                          <b>{def.name}</b>{" "}
                          <span style={{ color: "var(--text-secondary)" }}>
                            +{fmtNum(def.specialLuck)} luck
                            {def.gated ? ` · ${def.gated.map(g => `${g.name} 1/${fmtNum(g.N)}`).join(", ")} (fixed)` : ""}
                            {def.wipesOthers ? " · wipes other buffs" : ""}
                          </span>
                        </span>
                        <button className="btn" style={{ padding: "1px 8px", fontSize: 12 }} onClick={() => applyPotion(def.key, -1)} disabled={count <= 0}>−</button>
                        <span style={{ width: 22, textAlign: "center" }}>{count}</span>
                        <button className="btn" style={{ padding: "1px 8px", fontSize: 12 }} onClick={() => applyPotion(def.key, 1)}>+</button>
                      </div>
                    );
                  })}
                  <div style={{ fontSize: 10.5, color: "var(--text-secondary)", marginTop: 6, lineHeight: 1.6 }}>
                    Each count = one roll of the effect (stacking extends the duration, never the boost). Oblivion cannot be used with a Heavenly Potion and suppresses other effects while it lasts; Pump King's Blood suppresses everything, including Oblivion. Potion-gated drops roll at fixed odds — luck does not touch them.
                  </div>
                </div>
              )}
              <label style={{ display: "block", fontSize: 12.5, marginBottom: 8 }}>
                <span style={{ color: "var(--text-secondary)" }}>Alert when aura rarity ≥ (min 99,000,000)</span>
                <input className="form-input" style={{ width: "100%", borderRadius: 4, marginTop: 3 }} type="number" min={99000000}
                  value={settings.notify_aura_min_rarity}
                  onChange={e => { setSettings(s => ({ ...s, notify_aura_min_rarity: Math.max(99000000, Number(e.target.value) || 99000000) })); persist(); }} />
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
      {launched && isGlitched && <GlitchSquares />}
      {launched && isRadiant && (
        <>
          <div className="sim-fx sim-fx-radiant" />
          <RadiantForest />
        </>
      )}
      {launched && !isGlitched && !isRadiant && fxClass && <div className={`sim-fx ${fxClass}`} />}

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

      {/* Reset confirmation: wiping a long honest run must be deliberate */}
      {confirmReset && (
        <div style={{ position: "fixed", inset: 0, zIndex: 9600, background: "rgba(0,0,0,.55)", display: "flex", alignItems: "center", justifyContent: "center" }} onClick={() => setConfirmReset(false)}>
          <div className="card" style={{ width: 370, padding: 18, background: "#12101c", border: "1px solid #7f1d1d" }} onClick={e => e.stopPropagation()}>
            <h4 style={{ margin: "0 0 8px", fontSize: 14, color: "#f87171" }}>🗑 Reset the simulator statistics?</h4>
            <div style={{ fontSize: 12.5, color: "var(--text-secondary)", lineHeight: 1.7 }}>
              This wipes everything earned in Sol's Sim:
              <div style={{ margin: "8px 0", padding: "8px 10px", borderRadius: 6, background: "rgba(248,113,113,.08)", border: "1px solid rgba(248,113,113,.25)" }}>
                • <b>{fmtNum(statsView.rolls)}</b> rolls and <b>{fmtNum(statsView.unique_auras.length)}</b> unique auras<br />
                • biome visits and the rarest drop ({statsView.rarest ? `${statsView.rarest.name} (1 in ${fmtNum(statsView.rarest.rarity)})` : "none yet"})<br />
                • the drop log
              </div>
              Settings, VIP flags and equipped gauntlets are <b>not</b> touched. There is no undo.
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 14 }}>
              <button className="btn" style={{ flex: 1, background: "#7f1d1d", borderColor: "#991b1b" }} onClick={() => { resetStats(); setConfirmReset(false); }}>Yes, wipe it</button>
              <button className="btn" style={{ flex: 1 }} onClick={() => setConfirmReset(false)}>Keep my data</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
