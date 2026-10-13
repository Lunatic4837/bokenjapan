#!/usr/bin/env python3
"""Deepen Dining on existing town pages from Tabelog rating-sorted lists (in-town only). Generic:
deepen.py <root> <pref> <pref_ja> <PrefEn> <target> <hub-codes.json> slug..."""
import sys, re, json, html as H
from pathlib import Path
sys.path.insert(0, '/workspace/p1/fn-uplift')
from fn_lib import fetch, genre_en, place_from_addr, download_img
from PIL import Image
root, pref, pref_ja, PREF_EN, target, hubf = sys.argv[1:7]; slugs = sys.argv[7:]
root = Path(root); target = int(target); E = lambda s: H.escape(s or '', quote=True)
hubs = json.load(open(hubf))['hubs']
def inm(a, name):
    a = (a or '').replace(' ', '').replace('\u3000', ''); a = a[len(pref_ja):] if a.startswith(pref_ja) else a
    return a.startswith(name) or bool(re.match(r'[^市県]{1,4}郡' + re.escape(name), a))
def jd(s): return re.sub(r'[\s\u3000・\-ー（）()]', '', s or '').lower()
for sl in slugs:
    h = next(v for v in hubs.values() if v['name_en'].lower().replace(' ', '') == sl.replace('-', ''))
    p = root / pref / sl / 'index.html'; t = p.read_text()
    m = re.search(r'(<section class="place-section"><h2>Dining</h2><ul class="place-list">)(.*?)(</ul></section>)', t, re.S)
    lis = re.findall(r'<li>.*?</li>', m.group(2), re.S)
    have = set(re.findall(r'tabelog\.com/[a-z]+/A\d+/A\d+/(\d+)/', m.group(2))) | {jd(H.unescape(x)) for x in re.findall(r'place-name">([^<]*)', t)}
    new = []
    for pg in range(1, 7):
        if len(lis) + len(new) >= target: break
        u = f'https://tabelog.com/{pref}/{h["tabelog_c"]}/rstLst/' + (f'{pg}/' if pg > 1 else '') + '?SrtT=rt'
        tx = fetch(u)
        if not tx: break
        for b in tx.split('class="list-rst__body"')[1:]:
            mm = re.search(r'href="(https://tabelog\.com/([a-z]+)/A\d+/A\d+/(\d+)/)">([^<]+)</a>', b)
            if not mm: continue
            nm = H.unescape(mm.group(4).strip()); rid = mm.group(3)
            if rid in have or jd(nm) in have: continue
            addr = re.search(r'list-rst__address[^>]*>\s*([^<]+)', b); addr = addr.group(1).strip() if addr else ''
            if mm.group(2) != pref or not addr.replace(' ', '').startswith(pref_ja) or not inm(addr, h['name_ja']): continue
            g = re.search(r'list-rst__area-genre[^>]*>([^<]+)', b); g = g.group(1).split('/')[-1].strip() if g else ''
            if re.search(r'コンビニ|結婚式場|^その他$', g): continue
            img = re.search(r'data-lazy="(https://tblg\.k-img\.com/[^"]+)"', b)
            have |= {rid, jd(nm)}
            new.append(dict(name=nm, url=mm.group(1), rid=rid, addr=addr, genre=g, img=img.group(1) if img else ''))
            if len(lis) + len(new) >= target: break
    out = []
    for x in new:
        rank = len(lis) + len(out) + 1; fn = f'{pref}-{sl}-d{x["rid"]}.webp'; dest = root / 'media' / fn; ph = ''
        if x['img'] and (download_img(x['img'].replace('320x320_square_', '640x640_rect_'), dest, 640) or download_img(x['img'], dest, 640)):
            w, hh = Image.open(dest).size
            ph = f'<img class="thumb" src="../../media/{fn}" alt="{E(x["name"])}" width="{w}" height="{hh}" loading="lazy">'
        ge = genre_en(x['genre']); pl = place_from_addr(x['addr'].replace(pref_ja, ''), h['name_ja'], h['name_en'])
        desc = f'{ge} in {pl}, {PREF_EN}.' if ge else ''
        out.append(f'<li><a href="{E(x["url"])}"><p class="place-name">{E(x["name"])}</p>{ph}</a>' + (f'<!-- photo-credit: 食べログ · Source {E(x["url"])} -->' if ph else '') +
                   f'<p class="place-blurb">{E(x["name"])}</p><p class="place-meta">#{rank} ranked in {E(h["name_en"])}</p>' +
                   (f'<p class="place-desc">{E(desc)}</p>' if desc else '') + f'<!-- desc-source: {E(x["url"])} --><!-- sources: tabelog_url={E(x["url"])} --><!-- locality-addr: {E(x["addr"])} --></li>')
    t = t[:m.start(2)] + m.group(2) + ''.join(out) + t[m.end(2):]
    p.write_text(t); print(sl, len(lis), '+', len(out), 'img', sum('thumb' in o for o in out), flush=True)
