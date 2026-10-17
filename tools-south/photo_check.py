#!/usr/bin/env python3
"""photo_check.py - cheap (no torch/CLIP) photo checks for bokenjapan.com.

 files mode:   photo_check.py [--kind stay|dining] a.webp b.jpg ...
 report mode:  photo_check.py --report --root TREE --pref tottori [--kind stay|dining|all] [--fetch] [--csv out.csv] [--json out.json]

Hard flags (reject):  tiny-bytes (<5KB), narrow (<400px dining / <560px stay), tiny-thumb (<=240px wide, e.g. 100x87), undecodable,
                      flat/logo (low entropy), few-colours (logo/graphic/badge), extreme-aspect, badge-dims (small near-square graphic),
                      alt-food/promo, name-promo (filename/URL: logo|banner|badge|award|icon|coupon|...), dup-image (same bytes on several cards).
Soft flags (review):  maybe-food (warm, saturated, close-up colour profile, no sky), text-heavy (many hard edges on flat colour).
Report mode reads <img class="thumb"> in cards of <pref>/*/{stay,eat}/**/index.html, takes width/height from the HTML attributes first
(free), then the file: local media dir (TREE/media or --media-root), else with --fetch from https://bokenjapan.com (cached in
/workspace/p1/scratch/photo-cache, polite 0.15 s gap).  Exit 0 always; findings are printed and written to CSV/JSON.
"""
import argparse, collections, csv, hashlib, html as H, io, json, re, sys, time
from pathlib import Path

LIVE = 'https://bokenjapan.com'
CACHE = Path('/workspace/p1/scratch/photo-cache')
MIN_BYTES = 5120
STAY_MIN_W, DINING_MIN_W, THUMB_MAX_W = 560, 400, 240
BAD_NAME = re.compile(r'logo|banner|badge|award|icon|sprite|favicon|coupon|campaign|ranking|noimage|no_image|no-image|dummy|placeholder|btn_|button|qr|emblem|stamp|ubereats|demae|wolt|menu\.jp|promo|bnr', re.I)
FOOD_ALT = re.compile(r'料理|ランチ|ディナー|夕食|朝食|食事|グルメ|会席|懐石|ステーキ|刺身|海鮮|カニ|蟹|ラーメン|寿司|鍋|弁当|ケーキ|スイーツ|メニュー|コース|バイキング|ブッフェ|'
                      r'\b(dinner|breakfast|lunch|meal|dish|dishes|cuisine|food|crab|sashimi|kaiseki|steak|menu|course|buffet|dessert|cake|sweets)\b', re.I)
PROMO_ALT = re.compile(r'クーポン|キャンペーン|プラン|ポイント|アワード|受賞|口コミ|ランキング|バナー|ロゴ|\b(award|badge|logo|banner|coupon|campaign|ranking|promo|plan)\b', re.I)
PROP_ALT = re.compile(r'外観|客室|部屋|ロビー|露天|大浴場|玄関|エントランス|館内|\b(exterior|room|lobby|bath|onsen|entrance|facade|building)\b', re.I)

def analyse(data, kind='stay', name='', alt='', html_wh=None):
    """-> dict(w,h,bytes,entropy,colours,flags[],soft[])"""
    flags, soft = [], []
    r = dict(bytes=len(data) if data is not None else None, w=None, h=None, entropy=None, colours=None)
    if html_wh and html_wh[0]: r['w'], r['h'] = html_wh
    if data is not None:
        if len(data) < MIN_BYTES: flags.append(f'tiny-bytes<{MIN_BYTES}')
        try:
            from PIL import Image
            im = Image.open(io.BytesIO(data)); im.load(); r['w'], r['h'] = im.size
            sm = im.convert('RGB').resize((96, 96))
            r['entropy'] = round(im.convert('L').resize((128, 128)).entropy(), 2)
            r['colours'] = len(set(sm.get_flattened_data() if hasattr(sm, "get_flattened_data") else sm.getdata()))
            if r['entropy'] < 5.0: flags.append('flat/logo-entropy')
            if r['colours'] < 350: flags.append('few-colours')
            soft += colour_soft(sm, r)
        except Exception:
            flags.append('undecodable')
    w, h = r['w'], r['h']
    if w:
        minw = STAY_MIN_W if kind == 'stay' else DINING_MIN_W
        if w <= THUMB_MAX_W: flags.append(f'tiny-thumb{w}x{h}')
        elif w < minw: flags.append(f'narrow<{minw}({w}px)')
        if h and not (0.45 <= w / h <= 3.3): flags.append(f'aspect{w / h:.2f}')
        if h and max(w, h) <= 320 and 0.85 <= w / h <= 1.18 and (r['colours'] is None or r['colours'] < 1500): flags.append(f'badge-dims{w}x{h}')
    if BAD_NAME.search(name): flags.append('name-promo')
    if alt:
        if PROMO_ALT.search(alt): flags.append('alt-promo')
        elif kind == 'stay' and FOOD_ALT.search(alt) and not PROP_ALT.search(alt): flags.append('alt-food')
    r['flags'], r['soft'] = flags, soft
    return r

def colour_soft(sm, r):
    """Cheap heuristics, review-only: warm/saturated close-up (food-like) and text-heavy graphics."""
    import colorsys
    px = list(sm.get_flattened_data() if hasattr(sm, "get_flattened_data") else sm.getdata()); n = len(px); warm = blue = 0; sat = 0.0
    for R, G, B in px:
        hh, s, v = colorsys.rgb_to_hsv(R / 255, G / 255, B / 255); sat += s
        if s > 0.35 and v > 0.25 and (hh < 0.14 or hh > 0.95): warm += 1
        if 0.5 < hh < 0.72 and s > 0.15 and v > 0.4: blue += 1
    out = []
    if warm / n > 0.45 and blue / n < 0.03 and sat / n > 0.33: out.append('maybe-food')
    return out

def html_attr_dims(tag):
    w = re.search(r'width="(\d+)"', tag); h = re.search(r'height="(\d+)"', tag)
    return (int(w.group(1)) if w else None, int(h.group(1)) if h else None)

def load_bytes(src, root, media_root, fetch):
    """local file -> bytes ; else live (cached) when fetch -> bytes ; else None"""
    rel = src.lstrip('/')
    for base in filter(None, [media_root and Path(media_root), Path(root)]):
        p = (base / Path(rel).name) if media_root and base == Path(media_root) else base / rel
        if p.exists(): return p.read_bytes(), 'local'
    cp = CACHE / hashlib.sha1(rel.encode()).hexdigest()[:2] / Path(rel).name
    if cp.exists(): return cp.read_bytes(), 'cache'
    if not fetch: return None, 'not-local'
    import requests
    time.sleep(0.15)
    try:
        r = requests.get(LIVE + '/' + rel, timeout=20, headers={'User-Agent': 'bokenjapan-photo-check/1.0 (read-only)'})
        if r.status_code != 200: return None, f'http{r.status_code}'
        cp.parent.mkdir(parents=True, exist_ok=True); cp.write_bytes(r.content)
        return r.content, 'live'
    except Exception as e: return None, type(e).__name__

CARD = re.compile(r'<li><a href="([^"]*)"><p class="place-name">([^<]*)</p>(<img class="thumb"[^>]*>)?', re.S)

def scan(root, pref, kind, media_root, fetch):
    rows, md5 = [], collections.defaultdict(list)
    root = Path(root)
    for sec in (['stay'] if kind in ('stay', 'all') else []) + (['eat'] if kind in ('dining', 'all') else []):
        for f in sorted((root / pref).glob(f'*/{sec}/**/index.html')):
            t = f.read_text(encoding='utf-8', errors='replace')
            town = f.relative_to(root / pref).parts[0]
            seen_page = set()
            for m in CARD.finditer(t):
                tag = m.group(3)
                if not tag: continue
                src = re.search(r'src="([^"]+)"', tag).group(1); alt = H.unescape(re.search(r'alt="([^"]*)"', tag).group(1) if 'alt="' in tag else '')
                if src in seen_page: continue
                seen_page.add(src)
                data, how = load_bytes(src, root, media_root, fetch)
                k = 'stay' if sec == 'stay' else 'dining'
                r = analyse(data, k, src, alt, html_attr_dims(tag))
                r.update(town=town, kind=k, page=str(f.relative_to(root)), src=src, name=H.unescape(m.group(2)), alt=alt, file=how)
                if data is not None: md5[hashlib.md5(data).hexdigest()].append(r)
                rows.append(r)
    for h, rs in md5.items():
        if len({x['src'] for x in rs}) > 1:   # same bytes under different file names (same file shown on several pages is fine, e.g. labelled neighbour stays)
            for x in rs: x['flags'].append(f'dup-image(x{len({y["src"] for y in rs})})')
    return rows

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='*'); ap.add_argument('--kind', default='stay', choices=['stay', 'dining', 'all'])
    ap.add_argument('--report', action='store_true'); ap.add_argument('--root'); ap.add_argument('--pref', action='append', default=[])
    ap.add_argument('--media-root'); ap.add_argument('--fetch', action='store_true'); ap.add_argument('--csv'); ap.add_argument('--json')
    ap.add_argument('--soft', action='store_true', help='also list soft (review) flags')
    A = ap.parse_args()
    if A.report:
        if not A.root or not A.pref: ap.error('--report needs --root and --pref')
        rows = []
        for p in A.pref: rows += scan(A.root, p, A.kind, A.media_root, A.fetch)
    else:
        rows = []
        for f in A.files:
            d = Path(f).read_bytes(); r = analyse(d, A.kind if A.kind != 'all' else 'stay', Path(f).name)
            r.update(file=f, src=f, town='', name='', alt='', page='', kind=A.kind); rows.append(r)
    bad = [r for r in rows if r['flags']]
    for r in rows:
        if r['flags'] or (A.soft and r['soft']):
            print(f"{'FLAG' if r['flags'] else 'soft'}  {r.get('town', '')}  {r['src']}  {r['w']}x{r['h']}  {r['bytes']}B  {','.join(r['flags'] + r['soft'])}  {r['name'][:30]}")
    c = collections.Counter(f.split('(')[0].split('<')[0].rstrip('0123456789x') for r in rows for f in r['flags'])
    print(f'checked {len(rows)} images, flagged {len(bad)}; by flag: {dict(c)}; soft maybe-food {sum("maybe-food" in r["soft"] for r in rows)}; '
          f'no pixel data (attrs only) {sum(1 for r in rows if r["bytes"] is None)}', file=sys.stderr)
    if A.csv:
        with open(A.csv, 'w', newline='', encoding='utf-8') as fh:
            w = csv.writer(fh); w.writerow(['town', 'kind', 'page', 'src', 'name', 'alt', 'w', 'h', 'bytes', 'entropy', 'colours', 'flags', 'soft', 'file'])
            for r in rows: w.writerow([r.get('town'), r.get('kind'), r.get('page'), r['src'], r.get('name'), r.get('alt'), r['w'], r['h'], r['bytes'], r['entropy'], r['colours'], ';'.join(r['flags']), ';'.join(r['soft']), r.get('file')])
    if A.json: json.dump(rows, open(A.json, 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__':
    main()
