#!/usr/bin/env python3
from __future__ import annotations
import json, re
from pathlib import Path
from common import curl, save_json, sleep_polite, RAW

def parse_list_page(html: str) -> list[dict]:
    items = []
    # primary: rst name links
    for m in re.finditer(
        r'href="(https://tabelog\.com/[a-z]+/A\d+/A\d+/(\d+)/)"[^>]*>([^<]+)</a>',
        html):
        url, rid, name = m.group(1), m.group(2), m.group(3).strip()
        if not name or len(name) > 80:
            continue
        seg = html[m.end():m.end() + 1500]
        a = re.search(r'list-rst__area-genre[^>]*>\s*([^<]*)', seg)
        area = a.group(1).strip() if a else ''
        items.append({'name_ja': name, 'name_en': '', 'url': url, 'rst_id': rid,
                      'tabelog_url': url, 'tabelog_rank': len(items) + 1,
                      'area': area, 'genre': area.split('/', 1)[1].strip() if '/' in area else ''})
    # dedupe by rst_id preserving order
    seen, out = set(), []
    for it in items:
        if it['rst_id'] in seen:
            continue
        seen.add(it['rst_id'])
        out.append(it)
        it['tabelog_rank'] = len(out)
    return out

def filter_by_muni(items: list[dict], muni_ja: str | None, html: str = '') -> list[dict]:
    # CoS fix (2026-10-13): when a town has few restaurants Tabelog pads the list with
    # "nearby/recommended" shops from other cities. Keep only rows whose area line names
    # this municipality; never keep out-of-town padding (ranks would be invented).
    if not muni_ja:
        return items
    kept = [it for it in items if not it.get('area') or muni_ja in it['area']]
    for i, it in enumerate(kept, 1):
        it['tabelog_rank'] = i
    return kept

def _scrape_one_c(slug: str, c: str, pref: str, page_max: int = 3, muni_ja: str | None = None):
    items, paths = [], []
    reported = None
    rawdir = RAW / slug
    rawdir.mkdir(parents=True, exist_ok=True)
    for page in range(1, page_max + 1):
        if page == 1:
            url = f'https://tabelog.com/{pref}/{c}/rstLst/'
        else:
            url = f'https://tabelog.com/{pref}/{c}/rstLst/{page}/'
        dest = rawdir / f'tabelog-{c}-p{page}.html'
        code, html = curl(url, dest, timeout=30)
        paths.append(str(dest))
        if code != 200 or not html:
            break
        if reported is None:
            m = re.search(r'([\d,]+)\s*件', html)
            if m:
                reported = int(m.group(1).replace(',', ''))
        batch = filter_by_muni(parse_list_page(html), muni_ja, html)
        if not batch:
            break
        # skip duplicates across pages
        have = {x['rst_id'] for x in items}
        new = [b for b in batch if b['rst_id'] not in have]
        if not new:
            break
        for b in new:
            b['tabelog_rank'] = len(items) + 1
            items.append(b)
        sleep_polite(0.3)
        if reported and len(items) >= reported:
            break
    return items, reported, f'tabelog:{c}', paths

def scrape_tabelog(slug: str, tabelog_c, pref: str = 'yamaguchi', page_max: int = 3, muni_ja: str | None = None) -> dict:
    codes = tabelog_c if isinstance(tabelog_c, list) else [tabelog_c]
    all_items, paths, reported_by = [], [], {}
    for c in codes:
        items, total, source, ps = _scrape_one_c(slug, c, pref, page_max=page_max, muni_ja=muni_ja)
        reported_by[c] = total
        have = {x['rst_id'] for x in all_items}
        for it in items:
            if it['rst_id'] not in have:
                it['tabelog_rank'] = len(all_items) + 1
                all_items.append(it)
                have.add(it['rst_id'])
        paths.extend(ps)
    out = {
        'count': len(all_items),
        'reported_total': max([v or 0 for v in reported_by.values()] or [0]),
        'reported_by_c': reported_by,
        'source': 'tabelog',
        'tabelog_c': codes,
        'items': all_items,
    }
    save_json(RAW / slug / 'tabelog.json', out)
    return out
