import sys, re, json, collections
sys.path.insert(0, '/workspace/p1/line4/work'); sys.path.insert(0, '/workspace/p1/phase-d/dining4'); sys.path.insert(0, '/workspace/p1/phase-d/w3')
import gen as B, parsers as P, ta_parse as T
from cards_lib import *
F = B.load_fetched(); st = collections.Counter(); out = []
LOD = re.compile(r'旅館・民宿|料理旅館|ペンション|オーベルジュ|ホテル')
for page, p in pages():
    if not re.match(r'(miyagi|akita|fukuoka|yamaguchi|oita)/', page): continue
    s = open(p).read(); m, d = section_cards(s, 'Dining')
    for i, c in enumerate(d or []):
        if c['tb']:
            h, r = B.page(F, c['tb'])
            g = (P.tabelog(h).get('genre') or '') if h else ''
            if LOD.search(g): st['tb:' + g] += 1; out.append(dict(page=page, idx=i, name=c['name'], en=c['en'], desc=c['desc'], url=c['tb'], genre=g))
        elif re.match(r'Inn \(ryokan|Ryokan|Hotel', c['desc'] or ''):
            h, r = B.page(F, c['ta']); g = T.groups(h) if h else {}
            st['ta:' + str(g.get('cuisines')) + str(g.get('establishment_types'))] += 1
            out.append(dict(page=page, idx=i, name=c['name'], en=c['en'], desc=c['desc'], url=c['ta'], genre='TA ' + str(g.get('cuisines')) + str(g.get('establishment_types'))))
json.dump(out, open('a2_candidates.json', 'w'), ensure_ascii=False, indent=0)
for k, v in st.most_common(40): print(v, k)
print(len(out))
