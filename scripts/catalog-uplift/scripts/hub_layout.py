#!/usr/bin/env python3
"""Generic layout post-pass for hub-template pages.
  python3 hub_layout.py --root <site> --pref aomori [--pref ...]
1. Main hub grid (first tile full width, then pairs): when the tile count is even, the last tile would sit alone at half
   width -> give it grid-column 1/-1 and the wide 21:9 ratio inline (styles.css is owned by Homepage; no CSS edits).
2. Card thumbs (<img class="thumb">) without width/height get the real pixel size of the media file (no layout shift).
"""
import re, glob, os, argparse, collections
from PIL import Image
WIDE = ' style="grid-column:1/-1"'
def fix_hub(src, st):
    def one(m):
        ul = m.group(0)
        lis = re.findall(r'<li(?: style="[^"]*")?>', ul)
        ul = ul.replace(f'<li{WIDE}>', '<li>').replace('<a class="hub-tile" style="aspect-ratio:21/9"', '<a class="hub-tile"')
        if len(lis) >= 2 and len(lis) % 2 == 0:
            i = ul.rfind('<li><a class="hub-tile"')
            ul = ul[:i] + f'<li{WIDE}><a class="hub-tile" style="aspect-ratio:21/9"' + ul[i + len('<li><a class="hub-tile"'):]
            st['wide_last'] += 1
        return ul
    return re.sub(r'<ul class="hub-tiles">.*?</ul>', one, src, flags=re.S)
_SZ = {}
def size(root, src):
    p = os.path.join(root, src.lstrip('/')) if src.startswith('/') else None
    if p is None:
        p = os.path.join(root, 'media', src.split('/')[-1])
    if p not in _SZ:
        try:
            with Image.open(p) as im: _SZ[p] = im.size
        except Exception: _SZ[p] = None
    return _SZ[p]
def fix_imgs(root, src, st):
    def one(m):
        t = m.group(0)
        if ' width=' in t: return t
        s = re.search(r'src="([^"]+)"', t); wh = s and size(root, s.group(1))
        if not wh: st['img_nosize'] += 1; return t
        st['img_wh'] += 1
        return t.replace(' loading=', f' width="{wh[0]}" height="{wh[1]}" loading=', 1) if ' loading=' in t else t[:-1] + f' width="{wh[0]}" height="{wh[1]}">'
    return re.sub(r'<img class="thumb"[^>]*>', one, src)
def run(root, pref):
    st = collections.Counter()
    for f in glob.glob(f'{root}/{pref}/**/index.html', recursive=True):
        s = open(f).read(); o = fix_imgs(root, fix_hub(s, st), st)
        if o != s: open(f, 'w').write(o); st['files'] += 1
    return st
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--pref', action='append', required=True); A = ap.parse_args()
    for p in A.pref: print(p, dict(run(A.root, p)), flush=True)
