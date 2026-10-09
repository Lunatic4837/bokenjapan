#!/usr/bin/env python3
"""Item 1 step 2: recompute the 'nearest options' link on every Stay=0 page from the GSI town-hall coordinates
(nearest same-prefecture page with >=1 Stay card, straight-line). Rewrites only lines whose target changed."""
import json, re, glob, math, html, sys
REPO = '/workspace/p1/pr12-work'
G = json.load(open('/workspace/p1/phase-d/nostay/geo.json'))
PREFS = ('miyagi', 'akita', 'fukuoka', 'yamaguchi', 'oita')
pages = {}
for p in sorted(glob.glob(f'{REPO}/*/*/index.html')):
    pref, slug = p.split('/')[-3:-1]
    if pref not in PREFS: continue
    s = open(p, encoding='utf-8').read()
    t = html.unescape(re.search(r'<h1 class="page-title">(.*?)</h1>', s).group(1))
    m = re.search(r'<section class="place-section"><h2>Stay</h2>(.*?)</section>', s, re.S)
    n = len(re.findall(r'<li\b', m.group(1))) if m else 0
    pages[f'{pref}/{slug}'] = dict(path=p, s=s, title=t, stay=n, none=bool(m and 'stay-none' in m.group(1)))
def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a['lat'], a['lon'], b['lat'], b['lon']))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))
res = {}; changed = 0; dry = '--dry' in sys.argv
for k, v in pages.items():
    if not v['none']: continue
    pref = k.split('/')[0]
    m = re.search(r'(<p class="stay-none">No listed places to stay in .*? — nearest options in <a href="/)([a-z]+/[a-z0-9-]+)(/">)(.*?)(</a>\.</p>)', v['s'])
    old = m.group(2)
    d, near = min((km(G[k], G[c]), c) for c, w in pages.items() if c.startswith(pref + '/') and w['stay'] and c in G)
    d_old = km(G[k], G[old])
    res[k] = dict(old=old, new=near, km_new=round(d, 1), km_old_gsi=round(d_old, 1), changed=old != near)
    if old != near:
        changed += 1
        if not dry:
            s = v['s'][:m.start(2)] + near + m.group(3) + html.escape(pages[near]['title'], quote=False) + m.group(5) + v['s'][m.end(5):]
            open(v['path'], 'w', encoding='utf-8').write(s)
json.dump(res, open('/workspace/p1/phase-d/w5/nearest-w5.json', 'w'), indent=1)
print(len(res), 'stay-none pages;', changed, 'links changed')
for k, r in res.items(): print(k, r['old'], '->', r['new'], r['km_old_gsi'], r['km_new'], 'CHANGED' if r['changed'] else '')
