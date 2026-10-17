#!/usr/bin/env python3
"""Second-chance photos for Sights/Do cards that still have only a photo_search comment.

  commons_sights.py --tree TREE --pref tottori --bbox S,W,N,E [--town a,b] [--dry-run] [--limit N]
Wikidata search on the card's English name -> entity must have coordinates inside the bbox (prefecture)
and a P18 image -> Commons file (>=400px, >=5KB gate) -> media/<town>-sc-<Qid>.webp.
Credit comment carries author · licence · Source file page.  Cards that stay photo-less keep their comment.
"""
import argparse, re, os, sys, json, hashlib, time, html as H, urllib.parse
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osm_dining as O
O.S.headers['User-Agent'] = 'BokenJapanBot/1.0 (+https://bokenjapan.com; sights photo check; contact via site)'
API = 'https://www.wikidata.org/w/api.php'; CAPI = 'https://commons.wikimedia.org/w/api.php'

def jget(url, **p):
    for i in range(3):
        try:
            time.sleep(0.6); r = O.S.get(url, params=p, timeout=20)
            if r.status_code == 200: return r.json()
        except Exception: time.sleep(2)
    return {}

def tokens(s): return set(re.findall(r'[a-z0-9]+', s.lower())) - {'the', 'of', 'no', 'in', 'and', 'park', 'town', 'city', 'museum', 'hall', 'onsen', 'shrine', 'temple'}

def ja_name(li):
    """Japanese spot name from the cached tottori-guide page (h1) of this card, if any."""
    m = re.search(r'<li><a href="([^"]+)"', li)
    if not m or 'tottori-guide.jp' not in m.group(1): return None
    import hashlib
    f = Path('/workspace/p1/scratch/sight-cache') / (hashlib.sha1(m.group(1).encode()).hexdigest()[:16] + '.html')
    if not f.exists(): return None
    h = re.search(r'<h1>([^<]+)</h1>', f.read_text(errors='replace'))
    return h.group(1).strip() if h else None

def find_entity(name, bbox, lang='en'):
    d = jget(API, action='wbsearchentities', search=name, language=lang, limit=5, format='json')
    for e in d.get('search', []):
        lab = e.get('label', '')
        if lang == 'en':
            if tokens(name) and not (tokens(name) <= tokens(lab) or tokens(lab) <= tokens(name)) and name.lower() not in lab.lower(): continue
        elif not (name == lab or name in lab or lab in name): continue
        c = jget(API, action='wbgetentities', ids=e['id'], props='claims', format='json').get('entities', {}).get(e['id'], {}).get('claims', {})
        try:
            co = c['P625'][0]['mainsnak']['datavalue']['value']; lat, lon = co['latitude'], co['longitude']
        except Exception: continue
        if not (bbox[0] <= lat <= bbox[2] and bbox[1] <= lon <= bbox[3]): continue
        if 'P18' not in c: continue
        return e['id'], c['P18'][0]['mainsnak']['datavalue']['value']
    return None, None

def commons_meta(fn):
    d = jget(CAPI, action='query', titles='File:' + fn, prop='imageinfo', iiprop='extmetadata|url', iiurlwidth=900, format='json')
    for p in d.get('query', {}).get('pages', {}).values():
        ii = (p.get('imageinfo') or [{}])[0]; em = ii.get('extmetadata', {})
        art = re.sub(r'<[^>]+>', '', em.get('Artist', {}).get('value', '') or '').strip() or 'Unknown author'
        lic = em.get('LicenseShortName', {}).get('value', '') or 'see file page'
        return ii.get('thumburl') or ii.get('url'), H.unescape(art)[:80], lic
    return None, None, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tree', required=True); ap.add_argument('--pref', required=True); ap.add_argument('--bbox', required=True)
    ap.add_argument('--town', default=''); ap.add_argument('--kinds', default='see,do'); ap.add_argument('--limit', type=int, default=0); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(); bbox = [float(x) for x in a.bbox.split(',')]
    tree = Path(a.tree); got = tried = 0; seen = set()
    towns = [t for t in a.town.split(',') if t] or sorted(p.name for p in (tree / a.pref).iterdir() if p.is_dir())
    for town in towns:
        for kind in a.kinds.split(','):
            f = tree / a.pref / town / kind / 'index.html'
            if not f.exists(): continue
            t = f.read_text(encoding='utf-8'); o = t
            def card(m):
                nonlocal got, tried
                li = m.group(0)
                if 'class="thumb"' in li or 'photo_search' not in li or 'commons-search' in li: return li
                if a.limit and tried >= a.limit: return li
                nm = H.unescape(re.search(r'place-name">([^<]*)', li).group(1)); tried += 1
                jn = ja_name(li)
                q, fn = find_entity(jn, bbox, 'ja') if jn else (None, None)
                if not q: q, fn = find_entity(re.sub(r'\s*[\(（].*', '', nm).strip(), bbox)
                res = None
                if q and q not in seen:
                    url, art, lic = commons_meta(fn)
                    if url:
                        d, r = O.get(url, maxb=10_000_000)
                        im, bad = O.img_ok(d) if d else (None, str(r))
                        if im is not None:
                            dest = tree / 'media' / f'{town}-sc-{q}.webp'
                            if a.dry_run: res = (dest.name, art, lic)
                            else:
                                ok, _ = O.save_webp(im, dest)
                                if ok: res = (dest.name, art, lic)
                if res:
                    got += 1; seen.add(q)
                    page = 'https://commons.wikimedia.org/wiki/File:' + urllib.parse.quote(fn.replace(' ', '_'))
                    img = f'<img class="thumb" src="/media/{res[0]}" alt="{H.escape(nm, quote=True)}" loading="lazy">'
                    li = li.replace('</p></a>', '</p>' + img + '</a>' + f'<!-- photo-credit: {res[1]} · {res[2]} · Source {page} -->', 1)
                else:
                    li = li.replace('</li>', '<!-- commons-search: no Wikidata/Commons image with coordinates inside the prefecture -->' + '</li>', 1)
                print(town, kind, nm[:40], '->', res[0] if res else 'none', flush=True)
                return li
            t = re.sub(r'<li><a href=.*?</li>', card, t, flags=re.S)
            if t != o and not a.dry_run: f.write_text(t, encoding='utf-8')
    print('SUMMARY', got, 'of', tried)
main()
