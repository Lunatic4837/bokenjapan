#!/usr/bin/env python3
"""Wave 3 structural cleanup of Dining sections (5 prefectures).
(a) Same-name duplicates: a later card is the SAME facility as an earlier same-name card when
    - it is a TA-only card whose photo-credit points at that Tabelog listing (the pipeline's own TB<->TA match) and the
      two listings' coordinates are within 500 m (or one has none), or
    - both listings carry geo coordinates within 100 m, or the same normalized street address.
    Same facility -> later card removed (Tabelog-first order kept). Otherwise both stay (distinct branches).
(b) Stay/Dining overlap (Dining name == a Stay name): Tabelog genre is lodging (ホテル/旅館・民宿/料理旅館/オーベルジュ/その他)
    -> the card is the lodging itself -> removed. Restaurant genre -> separate restaurant listing -> kept.
    TA-only: kept if TA lists a cuisine, removed if no cuisine (no evidence of a separate restaurant).
Dining '#N ranked in X' lines are renumbered sequentially afterwards. Writes plan.json / removed.csv. --apply writes pages."""
import sys, re, json, csv, math, collections, unicodedata
sys.path.insert(0, '/workspace/p1/line4/work'); sys.path.insert(0, '/workspace/p1/phase-d/dining4'); sys.path.insert(0, '/workspace/p1/phase-d/w3')
import gen as B, parsers as P, ta_parse as T
from cards_lib import *
F = B.load_fetched()
LODGE = re.compile(r'ホテル|旅館|民宿|オーベルジュ|ペンション')
def info(c):
    u = c['tb'] or c['ta']; s, r = B.page(F, u) if u else (None, None)
    o = dict(geo=None, addr=None, genre=None, cuisines=None)
    if not s: return o
    for d in P.ldjson(s):
        if isinstance(d, dict) and d.get('@type') in ('Restaurant', 'FoodEstablishment'):
            g = d.get('geo') or {}; a = d.get('address') or {}
            try: o['geo'] = (float(g['latitude']), float(g['longitude']))
            except Exception: pass
            if isinstance(a, dict) and a.get('streetAddress'):
                o['addr'] = re.sub(r'\s', '', unicodedata.normalize('NFKC', (a.get('addressLocality') or '') + a['streetAddress'])).lower()
            break
    if c['tb']: o['genre'] = P.tabelog(s).get('genre') or ''
    else: o['cuisines'] = T.groups(s).get('cuisines') or []
    return o
def dist(a, b):
    if not a or not b: return None
    dy = (a[0]-b[0])*111320; dx = (a[1]-b[1])*111320*math.cos(math.radians(a[0])); return math.hypot(dx, dy)
def credit(c):
    m = re.search(r'<!-- photo-credit: .*?Source (\S+) -->', c['li']); return m.group(1) if m else ''
plan = {}; rows = []; st = collections.Counter(); keep_groups = []
for page, p in pages():
    if not re.match(r'(miyagi|akita|fukuoka|yamaguchi|oita)/', page): continue
    s = open(p).read(); m, d = section_cards(s, 'Dining'); _, stay = section_cards(s, 'Stay')
    if not d: continue
    rm = {}; cache = {}
    I = lambda i: cache.setdefault(i, info(d[i]))
    groups = collections.defaultdict(list)
    for i, c in enumerate(d): groups[nk(c['name'])].append(i)
    for n, idx in groups.items():
        if len(idx) < 2: continue
        kept = []
        for i in idx:
            c = d[i]; same = None
            for j in kept:
                k = d[j]
                if c['tb'] and c['tb'] == k['tb'] or c['ta'] and c['ta'] == k['ta']: same = (j, 'same listing URL'); break
                dd = dist(I(i)['geo'], I(j)['geo'])
                if not c['tb'] and k['tb'] and credit(c).startswith(k['tb']) and (dd is None or dd <= 500): same = (j, 'TA listing matched to this Tabelog listing'); break
                if dd is not None and dd <= 100: same = (j, f'same name, {dd:.0f} m apart'); break
                if I(i)['addr'] and I(i)['addr'] == I(j)['addr']: same = (j, 'same name and street address'); break
            if same: rm[i] = ('duplicate of #%d: %s' % (same[0]+1, same[1])); st['dup:' + same[1].split(',')[0]] += 1
            else: kept.append(i)
        if len(kept) > 1: keep_groups.append((page, n, [d[i]['tb'] or d[i]['ta'] for i in kept])); st['distinct-branch groups'] += 1
    sn = {nk(c['name']) for c in stay}
    for i, c in enumerate(d):
        if i in rm or nk(c['name']) not in sn: continue
        o = I(i)
        if c['tb']:
            if LODGE.search(o['genre'] or '') or (o['genre'] or '').strip() == 'その他': rm[i] = f"lodging itself (Tabelog genre {o['genre']})"; st['stay-dining removed tb'] += 1
            else: st['stay-dining kept (restaurant genre)'] += 1
        else:
            if not o['cuisines']: rm[i] = 'lodging itself (TA listing has no cuisine)'; st['stay-dining removed ta'] += 1
            else: st['stay-dining kept (TA cuisine)'] += 1
    if rm:
        plan[page] = sorted(rm)
        for i in sorted(rm): rows.append(dict(page=page, idx=i, rank=i+1, name=d[i]['name'], url=d[i]['tb'] or d[i]['ta'], reason=rm[i]))
json.dump(dict(remove=plan, distinct=keep_groups), open('plan.json', 'w'), ensure_ascii=False, indent=0)
with open('removed.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['page', 'idx', 'rank', 'name', 'url', 'reason']); w.writeheader(); w.writerows(rows)
print(dict(st)); print('cards removed', len(rows), 'pages', len(plan))
if '--apply' in sys.argv:
    for page, idxs in plan.items():
        p = f'{REPO}/{page}/index.html'; s = open(p).read(); m, d = section_cards(s, 'Dining')
        lis = re.findall(r'<li\b.*?</li>', m.group(2), re.S); body = m.group(2)
        for i in sorted(idxs, reverse=True):
            pos = [mm.start() for mm in re.finditer(r'<li\b.*?</li>', body, re.S)][i]
            mm = re.compile(r'<li\b.*?</li>', re.S).match(body, pos); body = body[:mm.start()] + body[mm.end():]
        n = [0]
        def ren(x): n[0] += 1; return re.sub(r'#\d+ ranked in', f'#{n[0]} ranked in', x.group(0), 1)
        body = re.sub(r'<p class="place-meta">#\d+ ranked in [^<]*</p>', ren, body)
        s = s[:m.start(2)] + body + s[m.end(2):]; open(p, 'w').write(s)
    print('applied')
