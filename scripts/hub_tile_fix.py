#!/usr/bin/env python3
"""Hub tile images: no tile may repeat the hero/cover image (check_live X21) or another tile's image.

For each municipality hub (<pref>/<town>/index.html with figure.cover + ul.hub-tiles) a tile whose <img>
has the cover's file name (or the same file name as an earlier tile) is re-pointed to the first photo on its own
sub-page (stay/ eat/ do/ see/ day-to-day/) that is not the cover and not used by another tile. Photos are only
taken from this town's own sub-pages (nothing invented). If no distinct photo exists the <img> is dropped and the
tile renders as the plain dark seal tile (styles.css .hub-tile background), never a repeated photo.
Idempotent (second run = zero diff).  --check exits 1 if any change is needed; --dry-run prints; --report FILE writes CSV.
Usage: python3 scripts/hub_tile_fix.py --root . [--pref slug] [--check|--dry-run] [--report out.csv]
"""
import argparse, csv, os, re, sys
from pathlib import Path

COVER = re.compile(r'<figure class="cover"><img src="([^"]+)"')
TILE = re.compile(r'(<a class="hub-tile[^"]*" href="([^"]+)">)(<img [^>]*>)?')
IMG = re.compile(r'<img [^>]*>')
SKIP = {'media', 'assets', 'data', 'scripts', 'go', 'fonts', 'sitemaps', 'photo-credits'}

def base(u): return u.split('?')[0].rstrip('/').rsplit('/', 1)[-1]
def attr(tag, n):
    m = re.search(r'\b' + n + r'="([^"]*)"', tag); return m.group(1) if m else None
def setattr_(tag, n, v):
    if re.search(r'\b' + n + r'="[^"]*"', tag): return re.sub(r'\b' + n + r'="[^"]*"', lambda m: f'{n}="{v}"', tag, count=1)
    return tag.replace('<img ', f'<img {n}="{v}" ', 1)

def candidates(hubdir, href):
    p = hubdir / href / 'index.html'
    if not p.is_file(): return []
    s = p.read_text(encoding='utf-8', errors='replace')
    return [t for t in IMG.findall(s) if 'class="thumb"' in t and '/media/' in (attr(t, 'src') or '')]

def process(path, report):
    s = path.read_text(encoding='utf-8')
    c = COVER.search(s)
    if not c or 'class="hub-tiles' not in s: return None
    cov = base(c.group(1)); hubdir = path.parent
    tiles = list(TILE.finditer(s))
    if not tiles: return None
    used, bad = {cov}, []
    for i, m in enumerate(tiles):
        if not m.group(3): continue
        b = base(attr(m.group(3), 'src') or '')
        if b in used: bad.append(i)
        else: used.add(b)
    if not bad: return None
    repl = {}
    for i in bad:
        m = tiles[i]; new = None; why = 'hero' if base(attr(m.group(3), 'src')) == cov else 'dup-tile'
        for t in candidates(hubdir, m.group(2)):
            b = base(attr(t, 'src') or '')
            if b not in used:
                new = t; used.add(b); break
        if new:
            tag = m.group(3)
            tag = setattr_(tag, 'src', attr(new, 'src')); tag = setattr_(tag, 'alt', attr(new, 'alt') or '')
            for k in ('width', 'height'):
                v = attr(new, k)
                if v: tag = setattr_(tag, k, v)
            repl[i] = tag; report.append((str(path.relative_to(ROOT)), m.group(2), why, 'photo', base(attr(new, 'src'))))
        else:
            repl[i] = ''; report.append((str(path.relative_to(ROOT)), m.group(2), why, 'seal-placeholder', ''))
    out, last = [], 0
    for i, m in enumerate(tiles):
        if i in repl:
            out.append(s[last:m.start(3)]); out.append(repl[i]); last = m.end(3)
    out.append(s[last:])
    return ''.join(out)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.'); ap.add_argument('--pref'); ap.add_argument('--check', action='store_true')
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--report')
    global ROOT
    a = ap.parse_args(); root = ROOT = Path(a.root).resolve()
    prefs = [a.pref] if a.pref else sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith('.') and d.name not in SKIP)
    changed, report, per = 0, [], {}
    for pref in prefs:
        for p in sorted((root / pref).glob('*/index.html')):
            r = process(p, report)
            if r is not None:
                changed += 1; per[pref] = per.get(pref, 0) + 1
                if not (a.check or a.dry_run): p.write_text(r, encoding='utf-8')
    for k, v in sorted(per.items()): print(f'{k}\t{v}')
    print(f'hub pages {"needing change" if a.check or a.dry_run else "changed"}: {changed}; tiles: {len(report)} '
          f'(photo {sum(1 for r in report if r[3]=="photo")}, seal {sum(1 for r in report if r[3]=="seal-placeholder")})')
    if a.report:
        with open(a.report, 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['page', 'tile', 'reason', 'action', 'new_image']); w.writerows(report)
    sys.exit(1 if (a.check and changed) else 0)

if __name__ == '__main__': main()
