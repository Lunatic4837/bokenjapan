#!/usr/bin/env python3
"""Make bokenjapan.com AI-agent friendly. Re-runnable and idempotent.
Usage (from the gh-pages checkout root):  python3 scripts/agent_friendly.py [--root .]
Generates: llms.txt, llms-full.txt, robots.txt, sitemap.xml, data/*.json, data/README.md,
inserts JSON-LD between <!-- bj-jsonld:start --> / <!-- bj-jsonld:end --> markers in <head>,
and replaces the '@boken_japan' text label with '@bokenjapan' (emails untouched).
Facts come only from each page's own HTML (plus scripts/town-geo.json coordinates)."""
import os,re,json,html,sys,datetime
ROOT=sys.argv[sys.argv.index('--root')+1] if '--root' in sys.argv else '.'
BASE='https://bokenjapan.com/'
SAME=['https://x.com/bokenjapan','https://www.instagram.com/bokenjapan/','https://www.tiktok.com/@bokenjapan','https://www.facebook.com/profile.php?id=61595415860080']
SKIP={'.git','media','go','data','scripts','node_modules'}
GEO=json.load(open(os.path.join(ROOT,'scripts/town-geo.json'))) if os.path.exists(os.path.join(ROOT,'scripts/town-geo.json')) else {}
M0,M1='<!-- bj-jsonld:start -->','<!-- bj-jsonld:end -->'
N0,N1='<!-- bj-nav:start -->','<!-- bj-nav:end -->'
D0,D1='<!-- bj-meta:start -->','<!-- bj-meta:end -->'
import subprocess
def git_dates():
    # last content commit date per file; generated commits are tagged [agent-friendly] and skipped
    try: out=subprocess.run(['git','-C',ROOT,'log','--format=@%cs','--name-only','--invert-grep','-E','--grep=\\[agent-friendly\\]|AI-agent friendly site','HEAD'],capture_output=True,text=True).stdout
    except Exception: return {}
    d={};cur=None
    for l in out.splitlines():
        if l.startswith('@'): cur=l[1:]
        elif l and l not in d: d[l]=cur
    return d
DATES=git_dates()
def crumb(s):
    m=re.search(r'(?s)<p class="crumb">(.*?)</p>',s); return [txt(x) for x in re.split(r'\s/\s',m.group(1))] if m else []
def strip_block(s,a,b): return re.sub(re.escape(a)+r'.*?'+re.escape(b)+r'\n?','',s,flags=re.S)
def txt(s): return re.sub(r'\s+',' ',html.unescape(re.sub(r'<[^>]+>',' ',s or ''))).strip()
def pages():
    for dp,dn,fn in os.walk(ROOT):
        dn[:]=sorted(d for d in dn if d not in SKIP and not d.startswith('.'))
        for f in sorted(fn):
            if f.endswith('.html'): yield os.path.relpath(os.path.join(dp,f),ROOT).replace(os.sep,'/')
def url(rel): return BASE+(rel[:-10] if rel.endswith('index.html') else rel)
def sections(s):
    out={}
    for m in re.finditer(r'(?s)<section class="place-section"><h2>(.*?)</h2>(.*?)</section>',s):
        name=txt(m.group(1)); body=m.group(2)
        if name=='Official':
            links=[(txt(a.group(2)),a.group(1)) for a in re.finditer(r'<a href="([^"]+)"[^>]*>(.*?)</a>',body)]
            dl={txt(d.group(1)):txt(d.group(2)) for d in re.finditer(r'(?s)<dt>(.*?)</dt><dd>(.*?)</dd>',body)}
            out['Official']={'links':[{'label':l,'url':u} for l,u in links],**{k.lower():v for k,v in dl.items()}}
            continue
        items=[]
        for li in re.finditer(r'(?s)<li>(.*?)</li>',body):
            b=li.group(1); n=re.search(r'(?s)<p class="place-name">(.*?)</p>',b)
            if not n: continue
            meta=re.search(r'(?s)<p class="place-meta">(.*?)</p>',b); mt=meta.group(1) if meta else ''
            src=re.search(r'<a href="(https?://[^"]+)"',mt)
            items.append({'name':txt(n.group(1)),'locality':txt(mt.split('·')[0]) if mt else None,'source_url':src.group(1) if src else None})
        out[name]=items
    return out
def place(t,i):
    d={'@type':t,'name':i['name']}
    if i.get('locality'): d['address']={'@type':'PostalAddress','addressLocality':i['locality'],'addressCountry':'JP'}
    if i.get('source_url'): d['url']=i['source_url']
    return d
ORG={'@type':'Organization','@id':BASE+'#org','name':'BokenJapan','url':BASE,'logo':BASE+'logo.svg','sameAs':SAME}
SITE={'@type':'WebSite','@id':BASE+'#website','name':'BokenJapan','url':BASE,'publisher':{'@id':BASE+'#org'},'inLanguage':'en'}
prefs={}; towns={}; allurls=[]
# pass 1: names from breadcrumbs (stable across reruns) for sibling navigation
NAMES={}; SIB={}
for rel in pages():
    parts=rel.split('/')
    if len(parts) in (2,3) and parts[-1]=='index.html':
        c=crumb(open(os.path.join(ROOT,rel),encoding='utf-8').read())
        if c: NAMES['/'.join(parts[:-1])]=c[-1]
        if len(parts)==3: SIB.setdefault(parts[0],[]).append(parts[1])
def a(href,t): return f'<a href="{href}">{html.escape(t)}</a>'
LABEL={"Dining":"Places to eat","Stay":"Places to stay","Sights":"Sights"}
for rel in pages():
    p=os.path.join(ROOT,rel); s=open(p,encoding='utf-8').read(); orig=s
    s=re.sub(r'(?<![\w.+-])@boken_japan\b','@bokenjapan',s)
    for x,y in ((M0,M1),(N0,N1),(D0,D1)): s=strip_block(s,x,y)
    noindex='name="robots" content="noindex' in s
    if not noindex: allurls.append(url(rel))
    parts=rel.split('/'); graph=None; title=None; h1=None; desc=None; nav=None
    mod=DATES.get(rel)
    if rel=='index.html': graph=[ORG,SITE]
    elif len(parts)==2 and parts[1]=='index.html':
        pf=parts[0]; pname=NAMES.get(pf,pf.title()); n=len(SIB.get(pf,[]))
        prefs[pf]={'slug':pf,'name':pname,'url':url(rel),'towns_file':BASE+f'data/towns/{pf}.json'}
        title=f'{pname} Prefecture travel guide: {n} towns with sights, food and stays · BokenJapan'
        desc=f'{pname} Prefecture, Japan: guides to {n} towns and villages, each listing sights, places to eat and places to stay with links to official sources.'
        page={'@type':'CollectionPage','@id':url(rel)+'#page','url':url(rel),'name':title.replace(' · BokenJapan',''),'isPartOf':{'@id':BASE+'#website'},
              'about':{'@type':'AdministrativeArea','name':f'{pname} Prefecture','url':url(rel),'containedInPlace':{'@type':'Country','name':'Japan'}},
              'breadcrumb':{'@type':'BreadcrumbList','itemListElement':[{'@type':'ListItem','position':1,'name':'Japan','item':BASE},{'@type':'ListItem','position':2,'name':pname,'item':url(rel)}]}}
        if mod: page['dateModified']=mod
        graph=[ORG,SITE,page]
    elif len(parts)==3 and parts[2]=='index.html':
        pref,town=parts[0],parts[1]; sec=sections(s)
        tname=NAMES.get(f'{pref}/{town}',town.title()); pname=NAMES.get(pref,pref.title())
        ns,nf,nst=len(sec.get('Sights',[])),len(sec.get('Dining',[])),len(sec.get('Stay',[]))
        bits=[f'{n} {w if n>1 else w1}' for n,w,w1 in ((ns,'sights','sight'),(nf,'places to eat','place to eat'),(nst,'stays','stay')) if n]
        title=f'{tname}, {pname}: things to do, where to eat and stay' + (f' ({", ".join(bits)})' if bits else '') + ' · BokenJapan'
        h1=f'{tname}, {pname}'
        desc=f'{tname} in {pname} Prefecture, Japan' + (': '+', '.join(bits) if bits else '') + ', with links to official and source pages.'
        g=GEO.get(f'{pref}/{town}')
        dest={'@type':['TouristDestination','City'],'@id':url(rel)+'#place','name':tname,'url':url(rel),
              'containedInPlace':{'@type':'AdministrativeArea','name':f'{pname} Prefecture','url':BASE+pref+'/'}}
        if g: dest['geo']={'@type':'GeoCoordinates','latitude':g['lat'],'longitude':g['lon']}
        srcs=[l['url'] for l in (sec.get('Official') or {}).get('links',[]) if l['url'].startswith('http')]
        for k in ('Stay','Dining','Sights'): srcs+=[i['source_url'] for i in sec.get(k,[]) if i.get('source_url')]
        srcs=list(dict.fromkeys(srcs))
        page={'@type':'WebPage','@id':url(rel)+'#page','url':url(rel),'name':title.replace(' · BokenJapan',''),'isPartOf':{'@id':BASE+'#website'},'about':{'@id':url(rel)+'#place'},
              'breadcrumb':{'@type':'BreadcrumbList','itemListElement':[{'@type':'ListItem','position':1,'name':'Japan','item':BASE},{'@type':'ListItem','position':2,'name':pname,'item':BASE+pref+'/'},{'@type':'ListItem','position':3,'name':tname,'item':url(rel)}]}}
        if srcs: page['isBasedOn']=srcs; page['citation']=srcs
        if mod: page['dateModified']=mod
        graph=[page,dest]
        for key,t in (('Dining','Restaurant'),('Stay','LodgingBusiness'),('Sights','TouristAttraction')):
            if sec.get(key):
                graph.append({'@type':'ItemList','name':f'{LABEL[key]} in {tname}','itemListElement':[{'@type':'ListItem','position':n+1,'item':place(t,i)} for n,i in enumerate(sec[key])]})
        sib=sorted(SIB.get(pref,[])); i=sib.index(town); others=[x for x in sib if x!=town]
        prev_,next_=sib[i-1],sib[(i+1)%len(sib)]
        nm=lambda x: NAMES.get(pref+'/'+x,x)
        nav=(f'{N0}<nav class="bj-more" aria-label="More in {html.escape(pname)}"><h2>More in {html.escape(pname)}</h2>'
             f'<p>{a("../"+prev_+"/","← "+nm(prev_))} · {a("../","All towns in "+pname)} · {a("../"+next_+"/",nm(next_)+" →")}</p>'
             '<p>Other towns: '+' · '.join(a("../"+x+"/",nm(x)) for x in others)+f'</p><p>{a("/","Back to all prefectures")}</p></nav>{N1}\n')
        rec={'name':tname,'slug':town,'prefecture':pref,'url':url(rel),'official':sec.get('Official'),
             'sights':sec.get('Sights',[]),'food':sec.get('Dining',[]),'stays':sec.get('Stay',[]),'date_modified':mod}
        if g: rec['geo']={'lat':g['lat'],'lon':g['lon']}
        towns.setdefault(pref,[]).append(rec)
    if not noindex and title:
        s=re.sub(r'(?s)<title>.*?</title>',f'<title>{html.escape(title,quote=False)}</title>',s,count=1)
    if not noindex and desc and 'name="description"' not in s:
        s=s.replace('</head>',f'{D0}<meta name="description" content="{html.escape(desc)}">{D1}\n</head>',1)
    if h1: s=re.sub(r'<h1 class="page-title">.*?</h1>',f'<h1 class="page-title">{html.escape(h1,quote=False)}</h1>',s,count=1)
    if nav: s=s.replace('</main>',nav+'</main>',1)
    if graph and not noindex:
        ld=json.dumps({'@context':'https://schema.org','@graph':graph},ensure_ascii=False).replace('</','<\\/')
        s=s.replace('</head>',f'{M0}<script type="application/ld+json">{ld}</script>{M1}\n</head>',1)
    if s!=orig: open(p,'w',encoding='utf-8').write(s)
os.makedirs(os.path.join(ROOT,'data/towns'),exist_ok=True)
W=lambda f,o: json.dump(o,open(os.path.join(ROOT,f),'w',encoding='utf-8'),ensure_ascii=False,indent=1)
today=datetime.date.today().isoformat()
for pf,ts in towns.items():
    prefs.setdefault(pf,{'slug':pf,'name':pf.title(),'url':BASE+pf+'/','towns_file':BASE+f'data/towns/{pf}.json'})
    prefs[pf]['town_count']=len(ts)
    W(f'data/towns/{pf}.json',{'prefecture':prefs[pf]['name'],'url':prefs[pf]['url'],'generated':today,'towns':ts})
PL=sorted(prefs.values(),key=lambda x:x['slug'])
W('data/prefectures.json',{'generated':today,'prefectures':PL})
W('data/index.json',{'name':'BokenJapan open data','generated':today,'license':'Facts as published on bokenjapan.com; each record links its source page.',
  'files':{'prefectures':BASE+'data/prefectures.json','towns':[p['towns_file'] for p in PL if 'town_count' in p]},
  'counts':{'prefectures':len(PL),'towns':sum(len(v) for v in towns.values())}})
open(os.path.join(ROOT,'data/README.md'),'w').write(f"""# BokenJapan open data
Static JSON, regenerated by `scripts/agent_friendly.py` from the published pages.
- `/data/index.json` – entry point and counts
- `/data/prefectures.json` – prefectures with page URL and towns file
- `/data/towns/<prefecture>.json` – towns with sights, food, stays and official links; every record has its page `url`, items have `source_url`
Served by GitHub Pages (CORS `Access-Control-Allow-Origin: *`). Free to read; please link back to the page URL.
""")
open(os.path.join(ROOT,'robots.txt'),'w').write('\n'.join(
  ['User-agent: *','Allow: /','Disallow: /go/','']+
  sum([[f'User-agent: {a}','Allow: /','Disallow: /go/',''] for a in ['GPTBot','ChatGPT-User','OAI-SearchBot','ClaudeBot','Claude-User','Claude-SearchBot','anthropic-ai','PerplexityBot','Perplexity-User','Google-Extended','Googlebot','Applebot','Applebot-Extended','xAI-Bot','GrokBot','Grok','CCBot','Bingbot']],[])+
  [f'Sitemap: {BASE}sitemap.xml',''])) 
extra=[BASE+'llms.txt',BASE+'llms-full.txt',BASE+'data/index.json']
open(os.path.join(ROOT,'sitemap.xml'),'w').write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+''.join(f'<url><loc>{html.escape(u)}</loc><lastmod>{today}</lastmod></url>\n' for u in sorted(set(allurls))+extra)+'</urlset>\n')
L=[ '# BokenJapan','',"> BokenJapan (bokenjapan.com) is an English travel guide to rural and small-town Japan: one page per prefecture and per municipality, listing sights, places to eat and places to stay, each with a link to its official or source page.",'',
 'Structure: `/` home → `/<prefecture>/` prefecture index (map + town list) → `/<prefecture>/<town>/` town page with sections Official, Stay, Dining, Sights. Pages are static; JSON-LD (schema.org) is embedded in each page head.','',
 '## Open data (JSON, CORS-enabled)',f'- [Data index]({BASE}data/index.json): entry point and counts',f'- [Prefectures]({BASE}data/prefectures.json): all prefectures with towns file URLs',f'- [Data README]({BASE}data/README.md): schema notes','',
 '## URL patterns','- `/<prefecture>/` prefecture hub; `/<prefecture>/<town>/` town page (sections Official, Stay, Dining, Sights; JSON-LD WebPage + TouristDestination with isBasedOn sources and dateModified).','- Reserved for future comparison guides (not yet published): `/best/<thing>-in-<place>/` (e.g. /best/onsen-ryokan-in-aomori/) and `/<prefecture>/<town>/getting-there/` access guides. Only real, sourced comparisons will be published there.','',
 '## Prefectures']+[f"- [{p['name']}]({p['url']}): {p.get('town_count',0)} towns · [JSON]({p['towns_file']})" for p in PL]+['','## Key pages',f'- [Home]({BASE})',f'- [Privacy]({BASE}privacy.html)',f'- [Terms]({BASE}terms.html)',f'- [Sitemap]({BASE}sitemap.xml)','','## Social']+[f'- {u}' for u in SAME]+['','## Optional',f'- [Full town list]({BASE}llms-full.txt)','']
open(os.path.join(ROOT,'llms.txt'),'w').write('\n'.join(L))
F=['# BokenJapan – full town list','','> Every town page with counts of sights, food and stays. See llms.txt for structure.','']
for p in PL:
    F+=[f"## {p['name']}",'']+[f"- [{t['name']}]({t['url']}): {len(t['sights'])} sights, {len(t['food'])} food, {len(t['stays'])} stays" for t in towns.get(p['slug'],[])]+['']
open(os.path.join(ROOT,'llms-full.txt'),'w').write('\n'.join(F))
print(f"pages={len(allurls)} prefectures={len(PL)} towns={sum(len(v) for v in towns.values())}")
