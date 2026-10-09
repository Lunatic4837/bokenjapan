import sys,re,json,os,glob,collections,time
REPO='/workspace/p1/pr12-work'
sys.path.insert(0,'/workspace/p1/phase-d/dining4'); os.chdir('/workspace/p1/phase-d/dining4')
import gen as B
B.FETCH_LOGS.append('/workspace/p1/line4/work/fetch_w4tb.jsonl')
t0=time.time(); F=B.load_fetched(); print('loaded',len(F),time.time()-t0,flush=True)
os.makedirs('/workspace/p1/phase-d/rollout/data',exist_ok=True)
pages=sorted(p for p in glob.glob(REPO+'/*/*/index.html') if p.split('/')[-3] in ('miyagi','akita','fukuoka','yamaguchi','oita') and 'daisen-05212' not in p)
st=collections.Counter()
for p in pages:
    key=p.split('/')[-3]+'/'+p.split('/')[-2]
    t=open(p).read()
    m=re.search(r'<section class="place-section"><h2>Dining</h2><ul class="place-list">(.*?)</ul></section>',t,re.S)
    lis=re.findall(r'<li>.*?</li>',m.group(1),re.S) if m else []
    out=[]
    for i,li in enumerate(lis):
        tb=re.search(r'tabelog_url=(\S+)',li); ta=re.search(r'ta_url=(\S+)',li)
        im=re.search(r'class="thumb" src="([^"]+)"',li)
        g=None;cu=[];imgs=[]
        for u,kind in ((tb and tb.group(1),'tb'),(ta and ta.group(1),'ta')):
            if not u: continue
            s,_=B.page(F,u)
            if not s: st['nocache-'+kind]+=1; continue
            if kind=='tb' and not g: g=B.P.tabelog(s).get('genre')
            if kind=='ta' and not cu:
                gg=B.T.groups(s); cu=list(gg.get('cuisines') or []) or list(B.P.tripadvisor(s).get('cuisines') or [])
            og=re.findall(r'<meta property="og:image" content="([^"]+)"',s)
            more=re.findall(r'https://tblg\.k-img\.com/restaurant/images/Rvw/\d+/640x640_rect_[0-9a-f]+\.jpg',s)
            more+=re.findall(r'https://dynamic-media-cdn\.tripadvisor\.com/media/photo-[a-z]/[^"\' ?]+\.jpg',s)
            imgs+=[x.replace('&amp;','&') for x in og]+more
        if not g and not cu: st['nogenre']+=1
        out.append(dict(i=i,name=re.search(r'place-name">(.*?)</p>',li).group(1),desc=re.search(r'class="place-desc">(.*?)</p>',li).group(1),
            img=im and im.group(1),tb=tb and tb.group(1),ta=ta and ta.group(1),genre=g,cuisines=cu,limgs=list(dict.fromkeys(imgs))[:5]))
        st['cards']+=1; st['img']+=bool(im); st['limgs']+=bool(imgs)
    json.dump(out,open(f'/workspace/p1/phase-d/rollout/data/{key.replace("/","__")}.json','w'),ensure_ascii=False)
print(len(pages),st,time.time()-t0)
