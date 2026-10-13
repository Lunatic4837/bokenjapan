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
for rel in pages():
    p=os.path.join(ROOT,rel); s=open(p,encoding='utf-8').read(); orig=s
    s=re.sub(r'(?<![\w.+-])@boken_japan\b','@bokenjapan',s)
    noindex='name="robots" content="noindex' in s
    if not noindex: allurls.append(url(rel))
    parts=rel.split('/'); title=txt((re.search(r'(?s)<title>(.*?)</title>',s) or [0,''])[1]).replace(' · BokenJapan','')
    graph=None
    if rel=='index.html': graph=[ORG,SITE]
    elif len(parts)==2 and parts[1]=='index.html':
        prefs[parts[0]]={'slug':parts[0],'name':title,'url':url(rel),'towns_file':BASE+f'data/towns/{parts[0]}.json'}
        graph=[ORG,SITE,{'@type':'AdministrativeArea','name':title,'url':url(rel),'containedInPlace':{'@type':'Country','name':'Japan'}}]
    elif len(parts)==3 and parts[2]=='index.html':
        pref,town=parts[0],parts[1]; sec=sections(s)
        tname=title.split(' · ')[0]; pname=title.split(' · ')[1] if ' · ' in title else pref.title()
        g=GEO.get(f'{pref}/{town}')
        dest={'@type':['TouristDestination','City'],'@id':url(rel)+'#place','name':tname,'url':url(rel),
              'containedInPlace':{'@type':'AdministrativeArea','name':pname,'url':BASE+pref+'/'}}
        if g: dest['geo']={'@type':'GeoCoordinates','latitude':g['lat'],'longitude':g['lon']}
        graph=[dest]
        for key,t in (('Dining','Restaurant'),('Stay','LodgingBusiness'),('Sights','TouristAttraction')):
            if sec.get(key):
                graph.append({'@type':'ItemList','name':f'{key} in {tname}','itemListElement':[{'@type':'ListItem','position':n+1,'item':place(t,i)} for n,i in enumerate(sec[key])]})
        rec={'name':tname,'slug':town,'prefecture':pref,'url':url(rel),'official':sec.get('Official'),
             'sights':sec.get('Sights',[]),'food':sec.get('Dining',[]),'stays':sec.get('Stay',[])}
        if g: rec['geo']={'lat':g['lat'],'lon':g['lon']}
        towns.setdefault(pref,[]).append(rec)
    s=re.sub(r'\n?'+re.escape(M0)+r'.*?'+re.escape(M1),'',s,flags=re.S)
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
 '## Prefectures']+[f"- [{p['name']}]({p['url']}): {p.get('town_count',0)} towns · [JSON]({p['towns_file']})" for p in PL]+['','## Key pages',f'- [Home]({BASE})',f'- [Privacy]({BASE}privacy.html)',f'- [Terms]({BASE}terms.html)',f'- [Sitemap]({BASE}sitemap.xml)','','## Social']+[f'- {u}' for u in SAME]+['','## Optional',f'- [Full town list]({BASE}llms-full.txt)','']
open(os.path.join(ROOT,'llms.txt'),'w').write('\n'.join(L))
F=['# BokenJapan – full town list','','> Every town page with counts of sights, food and stays. See llms.txt for structure.','']
for p in PL:
    F+=[f"## {p['name']}",'']+[f"- [{t['name']}]({t['url']}): {len(t['sights'])} sights, {len(t['food'])} food, {len(t['stays'])} stays" for t in towns.get(p['slug'],[])]+['']
open(os.path.join(ROOT,'llms-full.txt'),'w').write('\n'.join(F))
print(f"pages={len(allurls)} prefectures={len(PL)} towns={sum(len(v) for v in towns.values())}")
