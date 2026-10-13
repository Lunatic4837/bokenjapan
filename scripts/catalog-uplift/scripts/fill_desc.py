#!/usr/bin/env python3
"""Fill missing Dining descriptions from the Tabelog servesCuisine cache. Usage: fill_desc.py ROOT pref pref_ja PrefEn hubs.json tb.jsonl"""
import re,glob,json,sys,html as H
sys.path.insert(0,'/workspace/p1/fn-uplift')
from fn_lib import genre_en, place_from_addr
root,pref,pref_ja,PREF_EN,hubf,tbf=sys.argv[1:7]
TB={json.loads(l)['u']:json.loads(l) for l in open(tbf)}
hubs=json.load(open(hubf))['hubs']; n=miss=0
for f in sorted(glob.glob(f'{root}/{pref}/*/index.html')):
    t=open(f).read(); muni_en=H.unescape(re.search(r'<h1 class="page-title">([^<]+)',t).group(1))
    h=next((v for v in hubs.values() if v['name_en']==muni_en),None)
    def fix(m):
        global n,miss
        li=m.group(0)
        if 'place-desc' in li or 'tabelog_url=' not in li: return li
        u=re.search(r'tabelog_url=(\S+?/)\s',li).group(1); g=genre_en((TB.get(u) or {}).get('genre') or '')
        a=(re.search(r'locality-addr: ([^ ]+) -->',li) or [0,''])[1]
        if not g or not h: miss+=1; return li
        d=f'{g} in {place_from_addr(a.replace(pref_ja,""),h["name_ja"],h["name_en"])}, {PREF_EN}.'
        n+=1; return li.replace('<!-- desc-source:',f'<p class="place-desc">{H.escape(d)}</p><!-- desc-source:',1)
    t2=re.sub(r'<li>.*?</li>',fix,t,flags=re.S)
    if t2!=t: open(f,'w').write(t2)
print('filled',n,'unfilled',miss)
