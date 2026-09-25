"""
Sol's Book — live wiki datasets for items and gauntlets (v1.0.7).

Implements the no-fallback Fandom pipeline that was used to build the
verified offline snapshots ``biome_tracker/gauntlets_fandom.json`` (53
records: gauntlets / lanterns / talismans) and
``biome_tracker/items_fandom.json`` (93 records). The offline snapshots stay
the source of truth whenever the wiki cannot be reached — a failed update
NEVER wipes or replaces them.

Hard rules (do not regress — they were paid for with a broken session):
  * Source is the MediaWiki API:
        https://sol-rng.fandom.com/api.php?action=parse&page=<title>
            &prop=wikitext&format=json&redirects=1
    with a browser User-Agent. ALL requests go through
    ``base_support.fandom_get`` (process-wide 1.0 s pacing + 429 cooldown).
  * API responses that carry an ``error`` key are NEVER cached or persisted.
    (A previous build once cached 90 error responses and broke half of the
    loaders.)
  * No fallbacks: a record without confirmed wiki data is dropped, never
    invented ("Heavenly Potion II" has no wiki page — it is deleted, not
    fabricated).
  * Gauntlets: ``Category:Left Gear`` -> slot "Left Hand",
    ``Category:Right Gear`` -> "Right Hand". Lanterns and talismans have no
    pages of their own — they are <tabber> tabs on the "Lanterns" and
    "Talismans" pages, slot "Pocket". Fields come from ``{{Gears Infobox}}``
    (title, obtainment, boost, effect, recipe, image gallery) plus the
    description from ``{{Item Quote}}``.
  * Items: direct page first; if missing — candidates: the name without
    bracket/roman-numeral suffix, then plural forms; hierarchical potions
    live on aggregated pages (Fortune Potions, Heavenly Potions, Godly
    Potions, Forbidden Potions, Haste Potions, Red Moon Potions, Strange
    Potions, Lucky Potion, Speed Potion) matched by tab/section name
    (normalization: lowercase + strip everything except [a-z0-9]; the Runes
    tabs have a leading space). Easter/dev items (Adele Doll, MandooMon
    Doll, XC' Signature, dwjk pillow, ...) exist only as table rows on the
    "Items" page — their name/description/effect/file come from there.
  * Template parsing: ``{{Item Quote}}`` may be positional
    (``|Gives you ...|Description``) — never include the template name in
    the text. Wiki cleanup: drop '''/''', tags, templates ({{Aura|X}} -> X —
    the last argument), links [[A|B]] -> B. NEVER drop lines that start with
    "-" (boosts like "-50% Luck, +75% Roll Speed" would vanish). Obtainment
    sections may be named Obtainment / Recipe / Brewing / Requirements — a
    section that is just one table cleans to an empty string, so keep
    looking instead of stopping at the first non-empty RAW text.
  * Thumbnails: file names are resolved via ``prop=imageinfo``; an old
    thumbnail is kept only when the file really exists on the wiki.
"""

from __future__ import annotations

import html as _html
import re
import threading
import time
import urllib.parse

WIKI_API = "https://sol-rng.fandom.com/api.php"
WIKI_BASE = "https://sol-rng.fandom.com/wiki/"

# Browser-like UA (matches main.py's media-cache client that is already
# verified against Fandom's Cloudflare).
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
_HEADERS = {"User-Agent": BROWSER_UA, "Referer": "https://sol-rng.fandom.com/"}

# Aggregated potion pages: hierarchical potions live here as tabs, not as
# standalone pages (verified against the live wiki).
AGGREGATED_POTION_PAGES = (
    "Fortune Potions",
    "Heavenly Potions",
    "Godly Potions",
    "Forbidden Potions",
    "Haste Potions",
    "Red Moon Potions",
    "Strange Potions",
    "Lucky Potion",
    "Speed Potion",
)
RUNES_PAGE = "Runes"
ITEMS_PAGE = "Items"

# Fallback HTTP when base_support cannot be imported (non-Windows dev box).
# Production always uses base_support.fandom_get (same pacing rules).
_fb_lock = threading.Lock()
_fb_last = [0.0]


def _fandom_get(url, timeout=20):
    try:
        from biome_tracker.base_support import fandom_get as _fg
    except Exception:
        try:
            from base_support import fandom_get as _fg  # type: ignore
        except Exception:
            _fg = None
    if _fg is not None:
        try:
            return _fg(url, timeout=timeout, headers=_HEADERS)
        except TypeError:
            return _fg(url, timeout=timeout)
    # Minimal process-wide 1.0 s pacing, mirroring base_support's gate.
    import requests

    while True:
        with _fb_lock:
            wait = _fb_last[0] + 1.0 - time.time()
            if wait <= 0:
                _fb_last[0] = time.time()
                break
        time.sleep(min(max(wait, 0.05), 2.0))
    try:
        import requests as _requests

        return _requests.get(url, timeout=timeout, headers=_HEADERS)
    except Exception:
        return None


def _api_json(params, timeout=20):
    """GET an api.php endpoint. Returns a dict or None.

    Responses carrying an "error" key are NEVER returned as data — callers
    treat None as "unavailable" (keep offline data) and detect
    confirmed-absent pages via fetch_page_status instead.
    """
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    resp = _fandom_get(url, timeout=timeout)
    if resp is None:
        return None
    if not getattr(resp, "ok", False):
        return None
    try:
        raw = resp.json()
    except Exception:
        return None
    if not isinstance(raw, dict) or "error" in raw:
        return None
    return raw


def fetch_page_status(title, timeout=20):
    """Fetch a page's wikitext. Returns (status, wikitext):

      "ok"          -> wikitext
      "missing"     -> the wiki CONFIRMED the page does not exist
                       (missingtitle; safe to treat the record as absent)
      "unavailable" -> network / API error — NOT a confirmation; callers
                       must keep the offline record untouched
    """
    url = (
        WIKI_API
        + "?"
        + urllib.parse.urlencode(
            {
                "action": "parse",
                "page": title,
                "prop": "wikitext",
                "format": "json",
                "redirects": "1",
            }
        )
    )
    resp = _fandom_get(url, timeout=timeout)
    if resp is None or not getattr(resp, "ok", False):
        return ("unavailable", "")
    try:
        raw = resp.json()
    except Exception:
        return ("unavailable", "")
    if not isinstance(raw, dict):
        return ("unavailable", "")
    if "error" in raw:
        code = str((raw.get("error") or {}).get("code", ""))
        if code == "missingtitle":
            return ("missing", "")
        return ("unavailable", "")
    parse = raw.get("parse") or {}
    wikitext = (parse.get("wikitext") or {}) if isinstance(parse, dict) else {}
    text = wikitext.get("*", "") or ""
    if not str(text).strip():
        return ("unavailable", "")
    return ("ok", text)


def category_members(category, timeout=20):
    """All content pages in a category (ns=0), e.g. 'Category:Left Gear'.
    Returns None when the API is unavailable (not an empty category)."""
    titles = []
    continue_token = ""
    while True:
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmnamespace": "0",
            "cmlimit": "500",
            "format": "json",
            "formatversion": "2",
        }
        if continue_token:
            params["cmcontinue"] = continue_token
        raw = _api_json(params, timeout=timeout)
        if raw is None:
            return None
        members = (raw.get("query") or {}).get("categorymembers") or []
        titles.extend(m.get("title", "") for m in members if isinstance(m, dict))
        cont = (raw.get("continue") or {}).get("cmcontinue") or ""
        if not cont:
            break
        continue_token = cont
    return [t for t in titles if t]


def page_categories(titles, timeout=20):
    """Batch page categories (50 titles per query, handle 'continue')."""
    out = {}
    titles = [t for t in titles if t]
    for i in range(0, len(titles), 50):
        chunk = titles[i : i + 50]
        continue_token = ""
        while True:
            params = {
                "action": "query",
                "prop": "categories",
                "titles": "|".join(chunk),
                "cllimit": "500",
                "format": "json",
                "formatversion": "2",
            }
            if continue_token:
                params["clcontinue"] = continue_token
            raw = _api_json(params, timeout=timeout)
            if raw is None:
                return None
            for p in (raw.get("query") or {}).get("pages") or []:
                if not isinstance(p, dict):
                    continue
                cats = [
                    c.get("title", "")
                    for c in (p.get("categories") or [])
                    if isinstance(c, dict)
                ]
                out[p.get("title", "")] = cats
            cont = (raw.get("continue") or {}).get("clcontinue") or ""
            if not cont:
                break
            continue_token = cont
    return out


def imageinfo_urls(file_names, timeout=20):
    """Resolve wiki file names to CDN URLs. Files that do not exist on the
    wiki are simply absent from the result (never guessed)."""
    out = {}
    names = []
    seen = set()
    for n in file_names:
        if n and n not in seen:
            seen.add(n)
            names.append(n)
    for i in range(0, len(names), 50):
        chunk = names[i : i + 50]
        raw = _api_json(
            {
                "action": "query",
                "titles": "|".join("File:" + n for n in chunk),
                "prop": "imageinfo",
                "iiprop": "url",
                "format": "json",
                "formatversion": "2",
            },
            timeout=timeout,
        )
        if raw is None:
            return None
        normalized = {n.lower(): n for n in chunk}
        for p in (raw.get("query") or {}).get("pages") or []:
            if not isinstance(p, dict):
                continue
            title = str(p.get("title", ""))
            if p.get("missing"):
                continue
            ii = (p.get("imageinfo") or [{}])[0]
            url = ii.get("url") if isinstance(ii, dict) else None
            if not url:
                continue
            name = title.replace("File:", "", 1)
            out[name] = url
            lower = name.lower()
            if lower in normalized and normalized[lower] != name:
                out[normalized[lower]] = url
    return out


# ------------------------------------------------------------------
# Wikitext cleanup
# ------------------------------------------------------------------

_TAG_RE = re.compile(r"</?[A-Za-z][^>]*>")
_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_GALLERY_RE = re.compile(r"<gallery[^>]*>.*?</gallery[^>]*>", re.S | re.I)
_TABLE_START_RE = re.compile(r"(?m)^\s*\{\|.*$", re.I)
_TABLE_END_RE = re.compile(r"(?m)^\s*\|\}\s*$")
_TABLE_ROW_RE = re.compile(r"(?m)^\s*\|-.*$",)
_TABLE_HEAD_RE = re.compile(r"(?m)^\s*!.*$")


def _innermost_template_spans(text):
    """Spans of innermost {{...}} occurrences."""
    spans = []
    i = 0
    n = len(text)
    while i < n - 1:
        if text[i : i + 2] == "{{":
            j = i + 2
            while j < n - 1:
                if text[j : j + 2] == "{{":
                    j += 2
                elif text[j : j + 2] == "}}":
                    break
                else:
                    j += 1
            if j < n - 1:
                spans.append((i, j + 2))
                i = j + 2
                continue
            break
        i += 1
    return spans


def _resolve_template(inner):
    """{{Aura|X}} -> X, {{Items|A|B}} -> B — a template collapses to its
    last non-empty argument. Color helper templates collapse to ""."""
    inner = inner.strip()
    parts = inner.split("|")
    if len(parts) == 1:
        return ""
    name = parts[0].strip()
    if "color" in name.lower() or "font" in name.lower() and name.lower() != "font":
        pass
    if "color" in name.lower():
        return ""
    args = parts[1:]
    named = []
    positional = []
    for a in args:
        a = a.strip()
        m = re.match(r"^([0-9]+)\s*=", a)
        if m:
            named.append((int(m.group(1)), a[m.end() :].strip()))
        elif re.match(r"^[A-Za-z_][A-Za-z0-9_ ()\-]*\s*=", a):
            continue
        else:
            positional.append(a)
    if named:
        named.sort(key=lambda t: t[0])
        for _k, val in reversed(named):
            if val:
                return val
    for a in reversed(positional):
        if a:
            return a
    return ""


def _clean_segment(text):
    """Clean one chunk of wikitext (no table handling)."""
    text = _COMMENT_RE.sub("", text)
    text = _GALLERY_RE.sub("", text)
    # <br> disappears, but keeps prose readable when it separated words
    # ("device.<br><br>Changes" -> "device. Changes"; "nerves.<br>+850%" gets
    # no space before the "+" boost - matches the verified dataset)
    text = re.sub(r"<br\s*/?>", "\x00", text, flags=re.I)
    text = _TAG_RE.sub("", text)
    # a space after <br> keeps prose readable ("[Quick Roll] [Quick Roll]",
    # "device. Changes") — but boost signs glue on directly
    # ("nerves.+850% Base Luck", matches the verified dataset)
    text = re.sub(r"\x00(?![+])", lambda m, _t=text: " " if (
        m.end() < len(_t)
        and (_t[m.end()].isalpha() or _t[m.end()] in "[*'”\"")
    ) else "", text)
    text = text.replace("\x00", "")
    text = text.replace("{{!}}", "!")
    for _ in range(60):
        spans = _innermost_template_spans(text)
        if not spans:
            break
        for start, end in reversed(spans):
            text = (
                text[:start]
                + _resolve_template(text[start + 2 : end - 2])
                + text[end:]
            )
    def _link_sub(m):
        inner = m.group(1)
        if re.match(r"^\s*File\s*:", inner, re.I):
            return inner.split("|", 1)[1] if "|" in inner else ""
        if re.match(r"^\s*Category\s*:", inner, re.I):
            return ""
        if "|" in inner:
            return inner.split("|", 1)[1]
        return inner

    # nested display brackets: [[Target|[Display]]] -> "[Display]"
    text = re.sub(r"\[\[([^\[\]|]+)\|((\[[^\[\]]*\])+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\[\]]+)\]\]", _link_sub, text)
    # external links stay raw (verified: "[https://... Jujutsu Kaisen]")
    text = text.replace("'''", "").replace("''", "")
    text = re.sub(r"\s+data-[a-z-]+=\"[^\"]*\"", "", text)
    text = _html.unescape(text)
    # "Lunar : Full Moon" -> "Lunar: Full Moon"; ":Flushed:" keeps its
    # leading colon ("2,000x :Flushed:" -> "2,000x:Flushed:")
    text = re.sub(r"[ \t]+:", ":", text)
    # "</b> )" -> ")" (reference: "((1 + Basic Buff) x Bonus Roll ...)")
    text = re.sub(r"[ \t]+\)", ")", text)
    return text


def clean_wikitext(text, join_lines=True, joiner=" "):
    """Wiki markup -> plain text. Keeps lines starting with "-" (boosts like
    "-50% Luck" must survive). Table structure is dropped but table cell
    text is preserved. Lines are joined with `joiner` (quotes/prose use " ",
    obtainment sections and table cells use "; " unless join_lines=False)."""
    if not text:
        return ""
    text = _clean_segment(text)
    lines = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if re.match(r"^\{\|", line) or re.match(r"^\|\}", line) or line == "|-":
            continue
        # table rows: split cells on | / || but keep cell text
        if line.startswith("|"):
            body = line[1:]
            body = re.sub(r"\|\|", " | ", body)
            segs = [s.strip() for s in body.split("|")]
            segs = [s for s in segs if s]
            if segs:
                lines.append(" ".join(segs))
            continue
        if line.startswith("!"):
            continue
        if re.match(r"^={2,4}.*={2,4}$", line):
            continue  # heading lines never belong to the prose
        line = re.sub(r"^\*+", "", line).strip()
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)
    if not lines:
        return ""
    if not join_lines:
        return "\n".join(lines).strip()
    return joiner.join(lines).strip()


def _canon(name):
    return re.sub(r"[^a-z0-9]", "", str(name or "").lower())


# ------------------------------------------------------------------
# Template / structure extraction
# ------------------------------------------------------------------


def _find_template(text, name, start=0):
    """Locate a balanced {{Name ...}} template. Returns (inner, end) or None."""
    empty = re.compile(r"\{\{\s*" + re.escape(name) + r"\s*\}\}", re.I)
    m = empty.search(text, start)
    if m:
        return ("", m.end())
    pattern = re.compile(r"\{\{\s*" + re.escape(name) + r"\s*[|:]", re.I)
    m = pattern.search(text, start)
    if not m:
        return None
    open_start = m.start()
    depth = 1
    j = m.end()
    n = len(text)
    while j < n - 1:
        if text[j : j + 2] == "{{":
            depth += 1
            j += 2
        elif text[j : j + 2] == "}}":
            depth -= 1
            if depth == 0:
                return (text[open_start + 2 : j], j + 2)
            j += 2
        else:
            j += 1
    return None


def _split_top_level(inner):
    """Split template inner content on top-level '|' (respect {{ }}, [[ ]],
    and <gallery> blocks)."""
    parts = []
    buf = []
    depth = 0
    link_depth = 0
    i = 0
    n = len(inner)
    low = inner.lower()
    while i < n:
        if low.startswith("<gallery", i):
            close = inner.find(">", i)
            if close != -1:
                buf.append(inner[i : close + 1])
                i = close + 1
                # skip to </gallery>
                endm = re.compile(r"</gallery\s*>", re.I).search(inner, i)
                if endm:
                    buf.append(inner[i : endm.end()])
                    i = endm.end()
                continue
        two = inner[i : i + 2]
        if two == "[[":
            link_depth += 1
            buf.append(two)
            i += 2
            continue
        if two == "]]" and link_depth:
            link_depth -= 1
            buf.append(two)
            i += 2
            continue
        if link_depth == 0:
            if two == "{{":
                depth += 1
                buf.append(two)
                i += 2
                continue
            if two == "}}":
                depth = max(0, depth - 1)
                buf.append(two)
                i += 2
                continue
            if inner[i] == "|" and depth == 0:
                parts.append("".join(buf))
                buf = []
                i += 1
                continue
        buf.append(inner[i])
        i += 1
    parts.append("".join(buf))
    return parts


def _parse_template_args(inner):
    """Parse template arguments into (named, positional). Keys lowercased."""
    named = {}
    positional = []
    for idx, part in enumerate(_split_top_level(inner)):
        if idx == 0:
            continue
        m = re.match(r"^\s*([^=|]*?)\s*=\s*(.*)$", part, re.S)
        if m and m.group(1).strip() and re.fullmatch(
            r"[0-9A-Za-z_ ()\-]*", m.group(1).strip()
        ):
            named[m.group(1).strip().lower()] = m.group(2)
        else:
            positional.append(part)
    return named, positional


def extract_template(text, name):
    """Parsed (named, positional) args of the FIRST {{Name ...}}, or None."""
    found = _find_template(text, name)
    if not found:
        return None
    inner, _end = found
    return _parse_template_args(inner)


def extract_item_quote_arg1(text):
    """{{Item Quote}} first argument — positional or named "1". The template
    name is never part of the result."""
    parsed = extract_template(text, "Item Quote")
    if parsed is None:
        return ""
    named, positional = parsed
    val = named.get("1")
    if val is None and positional:
        val = positional[0]
    return val or ""


def _gallery_files(value):
    """File names from an image field: a File: link or a <gallery> block
    (first entry wins — it is the Inventory preview)."""
    if not value:
        return []
    files = []
    gal = re.search(r"<gallery[^>]*>(.*?)</gallery[^>]*>", value, re.S | re.I)
    if gal:
        for line in gal.group(1).split("\n"):
            line = line.strip()
            if not line:
                continue
            name = line.split("|")[0].strip()
            name = re.sub(r"^\s*File\s*:", "", name, flags=re.I)
            if name:
                files.append(name)
        return files
    for m in re.finditer(r"\[\[\s*File\s*:\s*([^\]|]+)", value, re.I):
        files.append(m.group(1).strip())
    if not files:
        v = value.strip()
        v = re.sub(r"^\s*File\s*:", "", v, flags=re.I)
        v = v.split("|")[0].strip()
        if v and " " not in v and "." in v:
            files.append(v)
    return files


def _split_tabber(text):
    """Split every <tabber> block's content into [(label, body), ...]."""
    blocks = re.findall(r"<tabber[^>]*>(.*?)</tabber\s*>", text, re.S | re.I)
    if not blocks:
        return []
    tabs = []
    for raw in blocks:
        _collect_tabs(raw, tabs)
    return tabs


def _collect_tabs(body, tabs):
    # tab separators are exactly "|-|Label=" — a table row "|-..." inside a
    # tab must NOT be treated as a new tab, so require the following "|"
    parts = re.split(r"(?m)^\|-(?=\|)", body)
    for part in parts[1:]:
        if "=" not in part:
            continue
        label, _, content = part.partition("=")
        label = label.strip().lstrip("|").strip()
        if label:
            tabs.append((label, content))


_HEADING_RE = re.compile(r"(?m)^(={2,4})\s*(.+?)\s*\1(?:[^\n]*)$")


def _sections(text):
    """Yield (heading, level, body). A section body extends until the next
    heading of the same or higher level, so "===Current===" bullet lists
    under "==Obtainment==" stay inside the obtainment section."""
    matches = list(_HEADING_RE.finditer(text))
    out = []
    for i, m in enumerate(matches):
        level = len(m.group(1))
        start = m.end()
        end = len(text)
        for m2 in matches[i + 1:]:
            if len(m2.group(1)) <= level:
                end = m2.start()
                break
        out.append((m.group(2).strip(), level, text[start:end]))
    return out


def _strip_tables(body):
    """Remove wiki table blocks entirely (prose only)."""
    out_lines = []
    in_table = False
    depth = 0
    for line in body.split("\n"):
        stripped = line.strip()
        if re.match(r"^\{\|", stripped):
            in_table = True
            depth = 1
            continue
        if in_table:
            if re.match(r"^\|\}", stripped):
                in_table = False
                continue
            continue
        out_lines.append(line)
    return "\n".join(out_lines)


def _section_text(text, names):
    """Cleaned text of the first matching section whose PROSE (outside
    tables) is non-empty. Candidate headings are tried in the given
    priority order; a section that is only one table has empty prose —
    keep looking instead of stopping at raw non-empty text."""
    for want in {_canon(n) for n in names}:
        for heading, _level, body in _sections(text):
            head_key = _canon(heading.split("|")[-1])
            if head_key != want and _canon(heading) != want:
                continue
            prose = clean_wikitext(_strip_tables(body), joiner="; ")
            if not prose:
                continue
            return prose
    return ""


# ------------------------------------------------------------------
# Record builders
# ------------------------------------------------------------------


def _join_boost(value):
    """Boost/effect fields. Bullet lines ("*...") are list items and join
    with "; " (reference: "+800% Luck; -50% Roll Speed"); plain wrapped
    lines join with " " (reference: "+10% Roll Speed. Or +100% During
    Rainy"). Lines starting with "-" are NEVER dropped."""
    if not value:
        return ""
    parts = []
    for line in value.split("\n"):
        raw = line.strip()
        if not raw:
            continue
        is_bullet = raw.startswith("*")
        if is_bullet:
            raw = raw[1:].strip()
        cleaned = clean_wikitext(raw, join_lines=False)
        cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
        if not cleaned:
            continue
        if parts:
            parts.append(("; " if is_bullet else " ") + cleaned)
        else:
            parts.append(cleaned)
    return "".join(parts).strip()


def _recipe_text(value):
    """Recipe list -> "1x Hologrammer, 2x Chromatic, ...".

    Only bullet entries count as recipe lines (the verified dataset treats
    plain-line "recipes" — Darkshader, Hologrammer, Luck Glove, Ragnaröker —
    as no recipe at all: flags stay empty, how_to_get has no Recipe part).
    A literal "N/A" recipe (Snow Rider, X-mas Champion) is no recipe."""
    if not value:
        return ""
    lines = []
    for line in value.split("\n"):
        line = line.strip()
        if not line.startswith("*"):
            continue
        line = line[1:].strip()
        if not line:
            continue
        cleaned = clean_wikitext(line, join_lines=False)
        cleaned = re.sub(r"[ \t]+", " ", cleaned).strip()
        if cleaned:
            lines.append(cleaned)
    joined = ", ".join(lines).strip()
    if joined.lower() in ("n/a", "na", "none", "-"):
        return ""
    return joined


def _gauntlet_record(name, slot, infobox_named, quote, categories):
    """Build one gauntlet/lantern/talisman record from parsed fields."""
    obtainment = clean_wikitext(infobox_named.get("obtainment", ""))
    boost = _join_boost(infobox_named.get("boost", ""))
    effect = _join_boost(infobox_named.get("effect", ""))
    recipe = _recipe_text(infobox_named.get("recipe", ""))
    usage = boost or effect
    description = clean_wikitext(quote or "")
    # No-fallback policy: a record needs at least one confirmed wiki text.
    if not usage and not description:
        return None
    how_to_get = obtainment
    if recipe:
        how_to_get = (
            (obtainment + " | Recipe: " + recipe)
            if obtainment
            else ("Recipe: " + recipe)
        )
    flags = []
    if recipe:
        flags.append("craftable")
    cat_names = [c.replace("Category:", "") for c in (categories or [])]
    if "Event" in cat_names or "Event Items" in cat_names or "Event Gears" in cat_names:
        flags.append("limited")
    record = {
        "name": name,
        "slot": slot,
        "category": slot,
        "limited": "limited" in flags,
        "thumbnail_url": "",
        "usage": usage,
        "how_to_get": how_to_get,
        "description": description,
        "flags": flags,
    }
    raw_info = {}
    if obtainment:
        raw_info["source"] = obtainment
    if boost:
        raw_info["boost(s)"] = boost
    if effect:
        raw_info["effect(s)"] = effect
    if recipe:
        raw_info["recipe"] = recipe
    if raw_info:
        record["raw_info"] = raw_info
    return record


def _page_image_files(wikitext):
    """Image files of a page/tab: the {{Gears Infobox}} image/gallery."""
    parsed = extract_template(wikitext, "Gears Infobox")
    if parsed is None:
        return []
    named, _pos = parsed
    return _gallery_files(named.get("image", ""))


def _match_url_for_file(resolved, f):
    return (
        resolved.get(f)
        or resolved.get(f.replace("_", " "))
        or resolved.get(f.replace(" ", "_"))
    )


def _thumbnail_file_from_url(url):
    """Best-effort wiki file name from a static.wikia thumbnail URL."""
    try:
        path = str(url).split("?")[0].split("#")[0]
        path = re.sub(r"/revision.*$", "", path)
        name = path.rstrip("/").split("/")[-1]
        return urllib.parse.unquote(name) if name else ""
    except Exception:
        return ""


def _resolve_thumbnails(thumb_requests, old_urls=(), timeout=20):
    """Resolve every requested file via imageinfo; keep an old thumbnail
    ONLY when its file still exists on the wiki."""
    all_files = []
    for _rec, files in thumb_requests:
        all_files.extend(files)
    old_files = []
    for url in old_urls:
        f = _thumbnail_file_from_url(url)
        if f:
            old_files.append(f)
    resolved = imageinfo_urls(all_files + old_files, timeout=timeout)
    if resolved is None:
        return  # cannot verify any file this run — leave thumbnails as-is
    old_ok = {}
    for url in old_urls:
        f = _thumbnail_file_from_url(url)
        if f and _match_url_for_file(resolved, f):
            old_ok[url] = True
    for rec, files in thumb_requests:
        url = ""
        for f in files:
            hit = _match_url_for_file(resolved, f)
            if hit:
                url = hit
                break
        if not url and rec.get("thumbnail_url") and rec["thumbnail_url"] in old_ok:
            url = rec["thumbnail_url"]
        rec["thumbnail_url"] = url


def build_gauntlets(progress=None, timeout=20):
    """Rebuild the gauntlets dataset from the live wiki. Returns the data
    dict, or None when the wiki is unavailable (caller keeps offline data)."""
    log = progress or (lambda msg: None)
    slots = {}
    for category, slot in (
        ("Category:Left Gear", "Left Hand"),
        ("Category:Right Gear", "Right Hand"),
    ):
        members = category_members(category, timeout=timeout)
        if members is None:
            log(f"[SolBookData] category unavailable: {category}")
            return None
        for t in members:
            slots[t] = slot
    log(f"[SolBookData] gauntlet pages: {len(slots)}")
    cats = page_categories(list(slots), timeout=timeout)
    if cats is None:
        log("[SolBookData] gauntlet categories unavailable")
        return None
    data = {}
    thumb_requests = []
    for title, slot in slots.items():
        status, text = fetch_page_status(title, timeout=timeout)
        if status == "unavailable":
            log(f"[SolBookData] page unavailable, kept out this run: {title}")
            continue
        if status == "missing":
            continue
        parsed = extract_template(text, "Gears Infobox")
        if parsed is None:
            continue
        named, _pos = parsed
        name = clean_wikitext(named.get("title", "")) or title
        rec = _gauntlet_record(
            name, slot, named, extract_item_quote_arg1(text), cats.get(title) or []
        )
        if not rec:
            log(f"[SolBookData] no confirmed data, dropped: {title}")
            continue
        thumb_requests.append((rec, _page_image_files(text)))
        data[rec["name"]] = rec
    # Lanterns and talismans: tabber tabs on shared pages, slot "Pocket".
    for page in ("Lanterns", "Talismans"):
        status, text = fetch_page_status(page, timeout=timeout)
        if status != "ok":
            log(f"[SolBookData] page unavailable: {page}")
            continue
        for label, body in _split_tabber(text):
            parsed = extract_template(body, "Gears Infobox")
            if parsed is None:
                continue
            named, _pos = parsed
            name = clean_wikitext(named.get("title", "")) or label
            rec = _gauntlet_record(name, "Pocket", named, extract_item_quote_arg1(body), [])
            if not rec:
                log(f"[SolBookData] no confirmed data, dropped tab: {label}")
                continue
            thumb_requests.append((rec, _page_image_files(body)))
            data[rec["name"]] = rec
    _resolve_thumbnails(
        thumb_requests,
        old_urls=[r.get("thumbnail_url", "") for r in data.values()],
        timeout=timeout,
    )
    log(f"[SolBookData] gauntlets built: {len(data)}")
    return data


# ------------------------------------------------------------------
# Items
# ------------------------------------------------------------------

_ROMAN_SUFFIX_RE = re.compile(r"\s+(?:I|II|III|IV|V|VI|VII|VIII|IX|X)$")
_BRACKET_RE = re.compile(r"\s*\([^)]*\)\s*$")


def _plural_forms(src):
    low = src.lower()
    if not src or low.endswith("s"):
        return []
    if low.endswith("y") and len(src) > 2 and src[-2] not in "aeiou":
        return [src[:-1] + "ies"]
    if re.search(r"(s|x|z|ch|sh)$", low):
        return [src + "es"]
    return [src + "s"]


def _page_candidates(name):
    """Resolution candidates for an item name, in order (verified rules):
    the direct page first, then plural forms of the name without
    bracket/roman-numeral suffix ("Godly Potion" -> "Godly Potions"). The
    stripped SINGULAR form itself is never fetched directly — a name like
    "Red Moon Potion II" must not resolve to the separate "Red Moon Potion"
    page; its data lives on the "Red Moon Potions" aggregate tab."""
    base = str(name or "").strip()
    cands = [base]
    cands.extend(_plural_forms(base))
    stripped = _BRACKET_RE.sub("", base).strip()
    bare = _ROMAN_SUFFIX_RE.sub("", stripped).strip()
    for src in (stripped, bare):
        if src and src != base:
            cands.extend(_plural_forms(src))
    seen = set()
    out = []
    for c in cands:
        key = _canon(c)
        if key and key not in seen:
            seen.add(key)
            out.append(c)
    return out


def _match_tab_in_text(name, text):
    """If `text` is an aggregate page (contains <tabber>), return the record
    built from the tab whose label matches `name` — never the first tab
    (e.g. "Abyssal Lantern" redirects to the Lanterns page; taking the first
    infobox would return Wind Fairy Lantern data). Returns None otherwise."""
    if not text or "<tabber" not in text.lower():
        return None
    target = _canon(name)
    for label, body in _split_tabber(text):
        if _canon(label) != target:
            continue
        built = _potion_record_from_text(name, body)
        if built:
            rec, files = built
            return (rec, files)
        return None
    return None


def _potion_record_from_text(name, wikitext):
    """Build an item record from a page/tab that uses {{Potion}},
    {{Gears Infobox}} or {{Item}}. Returns (record, thumbnail_files) or None."""
    quote = extract_item_quote_arg1(wikitext)
    description = clean_wikitext(quote or "")
    usage = ""
    effects = ""
    thumbnail_files = []
    potion = extract_template(wikitext, "Potion")
    gears = extract_template(wikitext, "Gears Infobox")
    item = extract_template(wikitext, "Item")
    category = ""
    if potion is not None:
        named, _pos = potion
        boost = _join_boost(named.get("boost", ""))
        duration = clean_wikitext(named.get("duration", ""))
        effects = clean_wikitext(named.get("effect", ""))
        if effects and effects.lower() in ("none", "n/a", "na", "-"):
            effects = ""
        usage = boost
        if boost and duration:
            usage = f"{boost} — lasts {duration}"
        thumbnail_files = _gallery_files(named.get("image1", "") or named.get("image", ""))
        category = "Potions"
    if gears is not None:
        named, _pos = gears
        boost = _join_boost(named.get("boost", ""))
        effect = _join_boost(named.get("effect", ""))
        if not usage:
            usage = boost or effect
        if not thumbnail_files:
            thumbnail_files = _gallery_files(named.get("image", ""))
    if item is not None:
        named, _pos = item
        effects = effects or clean_wikitext(named.get("effects", ""))
        if not thumbnail_files:
            thumbnail_files = _gallery_files(named.get("image", ""))
    if not usage and not description and not effects:
        return None
    if effects and "(" in effects:
        # parenthesized effect strings are page-layout artifacts
        # ("Rainbow Ice (Effect)(+100% ...)") — the verified dataset drops them
        effects = ""
    # Obtainment section: candidate headings are tried in priority order
    # (verified: "How to Obtain" wins over "Recipe" when both exist); a
    # table-only section has empty prose — keep looking instead of stopping
    # at raw non-empty text.
    how_to_get = _section_text(
        wikitext,
        (
            "Obtainment",
            "How to Obtain",
            "How to obtain",
            "Brewing",
            "Recipe",
            "Requirements",
        ),
    )
    record = {
        "name": name,
        "category": category,
        "thumbnail_url": "",
        "how_to_get": how_to_get,
        "usage": usage,
        "description": description,
        "flags": ["fandom"],
    }
    if effects:
        record["effects"] = effects
    return record, thumbnail_files


def _items_table_rows(wikitext):
    """Parse the 'Items' page 4-column tables
    (Image | Item | Description | Effect) -> {canon_name: {...}}."""
    rows = {}
    if not wikitext:
        return rows
    for m in re.finditer(r"(?m)^\{\|.*?^\|\}", wikitext, re.S):
        table = m.group(0)
        head = table[: table.find("|-", 1) if "|-" in table else len(table)]
        low_head = head.lower()
        if "description" not in low_head or "item" not in low_head:
            continue
        # rows are separated by |- lines; cells start at a line beginning
        # with "|" (or inline "||" separators)
        row_chunks = re.split(r"(?m)^\s*\|-.*$", table)[1:]
        for chunk in row_chunks:
            cells = []
            current = None
            for line in chunk.split("\n"):
                stripped = line.strip()
                if stripped.startswith("|"):
                    first = stripped[1:]
                    inline = first.split("||")
                    current = inline[0]
                    cells.append(current)
                    for extra in inline[1:]:
                        cells.append(extra)
                elif stripped.startswith("!"):
                    continue
                elif current is not None and stripped:
                    cells[-1] = cells[-1] + "\n" + stripped
            if len(cells) < 4:
                continue
            files = []
            for cm in re.finditer(r"\[\[\s*File\s*:\s*([^\]|]+)", cells[0], re.I):
                files.append(cm.group(1).strip())
            name_raw = cells[1]
            nm = re.search(r"\{\{\s*Items\s*\|([^{}]*)\}\}", name_raw)
            if nm:
                name = nm.group(1).split("|")[-1].strip()
            else:
                name = clean_wikitext(name_raw, join_lines=False)
                name = re.sub(r"[ \t]+", " ", name).strip()
            if not name:
                continue
            description = clean_wikitext(cells[2], joiner="; ") if len(cells) > 2 else ""
            usage = clean_wikitext(cells[3], joiner="; ") if len(cells) > 3 else ""
            rows[_canon(name)] = {
                "name": name,
                "description": description,
                "usage": usage,
                "files": files,
            }
    return rows


def build_items(seed_names, progress=None, timeout=20):
    """Rebuild the items dataset from the live wiki.

    seed_names: curated names to refresh (the verified dataset's keys). The
    pipeline refreshes every seed name, adds genuinely new aggregated
    potion/rune tabs, and drops records whose data is confirmed gone.
    Returns (data, uncertain_names, dropped_names); data is None when the
    wiki is unavailable (caller keeps the offline dataset).
    """
    log = progress or (lambda msg: None)
    seed_names = [n for n in (seed_names or []) if n]
    data = {}
    dropped = []
    uncertain = []
    thumb_requests = []

    aggregate_tabs = {}
    for page in AGGREGATED_POTION_PAGES + (RUNES_PAGE,):
        status, text = fetch_page_status(page, timeout=timeout)
        if status == "ok":
            aggregate_tabs[page] = _split_tabber(text)
        else:
            log(f"[SolBookData] aggregate page unavailable: {page}")
            aggregate_tabs[page] = []
    items_rows = {}
    status, text = fetch_page_status(ITEMS_PAGE, timeout=timeout)
    if status == "ok":
        items_rows = _items_table_rows(text)
    else:
        log("[SolBookData] Items page unavailable")

    def match_tab(target):
        for page, tabs in aggregate_tabs.items():
            for label, body in tabs:
                if _canon(label) == target:
                    cat = "Runes" if page == RUNES_PAGE else "Potions"
                    return page, label, body, cat
        return None

    def resolve(name):
        # 1) aggregated potion/rune tab whose label matches the name exactly
        #    (hierarchical potions live there; a name like "Heavenly Potion I"
        #    must match ITS tab, never the page's first tab)
        target = _canon(name)
        tab = match_tab(target)
        # 2) direct page — but never the aggregate pages themselves
        for cand in _page_candidates(name):
            if cand in AGGREGATED_POTION_PAGES or cand == RUNES_PAGE:
                continue
            status, text = fetch_page_status(cand, timeout=timeout)
            if status == "unavailable":
                return ("unavailable", None, None)
            if status == "ok":
                guarded = _match_tab_in_text(name, text)
                if guarded is not None:
                    rec, files = guarded
                    rec["name"] = name
                    return ("ok", rec, files)
                if "<tabber" in text.lower():
                    continue  # aggregate page without a matching tab
                built = _potion_record_from_text(name, text)
                if built:
                    rec, files = built
                    rec["name"] = name
                    return ("ok", rec, files)
        if tab:
            page, _label, body, cat = tab
            built = _potion_record_from_text(name, body)
            if built:
                rec, files = built
                rec["name"] = name
                rec["category"] = rec.get("category") or cat
                return ("ok", rec, files)
        # 3) Items page table rows (easter / dev items)
        row = items_rows.get(target)
        if row:
            rec = {
                "name": name,
                "category": "Special / Misc",
                "thumbnail_url": "",
                "how_to_get": "",
                "usage": row["usage"],
                "description": row["description"],
                "flags": ["fandom"],
            }
            return ("ok", rec, row["files"])
        return ("missing", None, None)

    names = list(seed_names)
    # discovery: aggregated potion/rune tabs that are not curated seeds yet
    existing_canon = {_canon(n) for n in names}
    for _page, tabs in aggregate_tabs.items():
        for label, _body in tabs:
            if _canon(label) and _canon(label) not in existing_canon:
                names.append(label)
                existing_canon.add(_canon(label))
                log(f"[SolBookData] new item from aggregate tabs: {label}")
    for name in names:
        status, rec, files = resolve(name)
        if status == "unavailable":
            uncertain.append(name)
            continue
        if status == "missing":
            if name in seed_names:
                dropped.append(name)
                log(f"[SolBookData] no confirmed wiki data, dropped: {name}")
            continue
        if rec:
            thumb_requests.append((rec, files or []))
            data[name] = rec
    # derive a category for brand-new records that have none (seed records
    # keep their curated category in refresh_items)
    uncategorized = [rec for rec in data.values() if not rec.get("category")]
    if uncategorized:
        cat_map = page_categories([r["name"] for r in uncategorized], timeout=timeout) or {}
        for rec in uncategorized:
            cats = [c.replace("Category:", "").lower() for c in cat_map.get(rec["name"], [])]
            if any("potion" in c for c in cats):
                rec["category"] = "Potions"
            elif any("tool" in c for c in cats):
                rec["category"] = "Tools"
            elif any("chest" in c for c in cats):
                rec["category"] = "Chests"
            elif any("rune" in c for c in cats):
                rec["category"] = "Runes"
            else:
                rec["category"] = "Materials"
    _resolve_thumbnails(thumb_requests, timeout=timeout)
    log(
        f"[SolBookData] items built: {len(data)} (dropped {len(dropped)}, "
        f"uncertain {len(uncertain)})"
    )
    return data, uncertain, dropped


# ------------------------------------------------------------------
# Public refresh API
# ------------------------------------------------------------------

_ITEM_REQUIRED_FIELDS = (
    "name",
    "category",
    "thumbnail_url",
    "how_to_get",
    "usage",
    "description",
    "flags",
)
_GAUNTLET_REQUIRED_FIELDS = (
    "name",
    "slot",
    "category",
    "limited",
    "thumbnail_url",
    "usage",
    "how_to_get",
    "description",
    "flags",
)
_PLACEHOLDER_CANON = {_canon(n) for n in ("???", "test item", "Gear A", "Gear B", "Potion")}


def validate_records(data, kind, seed_count=None):
    """Sanity gate for a freshly built dataset. Returns (ok, reason)."""
    if not isinstance(data, dict) or not data:
        return (False, "empty dataset")
    required = _GAUNTLET_REQUIRED_FIELDS if kind == "gauntlets" else _ITEM_REQUIRED_FIELDS
    for key, rec in data.items():
        if not isinstance(rec, dict):
            return (False, f"non-dict record: {key}")
        for field in required:
            if field not in rec:
                return (False, f"{key}: missing field {field}")
        if _canon(key) in _PLACEHOLDER_CANON or _canon(rec.get("name", "")) in _PLACEHOLDER_CANON:
            return (False, f"placeholder record: {key}")
        if kind == "gauntlets":
            if not rec.get("usage") and not rec.get("description"):
                return (False, f"{key}: no confirmed usage/description")
    if seed_count:
        n = len(data)
        if n < seed_count * 0.6:
            return (False, f"record count {n} far below the verified {seed_count}")
        if n > seed_count * 1.8:
            return (False, f"record count {n} far above the verified {seed_count}")
    return (True, "")


def refresh_gauntlets(current=None, progress=None, timeout=20):
    """Build fresh gauntlet data. `current` is the offline dataset used for
    seed counts and thumbnail fallbacks. Returns the new dict, or None when
    the wiki is unavailable or the result fails validation (never a partial
    wipe)."""
    data = build_gauntlets(progress=progress, timeout=timeout)
    if data is None:
        return None
    # preserve curated record identity fields for known records
    for name, rec in data.items():
        old = (current or {}).get(name)
        if isinstance(old, dict) and old.get("category"):
            rec["category"] = old["category"]
    ok, reason = validate_records(
        data, "gauntlets", seed_count=len(current or {}) or None
    )
    if not ok:
        if progress:
            progress(f"[SolBookData] gauntlet refresh rejected: {reason}")
        return None
    _resolve_thumbnails(
        [(rec, []) for rec in data.values()],
        old_urls=[r.get("thumbnail_url", "") for r in (current or {}).values()]
        + [r.get("thumbnail_url", "") for r in data.values()],
        timeout=timeout,
    )
    if current:
        for name, rec in data.items():
            if not rec.get("thumbnail_url"):
                old = (current.get(name) or {}).get("thumbnail_url") or ""
                if old:
                    rec["thumbnail_url"] = old
    return data


def refresh_items(current=None, progress=None, timeout=20):
    """Build fresh item data. Returns (data, dropped); data is None when the
    wiki is unavailable or validation fails (caller keeps offline data).
    Records that could not be re-confirmed due to network trouble stay as
    they are — offline data is never wiped with emptiness."""
    current = current or {}
    seed_names = list(current.keys())
    data, uncertain, dropped = build_items(seed_names, progress=progress, timeout=timeout)
    if data is None:
        return (None, [])
    for name in uncertain:
        if name in current and name not in data:
            data[name] = current[name]
    # keep curated categories for known records
    for name, rec in data.items():
        old = current.get(name)
        if isinstance(old, dict) and old.get("category"):
            rec["category"] = old["category"]
    ok, reason = validate_records(data, "items", seed_count=len(seed_names) or None)
    if not ok:
        if progress:
            progress(f"[SolBookData] item refresh rejected: {reason}")
        return (None, [])
    _resolve_thumbnails(
        [(rec, []) for rec in data.values()],
        old_urls=[r.get("thumbnail_url", "") for r in current.values()]
        + [r.get("thumbnail_url", "") for r in data.values()],
        timeout=timeout,
    )
    for name, rec in data.items():
        if not rec.get("thumbnail_url"):
            old = (current.get(name) or {}).get("thumbnail_url") or ""
            if old:
                rec["thumbnail_url"] = old
    return (data, dropped)


# ------------------------------------------------------------------
# Live detail views (analog of load_fandom_aura_detail)
# ------------------------------------------------------------------


class _DetailCache:
    """In-memory cache for live detail lookups. Error results are NEVER
    cached (a failed lookup must stay retryable)."""

    def __init__(self):
        self._items = {}
        self._gauntlets = {}


_DETAIL_CACHE = _DetailCache()


def _merge_detail(base, rec):
    result = dict(base or {})
    for key, val in rec.items():
        if val in (None, ""):
            continue
        result[key] = val
    return result


def load_item_detail(name, current=None, timeout=20):
    """Live wiki detail for one item; merges over the offline record."""
    name = str(name or "").strip()
    if not name:
        return {"error": "Empty item name"}
    cached = _DETAIL_CACHE._items.get(name)
    if isinstance(cached, dict) and cached and not cached.get("error"):
        return cached
    built = _resolve_single_item(name, timeout=timeout)
    if built is None:
        return {"error": "Fandom item page unavailable"}
    rec, files = built
    if files:
        resolved = imageinfo_urls(files, timeout=timeout) or {}
        for f in files:
            hit = _match_url_for_file(resolved, f)
            if hit:
                rec["thumbnail_url"] = hit
                break
    result = _merge_detail(current, rec)
    result["fandom_page"] = WIKI_BASE + name.replace(" ", "_")
    result["_metadata_source"] = "fandom"
    _DETAIL_CACHE._items[name] = result
    return result


def _resolve_single_item(name, timeout=20):
    """Resolution for ONE item (detail view): aggregate tab match -> direct
    page -> candidates -> Items table row. Returns (record, files) or None."""
    aggregate_tabs = {}
    for page in AGGREGATED_POTION_PAGES + (RUNES_PAGE,):
        status, text = fetch_page_status(page, timeout=timeout)
        if status == "ok":
            aggregate_tabs[page] = _split_tabber(text)
    target = _canon(name)
    for page, tabs in aggregate_tabs.items():
        for label, body in tabs:
            if _canon(label) != target:
                continue
            built = _potion_record_from_text(name, body)
            if built:
                rec, files = built
                rec["category"] = rec.get("category") or (
                    "Runes" if page == RUNES_PAGE else "Potions"
                )
                return (rec, files)
    for cand in _page_candidates(name):
        if cand in AGGREGATED_POTION_PAGES or cand == RUNES_PAGE:
            continue
        status, text = fetch_page_status(cand, timeout=timeout)
        if status == "unavailable":
            return None
        if status == "ok":
            guarded = _match_tab_in_text(name, text)
            if guarded is not None:
                return guarded
            if "<tabber" in text.lower():
                continue  # aggregate page without a matching tab
            built = _potion_record_from_text(name, text)
            if built:
                return built
    status, text = fetch_page_status(ITEMS_PAGE, timeout=timeout)
    if status == "ok":
        row = _items_table_rows(text).get(target)
        if row:
            rec = {
                "name": name,
                "category": "Special / Misc",
                "thumbnail_url": "",
                "how_to_get": "",
                "usage": row["usage"],
                "description": row["description"],
                "flags": ["fandom"],
            }
            return (rec, row["files"])
    return None


def load_gauntlet_detail(name, current=None, timeout=20):
    """Live wiki detail for one gauntlet/lantern/talisman."""
    name = str(name or "").strip()
    if not name:
        return {"error": "Empty gauntlet name"}
    cached = _DETAIL_CACHE._gauntlets.get(name)
    if isinstance(cached, dict) and cached and not cached.get("error"):
        return cached
    # 1) direct page (real gauntlets/devices). A redirect to the Lanterns /
    #    Talismans aggregate lands in the tab path below — the first tab's
    #    infobox must never be used for a different name.
    status, text = fetch_page_status(name, timeout=timeout)
    if status == "unavailable":
        return {"error": "Fandom gauntlet page unavailable"}
    tabber_text = text if (status == "ok" and "<tabber" in text.lower()) else ""
    if status == "ok" and not tabber_text:
        parsed = extract_template(text, "Gears Infobox")
        if parsed is not None:
            named, _pos = parsed
            cats = []
            cats_raw = _api_json(
                {
                    "action": "query",
                    "prop": "categories",
                    "titles": name,
                    "cllimit": "500",
                    "format": "json",
                    "formatversion": "2",
                },
                timeout=timeout,
            )
            if cats_raw:
                for p in (cats_raw.get("query") or {}).get("pages") or []:
                    if isinstance(p, dict):
                        cats = [c.get("title", "") for c in p.get("categories") or []]
            slot = ""
            if "Category:Left Gear" in cats:
                slot = "Left Hand"
            elif "Category:Right Gear" in cats:
                slot = "Right Hand"
            rec = _gauntlet_record(
                name,
                slot or str((current or {}).get("slot") or ""),
                named,
                extract_item_quote_arg1(text),
                cats,
            )
            if rec:
                files = _page_image_files(text)
                if files:
                    resolved = imageinfo_urls(files, timeout=timeout) or {}
                    for f in files:
                        hit = _match_url_for_file(resolved, f)
                        if hit:
                            rec["thumbnail_url"] = hit
                            break
                result = _merge_detail(current, rec)
                result["fandom_page"] = WIKI_BASE + name.replace(" ", "_")
                result["_metadata_source"] = "fandom"
                _DETAIL_CACHE._gauntlets[name] = result
                return result
    # 2) lantern / talisman tab — including the page the name redirects to
    tab_sources = []
    if tabber_text:
        tab_sources.append(("_redirect", tabber_text))
    for page in ("Lanterns", "Talismans"):
        status, text = fetch_page_status(page, timeout=timeout)
        if status == "ok":
            tab_sources.append((page, text))
    for page, text in tab_sources:
        found = False
        for label, body in _split_tabber(text):
            if _canon(label) != _canon(name):
                continue
            found = True
            parsed = extract_template(body, "Gears Infobox")
            if parsed is None:
                continue
            named, _pos = parsed
            rec = _gauntlet_record(
                name, "Pocket", named, extract_item_quote_arg1(body), []
            )
            if rec:
                files = _page_image_files(body)
                if files:
                    resolved = imageinfo_urls(files, timeout=timeout) or {}
                    for f in files:
                        hit = _match_url_for_file(resolved, f)
                        if hit:
                            rec["thumbnail_url"] = hit
                            break
                result = _merge_detail(current, rec)
                result["fandom_page"] = WIKI_BASE + (
                    name.replace(" ", "_") if page == "_redirect" else page.replace(" ", "_")
                )
                result["_metadata_source"] = "fandom"
                _DETAIL_CACHE._gauntlets[name] = result
                return result
        if found:
            break
    return {"error": "Fandom gauntlet page has no parseable infobox"}
