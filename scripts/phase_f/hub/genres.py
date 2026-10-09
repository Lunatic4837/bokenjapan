import sys,re,json,os
sys.path.insert(0,'/workspace/p1/phase-d/dining4')
os.chdir('/workspace/p1/phase-d/dining4')
import gen as B
B.FETCH_LOGS.append('/workspace/p1/line4/work/fetch_w4tb.jsonl')
F=B.load_fetched()
t=open('/workspace/p1/pr12-work/akita/daisen-05212/index.html').read()
sec=re.search(r'<h2>Dining</h2><ul class="place-list">(.*?)</ul></section>',t,re.S).group(1)
lis=re.findall(r'<li>.*?</li>',sec,re.S)
out=[];miss=0
for i,li in enumerate(lis):
    tb=re.search(r'tabelog_url=(\S+)',li); ta=re.search(r'ta_url=(\S+)',li)
    g=None;cu=None;src=None
    if tb:
        s,_=B.page(F,tb.group(1))
        if s: g=B.P.tabelog(s).get('genre'); src='tb'
    if not g and ta:
        s,_=B.page(F,ta.group(1))
        if s:
            gg=B.T.groups(s); cu=list(gg.get('cuisines') or []) or list(B.P.tripadvisor(s).get('cuisines') or []); src='ta'
    desc=re.search(r'class="place-desc">(.*?)</p>',li).group(1)
    if not g and not cu: miss+=1
    out.append(dict(i=i,genre=g,cuisines=cu,src=src,desc=desc,name=re.search(r'place-name">(.*?)</p>',li).group(1)))
json.dump(out,open('/workspace/p1/phase-d/preview/daisen_genres.json','w'),ensure_ascii=False,indent=0)
print(len(lis),'miss',miss)
