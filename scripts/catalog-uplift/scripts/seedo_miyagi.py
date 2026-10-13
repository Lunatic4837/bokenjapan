#!/usr/bin/env python3
"""Do/Stay candidates from the official Miyagi tourism guide (miyagi-kankou.or.jp theme search) -> JSONL for seedo_pages.py."""
import re, json, html, subprocess, sys, argparse, time
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
B = 'https://www.miyagi-kankou.or.jp'
CATS = {'do': [116, 114, 117, 113, 121, 258, 102, 103, 104, 251, 252], 'stay': [110, 111, 255, 246]}
def get(u): return subprocess.run(['curl', '-sL', '--max-time', '30', '-A', UA, u], capture_output=True).stdout.decode('utf-8', 'ignore')
def field(t, k):
    m = re.search(r'\n' + k + r'\n+([^\n]+)', t); return m.group(1).strip() if m else ''
ap = argparse.ArgumentParser(); ap.add_argument('--town', nargs=4, action='append', metavar=('SLUG', 'AREA', 'JA', 'KIND')); ap.add_argument('--out'); A = ap.parse_args()
out = open(A.out, 'a')
for slug, area, ja, kind in A.town:
    q = '&'.join(f'c%5B%5D={c}' for c in CATS[kind])
    ids = list(dict.fromkeys(re.findall(r'detail\.php\?id=(\d+)', get(f'{B}/theme/?sid=36&a%5B%5D={area}&{q}&l=60'))))
    n = 0
    for i in ids[:25]:
        u = f'{B}/theme/detail.php?id={i}'; s = get(u); time.sleep(0.3)
        s2 = re.sub(r'<script.*?</script>|<style.*?</style>', '', s, flags=re.S)
        k = s2.find('theme_secTTL')
        if k < 0: continue
        blk = s2[k:k + 8000]
        t = re.sub(r'\n\s*\n+', '\n', re.sub(r'<[^>]+>', '\n', blk))
        name = html.unescape(re.search(r'theme_secTTL">([^<]+)', blk).group(1)).strip()
        addr = field(t, '住所'); cat = field(t, '目的'); tel = re.sub(r'\s', '', field(t, 'TEL：'))
        img = next((x for x in re.findall(r'<img[^>]+src="([^"]+)"', blk) if 'file.php' in x), '')
        r = dict(id=i, url=u, name=name, og=(B + html.unescape(img)) if img else '', cat=cat, tel=tel, addr=addr,
                 desc_ja=field(t, '内容')[:300], muni=slug, kind=kind, in_town=ja in addr or ja in field(t, '市町村'))
        out.write(json.dumps(r, ensure_ascii=False) + '\n'); n += 1
    print(slug, kind, len(ids), n, file=sys.stderr)
