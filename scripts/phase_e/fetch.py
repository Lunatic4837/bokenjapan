import json,os,re,time,requests,concurrent.futures as cf,threading
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'
urls=sorted({c['jalan'] for c in json.load(open('cards.json')) if c['jalan']})
tl=threading.local()
def one(u):
    yid=re.search(r'yad(\d+)',u).group(1); f=f'html/{yid}.html'
    if os.path.exists(f): return 'cached'
    if not hasattr(tl,'s'): tl.s=requests.Session(); tl.s.headers['User-Agent']=UA
    for i in range(3):
        try:
            r=tl.s.get(u,timeout=25); time.sleep(0.8)
            if r.status_code==200:
                open(f,'w',encoding='utf-8').write(r.content.decode('cp932',errors='replace')); return 'ok'
            if r.status_code in (403,429,503): time.sleep(15*(i+1)); continue
            return str(r.status_code)
        except Exception: time.sleep(5)
    return 'ERR'
import collections
with cf.ThreadPoolExecutor(2) as ex: print(collections.Counter(ex.map(one,urls)))
