
# EndSol Macro

Automation macro for **Sol's RNG** (Roblox): biome tracking with Discord webhooks, Memory Match and Quest Board auto-play, fishing, auto item usage, custom walk paths, and an in-game wiki browser (Sol's Book) — all in one desktop panel.

> Based on [Noteab-Macro](https://github.com/xVapure/Noteab-Macro) by xVapure — thanks to the original author. This project is an independent continuation with its own feature set.

<img width="1024" height="1024" alt="endsol-macro" src="https://github.com/user-attachments/assets/c7dad909-1fa2-4610-9d52-654c430217fa" />
## Features

- **Biome detection** — reads Roblox logs, detects every biome, sends rich Discord webhook messages (customizable titles, colors, pings).
- **Aura webhooks** — rarity-aware announcements with configurable ping thresholds; event / Transcendent / Challenged classes handled automatically.
- **Memory Match** — auto-plays the Memory Match minigame: reveals tiles, remembers items and quantities, prioritizes high-value rewards, verifies every pair.
- **Quest Board** — accepts/dismisses quests by your per-type preferences, tolerant to OCR noise.
- **Fishing** — fully automatic fishing with selling and failsafes.
- **Custom paths** — record your own walk routes (fishing spot, obby, egg routes, Memory Match) with VIP/non-VIP speed handling.
- **Sol's Book** — built-in wiki browser with live Fandom data: auras, biomes, videos, crafting recipes. <img width="1646" height="840" alt="image" src="https://github.com/user-attachments/assets/a81f48dd-0b2a-46f3-9df6-a8911986dbc1" />

- **Auto Pop / Strange Controller / Biome Randomizer**, daily rewards, anti-AFK, auto-reconnect, multi-instance support.
- **Remote control** — Discord bot integration for status and control from your phone.
- **Panel** — desktop app (pywebview + React) with EN/RU localization and deep UI customization.

<img width="959" height="537" alt="image" src="https://github.com/user-attachments/assets/5ead6f00-94f6-4d46-b720-8623be4fe121" />

<img width="1920" height="1036" alt="image" src="https://github.com/user-attachments/assets/c44821a2-8c5e-478d-bca4-33ddb0964e7e" />

## Installation

### Ready EXE (recommended)

1. Download `EndSolMacro.exe` from the [Releases](https://github.com/MiraxKito/EndSol-Macro/releases/latest) page.
2. Run it — everything is packed into one file. User data lives in `%LOCALAPPDATA%\EndSolMacro`.
3. Follow the in-panel instructions: calibrate the Memory Match / Quest Board grids, set up your Discord webhook, and start the macro (F1) with Roblox open.

The in-app updater checks GitHub Releases automatically and offers new versions.

### From source

Requires **Python 3.13** and **Node.js**:

```bat
git clone https://github.com/MiraxKito/EndSol-Macro.git
cd EndSol-Macro
build_windows_exe.bat   :: creates .venv, installs deps, builds frontend + EXE
```

To just run from source without building the EXE:

```bat
build_frontend.bat      :: once, builds frontend/dist
Start.bat
```

See [BUILD_EXE.md](BUILD_EXE.md) and [BUILD_PROTECTED_EXE.md](BUILD_PROTECTED_EXE.md) for build details, including the Nuitka-compiled release build.

## Important notes

- Windows OCR is used for reading game text — run Windows in your display language and keep the game in English.
- Calibrate at **1920×1080, 100% scaling** for the shipped calibration profiles to work out of the box.
- Use of automation may violate Roblox ToS — use at your own risk on your own account.
- Never share your `config.json`: it contains your Discord webhook URL and bot token.

## Community calibrations

Running a non-standard setup (different resolution, scaling, or window mode)? Share your working calibration so others can use it: open [Discussions](https://github.com/MiraxKito/EndSol-Macro/discussions), pick the **Calibration sharing** template, and attach the JSON exported from *Macro Calibrations → Export*. Verified presets are added to the built-in calibration picker, where everyone can load them with one click.

## Support

EndSol Macro is free and will stay free. If you want to support development: [Boosty](https://boosty.to/eds_mirax/donation).

## License

Free for personal, non-commercial use. See [LICENSE.txt](LICENSE.txt) — redistribution, republishing as your own, or commercial use is not allowed without permission. Third-party dependencies keep their own licenses.
