import { useT } from "../i18n";

export default function NoticePage() {
  const t = useT();
  return <>
    <div className="page-header">
      <h2>{t("Notice")}</h2>
      <p>
        {t("Current EndSol Macro changes")} ·{" "}
        <a href="https://github.com/MiraxKito/EndSol-Macro" target="_blank" rel="noreferrer" style={{ color: "var(--accent)" }}>
          GitHub Repo
        </a>
      </p>
    </div>
    <div className="card"><div className="card-header"><div><h3>v1.1.2 — Calibrations that follow your screen, a calmer music player, more remote controls</h3><p>The macro adapts to your resolution and window size, the music behaves, and Dry mode really keeps its hands off the game</p></div></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Calibrations follow your screen:</b> the points you calibrate now stay where they belong when you change the resolution, the window size or the Windows scaling. A calibration file or preset from someone else is fitted to your own screen when you import it.</li>
        <li><b>Remote Control gets new commands:</b> <code>/toggle</code> switches a feature on or off (fishing, Dry mode, potion crafting, …), <code>/logs</code> sends the last lines of the macro log, <code>/biome</code> shows the current biome and the last aura, <code>/stats</code> shows today's totals and <code>/restart_macro</code> restarts the macro without closing Roblox.</li>
        <li><b>Aura preview in the webhook page:</b> type an aura name in Discord Webhook Customization and see exactly how the announcement will look in Discord before it ever fires.</li>
        <li><b>Sol's Sim — two more one-roll potions:</b> Popping Potion and Godlike Potion are in the sandbox with their real luck values.</li>
      </ul></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>The music player keeps its place:</b> pausing and resuming continues where it stopped, switching tracks works, and the book's music no longer plays on top of the panel player.</li>
        <li><b>Dry mode is now really dry:</b> with Dry mode on the macro does not click or press anything in the game — the merchant, fishing, crafting, quests and Memory Match stay untouched.</li>
        <li><b>Potion crafting switches potions for real:</b> in Simple mode the macro now crafts the potions one after another, and in Partial mode the recorded recipe is actually played back instead of falling back to the simple routine.</li>
        <li><b>Your panel theme survives a restart:</b> "My Palette" is saved properly and is picked up when the panel starts again; editing the palette switches to it right away.</li>
        <li><b>A disconnect that does not heal itself:</b> when the game cannot get back into the server on its own (the client ends up on error 277 or 279), the macro notices it and reconnects for you instead of waiting forever.</li>
        <li><b>The Player Logger was removed:</b> it relied on log lines the game no longer writes, so it could not work. The button is gone instead of sitting there broken.</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div><h3>v1.1.1-fix — Full wiki text, own biome icons, music player</h3><p>Sol's Book stops cutting the wiki short, the rare biomes look like themselves, and the panel gets a music player</p></div></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Music player:</b> a built-in player with starred tracks, a playlist and repeat modes — it can play in the background after the panel starts. The button sits in the header next to the theme.</li>
        <li><b>Sol's Book — full entries:</b> the wiki's own <b>Appearance</b> and <b>Ability</b> text is shown next to the rarity, and the flavour quote opens the entry.</li>
        <li><b>Own biome icons:</b> the biome icons ship with the macro and come from this repository's CDN.</li>
      </ul></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>Sol's Book — nothing cut short:</b> biome descriptions run to the end, every aura shows its own picture (not an inventory screenshot or a cutscene), and auras behind a redirect now load properly.</li>
        <li><b>Sol's Book — no more hanging ⏱:</b> the page loads the list and the entries much faster.</li>
        <li><b>Sol's Sim — rare biomes:</b> Glitched tears the screen apart, Singularity became a real black hole, and The Radiant Forest can now replace Lost Forest (1 in 20).</li>
        <li><b>Update prompt:</b> a fix release under a new tag reaches everyone who already has the macro.</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div><h3>v1.1.1 — The Forest Update & Sol's Sim Upgrade</h3><p>One-roll potions, the real luck formula, connection-aware reconnects, and a wave of fixes</p></div></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Sol's Sim — one-roll potions:</b> Heavenly, Oblivion, Potion of Bound, Potion of the Dune, Red Moon Potion I/II and Pump King's Blood, with their real effects and the auras only they unlock (Neferkhaf, Fragments of the Crimson Moon, Oblivion, Memory).</li>
        <li><b>Sol's Sim — biome log:</b> the statistics panel keeps a history of which biomes appeared and when.</li>
        <li><b>Sol's Book player:</b> the track title is always visible and the music can be put on repeat.</li>
        <li><b>New game content (Radiant Forest update):</b> Lost Forest and The Radiant Forest are known everywhere — Stats, Webhook, Auto-Pop Buffs and Sol's Sim — with the game's own Weather / Biomes / Rare grouping.</li>
        <li><b>Calibration sharing:</b> a GitHub Discussions template for sharing calibration presets.</li>
      </ul></div>
      <div className="changelog-item"><h4>✨ Improvements</h4><ul>
        <li><b>Sol's Sim rolls follow the exact in-game luck formula</b> from the wiki, fixed-chance auras and potion luck included. The luck panel shows a full breakdown (base, cheat, gauntlets, potions, VIP) and the drop log tags bonus rolls and luck spikes.</li>
        <li><b>Sol's Book:</b> aura entries no longer repeat the same rarity numbers and read naturally; biome previews are wide cinematic strips that unfold while you hold the mouse on them; theme music is available for every biome, Pumpkin Moon and Graveyard included.</li>
        <li><b>Panel themes work again:</b> built-in presets are no longer overridden by the custom palette, which is now its own <b>My Palette</b> theme in the picker.</li>
        <li><b>Connection-aware reconnects:</b> after a disconnect the macro waits 2 minutes for the game's own auto-rejoin, then reconnects only with a verified internet connection; with no internet it switches off and restores itself (macro + game) once the line is stable.</li>
        <li><b>Credits and license updated</b> — including the rule that even partial reuse of the macro requires the author's consent.</li>
      </ul></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>Sol's Sim settings</b> no longer revert to old values on the next launch.</li>
        <li><b>VIP+VIP+</b> gives ×1.3 together (it used to stack to ×1.56), and event auras that need an admin effect (Megaphone, Astral : Astrald) no longer drop in the sim.</li>
        <li><b>Sim odds:</b> biome bonuses and biome-exclusive chances are correct now (some were far too generous); locked auras show their base odds in the statistics; fixed-chance auras ignore luck like in the real game; resetting the stats asks for confirmation first.</li>
        <li><b>Settings loss on startup</b> fixed for setups without a webhook or username; fishing counters only count real catches; potion-crafting slot files persist again.</li>
        <li><b>Background stability:</b> a quick Stop→Start no longer duplicates background loops (Anti-AFK could fire several times), and Memory Match / Quest Board wait for other actions instead of clashing with them.</li>
        <li><b>Remote Control</b> denies every bot command until the owner's Discord ID is configured, and the local API is hardened against outside access.</li>
        <li><b>Images load reliably:</b> sim banners and Sol's Book media go through the local cache — no more missing pictures.</li>
        <li><b>Aura webhook thresholds</b> are respected by more aura types; only biome-exclusive, crafted and potion auras always notify.</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div><h3>v1.1.0 — Sol's Sim & Sol's Book media</h3><p>New sandbox minigame and a nicer media experience in the built-in wiki</p></div></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Sol's Sim</b> — a sandbox of Sol's RNG inside the panel: roll auras, build a collection and track your stats.</li>
        <li><b>Sol's Book media</b> — media galleries with captions and fullscreen view, ←/→ navigation, and a music player with volume and track length.</li>
      </ul></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>Sol's Book:</b> biome previews now show the actual biome picture instead of an icon.</li>
        <li><b>Memory Match</b> is now labeled <b>Experimental</b> — it works end-to-end but can still miss a pair.</li>
        <li><b>Daily Rewards:</b> "Collect Daily Event Check-in" renamed to <b>Daily Check-In</b>.</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div><h3>v1.0.9 — Achievements, new Potion Crafting, Multi-Instances QoL</h3><p>Sol's Book Achievements, Potion Crafting rebuilt for the new UI, MI close buttons, lag fixes</p></div></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Sol's Book — Achievements:</b> a new section with every in-game achievement — icon, description, how to obtain it and the reward — searchable and filtered by category, auto-updated from the wiki.</li>
        <li><b>Potion Crafting rebuilt for the new crafting UI:</b> <b>Simple mode</b> drives the Auto button safely (the current state is detected and switched with verification) and clicks Add Everything + Craft; <b>Full / Partial occupancy</b> — in Partial mode the macro walks to the crafting station on a schedule (a walk path is bundled), crafts for the set duration, then resets back to spawn.</li>
        <li><b>Multiple-Instances:</b> a <b>Close</b> button on every running window in the process list (graceful close, force-kill fallback; the main window is protected while the macro runs), and the mode can now be turned off while a single client is still running.</li>
        <li><b>Required Roblox username:</b> the macro refuses to start without a valid username (format + online check on the Webhook page) — log reading, stats and multi-instance resolution depend on it.</li>
      </ul></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>Memory Match:</b> white/gray (desaturated) items are now read from their silhouettes, and a pair the game scores between two captures is no longer miscounted.</li>
        <li><b>Lag fixes:</b> the main Roblox log is scanned incrementally with bounded reads — no more read bursts and Defender spikes while the panel runs.</li>
        <li><b>Sol's Book media:</b> thumbnails whose file names contain underscores/encoded characters now resolve correctly (some images previously failed to load).</li>
        <li><b>Daily stats webhook:</b> the summary now names the configured player and states that stats cover the main window only.</li>
      </ul></div>
      <div className="changelog-item"><h4>✨ Other</h4><ul>
        <li>Windows toast notifications were removed; all feedback lives in the panel log.</li>
        <li>Rare-biome webhook texts refreshed (Glitched, Dreamspace, Singularity and others).</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div><h3>v1.0.8 — Multiple-Instances: Main Window & Secondary Windows</h3><p>Play on several Roblox windows at once, cleaner settings, a new Status page and start/stop sounds</p></div></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Multiple windows:</b> pick your main Roblox window — the macro plays fully on it (fishing, quests, Memory Match, merchant), while your other windows stay logged in and send biome, aura and disconnect alerts to Discord.</li>
        <li><b>Smart Anti-AFK for other windows:</b> they only jump when the main window isn't busy, your current window gets its focus back right after, and jumps got more reliable on slower PCs.</li>
        <li><b>Start/stop sounds:</b> two short pleasant sounds tell you when the macro starts and stops — even if Roblox is in fullscreen.</li>
        <li><b>Self-fixing Roblox window:</b> if Roblox got minimized, shrunk or restarted in a small window, the macro fixes it automatically so no clicks are missed.</li>
        <li><b>Separate Discord webhook for multi-windows (optional):</b> get a message when multi-window mode starts or stops and how many windows it's watching.</li>
      </ul></div>
      <div className="changelog-item"><h4>✨ Improvements</h4><ul>
        <li><b>Cleaner settings:</b> options for disabled features are now hidden until you turn the feature on.</li>
        <li><b>New Status page:</b> see at a glance what's running, your session time and the main window.</li>
        <li><b>Less interruptions:</b> auras you filtered out no longer steal focus or take screenshots, and aura info from the wiki got more accurate.</li>
        <li><b>Auto-start after inactivity:</b> more reliable — if the macro stops on its own while you're away, it starts again.</li>
        <li><b>Reliability:</b> reconnects no longer close your other Roblox windows, and background tasks recover from errors on their own.</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div><h3>v1.0.7 — Memory Match, Sol's Book (Items & Gauntlets), Optimization & UI Polish</h3><p>Fixed Memory Match tile matching; added Items & Gauntlets tabs to Sol's Book; FPS optimization; UI styling</p></div></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>Memory Match:</b> fixed tile matching and tolerance thresholds so matching items are correctly paired and not prematurely discarded.</li>
        <li><b>Donation link:</b> fixed Boosty URL to end in /donate.</li>
        <li><b>Sol's Book media saving:</b> fixed saving cutscene videos (the save button passed a local cache path instead of the wiki URL) and added a Save button to theme music players — music and media can be downloaded again.</li>
        <li><b>Auto-Start after inactivity:</b> the idle timeout was silently clamped to a 5-minute minimum, so shorter values (e.g. 2 minutes) never triggered. The configured timeout is now honored (1–1440 minutes).</li>
        <li><b>Sol's Book performance:</b> removed mini GIF icons from all selection lists (Items, Gauntlets, Auras, Biomes) — lists now render instantly as text with rarity color dots; previews remain only in the detail pane and Media tab as static thumbnails.</li>
      </ul></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Sol's Book:</b> added dedicated Items and Gauntlets databases with full descriptions, obtainment methods, and uses directly from Fandom Wiki.</li>
      </ul></div>
      <div className="changelog-item"><h4>✨ Improvements</h4><ul>
        <li><b>Performance:</b> optimized process check intervals and caching to prevent FPS drops on low-end systems.</li>
        <li><b>UI Polish:</b> unified border-radius styling across panel components to fit the overall aesthetic.</li>
        <li><b>Discord Webhooks:</b> updated version metadata and footers across all webhook notifications.</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div><h3>v1.0.6 — Memory Match, Sol's Book & new extras</h3><p>Memory Match reads quantities reliably; The Limbo added to Sol's Book; new optional automations and tools</p></div></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>Memory Match:</b> no longer gets stuck flipping the same two tiles when items look identical but have different quantities. Quantities are detected with a new image-processing pipeline (binarized text, upscaled reads) and compared pixel-wise, so unreadable text can no longer create false pairs.</li>
        <li><b>Custom paths:</b> custom Eden Path recordings are now used during Eden pathing (previously only the bundled route played).</li>
        <li><b>Sol's Book:</b> the Crafting badge no longer shows on potion-only auras — they now get their own Potion badge; media captions are more informative.</li>
      </ul></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Sol's Book:</b> The Limbo dimension in the Biomes chapter with its exclusive auras and a captioned image gallery.</li>
        <li><b>Feature Schedule</b> on the Status page: what every automation will do next and when.</li>
        <li><b>Config Profiles:</b> save and switch complete setting sets with one click.</li>
        <li><b>Optional toggles (off by default):</b> Dry-run mode (log actions without performing them), key-release failsafe after reconnect, daily stats webhook, Windows notifications on Legendary+ auras.</li>
        <li><b>Clear Logs</b> button in System Settings.</li>
      </ul></div>
      <div className="changelog-item"><h4>✨ Other</h4><ul>
        <li>The media cache is limited to 300 MB and cleaned up automatically at every startup.</li>
        <li>The macro now uses its own GitHub repository for updates and data files.</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div><h3>v1.0.5 — Soft-disconnect reconnect, Memory Match & Quest Board fixes, localization</h3><p>Reconnects on silent internet drops; smarter Memory Match matching; Quest Board accepts damaged OCR names; EN/RU panel language</p></div></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Panel localization (EN / RU)</b> with a language switcher in Other Features → System Settings.</li>
        <li><b>Reconnect on silent internet drops</b> and a Remote Access help panel with bot setup steps.</li>
        <li><b>Sol's Book rarity colors:</b> aura entries are colored by rarity type instead of a single yellow; stats reset now asks for confirmation.</li>
      </ul></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>Quest Board</b> no longer skips Breakthrough quests when OCR heavily damages the quest name.</li>
        <li><b>Memory Match</b> matching made reliable on semi-transparent tiles: background-normalized signatures, smarter candidate choice, and multi-attempt quantity OCR.</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div><h3>Supported features</h3><p>EndSol Macro functionality outside Multiple-Instances mode</p></div></div>
      <div className="changelog-item"><ul><li>Biome and aura detection</li><li>Discord webhook notifications</li><li>Fishing automation and potion crafting</li><li>Auto-pop buff system per biome</li><li>Resolution/DPI-aware calibration</li><li>Remote control and screen capture</li></ul></div>
    </div>
  </>;
}
