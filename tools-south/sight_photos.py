#!/usr/bin/env python3
"""Add photos to photo-less Sights/Do cards from the card's own linked page.

  sight_photos.py --tree TREE --pref tottori [--town a,b] [--kinds see,do] [--limit N] [--dry-run]

Order: tottori-guide.jp spot page (images inside #ContsBox = the spot's own content), else the
official page's og:image / first large <img>.  Gate: >=5KB, >=400px wide, entropy/colour checks, logo
patterns rejected, one md5 -> one card.  Output media/<town>-sp-<key>.webp (560px, q25).
Cards that find nothing get a photo_search comment (once) and stay in their town.
Every photo gets  <!-- photo-credit: author · Source url -->.  Nothing is deleted.
"""
import argparse, re, os, sys, json, hashlib, time, urllib.parse
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import osm_dining as O
from bs4 import BeautifulSoup

O.S.headers['User-Agent'] = 'BokenJapanBot/1.0 (+https://bokenjapan.com; sights photo check)'
CACHE = Path('/workspace/p1/scratch/sight-cache'); CACHE.mkdir(parents=True, exist_ok=True)
EXTRA_BAD = re.compile(r'ogp|_new20\d\d/img|/img/common|noimage|no_image|blank|loading|qr|map', re.I)
_last = {}

def polite(url, gap=1.2):
    h = urllib.parse.urlparse(url).netloc
    w = _last.get(h, 0) + gap - time.time()
    if w > 0: time.sleep(w)
    _last[h] = time.time()

def fetch(url, maxb=6_000_000):
    for i in range(3):
        polite(url, 1.2 + 3 * i)
        d, r = O.get(url, maxb=maxb)
        if d is not None or isinstance(r, int): break
    return d, r

def page_html(url):
    f = CACHE / (hashlib.sha1(url.encode()).hexdigest()[:16] + '.html')
    if f.exists(): return f.read_text(errors='replace'), url
    d, r = fetch(url, maxb=3_000_000)
    if d is None: return None, str(r)
    enc = getattr(r, 'encoding', None) or 'utf-8'
    t = d.decode(enc, errors='replace'); f.write_text(t); return t, r.url

def candidates(url, html, base):
    soup = BeautifulSoup(html, 'lxml')
    out = []
    if 'tottori-guide.jp' in url:
        box = soup.find(id='ContsBox')
        if box:
            for im in box.find_all('img')[:3]:
                s = im.get('src') or ''
                if s and not s.startswith('data:'): out.append(('spot', urllib.parse.urljoin(base, s)))
        return out
    for k, u in O.og_candidates(html, base):
        if not EXTRA_BAD.search(urllib.parse.urlparse(u).path): out.append((k, u))
    return out[:5]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tree', required=True); ap.add_argument('--pref', required=True)
    ap.add_argument('--town', default=''); ap.add_argument('--kinds', default='see,do')
    ap.add_argument('--retry', action='store_true', help='re-try cards whose photo_search failed on a transient error'); ap.add_argument('--limit', type=int, default=0); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    tree = Path(a.tree); media = tree / 'media'
    seen_md5 = set(); done = 0; stats = {'photo': 0, 'none': 0, 'skipped': 0}
    towns = [t for t in a.town.split(',') if t] or sorted(p.name for p in (tree / a.pref).iterdir() if p.is_dir())
    for town in towns:
        for kind in a.kinds.split(','):
            f = tree / a.pref / town / kind / 'index.html'
            if not f.exists(): continue
            t = f.read_text(encoding='utf-8'); o = t
            if a.retry:
                t = re.sub(r'<!-- photo_search: tried page images of [^>]*?(?:ConnectTimeout|ReadTimeout|ssl|ConnectionError|ChunkedEncodingError|page:5\d\d)[^>]*-->', '', t)
            def card(m):
                nonlocal done
                li = m.group(0)
                if 'class="thumb"' in li or 'photo_search' in li: return li
                if a.limit and done >= a.limit: return li
                href = re.search(r'<li><a href="([^"]+)"', li).group(1)
                nm = re.search(r'place-name">([^<]*)', li)
                if not nm or not href.startswith('http'): return li
                done += 1
                key = (re.search(r'/view/(\d+)', href) or [None, None])[1] or hashlib.sha1(href.encode()).hexdigest()[:8]
                dest = media / f'{town}-sp-{key}.webp'
                html, base = page_html(href)
                why, photo = [], None
                if html is None: why.append(f'page:{base}')
                else:
                    best = None
                    for k, u in candidates(href, html, base):
                        d, r = fetch(u, maxb=8_000_000)
                        if d is None: why.append(f'{k}:{r}'); continue
                        im, bad = O.img_ok(d)
                        if im is None: why.append(f'{k}:{bad}'); continue
                        md = hashlib.md5(d).hexdigest()
                        if md in seen_md5: why.append(f'{k}:dup'); continue
                        if best is None or im.width * im.height > best[0].width * best[0].height: best = (im, u, md)
                    if best:
                        if a.dry_run: photo = (best[1], None)
                        else:
                            ok, size = O.save_webp(best[0], dest)
                            if ok: seen_md5.add(best[2]); photo = (best[1], dest.name)
                            else: dest.unlink(missing_ok=True); why.append('webp<5KB')
                if photo:
                    stats['photo'] += 1
                    author = '公益社団法人鳥取県観光連盟' if 'tottori-guide.jp' in href else 'Official website'
                    alt = nm.group(1)
                    img = f'<img class="thumb" src="/media/{photo[1]}" alt="{alt}" loading="lazy">'
                    cm = f'<!-- photo-credit: {author} · Source {href} -->'
                    li = li.replace('</p></a>', '</p>' + img + '</a>' + cm, 1) if 'place-name">' in li else li
                    # keep the credit comment next to the other comments
                else:
                    stats['none'] += 1
                    cm = f'<!-- photo_search: tried page images of {href}; {";".join(why[:3]) or "no-image-found"}; Commons/municipal search pending -->'
                    li = li.replace('</li>', cm + '</li>', 1)
                print(town, kind, nm.group(1)[:40], '->', photo[1] if photo else ('none ' + ';'.join(why[:2])), flush=True)
                return li
            t = re.sub(r'<li><a href=.*?</li>', card, t, flags=re.S)
            if t != o and not a.dry_run: f.write_text(t, encoding='utf-8')
    print('SUMMARY', stats)

if __name__ == '__main__': main()
