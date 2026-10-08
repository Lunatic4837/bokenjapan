#!/usr/bin/env python3
"""HEAD every distinct image URL referenced by the 5-pref pages + homepage (local repo files). Read-only."""
import re, glob, sys, json, collections, concurrent.futures as cf, requests
REPO = sys.argv[1] if len(sys.argv) > 1 else '/workspace/p1/pr12-work'
urls = collections.Counter()
for p in glob.glob(f'{REPO}/*/*/index.html') + glob.glob(f'{REPO}/*/index.html') + [f'{REPO}/index.html']:
    for u in re.findall(r'<img[^>]+src="(https?://[^"]+)"', open(p, encoding='utf-8').read()): urls[u] += 1
s = requests.Session(); a = requests.adapters.HTTPAdapter(pool_maxsize=48); s.mount('https://', a)
def h(u):
    for i in range(3):
        try:
            r = s.head(u, timeout=20)
            return u, r.status_code, r.headers.get('content-type', ''), int(r.headers.get('content-length') or 0)
        except Exception as e: err = str(e)[:80]
    return u, None, err, 0
bad = []; st = collections.Counter()
with cf.ThreadPoolExecutor(48) as ex:
    for u, code, ct, n in ex.map(h, list(urls)):
        ok = code == 200 and ct.startswith('image/') and n >= 1000
        st['ok' if ok else 'bad'] += 1
        if not ok: bad.append((u, code, ct, n))
print('distinct', len(urls), 'refs', sum(urls.values()), dict(st))
json.dump(bad, open('/workspace/p1/phase-d/img_sweep_bad.json', 'w'), indent=0)
print(bad[:10])
