#!/usr/bin/env python3
"""Per-town / per-lane coverage report (standing quality bar, 2026-10-15): Dining+Stay counts vs population target,
photo coverage %, English-description coverage %, neighbour labels, title-as-name, rough romaji.
Works on a built tree (worktree root or an exported gh-pages tree), so builders can gate before publishing.

  coverage_report.py --root /path/to/tree --pref ehime [--pref kochi ...]
  coverage_report.py --root /path/to/tree --lane South            # lanes from quality/audit47/per-town.csv
  coverage_report.py --root TREE --lane all --out report.md --csv report.csv --strict
Options: --min-photo 100 --min-desc 100 (percent; default 100) ; --strict -> exit 1 when any town is below."""
import argparse, csv, glob, html as H, json, os, re, sys
from pathlib import Path
sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as S
P1 = Path('/workspace/p1'); CJK = S.CJK
ap = argparse.ArgumentParser()
ap.add_argument('--root', required=True); ap.add_argument('--pref', action='append', default=[]); ap.add_argument('--lane', default='')
ap.add_argument('--min-photo', type=float, default=float(os.environ.get('BJ_MIN_PHOTO_PCT', 100)))
ap.add_argument('--min-desc', type=float, default=float(os.environ.get('BJ_MIN_DESC_PCT', 100)))
ap.add_argument('--out', default=''); ap.add_argument('--csv', default=''); ap.add_argument('--strict', action='store_true')
ap.add_argument('--nophoto-log', default=os.environ.get('BJ_NOPHOTO_LOG', str(P1 / 'photos-5pref/no-photo-found.csv')))
A = ap.parse_args(); root = Path(A.root)
lanes = {}; pt = P1 / 'quality/audit47/per-town.csv'
if pt.exists():
    for r in csv.DictReader(open(pt)): lanes[r['key']] = r['lane']
prefs = A.pref or sorted({k.split('/')[0] for k, l in lanes.items() if A.lane in ('', 'all', l)} or {p.name for p in root.iterdir() if p.is_dir()})
logged = set()
for f in {A.nophoto_log, *glob.glob(str(P1 / 'partials-build/data/*/no-photo-found.csv'))}:
    try:
        for r in csv.reader(open(f, encoding='utf-8')):
            logged.update(x.strip() for x in r if x.startswith('http'))
    except OSError: pass
ps = {}
for f in glob.glob(str(P1 / 'partials-build/data/*/_photo_search.json')): ps.update(json.load(open(f)))
rows = []
for pref in prefs:
    for idx in sorted(glob.glob(f'{root}/{pref}/*/index.html')):
        slug = idx.split('/')[-2]; key = f'{pref}/{slug}'
        if A.lane not in ('', 'all') and lanes.get(key) not in (A.lane, None): continue
        txt = ''.join(Path(f).read_text(errors='replace') for f in [idx] + glob.glob(f'{root}/{pref}/{slug}/*/index.html') + glob.glob(f'{root}/{pref}/{slug}/*/*/index.html'))
        cards = []
        for li in re.findall(r'<li>\s*<a href="([^"]+)">(.*?)</li>', txt, re.S):
            href, body = li
            kind = 'dining' if 'tabelog.com' in href else 'stay' if re.search(r'jalan\.net|ikyu\.com|ikkyu|rakuten', href) else None
            if kind: cards.append((kind, href, body))
        seen = {}
        for k, h, b in cards: seen.setdefault(h, (k, h, b))
        cards = list(seen.values())
        d = [c for c in cards if c[0] == 'dining']; s = [c for c in cards if c[0] == 'stay']
        ph = sum('class="thumb"' in c[2] for c in cards)
        just = sum(1 for c in cards if 'class="thumb"' not in c[2] and (c[1] in logged or (ps.get(c[1]) or {}).get('tried')))
        de = sum(1 for c in cards if re.search(r'place-desc">([^<]+)', c[2]) and not CJK.search(re.search(r'place-desc">([^<]+)', c[2]).group(1)))
        names = re.findall(r'place-(?:name|blurb)">([^<]*)', txt)
        tn = sum(S.title_as_name(H.unescape(x)) for x in names)
        rough = sum(S.rough_romaji(H.unescape(x)) for x in re.findall(r'place-blurb">([^<]*)', txt))
        nb = sum('<!-- neighbour:' in c[2] for c in s)
        pop = S.town_pop(pref, slug); td, ts = S.target_dining(pop), S.target_stay(pop)
        n = len(cards)
        rows.append(dict(key=key, lane=lanes.get(key, '?'), pop=pop or 0, dining=len(d), dining_target=td, stay=len(s), stay_target=ts, cards=n,
                         photo_pct=round(100 * ph / n, 1) if n else 100.0, photo_pct_justified=round(100 * (ph + just) / n, 1) if n else 100.0,
                         desc_pct=round(100 * de / n, 1) if n else 100.0, neighbour_stays=nb, title_as_name=tn, rough_romaji=rough,
                         ok=(len(d) >= td or '<!-- source-exhausted: dining' in txt) and (n == 0 or ((ph + just) / n * 100 >= A.min_photo and de / n * 100 >= A.min_desc))))
rows.sort(key=lambda r: (r['lane'], r['photo_pct_justified'], r['desc_pct']))
tot = lambda k: sum(r[k] for r in rows)
L = [f'# Coverage report — {A.lane or "prefs " + ", ".join(prefs)} ({len(rows)} towns, root {root})\n',
     f'Standing bar: photo ≥ {A.min_photo:g}% (justified no-photo = sources tried, logged), English description ≥ {A.min_desc:g}%, Dining ≥ population target (or source exhausted).\n']
for lane in sorted({r['lane'] for r in rows}):
    rs = [r for r in rows if r['lane'] == lane]; c = sum(r['cards'] for r in rs)
    L.append(f"- **{lane}**: {len(rs)} towns, Dining {sum(r['dining'] for r in rs)}/{sum(r['dining_target'] for r in rs)} target, Stay {sum(r['stay'] for r in rs)}/{sum(r['stay_target'] for r in rs)}, "
             f"photo {round(sum(r['photo_pct']*r['cards'] for r in rs)/c,1) if c else 100}%, EN desc {round(sum(r['desc_pct']*r['cards'] for r in rs)/c,1) if c else 100}%, "
             f"towns below bar: {sum(not r['ok'] for r in rs)}")
L += ['', '| Town | Lane | Pop | Dining/target | Stay/target | Photo % | Photo % (justified) | EN desc % | Neighbour stays | Title-as-name | Rough romaji | OK |', '|---|---|---:|---|---|---:|---:|---:|---:|---:|---:|---|']
for r in rows:
    L.append(f"| {r['key']} | {r['lane']} | {r['pop']:,} | {r['dining']}/{r['dining_target']} | {r['stay']}/{r['stay_target']} | {r['photo_pct']} | {r['photo_pct_justified']} | {r['desc_pct']} | {r['neighbour_stays']} | {r['title_as_name']} | {r['rough_romaji']} | {'yes' if r['ok'] else '**NO**'} |")
out = '\n'.join(L) + '\n'
if A.out: Path(A.out).write_text(out)
else: print(out if len(rows) <= 60 else '\n'.join(L[:12]) + f'\n… {len(rows)} towns (use --out)')
if A.csv:
    with open(A.csv, 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ['key']); w.writeheader(); w.writerows(rows)
bad = sum(not r['ok'] for r in rows)
print(f'coverage: {len(rows)} towns, {bad} below the bar', file=sys.stderr)
sys.exit(1 if (A.strict and bad) else 0)
