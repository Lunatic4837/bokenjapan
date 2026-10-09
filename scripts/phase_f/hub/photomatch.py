import sys,re,io,json,requests,concurrent.futures as cf
sys.path.insert(0,'/workspace/p1/phase-d/dining4'); import os; os.chdir('/workspace/p1/phase-d/dining4')
import gen as B
B.FETCH_LOGS.append('/workspace/p1/line4/work/fetch_w4tb.jsonl'); F=B.load_fetched()
from PIL import Image
import warnings; warnings.filterwarnings('ignore')
S=requests.Session()
def ah(b):
    im=Image.open(io.BytesIO(b)).convert('L').resize((9,8)); p=list(im.getdata()); return sum(1<<i for i in range(64) if p[(i//8)*9+i%8]>p[(i//8)*9+i%8+1])
def get(u):
    for _ in range(2):
        try:
            r=S.get(u,timeout=25)
            if r.status_code==200: return ah(r.content)
        except Exception: pass
src=open('/workspace/p1/phase-d/preview/daisen-orig.html').read()
sec=re.search(r'<h2>Dining</h2><ul class="place-list">(.*?)</ul>',src,re.S).group(1)
lis=re.findall(r'<li>.*?</li>',sec,re.S)
cards=[]
for i,li in enumerate(lis):
    im=re.search(r'class="thumb" src="([^"]+)"',li); tb=re.search(r'tabelog_url=(\S+)',li); ta=re.search(r'ta_url=(\S+)',li)
    cards.append(dict(i=i,img=im and im.group(1),tb=tb and tb.group(1),ta=ta and ta.group(1)))
r2=sorted({c['img'] for c in cards if c['img']})
with cf.ThreadPoolExecutor(16) as ex: R=dict(zip(r2,ex.map(get,r2)))
print('r2 imgs',len(r2),'hashed',sum(1 for v in R.values() if v is not None))
def listing_imgs(c):
    out=[]
    for u in (c['tb'],c['ta']):
        if not u: continue
        s,_=B.page(F,u)
        if not s: continue
        og=re.findall(r'<meta property="og:image" content="([^"]+)"',s)
        more=re.findall(r'https://tblg\.k-img\.com/restaurant/images/Rvw/\d+/640x640_rect_[0-9a-f]+\.jpg',s)
        more+=re.findall(r'https://dynamic-media-cdn\.tripadvisor\.com/media/photo-[a-z]/[^"\' ?]+\.jpg',s)
        out+= [x.replace('&amp;','&') for x in og]+more
    return list(dict.fromkeys(out))[:5]
def work(c):
    if not c['img']: return dict(i=c['i'],status='no-photo')
    best=None
    for iu in listing_imgs(c):
        h=get(iu)
        if h is None: continue
        for k,v in R.items():
            if v is None: continue
            d=bin(v^h).count('1')
            if best is None or d<best[0]: best=(d,k,iu)
        if best and best[0]<=4: break
    cur=R.get(c['img']); 
    return dict(i=c['i'],cur=c['img'],best=best and best[1],dist=best and best[0],src=best and best[2])
with cf.ThreadPoolExecutor(12) as ex: res=list(ex.map(work,cards))
json.dump(res,open('/workspace/p1/phase-d/preview/photomatch.json','w'),indent=0)
import collections
st=collections.Counter()
for r in res:
    if r.get('status'): st[r['status']]+=1
    elif r['dist'] is None: st['no-listing-img']+=1
    elif r['dist']<=4: st['ok-same' if r['best']==r['cur'] else 'ok-moved']+=1
    else: st['nomatch']+=1
print(st)
