import { useT } from "../i18n";

export default function NoticePage() {
  const t = useT();
  return <>
    <div className="page-header"><h2>{t("Notice")}</h2><p>{t("Current EndSol Macro changes")}</p></div>
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
    <div className="card"><div className="card-header"><div className="card-icon">📖</div><div><h3>v1.0.4 — Fandom data system, recorders, and calibration profiles</h3><p>Sol's Book now runs on live Fandom data; secondary windows and calibration save/export/import fixed</p></div></div>
      <div className="changelog-item"><h4>✅ New</h4><ul>
        <li><b>Sol's Book on live Fandom data:</b> biomes and auras (including limited, craftable, unobtainable, and dev-exclusive entries) are parsed directly from the wiki — spawn chances, durations, breakthrough multipliers, chat colors, native/exclusive aura links, and real wiki rarity classes. Offline fallback now uses a bundled Fandom snapshot instead of placeholder data.</li>
        <li><b>Custom Paths recorder:</b> a "Record new path" button opens the generic Recorder directly from the Custom Paths page.</li>
        <li><b>Quest Board quest-type preferences:</b> choose per quest type whether the macro accepts or dismisses it (hunts/meditation/breakthrough by default; fishing, player hunts, deliveries, tutorial quests are dismissed).</li>
        <li><b>Memory Match and Quest Board settings</b> exposed in Misc: check intervals, play-during-fishing, and playback speed multiplier.</li>
        <li><b>Daily Rewards manual test:</b> "Collect now (test)" and "Reset claimed date" buttons next to the Daily Rewards toggle.</li>
        <li><b>Instructions</b> sections for Custom Paths, Memory Match, Quest Board, Sol's Book, and Daily Rewards.</li>
      </ul></div>
      <div className="changelog-item"><h4>🛠️ Fixed</h4><ul>
        <li><b>Recorder and rare-biome popup windows rendered a black screen</b> in the packaged app — secondary windows now load through the same file URL as the main window, so assets resolve.</li>
        <li><b>Calibration Save / Load / Export / Import</b> crashed on start (missing helper and import). The full profile flow now works: save with resolution/scale/mode metadata, list with validity status, load with automatic backup, export/import JSON files with validation.</li>
        <li>Obby automation could not be enabled from the new UI (dead config keys); the toggle and interval now use the backend keys.</li>
        <li>Aura detail cards showed raw wiki markup; names, obtainment text, and descriptions are now clean, and rarity shows both the native and the global chance.</li>
        <li>Biome descriptions contained leftover image markup ("thumb…"); descriptions are now clean prose.</li>
        <li>Portable Crack default interval aligned (3 minutes) and the Eden contract interval no longer falls back to a different value.</li>
        <li>Auto-fullscreen re-verifies the Roblox window once a minute, so a manual exit from fullscreen is restored automatically.</li>
        <li>Default calibrations for 1920×1080 / 100% / Fullscreen replaced with a verified profile.</li>
        <li>Recorder windows now render correctly (assets resolve through the bundled page base).</li>
        <li>Aura obtainment for potion-crafted auras (e.g. Fragments of the Crimson Moon) now lists every potion source with its exact chance.</li>
        <li>Limbo-locked auras (Anima and friends) are marked "Exclusive to THE LIMBO" instead of "anywhere".</li>
        <li>Webhook ping policy: event auras are never pinged; Transcendent / Challenged / Challenged+ bypass the minimum-rarity threshold but are sent without a ping; other auras ping only at or above the configured minimum.</li>
        <li>Quest Board: tutorial and one-time NPC/location quests can no longer be automated (always dismissed); per-type preferences remain for automatable quests.</li>
        <li>Aura article details are cached per session, reducing repeat Fandom requests.</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div className="card-icon">🛠️</div><div><h3>v1.0.3 — Multiple-Instances redesign</h3><p>External window monitoring through Avaluate MultipleRobloxInstances</p></div></div>
      <div className="changelog-item"><h4>✅ Changed</h4><ul>
        <li>Removed the custom account-profile, launcher, persistence, PID ownership, and emergency-stop system.</li>
        <li>Multiple-Instances now expects the user to launch Roblox windows with Avaluate/MultipleRobloxInstances.</li>
        <li>EndSol only detects visible Roblox windows and processes them in deterministic order for one Anti-AFK action at a time.</li>
        <li>Statistics, biome/aura detection, mouse input, OCR, pathing, fishing, merchant, potion crafting, and other foreground automation are disabled while the mode is enabled.</li>
        <li>No built-in scheduler for the main instance - juggling several game windows reliably isn't possible on every PC, so EndSol keeps them active in order instead.</li>
      </ul></div>
      <div className="changelog-item"><h4>⚠️ Compatibility warning</h4><ul>
        <li>Avaluate's own documentation warns that Roblox may close additional windows randomly. EndSol does not bypass or work around that behavior.</li>
        <li>Supported workflow: start Avaluate first, load the first Roblox account fully, open additional accounts, then enable this mode in EndSol.</li>
        <li>If a window closes or cannot be focused, EndSol skips it and continues without touching account data.</li>
      </ul></div>
    </div>
    <div className="card"><div className="card-header"><div className="card-icon">📋</div><div><h3>Supported features</h3><p>EndSol Macro functionality outside Multiple-Instances mode</p></div></div>
      <div className="changelog-item"><ul><li>Biome and aura detection</li><li>Discord webhook notifications</li><li>Fishing automation and potion crafting</li><li>Auto-pop buff system per biome</li><li>Resolution/DPI-aware calibration</li><li>Remote control and screen capture</li></ul></div>
    </div>
  </>;
}
