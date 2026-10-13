import re,json,subprocess,time,glob,html,os
ids=sorted(set(re.findall(r'asobo-saga\.jp/spots/detail/([0-9a-f-]+)',''.join(open(f).read() for f in glob.glob('/workspace/p1/wt-saga/saga/**/index.html',recursive=True)))))
OUT='/workspace/p1/data/saga/sights-ja.json'; D=json.load(open(OUT)) if os.path.exists(OUT) else {}
for i in ids:
    if i in D: continue
    u=f'https://www.asobo-saga.jp/spots/detail/{i}'
    h=subprocess.run(['curl','-sL','-A','Mozilla/5.0','--max-time','25',u],capture_output=True).stdout.decode('utf-8','replace')
    t=re.search(r'<title>([^|<]+)',h); d=re.search(r'og:description" content="([^"]*)',h)
    cats=re.findall(r'class="[^"]*tag[^"]*"[^>]*>\s*([^<]{1,20})<',h)
    D[i]=dict(url=u,name_ja=html.unescape(t.group(1).strip()) if t else None,desc_ja=html.unescape(d.group(1)) if d else None,tags=list(dict.fromkeys(c.strip() for c in cats))[:8])
    json.dump(D,open(OUT,'w'),ensure_ascii=False,indent=1); time.sleep(1.5)
print(len(D))
