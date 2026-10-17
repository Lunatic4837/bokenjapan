#!/usr/bin/env python3
"""Refresh the bj-nav block (More in <Town>) of town sub-pages whose nav is stale: it links to a section page that does not
exist on disk (404) or the sub-page lacks the 'Nearby in' line (check_live X20 / R8.hub-sub, e.g. /osaka/chihayaakasaka/eat/).
The block is produced by the unchanged scripts/ai_friendly.py generator, run on a scratch copy of only that prefecture, and
only the <!-- bj-nav -->..<!-- /bj-nav --> block of stale pages is copied back (no dates, JSON-LD or other blocks touched).
Idempotent: after the refresh no page is stale, so a second run changes nothing.  tokyo/ is skipped.
Usage: python3 scripts/nav_refresh.py --root . [--pref slug] [--check|--dry-run] [--report out.csv]
"""
import argparse, csv, re, shutil, subprocess, sys, tempfile
from pathlib import Path
NAV = re.compile(r'<!-- bj-nav -->.*?<!-- /bj-nav -->', re.S)
SKIP = {'media', 'assets', 'data', 'scripts', 'go', 'fonts', 'sitemaps', 'photo-credits', 'tokyo'}

def stale(root, p):
    t = p.read_text(encoding='utf-8', errors='replace'); m = NAV.search(t)
    if not m: return None
    reasons = []
    for h in re.findall(r'href="(/[^"#]*)"', m.group(0)):
        q = root / h.strip('/')
        if h != '/' and not (q / 'index.html').is_file(): reasons.append('dead-link ' + h)
    if len(p.relative_to(root).parts) >= 4 and 'Nearby in' not in m.group(0): reasons.append('no-nearby')
    return reasons or None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default='.'); ap.add_argument('--pref')
    ap.add_argument('--check', action='store_true'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--report')
    a = ap.parse_args(); root = Path(a.root).resolve(); rows = []; per = {}
    prefs = [a.pref] if a.pref else sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith('.') and d.name not in SKIP)
    for pref in prefs:
        bad = {}
        for p in (root / pref).rglob('index.html'):
            if 'photo-credits' in p.parts: continue
            r = stale(root, p)
            if r: bad[p] = r
        if not bad: continue
        tmp = Path(tempfile.mkdtemp(prefix='navref-'))
        try:
            shutil.copytree(root / pref, tmp / pref)
            for f in ('index.html',): shutil.copy(root / f, tmp / f)
            for d in ('scripts', 'data'):
                if (root / d).is_dir(): shutil.copytree(root / d, tmp / d)
            r = subprocess.run([sys.executable, 'scripts/ai_friendly.py', '--root', '.'], cwd=tmp, capture_output=True, text=True)
            if r.returncode: print('generator failed for', pref, r.stderr[-300:]); sys.exit(2)
            for p, why in sorted(bad.items()):
                rel = p.relative_to(root); nb = NAV.search((tmp / rel).read_text(encoding='utf-8'))
                if not nb: rows.append((str(rel), pref, ';'.join(why), 'no-generated-nav')); continue
                t = p.read_text(encoding='utf-8'); n = NAV.sub(lambda m: nb.group(0), t, count=1)
                if n != t:
                    per[pref] = per.get(pref, 0) + 1; rows.append((str(rel), pref, ';'.join(why), 'refreshed'))
                    if not (a.check or a.dry_run): p.write_text(n, encoding='utf-8')
        finally: shutil.rmtree(tmp, ignore_errors=True)
    for k, v in sorted(per.items()): print(f'{k}\t{v}')
    print(f'pages {"needing change" if a.check or a.dry_run else "changed"}: {sum(per.values())}')
    if a.report:
        with open(a.report, 'w', newline='') as f: w = csv.writer(f); w.writerow(['page', 'pref', 'stale_reason', 'action']); w.writerows(rows)
    sys.exit(1 if (a.check and per) else 0)
if __name__ == '__main__': main()
