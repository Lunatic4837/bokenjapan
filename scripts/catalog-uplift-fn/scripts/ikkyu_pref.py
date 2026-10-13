#!/usr/bin/env python3
"""Build ordered Ikkyu inventory for one prefecture (list order = Ikkyu recommended rank)."""
from __future__ import annotations
import json, re, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import curl, save_json, RAW

AREAS = {'fukushima': 'tohoku/120260', 'niigata': 'koshinetsu/210551'}

def build(pref: str) -> dict:
    area = AREAS[pref]
    d = RAW / f'_ikkyu_{pref}'; d.mkdir(parents=True, exist_ok=True)
    out_path = RAW / f'ikkyu-{pref}.json'
    cache = json.loads(out_path.read_text()) if out_path.exists() else {'ids': [], 'hotels': {}}
    ids = cache['ids']
    if not ids:
        for p in range(1, 60):
            url = f'https://www.ikyu.com/{area}/' + (f'p{p}/' if p > 1 else '')
            code, html = curl(url, d / f'list-p{p}.html', timeout=30)
            got = [m for m in re.findall(r'href="/(000\d{5})/', html)]
            new = [x for x in dict.fromkeys(got) if x not in ids]
            print('page', p, code, len(new), flush=True)
            if code != 200 or not new:
                break
            ids.extend(new)
            time.sleep(1.0)
        cache['ids'] = ids
        save_json(out_path, cache)
    for i, hid in enumerate(ids):
        if hid in cache['hotels']:
            continue
        url = f'https://www.ikyu.com/{hid}/'
        code, html = curl(url, d / 'detail.html', timeout=30)
        rec = {'id': hid, 'rank': i + 1, 'ikkyu_url': url, 'http': code}
        if code == 200:
            t = re.search(r'<title>([^<]*?) - 宿泊予約', html)
            rec['name_ja'] = (t.group(1).strip() if t else '')
            og = re.search(r'property="og:image"\s+content="([^"]+)"|content="([^"]+)"\s+property="og:image"', html)
            rec['image'] = (og.group(1) or og.group(2)).replace('&amp;', '&') if og else ''
            loc = re.search(r'"addressLocality":"([^"]*)"', html)
            reg = re.search(r'"addressRegion":"([^"]*)"', html)
            rec['locality'] = loc.group(1) if loc else ''
            rec['region'] = reg.group(1) if reg else ''
            ne = re.search(r'<meta property="og:title" content="([^"]*)"', html)
        cache['hotels'][hid] = rec
        print(i + 1, hid, code, rec.get('name_ja'), rec.get('locality'), flush=True)
        if (i + 1) % 10 == 0:
            save_json(out_path, cache)
        time.sleep(0.8)
    save_json(out_path, cache)
    return cache

if __name__ == '__main__':
    build(sys.argv[1])
