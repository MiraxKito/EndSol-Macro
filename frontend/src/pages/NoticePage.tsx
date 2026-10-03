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
    <div className="card"><div className="card-header"><div className="card-icon">🏆</div><div><h3>v1.0.9 — Achievements, new Potion Crafting, Multi-Instances QoL</h3><p>Sol's Book Achievements, Potion Crafting rebuilt for the new UI, MI close buttons, lag fixes</p></div></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Sol's Book — Achievements 🏆:</b> a new section with every in-game achievement — icon, description, how to obtain it and the reward — searchable and filtered by category, auto-updated from the wiki.</li>
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
    <div className="card"><div className="card-header"><div className="card-icon">🖥️</div><div><h3>v1.0.8 — Multiple-Instances: Main Window & Secondary Windows</h3><p>Play on several Roblox windows at once, cleaner settings, a new Status page and start/stop sounds</p></div></div>
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
    <div className="card"><div className="card-header"><div className="card-icon">📖</div><div><h3>v1.0.7 — Memory Match, Sol's Book (Items & Gauntlets), Optimization & UI Polish</h3><p>Fixed Memory Match tile matching; added Items & Gauntlets tabs to Sol's Book; FPS optimization; UI styling</p></div></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>Memory Match:</b> fixed tile matching and tolerance thresholds so matching items are correctly paired and not prematurely discarded.</li>
        <li><b>Donation link:</b> fixed Boosty URL to end in /donate.</li>
        <li><b>Sol's Book media saving:</b> fixed saving cutscene videos (the save button passed a local cache path instead of the wiki URL) and added a 💾 Save button to theme music players — music and media can be downloaded again.</li>
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
    <div className="card"><div className="card-header"><div className="card-icon">📖</div><div><h3>v1.0.6 — Memory Match, Sol's Book & new extras</h3><p>Memory Match reads quantities reliably; The Limbo added to Sol's Book; new optional automations and tools</p></div></div>
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
    <div className="card"><div className="card-header"><div className="card-icon">📖</div><div><h3>v1.0.5 — Soft-disconnect reconnect, Memory Match & Quest Board fixes, localization</h3><p>Reconnects on silent internet drops; smarter Memory Match matching; Quest Board accepts damaged OCR names; EN/RU panel language</p></div></div>
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
    <div className="card"><div className="card-header"><div className="card-icon">📋</div><div><h3>Supported features</h3><p>EndSol Macro functionality outside Multiple-Instances mode</p></div></div>
      <div className="changelog-item"><ul><li>Biome and aura detection</li><li>Discord webhook notifications</li><li>Fishing automation and potion crafting</li><li>Auto-pop buff system per biome</li><li>Resolution/DPI-aware calibration</li><li>Remote control and screen capture</li></ul></div>
    </div>
  </>;
}
