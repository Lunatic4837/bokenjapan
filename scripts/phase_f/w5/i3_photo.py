#!/usr/bin/env python3
"""Item 3 step 4: photo per rules - official homepage (og:image/twitter:image) first, else Jalan listing photo."""
import json, re, os, io, time, hashlib, requests, collections
from PIL import Image
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'
S = requests.Session(); S.headers['User-Agent'] = UA
cards = json.load(open('i3_cards.json'))
for c in cards:
    if c.get('hp') and c['hp'].startswith('http://'): c['hp'] = 'https://' + c['hp'][7:]; st = collections.Counter()
def grab(u, ref=None):
    try:
        r = S.get(u, timeout=(8, 20), headers={'Referer': ref} if ref else {}); time.sleep(0.7)
        if r.status_code != 200 or not r.headers.get('content-type', '').startswith('image'): return None
        im = Image.open(io.BytesIO(r.content)); im.load(); return r.content, im
    except Exception: return None
def ok(im):
    w, h = im.size; return w >= 480 and h >= 300 and 1.0 <= w / h <= 2.2
for c in cards:
    slug = c['page'].split('/')[1]; c['photo'] = None
    if c.get('hp'):
        try:
            r = S.get(c['hp'], timeout=(8, 20)); time.sleep(0.7)
            if r.status_code == 200:
                t = r.content.decode(r.apparent_encoding or 'utf-8', 'replace')
                m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', t, re.I) or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)', t, re.I)
                if m:
                    iu = requests.compat.urljoin(r.url, m.group(1).strip())
                    g = grab(iu, r.url)
                    if g and ok(g[1]): c['photo'] = dict(src=iu, page=c['hp'], kind='official', size=g[1].size); c['_bytes'] = g[0]; st['official'] += 1
                    else: c['hp_note'] = f'og:image unusable {g[1].size if g else "fetch failed"}'
                else: c['hp_note'] = 'no og:image'
            else: c['hp_note'] = f'HTTP {r.status_code}'
        except Exception as e: c['hp_note'] = 'fetch error ' + type(e).__name__
    if not c['photo']:
        for iu in [c.get('jalan_img'), c.get('og_img')]:
            if not iu: continue
            g = grab(iu, c['jalan_url'])
            if g and g[1].size[0] >= 300: c['photo'] = dict(src=iu, page=c['jalan_url'], kind='jalan', size=g[1].size); c['_bytes'] = g[0]; st['jalan'] += 1; break
    if not c['photo']: st['none'] += 1; continue
    im = Image.open(io.BytesIO(c.pop('_bytes'))).convert('RGB')
    if im.size[0] > 1200: im = im.resize((1200, round(im.size[1] * 1200 / im.size[0])), Image.LANCZOS)
    key = f"media/{slug}-stay-w5-{c['yid']}.jpg"; p = f'stage/{key}'
    im.save(p, 'JPEG', quality=85, optimize=True, progressive=True)
    c['photo'].update(key=key, w=im.size[0], h=im.size[1], bytes=os.path.getsize(p), sha256=hashlib.sha256(open(p, 'rb').read()).hexdigest())
json.dump(cards, open('i3_cards_photo.json', 'w'), ensure_ascii=False, indent=0)
print(dict(st))
for c in cards: print(c['page'], c['name'], (c['photo'] or {}).get('kind'), (c['photo'] or {}).get('size'), c.get('hp_note', ''))
