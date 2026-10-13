#!/usr/bin/env python3
"""Collect Do (leisure + onsen) / See (sightseeing) spots for Iwate municipalities from the official guide iwatetabi.jp.
Lists JA category pages filtered by area, then reads each spot's EN page (h1 name, city, lead paragraph, first slide image, TEL).
  python3 seedo_iwate.py --munis morioka:morioka-city ... --kinds do --out /workspace/p1/data/seedo/iwate.jsonl
"""
import re, json, html, subprocess, argparse, os, time
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
CATS = {'do': ['leisure', 'onsen-accomodations/onsen'], 'see': ['sightseeing']}
def get(u):
    return subprocess.run(['curl', '-sL', '--compressed', '--max-time', '30', '-A', UA, u], capture_output=True).stdout.decode('utf-8', 'ignore')
clean = lambda x: re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', x or ''))).strip()
def ids(area, cat):
    out = []
    for pg in (1, 2):
        s = get(f'https://iwatetabi.jp/spots/spots_category/{cat}/' + (f'page/{pg}/' if pg > 1 else '') + f'?area%5B%5D={area}')
        new = [x for x in re.findall(r'href="https://iwatetabi.jp/spots/(\d+)/"', s) if x not in out]
        if not new: break
        out += new
    return out
def spot(i):
    s = get(f'https://iwatetabi.jp/en/spots/{i}/')
    g = lambda rx: (re.search(rx, s, re.S) or [None, ''])[1]
    tel = re.search(r'TEL\.?\s*([0-9０-９\-－]{9,})', clean(s))
    return dict(id=i, url=f'https://iwatetabi.jp/en/spots/{i}/', name=clean(g(r'<h1 class="c-page-ttl">(.*?)</h1>')),
                city=clean(g(r'class="c-place__city">(.*?)</p>')), og=g(r'l-underlayer-slide__img[^>]*>\s*<img src="([^"]+)"') or None,
                desc=clean(g(r'<p class="l-underlayer-lead">(.*?)</p>')), cats=re.findall(r'class="c-category__item">([^<]+)<', s),
                tel=tel.group(1) if tel else '')
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--munis', nargs='+'); ap.add_argument('--kinds', nargs='+', default=['do']); ap.add_argument('--out'); A = ap.parse_args()
    done = set()
    if os.path.exists(A.out):
        for l in open(A.out): x = json.loads(l); done.add((x['muni'], x['kind'], x['id']))
    with open(A.out, 'a') as fh:
        for m in A.munis:
            slug, area = m.split(':'); city_en = area.split('-')[0]
            for kind in A.kinds:
                seen = []
                for c in CATS[kind]: seen += [x for x in ids(area, c) if x not in seen]
                for i in seen[:14]:
                    if (slug, kind, i) in done: continue
                    d = spot(i); d.update(muni=slug, kind=kind, in_town=d['city'].lower().startswith(city_en))
                    fh.write(json.dumps(d, ensure_ascii=False) + '\n'); fh.flush(); time.sleep(0.3)
            print(slug, 'done', flush=True)
