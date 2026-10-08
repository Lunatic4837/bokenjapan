#!/usr/bin/env python3
"""Add a Stay section to municipality pages that have no Stay cards:
'No listed places to stay in {Town} — nearest options in {Nearest}.' linking to the nearest same-prefecture
page with >=1 Stay card, by straight-line distance between town-hall coordinates (geo.json)."""
import json, re, glob, math, os, html
REPO = '/workspace/p1/pr12-work'
G = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'geo.json')))
PREFS = ('miyagi','akita','fukuoka','yamaguchi','oita')
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
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 12742 * math.asin(math.sqrt(h))
out = {}
for k, v in pages.items():
    if v['stay'] or v['none']: continue
    pref = k.split('/')[0]
    cands = [(km(G[k], G[c]), c) for c, w in pages.items() if c.startswith(pref + '/') and w['stay'] and c in G]
    d, near = min(cands)
    out[k] = dict(nearest=near, km=round(d, 1))
    sec = (f'<section class="place-section"><h2>Stay</h2><p class="stay-none">No listed places to stay in '
           f'{html.escape(v["title"], quote=False)} — nearest options in <a href="/{near}/">'
           f'{html.escape(pages[near]["title"], quote=False)}</a>.</p></section>')
    s = v['s']; i = s.find('<section class="place-section">')
    s = s[:i] + sec + '\n' + s[i:]
    open(v['path'], 'w', encoding='utf-8').write(s)
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'nearest.json'), 'w'), indent=1)
print(len(out), 'pages got a no-lodging Stay line')
for k, v in out.items(): print(k, '->', v['nearest'], v['km'], 'km')
