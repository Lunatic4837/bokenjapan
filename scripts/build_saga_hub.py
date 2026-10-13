import re,glob,os,html,json,collections,shutil
R='/workspace/p1/wt-saga'
def esc(s): return html.escape(s,quote=True)
def plural(n): return f'{n} place' if n==1 else f'{n:,} places'
def name(li): return html.unescape(re.search(r'class="place-name">(.*?)</p>',li).group(1))
def img(li):
    m=re.search(r'<img class="thumb" src="([^"]+)"',li); return m and m.group(1)
def absmedia(s): return s.replace('src="../../media/','src="/media/').replace('src="../../logo.svg"','src="/logo.svg"')
def cls(li):
    s=name(li).lower()
    if re.search(r'town hall|city hall|information|kanko|tourist|michi|roadside|market|chokubai|ja |farm|shop|store',s): return 'daily'
    if re.search(r'onsen|spa|ski|camp|park|beach|festival|matsuri|experience|kiln|gama|kama|brew|shuzo|golf|cycling|hiking|course|fishing|pottery|yaki|cruise|ranch|pool|resort',s): return 'do'
    return 'see'
S={}
for p in sorted(glob.glob(R+'/saga/*/index.html')):
    town=p.split('/')[-2]; src=open(p).read(); PAGE=f'saga/{town}'
    m=re.search(r'<section class="place-section"><h2>Sights</h2><ul class="place-list">(.*?)</ul></section>',src,re.S)
    lis=re.findall(r'<li>.*?</li>',m.group(1),re.S)
    MUNI=html.unescape(re.search(r'<h1 class="page-title">([^<]+)</h1>',src).group(1)); PREF='Saga'
    cover=(re.search(r'<figure class="cover"><img src="([^"]+)"',src) or [0,''])[1]
    G=collections.defaultdict(list)
    for li in lis: G[cls(li)].append(li)
    head=src[:src.index('</head>')]; mast=src[src.index('<body>'):src.index('<main class="page-main">')]
    me=src.rindex('</main>'); foot=re.sub(r'\s*<script>.*?</script>','',src[me:],flags=re.S)
    BASE=f'https://bokenjapan.com/{PAGE}/'
    def subhead(title,desc,canon):
        h=re.sub(r'<title>.*?</title>',f'<title>{esc(title)} · BokenJapan</title>',head)
        h=h.replace('href="../../styles.css"','href="/styles.css"')
        h=re.sub(r'\s*<!--\s*Municipality boundaries:.*?-->','',h,flags=re.S)
        return h+f'  <link rel="canonical" href="{canon}">\n  <meta name="description" content="{esc(desc)}">\n'
    for d in glob.glob(f'{R}/{PAGE}/*/'): shutil.rmtree(d)
    tiles=[]
    for k,label,slug in [('do','Do','do'),('see','See','see'),('daily','Day to day','day-to-day')]:
        L=G[k]
        if not L: continue
        rep=next((l for l in L if img(l) and (k=='daily' or img(l)!=cover)),None) or next((l for l in L if img(l)),None)
        pic=f'<img src="{absmedia("src="+chr(34)+img(rep)+chr(34))[5:-1]}" alt="{esc(name(rep))}" width="300" height="225" decoding="async">' if rep else ''
        tiles.append(f'<li><a class="hub-tile" href="{slug}/">{pic}<span class="hub-tile-label"><span class="hub-tile-name">{label}</span><span class="hub-tile-count">{plural(len(L))}</span></span></a></li>')
        cr=f'<a href="/">Japan</a> / <a href="/saga/">Saga</a> / <a href="/{PAGE}/">{esc(MUNI)}</a> / {label}'
        body=f'<section class="place-section"><h2 class="visually-hidden">{label}</h2><ul class="place-list">{"".join(L)}</ul></section>'
        doc=(subhead(f'{label} · {MUNI}',f'{label} in {MUNI}, Saga: places.',BASE+slug+'/')+'</head>\n'+absmedia(mast).replace('<body>','<body class="hubbed">').replace('href="../"','href="/saga/"')+
             f'<main class="page-main">\n    <p class="crumb">{cr}</p>\n    <h1 class="page-title">{label} in {esc(MUNI)}</h1>\n    <p class="page-sub">{esc(MUNI)} · Saga · {plural(len(L))}</p>\n'+absmedia(body)+'\n  '+absmedia(foot))
        os.makedirs(f'{R}/{PAGE}/{slug}',exist_ok=True); open(f'{R}/{PAGE}/{slug}/index.html','w').write(doc)
    hub=src[:m.start()]+f'<section class="hub"><h2 class="visually-hidden">Explore {esc(MUNI)}</h2><ul class="hub-tiles">{"".join(tiles)}</ul></section>'+src[m.end():]
    open(p,'w').write(hub.replace('<body>','<body class="hubbed">',1))
    S[PAGE]={k:len(v) for k,v in G.items()}
json.dump(S,open('/workspace/p1/saga-build/summary-saga.json','w'),indent=1)
print(len(S),'towns',sum(sum(v.values()) for v in S.values()),'listings',sum(len(v) for v in S.values()),'subpages')
