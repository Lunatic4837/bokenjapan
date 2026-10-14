#!/usr/bin/env python3
"""Scrape-only pass (Ohira v2): Tabelog rating-ordered, in-muni filtered by list area text; Jalan strict address filter;
Ikkyu probe; TA if geo. Photos downloaded into ROOT/media. Writes out/<pref>/<slug>/union.json. Rendering is finalize_pref.py.
Usage: run_pref_v2.py PREF ROOT [slugs...]"""
from __future__ import annotations
import sys, re, html as H
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
pref, root = sys.argv[1], Path(sys.argv[2])
import common, fetch_photos
common.CUTOVER = root; common.MEDIA = root / 'media'
fetch_photos.CUTOVER = root; fetch_photos.MEDIA = root / 'media'
(root / 'media').mkdir(exist_ok=True)
from common import load_hubs, save_json, OUT, RAW, curl, sleep_polite, clean_raw_slug, disk_avail_gib
sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as BJS  # AUDIT-47 P1-P4: population-scaled targets, no hard caps
from scrape_tripadvisor import scrape_tripadvisor
from scrape_jalan import scrape_jalan
from scrape_ikkyu import scrape_ikkyu
from scrape_tabelog import scrape_tabelog  # P2: shared paginated collector (replaces the inline 2-page tabelog())
from union_catalogs import build_union
DINING_CAP, STAY_CAP = 24, 12

def tabelog(slug, c, muni_ja):
    rawdir = RAW / slug; rawdir.mkdir(parents=True, exist_ok=True)
    items, seen, reported = [], set(), None
    for page in (1, 2):
        url = f'https://tabelog.com/{pref}/{c}/rstLst/' + (f'{page}/' if page > 1 else '') + '?SrtT=rt'
        dest = rawdir / f'tabelog-{c}-p{page}.html'
        code, html = curl(url, dest, timeout=30)
        if code != 200 or not html: break
        if reported is None:
            m = re.search(r'([\d,]+)\s*件', html); reported = int(m.group(1).replace(',', '')) if m else None
        blocks = re.split(r'class="list-rst__rst-name-target', html)[1:]
        new = 0
        for b in blocks:
            m = re.search(r'href="(https://tabelog\.com/[a-z]+/A\d+/A\d+/(\d+)/)"[^>]*>([^<]+)</a>', b)
            if not m: continue
            url_, rid, name = m.group(1), m.group(2), H.unescape(m.group(3).strip())
            if rid in seen: continue
            seen.add(rid); new += 1
            ag = re.search(r'list-rst__area-genre[^>]*>([^<]*)<', b)
            ag = re.sub(r'\s+', ' ', ag.group(1)).strip() if ag else ''
            area, _, genre = ag.partition(' / ')
            if muni_ja not in area:   # strict: no out-of-town padding
                continue
            items.append({'name_ja': name, 'name_en': '', 'url': url_, 'tabelog_url': url_, 'rst_id': rid,
                          'genre_ja': genre.strip(), 'area_ja': area.strip(), 'tabelog_rank': len(items) + 1})
        sleep_polite(0.6)
        if not new or (reported and len(seen) >= reported): break
    return {'count': len(items), 'reported_total': reported, 'items': items}

meta = load_hubs(pref); hubs = meta['hubs']
slugs = sys.argv[3:] or sorted(hubs)
for slug in slugs:
    if disk_avail_gib() < 8.0:
        print('PAUSE_DISK_UNDER_8GiB', flush=True); break
    h = hubs[slug]
    TD, TS, POP = BJS.targets(pref, slug, h)  # P1
    tb = scrape_tabelog(slug, h['tabelog_c'], pref, muni_ja=h['name_ja'], target=TD)
    ta = scrape_tripadvisor(slug, h.get('ta_geo') or '', h['name_en'], h['name_ja'], page_max=max(1, -(-TD // 30) + 1))
    jl = scrape_jalan(slug, meta['pref_jalan'], h['jalan_cty'], h['address_filter'])
    jl['items'] = [i for i in jl['items'] if h['address_filter'] in (i.get('addressLocality') or '')]
    ik = scrape_ikkyu(slug, h['name_ja'], pref=pref)
    union = build_union(slug, h['name_en'], tb, ta, ik, jl, pref_en=meta['pref_en'])
    g = {it['rst_id']: it['genre_ja'] for it in tb['items']}
    for d in union['dining']:
        d['genre_ja'] = g.get(d.get('rst_id'), '')
    union['dining'] = union['dining'][:BJS.dining_keep(TD)]; union['stay'] = union['stay'][:BJS.stay_keep(TS)]
    union = fetch_photos.attach_dining_photos(slug, union, tb)
    union = fetch_photos.attach_stay_photos(slug, union, jl)
    union['jalan_http'] = jl.get('http_code'); union['ikkyu_codes'] = ik.get('http_codes'); union['tabelog_reported'] = tb['reported_total']
    save_json(OUT / pref / slug / 'union.json', union)
    clean_raw_slug(slug)
    print(slug, 'tb', tb['count'], '/', tb['reported_total'], 'ta', ta['count'], 'jalan', len(jl['items']), jl.get('http_code'), 'ikkyu', ik.get('http_codes'),
          'dphoto', sum(1 for x in union['dining'] if x.get('photo')), '/', len(union['dining']),
          'sphoto', sum(1 for x in union['stay'] if x.get('photo')), '/', len(union['stay']), flush=True)
