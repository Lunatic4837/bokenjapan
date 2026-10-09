#!/usr/bin/env python3
"""Cover candidates, own images only: crossroadfukuoka (storage/tourism_attractions/{id}/), yamaguchi-tourism
(/lsc/upfile/spot/../{id}_N_l.jpg), akita-fun (spot gallery: first representation images). Cover spot first, then the
page's Sights spots on the same site. Records sizes; does not touch pages."""
import re, json, sys, io
from urllib.parse import urljoin, urlparse
from PIL import Image
sys.argv = ['x']; exec(open('/workspace/p1/phase-d/w4/a4_find.py').read().split('res = {}')[0])
def own(spot, h):
    host = urlparse(spot).netloc
    if 'crossroadfukuoka' in host:
        sid = spot.rstrip('/').split('/')[-1]
        return list(dict.fromkeys(urljoin(spot, u) for u in re.findall(rf'(?:https://www\.crossroadfukuoka\.jp)?/storage/tourism_attractions/{sid}/responsive_images/[^"\s,]+?__\d+_\d+\.(?:jpe?g|png|webp)', h)))
    if 'yamaguchi-tourism' in host:
        sid = re.search(r'detail_(\d+)', spot).group(1)
        return list(dict.fromkeys(urljoin(spot, u) for u in re.findall(rf'/lsc/upfile/spot/\d+/\d+/{sid}_\d+_l\.(?:jpe?g|png)', h)))
    if 'akita-fun' in host:
        return list(dict.fromkeys(urljoin(spot, u.replace('&amp;', '&')) for u in re.findall(r'(https://akita-fun\.jp/rails/active_storage/representations/proxy/[^"\s]+)', h)))[:6]
    return []
res = {}
for page, v in sorted(todo.items()):
    if all('no-credit' in x for x in v) or page.startswith('oita/'): continue
    s = open(f'{REPO}/{page}/index.html').read()
    fig = re.search(r'<figure class="cover">(.*?)</figure>', s, re.S).group(1)
    src = re.search(r'Source (\S+) -->', fig).group(1); host = urlparse(src).netloc
    sights = re.search(r'<section class="place-section"><h2>Sights</h2>(.*?)</section>', s, re.S)
    spots = [src] + [u for u in (re.findall(r'<a href="([^"]+)"', sights.group(1)) if sights else []) if urlparse(u).netloc == host and u != src][:10]
    cands = []
    for sp in spots:
        h = get(sp)
        if not h: continue
        t = re.search(r'<title>(.*?)</title>', h, re.S); t = re.sub(r'\s+', ' ', t.group(1)).split('|')[0].strip() if t else ''
        urls = own(sp, h)
        if 'crossroadfukuoka' in host:  # keep only the largest rendition of each image
            best = {}
            for u in urls:
                k, w = re.search(r'/([^/]+)__(\d+)_\d+\.', u).groups()
                if int(w) > best.get(k, (0, ''))[0]: best[k] = (int(w), u)
            urls = [u for _, u in best.values()]
        for u in urls[:6]:
            b = get(u, True)
            if not b: continue
            try: w, hh = Image.open(io.BytesIO(b)).size
            except Exception: continue
            cands.append(dict(spot=sp, title=t, img=u, w=w, h=hh, bytes=len(b), cache=f"{D}/cache/{hashlib.sha1(u.encode()).hexdigest()}"))
        if sp == src and any(c['spot'] == src and c['w'] >= 800 and c['w'] > c['h'] for c in cands): break
        if sum(1 for c in cands if c['w'] >= 1000 and c['w'] > c['h']) >= 3: break
    own_ok = [c for c in cands if c['spot'] == src and c['w'] >= 800 and c['w'] > c['h'] and c['bytes'] >= 60000]
    other = sorted([c for c in cands if c['spot'] != src and c['w'] >= 1000 and c['w'] > c['h'] and c['bytes'] >= 60000], key=lambda c: -c['w'])
    pick = (sorted(own_ok, key=lambda c: -c['w']) or other or [None])[0]
    res[page] = dict(src=src, pick=pick, n=len(cands))
    print(page, len(cands), pick and (pick['spot'] == src, pick['w'], pick['h'], pick['title'], pick['spot']), flush=True)
json.dump(res, open('/workspace/p1/phase-d/w4/covers_pick.json', 'w'), ensure_ascii=False, indent=0)
