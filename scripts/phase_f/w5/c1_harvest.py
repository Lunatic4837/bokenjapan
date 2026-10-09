#!/usr/bin/env python3
"""Item 2: harvest large landscape photos from each town's own official tourism / municipal site (same host only)."""
import re, json, os, io, sys, time, hashlib, html, urllib.parse as U, requests, concurrent.futures as cf
from PIL import Image
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'
SEEDS = {
 'oita/bungoono': ['https://sato-no-tabi.jp/', 'https://sato-no-tabi.jp/introduce/%e5%8e%9f%e5%b0%bb%e3%81%ae%e6%bb%9d/'],
 'oita/bungotakada': ['https://www.city.bungotakada.oita.jp/site/showanomachi/', 'https://www.city.bungotakada.oita.jp/site/showanomachi/1278.html'],
 'oita/hiji': ['https://hijinavi.com/'],
 'oita/himeshima': ['https://www.himeshima.jp/kankou/', 'https://www.himeshima.jp/about/geopark/'],
 'oita/hita': ['https://oidehita.com/', 'https://oidehita.com/archives/29493'],
 'oita/kitsuki': ['https://kit-suki.com/', 'https://kit-suki.com/pages/36/'],
 'oita/kunisaki': ['https://visit-kunisaki.com/'],
 'oita/kusu': ['https://kusumachi.jp/', 'https://kusumachi.jp/kankouspot/'],
 'oita/nakatsu': ['https://nakatsuyaba.com/'],
 'oita/saiki': ['https://www.visit-saiki.jp/', 'https://www.visit-saiki.jp/photos/'],
 'oita/taketa': ['https://taketa.guide/', 'https://taketa.guide/spots/detail/07fb5cc5-fa6c-4eee-9b51-fea20d2b67fc'],
 'oita/tsukumi': ['https://tsukumiryoku.com/'],
 'oita/usa': ['https://www.usa-kanko.jp/', 'https://www.usa-kanko.jp/pages/116/'],
 'fukuoka/kawasaki': ['https://www.town-kawasaki.com/kanko', 'https://www.town-kawasaki.com/kanko/shizen/869', 'https://www.town-kawasaki.com/kanko/shizen/865'],
 'akita/ugo': ['https://ugokanko.com/'],
}
KW = re.compile(r'spot|kankou|kanko|introduce|pages/|archives|detail|shizen|sightseeing|see|course|geopark|photo|gallery|midokoro', re.I)
def work(key):
    S = requests.Session(); S.headers['User-Agent'] = UA
    host = U.urlparse(SEEDS[key][0]).netloc
    out_dir = f'cov/{key.replace("/", "_")}'; os.makedirs(out_dir, exist_ok=True)
    queue = list(SEEDS[key]); seen = set(); imgs = {}; pages = 0
    while queue and pages < 45:
        u = queue.pop(0)
        if u in seen: continue
        seen.add(u)
        try: r = S.get(u, timeout=(8, 20)); time.sleep(0.5)
        except Exception: continue
        if r.status_code != 200 or 'html' not in r.headers.get('content-type', ''): continue
        pages += 1
        t = r.content.decode(r.apparent_encoding or 'utf-8', 'replace')
        title = html.unescape((re.search(r'<title>(.*?)</title>', t, re.S) or [None, ''])[1]).strip()
        cands = []
        for m in re.finditer(r'<img\b[^>]*>', t, re.I):
            tag = m.group(0); alt = (re.search(r'alt=["\']([^"\']*)', tag) or [None, ''])[1]
            for a in ('data-src', 'data-lazy-src', 'data-original', 'src'):
                mm = re.search(a + r'=["\']([^"\']+)', tag)
                if mm: cands.append((mm.group(1), alt)); break
            ss = re.search(r'srcset=["\']([^"\']+)', tag)
            if ss:
                parts = [p.strip().split(' ')[0] for p in ss.group(1).split(',') if p.strip()]
                if parts: cands.append((parts[-1], alt))
        for mm in re.finditer(r'(?:og:image|twitter:image)["\'][^>]*content=["\']([^"\']+)', t): cands.append((mm.group(1), 'og'))
        for mm in re.finditer(r'url\(["\']?([^"\')]+\.(?:jpe?g|png|webp))', t, re.I): cands.append((mm.group(1), 'bg'))
        for mm in re.finditer(r'href=["\']([^"\']+\.(?:jpe?g|png|webp))["\']', t, re.I): cands.append((mm.group(1), 'link'))
        for src, alt in cands:
            iu = U.urljoin(r.url, html.unescape(src))
            if not re.search(r'\.(jpe?g|png|webp)(\?|$)', iu, re.I): continue
            if iu not in imgs: imgs[iu] = dict(page=r.url, title=title, alt=alt)
        for mm in re.finditer(r'href=["\']([^"\'#]+)', t):
            v = U.urljoin(r.url, html.unescape(mm.group(1)))
            if U.urlparse(v).netloc == host and v not in seen and KW.search(v) and not re.search(r'\.(pdf|jpe?g|png|zip)$', v, re.I):
                queue.append(v)
    keep = []; n = 0
    for iu, meta in imgs.items():
        if n >= 220: break
        n += 1
        try:
            r = S.get(iu, timeout=(8, 25)); time.sleep(0.3)
            if r.status_code != 200: continue
            im = Image.open(io.BytesIO(r.content)); w, h = im.size
        except Exception: continue
        if w >= 1000 and 1.2 <= w / h <= 2.5:
            fn = hashlib.md5(iu.encode()).hexdigest()[:12] + '.' + (im.format or 'jpg').lower().replace('jpeg', 'jpg')
            open(f'{out_dir}/{fn}', 'wb').write(r.content)
            keep.append(dict(file=fn, url=iu, w=w, h=h, bytes=len(r.content), **meta))
    json.dump(keep, open(f'{out_dir}/index.json', 'w'), ensure_ascii=False, indent=0)
    return key, pages, len(imgs), len(keep)
with cf.ThreadPoolExecutor(5) as ex:
    for res in ex.map(work, list(SEEDS)): print(*res, flush=True)
