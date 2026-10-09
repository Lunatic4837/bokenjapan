#!/usr/bin/env python3
"""Item 3 step 2: confirm Tabelog inn == Jalan yad by address (Tabelog listing ld+json vs Jalan listing ld+json)."""
import sys, re, json, unicodedata, collections
sys.path.insert(0, '/workspace/p1/line4/work'); sys.path.insert(0, '/workspace/p1/phase-d/dining4')
import gen as B
B.FETCH_LOGS.append('/workspace/p1/line4/work/fetch_w4tb.jsonl')
F = B.load_fetched()
geo = json.load(open('/workspace/p1/phase-d/nostay/geo.json'))
def ldaddr(s):
    for m in re.finditer(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', s, re.S):
        try: d = json.loads(m.group(1), strict=False)
        except Exception: continue
        for el in (d if isinstance(d, list) else [d]):
            if isinstance(el, dict) and isinstance(el.get('address'), dict):
                a = el['address']; return (a.get('addressRegion') or '') + (a.get('addressLocality') or '') + (a.get('streetAddress') or '')
    return None
def norm(a):
    a = unicodedata.normalize('NFKC', a or '')
    a = re.sub(r'\s', '', a)
    a = re.sub(r'^(宮城県|秋田県|福岡県|山口県|大分県)', '', a)
    a = re.sub(r'^[^市]{1,4}郡', '', a)
    a = a.replace('大字', '').replace('字', '')
    a = re.sub(r'(丁目|番地の?|番|号|の(?=\d))', '-', a)
    a = re.sub(r'[‐－ー―−]', '-', a); a = re.sub(r'-+', '-', a).strip('-')
    return a
def split(a):
    m = re.match(r'^(.*?)(\d.*)?$', a); return m.group(1), re.findall(r'\d+', m.group(2) or '')
cands = json.load(open('i3_cands.json')); out = []; st = collections.Counter()
for c in cands:
    if not c['jalan_url']: c['verdict'] = 'no Jalan listing'; out.append(c); st[c['verdict']] += 1; continue
    yid = re.search(r'yad(\d+)', c['jalan_url']).group(1)
    js = open(f'/workspace/p1/phase-d/stay4/html/{yid}.html', encoding='utf-8', errors='replace').read()
    ja_ = ldaddr(js)
    h, r = B.page(F, c['tabelog_url'])
    tb_ = ldaddr(h) if h else None
    if not tb_ and h:
        m = re.search(r'<p class="rstinfo-table__address">(.*?)</p>', h, re.S)
        if m: tb_ = re.sub(r'<[^>]+>', '', m.group(1))
    a, b = norm(tb_), norm(ja_)
    town = geo[c['page']]['ja']
    (ap, an), (bp, bn) = split(a), split(b)
    same_town = town in (ja_ or '') and town in (tb_ or '')
    if not tb_: v = 'no Tabelog address'
    elif not same_town: v = 'different municipality'
    elif a == b or (ap == bp and an[:2] == bn[:2] and an): v = 'confirmed (same address)'
    elif ap == bp and an[:1] == bn[:1] and an: v = 'confirmed (same block)'
    elif (ap == bp or ap.startswith(bp) or bp.startswith(ap)) and not an and not bn: v = 'review (same area, no number)'
    else: v = 'address differs'
    c.update(tb_addr=tb_, jalan_addr=ja_, verdict=v); out.append(c); st[v] += 1
json.dump(out, open('i3_verify.json', 'w'), ensure_ascii=False, indent=0)
print(dict(st))
for c in out:
    if c['jalan_url']: print(c['verdict'][:22].ljust(22), c['page'], c['name'], '|', c.get('jalan_name') or '', '|', c.get('tb_addr'), '|', c.get('jalan_addr'))
