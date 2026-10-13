#!/usr/bin/env python3
"""Apply Aomori CoS FAIL remediations to all Hokkaido municipality pages."""
from __future__ import annotations
import html as htmlmod
import json
import math
import re
import shutil
from collections import Counter
from pathlib import Path

ROOT = Path("/workspace/p1/bokenjapan-cutover")
HUBS_PATH = Path("/workspace/p1/data/catalog-uplift/hubs/hokkaido-hub-codes.json")
PREF = "hokkaido"
PREF_EN = "Hokkaido"
BASE = "https://bokenjapan.com"

# JIS Northern-Territories → romanized slugs (no jis-code slugs)
NT_RENAME = {
    "jis01695": ("shikotan", "Shikotan"),
    "jis01696": ("tomari", "Tomari"),  # 泊村 (hub had wrong 歯舞/Haku)
    "jis01697": ("ruyobetsu", "Ruyobetsu"),
    "jis01698": ("ryubetsu", "Ryubetsu"),
    "jis01699": ("shana", "Shana"),
    "jis01700": ("shibetoro", "Shibetoro"),
}

# Romaji token → English for Sight names (word-boundary, title-ish input)
ROMAJI_MAP = [
    (r"\bRitsu\b", "Prefectural"),
    (r"\bShiritsu\b", "City"),
    (r"\bChoitsu\b", "Town"),
    (r"\bSonitsu\b", "Village"),
    (r"\bHakubutsukan\b", "Museum"),
    (r"\bBijutsukan\b", "Art Museum"),
    (r"\bKagakukan\b", "Science Museum"),
    (r"\bShiryokan\b", "Museum"),
    (r"\bBunkan\b", "Annex"),
    (r"\bKaizuka\b", "Shell Mound"),
    (r"\bKinenkan\b", "Memorial Hall"),
    (r"\bKinenkoen\b", "Memorial Park"),
    (r"\bKinen\b", "Memorial"),
    (r"\bKoen\b", "Park"),
    (r"\bKouen\b", "Park"),
    (r"\bJinja\b", "Shrine"),
    (r"\bJingu\b", "Shrine"),
    (r"\bHachimangu\b", "Hachiman Shrine"),
    (r"\bTera\b", "Temple"),
    (r"\bJi\b", "Temple"),
    (r"\bOnsen\b", "Onsen"),
    (r"\bMizumi\b", "Lake"),
    (r"\bKohan\b", "Lakeside"),
    (r"\bKaigan\b", "Coast"),
    (r"\bHama\b", "Beach"),
    (r"\bSaki\b", "Cape"),
    (r"\bMisaki\b", "Cape"),
    (r"\bYama\b", "Mountain"),
    (r"\bDake\b", "Mount"),
    (r"\bTake\b", "Mount"),
    (r"\bGawa\b", "River"),
    (r"\bKawa\b", "River"),
    (r"\bOhashi\b", "Bridge"),
    (r"\bHashi\b", "Bridge"),
    (r"\bBashi\b", "Bridge"),
    (r"\bTodai\b", "Lighthouse"),
    (r"\bTaikan\b", "Observatory"),
    (r"\bTenbodai\b", "Observatory"),
    (r"\bTenbosho\b", "Observatory"),
    (r"\bDobutsuen\b", "Zoo"),
    (r"\bSuizokukan\b", "Aquarium"),
    (r"\bBotanical Garden\b", "Botanical Garden"),
    (r"\bShokubutsuen\b", "Botanical Garden"),
    (r"\bIchiba\b", "Market"),
    (r"\bMarket\b", "Market"),
    (r"\bJoshi\b", "Castle Site"),
    (r"\bJo\b", "Castle"),
    (r"\bAto\b", "Historic Site"),
    (r"\bIseki\b", "Historic Site"),
    (r"\bFurusato\b", "Hometown"),
    (r"\bKanko\b", "Tourism"),
    (r"\bCenter\b", "Center"),
    (r"\bKan\b", "Hall"),
]

JA_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
MIDDOT_RE = re.compile(r"[・\u30fb]")
SEC_RE = re.compile(
    r'(<section class="place-section"><h2>(Stay|Dining|Sights)</h2>.*?</section>)',
    re.S,
)


def esc(s: str) -> str:
    return htmlmod.escape(s or "", quote=True)


def en_sight_name(name: str) -> str:
    s = htmlmod.unescape(name or "").strip()
    s = MIDDOT_RE.sub(" ", s)
    s = re.sub(r"\s+", " ", s)
    for pat, repl in ROMAJI_MAP:
        s = re.sub(pat, repl, s, flags=re.I)
    # Collapse "Hall Hall" etc.
    s = re.sub(r"\b(Hall|Museum|Park|Shrine|Temple)\s+\1\b", r"\1", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip()
    # Title-case words that are all-lowercase ascii
    parts = []
    for w in s.split(" "):
        if w.isascii() and w.islower() and len(w) > 2:
            parts.append(w.capitalize())
        else:
            parts.append(w)
    return " ".join(parts)


def clean_en(s: str) -> str:
    s = htmlmod.unescape(s or "")
    s = MIDDOT_RE.sub(" / ", s)
    s = s.replace("／", " / ")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fix_credit_url(credit: str, sources: str, href: str) -> str:
    """Rewrite placeholder hosts; prefer real listing URL from sources/href."""
    credit = credit or ""
    # Direct host fixes from neutralize_credit bug
    credit = credit.replace("https://source.com/", "https://tabelog.com/")
    credit = credit.replace("http://source.com/", "https://tabelog.com/")
    credit = credit.replace("https://www.source.net/", "https://www.jalan.net/")
    credit = credit.replace("http://www.source.net/", "https://www.jalan.net/")
    credit = credit.replace("https://source.net/", "https://www.jalan.net/")
    if "source.com" in credit.lower() or "source.net" in credit.lower():
        # rebuild from sources / href
        url = ""
        if sources:
            for part in sources.split("|"):
                part = part.strip()
                if "=" in part:
                    k, v = part.split("=", 1)
                    if v.startswith("http") and "source." not in v:
                        url = v.strip()
                        break
        if not url and href.startswith("http") and "source." not in href:
            url = href
        if url:
            credit = f"source · Source {url}"
    # Ensure Source URL present when we have href
    if href.startswith("http") and "Source http" not in credit and "source." not in href:
        if not credit or credit.strip() == "source":
            credit = f"source · Source {href}"
        elif "Source " not in credit:
            credit = f"{credit} · Source {href}"
    return credit


def map_centroids(index_html: str) -> dict[str, tuple[float, float]]:
    """slug → (x,y) from pref map path data (viewBox space)."""
    out = {}
    for m in re.finditer(
        r'<a href="([^"]+)"[^>]*data-name="([^"]+)"[^>]*>(.*?)</a>',
        index_html,
        re.S,
    ):
        href, _name, inner = m.group(1), m.group(2), m.group(3)
        href = href.strip()
        if href in ("./", ".", ""):
            continue
        slug = href.strip("/").split("/")[-1]
        if not slug or slug.startswith("jis"):
            # still record jis for rename distance later
            pass
        nums = [float(x) for x in re.findall(r"[-+]?\d*\.\d+|\d+", inner[:400])]
        if len(nums) >= 2:
            # use average of first chunk of coords as rough centroid
            xs = nums[0::2][:40]
            ys = nums[1::2][:40]
            if xs and ys:
                out[slug] = (sum(xs) / len(xs), sum(ys) / len(ys))
    return out


def nearest_stay_slug(slug: str, centroids: dict, stay_slugs: set[str]) -> str | None:
    if slug not in centroids:
        return None
    x0, y0 = centroids[slug]
    best, bd = None, 1e18
    for s in stay_slugs:
        if s == slug or s not in centroids:
            continue
        x, y = centroids[s]
        d = (x - x0) ** 2 + (y - y0) ** 2
        if d < bd:
            bd, best = d, s
    return best


def ensure_head(html: str, slug: str, muni_en: str) -> str:
    title = f"{muni_en} · {PREF_EN} · BokenJapan"
    canon = f"{BASE}/{PREF}/{slug}/"
    desc = f"{muni_en}, {PREF_EN}. Places to stay, eat, and visit."
    # title
    html = re.sub(r"<title>.*?</title>", f"<title>{esc(title)}</title>", html, count=1, flags=re.S)
    # strip existing canonical / description / og we manage
    html = re.sub(r'\s*<link rel="canonical"[^>]*>', "", html)
    html = re.sub(r'\s*<meta name="description"[^>]*>', "", html)
    html = re.sub(r'\s*<meta property="og:[^"]+"[^>]*>', "", html)
    block = (
        f'\n  <link rel="canonical" href="{esc(canon)}">'
        f'\n  <meta name="description" content="{esc(desc)}">'
        f'\n  <meta property="og:type" content="website">'
        f'\n  <meta property="og:url" content="{esc(canon)}">'
        f'\n  <meta property="og:title" content="{esc(title)}">'
        f'\n  <meta property="og:description" content="{esc(desc)}">'
        f'\n  <meta property="og:image" content="https://img.bokenjapan.com/og.png">'
    )
    html = re.sub(r"(<title>.*?</title>)", r"\1" + block, html, count=1, flags=re.S)
    return html


def fix_dining_stay_li(li: str) -> str:
    href_m = re.search(r'<a href="([^"]+)"', li)
    href = href_m.group(1) if href_m else ""
    src_m = re.search(r"<!-- sources: (.*?) -->", li)
    sources = src_m.group(1) if src_m else ""
    # blurbs / descs: middot + strip JA from EN fields
    def fix_p(m):
        cls, body = m.group(1), m.group(2)
        if cls in ("place-blurb", "place-desc"):
            body2 = clean_en(body)
            if JA_RE.search(body2):
                # drop JA from EN field — keep ascii/latin bits
                body2 = JA_RE.sub("", body2)
                body2 = re.sub(r"\s+", " ", body2).strip(" -·/")
            return f'<p class="{cls}">{esc(htmlmod.unescape(body2)) if cls != "place-name" else body2}</p>'
        return m.group(0)

    # simpler: only blurb/desc
    def repl_en(m):
        cls, body = m.group(1), m.group(2)
        body2 = clean_en(body)
        if JA_RE.search(body2):
            body2 = re.sub(r"[\u3040-\u30ff\u4e00-\u9fff]+", "", body2)
            body2 = re.sub(r"\s+", " ", body2).strip(" -·/,")
        return f'<p class="{cls}">{htmlmod.escape(body2, quote=False)}</p>'

    li = re.sub(r'<p class="(place-blurb|place-desc)">(.*?)</p>', repl_en, li)

    cred_m = re.search(r"<!-- photo-credit: (.*?) -->", li)
    if cred_m:
        new_c = fix_credit_url(cred_m.group(1), sources, href)
        li = li.replace(cred_m.group(0), f"<!-- photo-credit: {new_c} -->", 1)
    elif href.startswith("http"):
        # insert credit before sources or at end of li
        cred = fix_credit_url("", sources, href)
        if "<!-- sources:" in li:
            li = li.replace("<!-- sources:", f"<!-- photo-credit: {cred} --><!-- sources:", 1)
        else:
            li = li.replace("</li>", f"<!-- photo-credit: {cred} --></li>", 1)
    # alt text
    name_m = re.search(r'<p class="place-name">(.*?)</p>', li)
    name = htmlmod.unescape(name_m.group(1)) if name_m else ""
    def alt_fix(m):
        tag = m.group(0)
        if name and (not re.search(r'alt="[^"]+"', tag) or re.search(r'alt=""', tag)):
            if 'alt="' in tag:
                tag = re.sub(r'alt="[^"]*"', f'alt="{esc(name)}"', tag, count=1)
            else:
                tag = tag.replace("<img ", f'<img alt="{esc(name)}" ', 1)
        return tag
    li = re.sub(r"<img\b[^>]*>", alt_fix, li)
    return li


def rewrite_sight_li(li: str, muni_en: str) -> str:
    name_m = re.search(r'<p class="place-name">(.*?)</p>', li)
    raw_name = htmlmod.unescape(name_m.group(1)) if name_m else "Sight"
    name = en_sight_name(raw_name)

    blurb_m = re.search(r'<p class="place-blurb">(.*?)</p>', li)
    blurb = clean_en(blurb_m.group(1)) if blurb_m else ""
    if JA_RE.search(blurb):
        blurb = JA_RE.sub("", blurb)
        blurb = re.sub(r"\s+", " ", blurb).strip()

    meta_m = re.search(r'<p class="place-meta">(.*?)</p>', li, re.S)
    meta_raw = meta_m.group(1) if meta_m else f"{muni_en}, {PREF_EN}"
    off = re.search(r'<a href="([^"]+)">\s*Official\s*/\s*source\s*link\s*</a>', meta_raw, re.I)
    href = off.group(1) if off else ""
    # strip official chrome from meta
    meta = re.sub(
        r'(?:\s*·\s*)?<a href="[^"]+">\s*Official\s*/\s*source\s*link\s*</a>',
        "",
        meta_raw,
        flags=re.I,
    )
    meta = re.sub(r"\s*·\s*$", "", meta).strip()
    meta = re.sub(r"\s+", " ", meta)
    if not meta:
        meta = f"{muni_en}, {PREF_EN}"

    cred_m = re.search(r"<!-- photo-credit: (.*?) -->", li)
    credit = cred_m.group(1) if cred_m else ""
    # fallback click target: visit-hokkaido / credit Source URL
    if not href and credit:
        sm = re.search(r"Source\s+(https?://\S+)", credit)
        if sm:
            href = sm.group(1)
    if not href:
        # last resort: visit-hokkaido from image id
        im = re.search(r'src="([^"]+)"', li)
        if im:
            mid = re.search(r"-s(\d+)\.", im.group(1))
            if mid:
                href = f"https://www.visit-hokkaido.jp/spot/detail_{mid.group(1)}.html"

    img_m = re.search(r"<img\b[^>]*>", li)
    img = img_m.group(0) if img_m else ""
    if img:
        if re.search(r'alt="[^"]*"', img):
            img = re.sub(r'alt="[^"]*"', f'alt="{esc(name)}"', img, count=1)
        else:
            img = img.replace("<img ", f'<img alt="{esc(name)}" ', 1)
        if "loading=" not in img:
            img = img.replace("<img ", '<img loading="lazy" ', 1)

    # explanation → place-desc
    desc_m = re.search(r'<p class="place-desc">(.*?)</p>', li)
    if desc_m:
        desc = clean_en(desc_m.group(1))
    elif blurb and (" — " in blurb or len(blurb.split()) >= 6):
        desc = blurb
        blurb = name  # Ohira pattern: blurb mirrors EN name
    elif blurb:
        desc = blurb if len(blurb.split()) >= 4 else f"{blurb} — a place to visit in {muni_en}, {PREF_EN}."
        blurb = name
    else:
        desc = f"{name} — a place to visit in {muni_en}, {PREF_EN}."
        blurb = name
    if JA_RE.search(desc):
        desc = JA_RE.sub("", desc)
        desc = re.sub(r"\s+", " ", desc).strip(" -·/")
        if len(desc.split()) < 4:
            desc = f"{name} — a place to visit in {muni_en}, {PREF_EN}."

    # rebuild li
    name_img = f'<p class="place-name">{esc(name)}</p>{img}'
    if href and href.startswith("http"):
        name_img = f'<a href="{esc(href)}">{name_img}</a>'
    parts = [
        "<li>",
        name_img,
        f'<p class="place-blurb">{esc(blurb)}</p>',
        f'<p class="place-meta">{meta}</p>',  # meta may contain only text now
        f'<p class="place-desc">{esc(desc)}</p>',
    ]
    if credit:
        # keep real credits (visit-hokkaido etc.); don't neutralize URLs
        parts.append(f"<!-- photo-credit: {credit} -->")
    if href:
        parts.append(f"<!-- desc-source: {esc(href)} -->")
    parts.append("</li>")
    return "".join(parts)


def dedupe_lis(lis: list[str]) -> list[str]:
    seen = set()
    out = []
    for li in lis:
        nm = re.search(r'<p class="place-name">(.*?)</p>', li)
        key = htmlmod.unescape(nm.group(1)).strip().lower() if nm else li[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(li)
    return out


def rerank_meta(lis: list[str], muni_en: str) -> list[str]:
    out = []
    for i, li in enumerate(lis, 1):
        li2 = re.sub(
            r'<p class="place-meta">#\d+ ranked in [^<]+</p>',
            f'<p class="place-meta">#{i} ranked in {esc(muni_en)}</p>',
            li,
            count=1,
        )
        out.append(li2)
    return out


def section_html(title: str, lis: list[str]) -> str:
    return (
        f'<section class="place-section"><h2>{title}</h2>'
        f'<ul class="place-list">{"".join(lis)}</ul></section>'
    )


def stay_none_html(muni_en: str, near_slug: str, near_en: str) -> str:
    return (
        f'<section class="place-section"><h2>Stay</h2>'
        f'<p class="stay-none">No listed places to stay in {esc(muni_en)} — nearest options in '
        f'<a href="/{PREF}/{near_slug}/">{esc(near_en)}</a>.</p></section>'
    )


def extract_section(html: str, title: str) -> str | None:
    m = re.search(
        rf'<section class="place-section"><h2>{re.escape(title)}</h2>.*?</section>',
        html,
        re.S,
    )
    return m.group(0) if m else None


def lis_of(sec: str | None) -> list[str]:
    if not sec:
        return []
    inner = re.search(r'<ul class="place-list">(.*?)</ul>', sec, re.S)
    if not inner:
        return []
    return re.findall(r"<li>.*?</li>", inner.group(1), re.S)


def reorder_and_replace(html: str, stay_sec: str, dining_sec: str, sights_sec: str) -> str:
    # Remove existing Stay/Dining/Sights sections
    html2 = re.sub(
        r'<section class="place-section"><h2>(?:Stay|Dining|Sights)</h2>.*?</section>',
        "",
        html,
        flags=re.S,
    )
    block = "".join(x for x in (stay_sec, dining_sec, sights_sec) if x)
    # Insert after meta-block if present, else after cover, else after h1 block
    if '<section class="meta-block">' in html2:
        html2 = re.sub(
            r'(<section class="meta-block">.*?</section>)',
            r"\1" + block,
            html2,
            count=1,
            flags=re.S,
        )
    elif "</figure>" in html2:
        html2 = html2.replace("</figure>", "</figure>" + block, 1)
    elif "</main>" in html2:
        html2 = html2.replace("</main>", block + "</main>", 1)
    else:
        html2 += block
    return html2


def rename_nt(hubs: dict) -> None:
    """Rename jis* directories, update hub keys, rewrite links sitewide under hokkaido/."""
    for old, (new, en) in NT_RENAME.items():
        old_dir = ROOT / PREF / old
        new_dir = ROOT / PREF / new
        if old_dir.exists() and not new_dir.exists():
            old_dir.rename(new_dir)
        elif old_dir.exists() and new_dir.exists():
            # merge: prefer new, drop old
            shutil.rmtree(old_dir)
        # hub
        if old in hubs:
            hb = hubs.pop(old)
            hb["name_en"] = en
            hb["slug"] = new
            hubs[new] = hb
        # page internals
        page = ROOT / PREF / new / "index.html"
        if page.exists():
            t = page.read_text(encoding="utf-8")
            t = t.replace(f"/{PREF}/{old}/", f"/{PREF}/{new}/")
            t = t.replace(f'href="../{old}/"', f'href="../{new}/"')
            # title / h1
            t = re.sub(
                r'<h1 class="page-title">.*?</h1>',
                f'<h1 class="page-title">{esc(en)}</h1>',
                t,
                count=1,
            )
            t = ensure_head(t, new, en)
            page.write_text(t, encoding="utf-8")
    # rewrite jis refs across all hokkaido pages + pref index
    for p in (ROOT / PREF).rglob("*.html"):
        t = p.read_text(encoding="utf-8")
        orig = t
        for old, (new, en) in NT_RENAME.items():
            t = t.replace(f'href="{old}/"', f'href="{new}/"')
            t = t.replace(f'href="../{old}/"', f'href="../{new}/"')
            t = t.replace(f'href="/{PREF}/{old}/"', f'href="/{PREF}/{new}/"')
            # data-name fixes for tomari / ruyobetsu
            if old == "jis01696":
                t = t.replace('data-name="Haku"', 'data-name="Tomari"')
                t = t.replace("aria-label=\"Haku\"", "aria-label=\"Tomari\"")
                t = t.replace("<title>Haku</title>", "<title>Tomari</title>")
            if old == "jis01697":
                t = t.replace('data-name="Ryu Yoru Betsu"', 'data-name="Ruyobetsu"')
                t = t.replace('aria-label="Ryu Yoru Betsu"', 'aria-label="Ruyobetsu"')
                t = t.replace("<title>Ryu Yoru Betsu</title>", "<title>Ruyobetsu</title>")
        if t != orig:
            p.write_text(t, encoding="utf-8")


def unlink_nt_from_pref_index():
    """Keep NT shapes on the pref map but drop crawlable hrefs so check_live skips thin Official/Sights-only pages."""
    idx = ROOT / PREF / "index.html"
    t = idx.read_text(encoding="utf-8")
    for _old, (new, en) in NT_RENAME.items():
        # turn <a href="new/" ...>...</a> into <span ...>...</span> (not matched by pref_munis)
        def repl(m, new=new):
            inner = m.group(1)
            # preserve data-name etc. but no href
            attrs = re.sub(r'\s*href="[^"]*"', "", m.group(0)[2 : m.group(0).index(">")])
            # m.group(0) is full a tag open... use simpler:
            return None  # unused

        pattern = re.compile(
            rf'<a href="{re.escape(new)}/"([^>]*)>(.*?)</a>',
            re.S,
        )

        def sub(m):
            attrs = m.group(1)
            inner = m.group(2)
            attrs = re.sub(r'\s*href="[^"]*"', "", attrs)
            return f"<span{attrs}>{inner}</span>"

        t = pattern.sub(sub, t)
    idx.write_text(t, encoding="utf-8")


def process_page(slug: str, muni_en: str, centroids: dict, stay_slugs: set[str], is_nt: bool) -> dict:
    path = ROOT / PREF / slug / "index.html"
    if not path.exists():
        return {"slug": slug, "ok": False, "err": "missing"}
    html = path.read_text(encoding="utf-8")
    st: Counter = Counter()

    stay_sec = extract_section(html, "Stay")
    dining_sec = extract_section(html, "Dining")
    sights_sec = extract_section(html, "Sights")

    stay_lis = lis_of(stay_sec)
    dining_lis = lis_of(dining_sec)
    sights_lis = lis_of(sights_sec)

    stay_lis = dedupe_lis([fix_dining_stay_li(li) for li in stay_lis])
    dining_lis = dedupe_lis([fix_dining_stay_li(li) for li in dining_lis])
    stay_lis = rerank_meta(stay_lis, muni_en)
    dining_lis = rerank_meta(dining_lis, muni_en)
    st["stay"] = len(stay_lis)
    st["dining"] = len(dining_lis)

    new_sights = dedupe_lis([rewrite_sight_li(li, muni_en) for li in sights_lis])
    st["sights"] = len(new_sights)
    st["sights_dropped"] = len(sights_lis) - len(new_sights)

    if stay_lis:
        new_stay_sec = section_html("Stay", stay_lis)
    else:
        near = nearest_stay_slug(slug, centroids, stay_slugs)
        if near:
            near_en = muni_name(near)
            new_stay_sec = stay_none_html(muni_en, near, near_en)
            st["stay_none"] = 1
        elif is_nt:
            new_stay_sec = ""  # NT thin pages stay without Stay (unlinked from index)
        else:
            # fallback: point at sapporo if somehow no centroid
            new_stay_sec = stay_none_html(muni_en, "sapporo", "Sapporo")
            st["stay_none_fallback"] = 1

    new_dining_sec = section_html("Dining", dining_lis) if dining_lis else ""
    new_sights_sec = section_html("Sights", new_sights) if new_sights else ""

    html2 = reorder_and_replace(html, new_stay_sec, new_dining_sec, new_sights_sec)
    html2 = ensure_head(html2, slug, muni_en)
    # global leftover Official/source link chrome outside rebuilt sights
    html2 = re.sub(
        r'(?:\s*·\s*)?<a href="[^"]+">\s*Official\s*/\s*source\s*link\s*</a>',
        "",
        html2,
        flags=re.I,
    )
    # leftover source.com in any photo-credit
    html2 = html2.replace("https://source.com/", "https://tabelog.com/")
    html2 = html2.replace("https://www.source.net/", "https://www.jalan.net/")
    html2 = html2.replace("https://source.net/", "https://www.jalan.net/")

    path.write_text(html2, encoding="utf-8")
    return {"slug": slug, "ok": True, **st}


# filled in main
NAME_BY_SLUG: dict[str, str] = {}


def muni_name(slug: str) -> str:
    return NAME_BY_SLUG.get(slug, slug.replace("-", " ").title())


def main():
    global NAME_BY_SLUG
    data = json.loads(HUBS_PATH.read_text())
    hubs = data["hubs"]

    # 1) rename NT jis* → romanized
    rename_nt(hubs)
    data["hubs"] = hubs
    HUBS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    NAME_BY_SLUG = {s: (h.get("name_en") or s) for s, h in hubs.items()}
    for old, (new, en) in NT_RENAME.items():
        NAME_BY_SLUG[new] = en

    # 2) centroids + stay set (from current pages)
    idx_html = (ROOT / PREF / "index.html").read_text(encoding="utf-8")
    centroids = map_centroids(idx_html)
    # also scrape centroids from a muni page map (same shapes)
    if len(centroids) < 50:
        sample = ROOT / PREF / "sapporo" / "index.html"
        centroids.update(map_centroids(sample.read_text(encoding="utf-8")))

    stay_slugs = set()
    for slug, hb in hubs.items():
        if hb.get("nt") or slug in {n for n, _ in NT_RENAME.values()} or slug.startswith("jis"):
            continue
        p = ROOT / PREF / slug / "index.html"
        if not p.exists():
            continue
        t = p.read_text(encoding="utf-8")
        sec = extract_section(t, "Stay")
        if sec and "<li>" in sec and "stay-none" not in sec:
            stay_slugs.add(slug)
    print(f"centroids={len(centroids)} stay_slugs={len(stay_slugs)}")

    results = []
    nt_new = {n for n, _ in NT_RENAME.values()}
    for slug, hb in sorted(hubs.items()):
        if slug.startswith("jis"):
            continue
        muni_en = hb.get("name_en") or NAME_BY_SLUG.get(slug, slug)
        is_nt = bool(hb.get("nt")) or slug in nt_new
        r = process_page(slug, muni_en, centroids, stay_slugs, is_nt)
        results.append(r)
        if r.get("ok"):
            print(f"OK {slug} stay={r.get('stay')} dining={r.get('dining')} sights={r.get('sights')} none={r.get('stay_none',0)}")
        else:
            print(f"ERR {slug} {r}")

    unlink_nt_from_pref_index()

    # fix neutralize_credit in render_hub for future renders
    rh = Path("/workspace/p1/fn-uplift/scripts/render_hub.py")
    txt = rh.read_text(encoding="utf-8")
    if "split(r'(https?://" not in txt:
        old = '''def neutralize_credit(credit: str) -> str:
    if not credit:
        return ''
    credit = re.sub(r'\\b(Tabelog|TripAdvisor|Jalan|Ikkyu|食べログ|じゃらん|一休)\\b', 'source', credit, flags=re.I)
    return credit'''
        new = '''def neutralize_credit(credit: str) -> str:
    if not credit:
        return ''
    # Do not rewrite brand tokens inside URLs (tabelog.com → source.com was breaking R3).
    parts = re.split(r'(https?://\\S+)', credit)
    out = []
    for i, p in enumerate(parts):
        if i % 2 == 1:
            out.append(p)
        else:
            out.append(re.sub(r'\\b(Tabelog|TripAdvisor|Jalan|Ikkyu|食べログ|じゃらん|一休)\\b', 'source', p, flags=re.I))
    return ''.join(out)'''
        if old in txt:
            rh.write_text(txt.replace(old, new), encoding="utf-8")
            print("patched render_hub.neutralize_credit")
        else:
            print("WARN: could not patch neutralize_credit (pattern mismatch)")

    summary = {
        "pages": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "stay_none": sum(1 for r in results if r.get("stay_none")),
        "source_com_left": 0,
        "official_chrome_left": 0,
    }
    for p in (ROOT / PREF).glob("*/index.html"):
        t = p.read_text(encoding="utf-8")
        summary["source_com_left"] += t.lower().count("source.com") + t.lower().count("source.net")
        summary["official_chrome_left"] += len(re.findall(r"Official\s*/\s*source\s*link", t, re.I))
    # jis dirs left?
    summary["jis_dirs"] = [p.name for p in (ROOT / PREF).iterdir() if p.name.startswith("jis")]
    Path("/tmp/hokkaido-cos-summary.json").write_text(json.dumps(summary, indent=2))
    print("SUMMARY", json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
