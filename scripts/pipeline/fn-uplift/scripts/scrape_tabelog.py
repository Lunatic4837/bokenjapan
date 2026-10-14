#!/usr/bin/env python3
"""Tabelog list collector — AUDIT-47 P2: full pagination (until in-town >= target, the reported N件 total is exhausted,
or page BJ_TABELOG_MAX_PAGES=60), strict in-town filter on the list area text, sub-area (A-code) fallback."""
from __future__ import annotations
import os, sys
from pathlib import Path
from common import curl, save_json, sleep_polite, RAW
sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as S

def parse_list_page(html: str) -> list[dict]:
    rows, _ = S.parse_tabelog_list(html)
    return rows

def _fetcher(slug):
    rawdir = RAW / slug; rawdir.mkdir(parents=True, exist_ok=True)
    def f(url):
        dest = rawdir / ('tabelog-' + __import__("re").sub(r'[^A-Za-z0-9]+', '_', url)[-80:] + '.html')
        code, html = curl(url, dest, timeout=30); sleep_polite(0.6)
        return html if code == 200 else ''
    return f

def scrape_tabelog(slug: str, tabelog_c, pref: str = 'yamaguchi', page_max: int | None = None, muni_ja: str | None = None, target: int | None = None) -> dict:
    """page_max is kept for old callers but ignored unless BJ_TARGET_MODE=legacy; target defaults to the P1 town target."""
    codes = tabelog_c if isinstance(tabelog_c, list) else [tabelog_c]
    target = target or 100
    if os.environ.get('BJ_TARGET_MODE') == 'legacy' and page_max: os.environ['BJ_TABELOG_MAX_PAGES'] = str(page_max)
    in_town = (lambda r: muni_ja in r['area_ja'] or muni_ja in r['addr']) if muni_ja else (lambda r: True)
    all_items, reported_by = [], {}
    for c in codes:
        items, rep = S.tabelog_collect(_fetcher(slug), pref, c, in_town, target - len(all_items), log=print)
        reported_by[c] = rep
        have = {x['rst_id'] for x in all_items}
        all_items += [x for x in items if x['rst_id'] not in have]
        if len(all_items) >= target: break
    for i, it in enumerate(all_items): it['tabelog_rank'] = i + 1; it.setdefault('name_en', '')
    out = {'count': len(all_items), 'reported_total': max([v or 0 for v in reported_by.values()] or [0]), 'reported_by_c': reported_by,
           'source': 'tabelog', 'tabelog_c': codes, 'target': target, 'source_exhausted': len(all_items) < target, 'items': all_items}
    save_json(RAW / slug / 'tabelog.json', out)
    return out
