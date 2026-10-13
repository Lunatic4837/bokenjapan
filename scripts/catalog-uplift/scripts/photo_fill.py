#!/usr/bin/env python3
"""Generic photo fill for photo-less cards (any page under <root>/<pref>/).
For each card without <img class="thumb">, fetch the card's own linked page (Tabelog, Tripadvisor, official site),
take og:image (placeholders rejected), validate (>=200px, not flat), save slim WebP to media/, insert thumb with
width/height + photo-credit comment. Every attempt is logged to a CSV (search log); og lookups cached in JSONL.
  python3 photo_fill.py --root <site> --pref miyagi [--muni ishinomaki ...] [--log out.csv] [--workers 6]
"""
import re, os, io, sys, csv, json, glob, html, hashlib, argparse, subprocess, collections, time
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageStat
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36'
CACHE = '/workspace/p1/data/photofill/og.jsonl'
BAD_OG = re.compile(r'no_?photo|no_?image|noimage|default|placeholder|logo|tblg\.k-img\.com/images/|/common/|ogp_default|share', re.I)
def curl(u, t=25):
    r = subprocess.run(['curl', '-sL', '--compressed', '--max-time', str(t), '-A', UA, '-w', '\n%{http_code}', u], capture_output=True)
    b = r.stdout; i = b.rfind(b'\n'); return b[:i], (b[i + 1:].decode() or '0')
def og_of(u):
    b, code = curl(u)
    if code != '200': return None, f'http_{code}'
    s = b.decode('utf-8', 'ignore')
    m = re.search(r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)', s) or re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+property=["\']og:image', s)
    if not m: return None, 'no_og'
    og = html.unescape(m.group(1))
    if og.startswith('//'): og = 'https:' + og
    if BAD_OG.search(og): return None, 'placeholder_og'
    return og, 'og'
def load_cache():
    d = {}
    if os.path.exists(CACHE):
        for l in open(CACHE):
            try: x = json.loads(l); d[x['u']] = x
            except Exception: pass
    return d
def fetch_img(og):
    b, code = curl(og, 30)
    if code != '200': return None
    try:
        im = Image.open(io.BytesIO(b)).convert('RGB')
    except Exception: return None
    if min(im.size) < 200 or ImageStat.Stat(im.convert('L').resize((64, 64))).stddev[0] < 15: return None
    if im.width > 480: im = im.resize((480, round(im.height * 480 / im.width)))
    return im
def work(u, root, cache, lock_out):
    if u in cache and cache[u].get('res') in ('filled', 'no_og', 'placeholder_og', 'bad_image') or (u in cache and cache[u].get('res', '').startswith('http_4')):
        return cache[u]
    og, res = og_of(u); rec = {'u': u, 'og': og, 'res': res}
    if og:
        name = 'pf-' + hashlib.sha1(u.encode()).hexdigest()[:12] + '.webp'; dest = os.path.join(root, 'media', name)
        if not os.path.exists(dest):
            im = fetch_img(og)
            if im is None: rec['res'] = 'bad_image'
            else: im.save(dest, 'WEBP', quality=72, method=5)
        if os.path.exists(dest):
            with Image.open(dest) as im: rec.update(res='filled', media=name, w=im.width, h=im.height)
    with lock_out: open(CACHE, 'a').write(json.dumps(rec) + '\n')
    time.sleep(0.3)
    return rec
def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--pref', required=True)
    ap.add_argument('--muni', nargs='*'); ap.add_argument('--log'); ap.add_argument('--workers', type=int, default=6); A = ap.parse_args()
    import threading; lk = threading.Lock()
    files = sorted(glob.glob(f'{A.root}/{A.pref}/*/**/index.html', recursive=True))
    if A.muni: files = [f for f in files if f.split('/')[-len(f.split('/')) + len(A.root.rstrip('/').split('/')) + 1] in A.muni or any(f'/{A.pref}/{m}/' in f for m in A.muni)]
    CARD = re.compile(r'<li><a href="(https?://[^"]+)"><p class="place-name">([^<]*)</p>(?:<!-- photo-missing[^>]*-->)?</a>')
    urls = collections.OrderedDict()
    for f in files:
        for u, n in CARD.findall(open(f).read()): urls.setdefault(html.unescape(u), (f, n))
    cache = load_cache(); print(A.pref, 'photo-less cards (unique urls):', len(urls), flush=True)
    with ThreadPoolExecutor(A.workers) as ex:
        recs = dict(zip(urls, ex.map(lambda u: work(u, A.root, cache, lk), urls)))
    st = collections.Counter(r['res'] for r in recs.values()); print(A.pref, dict(st), flush=True)
    for f in files:
        s = open(f).read()
        def rep(m):
            r = recs.get(html.unescape(m.group(1)))
            if not r or r.get('res') != 'filled': return m.group(0)
            rel = '/media/' + r['media']
            return (f'<li><a href="{m.group(1)}"><p class="place-name">{m.group(2)}</p><img class="thumb" src="{rel}" alt="{m.group(2)}" '
                    f'width="{r["w"]}" height="{r["h"]}" loading="lazy"><!-- photo-credit: source · Source {m.group(1)} --></a>')
        o = CARD.sub(rep, s)
        if o != s: open(f, 'w').write(o)
    if A.log:
        new = not os.path.exists(A.log)
        with open(A.log, 'a', newline='') as fh:
            w = csv.writer(fh)
            if new: w.writerow(['pref', 'page', 'name', 'card_url', 'source_searched', 'result', 'og_image'])
            for u, (f, n) in urls.items():
                r = recs[u]; w.writerow([A.pref, f.split(A.root.rstrip('/') + '/')[-1], html.unescape(n), u, re.sub(r'^https?://([^/]+).*', r'\1', u), r['res'], r.get('og') or ''])
main()
