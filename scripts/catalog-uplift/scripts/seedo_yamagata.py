#!/usr/bin/env python3
"""Collect See/Do spots for Yamagata municipalities from the official prefectural tourism site (yamagatakanko.com).
Per municipality: list pages filtered by area + See or Do categories, then each spot's detail page
(name, categories, address -> must contain the town's JA name, phone, og:image). Output JSONL cache.
  python3 seedo_yamagata.py --munis kaneyama:金山町:9 ... --out /workspace/p1/data/seedo/yamagata.jsonl
"""
import re, sys, json, html, subprocess, argparse, os, time
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
SEE = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 23, 25]
DO = [16, 17, 18, 19, 20, 21, 22, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39]
def get(u):
    r = subprocess.run(['curl', '-sL', '--compressed', '--max-time', '30', '-A', UA, u], capture_output=True)
    return r.stdout.decode('utf-8', 'ignore')
def listing(area, cats, pages=2):
    ids = []
    for pg in range(1, pages + 1):
        s = get(f'https://yamagatakanko.com/attractions/index_{pg}_2_{",".join(map(str, cats))}_{area}________.html')
        new = [x for x in re.findall(r'href="detail_(\d+)\.html"', s) if x not in ids]
        if not new: break
        ids += new
    return ids
def detail(i):
    s = get(f'https://yamagatakanko.com/attractions/detail_{i}.html')
    t = lambda k: (re.search(k + r'</(?:dt|th)>\s*<(?:dd|td)[^>]*>(.*?)</(?:dd|td)>', s, re.S) or [None, ''])[1]
    clean = lambda x: re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', x or ''))).strip()
    name = clean((re.search(r'<h2[^>]*>(.*?)</h2>', s, re.S) or re.search(r'<title>(.*?)[｜|]', s, re.S) or [None, ''])[1])
    og = (re.search(r'og:image" content="([^"]+)', s) or [None, None])[1]
    cats = re.findall(r'class="[^"]*cat[^"]*"[^>]*>([^<]+)<', s)
    ci = s.find('カテゴリー'); catblk = clean(s[ci:ci + 400]) if ci > 0 else ''
    return dict(id=i, url=f'https://yamagatakanko.com/attractions/detail_{i}.html', name=name, og=og, cat=catblk,
                addr=clean(t('住所')), tel=clean(t('電話番号')).split(' ')[0])
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--munis', nargs='+'); ap.add_argument('--out'); A = ap.parse_args()
    done = set()
    if os.path.exists(A.out):
        for l in open(A.out): x = json.loads(l); done.add((x['muni'], x['kind'], x['id']))
    with open(A.out, 'a') as fh:
        for m in A.munis:
            slug, ja, area = m.split(':')
            for kind, cats in (('see', SEE), ('do', DO)):
                for i in listing(area, cats)[:14]:
                    if (slug, kind, i) in done: continue
                    d = detail(i); d.update(muni=slug, muni_ja=ja, kind=kind, in_town=ja in d['addr'])
                    fh.write(json.dumps(d, ensure_ascii=False) + '\n'); fh.flush(); time.sleep(0.3)
            print(slug, 'done', flush=True)
