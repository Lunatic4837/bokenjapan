#!/usr/bin/env python3
"""osm_dining.py - lean Tabelog-free dining collector for bokenjapan.com (P1 Rural South).

  python3 osm_dining.py <pref> <slug> [--tree DIR] [--need N] [--photo-limit M] [--no-photos] [--bbox S,W,N,E] [--refresh]
  e.g. python3 osm_dining.py tottori yonago --need 77

Sources ONLY: OpenStreetMap via the public Overpass API (ODbL; credit lives in the page footer note), the venue's own
official website (og:image / first large image), Wikimedia Commons / Wikidata image of the venue. Never Tabelog, Hot Pepper,
Gurunavi, Google, TripAdvisor or any paid API.  Overpass etiquette: one query at a time (file lock), >=4 s gap, UA, retry/backoff,
all responses cached on disk (gzip), photo results cached per OSM id.

Output: <out>/<pref>/<slug>.json (default /workspace/p1/scratch/osm-dining/out) + <out>/media/<town>-osm-<osmid>.webp
(560px wide, q25).  Each card: osmid, osm_url, name_ja, name_en, name_en_src, category, cuisine, addr, phone, website,
opening_hours, lat, lon, photo{file,credit,source} | null, photo_search{tried,result,notes}, selected(bool).
"""
import argparse, fcntl, gzip, hashlib, io, json, os, re, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import requests
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bjlib as L

UA = 'BokenJapanBot/1.0 (+https://bokenjapan.com; OSM dining collector; one Overpass query at a time; ODbL)'
OUT = Path(os.environ.get('OSM_DINING_OUT', '/workspace/p1/scratch/osm-dining/out'))
CACHE = Path(os.environ.get('OSM_DINING_CACHE', '/workspace/p1/scratch/osm-dining/cache'))
ENDPOINTS = ['https://overpass-api.de/api/interpreter', 'https://overpass.kumi.systems/api/interpreter']
MIN_GAP = 4.0
AMENITY = 'restaurant|cafe|fast_food|bar|pub|izakaya|food_court|biergarten|ice_cream'
SHOP = 'bakery|confectionery|pastry'

BLOCKED = re.compile(r'(tabelog|hotpepper|gnavi|gurunavi|retty|tripadvisor|rakuten|google\.|goo\.gl|g\.page|yelp|jalan\.net|ikyu|ekiten|navitime|mapion|'
                     r'facebook|fb\.com|fb\.me|instagram|twitter\.com|(^|\.)x\.com|t\.co|line\.me|lin\.ee|tiktok|youtube|youtu\.be|ameblo|note\.com|linktr\.ee|'
                     r'peraichi|wikipedia|wikidata|yahoo\.co\.jp|amazon|uber|demae-can|menu\.jp|favy|hitosara|ozmall|opentable|tablecheck|goo-net)', re.I)
BAD_IMG = re.compile(r'logo|banner|favicon|icon|sprite|header|noimage|no_image|no-image|dummy|default|common/ogp|btn_|button|/nav|spacer|1x1|blank|'
                     r'placeholder|emblem|badge|avatar|qr|map\.|line_|sns|share|ubereats|demae|wolt|menu\.jp|coupon|campaign|tabelog|hotpepper|gnavi|award', re.I)
CHAIN_RE = re.compile('マクドナルド|スターバックス|すき家|吉野家|松屋|ガスト|サイゼリヤ|ジョナサン|バーミヤン|くら寿司|スシロー|はま寿司|かっぱ寿司|ミスタードーナツ|'
                      'ドトール|コメダ|タリーズ|モスバーガー|ケンタッキー|ロッテリア|ココス|ジョイフル|丸亀製麺|はなまる|幸楽苑|日高屋|リンガーハット|'
                      'ココイチ|CoCo壱|餃子の王将|大戸屋|やよい軒|びっくりドンキー|ほっともっと|丸源|焼肉きんぐ|牛角|白木屋|魚民|笑笑|和民|鳥貴族|山岡家|8番らーめん|'
                      'サーティワン|ドミノ|ピザーラ|ピザハット|ミスド|セブン|ローソン|ファミリーマート', re.I)

def log(*a): print(*a, file=sys.stderr, flush=True)
def hkey(s): return hashlib.sha1(s.encode()).hexdigest()[:16]

# ------------------------------------------------------------ Overpass (serial, cached, backoff)
def overpass(ql, tag, refresh=False, ttl=30 * 86400):
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f'op-{tag}-{hkey(ql)}.json.gz'
    if f.exists() and not refresh and time.time() - f.stat().st_mtime < ttl:
        return json.load(gzip.open(f, 'rt'))
    with open(CACHE / '.overpass.lock', 'w') as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try: last = float((CACHE / '.last').read_text())
        except Exception: last = 0
        if MIN_GAP - (time.time() - last) > 0: time.sleep(MIN_GAP - (time.time() - last))
        delay, err = 10, None
        for attempt in range(6):
            ep = ENDPOINTS[0 if attempt < 4 else 1]
            try:
                r = requests.post(ep, data={'data': ql}, headers={'User-Agent': UA}, timeout=200)
                if r.status_code == 200:
                    d = r.json()
                    if 'runtime error' in d.get('remark', '') and not d.get('elements'): raise RuntimeError(d['remark'])
                    tmp = f.with_suffix('.tmp'); json.dump(d, gzip.open(tmp, 'wt'), ensure_ascii=False); tmp.rename(f)
                    (CACHE / '.last').write_text(str(time.time()))
                    return d
                err = f'HTTP {r.status_code}'
                wait = int(r.headers['Retry-After']) if r.headers.get('Retry-After', '').isdigit() else delay
            except Exception as e:
                err, wait = str(e)[:100], delay
            log(f'  overpass retry {attempt + 1} ({err}); sleep {wait}s'); time.sleep(wait); delay = min(delay * 2, 120)
        raise RuntimeError(f'Overpass failed: {err}')

def build_query(pref, slug, bbox=None):
    sel = f'nwr["amenity"~"^({AMENITY})$"]["name"]{{A}};nwr["shop"~"^({SHOP})$"]["name"]{{A}};'
    if bbox:
        s, w, n, e = bbox
        return '[out:json][timeout:120];(' + sel.replace('{A}', f'({s},{w},{n},{e})') + ');out tags center;'
    pj, tj = L.PREF_JA[pref], L.town_ja(pref, slug)
    if not tj: raise SystemExit(f'no Japanese town name for {pref}/{slug} in popmap.json; pass --bbox')
    return (f'[out:json][timeout:120];area["name"="{pj}"]["boundary"="administrative"]["admin_level"="4"]->.p;'
            f'area["name"="{tj}"]["boundary"="administrative"](area.p)->.a;(' + sel.replace('{A}', '(area.a)') + ');out tags center;')

# ------------------------------------------------------------ classification into the site's food-genre tiles
CUISINE = {  # osm cuisine value -> (category, English adjective)
    'ramen': ('noodles', 'Ramen'), 'noodle': ('noodles', 'Noodle'), 'udon': ('noodles', 'Udon'), 'soba': ('noodles', 'Soba'), 'chuka_soba': ('noodles', 'Ramen'),
    'sushi': ('seafood', 'Sushi'), 'seafood': ('seafood', 'Seafood'), 'sashimi': ('seafood', 'Sashimi'), 'fish': ('seafood', 'Fish'), 'kaiten_zushi': ('seafood', 'Conveyor-belt sushi'),
    'crab': ('seafood', 'Crab'), 'eel': ('seafood', 'Eel'), 'unagi': ('seafood', 'Eel'),
    'yakiniku': ('meat', 'Yakiniku'), 'steak_house': ('meat', 'Steak'), 'steak': ('meat', 'Steak'), 'beef': ('meat', 'Beef'), 'barbecue': ('meat', 'Barbecue'),
    'tonkatsu': ('meat', 'Tonkatsu'), 'yakitori': ('meat', 'Yakitori'), 'chicken': ('meat', 'Chicken'), 'pork': ('meat', 'Pork'), 'teppanyaki': ('meat', 'Teppanyaki'),
    'shabu-shabu': ('meat', 'Shabu-shabu'), 'sukiyaki': ('meat', 'Sukiyaki'), 'hot_pot': ('meat', 'Hot pot'), 'kushikatsu': ('meat', 'Kushikatsu'), 'gyudon': ('casual', 'Beef bowl'),
    'italian': ('european', 'Italian'), 'pizza': ('european', 'Pizza'), 'pasta': ('european', 'Pasta'), 'french': ('european', 'French'), 'german': ('european', 'German'),
    'spanish': ('european', 'Spanish'), 'european': ('european', 'European'), 'western': ('european', 'Western-style'), 'yoshoku': ('european', 'Western-style Japanese'),
    'american': ('european', 'American'), 'mediterranean': ('european', 'Mediterranean'),
    'coffee_shop': ('cafe', 'Cafe'), 'cafe': ('cafe', 'Cafe'), 'coffee': ('cafe', 'Coffee'), 'tea': ('cafe', 'Tea'), 'kissaten': ('cafe', 'Kissaten'),
    'curry': ('curry', 'Curry'), 'indian': ('curry', 'Indian'), 'thai': ('chinese-asian', 'Thai'), 'chinese': ('chinese-asian', 'Chinese'),
    'korean': ('chinese-asian', 'Korean'), 'vietnamese': ('chinese-asian', 'Vietnamese'), 'asian': ('chinese-asian', 'Asian'), 'gyoza': ('chinese-asian', 'Gyoza'),
    'dumpling': ('chinese-asian', 'Dumpling'), 'taiwanese': ('chinese-asian', 'Taiwanese'),
    'izakaya': ('izakaya-bars', 'Izakaya'), 'pub': ('izakaya-bars', 'Pub'), 'bar': ('izakaya-bars', 'Bar'), 'sake': ('izakaya-bars', 'Sake'), 'beer': ('izakaya-bars', 'Beer'),
    'ice_cream': ('sweets-bakeries', 'Ice cream'), 'cake': ('sweets-bakeries', 'Cake'), 'bakery': ('sweets-bakeries', 'Bakery'), 'dessert': ('sweets-bakeries', 'Dessert'),
    'donut': ('sweets-bakeries', 'Donut'), 'crepe': ('sweets-bakeries', 'Crepe'), 'sweets': ('sweets-bakeries', 'Sweets'), 'pastry': ('sweets-bakeries', 'Pastry'),
    'japanese_sweets': ('sweets-bakeries', 'Japanese sweets'),
    'burger': ('casual', 'Burger'), 'sandwich': ('casual', 'Sandwich'), 'fast_food': ('casual', 'Fast-food'), 'family_restaurant': ('casual', 'Family'),
    'bento': ('casual', 'Bento'), 'rice_bowl': ('casual', 'Rice bowl'), 'don': ('casual', 'Rice bowl'),
    'regional': ('other-japanese', 'Regional Japanese'), 'japanese': ('other-japanese', 'Japanese'), 'okonomiyaki': ('other-japanese', 'Okonomiyaki'),
    'tempura': ('other-japanese', 'Tempura'), 'kaiseki': ('other-japanese', 'Kaiseki'), 'oden': ('other-japanese', 'Oden'), 'tofu': ('other-japanese', 'Tofu'),
    'takoyaki': ('other-japanese', 'Takoyaki'), 'washoku': ('other-japanese', 'Japanese'),
}
NAME_KW = [  # regex on the venue's own name -> (category, adjective)
    ('ラーメン|らーめん|らぁめん|拉麺|中華そば|ramen', 'noodles', 'Ramen'), ('うどん|udon', 'noodles', 'Udon'), ('そば|蕎麦|soba', 'noodles', 'Soba'),
    ('寿司|鮨|すし|sushi', 'seafood', 'Sushi'), ('海鮮|かに|蟹|うなぎ|鰻|刺身', 'seafood', 'Seafood'),
    ('焼肉|焼き肉|ホルモン|yakiniku', 'meat', 'Yakiniku'), ('焼鳥|焼き鳥|やきとり|yakitori', 'meat', 'Yakitori'), ('ステーキ|steak|とんかつ|しゃぶしゃぶ|すき焼|鉄板', 'meat', 'Meat'),
    ('イタリア|ピザ|pizza|パスタ|pasta|フレンチ|ビストロ|bistro|トラットリア|洋食|ハンバーグ|オムライス', 'european', 'Western-style'),
    ('カフェ|珈琲|コーヒー|喫茶|coffee|cafe|茶房|紅茶', 'cafe', 'Cafe'), ('カレー|curry', 'curry', 'Curry'),
    ('中華|餃子|ぎょうざ|台湾|韓国|タイ料理|ベトナム|インド|chinese|korean|thai', 'chinese-asian', 'Asian'),
    ('居酒屋|酒場|パブ|スナック|酒処|呑|飲み|izakaya|ビアガーデン', 'izakaya-bars', 'Izakaya'),
    ('ケーキ|スイーツ|ベーカリー|bakery|アイス|クレープ|菓子|ドーナツ|パティスリー|ジェラート', 'sweets-bakeries', 'Sweets'),
    ('お好み焼|たこ焼|天ぷら|天婦羅|懐石|割烹|定食|食堂|和食|郷土|会席|丼', 'other-japanese', 'Japanese'),
]
KIND = {'restaurant': 'restaurant', 'cafe': 'cafe', 'fast_food': 'fast-food restaurant', 'bar': 'bar', 'pub': 'pub', 'izakaya': 'izakaya',
        'food_court': 'food court', 'biergarten': 'beer garden', 'ice_cream': 'ice cream shop'}
SHOPKIND = {'bakery': 'bakery', 'confectionery': 'sweets shop', 'pastry': 'pastry shop'}

STRONG = [('ラーメン|らーめん|らぁめん|拉麺|中華そば|ramen', 'noodles', 'Ramen'), ('うどん|udon', 'noodles', 'Udon'), ('そば|蕎麦', 'noodles', 'Soba'),
          ('寿司|鮨|すし|sushi', 'seafood', 'Sushi'), ('焼肉|焼き肉|ホルモン|yakiniku', 'meat', 'Yakiniku'), ('カレー|curry', 'curry', 'Curry'),
          ('カフェ|珈琲|コーヒー|喫茶|coffee|cafe', 'cafe', 'Cafe')]
PROPER = {'Italian', 'French', 'Chinese', 'Korean', 'German', 'Spanish', 'Thai', 'Indian', 'Vietnamese', 'American', 'Japanese', 'Taiwanese', 'European', 'Mediterranean', 'Western-style', 'Regional Japanese', 'Western-style Japanese'}

def classify(tags):
    """-> (category slug, English noun phrase for the description sentence, cuisine list)"""
    am, shop = tags.get('amenity', ''), tags.get('shop', '')
    cu = [c.strip().lower() for c in re.split(r'[;,]', tags.get('cuisine', '')) if c.strip()]
    cat = adj = None
    for c in cu:
        if c in CUISINE: cat, adj = CUISINE[c]; break
    if not cat:
        nm = tags.get('name', '') + ' ' + tags.get('name:en', '')
        for rx, c, a in NAME_KW:
            if re.search(rx, nm, re.I): cat, adj = c, a; break
    nm0 = tags.get('name', '') + ' ' + tags.get('name:en', '')
    if cat in (None, 'chinese-asian', 'other-japanese', 'casual', 'other', 'european'):
        for rx, c, a in STRONG:
            if re.search(rx, nm0, re.I) and c != cat: cat, adj = c, a; break
    if am in ('bar', 'pub', 'biergarten', 'izakaya') and cat in (None, 'other-japanese', 'casual', 'other'): cat = 'izakaya-bars'
    elif am == 'cafe' and cat not in ('cafe', 'sweets-bakeries'): cat = 'cafe'
    elif am == 'ice_cream' or shop in SHOPKIND: cat = 'sweets-bakeries'
    elif am == 'fast_food' and cat in (None, 'other-japanese', 'other'): cat = 'casual'
    if not cat: cat = 'casual' if am in ('fast_food', 'food_court') else 'other'
    kind = SHOPKIND.get(shop) if shop in SHOPKIND else KIND.get(am, 'restaurant')
    adjs = [CUISINE[c][1] for c in cu if c in CUISINE and CUISINE[c][0] == cat] or ([adj] if adj and cat not in ('other', 'casual') else [])
    if not adjs and adj and cat not in ('other', 'casual'): adjs = [adj]
    adjs = list(dict.fromkeys(a for a in adjs if a.lower() not in kind.split()))[:2]
    if kind == 'izakaya': adjs = [a for a in adjs if a != 'Izakaya']
    if shop in SHOPKIND: adjs = [a for a in adjs if a not in ('Sweets', 'Pastry', 'Bakery', 'Confectionery', 'Cake')]
    if kind in ('restaurant', 'fast-food restaurant') and cat == 'cafe': kind = 'cafe'; adjs = [a for a in adjs if a not in ('Cafe', 'Coffee')]
    if kind == 'fast-food restaurant' and cat not in ('casual', 'other'): kind = 'restaurant'
    if kind == 'cafe' and adjs == ['Coffee']: adjs = []
    phrase = ' and '.join([adjs[0]] + [a if a in PROPER else a.lower() for a in adjs[1:]]) if adjs else ''
    noun = (phrase + ' ' + kind).strip()
    return cat, noun[0].upper() + noun[1:], cu

def addr_of(t):
    if t.get('addr:full'): return t['addr:full'].strip()
    return ' '.join(t[k] for k in ('addr:province', 'addr:city', 'addr:suburb', 'addr:quarter', 'addr:neighbourhood', 'addr:block_number', 'addr:housenumber') if t.get(k)).strip()

def area_en(t):
    """Romanised neighbourhood from the venue's own address tags, if any."""
    for k in ('addr:suburb', 'addr:quarter', 'addr:neighbourhood'):
        v = t.get(k)
        if v:
            e = L.romanize(re.sub(r'[0-9０-９]+丁目?$', '', v).strip()) if L.CJK.search(v) else v
            e = re.sub(r'\s+\d.*$', '', e).strip()
            if e and re.fullmatch(r"[A-Za-z' -]{2,28}", e): return e
    return ''

# ------------------------------------------------------------ photos (cheapest first: official site, then Commons/Wikidata)
S = requests.Session(); S.headers['User-Agent'] = UA + ' photo-check'

def get(url, maxb=8_000_000, timeout=(6, 12), **kw):
    """-> (bytes, response) or (None, reason)"""
    for verify in (True, False):
        try:
            r = S.get(url, timeout=timeout, stream=True, verify=verify, allow_redirects=True, **kw)
            if r.status_code != 200: return None, r.status_code
            buf = b''
            for ch in r.iter_content(65536):
                buf += ch
                if len(buf) > maxb: return None, 'toobig'
            return buf, r
        except requests.exceptions.SSLError:
            if not verify: return None, 'ssl'
        except Exception as e:
            return None, type(e).__name__
    return None, 'err'

def img_ok(data):
    """-> (PIL image or None, reason). >=5KB, >=400px wide, sane aspect, not flat/logo-like."""
    from PIL import Image
    if len(data) < L.MIN_BYTES: return None, f'tiny<{L.MIN_BYTES}B'
    try:
        im = Image.open(io.BytesIO(data)); im.load()
    except Exception: return None, 'undecodable'
    w, h = im.size
    if w < 400: return None, f'narrow<{w}px'
    if not (0.45 <= w / h <= 3.3): return None, f'aspect{w / h:.2f}'
    if im.convert('L').resize((128, 128)).entropy() < 5.0: return None, 'flat/logo-entropy'
    if len(set(im.convert('RGB').resize((96, 96)).getdata())) < 350: return None, 'few-colours'
    return im, None

def save_webp(im, path):
    from PIL import Image
    im = im.convert('RGB')
    if im.width > 560: im = im.resize((560, max(1, round(im.height * 560 / im.width))), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, 'WEBP', quality=25, method=6)
    return path.stat().st_size >= L.MIN_BYTES, im.size

def og_candidates(html, base):
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')
    c = []
    for sel in ({'property': 'og:image'}, {'name': 'twitter:image'}, {'property': 'og:image:url'}):
        for m in soup.find_all('meta', attrs=sel):
            if m.get('content'): c.append(('og', urllib.parse.urljoin(base, m['content'].strip())))
    for img in soup.find_all('img')[:60]:
        src = img.get('data-src') or img.get('src') or ''
        if not src or src.startswith('data:'): continue
        wd = re.sub(r'\D', '', str(img.get('width') or '0')) or '0'
        if int(wd) and int(wd) < 300: continue
        c.append(('img', urllib.parse.urljoin(base, src)))
    seen, out = set(), []
    for k, u in c:
        if u in seen or BAD_IMG.search(urllib.parse.urlparse(u).path): continue
        seen.add(u); out.append((k, u))
    return out[:7]

def commons_url(tags):
    """(image URL, file page URL) from wikimedia_commons tag or the Wikidata P18 image (no API key)."""
    wc, fn = tags.get('wikimedia_commons', ''), None
    if wc.startswith('File:'): fn = wc[5:]
    elif wc.startswith('Category:'):
        d = S.get('https://commons.wikimedia.org/w/api.php', params={'action': 'query', 'list': 'categorymembers', 'cmtitle': wc, 'cmtype': 'file', 'cmlimit': 5, 'format': 'json'}, timeout=15).json()
        for m in d.get('query', {}).get('categorymembers', []):
            if re.search(r'\.(jpe?g|png|webp)$', m['title'], re.I): fn = m['title'][5:]; break
    if not fn and tags.get('wikidata'):
        d = S.get('https://www.wikidata.org/w/api.php', params={'action': 'wbgetclaims', 'entity': tags['wikidata'], 'property': 'P18', 'format': 'json'}, timeout=15).json()
        cl = d.get('claims', {}).get('P18', [])
        if cl: fn = cl[0]['mainsnak']['datavalue']['value']
    if not fn: return None, None
    q = urllib.parse.quote(fn.replace(' ', '_'))
    return f'https://commons.wikimedia.org/wiki/Special:FilePath/{q}?width=900', f'https://commons.wikimedia.org/wiki/File:{q}'

def photo_search(card, tags, town_slug, media_dir):
    """Returns (photo|None, photo_search dict). Results cached per OSM id."""
    notes, tried, photo = {}, [], None
    cf = CACHE / 'photos' / f'photo-{card["osmid"]}.json'
    dest = media_dir / f'{town_slug}-osm-{card["osmid"]}.webp'
    if cf.exists():
        d = json.load(open(cf))
        if d['photo'] is None or dest.exists(): return d['photo'], d['photo_search']
    site = card.get('website')
    if site and not card['chain']:
        tried.append('official')
        data, r = get(site, maxb=3_000_000)
        if data is None: notes['official'] = f'fetch-failed:{r}'
        else:
            try: cands = og_candidates(data.decode(r.encoding or 'utf-8', errors='replace'), r.url)
            except Exception as e: cands = []; notes['official'] = f'parse:{type(e).__name__}'
            why = []
            for k, u in cands:
                d2, r2 = get(u, maxb=6_000_000)
                if d2 is None: why.append(f'{k}:{r2}'); continue
                im, bad = img_ok(d2)
                if im is None: why.append(f'{k}:{bad}'); continue
                ok, size = save_webp(im, dest)
                if not ok: why.append(f'{k}:webp<5KB'); dest.unlink(missing_ok=True); continue
                photo = {'file': f'media/{dest.name}', 'credit': 'Official website', 'source': r.url, 'img_url': u, 'size': list(size)}
                break
            if 'official' not in notes: notes['official'] = 'ok' if photo else ('no-image-found' if not cands else ';'.join(why[:4]))
    elif site: notes['official'] = 'skipped:chain'
    else: notes['official'] = 'no-website-tag'
    if not photo and (tags.get('wikidata') or tags.get('wikimedia_commons')):
        tried.append('commons')
        try:
            u, page = commons_url(tags)
            if not u: notes['commons'] = 'no-image-on-entity'
            else:
                d2, r2 = get(u, maxb=10_000_000)
                im, bad = img_ok(d2) if d2 else (None, str(r2))
                if im is not None:
                    ok, size = save_webp(im, dest)
                    if ok: photo = {'file': f'media/{dest.name}', 'credit': 'Wikimedia Commons', 'source': page, 'img_url': u, 'size': list(size)}
                    else: dest.unlink(missing_ok=True); notes['commons'] = 'webp<5KB'
                else: notes['commons'] = f'rejected:{bad}'
        except Exception as e: notes['commons'] = f'err:{type(e).__name__}'
    elif not photo: notes['commons'] = 'no-wikidata-or-commons-tag'
    ps = {'tried': tried or ['none'], 'result': photo['credit'] if photo else None, 'notes': notes}
    cf.parent.mkdir(parents=True, exist_ok=True); json.dump({'photo': photo, 'photo_search': ps}, open(cf, 'w'), ensure_ascii=False)
    return photo, ps

# ------------------------------------------------------------ main
def pre_score(c):
    return (3 if c['website'] else 0) + (2 if c['has_wd'] else 0) + (1 if c['name_en_src'] != 'romanised' else 0) + (1 if c['cuisine'] else 0) - (3 if c['chain'] else 0)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pref'); ap.add_argument('slug')
    ap.add_argument('--tree', default=L.DEFAULT_TREE, help='checkout holding the live pages (for dedupe + English town name)')
    ap.add_argument('--need', type=int, default=0, help='how many new cards to select (default: target - live)')
    ap.add_argument('--photo-limit', type=int, default=0, help='max venues to photo-search (default 2.5*need)')
    ap.add_argument('--no-photos', action='store_true'); ap.add_argument('--refresh', action='store_true')
    ap.add_argument('--bbox', help='S,W,N,E instead of the Overpass area for the town name')
    ap.add_argument('--out', default=str(OUT)); ap.add_argument('--workers', type=int, default=6)
    A = ap.parse_args()
    out = Path(A.out); media = out / 'media'
    ql = build_query(A.pref, A.slug, tuple(float(x) for x in A.bbox.split(',')) if A.bbox else None)
    els = overpass(ql, f'{A.pref}-{A.slug}', A.refresh).get('elements', [])
    log(f'overpass: {len(els)} named food elements')
    live = L.live_names(A.tree, A.pref, A.slug)
    live_n = {L.norm_name(x) for x in live}; live_b = {L.strip_branch(n) for n in live_n if len(n) >= 4}
    town_e, pref_e = L.town_en(A.pref, A.slug, A.tree)
    pop = (L.popmap().get(f'{A.pref}/{A.slug}') or {}).get('pop')
    need = A.need or max(0, L.target_dining(pop) - len(live))
    cards, seen_geo, skipped = [], [], {'dup-live': 0, 'dup-osm': 0, 'no-name': 0, 'no-english': 0}
    for e in els:
        t = e.get('tags', {}); nm = (t.get('name') or '').strip()
        if not nm: skipped['no-name'] += 1; continue
        lat = e.get('lat') or (e.get('center') or {}).get('lat') or 0; lon = e.get('lon') or (e.get('center') or {}).get('lon') or 0
        n = L.norm_name(nm)
        if n in live_n or (len(n) >= 4 and L.strip_branch(n) in live_b) or (t.get('name:en') and L.norm_name(t['name:en']) in live_n):
            skipped['dup-live'] += 1; continue
        if n in seen_geo: skipped['dup-osm'] += 1; continue   # same Japanese name in the same town = one card (chain branches included)
        seen_geo.append(n)
        cat, noun, cu = classify(t)
        site = (t.get('website') or t.get('contact:website') or t.get('url') or '').strip()
        if site and not re.match(r'https?://', site): site = 'http://' + site
        if site and BLOCKED.search(urllib.parse.urlparse(site).netloc): site = ''
        en = (t.get('name:en') or '').strip()
        if en and L.CJK.search(en): en = ''
        src = 'osm name:en' if en else ''
        if not en:
            en, src = (L.romanize(nm), 'romanised') if L.CJK.search(nm) else (nm, 'osm name')
        if not en or L.CJK.search(en): skipped['no-english'] += 1; continue
        cards.append(dict(osmid=e['type'][0] + str(e['id']), osm_url=f'https://www.openstreetmap.org/{e["type"]}/{e["id"]}', name_ja=nm, name_en=L.nomacron(en),
                          name_en_src=src, category=cat, noun=noun, cuisine=cu, addr=addr_of(t), area=area_en(t),
                          phone=t.get('phone') or t.get('contact:phone') or '', website=site, opening_hours=t.get('opening_hours', ''),
                          price=t.get('price_range') or t.get('price:range') or '', lat=lat, lon=lon,
                          chain=bool(CHAIN_RE.search(nm) or t.get('brand:wikidata') or t.get('brand')),
                          has_wd=bool(t.get('wikidata') or t.get('wikimedia_commons')), photo=None, photo_search=None, _tags=t))
    cards.sort(key=lambda c: -pre_score(c))
    lim = A.photo_limit or int(need * 2.5) or 40
    todo = [c for c in cards if (c['website'] or c['has_wd']) and not c['chain']][:lim]
    ids = {c['osmid'] for c in todo}
    for c in cards:
        if c['osmid'] not in ids:
            c['photo_search'] = {'tried': ['official'] if c['chain'] and c['website'] else ['none'], 'result': None,
                                 'notes': {'official': 'skipped:chain' if c['chain'] else ('no-website-tag' if not c['website'] else 'not-searched:over-limit')}}
    if not A.no_photos and todo:
        t0 = time.time()
        def work(c):
            try: return c, photo_search(c, c['_tags'], A.slug, media)
            except Exception as ex: return c, (None, {'tried': ['official'], 'result': None, 'notes': {'error': type(ex).__name__}})
        with ThreadPoolExecutor(A.workers) as ex:
            for i, (c, (ph, ps)) in enumerate(ex.map(work, todo)):
                c['photo'], c['photo_search'] = ph, ps
                if (i + 1) % 20 == 0: log(f'  photos {i + 1}/{len(todo)}  {sum(1 for x in todo if x["photo"])} found  {time.time() - t0:.0f}s')
    elif A.no_photos:
        for c in todo: c['photo_search'] = {'tried': ['none'], 'result': None, 'notes': {'official': 'not-searched:no-photos-flag'}}
    md5s = {}   # same image on several venues (chain / portal default) -> keep first only
    for c in cards:
        if c['photo']:
            h = hashlib.md5((media / Path(c['photo']['file']).name).read_bytes()).hexdigest()
            if h in md5s: c['photo'] = None; c['photo_search'] = dict(c['photo_search'], result=None, notes=dict(c['photo_search']['notes'], dedupe='same-image-as-' + md5s[h]))
            else: md5s[h] = c['osmid']
    cards.sort(key=lambda c: -(pre_score(c) + (6 if c['photo'] else 0) + (1 if c['opening_hours'] else 0)))
    for i, c in enumerate(cards): c['selected'] = i < need; c.pop('_tags', None)
    sel = [c for c in cards if c['selected']]
    res = dict(pref=A.pref, slug=A.slug, town_ja=L.town_ja(A.pref, A.slug), town_en=town_e, pref_en=pref_e, live_cards=len(live), pop=pop,
               target=L.target_dining(pop), need=need, osm_elements=len(els), skipped=skipped, candidates=len(cards), selected=len(sel),
               selected_with_photo=sum(1 for c in sel if c['photo']), credit='OpenStreetMap contributors (ODbL)', cards=cards)
    (out / A.pref).mkdir(parents=True, exist_ok=True)
    json.dump(res, open(out / A.pref / f'{A.slug}.json', 'w'), ensure_ascii=False, indent=1)
    log(f'{A.pref}/{A.slug}: live {len(live)}, target {res["target"]}, need {need}; candidates {len(cards)}, selected {len(sel)} ({res["selected_with_photo"]} with photo); skipped {skipped}')
    print(out / A.pref / f'{A.slug}.json')

if __name__ == '__main__':
    main()
