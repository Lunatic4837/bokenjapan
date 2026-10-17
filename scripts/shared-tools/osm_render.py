#!/usr/bin/env python3
"""osm_render.py -- render Tabelog-free (OSM / official-site) dining records into the LIVE eat-page format.

  python3 osm_render.py --root <worktree> --pref okayama --data DIR [--towns a,b] [--select SEL.json] [--nophoto-csv CSV]

DIR holds osm_dining.py output: <slug>.json (+ media/). SEL.json (optional) = {slug: [rid, ...]} chosen cards per town.
Live format (https://bokenjapan.com/okayama/kurashiki/eat/): eat/index.html = cuisine hub tiles, eat/<cuisine>/index.html = card list.
New cards go into a SECOND <section class="place-section osm-dining"> on its own line after the existing list, so the
existing (Tabelog) card lines are never rewritten (git diff shows only additions + count lines). Cards:
  <li><a href=official|osm><p class=place-name>JA</p><img class=thumb ...></a><!-- photo-credit ... --><p class=place-blurb>EN</p>
  <p class=place-meta>Dining in {Town}</p><p class=place-desc>EN from OSM tags (+official-page text)</p>
  <!-- desc-source --><!-- sources: osm_url=..|official_url=.. --><!-- photo_search: {json} (photo-less cards) --></li>
Keys: osm_url / official_url, rid osm-n123 / osm-w123. Never '#N ranked'. Visible credit: 'OpenStreetMap contributors (ODbL)'.
Idempotent: re-running replaces the osm-dining sections. Existing Tabelog card HTML is never touched.
"""
import argparse, csv, glob, html as H, json, os, re, shutil, sys, unicodedata
from pathlib import Path

E = lambda s: H.escape(s or '', quote=True)
T = lambda s: H.escape(s or '', quote=False)
ORDER = ['seafood', 'meat', 'noodles', 'european', 'cafe', 'curry', 'casual', 'chinese-asian', 'izakaya-bars', 'sweets-bakeries', 'other-japanese', 'other']
LABEL = {'seafood': 'Japanese (seafood)', 'meat': 'Japanese (meat)', 'noodles': 'Japanese (noodles)', 'european': 'European', 'cafe': 'Cafe', 'curry': 'Curry',
         'casual': 'Casual', 'chinese-asian': 'Chinese & Asian', 'izakaya-bars': 'Izakaya & bars', 'sweets-bakeries': 'Sweets & bakeries',
         'other-japanese': 'Other Japanese', 'other': 'Other'}
# 2026-10-17: the per-card/section "© OpenStreetMap" paragraph is gone; ODbL attribution is a short footer line on every page that
# carries OSM-sourced cards (same text as scripts/site_chrome.py FOOT_DATA) plus the "Data and map credits" section on /photo-credits/.
CREDIT_P = ''
FOOT_DATA = '<p class="foot-data">Data: © <a href="https://www.openstreetmap.org/copyright" rel="noopener">OpenStreetMap contributors</a> (ODbL)</p>'
def ensure_foot_data(t):
    if 'class="foot-data"' in t: return t
    return re.sub(r'(<nav class="foot-legal"[^>]*>.*?</nav>)', lambda m: m.group(1) + '\n    ' + FOOT_DATA, t, count=1, flags=re.S)
MARK = 'osm-dining'

NOOD = {'ramen', 'udon', 'soba', 'noodle', 'tonkotsu', 'champon', 'somen'}
SEA = {'sushi', 'seafood', 'eel', 'unagi', 'fish', 'sashimi', 'kaisen'}
MEAT = {'yakiniku', 'yakitori', 'steak_house', 'steak', 'tonkatsu', 'chicken', 'beef', 'pork', 'barbecue', 'bbq', 'kushikatsu', 'hamburg_steak', 'shabu_shabu', 'sukiyaki', 'teppanyaki', 'beef_bowl', 'gyudon'}
EURO = {'italian', 'french', 'pizza', 'pasta', 'spanish', 'german', 'european', 'bistro', 'tapas', 'mediterranean', 'american', 'burger', 'hamburger', 'sandwich', 'steak_house_western', 'turkish', 'mexican', 'international'}
ASIA = {'chinese', 'korean', 'thai', 'indian', 'vietnamese', 'asian', 'gyoza', 'nepalese', 'taiwanese', 'ramen_chinese'}
SWEET = {'ice_cream', 'cake', 'donut', 'dessert', 'bakery', 'crepe', 'waffle', 'pancake', 'sweets', 'confectionery', 'patisserie', 'tea', 'bubble_tea'}
JPN = {'japanese', 'okonomiyaki', 'tempura', 'kaiseki', 'regional', 'oden', 'takoyaki', 'bento', 'rice_bowl', 'donburi', 'ryotei', 'set_meal', 'teishoku', 'hot_pot', 'nabe', 'tofu', 'okinawan'}

def _cat_one(x, am):
    if x == 'curry': return 'curry'
    if x in NOOD: return 'noodles'
    if x in SEA: return 'seafood'
    if x in MEAT: return 'meat'
    if x in SWEET: return 'cafe' if (am == 'cafe' and x in ('tea', 'bubble_tea')) else 'sweets-bakeries'
    if x in ('coffee_shop', 'coffee'): return 'cafe'
    if x in EURO: return 'european'
    if x in ASIA: return 'chinese-asian'
    if x in JPN: return 'other-japanese'
    if x in ('family', 'family_restaurant'): return 'casual'
    return None

def category(c):
    cs = [x.strip().lower().replace(' ', '_') for x in re.split(r'[;,]', c.get('cuisine') or '') if x.strip()]
    am = c.get('amenity', '')
    if am in ('bar', 'pub', 'izakaya', 'biergarten'): return 'izakaya-bars'
    if am == 'ice_cream': return 'sweets-bakeries'
    if cs and cs[0] == 'okonomiyaki': return 'other-japanese'
    for x in cs:
        r = _cat_one(x, am)
        if r and not (r == 'sweets-bakeries' and am == 'restaurant'): return r
    if am == 'cafe': return 'cafe'
    if cs and am == 'restaurant':
        for x in cs:
            r = _cat_one(x, am)
            if r: return r
    if am in ('fast_food', 'food_court') or (am == 'restaurant' and not cs): return 'casual'
    return 'other'

def nk(s): return re.sub(r'[\s\u3000・･\-–―ー~〜()（）「」『』【】\[\]&＆.,、。!！/／]', '', unicodedata.normalize('NFKC', s or '').lower())

def card_html(c, town_en, nophoto_rows, pref, slug):
    link = c.get('website') or c['osm_url']
    ja = c['name_ja']; en = c.get('name_en') or ja
    ph = c.get('img')
    img = ''; credit = ''
    if ph:
        img = f'<img class="thumb" src="/{E(ph)}" alt="{E(en)}" width="{c.get("img_w", 560)}" height="{c.get("img_h", 373)}" loading="lazy">'
        cr = c.get('img_credit') or ''
        if c.get('img_src') == 'official': cr = cr or f'Official website · Source {c.get("img_source_url") or c.get("website")}'
        credit = f'<!-- photo-credit: {E(cr)} -->'
    srcs = [f'osm_url={c["osm_url"]}'] + ([f'official_url={c["website"]}'] if c.get('website') else [])
    desc = c.get('desc_en') or ''
    ps = ''
    if not ph:
        ps = '<!-- photo_search: ' + json.dumps(c.get('photo_search') or {}, ensure_ascii=False).replace('--', '- -') + ' -->'
        nophoto_rows.append({'card_key': f'{pref}/{slug}|{c["rid"]}', 'name_ja': ja, 'card_name_on_page': ja, 'listing_url': link,
                             'photo_search': json.dumps(c.get('photo_search') or {}, ensure_ascii=False)})
    return (f'<li><a href="{E(link)}"><p class="place-name">{T(ja)}</p>{img}</a>{credit}<p class="place-blurb">{T(en)}</p>'
            f'<p class="place-meta">Dining in {E(town_en)}</p>'
            + (f'<p class="place-desc">{T(desc)}</p><!-- desc-source: {E(c["osm_url"])} -->' if desc else '')
            + f'<!-- sources: {" | ".join(srcs)} -->{ps}</li>')

def jsonld_items(cards, town_en, slug, pref):
    items = []
    for i, c in enumerate(cards, 1):
        items.append({'@type': 'ListItem', 'position': i, 'item': {'@type': 'Restaurant', 'name': c['name_ja'], 'alternateName': c.get('name_en') or c['name_ja'],
                      'url': c.get('website') or c['osm_url'], 'containedInPlace': {'@id': f'https://bokenjapan.com/{pref}/{slug}/#place'}}})
    return items

def count_li(t): return len(re.findall(r'<li>', re.sub(r'<section class="hub">.*?</section>', '', t, flags=re.S)))
def plural(n): return f'{n} place' + ('' if n == 1 else 's')

def strip_osm(t):
    """Remove a previous osm-dining section line, its JSON-LD line and the hub credit line."""
    t = re.sub(r'\n?<section class="place-section osm-dining"[^\n]*</section>', '', t)
    t = re.sub(r'\n?<!-- bj-jsonld-osm -->[^\n]*', '', t)
    t = re.sub(r'\n?<p class="osm-credit"[^\n]*</p>', '', t)
    return t

def update_cuisine_page(t, new_cards, town_en, slug, pref, nophoto_rows):
    t = strip_osm(t)
    lis = ''.join(card_html(c, town_en, nophoto_rows, pref, slug) for c in new_cards)
    sec = (f'<section class="place-section osm-dining" style="margin-top:0"><h2 class="visually-hidden">More places in {E(town_en)}</h2>'
           f'<ul class="place-list" style="border-top:0">{lis}</ul>{CREDIT_P}</section>')
    m = re.search(r'</section>\n', t[t.index('<section class="place-section"'):])
    end = t.index('<section class="place-section"') + m.end()
    t = t[:end] + sec + '\n' + t[end:]
    n = count_li(t)
    t = re.sub(r'(<title>[^<]*?: )\d+ places?(, with source links)', lambda m: f'{m.group(1)}{plural(n)}{m.group(2)}', t, count=1)
    t = re.sub(r'(<p class="page-sub">[^<]*· )\d+ places?(</p>)', lambda m: f'{m.group(1)}{plural(n)}{m.group(2)}', t, count=1)
    ld = {'@context': 'https://schema.org', '@type': 'ItemList', 'name': f'More places to eat in {town_en}, Okayama', 'numberOfItems': len(new_cards), 'itemListElement': jsonld_items(new_cards, town_en, slug, pref)}
    t = t.replace('</head>', f'<!-- bj-jsonld-osm --><script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>\n</head>', 1)
    return ensure_foot_data(t), n

def new_cuisine_page(template, cat, town_en, slug, pref, new_cards, nophoto_rows, pref_en):
    """Build eat/<cat>/index.html for a cuisine the town doesn't have yet, from another cuisine page of the same town (head/foot chrome only)."""
    t = strip_osm(template)
    old_slug = re.search(r'/eat/([a-z\-]+)/"', t).group(1)
    old_label = re.search(r'<h1 class="page-title">(.*?) in ', t).group(1)
    lab = E(LABEL[cat])
    head, rest = t.split('<!-- bj-jsonld -->', 1)
    head = head.replace(f'/eat/{old_slug}/', f'/eat/{cat}/').replace(old_label, lab)
    ld_end = rest.index('<!-- /bj-jsonld -->')
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', rest[:ld_end], re.S).group(1))
    g = ld['@graph']; page = g[0]; page['@id'] = page['@id'].replace(f'/eat/{old_slug}/', f'/eat/{cat}/'); page['url'] = page['url'].replace(f'/eat/{old_slug}/', f'/eat/{cat}/')
    page['name'] = f'{LABEL[cat]} in {town_en}, {pref_en}: {len(new_cards)} places, with source links'
    bc = page['breadcrumb']['itemListElement'][-1]; bc['name'] = LABEL[cat]; bc['item'] = bc['item'].replace(f'/eat/{old_slug}/', f'/eat/{cat}/')
    page.pop('isBasedOn', None); page.pop('citation', None)
    page['isBasedOn'] = ['https://www.openstreetmap.org/copyright']
    g[:] = [x for x in g if x.get('@type') != 'ItemList']
    jl = f'<!-- bj-jsonld --><script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>'
    body = rest[ld_end:]
    body = body[:body.index('<section class="place-section"')] if '<section class="place-section"' in body else body
    # body now: '<!-- /bj-jsonld -->...<main>...<h1>...<p class=page-sub>' ; swap labels/slugs/count
    body = body.replace(f'/eat/{old_slug}/', f'/eat/{cat}/').replace(old_label, lab)
    body = re.sub(r'(<p class="page-sub">[^<]*· )\d+ places?(</p>)', lambda m: f'{m.group(1)}{plural(len(new_cards))}{m.group(2)}', body, count=1)
    head = re.sub(r'(<title>[^<]*?: )\d+ places?(, with source links)', lambda m: f'{m.group(1)}{plural(len(new_cards))}{m.group(2)}', head, count=1)
    tail = template[template.index('<!-- bj-nav -->'):]
    tail = strip_osm(tail)
    tail = re.sub(r'\n[ \t]*<p>Pages are compiled from publicly available local sources\.</p>', '', tail)  # 2026-10-17: line removed site-wide
    tail = re.sub(r'(<nav class="foot-legal"[^>]*>.*?)(</nav>)', lambda m: m.group(0) if 'photo-credits' in m.group(0) else m.group(1) + ' · <a href="/photo-credits/">Photo credits</a>' + m.group(2), tail, count=1, flags=re.S)  # footer Photo credits link
    lis = ''.join(card_html(c, town_en, nophoto_rows, pref, slug) for c in new_cards)
    sec = (f'<section class="place-section osm-dining"><h2 class="visually-hidden">{lab}</h2><ul class="place-list">{lis}</ul>{CREDIT_P}</section>\n')
    ld2 = {'@context': 'https://schema.org', '@type': 'ItemList', 'name': f'{LABEL[cat]} in {town_en}, {pref_en}', 'numberOfItems': len(new_cards), 'itemListElement': jsonld_items(new_cards, town_en, slug, pref)}
    out = head + jl + body + sec + tail
    out = out.replace('</head>', f'<!-- bj-jsonld-osm --><script type="application/ld+json">{json.dumps(ld2, ensure_ascii=False)}</script>\n</head>', 1)
    return ensure_foot_data(out)

def rebuild_hub(t, cats, town_en, total, first_img):
    """Update tile counts, add tiles for new cuisines, title/page-sub/JSON-LD totals, credit line."""
    t = strip_osm(t)
    m = re.search(r'(<section class="hub"><h2 class="visually-hidden">Cuisines</h2><ul class="hub-tiles hub-tiles-sm">)(.*?)(</ul></section>)', t, re.S)
    tiles = {mm.group(1): mm.group(0) for mm in re.finditer(r'<li><a class="hub-tile hub-tile-sm" href="([^"]+)/">.*?</li>', m.group(2), re.S)}
    for cat, n in cats.items():
        if cat in tiles:
            tiles[cat] = re.sub(r'(<span class="hub-tile-count">)[^<]*(</span>)', lambda mm: f'{mm.group(1)}{plural(n)}{mm.group(2)}', tiles[cat])
        else:
            im = first_img.get(cat)
            img = f'<img src="/{E(im[0])}" alt="{E(im[1])}" width="{im[2]}" height="{im[3]}"  loading="lazy" decoding="async">' if im else ''
            tiles[cat] = (f'<li><a class="hub-tile hub-tile-sm" href="{cat}/">{img}<span class="hub-tile-label"><span class="hub-tile-name">{E(LABEL[cat])}</span>'
                          f'<span class="hub-tile-count">{plural(n)}</span></span></a></li>')
    keys = [k for k in tiles if k in cats or True]
    seq = [k for k in ORDER if k in tiles] + [k for k in tiles if k not in ORDER]
    t = t[:m.start(2)] + ''.join(tiles[k] for k in seq) + t[m.end(2):]
    t = re.sub(r'(Where to eat in [^:<"]*: )\d+( restaurants and caf)', lambda mm: f'{mm.group(1)}{total}{mm.group(2)}', t)
    t = re.sub(r'(<p class="page-sub">[^<]*· )\d+ places?(</p>)', lambda mm: f'{mm.group(1)}{plural(total)}{mm.group(2)}', t, count=1)
    return ensure_foot_data(t)

def update_town_index(t, total):
    t = re.sub(r'\d+ places to eat', f'{total} places to eat', t)
    t = re.sub(r'(<a class="hub-tile" href="eat/">.*?<span class="hub-tile-name">Eat</span><span class="hub-tile-count">)[^<]*(</span>)', lambda m: f'{m.group(1)}{plural(total)}{m.group(2)}', t, count=1, flags=re.S)
    return t

def run(a):
    root = Path(a.root); pref = a.pref; data = Path(a.data)
    sel = json.load(open(a.select)) if a.select else None
    nophoto_rows = []; summary = {}
    for f in sorted(glob.glob(str(data / '*.json'))):
        slug = Path(f).stem
        if slug.startswith('_') or (a.towns and slug not in a.towns.split(',')): continue
        d = json.load(open(f)); meta = d['meta']; town_en = meta['name_en']
        cards = d['dining']
        if sel is not None:
            if slug not in sel: continue
            cards = [c for c in cards if c['rid'] in set(sel[slug])]
        elif meta.get('selected'):   # osm_dining.py --need N already chose photo > official site > rest (non-chain first)
            cards = [c for c in cards if c['rid'] in set(meta['selected'])]
        eatdir = root / pref / slug / 'eat'
        if not (eatdir / 'index.html').exists(): print('no eat page for', slug); continue
        pages = {p.parent.name: p.read_text(encoding='utf-8') for p in eatdir.glob('*/index.html')}
        existing = {nk(n) for t in pages.values() for n in re.findall(r'place-name">([^<]*)</p>', strip_osm(t)) if nk(n)}
        by = {}
        added = []
        for c in cards:
            k = nk(c['name_ja'])
            if any(len(k) >= 3 and len(e) >= 3 and (k in e or e in k) for e in existing) or k in existing: continue
            by.setdefault(category(c), []).append(c); added.append(c)
        # media
        mdir = data / 'media'
        for c in added:
            if c.get('img'):
                src = mdir / Path(c['img']).name
                if src.exists(): shutil.copy2(src, root / 'media' / src.name)
                else: c['img'] = ''; c.setdefault('photo_search', {}).setdefault('notes', {})['render'] = 'media-file-missing'
        by = {}
        for c in added: by.setdefault(category(c), []).append(c)
        counts = {}; first_img = {}
        for cat, cs in by.items():
            cs.sort(key=lambda c: (not c.get('img'), not c.get('website'), c['name_ja']))
            p = eatdir / cat / 'index.html'
            if cat in pages:
                new, n = update_cuisine_page(pages[cat], cs, town_en, slug, pref, nophoto_rows)
            else:
                tmpl = next(iter(pages.values()))
                new = new_cuisine_page(tmpl, cat, town_en, slug, pref, cs, nophoto_rows, a.pref_en); n = len(cs)
                p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(new, encoding='utf-8'); pages[cat] = new
            ph = next((c for c in cs if c.get('img')), None)
            if ph: first_img[cat] = (ph['img'], ph.get('name_en') or ph['name_ja'], ph.get('img_w', 560), ph.get('img_h', 373))
        cats = {cat: count_li(t) for cat, t in pages.items()}
        total = sum(cats.values())
        hp = eatdir / 'index.html'; ht = hp.read_text(encoding='utf-8')
        hp.write_text(rebuild_hub(ht, cats, town_en, total, first_img), encoding='utf-8')
        ip = root / pref / slug / 'index.html'
        ip.write_text(update_town_index(ip.read_text(encoding='utf-8'), total), encoding='utf-8')
        summary[slug] = {'added': len(added), 'with_photo': sum(1 for c in added if c.get('img')), 'total': total, 'cats': {k: len(v) for k, v in by.items()}}
        print(slug, summary[slug], flush=True)
    if a.nophoto_csv and nophoto_rows:
        p = Path(a.nophoto_csv); new = not p.exists()
        old = []
        if not new:
            old = list(csv.DictReader(open(p, encoding='utf-8')))
            keep = {r['card_key'] for r in nophoto_rows}; old = [r for r in old if r['card_key'] not in keep]
        with open(p, 'w', newline='', encoding='utf-8') as fh:
            w = csv.DictWriter(fh, fieldnames=['card_key', 'name_ja', 'card_name_on_page', 'listing_url', 'photo_search']); w.writeheader()
            for r in old + nophoto_rows: w.writerow(r)
    json.dump(summary, sys.stdout.buffer.raw if False else open(os.devnull, 'w'))
    return summary

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True); ap.add_argument('--pref', required=True); ap.add_argument('--data', required=True)
    ap.add_argument('--towns'); ap.add_argument('--select'); ap.add_argument('--nophoto-csv'); ap.add_argument('--pref-en', default='Okayama')
    run(ap.parse_args())
