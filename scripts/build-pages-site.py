#!/usr/bin/env python3
"""Build a slim GitHub Pages artifact under _site/.

Why: main tree is ~7GB (duplicated inline SVG maps + full-res media) and exceeds
GitHub Pages' 1GB published-site limit / 10-minute deploy timeout.

Facility catalog waves made "compress every referenced photo" fail the budget:
after main 73401b10f4, _site was ~1010 MiB (WebP ~1.00 GiB + HTML ~43 MiB) and
the 1000 MiB gate exited 2. Homepage and Miyagi, Akita, Fukuoka, Yamaguchi,
and Oita photos are hosted on Cloudflare R2 (see R2_BASE). Those URLs stay
absolute and are not copied into _site. Every other prefecture still uses
local files, with the caps and WebP encode below.

This script:
  1) Copies flat HTML site structure (no prefecture filter; publish set unchanged)
  2) Externalizes per-prefecture SVG locator maps (dedupe ~679MB of embeds)
  3) Bakes local WebP only for:
       - every municipality cover (1200px edge, q=62) so the hero still meets
         the homepage / Instagram bar
       - a per-section cap of facility thumbs (560px, q=25):
           Stay 8, Dining 8, Sights 4, any other section 2
         Priority is per section, so a 6,000-photo dining dump cannot crowd
         out Stay or the cover. Ohira keeps its stay photo, its sights (3),
         and the first 8 dining photos. Place names stay; photo-credit
         comments stay hidden.
  4) Rewrites remaining media/*.jpg|png refs in published HTML/CSS to .webp
  5) Keeps CNAME, .nojekyll, styles.css, logo, index, privacy.html,
     terms.html, the TikTok site-verification file, and every municipality page

Soft gate is 900 MiB (GitHub Pages hard limit is 1 GiB). At full saturation
(~1,750 municipality pages × the caps, ~16–20 KiB/thumb) plus HTML and richer
covers, _site stays under that line. See scripts/PAGES-SLIM-NOTES.md.
"""
from __future__ import annotations

import os
import re
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from r2_images import (  # noqa: E402
    inside_absolute_url,
    load_manifest_keys,
    load_missing_keys,
    load_placeholder_names,
    local_media_names,
    rewrite_page,
)

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
MEDIA_IN = ROOT / "media"
MEDIA_OUT = OUT / "media"

# Public photo host. Switch to https://img.bokenjapan.com by editing this line
# and re-running scripts/render_phase_c.py. Do not copy the string elsewhere.
R2_BASE = "https://pub-f074f228689740b2a22b36f38e90e96e.r2.dev"
R2_PREFS = frozenset({"miyagi", "akita", "fukuoka", "yamaguchi", "oita"})
MANIFEST_PATH = SCRIPTS / "manifest-5pref-all.csv"
MISSING_PATH = SCRIPTS / "missing-on-main.tsv"
MANIFEST_KEYS: set[str] = set()
MISSING_KEYS: set[str] = set()
PLACEHOLDER_NAMES: set[str] = set()

# List thumbs. Covers use a larger edge so municipality heroes stay sharp.
MAX_EDGE = 560
WEBP_QUALITY = 25
COVER_MAX_EDGE = 1200
COVER_QUALITY = 62
WORKERS = max(2, min(8, (os.cpu_count() or 4)))

# Local thumbs baked into gh-pages, per place-section, per page.
# Stay / Dining are capped high enough to keep the Ohira template rows.
# Sights stay short because the cover already leads the page.
THUMB_CAPS = {
    "Stay": 8,
    "Dining": 8,
    "Sights": 4,
}
DEFAULT_THUMB_CAP = 2

# Soft budget. Pages rejects publishes at 1 GiB; stay under this so the
# auto-deploy fails here instead of on the host.
SOFT_BUDGET_BYTES = 900 * 1024 * 1024

SKIP_DIRS = {".git", "_site", "scripts", ".github", "node_modules", "media"}
# Copied to _site root. privacy.html and terms.html are public TikTok OAuth
# URLs and must survive the slim publish, same as the site-verification file.
ROOT_FILES = [
    "index.html",
    "privacy.html",
    "terms.html",
    "styles.css",
    "CNAME",
    ".nojekyll",
    "logo.svg",
    "favicon.ico",
    "apple-touch-icon.png",
    "og.png",
    "hero-himeji.jpg",
    "PUBLISH-MANIFEST.txt",
    "tiktokEFvXON4ipvA4nlkjYEPd1T1qF6H6WPGx.txt",
]

SVG_RE = re.compile(r"(<div class=\"map-wrap\">)\s*(<svg[\s\S]*?</svg>)\s*(</div>)", re.I)
MEDIA_RE = re.compile(
    r"""((?:src|href|content|poster|data-src)=["']|(?:url\(\s*["']?))((?:\.\./)*media/[^"')?#\s]+)(\.(?:jpg|jpeg|png|webp))(["')]?)""",
    re.I,
)
LOADER_JS = """<script>(function(){var w=document.currentScript.previousElementSibling;if(!w||!w.dataset.map)return;var here=w.dataset.here||"";fetch(w.dataset.map).then(function(r){return r.text()}).then(function(t){w.innerHTML=t;var svg=w.querySelector("svg");if(svg){svg.removeAttribute("width");svg.removeAttribute("height");svg.setAttribute("class",(svg.getAttribute("class")||"")+" pref-map");}var nodes=w.querySelectorAll("a[data-name]");for(var i=0;i<nodes.length;i++){var a=nodes[i];a.classList.remove("is-here");if(here&&a.getAttribute("data-name")===here){a.classList.add("is-here");}var href=a.getAttribute("href")||"";if(href==="./"||href==="."){var slug=(location.pathname.replace(/\\/+$/,"").split("/").pop()||"");if(slug)a.setAttribute("href","../"+slug+"/");}}}).catch(function(){w.innerHTML="<p class=\\"map-note\\">Map unavailable.</p>";});})();</script>"""

H2_SPLIT_RE = re.compile(r"(<h2>[^<]*</h2>)", re.I)
THUMB_IMG_RE = re.compile(r'<img\b[^>]*\bclass="thumb"[^>]*>', re.I)
THUMB_SRC_RE = re.compile(r"""\bsrc="[^"]*media/([^"?#]+)""", re.I)
COVER_SRC_RE = re.compile(
    r"""<figure class="cover">\s*<img\b[^>]*\bsrc="[^"]*media/([^"?#]+)""",
    re.I,
)


def rewrite_media_refs(text: str) -> str:
    """Map local jpg/png refs to .webp. Absolute http(s) URLs, including R2, stay."""

    def repl(m: re.Match) -> str:
        if inside_absolute_url(text, m.start(2)):
            return m.group(0)
        prefix, path, ext, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
        # keep .webp as-is; map jpg/jpeg/png -> .webp
        if ext.lower() == ".webp":
            return m.group(0)
        return f"{prefix}{path}.webp{suffix}"

    # Also rewrite plain media/foo.jpg occurring in srcset-like contexts.
    # The second pattern matches the media/ segment inside an R2 URL; skip those.
    text = MEDIA_RE.sub(repl, text)

    def repl_plain(m: re.Match) -> str:
        if inside_absolute_url(text, m.start()):
            return m.group(0)
        return m.group(1) + ".webp"

    text = re.sub(
        r"(media/[^\"')?#\s]+)\.(?:jpg|jpeg|png)\b",
        repl_plain,
        text,
        flags=re.I,
    )
    return text


def rewrite_local_hero(text: str) -> str:
    """Compress-name only a root-relative hero. Leave the R2 object key as .jpg."""

    def repl(m: re.Match) -> str:
        if text[max(0, m.start() - len(R2_BASE) - 1) : m.start()].endswith(R2_BASE + "/"):
            return m.group(0)
        return "hero-himeji.webp"

    return re.sub(r"hero-himeji\.jpg", repl, text)


def hero_needs_local_file(text: str) -> bool:
    for match in re.finditer(r"hero-himeji\.jpg", text):
        if text[max(0, match.start() - len(R2_BASE) - 1) : match.start()].endswith(
            R2_BASE + "/"
        ):
            continue
        return True
    return False


def section_thumb_cap(section: str) -> int:
    return THUMB_CAPS.get(section, DEFAULT_THUMB_CAP)


def cap_facility_thumbs(text: str) -> tuple[str, int]:
    """Omit local thumb <img> tags past the per-section cap.

    Cover images are not thumbs and are left in place. A filename already
    kept in that section (or used as this page's cover) does not take
    another slot. Place-name text and photo-credit comments stay.
    """
    cover_names = {Path(m.group(1)).name for m in COVER_SRC_RE.finditer(text)}
    kept: dict[str, set[str]] = {}
    dropped = 0
    section = ""

    def repl(m: re.Match) -> str:
        nonlocal dropped
        tag = m.group(0)
        src_m = re.search(r'\bsrc="([^"]+)"', tag, re.I)
        # R2 photos are already hosted. Do not drop them and do not spend a cap slot.
        if src_m and src_m.group(1).startswith(R2_BASE + "/"):
            return tag
        sm = THUMB_SRC_RE.search(tag)
        if not sm:
            return tag
        name = Path(sm.group(1)).name
        if name in cover_names:
            return tag
        bucket = kept.setdefault(section, set())
        if name in bucket:
            return tag
        if len(bucket) >= section_thumb_cap(section):
            dropped += 1
            return ""
        bucket.add(name)
        return tag

    out: list[str] = []
    for part in H2_SPLIT_RE.split(text):
        heading = re.fullmatch(r"<h2>([^<]*)</h2>", part, re.I)
        if heading:
            section = heading.group(1).strip()
            out.append(part)
            continue
        out.append(THUMB_IMG_RE.sub(repl, part))
    return "".join(out), dropped


def extract_here_name(svg: str) -> str:
    m = re.search(r'<a[^>]*class="[^"]*\bis-here\b[^"]*"[^>]*data-name="([^"]+)"', svg)
    if m:
        return m.group(1)
    m = re.search(r'<a[^>]*data-name="([^"]+)"[^>]*class="[^"]*\bis-here\b', svg)
    return m.group(1) if m else ""


def normalize_map_svg(svg: str, pref: str, here_slug: str | None = None) -> str:
    """Rewrite municipality hrefs to absolute /{pref}/{slug}/ and drop is-here.

    A city can share its prefecture's name (Akita, Fukuoka, Yamaguchi, Oita).
    That slug must stay a municipality path. Treating ``slug == pref`` as the
    prefecture index sent those four shapes to ``/{pref}/``.
    """
    # remove is-here class
    svg = re.sub(r"""\sclass="is-here\"""", "", svg)
    svg = re.sub(r"""\sclass='is-here'""", "", svg)
    svg = re.sub(r"""(class="[^"]*)\bis-here\b([^"]*")""", r"\1\2", svg)

    def href_repl(m: re.Match) -> str:
        href = m.group(1)
        if href in ("./", ".", "#", ""):
            # The inline map uses "./" for whichever town the source page is.
            # Resolve it here so the shared SVG does not follow the reader.
            if here_slug and re.fullmatch(r"[a-z0-9-]+", here_slug):
                return f'href="/{pref}/{here_slug}/"'
            return m.group(0)
        slug = href.strip("/").split("/")[-1]
        if not re.fullmatch(r"[a-z0-9-]+", slug or ""):
            return m.group(0)
        return f'href="/{pref}/{slug}/"'

    svg = re.sub(r'href="([^"]+)"', href_repl, svg)
    return svg


def process_html(
    src: Path, dst: Path, pref: str | None, use_r2: bool = False
) -> tuple[set[str], set[str], int]:
    text = src.read_text(encoding="utf-8", errors="ignore")
    if use_r2:
        text, _stats = rewrite_page(
            text,
            src,
            ROOT,
            R2_BASE,
            MANIFEST_KEYS,
            MISSING_KEYS,
            PLACEHOLDER_NAMES,
        )
    text, dropped = cap_facility_thumbs(text)
    cover_names = {Path(m.group(1)).name for m in COVER_SRC_RE.finditer(text)}

    # Local files only. R2 URLs contain "media/" but those objects stay on R2.
    media_needed = local_media_names(text, R2_BASE)

    if pref and SVG_RE.search(text):
        map_rel = "_map.svg" if src.parent.name == pref or src.name == "index.html" and src.parent.name == pref else "../_map.svg"
        # prefecture index is pref/index.html -> _map.svg; muni is pref/town/index.html -> ../_map.svg
        if len(src.relative_to(ROOT).parts) == 2:  # pref/index.html
            map_rel = "_map.svg"
        else:
            map_rel = "../_map.svg"

        def svg_repl(m: re.Match) -> str:
            svg = m.group(2)
            here = extract_here_name(svg)
            # ensure map file exists (write once)
            map_path = OUT / pref / "_map.svg"
            if not map_path.exists():
                map_path.parent.mkdir(parents=True, exist_ok=True)
                # pref/town/index.html → the "./" shape is that town.
                here_slug = src.parent.name if len(src.relative_to(ROOT).parts) == 3 else None
                map_path.write_text(
                    normalize_map_svg(svg, pref, here_slug), encoding="utf-8"
                )
            return (
                f'<div class="map-wrap" data-map="{map_rel}" data-here="{here}"></div>\n'
                f"      {LOADER_JS}"
            )

        text = SVG_RE.sub(svg_repl, text, count=1)

    text = rewrite_media_refs(text)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8")
    return media_needed, cover_names, dropped


def compress_one(args: tuple[str, str, int, int]) -> tuple[str, int, int, str]:
    src_s, dst_s, max_edge, quality = args
    src = Path(src_s)
    dst = Path(dst_s)
    try:
        orig = src.stat().st_size
        im = Image.open(src)
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        elif im.mode == "L":
            im = im.convert("RGB")
        im.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, format="WEBP", quality=quality, method=4)
        return (src.name, orig, dst.stat().st_size, "ok")
    except Exception as e:
        return (src.name, 0, 0, f"err:{e}")


def main() -> int:
    global MANIFEST_KEYS, MISSING_KEYS, PLACEHOLDER_NAMES
    if not MANIFEST_PATH.is_file():
        print(f"ERROR: missing R2 allow-list {MANIFEST_PATH}", file=sys.stderr)
        return 2
    MANIFEST_KEYS = load_manifest_keys(MANIFEST_PATH)
    MISSING_KEYS = load_missing_keys(MISSING_PATH) if MISSING_PATH.is_file() else set()
    PLACEHOLDER_NAMES = load_placeholder_names(MEDIA_IN)

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    MEDIA_OUT.mkdir(parents=True)

    media_needed: set[str] = set()
    cover_names: set[str] = set()
    thumbs_dropped = 0

    # Root files. index.html is in the R2 scope; other root HTML stays local.
    for name in ROOT_FILES:
        src = ROOT / name
        if not src.exists():
            continue
        if name == "index.html":
            text = src.read_text(encoding="utf-8", errors="ignore")
            text, _stats = rewrite_page(
                text,
                src,
                ROOT,
                R2_BASE,
                MANIFEST_KEYS,
                MISSING_KEYS,
                PLACEHOLDER_NAMES,
            )
            text = rewrite_media_refs(text)
            (OUT / name).write_text(text, encoding="utf-8")
            media_needed |= local_media_names(text, R2_BASE)
        elif name.endswith(".html") or name.endswith(".css"):
            raw = src.read_text(encoding="utf-8", errors="ignore")
            text = rewrite_media_refs(raw)
            (OUT / name).write_text(text, encoding="utf-8")
            media_needed |= local_media_names(raw, R2_BASE)
        elif name == "hero-himeji.jpg":
            # Published only when the homepage still references the local file.
            pass
        else:
            shutil.copy2(src, OUT / name)

    # Local hero becomes a WebP. An R2 hero URL keeps the .jpg object key.
    hero = ROOT / "hero-himeji.jpg"
    idx = OUT / "index.html"
    if hero.exists() and idx.exists():
        t = idx.read_text(encoding="utf-8")
        if hero_needs_local_file(t):
            im = Image.open(hero)
            if im.mode != "RGB":
                im = im.convert("RGB")
            im.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
            im.save(OUT / "hero-himeji.webp", format="WEBP", quality=40, method=2)
            t = rewrite_local_hero(t)
            idx.write_text(t, encoding="utf-8")

    # Prefecture trees
    prefs = sorted(
        p
        for p in ROOT.iterdir()
        if p.is_dir() and p.name not in SKIP_DIRS and not p.name.startswith(".")
    )
    html_count = 0
    for pref_dir in prefs:
        pref = pref_dir.name
        for src in pref_dir.rglob("*"):
            if src.is_dir():
                continue
            rel = src.relative_to(ROOT)
            dst = OUT / rel
            if src.suffix.lower() in {".html", ".css"}:
                needed, covers, dropped = process_html(
                    src,
                    dst,
                    pref if src.suffix.lower() == ".html" else None,
                    use_r2=pref in R2_PREFS and src.suffix.lower() == ".html",
                )
                media_needed |= needed
                cover_names |= covers
                thumbs_dropped += dropped
                html_count += 1
            else:
                # rare non-html assets under pref
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    # Compress media (only needed basenames that exist).
    # Manifest files referenced as R2 URLs are not in media_needed.
    # Covers are encoded once, at the sharper setting, even if a thumb uses the same file.
    cover_stems = {Path(name).stem for name in cover_names}
    jobs = []
    for name in sorted(media_needed):
        src = MEDIA_IN / name
        if not src.is_file():
            # try without expecting exact; skip missing
            continue
        stem = Path(name).stem
        dst = MEDIA_OUT / f"{stem}.webp"
        if stem in cover_stems:
            edge, quality = COVER_MAX_EDGE, COVER_QUALITY
        else:
            edge, quality = MAX_EDGE, WEBP_QUALITY
        jobs.append((str(src), str(dst), edge, quality))

    print(f"HTML pages processed: {html_count}", flush=True)
    print(
        f"Thumbs omitted past cap: {thumbs_dropped} "
        f"(Stay {THUMB_CAPS['Stay']}, Dining {THUMB_CAPS['Dining']}, "
        f"Sights {THUMB_CAPS['Sights']}, other {DEFAULT_THUMB_CAP})",
        flush=True,
    )
    print(
        f"Media files to compress: {len(jobs)} "
        f"(covers≤{len(cover_stems)}, workers={WORKERS})",
        flush=True,
    )

    ok = err = 0
    orig_b = new_b = 0
    with ProcessPoolExecutor(max_workers=WORKERS) as ex:
        futs = [ex.submit(compress_one, j) for j in jobs]
        done = 0
        for fut in as_completed(futs):
            name, o, n, status = fut.result()
            done += 1
            if status == "ok":
                ok += 1
                orig_b += o
                new_b += n
            else:
                err += 1
                print(f"WARN {name}: {status}", flush=True)
            if done % 2000 == 0 or done == len(futs):
                print(f"  compressed {done}/{len(futs)}", flush=True)

    # Ensure CNAME / nojekyll
    (OUT / ".nojekyll").write_text("", encoding="utf-8")
    cname = ROOT / "CNAME"
    if cname.exists():
        shutil.copy2(cname, OUT / "CNAME")

    # Size report
    total = sum(f.stat().st_size for f in OUT.rglob("*") if f.is_file())
    media_bytes = sum(f.stat().st_size for f in MEDIA_OUT.rglob("*") if f.is_file())
    html_bytes = sum(
        f.stat().st_size for f in OUT.rglob("*.html") if f.is_file()
    )
    print(
        f"DONE ok={ok} err={err} media {orig_b/1024/1024:.1f}MiB -> {new_b/1024/1024:.1f}MiB; "
        f"webp={media_bytes/1024/1024:.1f}MiB html={html_bytes/1024/1024:.1f}MiB "
        f"_site total={total/1024/1024:.1f}MiB "
        f"(soft budget {SOFT_BUDGET_BYTES/1024/1024:.0f} MiB, Pages hard limit 1 GiB)",
        flush=True,
    )
    if total > SOFT_BUDGET_BYTES:
        print(
            "ERROR: _site exceeds 900 MiB soft budget (Pages hard limit is 1 GiB)",
            flush=True,
        )
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
