#!/usr/bin/env python3
"""Re-pick hub tile images that tile_check.py flags (hero repeat, duplicate tile, non-lodging Stay,
non-category photo): first card photo of the tile's own category that is not the hero, not used by
another tile, and (Stay) not in tile_nonlodging.txt; else no image. Usage: tile_fix.py <root> <pref>"""
import re, sys, glob, os, pathlib, importlib.util
spec = importlib.util.spec_from_file_location('tc', pathlib.Path(__file__).with_name('tile_check.py'))
root, pref = sys.argv[1], sys.argv[2]
sys.argv = [sys.argv[0], root, pref, '--lib']; tc = importlib.util.module_from_spec(spec); spec.loader.exec_module(tc)
b = os.path.basename
for idx in sorted(glob.glob(f'{root}/{pref}/*/index.html')):
    src = open(idx).read()
    if 'class="hub-tiles"' not in src: continue
    cover = b((re.search(r'<figure class="cover"><img src="([^"]+)"', src) or [0, ''])[1] or '')
    tiles = re.findall(r'<a class="hub-tile" href="([^"]+)/">(?:<img src="([^"]+)")?', src)
    used = {}; changed = False
    for href, im in tiles:
        d = pathlib.Path(idx).parent / href
        pages = [d / 'index.html'] + ([pathlib.Path(p) for p in sorted(glob.glob(str(d / '*' / 'index.html')))] if href == 'eat' else [])
        cards = [c for p in pages if p.exists() for c in re.findall(r'<img class="thumb" src="/media/([^"]+)" alt="([^"]*)" width="(\d+)" height="(\d+)"', p.read_text())]
        def ok(f): return not (cover and tc.same(f, cover)) and not any(tc.same(f, u) for u in used.values()) and not (href == 'stay' and f in tc.NONLODGE)
        cur = b(im) if im else None
        if cur and ok(cur) and cur in {c[0] for c in cards}: used[href] = cur; continue
        c = next((c for c in cards if ok(c[0])), None)
        new = f'<img src="../../media/{c[0]}" alt="{c[1]}" width="{c[2]}" height="{c[3]}"  decoding="async">' if c else ''
        src = re.sub(rf'(<a class="hub-tile" href="{re.escape(href)}/">)(?:<img [^>]*>)?', lambda m: m.group(1) + new, src, count=1)
        if c: used[href] = c[0]
        print(pathlib.Path(idx).parent.name, href, cur, '->', c and c[0]); changed = True
    if changed: open(idx, 'w').write(src)
# hub tile alt = the English name of the card the photo comes from (2026-10-14)
for idx in sorted(glob.glob(f'{root}/{pref}/*/index.html') + glob.glob(f'{root}/{pref}/*/eat/index.html')):
    d = os.path.dirname(idx); alts = {}
    for f in sorted(glob.glob(d + '/*/index.html') + glob.glob(d + '/*/*/index.html')):
        for src, alt in re.findall(r'<img class="thumb" src="/media/([^"]+)" alt="([^"]*)"', open(f).read()): alts.setdefault(src, alt)
    t = open(idx).read()
    t2 = re.sub(r'(<a class="hub-tile[^"]*" href="[^"]*/"><img src="(?:\.\./\.\./|/)media/)([^"]+)" alt="([^"]*)"',
                lambda m: m.group(1) + m.group(2) + '" alt="' + alts.get(m.group(2), m.group(3)) + '"', t)
    if t2 != t: open(idx, 'w').write(t2)
