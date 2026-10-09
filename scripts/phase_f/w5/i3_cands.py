#!/usr/bin/env python3
"""Item 3 step 1: Jalan index (listing order) from the cached large-area crawls; candidate pairs (Tabelog inn -> Jalan yad)."""
import re, json, glob, os, csv, unicodedata, collections
src = open('/workspace/p1/phase-d/jalan_stay.py').read().split('res = {}')[0]
ns = {}; exec(src, ns); hotels = ns['hotels']
D = '/workspace/p1/phase-d/jalan'
idx = {}
for pref in ('miyagi', 'akita', 'fukuoka', 'yamaguchi', 'oita'):
    files = glob.glob(f'{D}/{pref}-LRG_*.html')
    def key(f):
        m = re.search(r'LRG_(\d+)(?:-idx(\d+))?\.html$', f); return (int(m.group(1)), int(m.group(2) or 0)) if m else (9e9, 0)
    n = 0
    for f in sorted([f for f in files if re.search(r'LRG_\d+(-idx\d+)?\.html$', f)], key=key):
        s = open(f, 'rb').read().decode('cp932', 'replace')
        for h in hotels(s):
            u = h.get('url')
            if not u or u in idx: continue
            a = h.get('address') or {}
            idx[u] = dict(name=unicodedata.normalize('NFKC', h.get('name') or ''), region=a.get('addressRegion'), locality=a.get('addressLocality') or '',
                          street=unicodedata.normalize('NFKC', a.get('streetAddress') or ''), postal=a.get('postalCode'), image=h.get('image'), pref=pref, order=n, lrg=key(f)[0])
            n += 1
    print(pref, n)
json.dump(idx, open('jalan_index.json', 'w'), ensure_ascii=False)
geo = json.load(open('/workspace/p1/phase-d/nostay/geo.json'))
GENW = ['料理旅館', '旅館', '民宿', 'ペンション', 'ホテル', '温泉', 'の宿', '宿', 'お宿', '湯元', '湯の宿', '一棟貸し', '天然洞窟']
def core(n):
    n = unicodedata.normalize('NFKC', n); n = re.sub(r'[\s\u3000・()（）\[\]［］「」]', '', n)
    return n
cands = []
for r in csv.DictReader(open('/workspace/p1/phase-d/w4/inns-not-in-stay.csv')):
    cands.append(dict(page=r['page'], name=r['name'], tabelog_url=r['tabelog_url'], jalan_url=r['jalan_url'], how=r['jalan_match']))
for r in csv.DictReader(open('/workspace/p1/phase-d/w4/inns-removed-from-dining.csv')):
    if not r['page'].startswith('oita/') or r['in_stay'] == 'yes': continue
    mja = geo[r['page']]['ja']; nm = core(r['name'])
    toks = [t for t in re.split('|'.join(map(re.escape, sorted(GENW, key=len, reverse=True))), unicodedata.normalize('NFKC', r['name']).replace('\u3000', ' ')) for t in t.split() if len(t) >= 2] if True else []
    hits = []
    for u, h in idx.items():
        if h['pref'] != 'oita': continue
        hn = core(h['name'])
        if nm and (nm in hn or hn in nm): hits.append((u, 'name contains')); continue
        if toks and all(t in hn for t in toks): hits.append((u, 'all name tokens'))
    if not hits: cands.append(dict(page=r['page'], name=r['name'], tabelog_url=r['tabelog_url'], jalan_url='', how='no Jalan listing found')); continue
    for u, how in hits: cands.append(dict(page=r['page'], name=r['name'], tabelog_url=r['tabelog_url'], jalan_url=u, how=how, jalan_name=idx[u]['name'], jalan_locality=idx[u]['locality'], town_ja=mja))
json.dump(cands, open('i3_cands.json', 'w'), ensure_ascii=False, indent=0)
c = collections.Counter(x['how'] for x in cands); print(c)
for x in cands:
    if x['page'].startswith('oita'): print(x['page'], x['name'], '->', x.get('jalan_name'), x.get('jalan_locality'), x['how'])
