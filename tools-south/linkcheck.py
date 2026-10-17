#!/usr/bin/env python3
"""Check a JSON list of URLs (HEAD, then GET fallback, 8 threads, 10s). Prints and writes status per URL.
  linkcheck.py urls.json out.json"""
import json, sys, requests, concurrent.futures as cf
requests.packages.urllib3.disable_warnings()
H = {'User-Agent': 'Mozilla/5.0 (compatible; BokenJapanBot/1.0; +https://bokenjapan.com)'}
def chk(u):
    last = None
    for m in ('HEAD', 'GET'):
        try:
            r = requests.request(m, u, headers=H, timeout=(6, 10), allow_redirects=True, verify=False, stream=True)
            last = r.status_code; r.close()
            if r.status_code < 400: return u, r.status_code
        except Exception as e: last = type(e).__name__
    return u, last
urls = json.load(open(sys.argv[1]))
with cf.ThreadPoolExecutor(8) as ex: res = dict(ex.map(chk, urls))
bad = {u: s for u, s in res.items() if not (isinstance(s, int) and s < 400)}
json.dump(res, open(sys.argv[2], 'w'), indent=0)
print('checked', len(res), 'bad', len(bad))
for u, s in sorted(bad.items()): print(s, u)
