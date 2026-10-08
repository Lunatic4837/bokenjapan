#!/usr/bin/env python3
"""Second photo pass for no-photo Dining cards: each facility's own Tabelog photo tab (/dtlphotolst/).
Food tab first (/dtlphotolst/1/), then all photos. Prefer restaurant-posted photos over user posts."""
import json, re, os, sys, time, threading, html, requests, concurrent.futures as cf
sys.path.insert(0, '/workspace/p1/photos-5pref/_work')
import imgproc
W = '/workspace/p1/phase-d/tbphoto'; OUT = '/workspace/p1/photos-5pref'
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0 Safari/537.36'
tgt = json.load(open('/workspace/p1/phase-d/tb_targets.json'))
names = {}
import csv
for r in csv.DictReader(open(f'{OUT}/no-photo-found.csv')): names[r['card_key']] = r['name_ja']
for r in json.load(open(f'{W}/rejected_rows.json')): names[r['card_key']] = r['name_ja']
res_path = f'{W}/results.json'
res = json.load(open(res_path)) if os.path.exists(res_path) else {}
lock = threading.Lock(); tl = threading.local()
def sess():
    if not hasattr(tl, 's'): tl.s = requests.Session(); tl.s.headers['User-Agent'] = UA
    return tl.s
def get(url, cache=None):
    if cache and os.path.exists(cache): return 200, open(cache, encoding='utf-8').read()
    for i in range(3):
        try:
            r = sess().get(url, timeout=25); time.sleep(0.6)
            if r.status_code == 200:
                if cache: open(cache, 'w', encoding='utf-8').write(r.text)
                return 200, r.text
            if r.status_code in (403, 429, 503): time.sleep(20 * (i + 1)); continue
            return r.status_code, ''
        except Exception as e: time.sleep(5)
    return 'ERR', ''
ITEM = re.compile(r'href="https://tblg\.k-img\.com/restaurant/images/Rvw/(\d+)/(?:\d+x\d+_rect_)?([0-9a-f]{32})\.(jpg|jpeg|png)"[^>]*data-analytics-post-type=\'(\w+)\'', re.S)
def one(url):
    rid = url.rstrip('/').rsplit('/', 1)[-1]
    tried = []
    for tab in ('dtlphotolst/1/', 'dtlphotolst/'):
        st, s = get(url + tab, f'{W}/html/{rid}-{tab.replace("/", "_")}.html')
        tried.append(f'{tab}:{st}')
        if st != 200: continue
        items = ITEM.findall(s)
        if not items: continue
        items.sort(key=lambda t: t[3] == 'user')  # restaurant/official posts first
        for d, h, ext, ptype in items[:4]:
            img = f'https://tblg.k-img.com/restaurant/images/Rvw/{d}/{h}.{ext}'
            try:
                r = sess().get(img, timeout=25, headers={'Referer': url}); time.sleep(0.3)
            except Exception: continue
            if r.status_code != 200: continue
            ok, why, im = imgproc.check(r.content, img)
            if not ok: tried.append(f'img-reject:{why}'); continue
            ck = tgt[url][0]; slug = ck.split('|')[0].split('/')[1]
            rel = f'media/{slug}-dining-{rid}-tp.webp'
            nm = names.get(ck, '')
            credit = f'{nm} (食べログ) · Source {url}{tab}'
            size = imgproc.save_webp(im, f'{OUT}/{rel}', credit, f'Tabelog listing photo · Source {url}{tab}')
            return dict(found=True, path=rel, img=img, page=url + tab, ptype=ptype, size=list(size), credit=credit, tried=tried)
    return dict(found=False, tried=tried)
todo = [u for u in tgt if u not in res]
print('targets', len(tgt), 'todo', len(todo), flush=True)
n = 0
with cf.ThreadPoolExecutor(3) as ex:
    for u, r in zip(todo, ex.map(one, todo)):
        with lock:
            res[u] = r; n += 1
            if n % 50 == 0:
                json.dump(res, open(res_path + '.tmp', 'w'), ensure_ascii=False); os.replace(res_path + '.tmp', res_path)
                print(time.strftime('%H:%M:%S'), n, 'found', sum(1 for v in res.values() if v['found']), flush=True)
json.dump(res, open(res_path, 'w'), ensure_ascii=False)
print('DONE', len(res), 'found', sum(1 for v in res.values() if v['found']))
