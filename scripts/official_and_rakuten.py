"""Pass 2 (Saga data only): (a) dining official-site og:image first (Tabelog 'homepage' field), Tabelog photo kept as fallback;
(b) Rakuten Travel stay fallback for towns with no Jalan stay. Polite 1.5s."""
import json,re,glob,subprocess,time,html as H,os,sys
OUT='/workspace/p1/data/saga/out'; MEDIA='/workspace/p1/wt-saga/media'
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
def get(u,t=20):
    r=subprocess.run(['curl','-sL','-A',UA,'--max-time',str(t),u],capture_output=True); time.sleep(1.5); return r.stdout.decode('utf-8','replace')
def dl(u,dest):
    r=subprocess.run(['curl','-sL','-A',UA,'--max-time','25','-o',dest,'-w','%{http_code}',u],capture_output=True,text=True); time.sleep(0.5)
    if r.stdout.strip()=='200' and os.path.exists(dest) and os.path.getsize(dest)>5000: return True
    if os.path.exists(dest): os.remove(dest)
    return False
SKIP=r'tabelog|instagram|facebook|twitter|x\.com|hotpepper|gnavi|retty|line\.me|ameblo|tiktok|youtube|google'
mode=sys.argv[1]
if mode=='official':
  for f in sorted(glob.glob(OUT+'/*/union.json')):
    u=json.load(open(f)); slug=f.split('/')[-2]; n=0
    for d in u['dining']:
        if d.get('photo_source')=='official' or not d.get('tabelog_url'): continue
        h=get(d['tabelog_url'])
        m=re.search(r'ホームページ</th>\s*<td>\s*<p class="homepage">\s*<a[^>]+href="([^"]+)"',h)
        hp=m and H.unescape(m.group(1)); d['official_url']=hp
        if not hp or re.search(SKIP,hp): continue
        hh=get(hp,15); og=re.search(r'property="og:image"\s+content="([^"]+)"',hh) or re.search(r'content="([^"]+)"\s+property="og:image"',hh)
        if not og: continue
        img=H.unescape(og.group(1)); img=img if img.startswith('http') else requests_join(hp,img) if False else (hp.rstrip('/')+'/'+img.lstrip('/'))
        fn=f'saga-{slug}-dining-{d["rst_id"]}-off.jpg'
        if dl(img,f'{MEDIA}/{fn}'):
            d['photo_fallback']=d.get('photo'); d['photo_credit_fallback']=d.get('photo_credit')
            d['photo']=f'../../media/{fn}'; d['photo_credit']=f'official site · Source {hp}'; d['photo_source']='official'; n+=1
    json.dump(u,open(f,'w'),ensure_ascii=False,indent=2); print(slug,'official',n,flush=True)
if mode=='rakuten':
  T={'kiyama':'基山町','miyaki':'みやき町','omachi':'大町町','shiroishi':'白石町'}
  nos=[]
  for p in range(1,12):
    h=get(f'https://search.travel.rakuten.co.jp/ds/yado/saga/p{p}')
    m=re.search(r'"displayedHotels":\[([\d,]*)\]',h)
    new=[x for x in (m.group(1).split(',') if m else []) if x and x not in nos]
    if not new: break
    nos+=new
  print('rakuten listed',len(nos),flush=True); R={}
  for no in nos:
    u=f'https://travel.rakuten.co.jp/HOTEL/{no}/{no}.html'; h=get(u)
    t=re.search(r'<title>(.*?)\s*宿泊予約',h); a=re.search(r'id="hotel-address"[^>]*>(.*?)<',h,re.S); im=re.search(r'og:image" content="([^"]+)',h)
    R[no]=dict(name_ja=H.unescape(t.group(1)).strip() if t else '',rakuten_url=u,address=re.sub(r'\s+','',H.unescape(a.group(1))) if a else '',image=im.group(1) if im else '')
  json.dump(R,open('/workspace/p1/data/saga/rakuten-saga.json','w'),ensure_ascii=False,indent=1)
  for slug,ja in T.items():
    f=f'{OUT}/{slug}/union.json'; u=json.load(open(f))
    for no,r in R.items():
        if ja in r['address'] and len(u['stay'])<12:
            fn=f'saga-{slug}-stay-rk{no}.jpg'; ok=r['image'] and dl(r['image'],f'{MEDIA}/{fn}')
            u['stay'].append(dict(name_ja=r['name_ja'],name_en='',rakuten_url=r['rakuten_url'],address=r['address'],source='rakuten',
              photo=f'../../media/{fn}' if ok else None,photo_credit=f'source · Source {r["rakuten_url"]}' if ok else None,photo_source='rakuten' if ok else None))
    u['rakuten_fallback']=True; json.dump(u,open(f,'w'),ensure_ascii=False,indent=2); print(slug,'rakuten stay',len(u['stay']),flush=True)
