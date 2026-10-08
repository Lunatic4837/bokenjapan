# Stay cards whose (older, short) explanation repeats on >3 cards of the same page: add them so gen.py can enrich them from Jalan.
import re,glob,html,json,collections
REPO='/workspace/p1/pr12-work'
cards=json.load(open('cards.json')); have={(c['page'],c['idx']) for c in cards}; add=[]
for p in sorted(glob.glob(f'{REPO}/*/*/index.html')):
    pref,slug=p.split('/')[-3:-1]
    if pref not in ('miyagi','akita','fukuoka','yamaguchi','oita'): continue
    s=open(p,encoding='utf-8').read()
    m=re.search(r'<section class="place-section"><h2>Stay</h2>(.*?)</section>',s,re.S)
    if not m: continue
    lis=re.findall(r'<li\b.*?</li>',m.group(1),re.S)
    ds=[html.unescape(x.group(1)) if (x:=re.search(r'<p class="place-desc">(.*?)</p>',li)) else '' for li in lis]
    cnt=collections.Counter(ds)
    for i,(li,d) in enumerate(zip(lis,ds)):
        if d and cnt[d]>3 and (f'{pref}/{slug}',i) not in have:
            j=re.search(r'jalan_url=(\S+)',li)
            if j: add.append(dict(page=f'{pref}/{slug}',idx=i,old=d,jalan=html.unescape(j.group(1)),name=''))
json.dump(cards+add,open('cards.json','w'),ensure_ascii=False,indent=0); print('added',len(add))
