#!/usr/bin/env python3
"""Point homepage and five-prefecture images at Cloudflare R2.

Rewrites only keys listed in scripts/manifest-5pref-all.csv. The public host
is R2_BASE in scripts/build-pages-site.py (one assignment). Re-run this script
after changing that host.

Does not add photos, rankings, or English explanations. Phase D owns those.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

from PIL import Image

from r2_images import load_manifest_keys, load_missing_keys, rewrite_page

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path(__file__).with_name("manifest-5pref-all.csv")
MISSING_PATH = Path(__file__).with_name("missing-on-main.tsv")
PREFS = ("miyagi", "akita", "fukuoka", "yamaguchi", "oita")


def load_r2_base() -> str:
    path = Path(__file__).with_name("build-pages-site.py")
    spec = importlib.util.spec_from_file_location("build_pages_site", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    base = module.R2_BASE
    if not isinstance(base, str) or not base.startswith("https://"):
        raise RuntimeError("R2_BASE missing from build-pages-site.py")
    return base


def scoped_pages() -> list[Path]:
    pages = [ROOT / "index.html"]
    for pref in PREFS:
        pages.extend(sorted((ROOT / pref).rglob("*.html")))
    return pages


def self_test(r2_base: str) -> None:
    import tempfile

    from r2_images import local_media_names

    build_path = Path(__file__).with_name("build-pages-site.py")
    spec = importlib.util.spec_from_file_location("build_pages_site_test", build_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load build script for self-test")
    build = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(build)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        media = root / "media"
        media.mkdir()
        Image.new("RGB", (12, 34), (9, 8, 7)).save(media / "tiny.png")
        html_path = root / "miyagi" / "ohira" / "index.html"
        html_path.parent.mkdir(parents=True)
        manifest = {
            "media/tiny.png",
            "media/keep.jpg",
            "og.png",
            "logo.svg",
            "favicon.ico",
            "hero-himeji.jpg",
        }
        missing = {"media/chikushino-dining-ta1.jpg"}
        sample = """
        <meta property="og:url" content="https://bokenjapan.com/miyagi/ohira/">
        <meta property="og:image" content="https://bokenjapan.com/og.png">
        <meta name="twitter:image" content="https://bokenjapan.com/og.png">
        <link rel="icon" href="/favicon.ico">
        <img class="brand-mark" src="../../logo.svg" width="168" height="168" alt="logo">
        <img src="hero-himeji.jpg" alt="hero" width="10" height="10">
        <path fill="url(#igFillMain)" d="M0 0"></path>
        <a href="https://example.com/photo.jpg">ext</a>
        <li><a href="https://example.com/place"><p class="place-name">Keep</p><img class="thumb" src="../../media/tiny.png" alt="Keep" loading="lazy"></a></li>
        <li><a href="https://example.com/gone"><p class="place-name">Gone</p><img class="thumb" src="../../media/chikushino-dining-ta1.jpg" alt="Gone"></a><p class="place-meta">#1 ranked in Ohira</p></li>
        <img class="thumb" src="../../media/local-only.jpg" alt="local">
        <img class="thumb" src="{r2}/media/keep.jpg" alt="already" loading="lazy" decoding="async" width="3" height="4">
        """.replace("{r2}", r2_base)
        # hero src above is relative to miyagi/ohira, so it would not resolve to
        # the repo root. Use a homepage path for the root-asset sample separately.
        once, stats = rewrite_page(sample, html_path, root, r2_base, manifest, missing)
        twice, again = rewrite_page(once, html_path, root, r2_base, manifest, missing)
        if once != twice or any(again.values()):
            raise SystemExit("rewrite_page is not idempotent")
        if f'{r2_base}/og.png' not in once:
            raise SystemExit("og:image was not rewritten")
        if "https://bokenjapan.com/miyagi/ohira/" not in once:
            raise SystemExit("og:url was rewritten")
        if f"{r2_base}/favicon.ico" not in once:
            raise SystemExit("favicon was not rewritten")
        if f"{r2_base}/logo.svg" not in once:
            raise SystemExit("logo was not rewritten")
        if "url(#igFillMain)" not in once:
            raise SystemExit("SVG paint server was rewritten")
        if "https://example.com/photo.jpg" not in once:
            raise SystemExit("external link was rewritten")
        if "chikushino-dining-ta1" in once:
            raise SystemExit("missing image src survived")
        if once.count("<!-- photo-missing -->") != 1:
            raise SystemExit("photo-missing comment missing or duplicated")
        if "Gone" not in once or "#1 ranked in Ohira" not in once:
            raise SystemExit("card with a missing photo was dropped")
        if f'width="12"' not in once or 'height="34"' not in once:
            raise SystemExit(f"thumb dimensions missing: {once}")
        if once.count('decoding="async"') < 2:
            raise SystemExit("decoding=async was not added to thumbs")
        if 'width="3"' not in once or once.count('loading="lazy"') < 2:
            raise SystemExit("existing thumb attributes were duplicated or dropped")
        if "../../media/local-only.jpg" not in once:
            raise SystemExit("non-manifest image was rewritten")
        if stats["removed"] != 1:
            raise SystemExit(f"unexpected removal count {stats}")

        home = root / "index.html"
        home_html = (
            '<img src="hero-himeji.jpg" alt="hero" width="10" height="10">'
            '<img src="logo.svg" alt="logo">'
        )
        home_out, _ = rewrite_page(
            home_html, home, root, r2_base, manifest, missing
        )
        if f'{r2_base}/hero-himeji.jpg' not in home_out:
            raise SystemExit("homepage hero was not rewritten")
        if f'{r2_base}/logo.svg' not in home_out:
            raise SystemExit("homepage logo was not rewritten")

    remote = f"{r2_base}/media/foo.jpg"
    mixed = f'src="{remote}" src="../../media/bar.jpg" media/baz.jpg'
    rewritten = build.rewrite_media_refs(mixed)
    if remote not in rewritten or "foo.webp" in rewritten:
        raise SystemExit(f"webp rewrite touched an R2 URL: {rewritten}")
    if "../../media/bar.webp" not in rewritten or "media/baz.webp" not in rewritten:
        raise SystemExit(f"webp rewrite skipped a local file: {rewritten}")

    dining = "<h2>Dining</h2>" + "".join(
        f'<img class="thumb" src="{r2_base}/media/remote-{i}.jpg" alt="">'
        for i in range(5)
    ) + "".join(
        f'<img class="thumb" src="../../media/local-{i}.jpg" alt="">'
        for i in range(10)
    )
    capped, dropped = build.cap_facility_thumbs(dining)
    if dropped != 2 or capped.count(r2_base) != 5 or capped.count("local-") != 8:
        raise SystemExit(
            f"R2 thumbs were capped: dropped={dropped} r2={capped.count(r2_base)} "
            f"local={capped.count('local-')}"
        )
    names = local_media_names(
        f'src="{r2_base}/media/remote.jpg" src="../../media/local.jpg"',
        r2_base,
    )
    if names != {"local.jpg"}:
        raise SystemExit(f"local media scan kept an R2 file: {names}")
    hero = f'src="{r2_base}/hero-himeji.jpg" src="hero-himeji.jpg"'
    if build.hero_needs_local_file(f'src="{r2_base}/hero-himeji.jpg"'):
        raise SystemExit("R2 hero still requests a local file")
    hero_out = build.rewrite_local_hero(hero)
    if f"{r2_base}/hero-himeji.webp" in hero_out or f"{r2_base}/hero-himeji.jpg" not in hero_out:
        raise SystemExit(f"hero rewrite changed an R2 URL: {hero_out}")
    if 'src="hero-himeji.webp"' not in hero_out:
        raise SystemExit(f"local hero was not rewritten: {hero_out}")
    print("self-test ok", flush=True)


def main() -> int:
    r2_base = load_r2_base()
    self_test(r2_base)
    manifest = load_manifest_keys(MANIFEST_PATH)
    missing = load_missing_keys(MISSING_PATH)
    if len(manifest) != 47372:
        raise SystemExit(f"manifest has {len(manifest)} keys, expected 47372")
    if len(missing) != 75:
        raise SystemExit(f"missing list has {len(missing)} keys, expected 75")
    overlap = manifest & missing
    if overlap:
        raise SystemExit(f"missing keys are in the manifest: {sorted(overlap)[:5]}")

    pages = scoped_pages()
    changed = 0
    removed = rewritten = thumbs = 0
    for path in pages:
        original = path.read_text(encoding="utf-8")
        once, stats = rewrite_page(
            original, path, ROOT, r2_base, manifest, missing
        )
        twice, again = rewrite_page(once, path, ROOT, r2_base, manifest, missing)
        if once != twice or any(again.values()):
            raise SystemExit(f"not idempotent: {path.relative_to(ROOT)}")
        removed += stats["removed"]
        rewritten += stats["rewritten"]
        thumbs += stats["thumbs"]
        if once != original:
            path.write_text(once, encoding="utf-8")
            changed += 1
        print(
            f"{path.relative_to(ROOT)} rewritten={stats['rewritten']} "
            f"removed={stats['removed']} thumbs={stats['thumbs']}",
            flush=True,
        )
    print(
        f"pages={len(pages)} changed={changed} rewritten={rewritten} "
        f"removed={removed} thumbs={thumbs}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
