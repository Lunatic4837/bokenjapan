#!/usr/bin/env python3
"""R4: fill empty town names in the line-3 card label ('#18 ranked in ' -> '#18 ranked in Ageo').

The name is the town's own page name: the town part of its H1 (exactly what check_live compares with: text before the first
', ' / ' in ' / ':').  Towns whose H1 name is only the slug with a Japanese admin suffix (…machi / …cho / …mura / …gun, e.g.
'Inamachi') are NOT filled but listed in --report (the real English name needs a lane decision / data).  tokyo/ is skipped.
Also fills the same empty town name in running text of the town's own pages ('Places to stay in , Saitama.' / 'ramen restaurant in , Saitama.' in
<meta description>, og/twitter, JSON-LD, card lines) and in that town's data/<pref>.json strings: ' in , <Pref>' -> ' in <Town>, <Pref>' (Saitama lane bug: ~3,500 places).
Idempotent (second run = zero diff).  --check exits 1 if a change is needed; --dry-run; --report CSV.
Usage: python3 scripts/fill_ranked_in.py --root . [--pref slug] [--check|--dry-run] [--report out.csv]
"""
import argparse, csv, html, json, re, sys
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
            gap = re.compile(r'(\bin) , (?=' + re.escape(pref.title()) + r'\b)')
            for p in pages:
                t = p.read_text(encoding='utf-8')
                if EMPTY.search(t) or gap.search(t): todo[p] = t
            slug = hub.parent.name; name = h1name(s)
            dj = root / 'data' / f'{pref}.json'
            djd = json.loads(dj.read_text(encoding='utf-8')) if dj.is_file() else None
            dj_has = bool(djd) and any(t.get('slug') == slug and gap.search(json.dumps(t, ensure_ascii=False)) for t in djd.get('towns', []))
            if not todo and not dj_has: continue
            if not name or (re.search(r'(machi|cho|mura|gun)$', slug) and norm(name) == norm(slug)):
                rows.append((pref, slug, name, 'not-filled', 'H1 name is slug-derived (admin suffix); real English name needs a decision'))
                continue
            towns += 1; per[pref] = per.get(pref, 0) + 1
            esc = html.escape(name, quote=False)
            for p, t in todo.items():
                n = len(EMPTY.findall(t)); labels += n; files += 1
                if write:
                    t2 = EMPTY.sub(lambda m: m.group(1) + ' ' + esc + m.group(2), t)
                    t2 = gap.sub(lambda m: m.group(1) + ' ' + esc + ',' + ' ', t2)
                    p.write_text(t2, encoding='utf-8')
            if dj_has:
                files += 1
                if write:
                    def fx(o):
                        if isinstance(o, str): return gap.sub(lambda m: m.group(1) + ' ' + name + ', ', o)
                        if isinstance(o, list): return [fx(x) for x in o]
                        if isinstance(o, dict): return {k: fx(v) for k, v in o.items()}
                        return o
                    djd['towns'] = [fx(t) if t.get('slug') == slug else t for t in djd['towns']]
                    dj.write_text(json.dumps(djd, ensure_ascii=False, indent=1) + '\n', encoding='utf-8')
            rows.append((pref, slug, name, 'filled', f'{len(todo)} pages' + (' + data json' if dj_has else '')))
    print(' '.join(f'{k}:{v}' for k, v in sorted(per.items())))
    print(f'towns {"to fill" if not write else "filled"}: {towns}; files: {files}; labels: {labels}; not filled (listed): {sum(1 for r in rows if r[3]=="not-filled")}')
    if a.report:
        with open(a.report, 'w', newline='') as f: w = csv.writer(f); w.writerow(['pref', 'town', 'h1_name', 'action', 'note']); w.writerows(rows)
    sys.exit(1 if (a.check and files) else 0)
if __name__ == '__main__': main()
