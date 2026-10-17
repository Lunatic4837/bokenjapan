#!/usr/bin/env python3
"""stay_photo_fix.py - find larger / better photos for stay cards from the card's own listing page (Ikkyu / Jalan), no new sources.

  stay_photo_fix.py cands --tree T --pref tottori [--town X] [--only narrow,tiny,food,...|--all] [--report stay_flags.json]
      for every stay card whose thumb is flagged (photo_check report) download candidate gallery images from the listing page
      (Jalan pict4L = 600px, Ikkyu gallery w=900), score similarity to the current thumb (dHash) and write
      <work>/cands.json plus contact sheets <work>/sheets/<town>-<n>.jpg for visual review.
  stay_photo_fix.py auto --tree T ...      upsize: where a candidate IS the current photo (dHash match) swap in the larger version
  stay_photo_fix.py pick --tree T --choices choices.json     explicit replacement: {"/media/old.webp": "<cand file name>"}  (food/promo/badge cases)
Replacement files get a new name (<stem>-r.webp, never overwriting or deleting the old media), 560px wide webp, >=5KB; the <img> src/width/height
in every page of the pref are updated; photo-credit comments stay as they are (same listing page).
"""
import argparse, hashlib, html as H, io, json, re, sys, time
from pathlib import Path
import requests
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent))
import photo_check as PC

WORK = Path('/workspace/p1/scratch/stay-fix'); HDR = {'User-Agent': 'Mozilla/5.0 (compatible; bokenjapan-photo-check/1.0; read-only)'}
CARD = re.compile(r'<li><a href="([^"]*)"><p class="place-name">([^<]*)</p>(<img class="thumb"[^>]*>)')

def fetch(u, tries=2):
    for _ in range(tries):
        try:
            r = requests.get(u, headers=HDR, timeout=25)
            if r.status_code == 200: return r.content
            if r.status_code in (403, 404, 410): return None
        except Exception: pass
        time.sleep(6)
    return None

def dhash(im, crop_ratio=None):
    im = im.convert('L')
    if crop_ratio:
        w, h = im.size
        if w / h > crop_ratio: nw = int(h * crop_ratio); im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
        else: nh = int(w / crop_ratio); im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    px = list(im.resize((9, 8)).get_flattened_data() if hasattr(im, 'get_flattened_data') else im.resize((9, 8)).getdata())
    return [1 if px[r * 9 + c] > px[r * 9 + c + 1] else 0 for r in range(8) for c in range(8)]
def dist(a, b): return sum(x != y for x, y in zip(a, b))

def candidate_urls(listing):
    time.sleep(2.0)   # polite: listing sites rate-limit bursts
    data = fetch(listing, tries=3)
    if not data: return []
    t = data.decode('utf-8', errors='replace')
    if 'ikyu.com' in listing:
        ids = re.findall(r'https://www\.img-ikyu\.com/contents/common/image/acc3/\d+/\d+/org/\d+\.jpg', t)
        og = re.findall(r'og:image"[^>]*content="([^"?]+)', t)
        urls = [u + '?auto=compress,format&lossless=0&w=900' for u in dict.fromkeys(ids)] + [u + '?auto=compress,format&lossless=0&w=900' for u in og if 'img-ikyu' in u and '/guide/' in u]
    else:
        urls = list(dict.fromkeys(re.findall(r'https://cdn\.jalan\.jp/jalan/images/pict4L/Y\d/Y\d+/Y\d+\.jpg', t)))
    return list(dict.fromkeys(urls))[:10]

def stay_cards(tree, pref, town=None):
    out = []
    for f in sorted(Path(tree).glob(f'{pref}/*/stay/index.html')):
        tw = f.parts[-3]
        if town and tw != town: continue
        for href, name, tag in CARD.findall(f.read_text(encoding='utf-8')):
            m = re.search(r'src="([^"]+)"', tag)
            if m and re.search(r'ikyu\.com|jalan\.net', href): out.append(dict(town=tw, href=href, name=H.unescape(name), src=m.group(1), alt=re.search(r'alt="([^"]*)"', tag).group(1)))
    seen, res = set(), []
    for c in out:
        if (c['town'], c['src']) not in seen: seen.add((c['town'], c['src'])); res.append(c)
    return res

def cur_image(src):
    p = PC.CACHE / hashlib.sha1(src.lstrip('/').encode()).hexdigest()[:2] / Path(src).name
    return Image.open(p) if p.exists() else None

def cmd_cands(A):
    flagged = None
    if A.report and not A.all:
        flagged = {r['src'] for r in json.load(open(A.report)) if r['flags']}
        if A.extra: flagged |= set(json.load(open(A.extra)))
    (WORK / 'cands').mkdir(parents=True, exist_ok=True); (WORK / 'sheets').mkdir(exist_ok=True)
    res = []
    for c in stay_cards(A.tree, A.pref, A.town):
        if A.only_src and c['src'] not in A.only_src: continue
        if flagged is not None and not A.only_src and c['src'] not in flagged: continue
        cur = cur_image(c['src']); cid = hashlib.sha1((c['town'] + c['src']).encode()).hexdigest()[:8]
        ch = None
        if cur is not None: w, h = cur.size; ch = (dhash(cur), w / h)
        cs = []
        def grab(ku):
            k, u = ku; data = fetch(u, tries=1)
            if not data: return None
            try: im = Image.open(io.BytesIO(data)); im.load()
            except Exception: return None
            if im.width < A.min_w or len(data) < PC.MIN_BYTES: return None
            fn = f'{cid}-{k}.jpg'; (WORK / 'cands' / fn).write_bytes(data)
            return dict(file=fn, url=u, w=im.width, h=im.height, d=dist(ch[0], dhash(im, ch[1])) if ch else None)
        with ThreadPoolExecutor(5) as ex:
            cs = [x for x in ex.map(grab, list(enumerate(candidate_urls(c['href'])[:8]))) if x]
        c.update(id=cid, cur_w=cur.width if cur else 0, cur_bytes=(PC.CACHE / hashlib.sha1(c['src'].lstrip('/').encode()).hexdigest()[:2] / Path(c['src']).name).stat().st_size if cur else 0, cands=cs, match=min((x for x in cs if x['d'] is not None), key=lambda x: x['d'], default=None))
        res.append(c); print(c['town'], c['name'][:20], len(cs), 'cands; best dHash', c['match'] and c['match']['d'], flush=True)
    if A.only_src and (WORK / 'cands.json').exists():   # merge into the earlier run
        old = {c['src']: c for c in json.load(open(WORK / 'cands.json'))}; old.update({c['src']: c for c in res}); res_all = list(old.values())
    else: res_all = res
    json.dump(res_all, open(WORK / 'cands.json', 'w'), ensure_ascii=False, indent=1)
    for c in res:   # contact sheet per card: current + candidates
        tiles = ([('cur', cur_image(c['src']))] if cur_image(c['src']) else []) + [(str(i), Image.open(WORK / 'cands' / x['file'])) for i, x in enumerate(c['cands'])]
        if not tiles: continue
        sh = Image.new('RGB', (min(6, len(tiles)) * 210, ((len(tiles) + 5) // 6) * 175), 'white'); d = ImageDraw.Draw(sh)
        for i, (lab, im) in enumerate(tiles):
            im = im.convert('RGB'); im.thumbnail((204, 150)); x, y = (i % 6) * 210, (i // 6) * 175; sh.paste(im, (x + 2, y + 2)); d.text((x + 4, y + 154), lab, fill='black')
        sh.save(WORK / 'sheets' / f"{c['town']}-{c['id']}.jpg", quality=65)

def save_webp(data, dest):
    im = Image.open(io.BytesIO(data)).convert('RGB')
    if im.width > 560: im = im.resize((560, round(im.height * 560 / im.width)), Image.LANCZOS)
    for q in (35, 45, 55, 70):
        im.save(dest, 'WEBP', quality=q, method=6)
        if dest.stat().st_size >= PC.MIN_BYTES: break
    return im.size

def apply_swap(tree, pref, old_src, cand_file, cid_meta=None):
    tree = Path(tree); stem = Path(old_src).stem
    n = 1
    while (tree / 'media' / f'{stem}-r{n if n > 1 else ""}.webp').exists(): n += 1
    new = f'{stem}-r{n if n > 1 else ""}.webp'
    w, h = save_webp((WORK / 'cands' / cand_file).read_bytes(), tree / 'media' / new)
    pat = re.compile(r'(<img[^>]*?)src="' + re.escape(old_src) + r'"([^>]*?)width="\d+" height="\d+"')
    touched = 0
    for f in (tree / pref).rglob('index.html'):
        t = f.read_text(encoding='utf-8')
        t2 = pat.sub(lambda m: f'{m.group(1)}src="/media/{new}"{m.group(2)}width="{w}" height="{h}"', t)
        if t2 != t: f.write_text(t2, encoding='utf-8'); touched += 1
    return new, touched

def cmd_auto(A, thr=14):
    res = json.load(open(WORK / 'cands.json')); done = skipped = 0
    extra = set(json.load(open(A.extra))) if A.extra else set()   # food/promo thumbs are replaced via `pick`, never upsized
    for c in res:
        m = c.get('match')
        if c['src'] in extra: skipped += 1; continue
        if not m or m['d'] > thr or not (c['cur_w'] < 560 or c['cur_bytes'] < PC.MIN_BYTES): skipped += 1; continue
        new, t = apply_swap(A.tree, A.pref, c['src'], m['file']); done += 1; print('upsized', c['town'], c['src'], '->', new, f'(d={m["d"]}, {t} pages)')
    print(f'upsized {done}, left {skipped}')

def cmd_pick(A):
    ch = json.load(open(A.choices)); res = {c['src']: c for c in json.load(open(WORK / 'cands.json'))}
    for src, idx in ch.items():
        c = res[src]; f = c['cands'][int(idx)]['file']
        new, t = apply_swap(A.tree, A.pref, src, f); print('replaced', c['town'], c['name'][:18], src, '->', new, f'({t} pages)')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd', choices=['cands', 'auto', 'pick']); ap.add_argument('--tree', required=True); ap.add_argument('--pref', required=True)
    ap.add_argument('--town'); ap.add_argument('--min-w', type=int, default=560, help='min candidate width (use 280 when a listing only has 300px photos)'); ap.add_argument('--report'); ap.add_argument('--all', action='store_true'); ap.add_argument('--only-src', action='append', default=[], help='restrict cands to these thumb srcs (merge into cands.json)'); ap.add_argument('--choices'); ap.add_argument('--extra', help='json list of extra thumb srcs (e.g. food/promo found by eye)')
    A = ap.parse_args()
    {'cands': cmd_cands, 'auto': cmd_auto, 'pick': cmd_pick}[A.cmd](A)

if __name__ == '__main__':
    main()
