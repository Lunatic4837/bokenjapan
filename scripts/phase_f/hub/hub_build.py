import re, json, os, html, collections
REPO='/workspace/p1/pr12-work'; PAGE='akita/daisen-05212'; MUNI='Daisen'; PREF='Akita'
src=open('/workspace/p1/phase-d/preview/daisen-fixed.html').read()
G={x['i']:x for x in json.load(open('/workspace/p1/phase-d/preview/daisen_genres.json'))}
def section(name):
    m=re.search(r'<section class="place-section"><h2>'+name+r'</h2><ul class="place-list">(.*?)</ul></section>',src,re.S)
    return re.findall(r'<li>.*?</li>',m.group(1),re.S) if m else []
stay=section('Stay'); dining=section('Dining'); sights=section('Sights')
def img(li):
    m=re.search(r'<img class="thumb" src="([^"]+)"[^>]*width="(\d+)" height="(\d+)"',li); return m and (m.group(1),int(m.group(2)),int(m.group(3)))
def name(li): return html.unescape(re.search(r'class="place-name">(.*?)</p>',li).group(1))
cover=re.search(r'<figure class="cover"><img src="([^"]+)"',src).group(1)
# ---------- cuisine classification ----------
CAT=[('seafood','Japanese (seafood)'),('meat','Japanese (meat)'),('noodles','Japanese (noodles)'),('european','European'),('cafe','Cafe'),('curry','Curry'),('casual','Casual'),('chinese','Chinese & Asian'),('izakaya','Izakaya & bars'),('sweets','Sweets & bakeries'),('japanese','Other Japanese'),('other','Other')]
TB={}
for k,gs in {
 'seafood':'寿司 回転寿司 海鮮 魚介料理・海鮮料理 魚介料理 海鮮丼 ふぐ かに うなぎ あなご 牡蠣 魚料理 シーフード',
 'meat':'焼肉 ホルモン 焼き鳥 串焼き とんかつ かつ丼 すき焼き しゃぶしゃぶ ステーキ 鶏料理 肉料理 ジンギスカン もつ鍋 からあげ 牛タン 鉄板焼き 馬肉料理 ハンバーグ',
 'noodles':'ラーメン つけ麺 そば うどん 麺類 油そば・まぜそば 沖縄そば 冷麺 ちゃんぽん 担々麺 中華そば 立ち食いそば 焼きそば',
 'european':'イタリアン パスタ ピザ フレンチ ヨーロッパ料理 洋食 オムライス ビストロ バル スペイン料理 西洋料理 アメリカ料理 ステーキ・ハンバーグ',
 'cafe':'カフェ 喫茶店 コーヒースタンド ジューススタンド コーヒー専門店 紅茶専門店',
 'curry':'カレー インドカレー スープカレー インド料理 ネパール料理',
 'casual':'食堂 ファミレス 定食・食堂 定食 ハンバーガー 丼 天丼 弁当 おにぎり 惣菜・デリ ビュッフェ 牛丼 親子丼 お好み焼き たこ焼き もんじゃ焼き 揚げ物 コロッケ 売店 ケバブ',
 'chinese':'中華料理 餃子 台湾料理 韓国料理 東南アジア料理 タイ料理 ベトナム料理 アジア・エスニック トルコ料理',
 'izakaya':'居酒屋 バー ダイニングバー 焼酎バー ビアバー パブ 日本酒バー ワインバー 立ち飲み スナック カラオケ',
 'sweets':'ケーキ 洋菓子 和菓子 パン ベーグル たい焼き・大判焼き かき氷 ジェラート・アイスクリーム ソフトクリーム クレープ・ガレット チョコレート スイーツ どら焼き 甘味処 サンドイッチ ドーナツ パフェ',
 'japanese':'日本料理 郷土料理 きりたんぽ 天ぷら おでん 釜飯 鍋 創作料理 沖縄料理 和食 懐石・会席料理 割烹・小料理 野菜料理 すっぽん 串揚げ 豆腐料理 そうめん 創作和食 精進料理',
}.items():
    for g in gs.split(): TB.setdefault(g,k)
DAILY_TB={'コンビニ・スーパー'}
TA_ORDER=[('Sushi','seafood'),('Seafood','seafood'),('Ramen','noodles'),('Barbecue','meat'),('Steakhouse','meat'),('Italian','european'),('French','european'),('Pizza','european'),('European','european'),('Spanish','european'),('American','european'),('German','european'),('Cafe','cafe'),('Indian','curry'),('Chinese','chinese'),('Korean','chinese'),('Asian','chinese'),('Thai','chinese'),('Izakaya (Japanese Style Tavern)','izakaya'),('Bar','izakaya'),('Pub','izakaya'),('Dessert','sweets'),('Bakery','sweets'),('Fast Food','casual'),('Diner','casual'),('Japanese','japanese'),('Japanese - Other ','japanese')]
DESC=[(r'sweets|bakery|cake|confection','sweets'),(r'ramen|soba|udon|noodle','noodles'),(r'sushi|seafood','seafood'),(r'izakaya|\bbar\b|pub','izakaya'),(r'caf[eé]|coffee','cafe'),(r'curry','curry'),(r'yakiniku|yakitori|tonkatsu|grill','meat'),(r'italian|french|pizz|western','european'),(r'chinese|korean|asian','chinese'),(r'diner|canteen|family restaurant|bento','casual'),(r'japanese','japanese')]
def classify(i,li):
    x=G[i]; gs=[g.strip() for g in re.split(r'[、,]',x['genre'] or '') if g.strip()]
    if gs and gs[0] in DAILY_TB: return 'daily','Tabelog genre '+gs[0]
    for g in gs:
        if g in TB: return TB[g],'Tabelog genre '+g
    if gs and any(g in DAILY_TB for g in gs): return 'daily','Tabelog genre コンビニ・スーパー'
    cu=x['cuisines'] or []
    for tag,k in TA_ORDER:
        if tag in cu: return k,'TripAdvisor cuisine '+tag.strip()
    d=x['desc'].lower()
    for rx,k in DESC:
        if re.search(rx,d): return k,'card line-4 genre word'
    return 'other','no genre in listing'
eat=collections.defaultdict(list); daily_d=[]; why=collections.Counter(); assign=[]
for i,li in enumerate(dining):
    assert name(li)==html.unescape(G[i]['name']),i
    k,basis=classify(i,li); why[(k,basis.split(' ')[0])]+=1
    assign.append(dict(rank=i+1,name=name(li),genre=G[i]['genre'],ta=G[i]['cuisines'],category=k,basis=basis))
    (daily_d if k=='daily' else eat[k]).append(li)
# ---------- sights: Do / See / Day to day ----------
stay_names=' '.join(name(l) for l in stay)
def classify_sight(li):
    n=name(li); d=re.search(r'class="place-desc">(.*?)</p>',li).group(1); s=(n+' '+d).lower()
    if re.search(r'\bhotel\b',s): return 'dup-stay'
    if re.search(r'information center|kankojoho|tourist info|\bja\b|farm|famazumagatto|chokubai|market',s): return 'daily'
    if re.search(r'museum|shrine|temple|garden|historic|ruins|castle|house|view|falls|gorge',s): return 'see'
    if re.search(r'hanabi|festival|matsuri|taiko|bonden|onsen|hot spring|baths|ski|experience|togei|resort|roadside station|brewery|shuzo|hiking|camp',s): return 'do'
    return 'see'
sg=collections.defaultdict(list)
for li in sights: sg[classify_sight(li)].append(li)
SECT={'stay':('Stay',stay),'eat':('Eat',[l for k,_ in CAT for l in eat.get(k,[])]),'do':('Do',sg['do']),'see':('See',sg['see']),'daily':('Day to day',sg['daily']+daily_d)}
# Eat total keeps global order
SECT['eat']=('Eat',[l for l in dining if l not in daily_d])
# ---------- html helpers ----------
HEAD_END=src.index('</head>'); BODY_START=src.index('<main class="page-main">')
head=src[:HEAD_END]; mast=src[src.index('<body>'):BODY_START]
foot=src[src.index('  </main>'):]
foot_noscript=re.sub(r'\s*<script>.*?</script>','',foot,flags=re.S)
def plural(n): return f'{n} place' if n==1 else f'{n:,} places'
def esc(s): return html.escape(s,quote=True)
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
def subhead(title,desc,canon):
    h=head
    h=re.sub(r'<title>.*?</title>',f'<title>{esc(title)} · BokenJapan</title>',h)
    h=re.sub(r'(<link rel="canonical" href=")[^"]+',r'\g<1>'+canon,h)
    h=re.sub(r'(<meta property="og:url" content=")[^"]+',r'\g<1>'+canon,h)
    h=re.sub(r'(<meta property="og:title" content=")[^"]+',r'\g<1>'+esc(title)+' · BokenJapan',h)
    h=re.sub(r'(<meta (?:name="description"|property="og:description") content=")[^"]+',r'\g<1>'+esc(desc),h)
    h=h.replace('href="../../styles.css"','href="/styles.css"')
    h=re.sub(r'\s*<!--\s*Municipality boundaries:.*?-->','',h,flags=re.S)
    return h
def mast_abs(m): return m.replace('href="../"','href="/akita/"')
BASE=f'https://bokenjapan.com/{PAGE}/'
def write(rel,doc):
    p=f'{REPO}/{PAGE}/{rel}index.html'; os.makedirs(os.path.dirname(p),exist_ok=True); open(p,'w').write(doc)
def subpage(rel,title,crumbs,h1,sub,body,desc):
    cr=' / '.join([f'<a href="/">Japan</a>',f'<a href="/akita/">{PREF}</a>',f'<a href="/{PAGE}/">{MUNI}</a>']+crumbs)
    return (subhead(title,desc,BASE+rel)+'</head>\n'+mast_abs(mast).replace('<body>','<body class="hubbed">')+
      f'<main class="page-main">\n    <p class="crumb">{cr}</p>\n    <h1 class="page-title">{esc(h1)}</h1>\n    <p class="page-sub">{esc(sub)}</p>\n'+body+'\n'+foot_noscript)
def plist(lis,h2): return f'<section class="place-section"><h2 class="visually-hidden">{esc(h2)}</h2><ul class="place-list">{"".join(lis)}</ul></section>'
# ---------- sub-pages ----------
SLUG={'stay':'stay','eat':'eat','do':'do','see':'see','daily':'day-to-day'}
tiles=[]
for key in ['stay','eat','do','see','daily']:
    label,lis=SECT[key]
    if not lis: continue
    rep=first_with_img(lis,avoid=(cover,) if key in ('do','see') else ())
    tiles.append(tile(SLUG[key]+'/',label,len(lis),rep))
    if key=='eat': continue
    write(SLUG[key]+'/',subpage(SLUG[key]+'/',f'{label} · {MUNI}',[esc(label)],f'{label} in {MUNI}',f'{MUNI} · {PREF} · {plural(len(lis))}',plist(lis,label),f'{label} in {MUNI}, {PREF}: ranked places.'))
# eat hub + cuisine pages
CSLUG={'seafood':'seafood','meat':'meat','noodles':'noodles','european':'european','cafe':'cafe','curry':'curry','casual':'casual','chinese':'chinese-asian','izakaya':'izakaya-bars','sweets':'sweets-bakeries','japanese':'other-japanese','other':'other'}
etiles=[]; counts={}
for k,lab in CAT:
    lis=[l for l in dining if l in eat.get(k,[])]
    if not lis: continue
    counts[lab]=len(lis)
    etiles.append(tile(CSLUG[k]+'/',lab,len(lis),first_with_img(lis),big=False))
    write(f'eat/{CSLUG[k]}/',subpage(f'eat/{CSLUG[k]}/',f'{lab} · Eat · {MUNI}',[f'<a href="/{PAGE}/eat/">Eat</a>',esc(lab)],lab,f'Eat in {MUNI} · {plural(len(lis))}',plist(lis,lab),f'{lab} in {MUNI}, {PREF}: ranked restaurants.'))
nEat=len(SECT['eat'][1])
write('eat/',subpage('eat/',f'Eat · {MUNI}',['Eat'],f'Eat in {MUNI}',f'{MUNI} · {PREF} · {plural(nEat)}',
   f'<section class="hub"><h2 class="visually-hidden">Cuisines</h2><ul class="hub-tiles hub-tiles-sm">{"".join(etiles)}</ul></section>',f'Restaurants in {MUNI}, {PREF}, by cuisine.'))
# ---------- hub (replace sections) ----------
start=src.index('<section class="place-section"><h2>Stay</h2>'); end=src.rindex('</section>')+len('</section>')
hub=src[:start]+f'<section class="hub"><h2 class="visually-hidden">Explore {MUNI}</h2><ul class="hub-tiles">{"".join(tiles)}</ul></section>'+src[end:]
hub=hub.replace('<body>','<body class="hubbed">',1)
open(f'{REPO}/{PAGE}/index.html','w').write(hub)
json.dump(dict(sections={k:len(v[1]) for k,v in SECT.items()},eat_categories=counts,sights_split={k:[name(l) for l in v] for k,v in sg.items()},daily_from_dining=[name(l) for l in daily_d],basis=collections.Counter(a['basis'].split(' genre')[0].split(' cuisine')[0] for a in assign)),open('/workspace/p1/phase-d/preview/daisen-summary.json','w'),ensure_ascii=False,indent=1)
import csv
with open('/workspace/p1/phase-d/preview/daisen-eat-categories.csv','w',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(assign[0])); w.writeheader(); w.writerows(assign)
print(json.dumps({k:len(v[1]) for k,v in SECT.items()}),counts)
