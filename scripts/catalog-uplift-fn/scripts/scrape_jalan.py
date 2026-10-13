#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from common import curl, save_json, RAW

def muni_match(loc: str, muni: str) -> bool:
    loc = re.sub(r'^(福島県|新潟県)', '', (loc or '').replace(' ', '').replace('\u3000', ''))
    loc = re.sub(r'^[^市町村]{1,6}郡', '', loc)
    return loc.startswith(muni)


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
            if address_filter:
                full = (addr.get('addressRegion') or '') + loc + (addr.get('streetAddress') or '')
                if not muni_match(loc or full, address_filter):
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
