import re, json, io, time, html, hashlib, os, requests, urllib.parse as U
from PIL import Image
S=requests.Session(); S.headers['User-Agent']='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/129.0'
os.makedirs('cov/oita_kitsuki2',exist_ok=True); imgs={}
for n in range(1,170):
    u=f'https://kit-suki.com/pages/{n}/'
    try: r=S.get(u,timeout=(8,20)); time.sleep(0.4)
    except Exception: continue
    if r.status_code!=200: continue
    t=r.text; title=html.unescape((re.search(r'<title>(.*?)</title>',t,re.S) or [0,''])[1]).strip()
    for m in re.finditer(r'(?:src|href)=["\']([^"\']+/files/libs/[^"\']+\.(?:jpe?g|png)[^"\']*)',t,re.I):
        iu=U.urljoin(u,html.unescape(m.group(1)))
        if iu not in imgs: imgs[iu]=dict(page=u,title=title)
keep=[]
for iu,meta in imgs.items():
    if not re.search(r'坂|武家|城|町|景|kitsuki|杵築',meta['title']): continue
    try: r=S.get(iu,timeout=(8,25)); time.sleep(0.3); im=Image.open(io.BytesIO(r.content)); w,h=im.size
    except Exception: continue
    if w>=1000 and 1.2<=w/h<=2.5:
        fn=hashlib.md5(iu.encode()).hexdigest()[:12]+'.jpg'; open('cov/oita_kitsuki2/'+fn,'wb').write(r.content); keep.append(dict(file=fn,url=iu,w=w,h=h,alt='',**meta))
json.dump(keep,open('cov/oita_kitsuki2/index.json','w'),ensure_ascii=False,indent=0)
print(len(imgs),len(keep))
