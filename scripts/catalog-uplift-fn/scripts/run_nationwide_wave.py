#!/usr/bin/env python3
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import save_json, OUT, clean_raw_slug, disk_avail_gib
from scrape_tabelog import scrape_tabelog
from scrape_tripadvisor import scrape_tripadvisor
from scrape_jalan import scrape_jalan
from scrape_ikkyu import scrape_ikkyu
from union_catalogs import build_union
from render_hub import render_to_html
from fetch_photos import attach_dining_photos, attach_stay_photos

HUBS_PATH = Path(__file__).resolve().parents[1] / 'hubs' / 'nationwide-waveB-hub-codes.json'

def run_one(slug: str, h: dict) -> dict:
    pref = h['pref']
    pref_en = h.get('pref_en') or pref.title()
    print('===', f'{pref}/{slug}', h['name_en'], '===', flush=True)
    tb = scrape_tabelog(slug, h['tabelog_c'], pref, page_max=3)
    print('  tabelog', tb['count'], '/', tb.get('reported_total'), flush=True)
    ta = scrape_tripadvisor(slug, h['ta_geo'], h['name_en'], h['name_ja'], h.get('ta_place'), page_max=2)
    if ta.get('items') and len(ta['items']) > 40:
        ta['items'] = ta['items'][:40]
        ta['count'] = len(ta['items'])
    print('  tripadvisor', ta['count'], flush=True)
    jl = scrape_jalan(slug, h['pref_jalan'], h['jalan_cty'], h['address_filter'])
    print('  jalan', jl['count'], jl.get('http_code'), flush=True)
    ik = scrape_ikkyu(slug, h['name_ja'])
    print('  ikkyu', ik['status'], ik['count'], flush=True)
    union = build_union(slug, h['name_en'], tb, ta, ik, jl, pref_en=pref_en)
    print('  dining_union', union['dining_union'], 'stay_union', union['stay_union'], flush=True)
    avail = disk_avail_gib()
    print(f'  disk_avail_GiB={avail:.2f}', flush=True)
    if avail < 8.0:
        raise SystemExit(f'PAUSE disk f_bavail={avail:.2f} GiB < 8')
    print('  photos...', flush=True)
    union = attach_dining_photos(slug, union, tb)
    union = attach_stay_photos(slug, union, jl)
    dmiss = sum(1 for x in union['dining'] if not x.get('photo'))
    smiss = sum(1 for x in union['stay'] if not x.get('photo'))
    print(f"  photos dining_ok={union['dining_union']-dmiss}/{union['dining_union']} stay_ok={union['stay_union']-smiss}/{union['stay_union']}", flush=True)
    save_json(OUT / slug / 'union.json', union)
    paths = render_to_html(slug, pref, union)
    print('  rendered', [str(p) for p in paths], flush=True)
    clean_raw_slug(slug)
    return {
        'pref': pref, 'path': f'{pref}/{slug}',
        'tabelog': union['tabelog_count'], 'ta': union['tripadvisor_count'],
        'dining_union': union['dining_union'], 'jalan': union['jalan_count'],
        'ikkyu': union['ikkyu_count'], 'stay_union': union['stay_union'],
        'dining_photos': union['dining_union']-dmiss, 'stay_photos': union['stay_union']-smiss,
        'ikkyu_status': union.get('ikkyu_status'),
    }

def main(slugs):
    meta = json.loads(HUBS_PATH.read_text(encoding='utf-8'))
    hubs = meta['hubs']
    for slug in slugs:
        h = hubs.get(slug)
        if not h:
            print('SKIP unknown', slug); continue
        try:
            r = run_one(slug, h)
            print(slug, r, flush=True)
        except Exception as e:
            print('ERROR', slug, e, flush=True)

if __name__ == '__main__':
    main(sys.argv[1:])
