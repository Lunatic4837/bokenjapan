import json, hashlib, io, os, csv, requests
from PIL import Image
P=[ # page, covdir, match(url substring), credit label, source page, alt
('oita/bungoono','oita_bungoono','原尻の滝⑧','豊後大野市観光協会 さとのたび','https://sato-no-tabi.jp/introduce/原尻の滝/','Harajiri Falls, the "Niagara of the East," in Bungo-Ono'),
('oita/bungotakada','oita_bungotakada','62_img1.jpg','豊後高田市 昭和の町','https://www.city.bungotakada.oita.jp/site/showanomachi/','Sunset over the tidal flats of Matama Beach, Bungo-Takada'),
('oita/hiji','oita_hiji','Spot_40_image','日出町観光協会 ひじなび','https://hijinavi.com/spots/detail/40','Sunset over the Kanawa Islands, Hiji'),
('oita/himeshima','oita_himeshima','ogp.jpg','姫島村 観光情報','https://www.himeshima.jp/kankou/','Aerial view of the coast of Himeshima Island'),
('oita/hita','oita_hita','mameda_1','日田市観光協会 おいでひた','https://oidehita.com/archives/29493','Old merchant houses along Mameda-machi street, Hita'),
('oita/kunisaki','oita_kunisaki','10b172935309ae8c8be2af6a3c4baf1c','国東市観光協会','https://visit-kunisaki.com/','Stone Nio guardians on the approach to Futago-ji Temple, Kunisaki'),
('oita/kusu','oita_kusu','kikankokouen02','玖珠町観光協会','https://kusumachi.jp/kikankokouen/','Steam locomotive and the Bungo-Mori Roundhouse, Kusu'),
('oita/nakatsu','oita_nakatsu','202504251210391868','中津耶馬渓観光協会','https://nakatsuyaba.com/pages/86/','Cyclists on the Maple Yaba Cycling Road, Nakatsu'),
('oita/saiki','oita_saiki','7e550741','佐伯市観光ナビ','https://www.visit-saiki.jp/photos/detail/7e550741-dde3-4664-8df0-97ebabd20bd9','Sunrise between the Bungo Futamigaura wedded rocks, Saiki'),
('oita/taketa','oita_taketa','value01/b0','たけ旅 竹田市観光ツーリズム協会','https://taketa.guide/spots/detail/07fb5cc5-fa6c-4eee-9b51-fea20d2b67fc','Autumn maples along the stone walls of Oka Castle ruins, Taketa'),
('oita/tsukumi','URL:https://tsukumiryoku.com/files/libs/2638/202006120942323686.jpg?1652833133','','津久見市観光協会','https://tsukumiryoku.com/pages/43/','Kawazu cherry blossoms above the sea on the Yotsuura Peninsula, Tsukumi'),
('oita/usa','oita_usa','202412161651498015','宇佐市観光協会','https://www.usa-kanko.jp/','Vermilion halls of Usa Jingu beside a giant camphor tree'),
('akita/ugo','akita_ugo','IMG_0045-2-2048x1365','羽後町観光物産協会','https://ugokanko.com/nishimonaibonodori2026/','Dancers of the Nishimonai Bon Odori at night, Ugo'),
]
os.makedirs('stage_cov/media',exist_ok=True); out=[]
for page,cd,sub,lab,src,alt in P:
    if cd.startswith('URL:'):
        url=cd[4:]; raw=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0'}).content
    else:
        idx=json.load(open(f'cov/{cd}/index.json'))
        hits=[x for x in idx if sub in x['url']]
        if page=='oita/taketa': hits=[idx[24]]
        assert len(hits)>=1,(page,sub); x=hits[0]; url=x['url']; raw=open(f'cov/{cd}/'+x['file'],'rb').read()
    im=Image.open(io.BytesIO(raw)).convert('RGB')
    if im.width>2000: im=im.resize((2000,round(im.height*2000/im.width)),Image.LANCZOS)
    b=io.BytesIO(); im.save(b,'JPEG',quality=86,optimize=True,progressive=True); d=b.getvalue()
    muni=page.split('/')[1]; key=f'media/{muni}-cover-w5-{hashlib.sha256(d).hexdigest()[:8]}.jpg'
    open('stage_cov/'+key,'wb').write(d)
    out.append(dict(page=page,key=key,w=im.width,h=im.height,bytes=len(d),sha256=hashlib.sha256(d).hexdigest(),img_url=url,label=lab,src=src,alt=alt))
    print(page,key,im.size,len(d),url[:90])
json.dump(out,open('covers-w5.json','w'),ensure_ascii=False,indent=1)
with open('r2-manifest-w5-covers.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['key','bytes','sha256'])
    for o in out: w.writerow([o['key'],o['bytes'],o['sha256']])
