#!/usr/bin/env python3
"""Sweep town hubs: each hub tile image must come from a card in that tile's category,
the See tile must not repeat the hero (cover), and the Stay tile must not be a photo listed
as non-lodging in tile_nonlodging.txt (visually reviewed Stay-card photos showing food etc.).
Usage: tile_check.py <root> <pref>"""
import re, sys, glob, os, pathlib
root, pref = pathlib.Path(sys.argv[1]), sys.argv[2]
NONLODGE = set()
nl = pathlib.Path(__file__).with_name('tile_nonlodging.txt')
if nl.exists(): NONLODGE = {l.split('#')[0].strip() for l in nl.read_text().splitlines() if l.split('#')[0].strip()}
b = lambda s: os.path.basename(s)
from PIL import Image
_h = {}
def dhash(f):
    if f not in _h:
        try:
            im = Image.open(root / 'media' / f).convert('L').resize((9, 8)); px = list(im.tobytes())
            _h[f] = sum(1 << i for i in range(64) if px[(i // 8) * 9 + i % 8] > px[(i // 8) * 9 + i % 8 + 1])
        except Exception: _h[f] = None
    return _h[f]
def same(a, c): return a == c or (dhash(a) is not None and dhash(c) is not None and bin(dhash(a) ^ dhash(c)).count('1') <= int(os.environ.get('DH',4)))
def card_imgs(html): return {b(m) for m in re.findall(r'<img class="thumb" src="([^"]+)"', html)}
def main():
    viol = []; hubs = 0
    for idx in sorted(glob.glob(str(root / pref / '*' / 'index.html'))):
        town = pathlib.Path(idx).parent.name; src = open(idx).read()
        if 'class="hub-tiles"' not in src: continue
        hubs += 1
        cover = b((re.search(r'<figure class="cover"><img src="([^"]+)"', src) or [0, ''])[1] or '')
        seen = []
        for href, im in re.findall(r'<a class="hub-tile" href="([^"]+)/">(?:<img src="([^"]+)")?', src):
            if not im: continue
            im = b(im); d = pathlib.Path(idx).parent / href
            pages = [d / 'index.html'] + ([pathlib.Path(p) for p in glob.glob(str(d / '*' / 'index.html'))] if href == 'eat' else [])
            cards = set().union(*[card_imgs(p.read_text()) for p in pages if p.exists()])
            if im not in cards: viol.append((town, href, im, 'not a card photo of this category'))
            if cover and same(im, cover): viol.append((town, href, im, 'tile repeats hero'))
            if any(same(im, x) for x in seen): viol.append((town, href, im, 'duplicate tile photo'))
            seen.append(im)
            if href == 'stay' and im in NONLODGE: viol.append((town, href, im, 'Stay tile is not a lodging photo'))
    for v in viol: print('VIOLATION', *v)
    print(f'hubs={hubs} violations={len(viol)}')
if '--lib' not in sys.argv: main()
