import React from "react";

const Section = ({ icon, title, children }: { icon: string; title: string; children: React.ReactNode }) => (
  <section className="card" style={{ marginBottom: 14 }}>
    <div className="card-header">
      <div className="card-icon">{icon}</div>
      <div><h3>{title}</h3></div>
    </div>
    <div style={{ color: "var(--text-secondary)", fontSize: 13, lineHeight: 1.7 }}>{children}</div>
  </section>
);

const Tip = ({ children }: { children: React.ReactNode }) => (
  <div style={{ padding: "10px 12px", margin: "10px 0", borderLeft: "3px solid var(--accent)", background: "rgba(124,91,245,.10)" }}>{children}</div>
);

export default function InstructionsPage() {
  return (
    <div className="animate-fade-in">
      <div className="page-header">
        <h2>Instructions</h2>
        <p>A practical guide to EndSol Macro, its tabs, settings, and safe operating order</p>
      </div>

      <Tip><strong>Recommended first setup:</strong> open <b>Macro Calibrations</b>, verify the Roblox window and resolution, then configure only the features you intend to use. Start the macro only after Roblox is loaded and focused.</Tip>

      <Section icon="🚀" title="Getting started">
        <ol>
          <li>Launch Roblox and join Sol's RNG. Keep the Roblox client visible while configuring mouse-based features.</li>
          <li>Set your resolution, scale, and window mode in <b>Macro Calibrations</b>, or calibrate individual points with the overlay.</li>
          <li>Configure webhook, username, User ID, and private-server settings only if those features are enabled.</li>
          <li>Enable the desired feature toggles and press the main macro switch in the header.</li>
          <li>Use the log panel and <b>Status</b> page to confirm which worker is active. Avoid enabling conflicting foreground actions together.</li>
        </ol>
      </Section>

      <Section icon="🎣" title="Fishing">
        <p>Fishing opens the fishing UI, detects the indicator, performs the reel clicks, and optionally sells fish or runs merchant/BR-SC flows.</p>
        <ul><li><b>Fishing Mode:</b> the main switch; it pauses most competing mouse actions.</li><li><b>Auto selling:</b> configure the fish threshold and amount before enabling it.</li><li><b>Playback multiplier:</b> affects recorded fishing movement timing; keep it at 1.0 for the original route timing.</li><li><b>Failsafe rejoin:</b> requires Auto Reconnect and should be tested with a private server.</li></ul>
      </Section>

      <Section icon="🧪" title="Auto Pop Buff and potion order">
        <p>Auto Pop uses the enabled loadout for the exact detected biome. Each selected item is searched in the inventory, checked by OCR when available, used for its configured amount, and then the next item is processed.</p>
        <ul><li>Open a biome's <b>Buff Selection</b> and enable the required items.</li><li>Use the <b>↑</b> and <b>↓</b> controls to choose the exact first-to-last order. The order is saved separately for each biome.</li><li>Items that are enabled but not manually ordered are appended after the manual list, so they are not silently skipped.</li><li>Do not enable Auto Pop while another foreground inventory action is being performed; it waits for blocked workers to finish.</li></ul>
        <Tip>For effects with dependencies or special timing, place the prerequisite potion first and the final/long-duration item last. Test a small amount before using a large amount.</Tip>
      </Section>

      <Section icon="🏪" title="Merchant and automated actions">
        <p><b>Merchant</b> handles teleporter, OCR, exchange, and purchase actions. <b>Automated Actions</b> contains quests, reconnect, screenshots, biome randomizer, strange controller, and recovery options.</p>
        <p>Mouse actions require valid calibrations. Do not run multiple features that need foreground control at the same time.</p>
      </Section>

      <Section icon="🗺️" title="Movements and paths">
        <p><b>Movements</b> controls saved routes such as Obby, Eden, and egg collection. Paths replay their recorded timestamps and key events; they are not recalculated from a generic speed formula.</p>
        <ul><li>Use the correct VIP/Non-VIP path option for the account.</li><li>Keep Roblox focused and use the same camera alignment as when the route was recorded.</li><li>Do not edit path JSON timestamps unless you intentionally want different timing.</li></ul>
      </Section>

      <Section icon="🛤️" title="Custom Paths">
        <p><b>Custom Paths</b> lets you record your own walk routes and assign them to features (Obby, Eden, Memory Match, Quest Board, egg routes). A custom path always overrides the built-in default route for that feature.</p>
        <ol><li>Press <b>Record new path (open Recorder)</b> on the Custom Paths page and perform the route in Roblox.</li><li>Stop the recording in the Recorder window, then save it on this page with a name and an optional feature.</li><li>Assign a saved path to a feature with the dropdown, or remove the assignment with <b>Custom:</b> (empty) to fall back to the default route.</li></ol>
        <Tip>Record routes at the same resolution and window mode you play with — path coordinates are resolution-dependent.</Tip>
      </Section>

      <Section icon="🧠" title="Memory Match">
        <p>Memory Match opens the mini-game, detects the 5×4 card grid from the calibrated region, matches pairs by image similarity, and closes the game when the board disappears.</p>
        <ul><li>Calibrate the grid region, the Start button, and the Close button in <b>Macro Calibrations</b> before enabling.</li><li><b>Check interval</b> controls how often the loop attempts a game (default 60 minutes).</li><li><b>Play during fishing mode</b> allows the loop to run alongside fishing; the macro pauses foreground actions safely via the shared scheduler.</li><li><b>Playback speed multiplier</b> speeds up or slows down the click sequence (1.0 = original timing).</li></ul>
      </Section>

      <Section icon="📜" title="Quest Board">
        <p>Quest Board walks to the board (optional custom path), opens it with <b>E</b>, reads each quest name with OCR, then accepts, dismisses, or claims it depending on your settings.</p>
        <ul><li>Calibrate the OCR region, Accept / Claim / Dismiss buttons, the left and right arrows, and the Close button.</li><li><b>Quest types — take or dismiss:</b> choose per category which quests the macro accepts (hunts, Meditation I/II, Breakthroughs) and which it dismisses (fishing, player hunts, deliveries, tutorial tasks). Unknown quests are dismissed for safety.</li><li><b>Check interval</b> and <b>Play during fishing mode</b> behave like the Memory Match options.</li></ul>
      </Section>

      <Section icon="📖" title="Sol's Book">
        <p><b>Sol's Book</b> is the built-in encyclopedia of biomes and auras. Data comes directly from the Sol's RNG Fandom wiki: spawn chances, durations, breakthrough multipliers, chat colors, native and exclusive auras, rarities, and obtainment paths.</p>
        <ul><li>While the macro runs it refreshes the data from Fandom automatically; the last verified copy is cached locally for offline use.</li><li>The source badge on the page shows whether you are viewing live Fandom data, the local cache, or the bundled offline snapshot.</li><li>Biome and aura statistics used by webhooks come from the same dataset.</li></ul>
      </Section>

      <Section icon="🎁" title="Daily (event) Rewards">
        <p>With <b>Daily Rewards</b> enabled in <b>Misc</b>, the macro claims the daily check-in automatically at 03:00 MSK. To verify the flow at any time, use the buttons under the toggle:</p>
        <ul><li><b>Collect now (test)</b> — runs one claim attempt immediately and reports the OCR result (requires the macro to be started and Roblox focused).</li><li><b>Reset claimed date</b> — clears the stored date so the next window collects again.</li></ul>
      </Section>

      <Section icon="✨" title="Auras, Potion Crafting, and Webhook">
        <p><b>Auras</b> configures detection, recording, force-ping, and aura equipping. <b>Potion Crafting</b> records/replays Stella recipes and can switch selected recipes. <b>Webhook</b> stores Discord destinations and notification preferences.</p>
        <p>Recordings use the in-game names/files exactly. Check the log after the first run to verify the selected file and target.</p>
      </Section>

      <Section icon="🪟" title="Multiple-Instances and safety">
        <p>Multiple-Instances is designed for Roblox windows started by the current Windows user. The first login is manual; saved profiles are runtime records for reconnect. Secondary windows remain passive and do not receive foreground fishing, pathing, OCR, or mouse automation.</p>
        <p>Never share webhook URLs, cookies, private-server links, or account identifiers. Stop the macro before changing calibration or closing Roblox.</p>
      </Section>

      <Section icon="⚙️" title="Status, Stats, Notice, Panel Customization, and Credits">
        <ul><li><b>Status:</b> shows enabled workers, active workers, and detected conflicts.</li><li><b>Stats:</b> shows session time, biome counts, and history.</li><li><b>Notice:</b> contains release notes and important warnings.</li><li><b>Panel Customization:</b> changes appearance, labels, icons, font, and background without changing automation logic.</li><li><b>Credits:</b> contains project attribution and original-author acknowledgement.</li></ul>
      </Section>

      <Section icon="🧭" title="Troubleshooting checklist">
        <ol><li>If a click misses, recalibrate the affected point and confirm Roblox mode/scale.</li><li>If a route is too slow or too fast, verify the selected VIP/Non-VIP option and playback multiplier.</li><li>If an item is skipped, check its exact in-game name, OCR visibility, amount, and Auto Pop order.</li><li>If workers wait indefinitely, open <b>Status</b> and disable the competing foreground feature.</li><li>Always reproduce the issue with one feature enabled before changing several settings at once.</li></ol>
      </Section>
    </div>
  );
}
