#!/usr/bin/env python3
"""Run catalog uplift wave for selected hubs (Ohira template). Supports --pref."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_hubs, save_json, OUT, disk_avail_gib
from scrape_tabelog import scrape_tabelog
from scrape_tripadvisor import scrape_tripadvisor
from scrape_jalan import scrape_jalan
from scrape_ikkyu import scrape_ikkyu
from union_catalogs import build_union
from fetch_photos import attach_dining_photos, attach_stay_photos
from render_hub import render_to_html

def run(slugs: list[str], pref: str | None = None) -> dict:
    meta = load_hubs(pref)
    pref = meta['pref']
    pref_en = meta.get('pref_en') or pref.title()
    report = {'wave': [], 'pref': pref, 'hubs': {}}
    for slug in slugs:
        avail = disk_avail_gib()
        print(f'=== disk_avail_GiB={avail:.1f} ===', flush=True)
        if avail < 8.0:
            print('PAUSE_DISK_UNDER_8GiB', flush=True)
            report['paused'] = True
            break
        h = meta['hubs'][slug]
        if h.get('skip'):
            continue
        print('===', slug, h.get('name_en'), '===', flush=True)
        tb = scrape_tabelog(slug, h['tabelog_c'], pref, muni_ja=h.get('name_ja') or h.get('address_filter'))
        print('  tabelog', tb['count'], '/', tb.get('reported_total'), flush=True)
        ta = scrape_tripadvisor(slug, h['ta_geo'], h['name_en'], h['name_ja'], ta_place=h.get('ta_place'))
        print('  tripadvisor', ta['count'], flush=True)
        jl = scrape_jalan(slug, meta['pref_jalan'], h['jalan_cty'], h['address_filter'])
        print('  jalan', jl['count'], jl.get('http_code'), flush=True)
        ik = scrape_ikkyu(slug, h['name_ja'])
        print('  ikkyu', ik.get('status'), ik['count'], flush=True)
        union = build_union(slug, h['name_en'], tb, ta, ik, jl, pref_en=pref_en)
        print(f"  dining_union {union['dining_union']} stay_union {union['stay_union']}", flush=True)
        print('  photos...', flush=True)
        union = attach_dining_photos(slug, union, tb)
        union = attach_stay_photos(slug, union, jl)
        dmiss = sum(1 for x in union['dining'] if not x.get('photo'))
        smiss = sum(1 for x in union['stay'] if not x.get('photo'))
        print(f"  photos dining_ok={union['dining_union']-dmiss}/{union['dining_union']} stay_ok={union['stay_union']-smiss}/{union['stay_union']}", flush=True)
        save_json(OUT / slug / 'union.json', union)
        paths = render_to_html(slug, pref, union)
        print('  rendered', [str(p) for p in paths], flush=True)
        report['wave'].append(slug)
        report['hubs'][slug] = {
            'tabelog': union['tabelog_count'], 'ta': union['tripadvisor_count'],
            'dining_union': union['dining_union'], 'stay_union': union['stay_union'],
            'dining_photos': sum(1 for x in union['dining'] if x.get('photo')),
            'stay_photos': sum(1 for x in union['stay'] if x.get('photo')),
            'ikkyu_status': union.get('ikkyu_status'),
        }
    save_json(OUT / 'wave-partial-report.json', report)
    return report

if __name__ == '__main__':
    args = sys.argv[1:]
    pref = None
    if args and args[0] == '--pref':
        pref = args[1]
        args = args[2:]
    run(args, pref=pref)
