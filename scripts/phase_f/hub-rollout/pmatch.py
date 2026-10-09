import sys,re,io,json,os,glob,requests,threading,collections,concurrent.futures as cf,time
from PIL import Image
import warnings; warnings.filterwarnings('ignore')
D='/workspace/p1/phase-d/rollout'
HC=D+'/hashcache.jsonl'; H={}
if os.path.exists(HC):
    for l in open(HC):
        try: k,v=json.loads(l); H[k]=v
        except Exception: pass
lock=threading.Lock(); hf=open(HC,'a')
tl=threading.local()
def sess():
    if not hasattr(tl,'s'): tl.s=requests.Session(); tl.s.headers['User-Agent']='Mozilla/5.0'
    return tl.s
def ah(b):
    im=Image.open(io.BytesIO(b)).convert('L').resize((9,8)); p=list(im.getdata()); return sum(1<<i for i in range(64) if p[(i//8)*9+i%8]>p[(i//8)*9+i%8+1])
def get(u):
    if u in H: return H[u]
    h=None
    for _ in range(2):
        try:
            r=sess().get(u,timeout=25)
            if r.status_code==200: h=ah(r.content); break
            if r.status_code in (403,404,410): break
        except Exception: pass
    with lock:
        H[u]=h; hf.write(json.dumps([u,h])+'\n'); hf.flush()
    return h
def dist(a,b): return bin(a^b).count('1')
os.makedirs(D+'/match',exist_ok=True)
EX=cf.ThreadPoolExecutor(24)
tot=collections.Counter(); t0=time.time()
for f in sorted(glob.glob(D+'/data/*.json')):
    out=D+'/match/'+os.path.basename(f)
    if os.path.exists(out): continue
    cards=json.load(open(f))
    r2=sorted({c['img'] for c in cards if c['img']})
    R=dict(zip(r2,EX.map(get,r2)))
    def work(c):
        if not c['img']: return dict(i=c['i'],status='no-photo')
        cur=R.get(c['img']); best=None
        for iu in c['limgs']:
            h=get(iu)
            if h is None: continue
            if cur is not None and dist(cur,h)<=4: return dict(i=c['i'],cur=c['img'],best=c['img'],dist=dist(cur,h),src=iu)
            for k,v in R.items():
                if v is None: continue
                d=dist(v,h)
                if best is None or d<best[0]: best=(d,k,iu)
            if best and best[0]<=4: break
        return dict(i=c['i'],cur=c['img'],best=best and best[1],dist=best and best[0],src=best and best[2],curhash=cur is not None)
    res=list(EX.map(work,cards))
    st=collections.Counter()
    for r in res:
        if r.get('status'): st[r['status']]+=1
        elif r['dist'] is None: st['no-listing-img']+=1
        elif r['dist']<=4: st['ok-same' if r['best']==r['cur'] else 'ok-moved']+=1
        else: st['nomatch']+=1
    json.dump(res,open(out,'w'))
    tot.update(st)
    print(os.path.basename(f),dict(st),int(time.time()-t0),flush=True)
print('TOTAL',dict(tot))
