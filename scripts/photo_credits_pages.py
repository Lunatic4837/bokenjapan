#!/usr/bin/env python3
"""Build /<pref>/photo-credits/index.html from the <!-- photo-credit: ... --> metadata on a prefecture's pages.

    python3 scripts/photo_credits_pages.py --root . --pref <slug> [--pref <slug2> ...] [--check] [--stats-json out.json]

Reads only what the page metadata says (author, licence, file/source URL); nothing is invented.
  * main list  : photos whose metadata names an author AND a licence (CC BY / BY-SA / CC0 / public domain / GFDL ...),
                 one row per photo file, with every card/page it is used on.
  * second list: Wikimedia/Wikipedia-sourced photos whose metadata lacks author or licence ("licence being confirmed"):
                 listed with their source link, never given a made-up licence.
  * photos credited only to a venue / tourism board / listing site (no licence in metadata) are counted, not listed
    (same policy as /hokkaido/photo-credits/: those come from the venue's or tourism board's own pages).
No <img> is touched; only <pref>/photo-credits/index.html is written. Run site_chrome.py afterwards (share tags, footer, lazy images)
and split_sitemap.py --from-git for the sitemap. Idempotent: same input -> same bytes. Pages are split into
photo-credits/ (+ photo-credits/page/N/) when one page would exceed PAGE_MAX_BYTES.
"""
import os, re, sys, json, html, collections
from urllib.parse import unquote, quote

SKIP_DIRS = {'.git', 'media', 'go', 'data', 'scripts', 'assets', 'fonts', 'sitemaps', 'node_modules', 'photo-credits'}
BASE = 'https://bokenjapan.com'
PAGE_MAX_BYTES = 900_000
CAT = {'see': 'Sights', 'eat': 'Eat', 'stay': 'Stay', 'do': 'Do', 'day-to-day': 'Day to day', 'access': 'Access'}
COMMENT = re.compile(r'<!--\s*photo-credit:?(.*?)-->', re.S)
IMG = re.compile(r'<img\b[^>]*>', re.I)
LIC = re.compile(r'\b(CC0(?:\s*1\.0)?|CC[ -]BY(?:-SA)?(?:\s*\d\.\d)?(?:\s*jp)?|Public[ -]domain|GFDL)\b', re.I)
URL = re.compile(r'https?://\S+')
WIKI = re.compile(r'wikimedia|wikipedia|commons', re.I)

def lic_norm(t):
    t = re.sub(r'\s+', ' ', t.strip())
    if re.match(r'public[ -]domain', t, re.I): return 'Public domain', ''
    if re.match(r'GFDL', t, re.I): return 'GFDL', ''
    if re.match(r'CC0', t, re.I): return 'CC0 1.0', 'https://creativecommons.org/publicdomain/zero/1.0/'
    m = re.match(r'CC[ -]BY(-SA)?(?: (\d\.\d))?(?: (jp))?$', t, re.I)
    if not m: return t, ''
    sa, ver, jp = m.group(1), m.group(2), m.group(3)
    name = 'CC BY' + ('-SA' if sa else '') + (' ' + ver if ver else '') + (' JP' if jp else '')
    if not ver: return name, ''
    return name, f'https://creativecommons.org/licenses/{"by-sa" if sa else "by"}/{ver}/' + ('jp/' if jp else '')

def commons_file(u):
    m = re.match(r'https?://commons\.wikimedia\.org/wiki/(?:File|Special:FilePath)(?::|%3A|/)(.+?)(?:[?#]|%3F|$)', u, re.I)
    if not m: return None
    return unquote(m.group(1)).replace('_', ' ')

def clean_url(u):
    """Drop tracking suffixes (?utm_..., %3Futm_...) from a Wikimedia/Wikipedia link; the page is the same."""
    return re.split(r'%3Futm_|\?utm_', u)[0] if u else u

def parse_comment(t):
    """-> dict(author, licence, lic_url, file_url, source, wiki) from one photo-credit comment (as given)."""
    t = html.unescape(t.strip())
    src = ''
    m = re.search(r'(?:^|\s·\s)Source\s+(\S+)', t)
    before = t
    if m:
        src = m.group(1); before = t[:m.start()]
    before = re.sub(r'\s+·\s*$', '', before)
    urls = URL.findall(before)
    file_url = next((u for u in urls if commons_file(u)), '')
    if not file_url and commons_file(src or ''): file_url = src
    plain = URL.sub('', before)
    author = lic = ''
    mm = re.match(r'^Photo:\s*(.+?),\s*(CC[^,]+?),\s*via Wikimedia Commons\s*$', plain.strip(), re.I)
    m2 = re.match(r'^(.+?)\s*/\s*Wikimedia Commons\s*\((.+?)\)\s*$', plain.strip(), re.I)
    if mm: author, lic = mm.group(1).strip(), mm.group(2).strip()
    elif m2: author, lic = m2.group(1).strip(), m2.group(2).strip()
    else:
        parts = [p.strip() for p in plain.split(' · ')]
        rest = []
        for p in parts:
            if not p: continue
            if not lic and LIC.fullmatch(p.strip()) or (not lic and LIC.match(p) and len(p) < 24):
                lic = p; continue
            if re.match(r'wikimedia commons', p, re.I): continue
            rest.append(p)
        author = rest[0] if rest else ''
        if not lic and not author is None:
            pass
    lic_name, lic_url = ('', '')
    if lic:
        ml = LIC.search(lic)
        if ml: lic_name, lic_url = lic_norm(ml.group(1))
    if author and re.search(r'\b(official|page|site|image|listing|source)\b', author, re.I) and not lic_name: author = author
    return dict(author=author, licence=lic_name, lic_url=lic_url, file_url=clean_url(file_url), source=clean_url(src),
                wiki=bool(WIKI.search(t)))

def text_of(frag):
    return html.unescape(re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', frag))).strip()

def scan_page(path, rel, pref_name, towns):
    s = open(path, encoding='utf-8').read()
    out = []
    parts = rel.split('/')[:-1]  # dirs
    town_slug = parts[1] if len(parts) > 1 else None
    if town_slug and town_slug not in towns:
        m = re.search(r'<a href="/%s/%s/">([^<]+)</a>' % (re.escape(parts[0]), re.escape(town_slug)), s)
        towns[town_slug] = (m.group(1).split(',')[0].split(':')[0].strip() if m else town_slug.replace('-', ' ').title())
    for m in COMMENT.finditer(s):
        pos = m.start()
        lo = max(s.rfind('<li', 0, pos), s.rfind('<figure', 0, pos))
        seg = s[lo:pos] if lo >= 0 else ''
        ii = seg.rfind('<img')
        if ii >= 0: imgs = [seg[ii:]]
        else:   # card markup broken upstream (e.g. alt swallowing the next card): nearest preceding <img> on the page
            j = s.rfind('<img', 0, pos); imgs = [s[j:pos]] if j >= 0 else []
        fac = ''
        if lo >= 0 and s.startswith('<li', lo):
            pn = re.search(r'<p class="place-name"[^>]*>(.*?)</p>', seg, re.S)
            fac = text_of(pn.group(1)) if pn else ''
        src = ''
        alt = ''
        if imgs:
            ms = re.search(r'\bsrc="([^"]+)"', imgs[-1]); src = ms.group(1) if ms else ''
            ma = re.search(r'\balt="([^"]*)"', imgs[-1]); alt = html.unescape(ma.group(1)) if ma else ''
        if not fac and 'class="cover"' in s[lo:lo + 40] if lo >= 0 else False: fac = ''
        d = parse_comment(m.group(1)); d.update(img=src, alt=alt, facility=fac or alt, rel=rel, parts=parts)
        out.append(d)
    return out

def title_case(slug): return slug.replace('-', ' ').title()

def collect(root, pref, pref_name):
    towns = {}
    items = []
    base = os.path.join(root, pref)
    for dp, dn, fn in os.walk(base):
        dn[:] = sorted(d for d in dn if d not in SKIP_DIRS and not d.startswith('.'))
        for f in sorted(fn):
            if f != 'index.html': continue
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace(os.sep, '/')
            items += scan_page(p, rel, pref_name, towns)
    return items, towns

def where(it, pref, pref_name, towns):
    parts = it['parts']
    url = '/' + '/'.join(parts) + '/'
    if len(parts) == 1: return url, pref_name, it['facility']
    town = towns.get(parts[1], title_case(parts[1]))
    cat = ''
    if len(parts) > 2: cat = ' › '.join([CAT.get(parts[2], title_case(parts[2]))] + [title_case(x) for x in parts[3:]])
    return url, town + (' › ' + cat if cat else ''), it['facility']

def img_base(src): return os.path.basename(src.split('?')[0]) if src else ''

def build_rows(items, pref, pref_name, towns):
    stats = collections.Counter()
    groups = collections.OrderedDict(); gaps = collections.OrderedDict()
    for it in items:
        stats['comments'] += 1
        ok = bool(it['licence'] and it['author'])
        key = ('F:' + commons_file(it['file_url']).casefold()) if it['file_url'] else ('S:' + (it['source'] or '') + '|' + img_base(it['img']))
        if ok:
            g = groups.setdefault(key, dict(it, uses=[]))
            g['uses'].append(where(it, pref, pref_name, towns))
        elif it['wiki'] or it['licence'] or (it['author'] and it['file_url']):
            k2 = ('I:' + img_base(it['img'])) if it['img'] else key
            g = gaps.setdefault(k2, dict(it, uses=[]))
            g['uses'].append(where(it, pref, pref_name, towns))
        else:
            stats['venue_or_site_only'] += 1
    return groups, gaps, stats

def uses_html(uses, limit=6):
    seen = []; seen_k = set()
    for u in uses:
        if u not in seen_k: seen_k.add(u); seen.append(u)
    def one(u):
        url, label, fac = u
        txt = label + (' › ' + fac if fac else '')
        return f'<a href="{html.escape(url)}">{html.escape(txt)}</a>'
    shown = ' · '.join(one(u) for u in seen[:limit])
    if len(seen) > limit: shown += f' · +{len(seen) - limit} more'
    return shown, len(seen)

def row_ok(g):
    title = commons_file(g['file_url']) if g['file_url'] else (img_base(g['img']) or 'photo')
    furl = g['file_url']
    t = f'<strong>{html.escape(title)}</strong>'
    line = 'By ' + html.escape(g['author']) + ' · ' + (f'<a href="{html.escape(g["lic_url"])}" rel="license noopener">{html.escape(g["licence"])}</a>' if g['lic_url'] else html.escape(g['licence']))
    if furl: line += f' · <a href="{html.escape(furl, quote=True)}" rel="noopener">Wikimedia Commons</a>'
    elif g['source']: line += f' · <a href="{html.escape(g["source"], quote=True)}" rel="noopener">Source</a>'
    img = img_base(g['img'])
    uh, _ = uses_html(g['uses'])
    return (f'<li class="credit-row"><p>{t}<br>{line}<br><span class="muted">Image: {html.escape(img) if img else "n/a"} · Used on: {uh}</span></p></li>')

def row_gap(g):
    img = img_base(g['img']) or 'photo'
    src = g['source'] or g['file_url']
    link = f'<a href="{html.escape(src, quote=True)}" rel="noopener">source (Wikipedia / Wikimedia Commons)</a>' if src else 'source not stated'
    au = 'author: ' + html.escape(g['author']) if g['author'] else 'author: not stated'
    li = 'licence: ' + html.escape(g['licence']) if g['licence'] else 'licence: to be confirmed'
    uh, _ = uses_html(g['uses'])
    return f'<li class="credit-row"><p>{html.escape(img)} · {link} · {au} · {li}<br><span class="muted">Used on: {uh}</span></p></li>'

HEAD = '''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <meta name="description" content="{desc}">
  <link rel="canonical" href="{canon}">
  <link rel="stylesheet" href="/styles.css">
</head>
<body class="hubbed">
  <header class="mast">
    <div class="mast-inner">
      <a class="brand" href="/"><img class="brand-mark" src="/logo.svg" width="168" height="168" alt="冒険日本">BokenJapan</a>
      <nav class="mast-nav" aria-label="Section">
        <a href="/">Home</a>
        <a href="/{pref}/">{name}</a>
      </nav>
    </div>
  </header>
  <main class="page-main">
'''
FOOT = '''</main>
  <footer class="site-foot">
    <div class="brand-foot"><img src="/logo.svg" width="56" height="56" alt="冒険日本"><p class="foot-name">BokenJapan</p></div>
    <nav class="foot-legal" aria-label="Legal"><a href="/privacy.html">Privacy</a> · <a href="/terms.html">Terms</a></nav>
  </footer>
</body>
</html>
'''

def page_html(pref, name, rows_ok, rows_gap, n_ok, n_gap, pageno, npages, stats):
    suffix = f' (page {pageno} of {npages})' if npages > 1 else ''
    path = f'/{pref}/photo-credits/' + (f'page/{pageno}/' if pageno > 1 else '')
    title = f'Photo credits{suffix} · {name} · BokenJapan'
    desc = f'Photographer credits and licences for Creative Commons photos used on BokenJapan {name} pages.'
    h = HEAD.format(title=html.escape(title), desc=html.escape(desc), canon=BASE + path, pref=pref, name=html.escape(name))
    h += f'<p class="crumb"><a href="/">Japan</a> / <a href="/{pref}/">{html.escape(name)}</a> / Photo credits</p>\n'
    h += f'<h1 class="page-title">Photo credits · {html.escape(name)}</h1>\n'
    h += f'<p class="page-sub">{n_ok} credited photos' + (f' · {n_gap} with licence being confirmed' if n_gap else '') + f' on {html.escape(name)} pages</p>\n'
    if pageno == 1:
        h += ('<p>These photos are used under open licences (Creative Commons, public domain). Each entry names the author, the licence '
              'and the original source file, as stated in the photo metadata. Other photos on these pages come from the venue\'s or tourism board\'s own pages; '
              'they stay with their owners and are removed on request.</p>\n')
    if npages > 1:
        h += '<nav class="credit-pages" aria-label="Photo credit pages">' + ' · '.join(
            (f'<span aria-current="page">{i}</span>' if i == pageno else f'<a href="/{pref}/photo-credits/' + (f'page/{i}/' if i > 1 else '') + f'">{i}</a>')
            for i in range(1, npages + 1)) + '</nav>\n'
    if rows_ok:
        h += '<ul class="credit-list" style="list-style:none;padding:0">\n' + '\n'.join(rows_ok) + '\n</ul>\n'
    if rows_gap:
        h += '<h2>Other Wikimedia photos (licence being confirmed)</h2>\n<ul class="credit-list" style="list-style:none;padding:0">\n' + '\n'.join(rows_gap) + '\n</ul>\n'
    h += FOOT
    return path, h

def write(root, pref, name, groups, gaps):
    ok_rows = sorted(groups.values(), key=lambda g: (commons_file(g['file_url']) or img_base(g['img']) or '').casefold())
    gap_rows = sorted(gaps.values(), key=lambda g: img_base(g['img']).casefold())
    rok = [row_ok(g) for g in ok_rows]; rgap = [row_gap(g) for g in gap_rows]
    allrows = [('ok', r) for r in rok] + [('gap', r) for r in rgap]
    # paginate by bytes
    pages = []; cur = []; size = 0
    for k, r in allrows:
        if size + len(r) > PAGE_MAX_BYTES and cur: pages.append(cur); cur = []; size = 0
        cur.append((k, r)); size += len(r) + 1
    pages.append(cur)
    written = []
    outdir = os.path.join(root, pref, 'photo-credits')
    for i, pg in enumerate(pages, 1):
        path, h = page_html(pref, name, [r for k, r in pg if k == 'ok'], [r for k, r in pg if k == 'gap'], len(rok), len(rgap), i, len(pages), None)
        fp = os.path.join(root, path.strip('/'), 'index.html')
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        old = open(fp, encoding='utf-8').read() if os.path.exists(fp) else None
        if old != h:
            open(fp, 'w', encoding='utf-8').write(h)
        written.append((fp, len(h.encode())))
    return written

def main():
    a = sys.argv[1:]
    root = a[a.index('--root') + 1] if '--root' in a else '.'
    prefs = [a[i + 1] for i, x in enumerate(a) if x == '--pref']
    stats_json = a[a.index('--stats-json') + 1] if '--stats-json' in a else None
    names = {x['slug']: x['name'] for x in json.load(open(os.path.join(root, 'data', 'prefectures.json'), encoding='utf-8'))['prefectures']}
    res = {}
    for pref in prefs:
        items, towns = collect(root, pref, names.get(pref, title_case(pref)))
        groups, gaps, st = build_rows(items, pref, names.get(pref, title_case(pref)), towns)
        res[pref] = dict(comments=st['comments'], credited_photos=len(groups), gap_photos=len(gaps), venue_or_site_only=st['venue_or_site_only'],
                         gap_no_author=sum(1 for g in groups.values() if not g['author']),
                         gap_wiki_no_licence=sum(1 for g in gaps.values() if not g['licence']),
                         gap_wiki_no_author=sum(1 for g in gaps.values() if not g['author']))
        if groups or gaps:
            w = write(root, pref, names.get(pref, title_case(pref)), groups, gaps)
            res[pref]['pages'] = [(os.path.relpath(f, root), n) for f, n in w]
        else:
            res[pref]['pages'] = []
        print(pref, json.dumps(res[pref], ensure_ascii=False))
    if stats_json: json.dump(res, open(stats_json, 'w'), ensure_ascii=False, indent=1)

if __name__ == '__main__': main()
