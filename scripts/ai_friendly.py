#!/usr/bin/env python3
"""Make bokenjapan.com friendly to AI assistants and search engines. Idempotent and re-runnable.

Usage (from the gh-pages checkout root):
    python3 scripts/ai_friendly.py [--root .] [--check]
  --check  only report which files would change (exit 1 if any), write nothing.

Generates: llms.txt, llms-full.txt, robots.txt, sitemap.xml (flat; scripts/split_sitemap.py turns it into an index + sitemaps/<pref>.xml), data/index.json,
data/prefectures.json, data/<pref>.json, data/README.md. In every HTML page it rewrites
only marked blocks (<!-- bj-jsonld -->..<!-- /bj-jsonld -->, bj-crumbs, bj-nav, bj-meta),
the <title> and the page H1, all derived from facts already on that page (breadcrumb,
official links, place lists) plus scripts/town-geo.json coordinates. Also replaces the
text label '@boken_japan' with '@bokenjapan' (email addresses untouched).
Files are processed one at a time (streamed); only small per-town summaries are kept,
and each prefecture's data file is flushed as soon as its directory has been walked.
"""
import os, re, json, html, sys, datetime, subprocess

ROOT = sys.argv[sys.argv.index('--root') + 1] if '--root' in sys.argv else '.'
CHECK = '--check' in sys.argv
BASE = 'https://bokenjapan.com/'
SAME = ['https://www.instagram.com/bokenjapan/',  # X (@bokenjapan) is left out until the account is confirmed live (homepage shows it unlinked)
        
        'https://www.tiktok.com/@bokenjapan', 'https://www.facebook.com/profile.php?id=61595415860080']
SKIP = {'.git', 'media', 'go', 'data', 'scripts', 'node_modules'}
SECTIONS = {  # dir -> (label, schema type, json key)
    'see': ('Sights', 'TouristAttraction', 'sights'),
    'do': ('Things to do', 'TouristAttraction', 'activities'),
    'eat': ('Places to eat', 'Restaurant', 'food'),
    'stay': ('Places to stay', 'LodgingBusiness', 'stays'),
    'day-to-day': ('Day-to-day services', 'LocalBusiness', 'day_to_day'),
    'access': ('Getting there', None, 'access'),
}
ORDER = ['see', 'do', 'eat', 'stay', 'access', 'day-to-day']
BLOCKS = [('bj-jsonld', 'head'), ('bj-meta', 'head'), ('bj-crumbs', None), ('bj-nav', None)]
LEGACY = [('<!-- bj-jsonld:start -->', '<!-- bj-jsonld:end -->'), ('<!-- bj-nav:start -->', '<!-- bj-nav:end -->'),
          ('<!-- bj-meta:start -->', '<!-- bj-meta:end -->')]
changed = []

def rd(p):
    with open(p, encoding='utf-8') as f: return f.read()
def wr(rel, s):
    p = os.path.join(ROOT, rel)
    if os.path.exists(p) and rd(p) == s: return
    changed.append(rel)
    if CHECK: return
    os.makedirs(os.path.dirname(p) or '.', exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f: f.write(s)
def wj(rel, o): wr(rel, json.dumps(o, ensure_ascii=False, indent=1) + '\n')
def txt(s): return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()
def esc(s): return html.escape(s, quote=True)
def url(rel): return BASE + (rel[:-10] if rel.endswith('index.html') else rel)

# ---- geo: drop OSM hits whose matched name is not the municipality itself
GEO = {}
gp = os.path.join(ROOT, 'scripts/town-geo.json')
if os.path.exists(gp):
    for k, v in json.load(open(gp, encoding='utf-8')).items():
        src = v.get('src', '')
        if src.startswith('osm:') and not src[4:].startswith(v.get('ja', '\0')): continue
        GEO[k] = v

# ---- dateModified: last git commit touching the file, ignoring this script's own commits
def git_dates():
    try:
        out = subprocess.run(['git', '-C', ROOT, 'log', '--format=@%cs', '--name-only', '--invert-grep', '-E',
                              '--grep=\\[(ai|agent)-friendly\\]|AI-agent friendly site', 'HEAD'],
                             capture_output=True, text=True).stdout
    except Exception: return {}
    d, cur = {}, None
    for l in out.splitlines():
        if l.startswith('@'): cur = l[1:]
        elif l and l not in d: d[l] = cur
    return d
DATES = git_dates()
def modified(rel):
    if rel in DATES: return DATES[rel]
    return datetime.date.fromtimestamp(os.path.getmtime(os.path.join(ROOT, rel))).isoformat()

def pages():
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = sorted(d for d in dn if d not in SKIP and not d.startswith('.'))
        for f in sorted(fn):
            if f.endswith('.html'): yield os.path.relpath(os.path.join(dp, f), ROOT).replace(os.sep, '/')

def strip(s):
    for a, b in LEGACY: s = re.sub(re.escape(a) + r'.*?' + re.escape(b) + r'\n?', '', s, flags=re.S)
    for n, _ in BLOCKS: s = re.sub(r'<!-- %s -->.*?<!-- /%s -->\n?' % (n, n), '', s, flags=re.S)
    return s

def crumb(s):
    """Names along the page breadcrumb (first = home). Reads the original p.crumb (kept, hidden by our nav)."""
    m = re.search(r'(?s)<p class="crumb"[^>]*>(.*?)</p>', s)
    return [txt(x) for x in re.split(r'\s(?:/|›)\s', m.group(1))] if m else []

def items(s):
    out = []
    for li in re.finditer(r'(?s)<li>(.*?)</li>', s):
        b = li.group(1); n = re.search(r'(?s)<p class="place-name">(.*?)</p>', b)
        if not n: continue
        a = re.search(r'<a href="(https?://[^"]+)"', b)
        bl = re.search(r'(?s)<p class="place-blurb">(.*?)</p>', b)
        de = re.search(r'(?s)<p class="place-desc">(.*?)</p>', b)
        it = {'name': txt(n.group(1))}
        if bl and txt(bl.group(1)): it['name_en'] = txt(bl.group(1))
        if de and txt(de.group(1)): it['description'] = txt(de.group(1))
        if a: it['source_url'] = a.group(1)
        out.append(it)
    return out

def official(s):
    m = re.search(r'(?s)<section class="meta-block"><h2>Official</h2>(.*?)</section>', s)
    if not m: return None
    b = m.group(1)
    o = {'links': [{'label': txt(x.group(2)), 'url': x.group(1)} for x in re.finditer(r'<a href="(https?://[^"]+)"[^>]*>(.*?)</a>', b)]}
    for d in re.finditer(r'(?s)<dt>(.*?)</dt><dd>(.*?)</dd>', b): o[txt(d.group(1)).lower()] = txt(d.group(2))
    return o

def kind(parts):
    n = len(parts) - 1  # dirs
    if parts == ['index.html']: return 'home'
    if parts[-1] != 'index.html': return 'other'
    if 'photo-credits' in parts[:-1]: return 'other'  # credit pages (/photo-credits/, /<pref>/photo-credits/): indexed in the sitemap, never rewritten, never counted as a town
    if n == 1: return 'pref'
    if n == 2: return 'town'
    if n == 3 and parts[2] in SECTIONS: return 'section'
    if n == 4 and parts[2] in SECTIONS: return 'sub'
    return 'other'

def plural(n, one, many): return f'{n} {one if n == 1 else many}'

# =============== pass 1: names, per-town summaries, data files (flushed per prefecture)
NAMES, SIB, TOWNSEC, COUNT = {}, {}, {}, {}
# Stay pages that only list a neighbouring town's lodging (stay-none note): titled 'Stays near X', never counted as in X
NEAR_RX = re.compile(r'class="stay-none">.*?nearest options in <a href="(?:https://bokenjapan\.com)?/([^/"]+)/([^/"]+)/">([^<]+)</a>', re.S)
NEAR = {}
prefs, cur_pref, cur_towns = {}, None, {}
today = datetime.date.today().isoformat()

def flush(pf):
    if not pf or pf not in prefs: return
    ts = [cur_towns[t] for t in sorted(cur_towns)]
    prefs[pf]['town_count'] = len(ts)
    prefs[pf]['counts'] = {SECTIONS[x][2]: sum(len(t.get(SECTIONS[x][2], [])) for t in ts) for x in ORDER}  # items listed on its town pages
    prefs[pf]['date_modified'] = max([t.get('date_modified') or '' for t in ts] or ['']) or None
    wj(f'data/{pf}.json', {'prefecture': prefs[pf]['name'], 'slug': pf, 'url': prefs[pf]['url'], 'towns': ts})

for rel in pages():
    parts = rel.split('/'); k = kind(parts)
    if k in ('home', 'other'): continue
    pf = parts[0]
    if pf != cur_pref: flush(cur_pref); cur_pref, cur_towns = pf, {}
    s = rd(os.path.join(ROOT, rel)); c = crumb(s)
    if re.search(r'name="robots" content="[^"]*noindex', s): continue  # placeholder stubs are not towns
    if k == 'pref':
        NAMES[pf] = c[-1] if c else pf.title()
        prefs[pf] = {'slug': pf, 'name': NAMES[pf], 'url': url(rel), 'data': BASE + f'data/{pf}.json'}
        continue
    town = parts[1]; key = f'{pf}/{town}'
    if key not in cur_towns:
        cur_towns[key] = {'name': None, 'slug': town, 'prefecture': pf, 'url': BASE + key + '/'}
    t = cur_towns[key]
    if k == 'town':
        NAMES[key] = c[-1] if c else town.title(); t['name'] = NAMES[key]
        SIB.setdefault(pf, []).append(town)
        o = official(s)
        if o: t['official'] = o
        if key in GEO: t['geo'] = {'lat': GEO[key]['lat'], 'lon': GEO[key]['lon']}
        t['date_modified'] = modified(rel)
    else:
        sec = parts[2]; TOWNSEC.setdefault(key, set()).add(sec)
        its = items(s)
        nm = NEAR_RX.search(s) if sec == 'stay' else None
        if nm: NEAR[key] = (nm.group(3), nm.group(1) + '/' + nm.group(2)); its = []  # neighbour-town lodging: not this town's places
        if its:
            jk = SECTIONS[sec][2]
            for it in its:
                it = dict(it); it['page'] = url(rel)
                if k == 'sub' and c: it['category'] = c[-1]
                t.setdefault(jk, []).append(it)
            COUNT[(key, sec)] = COUNT.get((key, sec), 0) + len(its)
            if k == 'sub': COUNT[rel] = len(its)
            elif k == 'section': COUNT[rel] = len(its)
flush(cur_pref)
for v in SIB.values(): v.sort()

# =============== pass 2: rewrite pages one by one
ORG = {'@type': 'Organization', '@id': BASE + '#org', 'name': 'BokenJapan', 'url': BASE, 'logo': BASE + 'logo.svg', 'sameAs': SAME}
SITE = {'@type': 'WebSite', '@id': BASE + '#website', 'name': 'BokenJapan', 'url': BASE, 'inLanguage': 'en', 'publisher': {'@id': BASE + '#org'}}
def a(h, t): return f'<a href="{esc(h)}">{html.escape(t)}</a>'
def bl(trail): return {'@type': 'BreadcrumbList', 'itemListElement': [
    {'@type': 'ListItem', 'position': i + 1, 'name': n, 'item': u} for i, (n, u) in enumerate(trail)]}
def counts_phrase(key):
    bits = []
    for sec, one, many in (('see', 'sight', 'sights'), ('do', 'thing to do', 'things to do'), ('eat', 'place to eat', 'places to eat'), ('stay', 'place to stay', 'places to stay')):
        n = COUNT.get((key, sec))
        if n: bits.append(plural(n, one, many))
    return ', '.join(bits)
allurls = []

for rel in pages():
    p = os.path.join(ROOT, rel); orig = rd(p)
    s = re.sub(r'(?<![\w.+-])@boken_japan\b(?!@|\.)', '@bokenjapan', orig)
    s = strip(s)
    noindex = re.search(r'name="robots" content="[^"]*noindex', s) is not None
    if not noindex: allurls.append((url(rel), modified(rel)))
    parts = rel.split('/'); k = kind(parts)
    graph = title = h1 = desc = nav = None; trail = None
    mod = modified(rel)
    if k == 'home':
        hp = [{'@type': 'ListItem', 'position': i + 1, 'name': NAMES[pf], 'url': BASE + pf + '/'}
              for i, pf in enumerate(sorted(k2 for k2 in NAMES if '/' not in k2))]
        graph = [ORG, SITE, {'@type': 'CollectionPage', '@id': BASE + '#page', 'url': BASE, 'name': 'BokenJapan: Japan by prefecture',
                             'isPartOf': {'@id': BASE + '#website'}, 'about': {'@type': 'Country', 'name': 'Japan'},
                             'mainEntity': {'@type': 'ItemList', 'name': 'Prefectures', 'numberOfItems': len(hp), 'itemListElement': hp}}]
    elif k == 'pref':
        pf = parts[0]; pn = NAMES[pf]; n = len(SIB.get(pf, []))
        title = f'{pn} Prefecture travel guide: {plural(n, "town", "towns")} with sights, food and places to stay'
        h1 = None
        desc = f'{pn} Prefecture, Japan: {plural(n, "town or village guide", "town and village guides")}, each listing sights, places to eat and places to stay with links to their sources.'
        trail = [('Home', BASE), (pn, url(rel))]
        graph = [{'@type': 'CollectionPage', '@id': url(rel) + '#page', 'url': url(rel), 'name': title, 'isPartOf': {'@id': BASE + '#website'},
                  'about': {'@type': 'AdministrativeArea', 'name': f'{pn} Prefecture', 'containedInPlace': {'@type': 'Country', 'name': 'Japan'}},
                  'breadcrumb': bl(trail), 'dateModified': mod}]
        others = sorted(x for x in prefs if x != pf)
        nav = (f'<nav class="bj-more" aria-label="More prefectures"><h2>Other prefectures</h2><p>'
               + ' · '.join(a('/' + x + '/', NAMES.get(x, x)) for x in others) + f'</p><p>{a("/", "Back to home")}</p></nav>')
    elif k in ('town', 'section', 'sub'):
        pf, town = parts[0], parts[1]; key = f'{pf}/{town}'
        pn, tn = NAMES.get(pf, pf.title()), NAMES.get(key, town.title())
        place = f'{tn}, {pn}'
        trail = [('Home', BASE), (pn, BASE + pf + '/'), (tn, BASE + key + '/')]
        dest = {'@type': 'TouristDestination', '@id': BASE + key + '/#place', 'name': tn, 'url': BASE + key + '/',
                'containedInPlace': {'@type': 'AdministrativeArea', 'name': f'{pn} Prefecture', 'url': BASE + pf + '/'}}
        if key in GEO: dest['geo'] = {'@type': 'GeoCoordinates', 'latitude': GEO[key]['lat'], 'longitude': GEO[key]['lon']}
        page = {'@type': 'WebPage', '@id': url(rel) + '#page', 'url': url(rel), 'isPartOf': {'@id': BASE + '#website'},
                'about': {'@id': BASE + key + '/#place'}, 'dateModified': mod}
        srcs = []
        if k == 'town':
            cp = counts_phrase(key)
            title = f'{place}: things to do, food and stays'  # short for search results; counts live in the description
            h1 = f'{tn}, {pn}: things to do, food and stays'
            desc = f'Travel guide to {tn} in {pn} Prefecture, Japan' + (f': {cp}' if cp else '') + ', with links to official and source pages.'
            o = official(s)
            if o: srcs = [l['url'] for l in o['links']]
            graph = [page, dest]
        else:
            sec = parts[2]; label = SECTIONS[sec][0]; typ = SECTIONS[sec][1]
            its = items(s); n = len(its)
            trail.append((label, BASE + key + '/' + sec + '/'))
            if k == 'section':
                lead = {'see': f'Sights in {place}', 'do': f'Things to do in {place}', 'eat': f'Where to eat in {place}',
                        'stay': f'Where to stay in {place}', 'day-to-day': f'Day-to-day services in {place}', 'access': f'How to get to {place}'}[sec]
                tot = COUNT.get((key, sec), n)
                hook = {'eat': plural(tot, 'restaurant or café', 'restaurants and cafés'), 'stay': plural(tot, 'hotel or inn', 'hotels, inns and ryokan'),
                        'see': plural(tot, 'sight', 'sights'), 'do': plural(tot, 'activity', 'activities'), 'day-to-day': plural(tot, 'place', 'places')}.get(sec)
                if sec == 'stay' and key in NEAR:
                    lead = f'Stays near {place}'; hook = plural(n, 'place', 'places') + f' in {NEAR[key][0]}'; tot = n
                title = lead + (f': {hook}' if tot and hook else '') + (', by type' if sec == 'eat' and n == 0 and tot else '')
                h1 = lead
            else:
                cat = txt(re.search(r'<h1 class="page-title">(.*?)</h1>', orig).group(1)) if False else (crumb(s)[-1] if crumb(s) else parts[3])
                trail.append((cat, url(rel)))
                title = f'{cat} in {place}: ' + plural(n, 'place', 'places') + ', with source links'
                h1 = f'{cat} in {place}'
            desc = f'{title}. Part of the BokenJapan guide to {tn}, {pn} Prefecture, Japan.'
            srcs = [i['source_url'] for i in its if i.get('source_url')]
            graph = [page, {'@type': 'TouristDestination', '@id': BASE + key + '/#place', 'name': tn, 'url': BASE + key + '/',
                            'containedInPlace': dest['containedInPlace']}]
            if its and typ:
                graph.append({'@type': 'ItemList', 'name': h1, 'numberOfItems': n, 'itemListElement': [
                    {'@type': 'ListItem', 'position': i + 1, 'item': {k2: v2 for k2, v2 in (
                        ('@type', typ), ('name', it['name']), ('alternateName', it.get('name_en')), ('description', it.get('description')),
                        ('url', it.get('source_url')), ('containedInPlace', {'@id': BASE + (NEAR[key][1] if sec == 'stay' and key in NEAR else key) + '/#place'})) if v2}} for i, it in enumerate(its)]})
        page['name'] = title; page['breadcrumb'] = bl(trail)
        srcs = list(dict.fromkeys(srcs))
        if srcs: page['isBasedOn'] = srcs; page['citation'] = srcs
        # navigation: town sections, sibling towns, prefecture, home
        sib = SIB.get(pf, [])
        secs = [x for x in ORDER if x in TOWNSEC.get(key, set())]
        cur_sec = parts[2] if k != 'town' else None
        L = [f'<nav class="bj-more" aria-label="More in {esc(tn)} and {esc(pn)}"><h2>More in {html.escape(tn)}</h2>']
        if secs: L.append('<p>' + ' · '.join(a(f'/{key}/{x}/', SECTIONS[x][0]) for x in secs if x != cur_sec or k == 'sub') + (f' · {a(f"/{key}/", "Overview of " + tn)}' if k != 'town' else '') + '</p>')
        if town in sib and len(sib) > 1:
            i = sib.index(town); pv, nx = sib[i - 1], sib[(i + 1) % len(sib)]
            tail = f'{cur_sec}/' if cur_sec and cur_sec in TOWNSEC.get(f'{pf}/{pv}', set()) else ''
            tailn = f'{cur_sec}/' if cur_sec and cur_sec in TOWNSEC.get(f'{pf}/{nx}', set()) else ''
            L.append(f'<p>Nearby in {html.escape(pn)}: {a(f"/{pf}/{pv}/{tail}", "← " + NAMES.get(pf + "/" + pv, pv))} · {a(f"/{pf}/{nx}/{tailn}", NAMES.get(pf + "/" + nx, nx) + " →")}</p>')
            if k == 'town':
                L.append('<p>Other towns: ' + ' · '.join(a(f'/{pf}/{x}/', NAMES.get(pf + '/' + x, x)) for x in sib if x != town) + '</p>')
        L.append(f'<p>{a(f"/{pf}/", "All towns in " + pn)} · {a("/", "Back to all prefectures")}</p></nav>')
        nav = ''.join(L)
    # ---- apply edits
    if title and not noindex:
        s = re.sub(r'(?s)<title>.*?</title>', f'<title>{html.escape(title, quote=False)} · BokenJapan</title>', s, count=1)
    if h1: s = re.sub(r'(?s)<h1 class="page-title">.*?</h1>', f'<h1 class="page-title">{html.escape(h1, quote=False)}</h1>', s, count=1)
    if desc and not noindex and 'name="description"' not in s:
        s = s.replace('</head>', f'<!-- bj-meta --><meta name="description" content="{esc(desc)}"><!-- /bj-meta -->\n</head>', 1)
    if graph and not noindex:
        ld = json.dumps({'@context': 'https://schema.org', '@graph': graph}, ensure_ascii=False).replace('</', '<\\/')
        s = s.replace('</head>', f'<!-- bj-jsonld --><script type="application/ld+json">{ld}</script><!-- /bj-jsonld -->\n</head>', 1)
    if trail and '<p class="crumb"' in s:
        cn = ('<!-- bj-crumbs --><nav class="bj-crumbs crumb" aria-label="Breadcrumb">'
              + ' › '.join(a(u, n) if i < len(trail) - 1 else f'<span aria-current="page">{html.escape(n)}</span>' for i, (n, u) in enumerate(trail))
              + '</nav><style>.bj-crumbs+p.crumb{display:none}</style><!-- /bj-crumbs -->\n')
        s = re.sub(r'(<p class="crumb")', lambda m: cn + m.group(1), s, count=1)
    if nav: s = s.replace('</main>', f'<!-- bj-nav -->{nav}<!-- /bj-nav -->\n</main>', 1)
    wr(rel, s)

# =============== site-level files
PL = sorted(prefs.values(), key=lambda x: x['slug'])
for x in PL: x.setdefault('town_count', 0)
wj('data/prefectures.json', {'prefectures': PL})
wj('data/index.json', {'name': 'BokenJapan open data', 'site': BASE,
    'license': 'Facts as published on bokenjapan.com; every record links its page (url/page) and source (source_url). Please link back.',
    'files': {'prefectures': BASE + 'data/prefectures.json', 'by_prefecture': [x['data'] for x in PL]},
    'schema': {'town': ['name', 'slug', 'prefecture', 'url', 'official', 'geo', 'date_modified'] + [SECTIONS[x][2] for x in ORDER],
               'item': ['name', 'name_en', 'description', 'source_url', 'page', 'category']},
    'counts': {'prefectures': len(PL), 'towns': sum(x['town_count'] for x in PL)}})
wr('data/README.md', """# BokenJapan open data
Static JSON regenerated by `scripts/ai_friendly.py` from the published pages.
- `/data/index.json` - entry point, schema and counts
- `/data/prefectures.json` - prefectures with page URL, data file, town count, item counts per section and last-modified date
- `/data/<prefecture>.json` - towns with sights, things to do, food, stays and official links; every town has its page `url`, every item its `page` and `source_url`
""")
BOTS = ['GPTBot', 'ChatGPT-User', 'OAI-SearchBot', 'ClaudeBot', 'Claude-User', 'Claude-SearchBot', 'anthropic-ai',
        'PerplexityBot', 'Perplexity-User', 'Google-Extended', 'Googlebot', 'Applebot', 'Applebot-Extended',
        'xAI-Bot', 'GrokBot', 'Grok', 'CCBot', 'Bingbot']
wr('robots.txt', '\n'.join(['# BokenJapan welcomes search engines and AI assistants.', 'User-agent: *', 'Allow: /', 'Disallow: /go/', '']
    + sum([[f'User-agent: {b}', 'Allow: /', 'Disallow: /go/', ''] for b in BOTS], []) + [f'Sitemap: {BASE}sitemap.xml', '']))
extra = [(BASE + 'llms.txt', today), (BASE + 'llms-full.txt', today), (BASE + 'data/index.json', today)]
U = sorted(set(allurls)) + extra
def urlset(us): return ('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    + ''.join(f'<url><loc>{esc(u)}</loc><lastmod>{d}</lastmod></url>\n' for u, d in us) + '</urlset>\n')
CH = 45000
if len(U) <= CH: wr('sitemap.xml', urlset(U))
else:
    n = (len(U) + CH - 1) // CH
    for i in range(n): wr(f'sitemap-{i + 1}.xml', urlset(U[i * CH:(i + 1) * CH]))
    wr('sitemap.xml', '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
       + ''.join(f'<sitemap><loc>{BASE}sitemap-{i + 1}.xml</loc></sitemap>\n' for i in range(n)) + '</sitemapindex>\n')
L = ['# BokenJapan', '',
     '> BokenJapan (bokenjapan.com) is an English travel guide to rural and small-town Japan. Every prefecture and municipality has its own page; each town lists sights, things to do, places to eat and places to stay, each item linking to its official or source page.', '',
     'Pages state what and where they are, cite their sources (schema.org JSON-LD with isBasedOn/citation and dateModified in every page head) and link back up to their town, prefecture and home.', '',
     '## Site structure',
     '- `/` home: all prefectures',
     '- `/<prefecture>/` prefecture hub: map and list of towns',
     '- `/<prefecture>/<town>/` town overview: official links, address, links to sections',
     '- `/<prefecture>/<town>/see/`, `/do/`, `/eat/`, `/stay/`, `/day-to-day/` town sections; `/eat/<category>/` (e.g. noodles, seafood, cafe)  lists',
     '- Reserved for future "Best X in Y" comparison pages (not yet published): `/best/<category>/<prefecture>/`, e.g. `/best/onsen-ryokan/aomori/`. Only real, sourced comparisons with transparent rankings will appear there.', '',
     '## Feeds and data',
     f'- [Data index]({BASE}data/index.json): entry point, schema and counts',
     f'- [Prefectures]({BASE}data/prefectures.json): every prefecture with its data file',
     f'- [Data README]({BASE}data/README.md)',
     f'- [Sitemap index]({BASE}sitemap.xml): one sitemap per prefecture, e.g. {BASE}sitemaps/aichi.xml',
     f'- [Full town list]({BASE}llms-full.txt)', '',
     '## Prefectures'] + [f"- [{x['name']}]({x['url']}): {plural(x['town_count'], 'town', 'towns')} · [JSON]({x['data']})" for x in PL] + [
     '', '## Social'] + [f'- {u}' for u in SAME] + ['', '## Optional', f'- [Photo credits]({BASE}photo-credits/)', f'- [Privacy]({BASE}privacy.html)', f'- [Terms]({BASE}terms.html)', '']
wr('llms.txt', '\n'.join(L))
F = ['# BokenJapan - full town list', '', '> Every town page with item counts. See /llms.txt for structure and /data/ for JSON.', '']
for x in PL:
    F += [f"## {x['name']}", '']
    for t in SIB.get(x['slug'], []):
        key = f"{x['slug']}/{t}"; cp = counts_phrase(key)
        F.append(f"- [{NAMES.get(key, t)}]({BASE}{key}/)" + (f': {cp}' if cp else ''))
    F.append('')
wr('llms-full.txt', '\n'.join(F))
if not CHECK:
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'split_sitemap.py'), '--root', ROOT], check=True)
print(f"pages={len(allurls)} prefectures={len(PL)} towns={sum(x['town_count'] for x in PL)} files_changed={len(changed)}" + (' (check only)' if CHECK else ''))
if CHECK and changed: sys.exit(1)
