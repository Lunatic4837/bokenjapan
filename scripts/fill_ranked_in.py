#!/usr/bin/env python3
"""R4: fill empty town names in the line-3 card label ('#18 ranked in ' -> '#18 ranked in Ageo').

The name is the town's own page name: the town part of its H1 (exactly what check_live compares with: text before the first
', ' / ' in ' / ':').  Towns whose H1 name is only the slug with a Japanese admin suffix (…machi / …cho / …mura / …gun, e.g.
'Inamachi') are NOT filled but listed in --report (the real English name needs a lane decision / data).  tokyo/ is skipped.
Idempotent (second run = zero diff).  --check exits 1 if a change is needed; --dry-run; --report CSV.
Usage: python3 scripts/fill_ranked_in.py --root . [--pref slug] [--check|--dry-run] [--report out.csv]
"""
import argparse, csv, html, re, sys
from pathlib import Path
SKIP = {'media', 'assets', 'data', 'scripts', 'go', 'fonts', 'sitemaps', 'photo-credits', 'tokyo'}
EMPTY = re.compile(r'(<p class="place-meta">#\d+ ranked in)[ \t]*(</p>)')
norm = lambda x: re.sub(r'[^a-z0-9]', '', x.lower())

def h1name(s):
    h = re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S)
    return re.split(r",| in |:", html.unescape(re.sub(r'<[^>]+>', '', h.group(1))).strip())[0].strip() if h else ''

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default='.'); ap.add_argument('--pref')
    ap.add_argument('--check', action='store_true'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--report')
    a = ap.parse_args(); root = Path(a.root).resolve(); write = not (a.check or a.dry_run)
    prefs = [a.pref] if a.pref else sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith('.') and d.name not in SKIP)
    rows, towns, files, labels, per = [], 0, 0, 0, {}
    for pref in prefs:
        for hub in sorted((root / pref).glob('*/index.html')):
            s = hub.read_text(encoding='utf-8', errors='replace')
            if 'ul class="hub-tiles' not in s: continue
            pages = [p for p in sorted(hub.parent.rglob('index.html'))]
            todo = {}
            for p in pages:
                t = p.read_text(encoding='utf-8')
                if EMPTY.search(t): todo[p] = t
            if not todo: continue
            slug = hub.parent.name; name = h1name(s)
            if not name or (re.search(r'(machi|cho|mura|gun)$', slug) and norm(name) == norm(slug)):
                rows.append((pref, slug, name, 'not-filled', 'H1 name is slug-derived (admin suffix); real English name needs a decision'))
                continue
            towns += 1; per[pref] = per.get(pref, 0) + 1
            for p, t in todo.items():
                n = len(EMPTY.findall(t)); labels += n; files += 1
                if write: p.write_text(EMPTY.sub(lambda m: m.group(1) + ' ' + html.escape(name, quote=False) + m.group(2), t), encoding='utf-8')
            rows.append((pref, slug, name, 'filled', f'{len(todo)} pages'))
    print(' '.join(f'{k}:{v}' for k, v in sorted(per.items())))
    print(f'towns {"to fill" if not write else "filled"}: {towns}; files: {files}; labels: {labels}; not filled (listed): {sum(1 for r in rows if r[3]=="not-filled")}')
    if a.report:
        with open(a.report, 'w', newline='') as f: w = csv.writer(f); w.writerow(['pref', 'town', 'h1_name', 'action', 'note']); w.writerows(rows)
    sys.exit(1 if (a.check and files) else 0)
if __name__ == '__main__': main()
