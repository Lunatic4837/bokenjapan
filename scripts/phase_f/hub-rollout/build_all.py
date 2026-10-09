import re, json, os, html, collections, csv, subprocess, sys, glob
REPO='/workspace/p1/pr12-work'; BASEREF='ad21eb936e'; D='/workspace/p1/phase-d/rollout'; PV='/workspace/p1/phase-d/preview'
exec(open(D+'/rules.py').read())   # CAT, TB, DAILY_TB, TA_ORDER, DESC, CSLUG
only=set(sys.argv[1:])
def section(src,name):
    m=re.search(r'<section class="place-section"><h2>'+name+r'</h2><ul class="place-list">(.*?)</ul></section>',src,re.S)
    return re.findall(r'<li>.*?</li>',m.group(1),re.S) if m else []
def img(li):
    m=re.search(r'<img class="thumb" src="([^"]+)"[^>]*width="(\d+)" height="(\d+)"',li); return m and (m.group(1),int(m.group(2)),int(m.group(3)))
def name(li): return html.unescape(re.search(r'class="place-name">(.*?)</p>',li).group(1))
def blurb(li):
    m=re.search(r'class="place-blurb">(.*?)</p>',li); return html.unescape(m.group(1)) if m else ''
def esc(s): return html.escape(s,quote=True)
def plural(n): return f'{n} place' if n==1 else f'{n:,} places'
def gsplit(g): return [x.strip() for x in re.split(r'[、,]',g or '') if x.strip()]
def classify(x):
    gs=gsplit(x['genre'])
    if gs and gs[0] in DAILY_TB: return 'daily','tb',True
    for j,g in enumerate(gs):
        if g in TB: return TB[g],'tb',j==0
    if any(g in DAILY_TB for g in gs): return 'daily','tb',False
    cu=x['cuisines'] or []
    for tag,k in TA_ORDER:
        if tag in cu: return k,'ta',True
    d=x['desc'].lower()
    for rx,k in DESC:
        if re.search(rx,d): return k,'desc',False
    return 'other','none',False
def classify_sight(li,stay_bl):
    n=name(li); d=re.search(r'class="place-desc">(.*?)</p>',li).group(1); s=(n+' '+d).lower()
    if stay_bl and re.search(r'\bhotel\b',n.lower()): return 'dup-stay'
    if re.search(r'information cent(er|re)|kankojoho|tourist info|\bja\b|farm|chokubai|market',s): return 'daily'
    if re.search(r'museum|shrine|temple|garden|historic|ruins|castle|house|view|falls|gorge',s): return 'see'
    if re.search(r'hanabi|festival|matsuri|taiko|bonden|onsen|hot spring|baths|ski|experience|togei|resort|roadside station|brewery|shuzo|hiking|camp',s): return 'do'
    return 'see'
PATCH={'oita/taketa':[('<li><a href="https://www.jalan.net/yad388720/">','<li><a href="https://www.suijinnomori.com/">'),('<!-- sources: jalan_url=https://www.jalan.net/yad388720/ -->','<!-- sources: jalan_url=https://www.jalan.net/yad388720/ (Jalan listing suspended 2026-10-09; card links to official site) -->')],'fukuoka/asakura':[('<li><a href="https://www.jalan.net/yad369937/">','<li><a href="https://www.viewhotelheisei.com/">'),('<!-- sources: jalan_url=https://www.jalan.net/yad369937/ -->','<!-- sources: jalan_url=https://www.jalan.net/yad369937/ (Jalan listing suspended 2026-10-09; card links to official site) -->')]}
NOPH=[]; FIXLOG=[]; SUMMARY={}; TOT=collections.Counter()
def photofix(key,src,cards,res):
    m=re.search(r'(<h2>Dining</h2><ul class="place-list">)(.*?)(</ul>)',src,re.S)
    lis=re.findall(r'<li>.*?</li>',m.group(2),re.S); assert len(lis)==len(res)
    dims={}
    for li in lis:
        x=img(li)
        if x: dims[x[0]]=(x[1],x[2])
    ok={r['i'] for r in res if r.get('dist') is not None and r['dist']<=4}
    claimed={r['best'] for r in res if r['i'] in ok}
    out=[]; st=collections.Counter()
    for i,li in enumerate(lis):
        r=res[i]; nm=name(li); tag=re.search(r'<img class="thumb"[^>]*>',li)
        if i in ok:
            new=r['best']
            if new!=r['cur']:
                w,h=dims[new]; t2=re.sub(r'src="[^"]+"',f'src="{new}"',tag.group(0)); t2=re.sub(r'width="\d+" height="\d+"',f'width="{w}" height="{h}"',t2)
                li=li.replace(tag.group(0),t2); st['moved']+=1; FIXLOG.append([key,i+1,nm,r['cur'],new,'matched own listing photo'])
            else: st['correct']+=1
        elif tag and r['cur'] in claimed:
            li=re.sub(r'<!-- photo-credit:[^>]*-->','',li.replace(tag.group(0),'')); st['removed']+=1
            NOPH.append([f'{key}|Dining|{i}',nm,'r2-hash-vs-listing:'+(r.get('src') or ''),'card photo belonged to another card (photo-shift fix); own listing photo not on R2','hubfix-all',nm,(re.search(r'(?:tabelog_url|ta_url)=(\S+)',li) or [0,''])[1]])
            FIXLOG.append([key,i+1,nm,r['cur'],'','photo belonged to another card; no own photo found'])
        elif tag: st['kept-unverified']+=1
        else: st['no-photo']+=1
        out.append(li)
    return src[:m.start(2)]+''.join(out)+src[m.end(2):], st, ok
def build(key):
    pref,muni_slug=key.split('/'); PAGE=key
    if key=='akita/daisen-05212':
        src=open(PV+'/daisen-fixed.html').read()
        cards=json.load(open(PV+'/daisen_genres.json')); res=json.load(open(PV+'/photomatch.json'))
        ok={r['i'] for r in res if r.get('dist') is not None and r['dist']<=4}; st=collections.Counter(daisen_prefixed=1)
    else:
        src=subprocess.run(['git','-C',REPO,'show',f'{BASEREF}:{key}/index.html'],capture_output=True,text=True,check=True).stdout
        for a,b in PATCH.get(key,[]): assert a in src,(key,a); src=src.replace(a,b)
        cards=json.load(open(f'{D}/data/{key.replace("/","__")}.json')); res=json.load(open(f'{D}/match/{key.replace("/","__")}.json'))
        src,st,ok=photofix(key,src,cards,res)
    TOT.update(st)
    PREF=html.unescape(re.search(r'<p class="crumb"><a href="/">Japan</a> / <a href="\.\./">([^<]+)</a>',src).group(1))
    MUNI=html.unescape(re.search(r'<h1 class="page-title">([^<]+)</h1>',src).group(1))
    stay=section(src,'Stay'); dining=section(src,'Dining'); sights=section(src,'Sights')
    onsen=section(src,'Onsen'); shop=section(src,'Shop')+section(src,'Clinics')
    assert len(dining)==len(cards)
    for i,li in enumerate(dining): assert name(li)==html.unescape(cards[i]['name']),(key,i)
    cover=re.search(r'<figure class="cover"><img src="([^"]+)"',src).group(1)
    cap=re.search(r'<p class="city-cap-note">.*?</p>',src,re.S); cap=cap.group(0) if cap else ''
    eat=collections.defaultdict(list); daily_d=[]; primary={}; pure={}; assign=[]
    for i,li in enumerate(dining):
        k,basis,prim=classify(cards[i]); primary[i]=prim; pure[i]=prim and all(TB.get(g,k)==k for g in gsplit(cards[i]['genre']))
        assign.append(dict(page=key,rank=i+1,name=name(li),genre=cards[i]['genre'],ta=';'.join(cards[i]['cuisines'] or []),category=k,basis=basis,primary=prim))
        (daily_d if k=='daily' else eat[k]).append(i)
    stay_bl=[blurb(l).lower() for l in stay]+[name(l).lower() for l in stay]
    sg=collections.defaultdict(list)
    for li in sights: sg[classify_sight(li,stay_bl)].append(li)
    SECT={'stay':('Stay',stay),'eat':('Eat',[l for i,l in enumerate(dining) if i not in set(daily_d)]),'do':('Do',onsen+sg['do']),'see':('See',sg['see']),
          'daily':('Day to day',sg['daily']+shop+[dining[i] for i in daily_d])}
    HEAD_END=src.index('</head>'); BODY_START=src.index('<main class="page-main">')
    head=src[:HEAD_END]; mast=src[src.index('<body>'):BODY_START]
    me=src.rindex('</main>'); ls=src.rfind('\n',0,me)+1
    foot=src[ls:] if src[ls:me].strip()=='' else src[me:]
    foot_noscript=re.sub(r'\s*<script>.*?</script>','',foot,flags=re.S)
    def tile(href,label,n,li,big=True):
        im=img(li) if li else None
        pic=f'<img src="{im[0]}" alt="{esc(name(li))}" width="{im[1]}" height="{im[2]}" {"" if big else " loading=\"lazy\""} decoding="async">' if im else ''
        return (f'<li><a class="hub-tile{"" if big else " hub-tile-sm"}" href="{href}">{pic}'
                f'<span class="hub-tile-label"><span class="hub-tile-name">{esc(label)}</span>'
                f'<span class="hub-tile-count">{plural(n)}</span></span></a></li>')
    def first_with_img(lis,avoid=()):
        for l in lis:
            im=img(l)
            if im and im[0] not in avoid: return l
        return lis[0] if lis else None
    didx={id(l):i for i,l in enumerate(dining)}
    def pick_dining(idxs,need_primary):
        tiers=[lambda i:i in ok and (pure[i] or not need_primary), lambda i:i in ok and (primary[i] or not need_primary), lambda i:i in ok, lambda i:primary[i] or not need_primary, lambda i:True]
        for t in tiers:
            for i in idxs:
                if img(dining[i]) and t(i): return dining[i]
        return dining[idxs[0]] if idxs else None
    def subhead(title,desc,canon):
        h=head
        h=re.sub(r'<title>.*?</title>',f'<title>{esc(title)} · BokenJapan</title>',h)
        h=re.sub(r'(<link rel="canonical" href=")[^"]+',lambda m:m.group(1)+canon,h)
        h=re.sub(r'(<meta property="og:url" content=")[^"]+',lambda m:m.group(1)+canon,h)
        h=re.sub(r'(<meta property="og:title" content=")[^"]+',lambda m:m.group(1)+esc(title)+' · BokenJapan',h)
        h=re.sub(r'(<meta (?:name="description"|property="og:description") content=")[^"]+',lambda m:m.group(1)+esc(desc),h)
        h=h.replace('href="../../styles.css"','href="/styles.css"')
        h=re.sub(r'\s*<!--\s*Municipality boundaries:.*?-->','',h,flags=re.S)
        return h
    def mast_abs(m): return m.replace('href="../"',f'href="/{pref}/"')
    BASE=f'https://bokenjapan.com/{PAGE}/'
    def write(rel,doc):
        p=f'{REPO}/{PAGE}/{rel}index.html'; os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'w').write(doc)
    def subpage(rel,title,crumbs,h1,sub,body,desc):
        cr=' / '.join([f'<a href="/">Japan</a>',f'<a href="/{pref}/">{esc(PREF)}</a>',f'<a href="/{PAGE}/">{esc(MUNI)}</a>']+crumbs)
        return (subhead(title,desc,BASE+rel)+'</head>\n'+mast_abs(mast).replace('<body>','<body class="hubbed">')+
          f'<main class="page-main">\n    <p class="crumb">{cr}</p>\n    <h1 class="page-title">{esc(h1)}</h1>\n    <p class="page-sub">{esc(sub)}</p>\n'+cap+body+'\n'+foot_noscript)
    def plist(lis,h2): return f'<section class="place-section"><h2 class="visually-hidden">{esc(h2)}</h2><ul class="place-list">{"".join(lis)}</ul></section>'
    import shutil
    for d in glob.glob(f'{REPO}/{PAGE}/*/'): shutil.rmtree(d)
    SLUG={'stay':'stay','eat':'eat','do':'do','see':'see','daily':'day-to-day'}
    tiles=[]
    for key2 in ['stay','eat','do','see','daily']:
        label,lis=SECT[key2]
        if not lis: continue
        if key2=='eat': rep=pick_dining([didx[id(l)] for l in lis],False)
        else: rep=first_with_img(lis,avoid=(cover,) if key2 in ('do','see') else ())
        tiles.append(tile(SLUG[key2]+'/',label,len(lis),rep))
        if key2=='eat': continue
        write(SLUG[key2]+'/',subpage(SLUG[key2]+'/',f'{label} · {MUNI}',[esc(label)],f'{label} in {MUNI}',f'{MUNI} · {PREF} · {plural(len(lis))}',plist(lis,label),f'{label} in {MUNI}, {PREF}: ranked places.'))
    etiles=[]; counts={}
    for k,lab in CAT:
        idxs=eat.get(k,[])
        if not idxs: continue
        lis=[dining[i] for i in idxs]; counts[lab]=len(lis)
        etiles.append(tile(CSLUG[k]+'/',lab,len(lis),pick_dining(idxs,k not in ('other',)),big=False))
        write(f'eat/{CSLUG[k]}/',subpage(f'eat/{CSLUG[k]}/',f'{lab} · Eat · {MUNI}',[f'<a href="/{PAGE}/eat/">Eat</a>',esc(lab)],lab,f'Eat in {MUNI} · {plural(len(lis))}',plist(lis,lab),f'{lab} in {MUNI}, {PREF}: ranked restaurants.'))
    if SECT['eat'][1]:
        nEat=len(SECT['eat'][1])
        write('eat/',subpage('eat/',f'Eat · {MUNI}',['Eat'],f'Eat in {MUNI}',f'{MUNI} · {PREF} · {plural(nEat)}',
           f'<section class="hub"><h2 class="visually-hidden">Cuisines</h2><ul class="hub-tiles hub-tiles-sm">{"".join(etiles)}</ul></section>',f'Restaurants in {MUNI}, {PREF}, by cuisine.'))
    start=src.index('<section class="place-section"><h2>Stay</h2>') if '<h2>Stay</h2>' in src else src.index('<section class="place-section">')
    end=src.rindex('</section>')+len('</section>')
    assert '<section class="place-section">' not in src[end:]
    sn=re.search(r'<section class="place-section"><h2>Stay</h2><p class="stay-none">.*?</p></section>',src,re.S)
    hub=src[:start]+(sn.group(0) if sn and not stay else '')+f'<section class="hub"><h2 class="visually-hidden">Explore {esc(MUNI)}</h2><ul class="hub-tiles">{"".join(tiles)}</ul></section>'+src[end:]
    hub=hub.replace('<body>','<body class="hubbed">',1)
    open(f'{REPO}/{PAGE}/index.html','w').write(hub)
    SUMMARY[key]=dict(sections={k:len(v[1]) for k,v in SECT.items()},eat=counts,photo=dict(st),dup_stay=[name(l) for l in sg['dup-stay']])
    return assign
pages=sorted(f.split('/')[-2]+'/'+f.split('/')[-1] for f in [os.path.dirname(p) for p in glob.glob(REPO+'/*/*/index.html')] if f.split('/')[-2] in ('miyagi','akita','fukuoka','yamaguchi','oita'))
pages=[p for p in pages if (not only) or p.split('/')[0] in only or p in only]
A=[]
for k in pages:
    if k!='akita/daisen-05212' and not os.path.exists(f'{D}/match/{k.replace("/","__")}.json'): print('SKIP no match',k); continue
    A+=build(k)
json.dump(SUMMARY,open(D+'/summary.json','w'),ensure_ascii=False,indent=1)
with open(D+'/photo-fix.csv','w',newline='') as f: w=csv.writer(f); w.writerow(['page','rank','name','old_img','new_img','note']); w.writerows(FIXLOG)
with open(D+'/noph-pending.csv','w',newline='') as f: csv.writer(f).writerows(NOPH)
with open(D+'/eat-categories.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(A[0])); w.writeheader(); w.writerows(A)
print(len(SUMMARY),'pages',dict(TOT),'noph',len(NOPH))
