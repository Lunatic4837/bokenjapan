#!/usr/bin/env python3
"""Ikkyu collector — AUDIT-47 P4 (replaces the stub that always returned items: []).
Pref list pages in Ikkyu recommended order -> facility pages (bj_shared.ikkyu_pool), cached per prefecture in
FN_OUT/_ikkyu/<pref>.json, then filtered to the town by JSON-LD addressRegion/Locality.
Status is explicit: ok / cached / BLOCKED_403 / NO_AREA_CODE — never a silent empty list."""
from __future__ import annotations
import os, re, sys
from pathlib import Path
from common import curl, save_json, RAW, OUT
sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as S

def _fetch(url, enc='utf-8'):
    dest = RAW / '_ikkyu' / (re.sub(r'[^A-Za-z0-9]+', '_', url)[-80:] + '.html')
    code, html = curl(url, dest, timeout=30)
    return html if code == 200 else ''

def scrape_ikkyu(slug: str, name_ja: str, pref: str | None = None, pref_ja: str | None = None, area: str | None = None) -> dict:
    pref = pref or os.environ.get('BJ_PREF') or ''
    r = S.ikkyu_pool(_fetch, pref, OUT / '_ikkyu' / f'{pref}.json', area=area, log=print)
    items = []
    for p in r['items']:
        if pref_ja and p.get('region') and p['region'] != pref_ja: continue
        if not S.jalan_in_town({'address': {'addressLocality': p.get('loc'), 'streetAddress': p.get('street')}}, name_ja): continue
        items.append({'name_ja': p['name_ja'], 'name_en': p.get('name_en_official', ''), 'ikkyu_url': p['ikkyu_url'], 'rank': p['order'] + 1,
                      'image': (p.get('gallery') or [p.get('img')])[0] or p.get('img'), 'image_alt': '', 'addressLocality': p.get('loc'),
                      'description': p.get('desc', '')})
    out = {'count': len(items), 'status': r['status'], 'note': None if r['status'] in ('ok', 'cached') else 'Ikkyu unavailable — Jalan fallback',
           'http_codes': [], 'items': items}
    save_json(RAW / slug / 'ikkyu.json', out)
    return out
