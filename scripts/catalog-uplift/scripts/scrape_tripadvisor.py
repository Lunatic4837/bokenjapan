#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from common import curl, save_json, sleep_polite, RAW

def scrape_tripadvisor(slug: str, ta_geo: str, name_en: str, name_ja: str, ta_place: str | None = None, page_max: int = 8) -> dict:
    rawdir = RAW / slug
    rawdir.mkdir(parents=True, exist_ok=True)
    if not ta_geo:
        out = {'count': 0, 'source': 'tripadvisor', 'ta_geo': ta_geo or '', 'items': [], 'note': 'no ta_geo'}
        save_json(rawdir / 'tripadvisor.json', out)
        return out
    items = []
    # TA restaurant list offset pages
    for i, oa in enumerate(range(0, page_max * 30, 30)):
        if oa == 0:
            url = f'https://www.tripadvisor.com/Restaurants-g{ta_geo}'
        else:
            url = f'https://www.tripadvisor.com/Restaurants-g{ta_geo}-oa{oa}'
        dest = rawdir / f'ta-rest-oa{oa}.html'
        code, html = curl(url, dest, timeout=35)
        if code != 200 or not html:
            break
        batch = []
        for m in re.finditer(
            r'href="(/Restaurant_Review-g' + re.escape(str(ta_geo)) + r'-d(\d+)-Reviews-([^"]+)\.html)"',
            html):
            path, did, slugish = m.group(1), m.group(2), m.group(3)
            name = slugish.replace('_', ' ').replace('-', ' ')
            name = re.sub(r'\s+', ' ', name).strip()
            batch.append({
                'name_en': name, 'name_ja': '', 'ta_id': did,
                'ta_url': 'https://www.tripadvisor.com' + path.split('?')[0],
                'ta_rank': 0,
            })
        # dedupe
        have = {x['ta_id'] for x in items}
        new = [b for b in batch if b['ta_id'] not in have]
        if not new:
            break
        for b in new:
            b['ta_rank'] = len(items) + 1
            items.append(b)
        sleep_polite(0.35)
    MAX_TA_ITEMS = 120
    items = items[:MAX_TA_ITEMS]
    out = {'count': len(items), 'source': 'tripadvisor', 'ta_geo': ta_geo, 'items': items}
    save_json(rawdir / 'tripadvisor.json', out)
    return out
