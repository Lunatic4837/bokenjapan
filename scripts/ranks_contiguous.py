#!/usr/bin/env python3
"""Close gaps in the '#N ranked in <Town>' numbering of a town's Dining cards (check_live R4.other 'rank #N+1 at position N').

Cause: the original ranking numbered every Tabelog/TripAdvisor card of the town; the hub split later moved non-food cards
(supermarkets, convenience stores, post offices...) to day-to-day/ (and some to stay/), leaving their numbers behind as gaps
in the Dining sequence.  Fix: renumber the Dining cards 1..k in their existing rank order (relative order preserved; no card
text other than the number in the line-3 label changes).  Grouping mirrors check_live hub_merged_soup (day-to-day -> Sights,
jalan/ikyu/stay -> Stay, tabelog/ta/osm/official source -> Dining).  Towns with tied ranks are NOT touched and are reported.
Idempotent (second run = zero diff).  --check exits 1 if a change is needed; --dry-run prints; --report CSV.
Usage: python3 scripts/ranks_contiguous.py --root . [--pref slug] [--check|--dry-run] [--report out.csv]
"""
import argparse, csv, re, sys
from pathlib import Path

SKIP = {'media', 'assets', 'data', 'scripts', 'go', 'fonts', 'sitemaps', 'photo-credits'}
LI = re.compile(r'<li>.*?</li>', re.S)
META = re.compile(r'(<p class="place-meta">)#(\d+)( ranked in )')
STAYSRC = re.compile(r"sources: [^>]*(jalan_url|ikk?yu_url)=")
DINSRC = re.compile(r"sources: [^>]*(tabelog_url|ta_url|osm_url|official_url)=")

def group(sec, li):
    if sec == 'day-to-day': return 'Sights'
    if STAYSRC.search(li) or sec == 'stay': return 'Stay'
    if DINSRC.search(li): return 'Dining'
    return 'Sights'

def town(td, report):
    hub = td / 'index.html'
    if 'ul class="hub-tiles' not in hub.read_text(encoding='utf-8', errors='replace'): return {}
    cards, texts = [], {}
    for p in sorted(td.rglob('index.html')):
        if p == hub: continue
        t = texts[p] = p.read_text(encoding='utf-8')
        sec = p.relative_to(td).parts[0]
        for m in LI.finditer(t):
            li = m.group(0)
            if 'class="place-meta"' not in li: continue
            mm = META.search(li)
            if group(sec, li) == 'Dining' and mm:
                cards.append((int(mm.group(2)), p, m.start() + mm.start(2), m.start() + mm.end(2)))
    if not cards: return {}
    ranks = [c[0] for c in cards]
    if sorted(ranks) == list(range(1, len(ranks) + 1)): return {}
    if len(set(ranks)) != len(ranks):
        report.append((str(td), 'skipped', 'tied/duplicate ranks in Dining group'))
        return {}
    order = sorted(cards, key=lambda c: c[0])
    edits = {}
    for new, (old, p, s, e) in enumerate(order, 1):
        if new != old: edits.setdefault(p, []).append((s, e, str(new)))
    out = {}
    for p, es in edits.items():
        t = texts[p]
        for s, e, v in sorted(es, reverse=True): t = t[:s] + v + t[e:]
        out[p] = t
    report.append((str(td), 'renumbered', f'{len(order)} Dining cards, {sum(len(v) for v in edits.values())} labels changed, gaps closed (max rank {max(ranks)} -> {len(ranks)})'))
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', default='.'); ap.add_argument('--pref'); ap.add_argument('--check', action='store_true')
    ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--report')
    a = ap.parse_args(); root = Path(a.root).resolve()
    prefs = [a.pref] if a.pref else sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith('.') and d.name not in SKIP)
    report, towns, files, per = [], 0, 0, {}
    for pref in prefs:
        for td in sorted((root / pref).iterdir()):
            if not (td.is_dir() and (td / 'index.html').exists()): continue
            out = town(td, report)
            if out:
                towns += 1; files += len(out); per[pref] = per.get(pref, [0, 0]); per[pref][0] += 1; per[pref][1] += len(out)
                if not (a.check or a.dry_run):
                    for p, t in out.items(): p.write_text(t, encoding='utf-8')
    for k, (t, f) in sorted(per.items()): print(f'{k}\ttowns {t}\tfiles {f}')
    print(f'towns {"needing change" if a.check or a.dry_run else "changed"}: {towns}; files: {files}; skipped: {sum(1 for r in report if r[1]=="skipped")}')
    if a.report:
        with open(a.report, 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['town_dir', 'action', 'detail']); w.writerows([(str(Path(r[0]).relative_to(root)),) + r[1:] for r in report])
    sys.exit(1 if (a.check and towns) else 0)

if __name__ == '__main__': main()
