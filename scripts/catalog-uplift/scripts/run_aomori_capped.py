#!/usr/bin/env python3
"""Capped Aomori uplift wave: disk-safe, polite, Stay+Dining for staging branch."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_hubs, save_json, OUT, clean_raw_slug, disk_avail_gib
from scrape_tabelog import scrape_tabelog
from scrape_tripadvisor import scrape_tripadvisor
from scrape_jalan import scrape_jalan
from scrape_ikkyu import scrape_ikkyu
from union_catalogs import build_union
from fetch_photos import attach_dining_photos, attach_stay_photos
from render_hub import render_to_html

DINING_CAP = 24
STAY_CAP = 12
PAGE_MAX = 2

def run(slugs: list[str] | None = None) -> dict:
    meta = load_hubs('aomori')
    pref = meta['pref']
    pref_en = meta.get('pref_en') or 'Aomori'
    pref_jalan = meta.get('pref_jalan') or '020000'
    hubs = meta['hubs']
    if not slugs:
        slugs = sorted(hubs.keys())
    report = {'pref': pref, 'wave': [], 'hubs': {}, 'paused': False}
    for slug in slugs:
        avail = disk_avail_gib()
        print(f'=== disk_avail_GiB={avail:.2f} {slug} ===', flush=True)
        if avail < 8.0:
            print('PAUSE_DISK_UNDER_8GiB', flush=True)
            report['paused'] = True
            break
        h = hubs[slug]
        if h.get('skip'):
            continue
        tb = scrape_tabelog(slug, h['tabelog_c'], pref, page_max=PAGE_MAX, muni_ja=h.get('name_ja'))
        print('  tabelog', tb['count'], '/', tb.get('reported_total'), flush=True)
        ta = scrape_tripadvisor(slug, h.get('ta_geo') or '', h['name_en'], h['name_ja'], ta_place=h.get('ta_place'), page_max=2)
        if ta.get('items') and len(ta['items']) > 40:
            ta['items'] = ta['items'][:40]
            ta['count'] = len(ta['items'])
        print('  tripadvisor', ta['count'], flush=True)
        jl = scrape_jalan(slug, pref_jalan, h.get('jalan_cty') or '', h.get('address_filter') or '')
        print('  jalan', jl['count'], jl.get('http_code'), flush=True)
        ik = scrape_ikkyu(slug, h['name_ja'])
        print('  ikkyu', ik.get('status'), ik['count'], flush=True)
        union = build_union(slug, h['name_en'], tb, ta, ik, jl, pref_en=pref_en)
        union['dining'] = union['dining'][:DINING_CAP]
        union['stay'] = union['stay'][:STAY_CAP]
        union['dining_union'] = len(union['dining'])
        union['stay_union'] = len(union['stay'])
        print(f"  capped dining={union['dining_union']} stay={union['stay_union']}", flush=True)
        avail = disk_avail_gib()
        if avail < 8.0:
            print('PAUSE_DISK_BEFORE_PHOTOS', flush=True)
            report['paused'] = True
            save_json(OUT / slug / 'union.json', union)
            break
        union = attach_dining_photos(slug, union, tb)
        union = attach_stay_photos(slug, union, jl)
        dmiss = sum(1 for x in union['dining'] if not x.get('photo'))
        smiss = sum(1 for x in union['stay'] if not x.get('photo'))
        print(f"  photos dining_ok={union['dining_union']-dmiss}/{union['dining_union']} stay_ok={union['stay_union']-smiss}/{union['stay_union']}", flush=True)
        save_json(OUT / slug / 'union.json', union)
        paths = render_to_html(slug, pref, union)
        print('  rendered', [str(p) for p in paths], flush=True)
        clean_raw_slug(slug)
        report['wave'].append(slug)
        report['hubs'][slug] = {
            'dining_union': union['dining_union'], 'stay_union': union['stay_union'],
            'dining_photos': union['dining_union']-dmiss, 'stay_photos': union['stay_union']-smiss,
        }
        save_json(OUT / 'aomori-wave-partial.json', report)
    save_json(OUT / 'aomori-wave-report.json', report)
    return report

if __name__ == '__main__':
    args = sys.argv[1:]
    run(args or None)
