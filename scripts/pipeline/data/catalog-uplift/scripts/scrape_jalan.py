#!/usr/bin/env python3
"""Jalan CTY collector — AUDIT-47 P4: ?idx= pagination (port of kyushu-uplift/jalan_area.py) and an enforced address
filter (an empty locality passes only when the street address matches). Image = facility og:image (exterior) at pict2L."""
from __future__ import annotations
import os, re, sys
from common import curl, save_json, RAW
sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as S

def muni_match(loc: str, muni: str) -> bool:
    loc = (loc or '').replace(' ', '').replace('\u3000', '')
    loc = re.sub(r'^.{2,3}[都道府県]', '', loc)
    loc = re.sub(r'^[^市町村]{1,6}郡', '', loc)
    return loc.startswith(muni)

def scrape_jalan(slug: str, pref_jalan: str, jalan_cty: str, address_filter: str, photos: bool = True) -> dict:
    rawdir = RAW / slug; rawdir.mkdir(parents=True, exist_ok=True)
    if not jalan_cty:
        out = {'count': 0, 'source': 'jalan', 'note': 'no jalan_cty', 'http_code': 0, 'items': []}
        save_json(rawdir / 'jalan.json', out); return out
    codes = []
    def fetch(url, enc='cp932'):
        dest = rawdir / ('jalan-' + re.sub(r'[^A-Za-z0-9]+', '_', url)[-60:] + '.html')
        code, _ = curl(url, dest, timeout=35); codes.append(code)
        return dest.read_bytes().decode('cp932', errors='replace') if dest.exists() and code == 200 else ''
    els = S.jalan_paginate(fetch, f'https://www.jalan.net/{pref_jalan}/{jalan_cty}/', log=print)
    items, seen = [], set()
    for el in els:
        if address_filter and not S.jalan_in_town(el, address_filter, match=muni_match): continue
        u = el.get('url') or el.get('name')
        if u in seen: continue
        seen.add(u); addr = el.get('address') or {}
        it = {'name_ja': el.get('name') or '', 'name_en': '', 'jalan_url': el.get('url') or '', 'image': S.jalan_big(el.get('image') or ''),
              'image_kind': 'plan', 'addressLocality': addr.get('addressLocality') or '', 'streetAddress': addr.get('streetAddress') or '',
              'description': el.get('description') or ''}
        if photos and it['jalan_url'] and os.environ.get('BJ_JALAN_FACILITY_PHOTO', '1') == '1':
            fu, alt = S.jalan_photo(fetch, it['jalan_url'])
            if fu: it.update(image=fu, image_alt=alt, image_kind='facility')
        items.append(it)
    out = {'count': len(items), 'source': 'jalan', 'note': None, 'http_code': codes[0] if codes else 0, 'pages': len(codes), 'found_on_cty': len(els), 'items': items}
    save_json(rawdir / 'jalan.json', out)
    return out
