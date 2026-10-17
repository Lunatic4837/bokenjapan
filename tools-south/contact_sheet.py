#!/usr/bin/env python3
"""contact_sheet.py - make labelled contact sheets from a photo_check --json report (for quick human/vision review).
  contact_sheet.py report.json outprefix [--per 24] [--only-flagged]"""
import argparse, hashlib, json, sys
from pathlib import Path
from PIL import Image, ImageDraw
CACHE = Path('/workspace/p1/scratch/photo-cache')
ap = argparse.ArgumentParser(); ap.add_argument('report'); ap.add_argument('out'); ap.add_argument('--per', type=int, default=24)
ap.add_argument('--only-flagged', action='store_true'); ap.add_argument('--cols', type=int, default=6)
A = ap.parse_args()
rows = json.load(open(A.report))
seen, items = set(), []
for r in rows:
    if r['src'] in seen or (A.only_flagged and not (r['flags'] or r['soft'])): continue
    seen.add(r['src'])
    p = CACHE / hashlib.sha1(r['src'].lstrip('/').encode()).hexdigest()[:2] / Path(r['src']).name
    if p.exists(): items.append((r, p))
TW, TH = 250, 190
for s in range(0, len(items), A.per):
    chunk = items[s:s + A.per]; rws = (len(chunk) + A.cols - 1) // A.cols
    sheet = Image.new('RGB', (A.cols * TW, rws * (TH + 18)), 'white'); d = ImageDraw.Draw(sheet)
    for i, (r, p) in enumerate(chunk):
        try: im = Image.open(p).convert('RGB'); im.thumbnail((TW - 4, TH - 4))
        except Exception: continue
        x, y = (i % A.cols) * TW, (i // A.cols) * (TH + 18)
        sheet.paste(im, (x + 2, y + 2)); d.text((x + 3, y + TH), f"{s + i}:{r['town'][:9]} {Path(r['src']).stem[-12:]} {r['w']}", fill='black')
    sheet.save(f'{A.out}-{s // A.per + 1}.jpg', quality=70)
json.dump([{'i': s + i, 'src': r['src'], 'town': r['town'], 'name': r['name']} for i, (r, p) in enumerate(items) for s in [0]], open(A.out + '-index.json', 'w'), ensure_ascii=False)
print(len(items), 'images,', (len(items) + A.per - 1) // A.per, 'sheets')
