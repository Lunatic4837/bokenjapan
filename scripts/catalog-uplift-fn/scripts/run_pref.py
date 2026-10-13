#!/usr/bin/env python3
"""Fukushima/Niigata uplift: Tabelog∪TA dining, Ikkyu∪Jalan stay (Ikkyu first)."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import load_hubs, save_json, OUT, RAW, clean_raw_slug, disk_avail_gib
from scrape_tabelog import scrape_tabelog
from scrape_tripadvisor import scrape_tripadvisor
from scrape_jalan import scrape_jalan, muni_match
from union_catalogs import build_union
from fetch_photos import attach_dining_photos, attach_stay_photos
from render_hub import render_to_html
DINING_CAP, STAY_CAP = 24, 12

def ikkyu_for(pref, name_ja):
    c = json.loads((RAW / f'ikkyu-{pref}.json').read_text())
    items = []
    for hid in c['ids']:
        h = c['hotels'].get(hid) or {}
        if h.get('http') == 200 and h.get('name_ja') and muni_match(h.get('locality', ''), name_ja):
            h = dict(h); import html as _h; h['name_ja'] = _h.unescape(h['name_ja']); items.append(h)
    return {'count': len(items), 'status': 'ok', 'items': items}

def run(pref, slugs=None):
    meta = load_hubs(pref); hubs = meta['hubs']
    slugs = slugs or sorted(hubs)
    rep_p = OUT / f'{pref}-wave-report.json'
    report = json.loads(rep_p.read_text()) if rep_p.exists() else {'pref': pref, 'hubs': {}}
    for slug in slugs:
        if disk_avail_gib() < 8.0:
            print('PAUSE_DISK_UNDER_8GiB', flush=True); report['paused'] = True; break
        h = hubs[slug]
        print('===', slug, h['name_en'], flush=True)
        tb = scrape_tabelog(slug, h['tabelog_c'], pref, page_max=2, muni_ja=h['name_ja'])
        ta = scrape_tripadvisor(slug, h.get('ta_geo') or '', h['name_en'], h['name_ja'], ta_place=h.get('ta_place'), page_max=2)
        ta['items'] = (ta.get('items') or [])[:40]; ta['count'] = len(ta['items'])
        jl = scrape_jalan(slug, meta['pref_jalan'], h.get('jalan_cty') or '', h['address_filter'])
        ik = ikkyu_for(pref, h['name_ja'])
        u = build_union(slug, h['name_en'], tb, ta, ik, jl, pref_en=meta['pref_en'])
        u['dining'] = u['dining'][:DINING_CAP]; u['stay'] = u['stay'][:STAY_CAP]
        u['dining_union'] = len(u['dining']); u['stay_union'] = len(u['stay'])
        u = attach_dining_photos(slug, u, tb); u = attach_stay_photos(slug, u, jl)
        save_json(OUT / slug / 'union.json', u)
        render_to_html(slug, pref, u)
        clean_raw_slug(slug)
        report['hubs'][slug] = {'tabelog': tb['count'], 'ta': ta['count'], 'ikkyu': ik['count'], 'jalan': jl['count'],
            'dining': u['dining_union'], 'stay': u['stay_union'],
            'dining_photos': sum(1 for x in u['dining'] if x.get('photo')), 'stay_photos': sum(1 for x in u['stay'] if x.get('photo'))}
        print(' ', report['hubs'][slug], flush=True)
        save_json(rep_p, report)
    return report

if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2:] or None)
