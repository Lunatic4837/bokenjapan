#!/usr/bin/env python3
"""check_live X1.note: remove leaked internal draft notes from HTML comments.

The municipality-boundary attribution comment (<!-- Municipality boundaries: MLIT ... -->) carries a line
'Note: local unpublished draft only; GSI reproduction filing gates ... (Do not commit this directory ...)'.
Only comment LINES that match the checker's INTERNAL_NOTE_RE are removed; the licence/citation lines and every other
comment (photo-credit, desc-source, structural markers) are kept. A comment consisting only of such lines is removed whole.
tokyo/ is skipped (use --include-tokyo to override). Idempotent (second run = zero diff).
Usage: python3 scripts/strip_draft_notes.py --root . [--pref slug] [--check|--dry-run] [--include-tokyo] [--report out.csv]
"""
import argparse, csv, re, sys
from pathlib import Path
NOTE = re.compile(r"unpublished draft|do not commit|\bTODO\b|\bFIXME\b|gated before public|local unpublished|not ready|WIP\b", re.I)
KEYS = ('unpublished draft', 'do not commit', 'todo', 'fixme', 'gated before public', 'local unpublished', 'not ready', 'wip')
CMT = re.compile(r'<!--(.*?)-->', re.S)
SKIP = {'media', 'assets', 'data', 'scripts', 'go', 'fonts', 'sitemaps'}

def clean(s):
    def fix(m):
        body = m.group(1)
        if not NOTE.search(body): return m.group(0)
        if m.group(0).startswith('<!-- photo-credit') or body.lstrip().startswith(('photo-credit', 'desc-source', 'sources:')): return m.group(0)
        lines = body.split('\n'); keep = [l for l in lines if not NOTE.search(l)]
        if not any(l.strip() for l in keep): return ''
        return '<!--' + '\n'.join(keep) + '-->'
    return CMT.sub(fix, s)

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default='.'); ap.add_argument('--pref')
    ap.add_argument('--check', action='store_true'); ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--include-tokyo', action='store_true'); ap.add_argument('--report')
    a = ap.parse_args(); root = Path(a.root).resolve(); rows = []; per = {}
    prefs = [a.pref] if a.pref else sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith('.') and d.name not in SKIP)
    skipped_tokyo = 0
    for pref in prefs:
        for p in sorted((root / pref).rglob('*.html')):
            t = p.read_text(encoding='utf-8', errors='replace')
            tl = t.lower()
            if not any(k in tl for k in KEYS) or not NOTE.search(t): continue
            n = clean(t)
            if n == t: continue
            if pref == 'tokyo' and not a.include_tokyo:
                skipped_tokyo += 1; rows.append((str(p.relative_to(root)), pref, 'skipped-tokyo')); continue
            per[pref] = per.get(pref, 0) + 1; rows.append((str(p.relative_to(root)), pref, 'stripped'))
            if not (a.check or a.dry_run): p.write_text(n, encoding='utf-8')
    for k, v in sorted(per.items()): print(f'{k}\t{v}')
    print(f'pages {"needing change" if a.check or a.dry_run else "changed"}: {sum(per.values())}; tokyo skipped: {skipped_tokyo}')
    if a.report:
        with open(a.report, 'w', newline='') as f: w = csv.writer(f); w.writerow(['page', 'pref', 'action']); w.writerows(rows)
    sys.exit(1 if (a.check and per) else 0)
if __name__ == '__main__': main()
