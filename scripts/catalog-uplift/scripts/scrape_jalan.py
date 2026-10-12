#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from common import curl, save_json, RAW

def scrape_jalan(slug: str, pref_jalan: str, jalan_cty: str, address_filter: str) -> dict:
    rawdir = RAW / slug
    rawdir.mkdir(parents=True, exist_ok=True)
    if not jalan_cty:
        out = {'count': 0, 'source': 'jalan', 'note': 'no jalan_cty', 'http_code': 0, 'items': []}
        save_json(rawdir / 'jalan.json', out)
        return out
    url = f'https://www.jalan.net/{pref_jalan}/{jalan_cty}/'
    dest = rawdir / 'jalan-cty.html'
    # Jalan often needs cp932
    code, _ = curl(url, dest, timeout=35)
    html = ''
    if dest.exists():
        html = dest.read_bytes().decode('cp932', errors='replace')
    items = []
    for m in re.finditer(r'<script type="application/ld\+json">\s*(\[.*?\])\s*</script>', html, re.S):
        try:
            data = json.loads(m.group(1))
        except Exception:
            continue
        for el in data:
            if not isinstance(el, dict) or el.get('@type') != 'Hotel':
                continue
            addr = el.get('address') or {}
            loc = addr.get('addressLocality') or ''
            if address_filter and address_filter not in loc and address_filter not in (addr.get('streetAddress') or ''):
                # also accept if locality empty
                if loc and address_filter not in loc:
                    continue
            items.append({
                'name_ja': el.get('name') or '',
                'name_en': '',
                'jalan_url': el.get('url') or '',
                'image': el.get('image') or '',
                'addressLocality': loc,
            })
    # dedupe by url
    seen, out_items = set(), []
    for it in items:
        u = it.get('jalan_url') or it.get('name_ja')
        if u in seen:
            continue
        seen.add(u)
        out_items.append(it)
    out = {'count': len(out_items), 'source': 'jalan', 'note': None, 'http_code': code, 'items': out_items}
    save_json(rawdir / 'jalan.json', out)
    return out
