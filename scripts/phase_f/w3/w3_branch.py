#!/usr/bin/env python3
"""Same Japanese name kept twice on a page (different listings, >100 m apart): add the listing's own area to the
English name (line 2) so the cards are distinguishable: TripAdvisor English address area, or for Tabelog the
nearest station named on the listing ('near X Station'). Nothing is added when the listing gives neither."""
import sys, re, html, collections
sys.path.insert(0, '/workspace/p1/line4/work'); sys.path.insert(0, '/workspace/p1/phase-d/dining4'); sys.path.insert(0, '/workspace/p1/phase-d/w3')
import gen as B, gen2 as G2, generate as G, parsers as P, ta_parse as T
from cards_lib import *
F = B.load_fetched(); st = collections.Counter()
def area(c, pref):
    u = c['tb'] or c['ta']; s, r = B.page(F, u)
    if not s: return None
    if c['ta'] and not c['tb']:
        a, _ = G2.ta_addr(T.decoded(s)); return a
    m = re.search(r'<title>[^<]*? - ([^/<|]+)/[^<|]*\| 食べログ</title>', s)
    sj = re.sub(r'（[^）]*）$', '', m.group(1).strip()) if m else None
    en = (G.station_en(sj, G.PREF_JA[pref]) or G2.BRT.get(sj)) if sj else None
    return ('near ' + (en if en.endswith('Station') else en + ' Station')) if en else None
for page, p in pages():
    if not re.match(r'(miyagi|akita|fukuoka|yamaguchi|oita)/', page): continue
    s = open(p).read(); m, d = section_cards(s, 'Dining')
    if not d: continue
    g = collections.defaultdict(list)
    for i, c in enumerate(d): g[nk(c['name'])].append(i)
    new = {}
    for n, idx in g.items():
        if len(idx) < 2: continue
        st['groups'] += 1
        ar = {i: area(d[i], page.split('/')[0]) for i in idx}
        for i in idx:
            a = ar[i]; en = d[i]['en'] or ''
            if not a or a.lower() in en.lower() or list(ar.values()).count(a) > 1: st['card left (no distinct area on listing)'] += 1; continue
            new[i] = f'{en} ({a})'; st['card got area'] += 1
    if not new: continue
    lis = list(re.finditer(r'<li\b.*?</li>', m.group(2), re.S)); body = m.group(2); out = []; last = 0
    for i, mm in enumerate(lis):
        li = mm.group(0)
        if i in new:
            li = re.sub(r'<p class="place-blurb">.*?</p>', lambda x: f'<p class="place-blurb">{html.escape(new[i], quote=False)}</p>', li, 1, flags=re.S)
        out.append(body[last:mm.start()] + li); last = mm.end()
    body = ''.join(out) + body[last:]
    open(p, 'w').write(s[:m.start(2)] + body + s[m.end(2):]); st['pages'] += 1
print(dict(st))
