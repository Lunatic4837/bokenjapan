#!/usr/bin/env python3
"""inventory cards per pref: photo / photo-less, per section. usage inv.py ROOT PREF [--json out]"""
import re,sys,json,html as H,collections
from pathlib import Path
root,pref=Path(sys.argv[1]),sys.argv[2]
LI=re.compile(r'<li>(?:<a href="([^"]*)">)?<p class="place-name">([^<]*)</p>(.*?)</li>',re.S)
rows=[];seen=set()
for f in sorted((root/pref).glob('*/*/**/index.html')):
    rel=f.relative_to(root/pref).parts
    sec=rel[1]
    if sec not in('eat','stay','see','do'): continue
    t=f.read_text(encoding='utf-8',errors='replace')
    for m in LI.finditer(t):
        href,name,rest=m.groups()
        key=(rel[0],sec,href,name)
        if key in seen: continue
        seen.add(key)
        img=re.search(r'<img class="thumb"[^>]*>',m.group(0))
        blurb=re.search(r'<p class="place-blurb">([^<]*)</p>',rest)
        rows.append(dict(town=rel[0],sec=sec,page=str(f.relative_to(root)),href=href,name=H.unescape(name),photo=bool(img),
            blurb=H.unescape(blurb.group(1)) if blurb else '',src=re.search(r'src="([^"]+)"',img.group(0)).group(1) if img else '',
            comment=bool(re.search(r'photo_search',rest))))
c=collections.Counter((r['sec'],r['photo']) for r in rows)
print(pref,len(rows),dict(c))
tot=len(rows);ph=sum(r['photo'] for r in rows);print('photo %.1f%%'%(100*ph/max(tot,1)))
if '--json' in sys.argv: json.dump(rows,open(sys.argv[sys.argv.index('--json')+1],'w'),ensure_ascii=False,indent=0)
