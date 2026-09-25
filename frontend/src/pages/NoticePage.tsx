import { useT } from "../i18n";

export default function NoticePage() {
  const t = useT();
  return <>
    <div className="page-header"><h2>{t("Notice")}</h2><p>{t("Current EndSol Macro changes")}</p></div>
    <div className="card"><div className="card-header"><div className="card-icon">📖</div><div><h3>v1.0.7 — Memory Match, Sol's Book (Items & Gauntlets), Optimization & UI Polish</h3><p>Fixed Memory Match tile matching; added Items & Gauntlets tabs to Sol's Book; FPS optimization; UI styling</p></div></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>Memory Match:</b> fixed tile matching and tolerance thresholds so matching items are correctly paired and not prematurely discarded.</li>
        <li><b>Donation link:</b> fixed Boosty URL to end in /donate.</li>
        <li><b>Sol's Book media saving:</b> fixed saving cutscene videos (the save button passed a local cache path instead of the wiki URL) and added a 💾 Save button to theme music players — music and media can be downloaded again.</li>
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
