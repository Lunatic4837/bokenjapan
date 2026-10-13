import json,subprocess,re,sys,time,urllib.parse
pref=sys.argv[1]; root=sys.argv[2]
PID={'fukushima':'7','niigata':'15'}[pref]; PEN=pref.title(); PJ={'fukushima':'070000','niigata':'150000'}[pref]
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
L=json.load(open('/workspace/p1/data/catalog-uplift/hubs/_localgovjp.json'))
ms=[x for x in L if x['pid']==PID and ' ' not in x['city']]
cty=json.load(open('raw/jalan-cty.json'))[PJ]
def ctyfor(ja):
    for k,v in cty.items():
        if re.sub(r'^.+?郡','',k)==ja: return v
    return ''
import os
slugs=sorted(os.listdir(f'{root}/{pref}')); slugs=[s for s in slugs if os.path.isdir(f'{root}/{pref}/{s}')]
hubs={}; audit=[]
for x in ms:
    jis=x['lgcode'][:5]
    if pref=='fukushima': slug='jis'+jis
    else:
        host=urllib.parse.urlparse(x['url']).hostname; tok=host.split('.')[1]
        slug=tok
    p=f'{root}/{pref}/{slug}/index.html'
    exists=os.path.exists(p)
    h=open(p,encoding='utf-8').read() if exists else ''
    m=re.search(r'<h1 class="page-title">([^<]+)</h1>',h); en=m.group(1).strip() if m else ''
    off=re.search(r'<h2>Official</h2><p><a href="([^"]+)"',h)
    addr=re.search(r'<dt>Address</dt><dd>([^<]*)</dd>',h)
    cover=re.search(r'<figure class="cover"><img src="([^"]+)"',h)
    title=re.search(r'<title>([^<]*)</title>',h)
    # TA geo
    q=urllib.parse.quote(f'{en} {PEN}')
    r=subprocess.run(['curl','-s','-A',UA,f'https://www.tripadvisor.com/TypeAheadJson?action=API&types=geo&query={q}&max=3'],capture_output=True,text=True).stdout
    geo='';place=''
    try:
        for res in json.loads(r).get('results',[]):
            nm=res.get('name','')
            if nm.lower().startswith(en.lower()+',') and f'{PEN} Prefecture' in nm:
                geo=str(res['value']); u=res['urls'][0]['url']; mm=re.search(r'-g\d+-(.+?)-Vacations',u); place=mm.group(1) if mm else ''; break
    except Exception: pass
    time.sleep(0.6)
    hubs[slug]={'name_ja':x['city'],'name_en':en,'jis':jis,'tabelog_c':'C'+jis,'ta_geo':geo,'ta_place':place,'jalan_cty':ctyfor(x['city']),'address_filter':x['city'],'official_list_url':x['url'],'skip':False}
    audit.append({'slug':slug,'jis':jis,'name_ja':x['city'],'name_en':en,'page_exists':exists,'title':title.group(1) if title else '','official_on_page':off.group(1) if off else '','official_list':x['url'],'address':addr.group(1) if addr else '','cover':cover.group(1) if cover else '','ta_geo':geo,'jalan_cty':hubs[slug]['jalan_cty']})
    print(slug,x['city'],en,exists,geo,hubs[slug]['jalan_cty'],off.group(1) if off else None,flush=True)
extra=set(slugs)-set(hubs)
json.dump({'pref':pref,'pref_en':PEN,'pref_jalan':PJ,'hubs':hubs},open(f'hubs/{pref}-hub-codes.json','w'),ensure_ascii=False,indent=1)
json.dump({'n_official':len(ms),'n_pages':len(slugs),'extra_pages':sorted(extra),'rows':audit},open(f'audit/{pref}-audit.json','w'),ensure_ascii=False,indent=1)
print('official',len(ms),'pages',len(slugs),'extra',extra)
