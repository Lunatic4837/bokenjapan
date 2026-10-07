#!/usr/bin/env python3
"""Build a slim GitHub Pages artifact under _site/.

Why: main tree is ~7GB (duplicated inline SVG maps + full-res media) and exceeds
GitHub Pages' 1GB published-site limit / 10-minute deploy timeout.

Facility catalog waves made "compress every referenced photo" fail the budget:
after main 73401b10f4, _site was ~1010 MiB (WebP ~1.00 GiB + HTML ~43 MiB) and
the 1000 MiB gate exited 2. There is no stable remote image host on this path
(Cloudflare R2 is not enabled). Direct HTTPS image URLs are not stored on the
pages — photo-credit comments point at article pages, not files — so facility
thumbs cannot be hotlinked.

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
  5) Keeps CNAME, .nojekyll, styles.css, logo, index, every municipality page

Soft gate is 900 MiB (GitHub Pages hard limit is 1 GiB). At full saturation
(~1,750 municipality pages × the caps, ~16–20 KiB/thumb) plus HTML and richer
covers, _site stays under that line. See scripts/PAGES-SLIM-NOTES.md.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from PIL import Image

Image.MAX_IMAGE_PIXELS = None

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "_site"
MEDIA_IN = ROOT / "media"
MEDIA_OUT = OUT / "media"

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
ROOT_FILES = [
    "index.html",
    "styles.css",
    "CNAME",
    ".nojekyll",
    "logo.svg",
    "hero-himeji.jpg",
    "PUBLISH-MANIFEST.txt",
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
    def repl(m: re.Match) -> str:
        prefix, path, ext, suffix = m.group(1), m.group(2), m.group(3), m.group(4)
        # keep .webp as-is; map jpg/jpeg/png -> .webp
        if ext.lower() == ".webp":
            return m.group(0)
        return f"{prefix}{path}.webp{suffix}"

    # Also rewrite plain media/foo.jpg occurring in srcset-like contexts
    text = MEDIA_RE.sub(repl, text)
    text = re.sub(
        r"(media/[^\"')?#\s]+)\.(?:jpg|jpeg|png)\b",
        lambda m: m.group(1) + ".webp",
        text,
        flags=re.I,
    )
    return text


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


def normalize_map_svg(svg: str, pref: str) -> str:
    """Rewrite municipality hrefs to absolute /{pref}/{slug}/ and drop is-here."""
    # remove is-here class
    svg = re.sub(r"""\sclass="is-here\"""", "", svg)
    svg = re.sub(r"""\sclass='is-here'""", "", svg)
    svg = re.sub(r"""(class="[^"]*)\bis-here\b([^"]*")""", r"\1\2", svg)

    def href_repl(m: re.Match) -> str:
        href = m.group(1)
        if href in ("./", ".", "#", ""):
            return m.group(0)  # leave; loader fixes current page
        # ../slug/ or ./slug/ or slug/
        slug = href.strip("/").split("/")[-1]
        if not slug or slug == pref:
            return f'href="/{pref}/"'
        return f'href="/{pref}/{slug}/"'

    svg = re.sub(r'href="([^"]+)"', href_repl, svg)
    return svg


def process_html(src: Path, dst: Path, pref: str | None) -> tuple[set[str], set[str], int]:
    text = src.read_text(encoding="utf-8", errors="ignore")
    text, dropped = cap_facility_thumbs(text)
    media_needed: set[str] = set()
    cover_names = {Path(m.group(1)).name for m in COVER_SRC_RE.finditer(text)}

    # collect media basenames before the jpg -> webp rewrite
    for m in re.finditer(r"""media/([^"')?#\s]+)""", text):
        media_needed.add(Path(m.group(1)).name)

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
                map_path.write_text(normalize_map_svg(svg, pref), encoding="utf-8")
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
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    MEDIA_OUT.mkdir(parents=True)

    media_needed: set[str] = set()
    cover_names: set[str] = set()
    thumbs_dropped = 0

    # Root files
    for name in ROOT_FILES:
        src = ROOT / name
        if not src.exists():
            continue
        if name.endswith(".html") or name.endswith(".css"):
            text = rewrite_media_refs(src.read_text(encoding="utf-8", errors="ignore"))
            (OUT / name).write_text(text, encoding="utf-8")
            for m in re.finditer(r"""media/([^"')?#\s]+)""", src.read_text(encoding="utf-8", errors="ignore")):
                media_needed.add(Path(m.group(1)).name)
        elif name == "hero-himeji.jpg":
            # compress to webp sibling referenced? index likely uses hero-himeji.jpg
            # keep filename but still copy compressed jpeg-as-webp rewritten in HTML separately
            media_needed.add("__hero__")
            # handled below
            pass
        else:
            shutil.copy2(src, OUT / name)

    # Special-case hero at root: compress to hero-himeji.webp and rewrite index
    hero = ROOT / "hero-himeji.jpg"
    if hero.exists():
        im = Image.open(hero)
        if im.mode != "RGB":
            im = im.convert("RGB")
        im.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
        im.save(OUT / "hero-himeji.webp", format="WEBP", quality=40, method=2)
        idx = OUT / "index.html"
        if idx.exists():
            t = idx.read_text(encoding="utf-8")
            t = t.replace("hero-himeji.jpg", "hero-himeji.webp")
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
                    src, dst, pref if src.suffix.lower() == ".html" else None
                )
                media_needed |= needed
                cover_names |= covers
                thumbs_dropped += dropped
                html_count += 1
            else:
                # rare non-html assets under pref
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    # Drop sentinel
    media_needed.discard("__hero__")

    # Compress media (only needed basenames that exist).
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
