#!/usr/bin/env python3
"""Miyagi/Ohira hub template for a prefecture's municipality pages (generator-level; reusable for later prefs).

  python3 template_hub.py --root <site> --pref aomori [--tb tb.jsonl] [--photos]

Per municipality page (flat Stay/Dining/Sights) it:
  1. Fills missing Dining thumbs from the card's own Tabelog page (og:image) when --photos (slim WebP, credit in comment only).
  2. Rewrites garbled Jalan/Ikkyu Stay romaji blurbs to natural English (en_natural.py) and normalizes phone numbers.
  3. Emits the hub: index.html with hub-tiles (Stay, Eat, Do, See, Day to day; stay-none line kept above tiles),
     stay/ do/ see/ day-to-day/ list pages and eat/ with food-genre category tiles + eat/<genre>/ list pages,
     using the exact markup of phase-d/rollout/build_all.py (Miyagi/Ohira) and body.hubbed (grid CSS in styles.css).
Genre comes from the Tabelog servesCuisine of each card (tb.jsonl: {u, genre, og}); categories from rollout/rules.py.
"""
import re, json, os, html, collections, glob, sys, shutil, argparse, io, subprocess, unicodedata
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from en_natural import natural_en
ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--pref', action='append', required=True)
ap.add_argument('--tb', default='/workspace/p1/data/template4/tb.jsonl'); ap.add_argument('--photos', action='store_true')
ap.add_argument('--rules', default='/workspace/p1/phase-d/rollout/rules.py'); A = ap.parse_args()
exec(open(A.rules).read())   # CAT, TB, DAILY_TB, TA_ORDER, DESC, CSLUG
ROOT = Path(A.root); MEDIA = ROOT / 'media'
TBD = {}
for l in open(A.tb):
    x = json.loads(l); TBD[x['u']] = x
def esc(s): return html.escape(s, quote=True)
def plural(n): return f'{n} place' if n == 1 else f'{n:,} places'
def gsplit(g): return [x.strip() for x in re.split(r'[、,]', g or '') if x.strip()]
def lis_of(src, name):
    m = re.search(r'<section class="place-section"><h2>' + name + r'</h2><ul class="place-list">(.*?)</ul></section>', src, re.S)
    return re.findall(r'<li>.*?</li>', m.group(1), re.S) if m else []
def img(li):
    m = re.search(r'<img class="thumb" src="([^"]+)"[^>]*?(?:width="(\d+)" height="(\d+)")?[^>]*>', li)
    if not m: return None
    w, h = m.group(2), m.group(3)
    if not w:
        p = ROOT / 'media' / m.group(1).split('/')[-1]
        try:
            from PIL import Image
            with Image.open(p) as im: w, h = im.size
        except Exception: w, h = 320, 240
    return (m.group(1), int(w), int(h))
def name(li): return html.unescape(re.search(r'class="place-name">(.*?)</p>', li).group(1))
def blurb(li):
    m = re.search(r'class="place-blurb">(.*?)</p>', li); return html.unescape(m.group(1)) if m else ''
def classify(x):
    gs = gsplit(x['genre'])
    if gs and gs[0] in DAILY_TB: return 'daily', True
    for j, g in enumerate(gs):
        if g in TB: return TB[g], j == 0
    if any(g in DAILY_TB for g in gs): return 'daily', False
    d = (x['desc'] or '').lower()
    for rx, k in DESC:
        if re.search(rx, d): return k, False
    return 'other', False
def classify_sight(li, stay_bl):
    n = name(li); d = (re.search(r'class="place-desc">(.*?)</p>', li) or [0, ''])[1]; s = (n + ' ' + d).lower()
    if stay_bl and re.search(r'\bhotel\b', n.lower()) and n.lower() in stay_bl: return 'dup-stay'
    if re.search(r'information cent(er|re)|kankojoho|tourist info|\bja\b|farm|chokubai|market', s): return 'daily'
    if re.search(r'museum|shrine|temple|garden|historic|ruins|castle|house|view|falls|gorge', s): return 'see'
    if re.search(r'hanabi|festival|matsuri|taiko|bonden|onsen|hot spring|baths|ski|experience|togei|resort|roadside station|brewery|shuzo|hiking|camp', s): return 'do'
    return 'see'
# ---------- photo fill (Tabelog og:image of the card's own listing)
def ok_image(b):
    from PIL import Image, ImageStat
    im = Image.open(io.BytesIO(b)).convert('RGB'); g = im.convert('L').resize((64, 64))
    if min(im.size) < 200 or ImageStat.Stat(g).stddev[0] < 15: return None
    return im
def fill_photo(li, slug, st):
    if 'class="thumb"' in li: return li
    tb = re.search(r'tabelog_url=(\S+?/)\s', li)
    og = tb and (TBD.get(tb.group(1)) or {}).get('og')
    if not og or 'no_image' in og or 'noimage' in og: st['nophoto'] += 1; return li
    rid = tb.group(1).rstrip('/').split('/')[-1]; dest = MEDIA / f'{slug}-dining-{rid}.webp'
    if not dest.exists():
        b = subprocess.run(['curl', '-sL', '--max-time', '20', '-A', 'Mozilla/5.0', og], capture_output=True).stdout
        try: im = ok_image(b)
        except Exception: im = None
        if not im: st['nophoto'] += 1; return li
        if im.width > 480: im = im.resize((480, round(im.height * 480 / im.width)))
        im.save(dest, 'WEBP', quality=72, method=5)
    from PIL import Image
    with Image.open(dest) as im: w, h = im.size
    nm = re.search(r'<p class="place-name">[^<]*</p>', li).group(0)
    li = li.replace(nm, nm + f'<img class="thumb" src="../../media/{dest.name}" alt="{esc(name(li))}" width="{w}" height="{h}" loading="lazy"><!-- photo-credit: 食べログ · Source {tb.group(1)} -->', 1)
    st['filled'] += 1; return li
# ---------- Stay romaji + phones
ROMAJI_BAD = re.compile(r'(\b[A-Z] [A-Z] [A-Z]\b|Hoteru|Ryokan [A-Z]|Sou\b|Paaku|Bijinesu|Purinsu|Shitei|ruutoin|Gurando|Nyuu|Rizooto|Penshon|Gesutohausu|Hausu|Puraza|Rooyaru|Sentaa|Onsenryokan|\( |aa|ii|uu|ee|oo|ou\b| Ya\b| Kan\b| En\b)', re.I)
def fix_stay(li, muni_ja, muni_en, st):
    if not re.search(r'sources: [^>]*(jalan_url|ikkyu_url)=', li): return li
    b = blurb(li); n = name(li)
    if b and not ROMAJI_BAD.search(b): return li
    new = natural_en(n, muni_ja, muni_en)
    if new and new != b:
        li = re.sub(r'<p class="place-blurb">[^<]*</p>', f'<p class="place-blurb">{esc(new)}</p>', li, count=1); st['stay_en'] += 1
    return li
def fix_phone(t):
    t = re.sub(r'(\d)[‐－―ー−](?=\d)', r'\1-', t)
    t = re.sub(r'\b[1-9](0\d{1,4}-\d{1,4}-\d{4})\b', r'\1', t)
    t = re.sub(r'\b(0\d{1,4}-\d{1,4}-\d{4}) (0\d{1,4}-\d{1,4}-\d{4})\b', r'\1 / \2', t)
    return t
# ---------- hub
def build(pref, slug, st):
    PAGE = f'{pref}/{slug}'; p = ROOT / PAGE / 'index.html'; src = p.read_text()
    if '<section class="hub">' in src: st['already'] += 1; return
    src = re.sub(r'(<p class="place-meta">)([^<]*)', lambda m: m.group(1) + fix_phone(m.group(2)), src)
    src = re.sub(r'(<dd>)([^<]*\d[^<]*)(</dd>)', lambda m: m.group(1) + fix_phone(m.group(2)) + m.group(3), src)
    muni_ja = (re.search(r'<!-- muni-ja: ([^ ]+) -->', src) or [0, None])[1]
    PREF = html.unescape(re.search(r'<p class="crumb"><a href="/">Japan</a> / <a href="\.\./">([^<]+)</a>', src).group(1))
    MUNI = html.unescape(re.search(r'<h1 class="page-title">([^<]+)</h1>', src).group(1))
    stay = [fix_stay(l, muni_ja, MUNI, st) for l in lis_of(src, 'Stay')]
    dining = [fill_photo(l, slug, st) if A.photos else l for l in lis_of(src, 'Dining')]
    sights = lis_of(src, 'Sights')
    cards = []
    for li in dining:
        tb = re.search(r'tabelog_url=(\S+?/)\s', li); g = tb and (TBD.get(tb.group(1)) or {}).get('genre')
        cards.append(dict(genre=g, desc=(re.search(r'class="place-desc">(.*?)</p>', li) or [0, ''])[1] + ' ' + blurb(li)))
        st['genre_ok' if g else 'genre_none'] += 1
    st['dining'] += len(dining); st['dining_img'] += sum(1 for l in dining if 'class="thumb"' in l)
    st['stay'] += len(stay); st['stay_img'] += sum(1 for l in stay if 'class="thumb"' in l)
    cover = (re.search(r'<figure class="cover"><img src="([^"]+)"', src) or [0, ''])[1]
    eat = collections.defaultdict(list); daily_d = []; primary = {}
    for i, li in enumerate(dining):
        k, prim = classify(cards[i]); primary[i] = prim
        (daily_d if k == 'daily' else eat[k]).append(i)
    stay_bl = [blurb(l).lower() for l in stay] + [name(l).lower() for l in stay]
    sg = collections.defaultdict(list)
    for li in sights: sg[classify_sight(li, stay_bl)].append(li)
    SECT = {'stay': ('Stay', stay), 'eat': ('Eat', [l for i, l in enumerate(dining) if i not in set(daily_d)]), 'do': ('Do', sg['do']),
            'see': ('See', sg['see'] + sg['dup-stay']), 'daily': ('Day to day', sg['daily'] + [dining[i] for i in daily_d])}
    HEAD_END = src.index('</head>'); BODY_START = src.index('<main class="page-main">')
    head = src[:HEAD_END]; mast = src[src.index('<body'):BODY_START]
    me = src.rindex('</main>'); ls = src.rfind('\n', 0, me) + 1
    foot = src[ls:] if src[ls:me].strip() == '' else src[me:]
    # drop page scripts (map) but keep analytics beacons (e.g. Cloudflare Web Analytics) so regen preserves them
    foot_noscript = re.sub(r'\s*<script\b[^>]*>.*?</script>', lambda m: m.group(0) if re.search(r'beacon|cloudflareinsights', m.group(0)) else '', foot, flags=re.S)
    def tile(href, label, n, li, big=True):
        im = img(li) if li else None
        pic = f'<img src="{im[0]}" alt="{esc(name(li))}" width="{im[1]}" height="{im[2]}" {"" if big else " loading=\"lazy\""} decoding="async">' if im else ''
        return (f'<li><a class="hub-tile{"" if big else " hub-tile-sm"}" href="{href}">{pic}'
                f'<span class="hub-tile-label"><span class="hub-tile-name">{esc(label)}</span>'
                f'<span class="hub-tile-count">{plural(n)}</span></span></a></li>')
    def first_with_img(lis, avoid=()):
        for l in lis:
            im = img(l)
            if im and im[0] not in avoid: return l
        return lis[0] if lis else None
    didx = {id(l): i for i, l in enumerate(dining)}
    def pick_dining(idxs, need_primary):
        for t in (lambda i: primary[i] or not need_primary, lambda i: True):
            for i in idxs:
                if img(dining[i]) and t(i): return dining[i]
        return dining[idxs[0]] if idxs else None
    def subhead(title, desc, canon):
        h = head
        h = re.sub(r'<title>.*?</title>', f'<title>{esc(title)} · BokenJapan</title>', h)
        h = re.sub(r'(<link rel="canonical" href=")[^"]+', lambda m: m.group(1) + canon, h)
        h = re.sub(r'(<meta property="og:url" content=")[^"]+', lambda m: m.group(1) + canon, h)
        h = re.sub(r'(<meta property="og:title" content=")[^"]+', lambda m: m.group(1) + esc(title) + ' · BokenJapan', h)
        h = re.sub(r'(<meta (?:name="description"|property="og:description") content=")[^"]+', lambda m: m.group(1) + esc(desc), h)
        h = h.replace('href="../../styles.css"', 'href="/styles.css"')
        h = re.sub(r'\s*<!--\s*Municipality boundaries:.*?-->', '', h, flags=re.S)
        return h
    def mast_abs(m): return m.replace('href="../"', f'href="/{pref}/"').replace('src="../../', 'src="/')
    BASE = f'https://bokenjapan.com/{PAGE}/'
    def absmedia(body, depth):  # list pages live deeper; keep media paths valid
        return body.replace('src="../../media/', 'src="/media/')
    def write(rel, doc):
        q = ROOT / PAGE / rel / 'index.html'; q.parent.mkdir(parents=True, exist_ok=True); q.write_text(doc)
    def subpage(rel, title, crumbs, h1, sub, body, desc):
        cr = ' / '.join([f'<a href="/">Japan</a>', f'<a href="/{pref}/">{esc(PREF)}</a>', f'<a href="/{PAGE}/">{esc(MUNI)}</a>'] + crumbs)
        return (subhead(title, desc, BASE + rel) + '</head>\n' + mast_abs(mast).replace('<body>', '<body class="hubbed">') +
                f'<main class="page-main">\n    <p class="crumb">{cr}</p>\n    <h1 class="page-title">{esc(h1)}</h1>\n    <p class="page-sub">{esc(sub)}</p>\n' + absmedia(body, 0) + '\n' + foot_noscript.replace('src="../../', 'src="/'))
    def plist(lis, h2): return f'<section class="place-section"><h2 class="visually-hidden">{esc(h2)}</h2><ul class="place-list">{"".join(lis)}</ul></section>'
    for d in glob.glob(str(ROOT / PAGE) + '/*/'): shutil.rmtree(d)
    SLUG = {'stay': 'stay', 'eat': 'eat', 'do': 'do', 'see': 'see', 'daily': 'day-to-day'}
    tiles = []
    for k2 in ['stay', 'eat', 'do', 'see', 'daily']:
        label, lis = SECT[k2]
        if not lis: continue
        rep = pick_dining([didx[id(l)] for l in lis], False) if k2 == 'eat' else first_with_img(lis, avoid=(cover,) if k2 in ('do', 'see') else ())
        t = tile(SLUG[k2] + '/', label, len(lis), rep)
        tiles.append(t.replace('src="../../media/', 'src="../../media/'))
        if k2 == 'eat': continue
        write(SLUG[k2], subpage(SLUG[k2] + '/', f'{label} · {MUNI}', [esc(label)], f'{label} in {MUNI}', f'{MUNI} · {PREF} · {plural(len(lis))}', plist(lis, label), f'{label} in {MUNI}, {PREF}: ranked places.'))
    etiles = []
    for k, lab in CAT:
        idxs = eat.get(k, [])
        if not idxs: continue
        lis = [dining[i] for i in idxs]; st['cat_' + k] += 1
        etiles.append(tile(CSLUG[k] + '/', lab, len(lis), pick_dining(idxs, k != 'other'), big=False).replace('src="../../media/', 'src="/media/'))
        write(f'eat/{CSLUG[k]}', subpage(f'eat/{CSLUG[k]}/', f'{lab} · Eat · {MUNI}', [f'<a href="/{PAGE}/eat/">Eat</a>', esc(lab)], lab, f'Eat in {MUNI} · {plural(len(lis))}', plist(lis, lab), f'{lab} in {MUNI}, {PREF}: ranked restaurants.'))
    if SECT['eat'][1]:
        nEat = len(SECT['eat'][1])
        write('eat', subpage('eat/', f'Eat · {MUNI}', ['Eat'], f'Eat in {MUNI}', f'{MUNI} · {PREF} · {plural(nEat)}',
              f'<section class="hub"><h2 class="visually-hidden">Cuisines</h2><ul class="hub-tiles hub-tiles-sm">{"".join(etiles)}</ul></section>', f'Restaurants in {MUNI}, {PREF}, by cuisine.'))
    secs = list(re.finditer(r'<section class="place-section">', src))
    start = secs[0].start(); end = src.rindex('</section>') + len('</section>')
    sn = re.search(r'<section class="place-section"><h2>Stay</h2><p class="stay-none">.*?</p></section>', src, re.S)
    hub = src[:start] + (sn.group(0) if sn and not stay else '') + f'<section class="hub"><h2 class="visually-hidden">Explore {esc(MUNI)}</h2><ul class="hub-tiles">{"".join(tiles)}</ul></section>' + src[end:]
    hub = hub.replace('<body>', '<body class="hubbed">', 1)
    p.write_text(hub); st['pages'] += 1
if __name__ == '__main__':
    for pref in A.pref:
        st = collections.Counter()
        for f in sorted(glob.glob(str(ROOT / pref / '*' / 'index.html'))):
            slug = f.split('/')[-2]
            build(pref, slug, st)
        print(pref, json.dumps(dict(st)), flush=True)
