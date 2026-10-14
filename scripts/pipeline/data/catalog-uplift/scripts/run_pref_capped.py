#!/usr/bin/env python3
"""Capped pref uplift (Aomori template) writing into a dedicated worktree (--root). Usage: run_pref_capped.py PREF ROOT [slugs...]"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
pref, root = sys.argv[1], Path(sys.argv[2])
import common, fetch_photos, render_hub
common.CUTOVER = root; common.MEDIA = root / 'media'
fetch_photos.CUTOVER = root; fetch_photos.MEDIA = root / 'media'
render_hub.CUTOVER = root
(root / 'media').mkdir(exist_ok=True)
from common import load_hubs, save_json, OUT, clean_raw_slug, disk_avail_gib
sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as BJS  # AUDIT-47 P1-P4: population-scaled targets, no hard caps
from scrape_tabelog import scrape_tabelog
from scrape_tripadvisor import scrape_tripadvisor
from scrape_jalan import scrape_jalan
from scrape_ikkyu import scrape_ikkyu
from union_catalogs import build_union
DINING_CAP, STAY_CAP, PAGE_MAX = 24, 12, 2
meta = load_hubs(pref); hubs = meta['hubs']
slugs = sys.argv[3:] or sorted(hubs)
report = {'pref': pref, 'hubs': {}, 'paused': False}
for slug in slugs:
    avail = disk_avail_gib()
    print(f'=== disk_avail_GiB={avail:.2f} {slug} ===', flush=True)
    if avail < 8.0:
        print('PAUSE_DISK_UNDER_8GiB', flush=True); report['paused'] = True; break
    h = hubs[slug]
    TD, TS, POP = BJS.targets(pref, slug, h)  # P1
    tb = scrape_tabelog(slug, h['tabelog_c'], pref, muni_ja=h['name_ja'], target=TD)
    ta = scrape_tripadvisor(slug, h.get('ta_geo') or '', h['name_en'], h['name_ja'], ta_place=h.get('ta_place'), page_max=max(1, -(-TD // 30) + 1))
    jl = scrape_jalan(slug, meta['pref_jalan'], h['jalan_cty'], h['address_filter'])
    ik = scrape_ikkyu(slug, h['name_ja'], pref=pref)
    print('  tabelog', tb['count'], 'ta', ta['count'], 'jalan', jl['count'], jl.get('http_code'), 'ikkyu', ik.get('status'), ik.get('http_codes'), flush=True)
    union = build_union(slug, h['name_en'], tb, ta, ik, jl, pref_en=meta['pref_en'])
    union['dining'] = union['dining'][:BJS.dining_keep(TD)]; union['stay'] = union['stay'][:BJS.stay_keep(TS)]
    union = fetch_photos.attach_dining_photos(slug, union, tb)
    union = fetch_photos.attach_stay_photos(slug, union, jl)
    union['dining_union'] = len(union['dining']); union['stay_union'] = len(union['stay'])
    save_json(OUT / pref / slug / 'union.json', union)
    render_hub.render_to_html(slug, pref, union, roots=[root])
    clean_raw_slug(slug)
    report['hubs'][slug] = {'dining': union['dining_union'], 'stay': union['stay_union'],
        'dining_photos': sum(1 for x in union['dining'] if x.get('photo')), 'stay_photos': sum(1 for x in union['stay'] if x.get('photo')),
        'ikkyu': ik.get('status'), 'ikkyu_codes': ik.get('http_codes')}
    print('  ', report['hubs'][slug], flush=True)
    save_json(OUT / f'{pref}-wave-report.json', report)
