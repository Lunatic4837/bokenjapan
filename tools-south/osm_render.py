#!/usr/bin/env python3
"""osm_render.py - render osm_dining.py output into a checkout in the exact live card markup.

  python3 osm_render.py <pref> <slug> [<slug>...] [--tree DIR] [--json-dir DIR] [--all] [--dry-run]

For each town: copies photo files into <tree>/media/, adds an `osm-dining` <section> to each category page
(<tree>/<pref>/<slug>/eat/<cat>/index.html; created from the town's own existing category page when missing),
photo-less cards go in a second "More places in <Town>" section and carry a photo_search comment, updates
title/sub counts, the hub page tiles (+ new category tiles, canonical order) and the single ODbL footer note on the hub
page, and adds new eat URLs to <tree>/sitemaps/<pref>.xml.  Idempotent: re-running replaces the osm-dining sections.
Existing (Tabelog-era) cards are never touched or removed.

Card (live template):
<li><a href="OFFICIAL or OSM node page"><p class="place-name">JA name</p><img class="thumb" ...></a><!-- photo-credit: ... -->
<p class="place-blurb">EN name</p><p class="place-meta">Dining in Town</p><p class="place-desc">one natural sentence</p>
<!-- desc-source: osm url --><!-- sources: osm_url=... | official_url=... --><!-- photo_search: {...} (photo-less only) --></li>
No visible per-card credit; the ODbL note is one footer-style paragraph per hub page.
"""
import argparse, datetime, html as H, json, re, shutil, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bjlib as L

DAYS = {'Mo': 'Mon', 'Tu': 'Tue', 'We': 'Wed', 'Th': 'Thu', 'Fr': 'Fri', 'Sa': 'Sat', 'Su': 'Sun', 'PH': 'public holidays'}
_D = r'(?:Mo|Tu|We|Th|Fr|Sa|Su|PH)'
_DR = rf'{_D}(?:-{_D})?'
_T = r'\d{1,2}:\d{2}-\d{1,2}:\d{2}'
CREDIT_P = ('<p class="osm-credit" style="margin:.85rem 0 0;font-size:.85rem;color:var(--muted)">Dining listings marked \u201cDining in\u201d use data \u00a9 '
            '<a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors (ODbL)</a>; photos are from each venue\u2019s own site or '
            'Wikimedia Commons as credited.</p>\n')

def _days(d):
    if not d or d == 'Mo-Su': return 'daily'
    return ', '.join('-'.join(DAYS[x] for x in part.split('-')) for part in d.split(','))

def hours_en(oh):
    """OSM opening_hours -> short English sentence, only when it parses cleanly (no guessing)."""
    oh = (oh or '').strip()
    if not oh: return ''
    if oh == '24/7': return 'Open 24 hours, every day.'
    out = []
    for seg in [x.strip() for x in oh.split(';') if x.strip()]:
        m = re.fullmatch(rf'((?:{_DR})(?:,{_DR})*)?\s*({_T}(?:,\s*{_T})*)', seg)
        if m: out.append(f"{_days(m.group(1))} {re.sub(r',\s*', ', ', m.group(2))}"); continue
        m = re.fullmatch(rf'((?:{_DR})(?:,{_DR})*)\s+off', seg)
        if m: out.append(f'closed {_days(m.group(1))}'); continue
        return ''
    s = '; '.join(out)
    if len(out) > 3 or len(s) > 110: return ''
    return 'Open ' + s + '.' if not s.startswith('closed') else s[0].upper() + s[1:] + '.'

def desc_en(c, town):
    area = c.get('area')
    place = f'{area}, {town}' if area and area.lower() != town.lower() else town
    parts = [f"{c['noun']} in {place}."]
    h = hours_en(c.get('opening_hours'))
    if h: parts.append(h)
    p = (c.get('price') or '').strip()
    if p and re.fullmatch(r'[\w\u00a5$ ,.\-~\u301c\u2013]{1,30}', p) and not L.CJK.search(p): parts.append(f'Price band: {p}.')
    return ' '.join(parts)

def card_html(c, town, photo_dims):
    e = L.esc
    href = c['website'] or c['osm_url']
    img, cred = '', ''
    ph = c.get('photo')
    if ph:
        w, h = photo_dims
        img = f'<img class="thumb" src="/{ph["file"]}" alt="{e(c["name_en"])}" width="{w}" height="{h}" loading="lazy">'
        cred = f'<!-- photo-credit: {ph["credit"]} \u00b7 Source {ph["source"]} -->'
    src = f'osm_url={c["osm_url"]}' + (f' | official_url={c["website"]}' if c['website'] else '')
    ps = '' if ph else f'<!-- photo_search: {json.dumps(c.get("photo_search") or {"tried": ["none"], "result": None, "notes": {}}, ensure_ascii=False)} -->'
    return (f'<li><a href="{e(href)}"><p class="place-name">{e(c["name_ja"])}</p>{img}</a>{cred}'
            f'<p class="place-blurb">{e(c["name_en"])}</p><p class="place-meta">Dining in {e(town)}</p>'
            f'<p class="place-desc">{e(desc_en(c, town))}</p><!-- desc-source: {c["osm_url"]} --><!-- sources: {src} -->{ps}</li>')

SEC_RE = re.compile(r'<section class="place-section osm-dining"[^>]*>.*?</section>\n?', re.S)

def sections(cards, town, cat_label, dims):
    photo = [c for c in cards if c.get('photo')]; bare = [c for c in cards if not c.get('photo')]
    out = ''
    if photo:
        out += (f'<section class="place-section osm-dining"><h2 class="visually-hidden">{L.esc(cat_label)}</h2><ul class="place-list">'
                + ''.join(card_html(c, town, dims[c['osmid']]) for c in photo) + '</ul></section>\n')
    if bare and not photo:
        out += (f'<section class="place-section osm-dining"><h2 class="visually-hidden">{L.esc(cat_label)}</h2><ul class="place-list">'
                + ''.join(card_html(c, town, None) for c in bare) + '</ul></section>\n')
    elif bare:
        out += (f'<section class="place-section osm-dining" style="margin-top:0"><h2 class="visually-hidden">More places in {L.esc(town)}</h2>'
                '<ul class="place-list" style="border-top:0">' + ''.join(card_html(c, town, None) for c in bare) + '</ul></section>\n')
    return out

def count_cards(t): return len(re.findall(r'<li><a href="[^"]*"><p class="place-name">', t))

def set_counts(t, n, kind):
    """kind 'hub' or 'cat'. Rewrites the title and page-sub place counts."""
    if kind == 'hub':
        t = re.sub(r'(<title>Where to eat in [^<:]+: )\d+( restaurants)', rf'\g<1>{n}\2', t, 1)
    else:
        t = re.sub(r'(<title>[^<]*?: )\d+ places?(, with source links)', rf'\g<1>{L.plural(n)}\2', t, 1)
    return re.sub(r'(<p class="page-sub">[^<]*· )\d+ places?', rf'\g<1>{L.plural(n)}', t, 1)

def _sub(pat, pre, text, t, post=''):
    return re.sub(pat, lambda m: (m.group(1) if pre else '') + text + (m.group(2) if post else ''), t, 1, flags=re.S)

def new_cat_page(template, town, pref_en, cat, label, n, pref, slug):
    t = template
    lab = H.escape(label, quote=False)
    url = f'https://bokenjapan.com/{pref}/{slug}/eat/{cat}/'
    desc = f'{lab} in {town}, {pref_en}: things to do, food and stays, {pref_en}: ranked restaurants.'
    t = _sub(r'<title>.*?</title>', 0, f'<title>{lab} in {town}, {pref_en}: {L.plural(n)}, with source links \u00b7 BokenJapan</title>', t)
    t = _sub(r'(<meta name="description" content=")[^"]*', 1, desc, t)
    t = _sub(r'(<link rel="canonical" href=")[^"]*', 1, url, t)
    t = _sub(r'(<meta property="og:title" content=")[^"]*', 1, f'{lab} \u00b7 Eat \u00b7 {town}, {pref_en}: things to do, food and stays \u00b7 BokenJapan', t)
    t = _sub(r'(<meta property="og:description" content=")[^"]*', 1, desc, t)
    t = _sub(r'(<meta property="og:url" content=")[^"]*', 1, url, t)
    t = _sub(r'(<span aria-current="page">)[^<]*(</span></nav><style>)', 1, lab, t, 1)
    t = _sub(r'(</a> / )[^<]*(</p>\n    <h1)', 1, lab, t, 1)
    t = _sub(r'<h1 class="page-title">[^<]*</h1>', 0, f'<h1 class="page-title">{lab} in {town}, {pref_en}</h1>', t)
    t = re.sub(r'<section class="place-section">.*?</section>\n?', '', t, 1, flags=re.S)
    t = SEC_RE.sub('', t)
    return set_counts(t, n, 'cat')

def tile_html(cat, label, n, c, dims):
    img = ''
    if c:
        w, h = dims
        img = f'<img src="/{c["photo"]["file"]}" alt="{L.esc(c["name_en"])}" width="{w}" height="{h}"  loading="lazy" decoding="async">'
    return (f'<li><a class="hub-tile hub-tile-sm" href="{cat}/">{img}<span class="hub-tile-label"><span class="hub-tile-name">{H.escape(label, quote=False)}</span>'
            f'<span class="hub-tile-count">{L.plural(n)}</span></span></a></li>')

def render_town(pref, slug, A):
    jf = Path(A.json_dir) / pref / f'{slug}.json'
    d = json.load(open(jf))
    tree = Path(A.tree); eat = tree / pref / slug / 'eat'
    town, pref_en = d['town_en'], d['pref_en']
    cards = [c for c in d['cards'] if c['selected'] or A.all]
    from PIL import Image
    dims = {}; media_src = Path(A.json_dir) / 'media'
    for c in cards:
        if c.get('photo'):
            src = media_src / Path(c['photo']['file']).name
            with Image.open(src) as im: dims[c['osmid']] = im.size
            if not A.dry_run:
                (tree / 'media').mkdir(exist_ok=True); shutil.copy2(src, tree / 'media' / src.name)
    bycat = {}
    for c in cards: bycat.setdefault(c['category'], []).append(c)
    hub = (eat / 'index.html').read_text(encoding='utf-8')
    template = next((p.read_text(encoding='utf-8') for p in sorted(eat.glob('*/index.html'))), None)
    cat_counts, newcats = {}, []
    for cat in bycat:
        label = L.CAT_LABEL[cat]; f = eat / cat / 'index.html'
        if f.exists(): t = SEC_RE.sub('', f.read_text(encoding='utf-8'))
        else:
            if template is None: print(f'  ! no template page for {pref}/{slug}; skipping {cat}'); continue
            t = new_cat_page(template, town, pref_en, cat, label, 0, pref, slug); newcats.append(cat)
        base = count_cards(t)
        group = sorted(bycat[cat], key=lambda c: (not c.get('photo'), not c['website'], c['name_en'].lower()))
        sec = sections(group, town, label, dims)
        n = base + len(group)
        i = t.find('<!-- bj-nav -->')
        t = t[:i] + sec + t[i:]
        t = set_counts(t, n, 'cat')
        cat_counts[cat] = n
        if not A.dry_run:
            f.parent.mkdir(parents=True, exist_ok=True); f.write_text(t, encoding='utf-8')
    # hub: counts, tiles, credit note
    hub = SEC_RE.sub('', hub)
    tiles = {m.group(1): m for m in re.finditer(r'<li><a class="hub-tile hub-tile-sm" href="([^"/]+)/">.*?</a></li>', hub, re.S)}
    tile_n = {}
    for cat, m in tiles.items():
        k = re.search(r'hub-tile-count">(\d+) place', m.group(0)); tile_n[cat] = int(k.group(1)) if k else 0
    for cat, n in cat_counts.items():
        if cat in tile_n:
            old = tiles[cat].group(0); base = tile_n[cat]
            # keep hub counts idempotent: recompute from the category page itself
            new = re.sub(r'hub-tile-count">\d+ places?', f'hub-tile-count">{L.plural(n)}', old)
            hub = hub.replace(old, new); tile_n[cat] = n
    allt = {m.group(1): m.group(0) for m in re.finditer(r'<li><a class="hub-tile hub-tile-sm" href="([^"/]+)/">.*?</a></li>', hub, re.S)}
    for cat in cat_counts:
        if cat not in allt:
            pc = next((c for c in sorted(bycat[cat], key=lambda c: not c.get('photo')) if c.get('photo')), None)
            allt[cat] = tile_html(cat, L.CAT_LABEL[cat], cat_counts[cat], pc, dims.get(pc['osmid']) if pc else None); tile_n[cat] = cat_counts[cat]
    ordered = ''.join(allt[c] for c in sorted(allt, key=lambda c: L.CAT_ORDER.get(c, 99)))
    hub = re.sub(r'(<ul class="hub-tiles hub-tiles-sm">).*?(</ul></section>)', lambda m: m.group(1) + ordered + m.group(2), hub, 1, flags=re.S)
    total = sum(tile_n.values())
    hub = set_counts(hub, total, 'hub')
    if 'class="osm-credit"' not in hub:
        i = hub.find('<!-- bj-nav -->'); hub = hub[:i] + CREDIT_P + hub[i:]
    if not A.dry_run: (eat / 'index.html').write_text(hub, encoding='utf-8')
    # sitemap
    smp = tree / 'sitemaps' / f'{pref}.xml'; added = []
    if smp.exists() and not A.dry_run:
        sm = smp.read_text(encoding='utf-8'); today = datetime.date.today().isoformat()
        for u in [f'https://bokenjapan.com/{pref}/{slug}/eat/'] + [f'https://bokenjapan.com/{pref}/{slug}/eat/{c}/' for c in cat_counts]:
            if f'<loc>{u}</loc>' not in sm:
                sm = sm.replace('</urlset>', f'<url><loc>{u}</loc><lastmod>{today}</lastmod></url>\n</urlset>'); added.append(u)
        smp.write_text(sm, encoding='utf-8')
    n_ph = sum(1 for c in cards if c.get('photo'))
    print(f'{pref}/{slug}: {len(cards)} new cards ({n_ph} with photo), categories {dict(sorted(cat_counts.items()))}, new category pages {newcats}, hub total {total}, sitemap +{len(added)}')
    return dict(cards=len(cards), photos=n_ph, hub_total=total, new_pages=newcats, sitemap_added=added)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pref'); ap.add_argument('slugs', nargs='+')
    ap.add_argument('--tree', default=L.DEFAULT_TREE); ap.add_argument('--json-dir', default='/workspace/p1/scratch/osm-dining/out')
    ap.add_argument('--all', action='store_true', help='render every candidate, not only the selected ones'); ap.add_argument('--dry-run', action='store_true')
    A = ap.parse_args()
    for s in A.slugs: render_town(A.pref, s, A)

if __name__ == '__main__':
    main()
