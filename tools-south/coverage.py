#!/usr/bin/env python3
"""coverage.py - per-town dining / stay counts vs population-scaled targets, written as CSV.

  coverage.py --root TREE --pref tottori [--pref shimane ...] [--csv out.csv] [--md out.md]

Targets (Emma's audit method):
  dining: pop >= 50k -> pop/1000 (min 50, max 100); 10-50k -> pop/750 (10-40); < 10k -> pop/500 (3-15)
  stays : < 20k -> 1; < 100k -> 3; else pop/20000 capped at 30
Population source: tools-south/popmap.json (e-Stat census, rebuilt from quality/audit47). Towns missing from it get the legacy
generic target (24 dining / 12 stay) and pop_source=none; --wikidata tries Wikidata (bjlib.wikidata_pop) for those first.
Counting reads the built pages: unique cards (place-name li) on <pref>/<slug>/eat/<genre>/ and /stay/.
"""
import argparse, csv, html as H, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bjlib as L

LI = re.compile(r'<li><a href="([^"]*)"><p class="place-name">([^<]*)</p>(.*?)</li>', re.S)

def cards_in(files):
    seen = {}
    for f in files:
        try: t = Path(f).read_text(encoding='utf-8', errors='replace')
        except OSError: continue
        for href, name, rest in LI.findall(t):
            seen.setdefault((H.unescape(name), href), rest)
    return seen

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default=L.DEFAULT_TREE); ap.add_argument('--pref', action='append', required=True)
    ap.add_argument('--csv'); ap.add_argument('--md'); ap.add_argument('--wikidata', action='store_true')
    A = ap.parse_args(); root = Path(A.root); rows = []
    for pref in A.pref:
        for d in sorted((root / pref).iterdir()):
            if not (d / 'index.html').exists() or not ((d / 'eat').exists() or (d / 'stay').exists()): continue
            slug = d.name; pm = L.popmap().get(f'{pref}/{slug}') or {}
            pop, src = pm.get('pop'), ('popmap(e-Stat)' if pm.get('pop') else 'none')
            if pop is None and A.wikidata and pm.get('code'):
                pop = L.wikidata_pop(pm['code'][:5]); src = 'wikidata' if pop else 'none'
            dn = cards_in(sorted((d / 'eat').glob('*/index.html'))); sn = cards_in([d / 'stay' / 'index.html'])
            ph = sum('class="thumb"' in r for r in dn.values()); sph = sum('class="thumb"' in r for r in sn.values())
            osm = sum('osm_url=' in r for r in dn.values()); n = len(dn)
            td, ts = L.target_dining(pop), L.target_stay(pop)
            rows.append(dict(pref=pref, slug=slug, ja=pm.get('ja', ''), pop=pop or '', pop_source=src, dining=n, dining_target=td,
                             dining_pct=round(100 * n / td) if td else 100, dining_gap=max(0, td - n), dining_photo=ph,
                             dining_photo_share=round(100 * ph / n) if n else 0, dining_osm=osm, stay=len(sn), stay_target=ts,
                             stay_pct=round(100 * len(sn) / ts) if ts else 100, stay_gap=max(0, ts - len(sn)),
                             stay_photo_share=round(100 * sph / len(sn)) if sn else 0))
    if not rows: sys.exit('no towns found under ' + str(root))
    if A.csv:
        with open(A.csv, 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    lines = ['| pref/town | pop | dining / target | photo % | stays / target |', '|---|---:|---|---:|---|']
    for r in rows:
        lines.append(f"| {r['pref']}/{r['slug']} | {r['pop']} | {r['dining']} / {r['dining_target']} ({r['dining_pct']}%) | {r['dining_photo_share']} | {r['stay']} / {r['stay_target']} |")
    tot = lambda k: sum(r[k] for r in rows)
    lines.append(f"\nTotal: dining {tot('dining')} / {tot('dining_target')}, stays {tot('stay')} / {tot('stay_target')}, towns below dining target "
                 f"{sum(r['dining_gap'] > 0 for r in rows)}, towns with unknown population {sum(r['pop_source'] == 'none' for r in rows)}")
    out = '\n'.join(lines)
    print(out)
    if A.md: Path(A.md).write_text(out + '\n')

if __name__ == '__main__':
    main()
