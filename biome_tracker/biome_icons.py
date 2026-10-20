"""Biome spawn icons shipped with the macro.

The icons live in `assets/biome_icons/` inside this repository and are
published with the source code, so the panel can point Discord embeds and
the biome lists at the project's OWN copy instead of a third-party repo.

Serving them through a CDN (jsDelivr) instead of `raw.githubusercontent.com`:
  - `raw.githubusercontent.com` is rate-limited (HTTP 403) once a few
    hundred requests per minute come in — Discord fetches every embed
    thumbnail separately, and the panel itself re-fetches icons on every
    biome change;
  - jsDelivr serves immutable, cached copies from many edge locations and
    does not count against the GitHub rate limit.

The file name inside `assets/biome_icons/` is the biome name in lower case
(``the null's existence.png``), so a new biome only needs one new PNG.

`BIOME_ICON_FILES` is the single source of truth — the default config
(`mixin_config.py`), the config migration (`config.py`) and the Discord
Webhook Customization page all read the map from here.
"""

from __future__ import annotations

from urllib.parse import quote

# ── Where the icons are published ──────────────────────────────────────────
GITHUB_REPO = "MiraxKito/EndSol-Macro"

#: Primary CDN for the published biome icons.
BIOME_ICON_CDN_BASE = f"https://cdn.jsdelivr.net/gh/{GITHUB_REPO}@main/assets/biome_icons"
#: Fallback CDN (different edge network) — used if jsDelivr is unreachable.
BIOME_ICON_CDN_FALLBACK_BASE = f"https://cdn.statically.io/gh/{GITHUB_REPO}/main/assets/biome_icons"
#: Direct GitHub copy (rate-limited, kept for the raw fallback).
BIOME_ICON_RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_REPO}/main/assets/biome_icons"

#: Biome name -> file name inside `assets/biome_icons/`.
#: Names match the keys used by `biome_data` (upper case, wiki spelling).
BIOME_ICON_FILES: dict[str, str] = {
    "AURORA": "aurora.png",
    "BLAZING SUN": "blazing sun.png",
    "BLOOD RAIN": "blood rain.png",
    "CORRUPTION": "corruption.png",
    "CYBERSPACE": "cyberspace.png",
    "DREAMSPACE": "dreamspace.png",
    "EGGLAND": "eggland.png",
    "GLITCHED": "glitched.png",
    "GRAVEYARD": "graveyard.png",
    "HEAVEN": "heaven.png",
    "HELL": "hell.png",
    "INCINERATOR": "incinerator.png",
    "LOST FOREST": "lost forest.png",
    "NORMAL": "normal.png",
    "NULL": "null.png",
    "PUMPKIN MOON": "pumpkin moon.png",
    "RAINY": "rainy.png",
    "SAND STORM": "sand storm.png",
    "SINGULARITY": "singularity.png",
    "SNOWY": "snowy.png",
    "STARFALL": "starfall.png",
    "THE CITADEL OF ORDERS": "the citadel of orders.png",
    "THE HYPERSPACE REALM": "the hyperspace realm.png",
    "THE NULL'S EXISTENCE": "the null's existence.png",
    "THE RADIANT FOREST": "radiant forest.png",
    "WINDY": "windy.png",
}

#: Chat color of every biome that has a spawn icon. The values come from the
#: Fandom "Biomes" article (the wiki's own <font color=...> tags).
BIOME_COLORS: dict[str, str] = {
    "AURORA": "0x0047ab",
    "CORRUPTION": "0x6d32a8",
    "CYBERSPACE": "0x0A1A3D",
    "DREAMSPACE": "0xea9dda",
    "EGGLAND": "0xd4fc8d",
    "GLITCHED": "0xbfff00",
    "HEAVEN": "0xFFE8A0",
    "HELL": "0xff4719",
    "NORMAL": "0xffffff",
    "NULL": "0x838383",
    "RAINY": "0x027cbd",
    "SAND STORM": "0x8F7057",
    "SINGULARITY": "0xcf4023",
    "SNOWY": "0xDceff9",
    "STARFALL": "0x011ab7",
    "WINDY": "0xF2F6FF",
    "BLAZING SUN": "0xFF6B00",
    "PUMPKIN MOON": "0xFF6600",
    "GRAVEYARD": "0x4A4A4A",
    "BLOOD RAIN": "0xCC0000",
    "THE NULL'S EXISTENCE": "0x1a1a2e",
    "THE HYPERSPACE REALM": "0x9b59b6",
    "THE CITADEL OF ORDERS": "0xc0a030",
    "INCINERATOR": "0xfc6537",
    "LOST FOREST": "0x27F55E",
    "THE RADIANT FOREST": "0x8A48A8",
}

#: Biomes without an icon in this repository. The admin-only Red Full Moon
#: is a dev/admin biome and never got a spawn icon here, so it keeps the
#: OysterDetector copy — OysterDetector stays a valid icon source.
EXTERNAL_ICON_ENTRIES: dict[str, dict[str, str]] = {
    "赤い満月": {
        "color": "0xcc0000",
        "thumbnail_url": "https://raw.githubusercontent.com/vexsyx/OysterDetector/main/assets/unknown_biome.png",
    },
}

#: Legacy icon sources that used to ship as the default. Configs saved
#: before the switch still point at them — they are rewritten to the
#: project's own CDN on load. The user's OWN custom URL is never touched.
#: All markers are lower case — URLs are compared case-insensitively.
LEGACY_ICON_URL_MARKERS: tuple[str, ...] = (
    "raw.githubusercontent.com/vexsyx/oysterdetector",
    "github.com/vexsyx/oysterdetector",
    "raw.githubusercontent.com/xvapure/noteab-macro",
    "github.com/xvapure/noteab-macro",
    "i.postimg.cc",
)

#: Hosts known to be dead for embed thumbnails (checked in the Discord
#: Webhook Customization page).
BROKEN_ICON_HOST_MARKERS: tuple[str, ...] = (
    "maxstellar",
    "fandom.com",
    "wikia.nocookie.net",
    "static.wikia",
    "fandomusercontent",
)

#: Hosts that are known to work for embed thumbnails.
TRUSTED_ICON_HOST_MARKERS: tuple[str, ...] = (
    "cdn.jsdelivr.net/gh/MiraxKito/EndSol-Macro",
    "cdn.statically.io/gh/MiraxKito/EndSol-Macro",
    "raw.githubusercontent.com/MiraxKito/EndSol-Macro",
    "cdn.jsdelivr.net/gh/vexsyx/OysterDetector",
    "cdn.statically.io/gh/vexsyx/OysterDetector",
    "raw.githubusercontent.com/vexsyx/OysterDetector",
)


def _icon_file(biome_name: str) -> str:
    """Return the icon file name for a biome (case/spacing tolerant)."""
    name = str(biome_name or "").strip()
    if not name:
        return ""
    if name in BIOME_ICON_FILES:
        return BIOME_ICON_FILES[name]
    upper = name.upper()
    if upper in BIOME_ICON_FILES:
        return BIOME_ICON_FILES[upper]
    collapsed = " ".join(upper.split())
    if collapsed in BIOME_ICON_FILES:
        return BIOME_ICON_FILES[collapsed]
    return ""


def biome_icon_url(biome_name: str, base: str = BIOME_ICON_CDN_BASE) -> str:
    """CDN URL of the biome spawn icon ("" when the biome has no icon)."""
    file_name = _icon_file(biome_name)
    if not file_name:
        return ""
    return f"{base.rstrip('/')}/{quote(file_name)}"


def is_legacy_icon_url(url: str) -> bool:
    """True when the URL points at one of the old third-party icon sources."""
    text = str(url or "").strip().lower()
    if not text:
        return False
    return any(marker in text for marker in LEGACY_ICON_URL_MARKERS)


#: The macro's own icon for the Discord embed footer. It comes from this
#: repository instead of a third-party image host, so it cannot die with
#: somebody else's account.
MACRO_FOOTER_ICON_URL = f"https://cdn.jsdelivr.net/gh/{GITHUB_REPO}@main/assets/endsol-macro.jpg"


def icon_url_mirrors(url: str) -> list[str]:
    """Public mirrors of one biome icon, best first.

    Discord fetches embed pictures from its own servers, so the icon has to
    live on a public host — a local server would never be reachable. The
    primary CDN is tried first, then the second CDN, then the raw copy, so
    a single unreachable host does not leave the embed without an icon.
    """
    text = str(url or "").strip()
    if not text:
        return []
    mirrors = [text]
    for base in (BIOME_ICON_CDN_BASE, BIOME_ICON_CDN_FALLBACK_BASE, BIOME_ICON_RAW_BASE):
        prefix = base.rstrip("/") + "/"
        if text.startswith(prefix):
            mirrors.append(prefix + text[len(prefix):])
    # The same file on the other hosts, when the URL points at our repo.
    for base in (BIOME_ICON_CDN_FALLBACK_BASE, BIOME_ICON_RAW_BASE):
        for known in (BIOME_ICON_CDN_BASE, BIOME_ICON_CDN_FALLBACK_BASE, BIOME_ICON_RAW_BASE):
            prefix = known.rstrip("/") + "/"
            if text.startswith(prefix):
                mirrors.append(base.rstrip("/") + "/" + text[len(prefix):])
                break
    seen = set()
    out = []
    for m in mirrors:
        if m and m not in seen:
            seen.add(m)
            out.append(m)
    return out


def migrate_legacy_icon_urls(overrides) -> int:
    """Rewrite legacy third-party icon URLs to the project's own CDN.

    Only URLs that still point at a known legacy source are replaced — a
    user who typed their own image URL keeps it. Returns the number of
    rewritten entries.
    """
    if not isinstance(overrides, dict):
        return 0
    changed = 0
    for biome_name, entry in overrides.items():
        if not isinstance(entry, dict):
            continue
        url = str(entry.get("thumbnail_url") or "")
        if not url or not is_legacy_icon_url(url):
            continue
        new_url = biome_icon_url(biome_name)
        if not new_url:
            continue
        entry["thumbnail_url"] = new_url
        changed += 1
    return changed


def default_biome_overrides(colors: dict[str, str] | None = None) -> dict[str, dict]:
    """Default `custom_biome_overrides` payload.

    Contains every biome that has a spawn icon in `assets/biome_icons/`
    (CDN URL + chat color) plus the few biomes that still use an external
    icon. This is the single source of truth for the default overrides —
    `defaults.py`, `config.py` and `mixin_config.py` all read it from here.
    """
    colors = colors if colors is not None else BIOME_COLORS
    out: dict[str, dict] = {}
    for biome_name in BIOME_ICON_FILES:
        entry: dict[str, str] = {"thumbnail_url": biome_icon_url(biome_name)}
        color = colors.get(biome_name)
        if color:
            entry["color"] = color
        out[biome_name] = entry
    for biome_name, entry in EXTERNAL_ICON_ENTRIES.items():
        out[biome_name] = dict(entry)
    return out
