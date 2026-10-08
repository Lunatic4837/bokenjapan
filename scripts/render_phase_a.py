#!/usr/bin/env python3
"""Phase A mechanical re-render for the homepage and five prefectures.

Rewrites HTML in place for Miyagi, Akita, Fukuoka, Yamaguchi, and Oita
(municipality pages and prefecture indexes) plus the homepage. Other
prefectures are not read or written.

This is the generator for these fixes. Photo-credit hosts are restored
only when the host is exactly source.com or source.net. Listing-site
names (tabelog, tripadvisor, jalan, ikkyu, 一休) are never substring-
replaced, which is what corrupted credits and the Chikugo restaurant name.

Do not invent facility names, descriptions, or photos. A card with no
live destination is left unlinked. A card whose only image is missing
or a NO-PHOTO placeholder inside the published thumb cap is left without
a photo.
"""
from __future__ import annotations

import html
import importlib.util
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
PREFS = ("miyagi", "akita", "fukuoka", "yamaguchi", "oita")
PREF_EN = {
    "miyagi": "Miyagi",
    "akita": "Akita",
    "fukuoka": "Fukuoka",
    "yamaguchi": "Yamaguchi",
    "oita": "Oita",
}
DEAD_PATH = Path(__file__).with_name("phase-a-dead-sources.txt")
PLACEHOLDER_HOSTS = {
    "source.com",
    "www.source.com",
    "source.net",
    "www.source.net",
    "example.com",
    "www.example.com",
    "example.org",
    "www.example.org",
    "placeholder.com",
}
# Image filenames are Akita Fan spot ids already used on these rows.
AKITA_FUN = {
    "senboku-s4.jpg": "https://akita-fun.jp/spots/4",
    "senboku-s547.jpg": "https://akita-fun.jp/spots/547",
    "senboku-s14.jpg": "https://akita-fun.jp/spots/14",
    "senboku-s20.jpg": "https://akita-fun.jp/spots/20",
    "oga-s17.jpg": "https://akita-fun.jp/spots/17",
    "oga-s19.jpg": "https://akita-fun.jp/spots/19",
    "oga-s64.jpg": "https://akita-fun.jp/spots/64",
    "oga-s53.jpg": "https://akita-fun.jp/spots/53",
    "oga-s381.jpg": "https://akita-fun.jp/spots/381",
}
SLUG_NAMES = {
    # slug: (corrupted display token, proper English name, prefecture)
    "yuzawashi": ("Yuzawashi", "Yuzawa", "akita"),
    "shiroishishi": ("Shiroishishi", "Shiroishi", "miyagi"),
    "kamimachi": ("Kamimachi", "Kami", "miyagi"),
    "akamura": ("Akamura", "Aka", "fukuoka"),
    "ashiyacho": ("Ashiyacho", "Ashiya", "fukuoka"),
}
CREDIT_URL_RE = re.compile(r"https?://(?:www\.)?source\.(?:com|net)[^\s\"'<>]*", re.I)
LI_RE = re.compile(r"<li>.*?</li>", re.S)
SECTION_RE = re.compile(r'<section class="place-section">.*?</section>', re.S)
THUMB_RE = re.compile(r'<img\b[^>]*\bclass="thumb"[^>]*>', re.I)
OFFICIAL_RE = re.compile(r'<a href="([^"]*)">Official / source link</a>')
SOURCES_RE = re.compile(r"<!-- sources: (.*?)-->")
H2_RE = re.compile(r"<h2>([^<]+)</h2>")

_spec = importlib.util.spec_from_file_location(
    "build_pages_site", ROOT / "scripts" / "build-pages-site.py"
)
_build = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_build)
section_thumb_cap = _build.section_thumb_cap
COVER_SRC_RE = _build.COVER_SRC_RE
normalize_map_svg = _build.normalize_map_svg


def load_dead(path: Path) -> set[str]:
    """Exact dead URLs.

    Lines that still contain a concatenated pair (space, ・, or a trailing
    fullwidth parenthetical) are kept only as the whole string. Their pieces
    are not marked dead: several of those pieces respond 200 once split.
    """
    exact: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        exact.add(line)
        if " " in line or "・" in line or "（" in line:
            continue
        exact.add(line.rstrip("/"))
    return exact


DEAD = load_dead(DEAD_PATH)


def restore_credit_urls(text: str) -> tuple[str, int]:
    """Put real hosts back. Never touches the words tabelog / 一休 / etc."""
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        url = m.group(0)
        parts = urlparse(url)
        host = parts.netloc.lower()
        path = parts.path or ""
        if host.endswith("source.net"):
            new_host = "www.jalan.net"
        elif "Review-" in path or "/Restaurant_Review" in path or "/Hotel_Review" in path:
            new_host = "www.tripadvisor.com"
        else:
            new_host = "tabelog.com"
        n += 1
        return url.replace(parts.netloc, new_host, 1)

    return CREDIT_URL_RE.sub(repl, text), n


def unescape_doubled(text: str) -> str:
    """Undo doubled entities only. A correct &#39; or &amp; is left alone."""
    while "&amp;amp;" in text:
        text = text.replace("&amp;amp;", "&amp;")
    text = text.replace("&amp;#39;", "'")
    text = text.replace("&amp;#039;", "'")
    text = text.replace("&amp;#x27;", "'")
    text = text.replace("&amp;#X27;", "'")
    text = text.replace("&amp;quot;", "&quot;")
    text = re.sub(r"&amp;39(?=[A-Za-z])", "'", text)
    text = re.sub(r"&amp;amp(?!;)", "&amp;", text)
    return text


def esc_href(url: str) -> str:
    url = html.unescape(url).replace("&amp;", "&")
    return url.replace("&", "&amp;").replace('"', "%22")


def esc_attr(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
    )


def host_of(url: str) -> str:
    return urlparse(url).netloc.lower()


def candidate_urls(raw: str) -> list[str]:
    if not raw:
        return []
    text = html.unescape(raw).strip()
    text = re.sub(r"（[^）]*）\s*$", "", text).strip()
    parts = re.split(r"\s+|・", text)
    out = []
    for part in parts:
        part = part.strip()
        if part.startswith("http://") or part.startswith("https://"):
            out.append(part)
    return out


def usable(raw: str) -> str | None:
    for url in candidate_urls(raw):
        host = host_of(url)
        if host in PLACEHOLDER_HOSTS or host.endswith("source.com") or host.endswith("source.net"):
            continue
        if url in DEAD or url.rstrip("/") in DEAD:
            continue
        return url
    return None


def sources_of(li: str) -> dict[str, str]:
    m = SOURCES_RE.search(li)
    if not m:
        return {}
    out = {}
    for part in m.group(1).split("|"):
        if "=" not in part:
            continue
        key, val = part.split("=", 1)
        out[key.strip()] = val.strip()
    return out


def apply_display_names(text: str, pref: str, town: str | None) -> str:
    for slug, (old, new, slug_pref) in SLUG_NAMES.items():
        if slug_pref != pref:
            continue
        text = text.replace(f'aria-label="{old} (this page)"', f'aria-label="{new} (this page)"')
        text = text.replace(f'aria-label="{old}"', f'aria-label="{new}"')
        text = text.replace(f'data-name="{old}"', f'data-name="{new}"')
        text = text.replace(f"<title>{old}</title>", f"<title>{new}</title>")
        text = text.replace(
            f'aria-label="Location of {old} in ',
            f'aria-label="Location of {new} in ',
        )

        def repl_a(m: re.Match, slug=slug, new=new) -> str:
            href = m.group(1)
            last = href.strip("/").split("/")[-1]
            if last == slug:
                return f'<a href="{href}">{new}</a>'
            return m.group(0)

        text = re.sub(rf'<a href="([^"]+)">{re.escape(old)}</a>', repl_a, text)
        if town == slug:
            text = text.replace(
                f'<h1 class="page-title">{old}</h1>',
                f'<h1 class="page-title">{new}</h1>',
            )
            text = text.replace(
                f'<p class="page-sub">{old} · ',
                f'<p class="page-sub">{new} · ',
            )
            text = text.replace(f"/ {old}</p>", f"/ {new}</p>")
            text = text.replace(
                f'<p class="locator-label">{old}</p>',
                f'<p class="locator-label">{new}</p>',
            )
            for kind in ("City Hall", "Town Hall", "Village Hall"):
                text = text.replace(f">{old} {kind}<", f">{new} {kind}<")
    if town == "osakishi":
        text = text.replace(
            '<p class="page-sub">大崎市 · Miyagi</p>',
            '<p class="page-sub">Osaki · Miyagi</p>',
        )
    return text


def insert_social_meta(text: str, canonical: str, description: str, og_title: str) -> str:
    block = ""
    if 'rel="canonical"' not in text:
        block += f'  <link rel="canonical" href="{canonical}">\n'
    if 'name="description"' not in text:
        block += f'  <meta name="description" content="{esc_attr(description)}">\n'
    if 'property="og:title"' not in text:
        block += (
            '  <meta property="og:type" content="website">\n'
            f'  <meta property="og:url" content="{canonical}">\n'
            f'  <meta property="og:title" content="{esc_attr(og_title)}">\n'
            f'  <meta property="og:description" content="{esc_attr(description)}">\n'
            '  <meta property="og:image" content="https://bokenjapan.com/og.png">\n'
        )
    if not block:
        return text
    needle = '  <link rel="stylesheet"'
    if needle not in text:
        return text
    return text.replace(needle, block + needle, 1)


def description_for(text: str, pref: str) -> tuple[str, str]:
    title_m = re.search(r"<title>([^<]*)</title>", text)
    og_title = title_m.group(1).strip() if title_m else "BokenJapan"
    h1_m = re.search(r'<h1 class="page-title">([^<]*)</h1>', text)
    h1 = h1_m.group(1).strip() if h1_m else PREF_EN[pref]
    sub_m = re.search(r'<p class="page-sub">([^<]*)</p>', text)
    sub = sub_m.group(1).strip() if sub_m else ""
    if "Pick a municipality" in sub:
        description = sub
    else:
        description = f"{h1}, {PREF_EN[pref]}. Places to stay, eat, and visit."
    return description, og_title


def reorder_sections(text: str) -> str:
    secs = list(SECTION_RE.finditer(text))
    if len(secs) < 2:
        return text

    def title_of(blob: str) -> str:
        m = H2_RE.search(blob)
        return m.group(1) if m else ""

    items = [(i, title_of(s.group(0)), s.group(0)) for i, s in enumerate(secs)]

    def key(item: tuple[int, str, str]) -> tuple[int, int]:
        title = item[1]
        rank = 0 if title == "Stay" else 1 if title == "Dining" else 2
        return (rank, item[0])

    ordered = sorted(items, key=key)
    if [item[2] for item in ordered] == [item[2] for item in items]:
        return text
    start, end = secs[0].start(), secs[-1].end()
    return text[:start] + "".join(item[2] for item in ordered) + text[end:]


def dedupe_ranked(lis: list[str], section: str, stats: dict) -> list[str]:
    primary = "tabelog_url" if section == "Dining" else "ikkyu_url"
    secondary = "ta_url" if section == "Dining" else "jalan_url"
    seen_primary: set[str] = set()
    seen_secondary: set[str] = set()
    kept = []
    for li in lis:
        src = sources_of(li)
        prim = src.get(primary) or ""
        sec = src.get(secondary) or ""
        if prim:
            if prim in seen_primary:
                stats["dupes_removed"] += 1
                continue
            seen_primary.add(prim)
            if sec:
                seen_secondary.add(sec)
        elif sec:
            if sec in seen_secondary:
                stats["dupes_removed"] += 1
                continue
            seen_secondary.add(sec)
        kept.append(li)
    return kept


def renumber(lis: list[str]) -> list[str]:
    out = []
    for i, li in enumerate(lis, 1):
        out.append(re.sub(r"#\d+ ranked in ", f"#{i} ranked in ", li, count=1))
    return out


def restore_ikkyu(li: str, stats: dict, page: str) -> str:
    if '<p class="place-name"></p>' not in li:
        return li
    alt_m = re.search(r'alt="([^"]*)"', li)
    alt = alt_m.group(1) if alt_m else ""
    ta = sources_of(li).get("ta_url", "")
    if alt not in ("一休", "Ikkyu") and "Reviews-Ikkyu" not in ta:
        return li
    li = li.replace('<p class="place-name"></p>', '<p class="place-name">一休</p>', 1)
    stats["names_restored"].append({"page": page, "alt": alt})
    if '<p class="place-blurb"></p>' in li and (alt == "Ikkyu" or "Reviews-Ikkyu" in ta):
        li = li.replace('<p class="place-blurb"></p>', '<p class="place-blurb">Ikkyu</p>', 1)
    return li


def media_file(page: Path, src: str) -> Path:
    return (page.parent / src).resolve()


def image_kind(path: Path) -> str:
    if not path.is_file():
        return "missing"
    try:
        size = path.stat().st_size
        magic = path.read_bytes()[:6]
    except OSError:
        return "missing"
    if size == 3027 and magic.startswith(b"GIF"):
        return "placeholder"
    return "real"


def place_name(li: str) -> str:
    m = re.search(r'<p class="place-name">(.*?)</p>', li)
    return m.group(1) if m else ""


def drop_bad_thumb(
    li: str,
    section: str,
    page: Path,
    cover_names: set[str],
    bucket: set[str],
    stats: dict,
) -> str:
    m = THUMB_RE.search(li)
    if not m:
        return li
    tag = m.group(0)
    sm = re.search(r'\bsrc="([^"]+)"', tag)
    if not sm:
        return li
    src = sm.group(1)
    name = Path(src.split("?", 1)[0]).name
    kind = image_kind(media_file(page, src.split("?", 1)[0]))
    cap = section_thumb_cap(section)
    consumes_slot = name not in cover_names and name not in bucket
    in_window = (not consumes_slot) or len(bucket) < cap
    # Past the published cap the slim build omits the tag. Leave it.
    if consumes_slot and len(bucket) >= cap:
        return li
    if kind == "real":
        if consumes_slot and len(bucket) < cap:
            bucket.add(name)
        return li
    if not in_window:
        return li
    # Missing or placeholder that the slim build would publish.
    stats["images_removed"].append(
        {
            "page": str(page.relative_to(ROOT)),
            "section": section,
            "name": place_name(li),
            "file": name,
            "reason": kind,
        }
    )
    return li[: m.start()] + li[m.end() :]


def choose_href(li: str, section: str, official: str | None, filename: str | None) -> str | None:
    live = usable(official) if official else None
    if live:
        return live
    src = sources_of(li)
    if section == "Dining":
        for key in ("tabelog_url", "ta_url"):
            if src.get(key):
                return src[key]
    elif section == "Stay":
        for key in ("ikkyu_url", "jalan_url"):
            if src.get(key):
                return src[key]
    else:
        for key in ("tabelog_url", "ta_url", "ikkyu_url", "jalan_url"):
            if src.get(key):
                return src[key]
    credit = re.search(r"<!-- photo-credit:.*?-->", li)
    if credit:
        um = re.search(r"https?://[^\s>]+", credit.group(0))
        if um:
            live = usable(um.group(0))
            if live:
                return live
    if filename and filename in AKITA_FUN:
        return AKITA_FUN[filename]
    return None


def link_card(li: str, section: str, page: str, stats: dict) -> str:
    if re.search(r'<a\b[^>]*>\s*<p class="place-name">', li):
        return li
    official_m = OFFICIAL_RE.search(li)
    official = official_m.group(1) if official_m else None
    if official_m:
        stats["official_removed"] += 1
    li = re.sub(r"\s*·\s*<a href=\"[^\"]*\">Official / source link</a>", "", li)
    li = OFFICIAL_RE.sub("", li)
    li = re.sub(r"<p class=\"place-meta\">\s*(?:·\s*)?</p>", "", li)
    li = re.sub(r"(<p class=\"place-meta\">[^<]*?)\s*·\s*</p>", r"\1</p>", li)
    thumb = THUMB_RE.search(li)
    filename = None
    if thumb:
        sm = re.search(r"media/([^\"?#]+)", thumb.group(0))
        if sm:
            filename = Path(sm.group(1)).name
    href = choose_href(li, section, official, filename)
    if not href:
        rejected = official or ""
        stats["unlinked"].append(
            {
                "page": page,
                "section": section,
                "name": place_name(li),
                "rejected": rejected[:180],
            }
        )
        return li
    img = thumb.group(0) if thumb else ""
    body = li
    if thumb:
        body = li[: thumb.start()] + li[thumb.end() :]
    name_m = re.search(r"<p class=\"place-name\">.*?</p>", body)
    if not name_m:
        return li
    wrapped = (
        body[: name_m.start()]
        + f'<a href="{esc_href(href)}">'
        + name_m.group(0)
        + img
        + "</a>"
        + body[name_m.end() :]
    )
    stats["cards_linked"] += 1
    return wrapped


def process_section(section_html: str, page: Path, cover_names: set[str], stats: dict) -> str:
    h = H2_RE.search(section_html)
    title = h.group(1) if h else ""
    m = re.search(r'(<ul class="place-list">)(.*?)(</ul>)', section_html, re.S)
    if not m:
        return section_html
    lis = LI_RE.findall(m.group(2))
    if title in ("Dining", "Stay"):
        lis = renumber(dedupe_ranked(lis, title, stats))
    bucket: set[str] = set()
    rel = str(page.relative_to(ROOT))
    out = []
    for li in lis:
        li = restore_ikkyu(li, stats, rel)
        li = drop_bad_thumb(li, title, page, cover_names, bucket, stats)
        li = link_card(li, title, rel, stats)
        out.append(li)
    return section_html[: m.start(2)] + "".join(out) + section_html[m.end(2) :]


def process_place_page(text: str, page: Path, stats: dict) -> str:
    text = reorder_sections(text)
    cover_names = {Path(m.group(1)).name for m in COVER_SRC_RE.finditer(text)}

    def repl(m: re.Match) -> str:
        return process_section(m.group(0), page, cover_names, stats)

    return SECTION_RE.sub(repl, text)


def strip_shared_chrome(text: str) -> str:
    text = re.sub(r"\n[ \t]*Note: local unpublished draft only;[^\n]*", "", text)
    text = re.sub(
        r"\n\s*<p>Pages are compiled from publicly available local sources\.</p>",
        "",
        text,
    )
    text = re.sub(r"\n\s*<p class=\"map-credit\">.*?</p>", "", text, flags=re.S)
    return text


def process_home(text: str) -> str:
    text = strip_shared_chrome(text)
    if 'rel="canonical"' not in text:
        text = text.replace(
            '  <meta name="viewport" content="width=device-width, initial-scale=1">\n',
            '  <meta name="viewport" content="width=device-width, initial-scale=1">\n'
            '  <link rel="canonical" href="https://bokenjapan.com/">\n',
            1,
        )
    if 'href="/privacy.html"' not in text and 'href="privacy.html"' not in text:
        text = text.replace(
            '<p class="foot-disclaimer">',
            '<nav class="foot-legal" aria-label="Legal">'
            '<a href="/privacy.html">Privacy</a> · <a href="/terms.html">Terms</a>'
            "</nav>\n    <p class=\"foot-disclaimer\">",
            1,
        )
    return text


def process_pref_file(text: str, page: Path, stats: dict) -> str:
    rel = page.relative_to(ROOT)
    pref = rel.parts[0]
    town = rel.parts[1] if len(rel.parts) == 3 else None
    text, n = restore_credit_urls(text)
    stats["credits_restored"] += n
    text = unescape_doubled(text)
    text = strip_shared_chrome(text)
    text = apply_display_names(text, pref, town)
    if town:
        canonical = f"https://bokenjapan.com/{pref}/{town}/"
    else:
        canonical = f"https://bokenjapan.com/{pref}/"
    description, og_title = description_for(text, pref)
    text = insert_social_meta(text, canonical, description, og_title)
    text = process_place_page(text, page, stats)
    return text


def iter_targets() -> list[Path]:
    pages = [ROOT / "index.html"]
    for pref in PREFS:
        pages.append(ROOT / pref / "index.html")
        pages.extend(sorted((ROOT / pref).glob("*/index.html")))
    return pages


def self_test() -> None:
    sample = (
        "keep https://tabelog.com/fukuoka/A4008/A400804/40004963/ and 一休 "
        "https://source.com/fukuoka/A4008/A400804/40004963/ "
        "https://www.source.com/Restaurant_Review-g1-d2-Reviews-X.html "
        "https://www.source.net/yad390720/"
    )
    out, n = restore_credit_urls(sample)
    assert n == 3, n
    assert out.count("https://tabelog.com/fukuoka/A4008/A400804/40004963/") == 2
    assert "https://www.tripadvisor.com/Restaurant_Review-g1-d2-Reviews-X.html" in out
    assert "https://www.jalan.net/yad390720/" in out
    assert "一休" in out
    assert "source.com" not in out and "source.net" not in out
    fixed = unescape_doubled(
        "REMMY&amp;39S Muffin&amp;ampDeli fan&amp;#39;s &#x27; stay &amp; ok"
    )
    assert fixed == "REMMY'S Muffin&amp;Deli fan's &#x27; stay &amp; ok", fixed
    svg = (
        '<a href="akita/" data-name="Akita"></a>'
        '<a href="noshiro/"></a>'
        '<a href="./" class="is-here" data-name="Akita"></a>'
        '<a href="../akita/"></a>'
    )
    norm = normalize_map_svg(svg, "akita", "akita")
    hrefs = re.findall(r'href="([^"]+)"', norm)
    assert hrefs.count("/akita/akita/") == 3, hrefs
    assert "/akita/noshiro/" in hrefs
    assert "/akita/" not in hrefs
    assert "is-here" not in norm
    dead_sample = usable(
        "https://oyustonecircles.explorekazuno.jp/ https://www.city.kazuno.lg.jp/soshiki/shogaigakushu/oyustonecirclekan/gyomu/1/1/1/2187.html"
    )
    assert dead_sample == "https://oyustonecircles.explorekazuno.jp/", dead_sample
    assert usable("http://www.osarizawa.jp/amusement/sports.php http://www.ink.or.jp/~mineland/ski/newpage3.htm") is None
    assert usable("https://sato-no-tabi.jp/news/20260511spot-asaji/（豊後大野市観光協会）") == "https://sato-no-tabi.jp/news/20260511spot-asaji/"


def main() -> int:
    self_test()
    stats = {
        "credits_restored": 0,
        "dupes_removed": 0,
        "official_removed": 0,
        "cards_linked": 0,
        "names_restored": [],
        "images_removed": [],
        "unlinked": [],
        "pages": 0,
    }
    for page in iter_targets():
        original = page.read_text(encoding="utf-8")
        if page == ROOT / "index.html":
            updated = process_home(original)
        else:
            updated = process_pref_file(original, page, stats)
        if "source.com" in updated or "source.net" in updated:
            raise SystemExit(f"placeholder host survived in {page}")
        if updated != original:
            page.write_text(updated, encoding="utf-8")
        stats["pages"] += 1
        if stats["pages"] % 20 == 0:
            print(f"processed {stats['pages']}", flush=True)
    summary = {
        "pages": stats["pages"],
        "credits_restored": stats["credits_restored"],
        "dupes_removed": stats["dupes_removed"],
        "official_removed": stats["official_removed"],
        "cards_linked": stats["cards_linked"],
        "names_restored": len(stats["names_restored"]),
        "images_removed": len(stats["images_removed"]),
        "unlinked": len(stats["unlinked"]),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    Path("/tmp/phase-a-render-stats.json").write_text(
        json.dumps(stats, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
