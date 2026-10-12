#!/usr/bin/env python3
from __future__ import annotations
from common import curl, save_json, RAW

def scrape_ikkyu(slug: str, name_ja: str) -> dict:
    rawdir = RAW / slug
    rawdir.mkdir(parents=True, exist_ok=True)
    urls = [
        f'https://www.ikyu.com/search/?keyword={name_ja}',
        f'https://www.ikyu.com/',
    ]
    codes, tried = [], []
    for i, url in enumerate(urls[:2]):
        dest = rawdir / f'ikkyu-try{i}.html'
        code, _ = curl(url, dest, timeout=20)
        codes.append(code)
        tried.append(url)
        if code == 200:
            break
    status = 'BLOCKER_NEED_BROWSER' if all(c in (403, 0, 404) for c in codes) else 'empty'
    out = {'count': 0, 'status': status, 'note': 'Ikkyu often 403 — Jalan-only OK',
           'urls_tried': tried, 'http_codes': codes, 'items': []}
    save_json(rawdir / 'ikkyu.json', out)
    return out
