#!/usr/bin/env python3
"""check_live X18: add the 'Day to day' hub tile to municipality hubs that lack it, but ONLY where <town>/day-to-day/index.html
exists on disk (no page is invented).  Hubs without such a page are listed in the report (action 'no-page').
Tile = same markup as the generator's wide day-to-day tile: image = first photo on the day-to-day page that is not the cover or
another tile's image (X21), else no <img>; count from the page's cards.  Idempotent.  tokyo/ is skipped.
Usage: python3 scripts/day_to_day_tile.py --root . [--pref slug] [--check|--dry-run] [--report out.csv]
"""
import argparse, csv, re, sys
from pathlib import Path
SKIP = {'media', 'assets', 'data', 'scripts', 'go', 'fonts', 'sitemaps', 'photo-credits', 'tokyo'}
COVER = re.compile(r'<figure class="cover"><img src="([^"]+)"')
HREF = re.compile(r'<a class="hub-tile[^>]*href="([^"]+)"')
IMG = re.compile(r'<img [^>]*>')
def base(u): return u.split('?')[0].rstrip('/').rsplit('/', 1)[-1]
def attr(t, n):
    m = re.search(r'\b' + n + r'="([^"]*)"', t); return m.group(1) if m else None
def esc(s): return s.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;')

def has_tile(s):
    if any('day-to-day' in h for h in HREF.findall(s)): return True
    return any(re.sub(r'[^a-z]', '', x.lower()).startswith('daytoday') for x in re.findall(r'hub-tile-name">([^<]*)', s))

def process(hub, rows, pref):
    s = hub.read_text(encoding='utf-8')
    if 'ul class="hub-tiles' not in s or has_tile(s): return None
    page = hub.parent / 'day-to-day' / 'index.html'
    if not page.is_file():
        rows.append((str(hub), pref, 'no-page', '')); return None
    t = page.read_text(encoding='utf-8')
    n = len(re.findall(r'<li>.*?</li>', re.search(r'<ul class="place-list">(.*?)</ul>', t, re.S).group(1) if re.search(r'<ul class="place-list">', t) else '', re.S))
    if n == 0:
        rows.append((str(hub), pref, 'no-page', 'day-to-day page has no cards')); return None
    c = COVER.search(s); used = {base(c.group(1))} if c else set()
    used |= {base(attr(i, 'src') or '') for i in IMG.findall(re.search(r'<ul class="hub-tiles.*?</ul>', s, re.S).group(0))}
    pic = ''
    for i in IMG.findall(t):
        src = attr(i, 'src') or ''
        if 'class="thumb"' in i and '/media/' in src and base(src) not in used:
            w, h = attr(i, 'width'), attr(i, 'height')
            pic = f'<img src="{src}" alt="{esc(attr(i, "alt") or "")}"' + (f' width="{w}" height="{h}"' if w and h else '') + ' decoding="async" loading="lazy">'
            break
    plural = f'{n} place' if n == 1 else f'{n:,} places'
    tile = (f'<li style="grid-column:1/-1"><a class="hub-tile" style="aspect-ratio:21/9" href="day-to-day/">{pic}'
            f'<span class="hub-tile-label"><span class="hub-tile-name">Day to day</span><span class="hub-tile-count">{plural}</span></span></a></li>')
    m = re.search(r'(<ul class="hub-tiles[^"]*">.*?)(</ul>)', s, re.S)
    rows.append((str(hub), pref, 'tile-added', 'photo' if pic else 'no-photo'))
    return s[:m.end(1)] + tile + s[m.end(1):]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default='.'); ap.add_argument('--pref')
    ap.add_argument('--check', action='store_true'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--report')
    a = ap.parse_args(); root = Path(a.root).resolve(); rows = []; changed = 0
    prefs = [a.pref] if a.pref else sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith('.') and d.name not in SKIP)
    for pref in prefs:
        for hub in sorted((root / pref).glob('*/index.html')):
            r = process(hub, rows, pref)
            if r is not None:
                changed += 1
                if not (a.check or a.dry_run): hub.write_text(r, encoding='utf-8')
    rows = [(str(Path(r[0]).relative_to(root)),) + r[1:] for r in rows]
    nop = sum(1 for r in rows if r[2] == 'no-page')
    print(f'tiles {"to add" if a.check or a.dry_run else "added"}: {changed}; hubs without day-to-day page (listed, not invented): {nop}')
    if a.report:
        with open(a.report, 'w', newline='') as f: w = csv.writer(f); w.writerow(['hub', 'pref', 'action', 'note']); w.writerows(rows)
    sys.exit(1 if (a.check and changed) else 0)
if __name__ == '__main__': main()
