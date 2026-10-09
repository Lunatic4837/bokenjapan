import sys, re, json, collections
sys.path.insert(0, '/workspace/p1/line4/work'); sys.path.insert(0, '/workspace/p1/phase-d/dining4'); sys.path.insert(0, '/workspace/p1/phase-d/w3')
import gen as _g; _g.FETCH_LOGS.append('/workspace/p1/line4/work/fetch_w4tb.jsonl')
exec(open('/workspace/p1/phase-d/w3/w3_struct.py').read().split('plan = {}')[0])
out = []; st = collections.Counter()
for page, p in pages():
    if not re.match(r'(miyagi|akita|fukuoka|yamaguchi|oita)/', page): continue
    s = open(p).read(); m, d = section_cards(s, 'Dining')
    if not d: continue
    for i, c in enumerate(d):
        if c['tb']: continue
        cr = credit(c)
        if 'tabelog.com' not in cr: continue
        tbu = re.match(r'(https://tabelog\.com/[a-z]+/A\d+/A\d+/\d+/)', cr); tbu = tbu.group(1) if tbu else None
        st['ta card w/ tabelog credit'] += 1
        sa, _ = B.page(F, c['ta']); ga = None
        sb, rb = B.page(F, tbu) if tbu else (None, None)
        ia = info(c); ib = info(dict(c, tb=tbu, ta=None)) if sb else {'geo': None}
        dd = dist(ia['geo'], ib['geo'])
        k = 'nogeo' if dd is None else ('far' if dd > 500 else 'near')
        st[k] += 1
        if k != 'near': out.append(dict(page=page, idx=i, name=c['name'], en=c['en'], ta=c['ta'], tb=tbu, dist=None if dd is None else round(dd), tbfetched=bool(sb)))
json.dump(out, open('a1_candidates.json', 'w'), ensure_ascii=False, indent=0)
print(dict(st)); [print(x) for x in out if x['dist']][:40]
print([ (x['name'],x['en'],x['tbfetched']) for x in out if x['dist'] is None][:15])
