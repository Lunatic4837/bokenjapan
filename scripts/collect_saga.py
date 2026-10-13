#!/usr/bin/env python3
"""Saga data collection wrapper. Imports the shared catalog-uplift scripts READ-ONLY (no edits);
redirects RAW/OUT/MEDIA to Saga-specific paths. Writes /workspace/p1/data/saga/out/<slug>/union.json
(same union.json schema as catalog-uplift/out/<pref>/<slug>/union.json). Photo priority: official site og:image,
then Tabelog (dining) / Jalan (stay). Polite: >=1.5s between requests."""
import sys, re, json, time, html as H
from pathlib import Path
S='/workspace/p1/data/catalog-uplift/scripts'; sys.path.insert(0,S)
import common
BASE=Path('/workspace/p1/data/saga'); common.RAW=BASE/'raw'; common.OUT=BASE/'out'
common.CUTOVER=Path('/workspace/p1/wt-saga'); common.MEDIA=common.CUTOVER/'media'
_sl=common.sleep_polite; common.sleep_polite=lambda s=0: time.sleep(max(1.5,s))
_curl=common.curl
def curl(*a,**k):
    r=_curl(*a,**k); time.sleep(1.5); return r
common.curl=curl
import fetch_photos, scrape_jalan, scrape_ikkyu
from union_catalogs import build_union
for m in (fetch_photos,scrape_jalan,scrape_ikkyu): m.curl=curl; m.RAW=common.RAW
fetch_photos.MEDIA=common.MEDIA; fetch_photos.CUTOVER=common.CUTOVER; fetch_photos.sleep_polite=common.sleep_polite
RAW,OUT,MEDIA=common.RAW,common.OUT,common.MEDIA
DINING_CAP,STAY_CAP=24,12
meta=json.load(open(BASE/'saga-hub-codes.json')); hubs=meta['hubs']
def tabelog(slug,c,muni):
    rd=RAW/slug; rd.mkdir(parents=True,exist_ok=True); items,seen,rep=[],set(),None
    for page in (1,2):
        url=f'https://tabelog.com/saga/{c}/rstLst/'+(f'{page}/' if page>1 else '')+'?SrtT=rt'
        code,h=curl(url,rd/f'tabelog-{c}-p{page}.html')
        if code!=200 or not h: break
        if rep is None:
            m=re.search(r'([\d,]+)\s*件',h); rep=int(m.group(1).replace(',','')) if m else None
        new=0
        for b in re.split(r'class="list-rst__rst-name-target',h)[1:]:
            m=re.search(r'href="(https://tabelog\.com/[a-z]+/A\d+/A\d+/(\d+)/)"[^>]*>([^<]+)</a>',b)
            if not m or m.group(2) in seen: continue
            seen.add(m.group(2)); new+=1
            ag=re.search(r'list-rst__area-genre[^>]*>([^<]*)<',b); ag=re.sub(r'\s+',' ',ag.group(1)).strip() if ag else ''
            area,_,genre=ag.partition(' / ')
            if muni not in area: continue
            items.append(dict(name_ja=H.unescape(m.group(3).strip()),name_en='',url=m.group(1),tabelog_url=m.group(1),rst_id=m.group(2),genre_ja=genre.strip(),area_ja=area.strip(),tabelog_rank=len(items)+1))
        if not new or (rep and len(seen)>=rep) or len(items)>=DINING_CAP: break
    return dict(count=len(items),reported_total=rep,items=items)
def official_first(slug,union):
    """Dining: try the official homepage listed on the Tabelog detail page first."""
    for d in union['dining']:
        rid=d.get('rst_id'); 
        if not rid: continue
        dp=RAW/slug/f'tabelog-detail-{rid}.html'
        code,h=curl(d['tabelog_url'],dp,timeout=20)
        if code!=200: continue
        meta=fetch_photos.extract_tabelog_detail_meta(h); d['official_url']=meta.get('homepage')
        if meta.get('homepage') and not re.search(r'tabelog|instagram|facebook|twitter|x\.com|hotpepper|gnavi|retty',meta['homepage']):
            f=f'saga-{slug}-dining-{rid}.jpg'
            ok,_=fetch_photos.fetch_official_og(meta['homepage'],MEDIA/f)
            if ok: d['photo']=f'../../media/{f}'; d['photo_credit']=f'official site · Source {meta["homepage"]}'; d['photo_source']='official'
    return union
slugs=sys.argv[1:] or sorted(hubs)
for slug in slugs:
    h=hubs[slug]; ms=f'saga-{slug}'
    tb=tabelog(ms,h['tabelog_c'],h['name_ja']); (RAW/slug).mkdir(parents=True,exist_ok=True)
    jl=scrape_jalan.scrape_jalan(ms,meta['pref_jalan'],h['jalan_cty'],h['address_filter'])
    jl['items']=[i for i in jl['items'] if h['address_filter'] in (i.get('addressLocality') or '')+(i.get('streetAddress') or '')]
    ik=scrape_ikkyu.scrape_ikkyu(ms,h['name_ja'])
    u=build_union(ms,h['name_en'],tb,{'items':[]},ik,jl,pref_en='Saga')
    g={i['rst_id']:i['genre_ja'] for i in tb['items']}
    for d in u['dining']: d['genre_ja']=g.get(d.get('rst_id'),'')
    u['dining']=u['dining'][:DINING_CAP]; u['stay']=u['stay'][:STAY_CAP]
    (RAW/slug).rmdir() if (RAW/slug).exists() and not any((RAW/slug).iterdir()) else None
    u=official_first(ms,u)
    u=fetch_photos.attach_dining_photos(ms,u,tb)
    u=fetch_photos.attach_stay_photos(ms,u,jl)
    for d in u['dining']:
        if d.get('photo') and not d.get('photo_source'): d['photo_source']='tabelog'
    for s in u['stay']:
        if s.get('photo'): s['photo_source']='jalan'
    u.update(jalan_http=jl.get('http_code'),ikkyu_codes=ik.get('http_codes'),ikkyu_status=ik.get('status'),tabelog_reported=tb['reported_total'],collected=time.strftime('%Y-%m-%d %H:%M JST'))
    common.save_json(OUT/slug/'union.json',u); common.clean_raw_slug(ms)
    print(slug,'tb',tb['count'],'/',tb['reported_total'],'jalan',len(jl['items']),jl.get('http_code'),'ikkyu',ik.get('http_codes'),
      'dphoto',sum(1 for x in u['dining'] if x.get('photo')),'/',len(u['dining']),'sphoto',sum(1 for x in u['stay'] if x.get('photo')),'/',len(u['stay']),flush=True)
