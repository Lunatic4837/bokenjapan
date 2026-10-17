#!/usr/bin/env python3
"""ph_fill.py - find real, relevant photos for photo-less cards (no Tabelog / paid APIs).

  ph_fill.py inv   --root TREE --pref fukuoka --out inv.json          # inventory of every card (photo / photo-less)
  ph_fill.py find  --inv inv.json --pref fukuoka --out DIR [--towns a,b] [--limit N]   # search; resumable; writes DIR/results.jsonl + DIR/media/*.webp
  ph_fill.py apply --root TREE --pref fukuoka --out DIR               # patch pages: add <img class="thumb"> or a photo_search comment

Search order per card (every step recorded in photo_search.tried / notes):
  1. osm-official : OSM element of the same town with a website/contact:website tag whose name matches the card -> og:image / large <img> of that site
  2. osm-commons  : OSM wikidata / wikimedia_commons tag of that element -> Commons file / Wikidata P18
  3. commons-search: Wikimedia Commons full-text search on name + town; accepted only when the file title/description contains the venue name
Rejected images: <5KB, <400px wide, flat/logo/few-colours, logo|banner|badge names, same bytes already used (md5).
"""
import argparse, collections, difflib, hashlib, html as H, io, json, os, re, sys, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bjlib as L
import osm_dining as OD

IMG_HOST = 'https://img.bokenjapan.com'
JP = L.CJK
LI = re.compile(r'<li>(?:<a href="([^"]*)">)?<p class="place-name">([^<]*)</p>(.*?)</li>', re.S)
BRANCH = re.compile(r'(本店|支店|[^\s]{1,8}店|[^\s]{1,8}(?:モール|ゆめタウン|イオン|アミュプラザ|駅)[^\s]*)$')

def core_name(n):
    """name without branch suffix token: 'XXX 筑後店' -> 'XXX'"""
    toks = re.split(r'[\s\u3000]+', H.unescape(n).strip())
    while len(toks) > 1 and BRANCH.search(toks[-1]): toks.pop()
    return ' '.join(toks)

def nl(s):  # latin compare key
    return re.sub(r'[^a-z0-9]', '', L.nomacron(s).lower())

# ------------------------------------------------------------------ inventory
def inventory(root, pref, kinds=('eat', 'stay', 'see', 'do')):
    rows, seen = [], set()
    root = Path(root)
    for f in sorted((root / pref).glob('*/*/**/index.html')):
        rel = f.relative_to(root / pref).parts
        if rel[1] not in kinds: continue
        t = f.read_text(encoding='utf-8', errors='replace')
        for m in LI.finditer(t):
            href, name, rest = m.groups()
            key = (rel[0], rel[1], href, name)
            if key in seen: continue
            seen.add(key)
            img = re.search(r'<img class="thumb"[^>]*>', m.group(0))
            bl = re.search(r'<p class="place-blurb">([^<]*)</p>', rest)
            rows.append(dict(town=rel[0], sec=rel[1], page=str(f.relative_to(root)), href=href or '', name=H.unescape(name), photo=bool(img),
                             blurb=H.unescape(bl.group(1)) if bl else '', src=re.search(r'src="([^"]+)"', img.group(0)).group(1) if img else '',
                             has_ps=bool(re.search(r'photo_search', rest))))
    return rows

def card_id(c):
    m = re.search(r'/(\d{6,})/?$', c['href'])
    if m and 'tabelog' in c['href']: return m.group(1)
    m = re.search(r'-d(\d+)-', c['href'])
    if m: return 'ta' + m.group(1)
    return 'h' + hashlib.sha1((c['href'] + c['name']).encode()).hexdigest()[:8]

# ------------------------------------------------------------------ OSM town index (only elements that carry a website / wikidata / commons tag)
def osm_town(pref, slug):
    pj, tj = L.PREF_JA[pref], L.town_ja(pref, slug)
    if not tj: return []
    ql = (f'[out:json][timeout:150];area["name"="{pj}"]["boundary"="administrative"]["admin_level"="4"]->.p;'
          f'area["name"="{tj}"]["boundary"="administrative"](area.p)->.a;'
          'nwr["name"][~"^(amenity|shop|tourism|leisure|craft)$"~"."][~"^(website|contact:website|url|wikidata|wikimedia_commons)$"~"."](area.a);out tags center;')
    try: els = OD.overpass(ql, f'ph-{pref}-{slug}').get('elements', [])
    except Exception as e:
        OD.log(f'overpass failed {slug}: {e}'); return None
    out = []
    for e in els:
        t = e.get('tags', {})
        site = (t.get('website') or t.get('contact:website') or t.get('url') or '').strip()
        if site and not re.match(r'https?://', site): site = 'http://' + site
        if site and OD.BLOCKED.search(urllib.parse.urlparse(site).netloc): site = ''
        if not (site or t.get('wikidata') or t.get('wikimedia_commons')): continue
        nm = t['name'].strip(); en = (t.get('name:en') or '').strip()
        out.append(dict(osmid=e['type'][0] + str(e['id']), name=nm, name_en=en, site=site, tags=t,
                        chain=bool(OD.CHAIN_RE.search(nm) or t.get('brand:wikidata') or t.get('brand'))))
    return out

def match_osm(card, els):
    best, bs = None, 0.0
    if JP.search(card['name']):
        a = L.norm_name(core_name(card['name']))
        if len(a) < 2: return None, 0
        for e in els:
            b = L.norm_name(core_name(e['name']))
            if not b: continue
            if a == b: s = 1.0
            elif len(min(a, b, key=len)) >= 4 and (a in b or b in a): s = 0.93
            else: s = difflib.SequenceMatcher(None, a, b).ratio()
            if s > bs: best, bs = e, s
        return (best, bs) if bs >= 0.9 else (None, bs)
    a = nl(card['name'])
    if len(a) < 5: return None, 0
    for e in els:
        if e['tags'].get('amenity') in ('place_of_worship', 'school', 'hospital', 'clinic') if isinstance(e.get('tags'), dict) else False: continue
        for b in (nl(e['name_en']) if e['name_en'] else '', nl(L.romanize(e['name'])) if JP.search(e['name']) else nl(e['name'])):
            if not b: continue
            s = 1.0 if a == b else difflib.SequenceMatcher(None, a, b).ratio()
            if s > bs: best, bs = e, s
    return (best, bs) if bs >= 0.92 else (None, bs)

# ------------------------------------------------------------------ image handling
_md5 = {}
def take_image(url, dest, referer=None):
    d, r = OD.get(url, maxb=8_000_000)
    if d is None: return None, f'fetch:{r}'
    h = hashlib.md5(d).hexdigest()
    im, bad = OD.img_ok(d)
    if im is None: return None, bad
    if h in _md5 and _md5[h] != dest.name: return None, 'dup-bytes'
    ok, size = OD.save_webp(im, dest)
    if not ok: dest.unlink(missing_ok=True); return None, 'webp<5KB'
    _md5[h] = dest.name
    return size, None

def official(site, dest):
    d, r = OD.get(site, maxb=3_000_000)
    if d is None: return None, f'site:{r}'
    try: cands = OD.og_candidates(d.decode(r.encoding or 'utf-8', errors='replace'), r.url)
    except Exception as e: return None, f'parse:{type(e).__name__}'
    if not cands: return None, 'no-image-on-page'
    why = []
    for k, u in cands:
        size, bad = take_image(u, dest)
        if size: return dict(source=r.url, img_url=u, size=list(size), credit='Official website'), None
        why.append(f'{k}:{bad}')
    return None, ';'.join(why[:3])

def commons_api(params):
    for i in range(3):
        try:
            r = OD.S.get('https://commons.wikimedia.org/w/api.php', params=dict(params, format='json'), timeout=25)
            if r.status_code == 200: return r.json()
        except Exception: pass
        time.sleep(3 * (i + 1))
    return {}

def commons_search(card, town_ja, town_en, dest):
    ja = bool(JP.search(card['name']))
    core = core_name(card['name'])
    if ja:
        key = L.norm_name(core)
        if len(key) < 3: return None, 'name-too-short'
        q = f'{core} {town_ja}'
    else:
        toks = [t for t in re.split(r'[^A-Za-z0-9]+', L.nomacron(core)) if t]
        sig = [t.lower() for t in toks if len(t) >= 3]
        if len(sig) < 2 and not any(len(t) >= 7 for t in sig): return None, 'name-too-generic'
        q = f'{core} {town_en}'
    d = commons_api({'action': 'query', 'generator': 'search', 'gsrsearch': q + ' filetype:bitmap', 'gsrnamespace': 6, 'gsrlimit': 8,
                     'prop': 'imageinfo', 'iiprop': 'url|size|extmetadata|mime', 'iiurlwidth': 900})
    pages = sorted((d.get('query') or {}).get('pages', {}).values(), key=lambda p: p.get('index', 99))
    if not pages: return None, 'no-results'
    for p in pages:
        ii = (p.get('imageinfo') or [{}])[0]
        md = ii.get('extmetadata') or {}
        text = p['title'] + ' ' + re.sub(r'<[^>]+>', ' ', (md.get('ImageDescription') or {}).get('value', '')) + ' ' + (md.get('ObjectName') or {}).get('value', '')
        if ii.get('mime') not in ('image/jpeg', 'image/png', 'image/webp'): continue
        if (ii.get('width') or 0) < 400: continue
        if re.search(r'logo|map|chart|diagram|menu|flag|stamp|poster|screenshot|icon', p['title'], re.I): continue
        tn = L.norm_name(text)
        town_hit = (town_ja and L.norm_name(town_ja).rstrip('市町村') in tn) or (town_en and nl(town_en) in nl(text)) or ('福岡' in text and ja)
        ok = bool(town_hit) and ((L.norm_name(core) in tn) if ja else (nl(core) in nl(text)))
        if not ok: continue
        u = ii.get('thumburl') or ii['url']
        size, bad = take_image(u, dest)
        if size:
            au = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', (md.get('Artist') or {}).get('value', ''))).strip()[:80] or 'unknown author'
            lic = (md.get('LicenseShortName') or {}).get('value', 'see source')
            return dict(source='https://commons.wikimedia.org/wiki/' + urllib.parse.quote(p['title'].replace(' ', '_')), img_url=u, size=list(size),
                        credit='Wikimedia Commons', author=au, licence=lic, commons_title=p['title']), None
    return None, 'no-title-match'

def commons_meta(page_url):
    t = urllib.parse.unquote(page_url.rsplit('/wiki/', 1)[-1]).replace('_', ' ')
    d = commons_api({'action': 'query', 'titles': t, 'prop': 'imageinfo', 'iiprop': 'extmetadata'})
    for p in (d.get('query') or {}).get('pages', {}).values():
        md = ((p.get('imageinfo') or [{}])[0]).get('extmetadata') or {}
        au = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', (md.get('Artist') or {}).get('value', ''))).strip()[:80] or 'unknown author'
        return au, (md.get('LicenseShortName') or {}).get('value', 'see source')
    return 'unknown author', 'see source'

def find_card(card, els, town_ja, town_en, media, prior=None):
    cid = card_id(card)
    dest = media / f"{card['town']}-dining-{cid}.webp"
    tried, notes, photo = [], {}, None
    m, sc = match_osm(card, els) if els else (None, 0)
    if els: tried.append('osm-name-match')
    if m:
        notes['osm'] = f"match:{m['osmid']}:{sc:.2f}"
        if m['site'] and not m['chain']:
            tried.append('osm-official'); photo, why = official(m['site'], dest)
            if not photo: notes['official'] = why
            else: photo['osm'] = m['osmid']; photo['official_url'] = m['site']
        elif m['site']: notes['official'] = 'skipped:chain'
        if not photo and (m['tags'].get('wikidata') or m['tags'].get('wikimedia_commons')):
            tried.append('osm-commons')
            try:
                u, page = OD.commons_url(m['tags'])
                if u:
                    size, bad = take_image(u, dest)
                    if size:
                        au, lic = commons_meta(page)
                        photo = dict(source=page, img_url=u, size=list(size), credit='Wikimedia Commons', author=au, licence=lic, osm=m['osmid'])
                    else: notes['commons'] = bad
                else: notes['commons'] = 'no-image-on-entity'
            except Exception as e: notes['commons'] = f'err:{type(e).__name__}'
    else:
        notes['osm'] = 'no-match-with-website' if els is not None else 'overpass-failed'
    if prior is not None:   # osm-only re-pass: commons-search already done
        tried = (prior['photo_search']['tried'] if prior else []) + tried; notes = dict(prior['photo_search']['notes'], **notes)
    elif not photo and not OD.CHAIN_RE.search(card['name']):
        tried.append('commons-search')
        photo, why = commons_search(card, town_ja, town_en, dest)
        if not photo: notes['commons-search'] = why
    elif not photo: notes['commons-search'] = 'skipped:chain'
    tried = [t for i, t in enumerate(tried) if t not in tried[:i] and t != 'none']
    return dict(key=f"{card['town']}|{card['sec']}|{card['href']}|{card['name']}", town=card['town'], name=card['name'], id=cid,
                photo=photo and dict(photo, file=f'media/{dest.name}'), photo_search=dict(tried=tried or ['none'], result=photo['credit'] if photo else None, notes=notes))


# ------------------------------------------------------------------ web search (DuckDuckGo html, free, no account) for the venue's own site
import threading
_ddg_last = [0.0]; _ddg_lock = threading.Lock()
class Blocked(Exception): pass
def bing(q):
    import base64
    with _ddg_lock:
        gap = 1.5 - (time.time() - _ddg_last[0])
        if gap > 0: time.sleep(gap)
        _ddg_last[0] = time.time()
    r = OD.S.get('https://www.bing.com/search', params={'q': q, 'setlang': 'ja', 'cc': 'jp'}, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64)', 'Accept-Language': 'ja,en;q=0.8'}, timeout=20)
    if r.status_code != 200: raise Blocked('bing' + str(r.status_code))
    if 'b_algo' not in r.text:
        if 'b_content' in r.text or 'b_results' in r.text or 'b_no' in r.text: return []
        raise Blocked('bing-nopage')
    out = []
    for blk in r.text.split('<li class="b_algo"')[1:]:
        m = re.search(r'[?&;]u=a1([A-Za-z0-9_\-]+)', H.unescape(blk))
        if m:
            b = m.group(1); b += '=' * (-len(b) % 4)
            try: out.append(base64.urlsafe_b64decode(b).decode())
            except Exception: pass
        else:
            m = re.search(r'<h2><a href="(https?://[^"]+)"', blk)
            if m: out.append(H.unescape(m.group(1)))
    return out

def ddg(q):
    gap = 3.0 - (time.time() - _ddg_last[0])
    if gap > 0: time.sleep(gap)
    _ddg_last[0] = time.time()
    r = OD.S.post('https://html.duckduckgo.com/html/', data={'q': q, 'kl': 'jp-jp'}, headers={'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) BokenJapanBot/1.0'}, timeout=20)
    if r.status_code in (202, 403, 429) or 'anomaly' in r.text[:5000].lower(): raise Blocked(str(r.status_code))
    out = []
    for m in re.finditer(r'class="result__a" href="([^"]+)"', r.text):
        u = H.unescape(m.group(1))
        mm = re.search(r'uddg=([^&]+)', u)
        if mm: u = urllib.parse.unquote(mm.group(1))
        out.append(u)
    return out

AGGR = re.compile(r'(tabelog|hotpepper|gnavi|retty|tripadvisor|rakuten|google\.|yelp|jalan|ikyu|ekiten|navitime|mapion|facebook|instagram|twitter|x\.com|line\.me|tiktok|youtube|ameblo|note\.com|linktr|wikipedia|yahoo|amazon|uber|demae|menu\.jp|favy|hitosara|ozmall|opentable|tablecheck|goo\.ne|goo-net|travel\.co|booking|agoda|expedia|trivago|mapfan|loco\.yahoo|itp\.ne|iタウン|townpage|navi|gourmet|kutikomi|ekiten|epark|minkou|bing\.com|duckduckgo|pinterest|hatena|blogspot|livedoor|fc2|seesaa|ja\.wikipedia|biglobe|fukuoka-now|rurubu|ana\.co|jtb|knt|nta\.co|yaplog|jimdo\.com/|wixsite|crayonsite|ameba)', re.I)

def web_find(card, town_ja, town_en, dest):
    ja = bool(JP.search(card['name'])); core = core_name(card['name'])
    q = f'{core} {town_ja or ""} 公式' if ja else f'{core} {town_en} Fukuoka restaurant'
    try: res = bing(q)
    except Blocked: res = ddg(q)
    cands, seen = [], set()
    for u in res:
        host = urllib.parse.urlparse(u).netloc.lower()
        if not host or AGGR.search(host) or host in seen: continue
        seen.add(host); cands.append(u)
    notes = {'web-candidates': [urllib.parse.urlparse(u).netloc for u in cands[:3]]}
    key = L.norm_name(core) if ja else nl(core)
    for u in cands[:3]:
        d, r = OD.get(u, maxb=2_000_000)
        if d is None: continue
        try: txt = d.decode(r.encoding or 'utf-8', errors='replace')
        except Exception: continue
        plain = re.sub(r'<script.*?</script>|<style.*?</style>|<[^>]+>', ' ', txt, flags=re.S)
        pk = L.norm_name(plain[:60000]) if ja else nl(plain[:60000])
        if key not in pk: continue
        tt = ' '.join(re.findall(r'<title[^>]*>(.*?)</title>|<h1[^>]*>(.*?)</h1>|property="og:site_name" content="([^"]*)"', txt, flags=re.S | re.I).__iter__().__next__() if False else [x for tup in re.findall(r'<title[^>]*>(.*?)</title>|<h1[^>]*>(.*?)</h1>|property="og:site_name" content="([^"]*)"', txt, flags=re.S | re.I) for x in tup])
        tt = L.norm_name(re.sub(r'<[^>]+>', ' ', tt)) if ja else nl(re.sub(r'<[^>]+>', ' ', tt))
        if key not in tt or len(key) < 3: continue   # the venue name must be in the page title / h1 / site name (blogs and news pages that merely mention it are rejected)
        hint = ('福岡' in plain) or (town_ja and town_ja.rstrip('市町村') in plain) or (town_en and town_en.lower() in plain.lower()) or 'fukuoka' in plain.lower()
        if not hint: continue
        photo, why = official(u, dest)
        if photo: photo['official_url'] = u; return photo, notes
        notes['web-site-' + urllib.parse.urlparse(u).netloc] = why
    return None, notes

def cmd_web(A):
    rows = {f"{r['town']}|{r['sec']}|{r['href']}|{r['name']}": r for r in json.load(open(A.inv))}
    out = Path(A.out); media = out / 'media'; rf = out / 'results.jsonl'
    last = {}
    for l in open(rf):
        r0 = json.loads(l); last[r0['key']] = r0
    for f in media.glob('*.webp'):
        _md5[hashlib.md5(f.read_bytes()).hexdigest()] = f.name
    todo = [k for k, r0 in last.items() if r0['photo'] is None and 'web-search' not in r0['photo_search']['tried']
            and (not A.towns or r0['town'] in A.towns.split(',')) and not OD.CHAIN_RE.search(r0['name'])]
    todo.sort(key=lambda k: 0 if JP.search(last[k]['name']) else 1)
    if A.jp_only: todo = [k for k in todo if JP.search(last[k]['name'])]
    OD.log(f'web phase: {len(todo)} cards')
    n = f = 0
    def one(k):
        r0 = last[k]; c = rows[k]
        tj = L.town_ja(A.pref, c['town']) or ''; te = L.town_en(A.pref, c['town'], A.root)[0]
        dest = media / f"{c['town']}-dining-{r0['id']}.webp"
        try: photo, notes = web_find(c, tj, te, dest)
        except Blocked as e: return None
        except Exception as e: return None
        ps = dict(r0['photo_search']); ps['tried'] = ps['tried'] + ['web-search']; ps['notes'] = dict(ps['notes'], **notes)
        if photo: ps['result'] = 'Official website'
        return dict(r0, photo=photo and dict(photo, file=f'media/{dest.name}'), photo_search=ps)
    with open(rf, 'a') as fh, ThreadPoolExecutor(10) as ex:
        for res in ex.map(one, todo):
            if res is None: continue
            fh.write(json.dumps(res, ensure_ascii=False) + '\n'); fh.flush(); n += 1; f += bool(res['photo'])
            if n % 25 == 0: OD.log(f'  web {n}/{len(todo)} found {f}')
            if A.limit and n >= A.limit: break
    OD.log(f'web done {n}, found {f}')


def cmd_romaji(A):
    """apply a JSON map {"<ja name>\t<old blurb>": "<new blurb>"} to place-blurb + JSON-LD alternateName on eat/stay pages"""
    mp = json.load(open(A.map)); root = Path(A.root); n = pages = 0
    for f in sorted((root / A.pref).glob('*/*/**/index.html')):
        if f.relative_to(root / A.pref).parts[1] not in ('eat', 'stay'): continue
        t = f.read_text(encoding='utf-8'); o = t
        def sub(m):
            nonlocal n
            name = H.unescape(m.group(2)); body = m.group(0)
            bl = re.search(r'<p class="place-blurb">([^<]*)</p>', body)
            if not bl: return body
            old = H.unescape(bl.group(1)); new = mp.get(name + '\t' + old)
            if not new: return body
            n += 1
            return body.replace(bl.group(0), '<p class="place-blurb">' + H.escape(new, quote=False) + '</p>', 1)
        t = LI.sub(sub, t)
        for k, new in mp.items():
            nm, old = k.split('\t', 1)
            a = '"name": ' + json.dumps(nm, ensure_ascii=False) + ', "alternateName": ' + json.dumps(old, ensure_ascii=False)
            if a in t: t = t.replace(a, '"name": ' + json.dumps(nm, ensure_ascii=False) + ', "alternateName": ' + json.dumps(new, ensure_ascii=False))
        if t != o: f.write_text(t, encoding='utf-8'); pages += 1
    print('romaji fixed on', n, 'cards in', pages, 'pages')

# ------------------------------------------------------------------ commands
def cmd_find(A):
    rows = json.load(open(A.inv)); out = Path(A.out); media = out / 'media'; media.mkdir(parents=True, exist_ok=True)
    rf = out / 'results.jsonl'
    last = {}
    if rf.exists():
        for l in open(rf):
            r0 = json.loads(l); last[r0['key']] = r0
    osm_pass = A.phase == 'osm'
    done = {k for k, r0 in last.items() if not (osm_pass and r0['photo'] is None and r0['photo_search']['notes'].get('osm') == 'overpass-failed')}
    if osm_pass: done = set(last) - {k for k, r0 in last.items() if r0['photo'] is None and r0['photo_search']['notes'].get('osm') == 'overpass-failed'}
    for f in media.glob('*.webp'):
        try: _md5[hashlib.md5(OD.Path(f).read_bytes() if False else f.read_bytes()).hexdigest()] = f.name
        except OSError: pass
    todo = [r for r in rows if not r['photo'] and r['sec'] == 'eat']
    towns = [t for t in (A.towns.split(',') if A.towns else sorted({r['town'] for r in todo}))]
    OSMJ = json.load(open(A.osm_json)) if A.osm_json else []
    n = 0; queue = list(towns); rounds = 0
    while queue:
        town = queue.pop(0)
        cs = [r for r in todo if r['town'] == town and f"{r['town']}|{r['sec']}|{r['href']}|{r['name']}" not in done]
        if not cs: continue
        if A.osm_json:
            tj0 = (L.town_ja(A.pref, town) or '').rstrip('市町村')
            els = []
            for e in OSMJ:
                site = (e['site'] or '').strip()
                if site and not re.match(r'https?://', site): site = 'http://' + site
                if site and OD.BLOCKED.search(urllib.parse.urlparse(site).netloc): site = ''
                if not (site or e['wikidata'] or e['commons']): continue
                if e['addr'] and tj0 and not any(x in e['addr'] for x in (tj0,)) and re.search(r'[市町村郡]', e['addr']): continue   # element is in another municipality
                els.append(dict(osmid=e['osmid'], name=e['name'], name_en=e['name_en'], site=site, tags=dict(wikidata=e['wikidata'], wikimedia_commons=e['commons']),
                                chain=bool(OD.CHAIN_RE.search(e['name']) or e['tags'].get('brand') or e['tags'].get('brand:wikidata'))))
        else:
            els = None if A.no_osm_wait else osm_town(A.pref, town)
        if els is None and osm_pass:
            OD.log(f'  {town}: Overpass still unavailable'); continue
        if els is None and not A.no_osm_wait:
            OD.log(f'  {town}: Overpass unavailable - deferred'); queue.append(town); rounds += 1
            if rounds > 60: break
            time.sleep(90); continue
        tj = L.town_ja(A.pref, town) or ''; te = L.town_en(A.pref, town, A.root)[0]
        OD.log(f'{town}: {len(cs)} photo-less, osm elements with site/wikidata: {len(els) if els is not None else "FAILED"}')
        t0 = time.time(); found = 0
        with ThreadPoolExecutor(A.workers) as ex, open(rf, 'a') as fh:
            futs = [ex.submit(lambda c=c: find_card(c, els, tj, te, media, last.get(f"{c['town']}|{c['sec']}|{c['href']}|{c['name']}") if osm_pass else None)) for c in cs]
            for fu in futs:
                try: res = fu.result()
                except Exception as e: continue
                fh.write(json.dumps(res, ensure_ascii=False) + '\n'); fh.flush(); n += 1; found += bool(res['photo'])
        OD.log(f'  {town}: +{found}/{len(cs)} photos in {time.time() - t0:.0f}s')
        if A.limit and n >= A.limit: break

def cmd_inv(A):
    rows = inventory(A.root, A.pref)
    json.dump(rows, open(A.out, 'w'), ensure_ascii=False)
    c = collections.Counter((r['sec'], r['photo']) for r in rows)
    ds = [r for r in rows if r['sec'] in ('eat', 'stay')]
    print(A.pref, len(rows), dict(c), 'dining+stay photo %.1f%%' % (100 * sum(r['photo'] for r in ds) / max(1, len(ds))))

def english_alt(c, fallback):
    b = c.get('blurb') or ''
    return b if b and not JP.search(b) else fallback

def cmd_apply(A):
    root, out = Path(A.root), Path(A.out)
    res = {}
    for l in open(out / 'results.jsonl'):
        r = json.loads(l); res[r['key']] = r
    stats = collections.Counter()
    for f in sorted((root / A.pref).glob('*/eat/**/index.html')):
        town = f.relative_to(root / A.pref).parts[0]
        t = f.read_text(encoding='utf-8'); orig = t
        def sub(m):
            href, name, rest = m.groups()
            if re.search(r'<img class="thumb"', m.group(0)): return m.group(0)
            key = f"{town}|eat|{href or ''}|{H.unescape(name)}"
            r = res.get(key)
            if not r: return m.group(0)
            body = re.sub(r'<!-- photo_search: .*? -->', '', m.group(0))
            bl = re.search(r'<p class="place-blurb">([^<]*)</p>', rest)
            alt = H.unescape(bl.group(1)) if bl else H.unescape(name)
            if r['photo']:
                p = r['photo']; w, h = p['size']
                src_f = out / p['file']; dst_f = root / p['file']
                if src_f.exists():
                    dst_f.parent.mkdir(parents=True, exist_ok=True)
                    if not dst_f.exists(): dst_f.write_bytes(src_f.read_bytes())
                else: return m.group(0)
                img = f'<img class="thumb" src="{IMG_HOST}/{p["file"]}" alt="{H.escape(alt, quote=True)}" loading="lazy" decoding="async" width="{w}" height="{h}">'
                body = body.replace('</p></a>', '</p>' + img + '</a>', 1)
                cred = f'<!-- photo-credit: {H.escape(p.get("author") or p["credit"], quote=False).replace("--", "-")} · {p.get("licence") or "all rights with the venue (official website)"} · Source {p["source"]} -->'
                body = body[:-5] + cred + '</li>'
                stats['photo'] += 1
            else:
                ps0 = r['photo_search']
                if 'web-search' not in ps0['tried'] and 'web-search' not in ps0['notes']:
                    ps0 = dict(ps0, notes=dict(ps0['notes'], **{'web-search': 'not-run:English-only name (pilot of 480 such cards returned only unrelated pages)'}))
                body = body[:-5] + '<!-- photo_search: ' + json.dumps(ps0, ensure_ascii=False, separators=(',', ':')) + ' -->' + '</li>'
                stats['search-recorded'] += 1
            return body
        t = LI.sub(sub, t)
        if t != orig: f.write_text(t, encoding='utf-8'); stats['pages'] += 1
    print(dict(stats))

def main():
    ap = argparse.ArgumentParser(); sp = ap.add_subparsers(dest='cmd', required=True)
    a = sp.add_parser('inv'); a.add_argument('--root', required=True); a.add_argument('--pref', required=True); a.add_argument('--out', required=True)
    b = sp.add_parser('find'); b.add_argument('--root', required=True); b.add_argument('--inv', required=True); b.add_argument('--pref', required=True); b.add_argument('--out', required=True)
    b.add_argument('--towns'); b.add_argument('--no-osm-wait', action='store_true'); b.add_argument('--phase', default='all', choices=['all', 'osm']); b.add_argument('--osm-json'); b.add_argument('--limit', type=int, default=0); b.add_argument('--workers', type=int, default=3)
    w = sp.add_parser('web'); w.add_argument('--root', required=True); w.add_argument('--inv', required=True); w.add_argument('--pref', required=True); w.add_argument('--out', required=True); w.add_argument('--towns'); w.add_argument('--limit', type=int, default=0); w.add_argument('--jp-only', action='store_true')
    r = sp.add_parser('romaji'); r.add_argument('--root', required=True); r.add_argument('--pref', required=True); r.add_argument('--map', required=True)
    c = sp.add_parser('apply'); c.add_argument('--root', required=True); c.add_argument('--pref', required=True); c.add_argument('--out', required=True)
    A = ap.parse_args()
    {'inv': cmd_inv, 'find': cmd_find, 'apply': cmd_apply, 'web': cmd_web, 'romaji': cmd_romaji}[A.cmd](A)

if __name__ == '__main__':
    main()
