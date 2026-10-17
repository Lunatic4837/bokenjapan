#!/usr/bin/env python3
"""R4.other 'ranked in <Town>' != page name: the page H1/title/breadcrumb/JSON-LD carry a slug-derived town name ('Aichikonan')
while the cards (and the page's own meta description) carry the real one ('Konan').

A town is renamed ONLY when all of these hold (no name is ever invented):
  * its current H1 name is the slug itself (slug-derived),
  * >= 10 '#N ranked in <Name>' card labels and one Name holds >= 75% of the non-empty labels,
  * the page's own <meta name="description"> starts with that same Name (independent original metadata) -- or, when that description is itself
    the slug-derived name (generator default 'Hidakacho, Hokkaido. Places to stay...'), the Name must be corroborated >= 2 times by the town's own page
    text ('in <Name>', 'of <Name>', '<Name> Town|Village', '<Name>, <Prefecture>'),
  * Name does not equal another town's H1 / dominant card label in the same prefecture (no clash).
  * NO-LABEL mode (Saitama 'Inamachi' / 'Ogawamachi' / 'Miyoshimachi': empty '#N ranked in ' labels, nothing to vote): the slug ends in machi / cho / mura,
    the H1 is the slug-derived name, Name = slug without that suffix (>= 3 letters, the page's own romanisation) and the same >= 2 on-page corroborations hold.
Everything else is listed in --report with its evidence (lane decision).  Slugs / URLs are never changed.
Rewrites (old slug-derived token -> Name, case-sensitive whole word, prefecture-scoped):
  * every page under <pref>/<slug>/ (H1, <title>, og/twitter title+description, JSON-LD names, breadcrumbs, 'More in', page-sub,
    address line, card text that embeds the slug-derived token),
  * link text of anchors to /<pref>/<slug>/ in the other pages of that prefecture (Other towns, Nearby, prefecture index list),
  * data/<pref>.json (that town's strings) and llms-full.txt / llms.txt link text.
tokyo/ is skipped.  Idempotent (second run = zero diff).  --check exits 1 if a change is needed; --dry-run; --report CSV.
Usage: python3 scripts/town_names_fix.py --root . [--pref slug] [--check|--dry-run] [--report out.csv]
"""
import argparse, collections, csv, json, re, sys
from pathlib import Path
SKIP = {'media', 'assets', 'data', 'scripts', 'go', 'fonts', 'sitemaps', 'photo-credits', 'tokyo'}
RANK = re.compile(r'<p class="place-meta">#\d+ ranked in ([^<]*)</p>')
norm = lambda x: re.sub(r'[^a-z0-9]', '', x.lower())

def h1name(s):
    h = re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S)
    return re.split(r",| in |:", re.sub(r'<[^>]+>', '', h.group(1)).strip())[0].strip() if h else ''

def survey(pdir):
    info = {}
    for hub in sorted(pdir.glob('*/index.html')):
        s = hub.read_text(encoding='utf-8', errors='replace')
        if 'ul class="hub-tiles' not in s: continue
        lab = collections.Counter()
        for p in hub.parent.rglob('index.html'):
            if p != hub: lab.update(RANK.findall(p.read_text(encoding='utf-8', errors='replace')))
        ds = re.search(r'name="description" content="([^"]*)"', s)
        info[hub.parent.name] = {'h1': h1name(s), 'empty': lab.get('', 0), 'labels': {k: v for k, v in lab.items() if k},
                                 'ds': ds.group(1).split(',')[0].strip() if ds else None}
    return info

SUFFIX = re.compile(r'(machi|cho|mura)$')

def corroboration(pdir, slug, name, pref):
    """how often the town's own pages (outside card names/blurbs) use <name> as the town's name"""
    pat = re.compile(r'(?:\b(?:in|of|near|around|at|from) ' + re.escape(name) + r'\b|\b' + re.escape(name) + r' (?:Town|Village)\b|\b' + re.escape(name) + r', ' + re.escape(pref.title()) + r'\b)')
    n = 0
    for p in (pdir / slug).rglob('index.html'):
        t = p.read_text(encoding='utf-8', errors='replace')
        t = re.sub(r'<(?:script|style)\b.*?</(?:script|style)>', ' ', t, flags=re.S)
        n += len(pat.findall(re.sub(r'<[^>]+>', ' ', t)))
    return n

def decide(pref, info, pdir):
    res, unres = {}, []
    for slug, v in info.items():
        L = v['labels']
        ev = f"labels={json.dumps(L, ensure_ascii=False)}; meta-description-name={v['ds']}"
        if not L:
            # NO-LABEL mode: only where the card labels are empty ('#N ranked in ') and the slug is name + admin suffix
            m = SUFFIX.search(slug)
            if not (v['empty'] and m and norm(v['h1']) == norm(slug) and len(slug) - len(m.group(1)) >= 3): continue
            top = slug[:-len(m.group(1))].capitalize()
            c = corroboration(pdir, slug, top, pref)
            clash = [o for o, w in info.items() if o != slug and w['h1'].lower() == top.lower()]
            if clash: unres.append((pref, slug, v['h1'], top, 'name clashes with ' + ','.join(clash), ev)); continue
            if c < 2: unres.append((pref, slug, v['h1'], top, f'only {c} on-page corroboration(s) of the stripped name (need 2)', ev)); continue
            res[slug] = (v['h1'], top, True); continue
        top, n = max(L.items(), key=lambda x: x[1]); tot = sum(L.values())
        if top == v['h1']: continue
        if norm(v['h1']) != norm(slug):
            unres.append((pref, slug, v['h1'], top, 'h1 not slug-derived (labels differ: neighbour-town cards?)', json.dumps(L, ensure_ascii=False))); continue
        if n < 10 or n / tot < 0.75: unres.append((pref, slug, v['h1'], top, 'no clear majority label', ev)); continue
        if v['ds'] != top:
            if not (v['ds'] == v['h1'] and corroboration(pdir, slug, top, pref) >= 2):
                unres.append((pref, slug, v['h1'], top, 'meta description disagrees with card labels', ev)); continue
        clash = [o for o, w in info.items() if o != slug and (w['h1'].lower() == top.lower() or (w['labels'] and max(w['labels'], key=w['labels'].get).lower() == top.lower()))]
        if clash: unres.append((pref, slug, v['h1'], top, 'name clashes with ' + ','.join(clash), ev)); continue
        res[slug] = (v['h1'], top, True)
    return res, unres

def sub_in_text(t, old, new): return re.sub(r'(?<![\w-])' + re.escape(old) + r'(?![\w-])', new, t)

def link_text(t, pref, slug, old, new):
    pat = re.compile(r'(<a [^>]*href="(?:https://bokenjapan\.com)?(?:/' + re.escape(pref) + r'/|\.\./|(?<=")(?=' + re.escape(slug) + r'/))' + re.escape(slug) + r'/[^"]*"[^>]*>(?:← )?)' + re.escape(old) + r'((?: →)?</a>)')
    t = pat.sub(lambda m: m.group(1) + new + m.group(2), t)
    pc = re.compile(r'(<a href="(?:https://bokenjapan\.com)?/' + re.escape(pref) + '/' + re.escape(slug) + r'/[^"]*">)' + re.escape(old) + r'( › )')  # photo-credits 'Used on:' links
    return pc.sub(lambda m: m.group(1) + new + m.group(2), t)

def map_label(t, pref, slug, old, new):
    # inline <svg class="pref-map"> / _map.svg anchors: <a href=".../slug/" data-name="Old" aria-label="Old"><title>Old</title>
    pat = re.compile(r'(<a href="(?:/' + re.escape(pref) + r'/|\.\./|(?=' + re.escape(slug) + r'/))' + re.escape(slug) + r'/" data-name=")' + re.escape(old) + r'(" aria-label=")' + re.escape(old) + r'("><title>)' + re.escape(old) + r'(</title>)')
    return pat.sub(lambda m: m.group(1) + new + m.group(2) + new + m.group(3) + new + m.group(4), t)

def fixjson(o, old, new):
    if isinstance(o, str): return sub_in_text(o, old, new)
    if isinstance(o, list): return [fixjson(x, old, new) for x in o]
    if isinstance(o, dict): return {k: fixjson(v, old, new) for k, v in o.items()}
    return o

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default='.'); ap.add_argument('--pref')
    ap.add_argument('--check', action='store_true'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--report')
    a = ap.parse_args(); root = Path(a.root).resolve(); write = not (a.check or a.dry_run)
    prefs = [a.pref] if a.pref else sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith('.') and d.name not in SKIP)
    rows, unres_all, files, renamed = [], [], set(), 0
    llm = {n: (root / n).read_text(encoding='utf-8') for n in ('llms-full.txt', 'llms.txt') if (root / n).is_file()}
    llm0 = dict(llm)
    for pref in prefs:
        pdir = root / pref
        res, unres = decide(pref, survey(pdir), pdir); unres_all += unres
        if not res: continue
        pages = sorted(list(pdir.rglob('*.html')) + ([pdir / '_map.svg'] if (pdir / '_map.svg').is_file() else []))
        texts = {p: p.read_text(encoding='utf-8') for p in pages}; orig = dict(texts)
        for slug, (old, new, own) in res.items():
            for p in pages:
                rel = p.relative_to(pdir).parts
                if rel[0] == slug and own and p.suffix == '.html': texts[p] = sub_in_text(texts[p], old, new)
                elif old in texts[p]: texts[p] = map_label(link_text(texts[p], pref, slug, old, new), pref, slug, old, new)
            for n in llm: llm[n] = re.sub(r'(\[)' + re.escape(old) + r'(\]\(https://bokenjapan\.com/' + re.escape(pref) + '/' + re.escape(slug) + '/\\))', lambda m: m.group(1) + new + m.group(2), llm[n])
            dj = root / 'data' / f'{pref}.json'
            if dj.is_file():
                d = json.loads(dj.read_text(encoding='utf-8')); ch = False
                for i, t in enumerate(d.get('towns', [])):
                    if t.get('slug') == slug:
                        nt = fixjson(t, old, new)
                        if nt != t: d['towns'][i] = nt; ch = True
                if ch:
                    out = json.dumps(d, ensure_ascii=False, indent=1) + '\n'
                    if out != dj.read_text(encoding='utf-8'):
                        files.add(dj)
                        if write: dj.write_text(out, encoding='utf-8')
            rows.append((pref, slug, old, new, 'renamed' if own else 'leftover-labels'))
        pc = [p for p in pages if texts[p] != orig[p]]
        for p in pc:
            files.add(p)
            if write: p.write_text(texts[p], encoding='utf-8')
        renamed += sum(1 for s in res if any(texts[p] != orig[p] for p in pages if p.relative_to(pdir).parts[0] == s))
    for n in llm:
        if llm[n] != llm0[n]:
            files.add(root / n)
            if write: (root / n).write_text(llm[n], encoding='utf-8')
    per = collections.Counter(str(f.relative_to(root)).split('/')[0] for f in files)
    print(' '.join(f'{k}:{v}' for k, v in sorted(per.items())))
    print(f'towns {"to rename" if not write else "renamed"}: {renamed}; files {"to change" if not write else "changed"}: {len(files)}; unresolved (lane decision): {len(unres_all)}')
    if a.report:
        with open(a.report, 'w', newline='') as f:
            w = csv.writer(f); w.writerow(['pref', 'town', 'current_name', 'card_label_or_new_name', 'status_or_reason', 'evidence'])
            for r in rows: w.writerow(list(r) + [''])
            for u in unres_all: w.writerow(u)
    sys.exit(1 if (a.check and files) else 0)
if __name__ == '__main__': main()
