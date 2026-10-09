import json,re,requests,concurrent.futures as cf,time
exec(open('scan.py').read().split('def reg')[0].split('dom=json.load')[0])  # imports
KW=re.compile(open('scan.py').read().split("KW=re.compile(r'")[1].split("',re.I)")[0],re.I)
e=json.load(open('errs.json')); dom=json.load(open('ext_links.json'))
def chk(x):
    u=dom[x['host']][0][1]
    for a in range(2):
        try:
            r=requests.get('https://r.jina.ai/'+u,timeout=60,headers={'X-Return-Format':'text'} if False else {})
            if r.status_code==429: time.sleep(10); continue
            t=r.text; title=(re.search(r'^Title:(.*)$',t,re.M) or [0,''])[1].strip()
            hits=sorted(set(m.group(0).lower() for m in KW.finditer(t)))[:10]
            return dict(host=x['host'],url=u,code=r.status_code,title=title[:100],hits=hits,len=len(t),warn=('Warning' in t[:600]) and t[:600].split('Warning:')[-1][:150] or '')
        except Exception as ex: err=str(ex)[:100]
    return dict(host=x['host'],url=u,err=err if 'err' in dir() else 'fail')
with cf.ThreadPoolExecutor(5) as ex: res=list(ex.map(chk,e))
json.dump(res,open('scan2.json','w'),ensure_ascii=False,indent=0)
print('done',len(res),sum(1 for r in res if r.get('hits')))
