<div align="center">

<p align="center"><img width="400" height="400" alt="endsol-macro" src="https://github.com/user-attachments/assets/f178a686-26c4-4e6b-a310-c285e7f1860c" /></p>

# EndSol Macro

**All-in-one automation panel for Sol's RNG (Roblox)**

Biome tracking · Discord webhooks · Sol's Book wiki · Memory Match · Quest Board · Fishing · Multi-instance

[Download](https://github.com/MiraxKito/EndSol-Macro/releases/latest) · [Report an issue](https://github.com/MiraxKito/EndSol-Macro/issues) · [Discussions](https://github.com/MiraxKito/EndSol-Macro/discussions)

<p align="center"><img width="972" height="548" alt="image" src="https://github.com/user-attachments/assets/ae9756fa-7d9c-4088-97cd-8a7250832310" /></p>

</div>

> Based on [Noteab-Macro](https://github.com/xVapure/Noteab-Macro) by xVapure — thanks to the original author. EndSol Macro is an independent continuation with its own feature set.

---

## ✨ Features

**Tracking & alerts**
- **Biome detection** — reads Roblox logs in real time and announces every biome with rich, fully customizable Discord webhooks: titles, colors, thumbnails, pings.
- **Aura webhooks** — rarity-aware announcements with configurable ping thresholds.

**Automation**
- **Memory Match** — auto-plays the Memory Match minigame: reveals tiles, remembers items and quantities, prioritizes high-value rewards, and verifies every pair.
- **Quest Board** — accepts or dismisses quests according to your preferences, tolerant to OCR noise.
- **Fishing** — fully automatic fishing with selling and failsafes.
- **Custom paths** — record your own walk routes (fishing spot, obby, egg routes, Memory Match) with VIP / non-VIP speed handling.
- **Multi-instance support** — run several Roblox windows under one panel.

**Sol's Book — built-in wiki 📖**
- Browse **Auras, Biomes, Items and Gauntlets** databases synced from the Sol's RNG Fandom Wiki: rarity, obtainment, crafting recipes, effects, descriptions.
- **Media tab** per entry — cutscene videos, opening cutscenes, image galleries and theme music, played from a local cache so they work reliably and offline after the first view.
<p align="center"><img width="1920" height="1018" alt="aura tab endsol" src="https://github.com/user-attachments/assets/6206bc39-43c4-4822-8906-47108675a294" /></p>


**Panel**
- Desktop app built with **pywebview + React**: EN/RU localization, theming, panel customization, live logs and diagnostics.
- **Remote control** — Discord bot integration: check status and control the macro from your phone.

<p align="center"><img width="1920" height="1018" alt="biome tab endsol" src="https://github.com/user-attachments/assets/d693b23d-1b2a-4608-a9c1-9d098bfa444c" /></p>


## Installation

### Ready EXE (recommended)

1. Download `EndSolMacro.exe` from the [Releases](https://github.com/MiraxKito/EndSol-Macro/releases/latest) page.
2. Run it — everything is packed into one file. User data lives in `%LOCALAPPDATA%\EndSolMacro`.
3. Follow the in-panel instructions:
   - set up your Discord webhook and private server link,
   - set up your calibrations (if you are not on 1920x1080px, 100% scale and fullscreen),
   - press **F1** to start (or **F2** to stop).

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

See [BUILD_EXE.md](BUILD_EXE.md) and [BUILD_PROTECTED_EXE.md](BUILD_PROTECTED_EXE.md) for build details.

## ⚠️ Important notes

- Windows OCR is used to read game text — run Windows in your display language and keep the game in **English**.
- Calibrate at **1920×1080, 100% scaling** for the shipped calibration profiles to work out of the box.
- Use of automation may violate Roblox ToS — use at your own risk on your own account.
- Never share your `config.json`: it contains your Discord webhook URL and bot token.

## 🤝 Community calibrations

Running a non-standard setup (different resolution, scaling, or window mode)? Share your working calibration so others can use it: open [Discussions](https://github.com/MiraxKito/EndSol-Macro/discussions), pick the **Calibration sharing** template, and attach the JSON exported from *Macro Calibrations → Export*. Verified presets are added to the built-in calibration picker, where everyone can load them with one click.

## 💜 Support

EndSol Macro is free and will stay free. If you want to support development: [Boosty](https://boosty.to/eds_mirax/donation).

## 📄 License

Free for personal, non-commercial use. See [LICENSE.txt](LICENSE.txt) — redistribution, republishing as your own, or commercial use is not allowed without permission. Third-party dependencies keep their own licenses.
