#!/usr/bin/env python3
"""Turn a flat sitemap.xml into a sitemap index plus one sitemap per prefecture.

    python3 scripts/split_sitemap.py [--root .] [--from-git]

  --from-git  rebuild the URL list from the files committed at HEAD (every index.html outside
              media/go/data/scripts/assets/fonts/sitemaps, plus root *.html), instead of trusting
              the old sitemap.xml. lastmod = newest of the old sitemap value and the last commit
              date that touched the page; pages with neither get no <lastmod>.

Reads <root>/sitemap.xml (a flat <urlset>, or an existing index: then the files in
<root>/sitemaps/ are re-read and re-split), writes <root>/sitemaps/<prefecture>.xml and
<root>/sitemaps/site.xml (home, legal pages, llms files, data index), then rewrites
<root>/sitemap.xml as a <sitemapindex> with one <lastmod> per child (newest URL in it).
Only URLs and lastmod values already in the sitemap are used; nothing is invented.
Idempotent. Run it after scripts/ai_friendly.py (which calls it at the end).
"""
import os, re, sys, html, json, subprocess

ROOT = sys.argv[sys.argv.index('--root') + 1] if '--root' in sys.argv else '.'
BASE = 'https://bokenjapan.com/'
LIMIT = 45000  # protocol maximum is 50,000 URLs per file

def rd(p):
    with open(os.path.join(ROOT, p), encoding='utf-8') as f: return f.read()

def urls_of(xml):
    return re.findall(r'<url><loc>([^<]+)</loc>(?:<lastmod>([^<]+)</lastmod>)?</url>', xml)

def collect():
    xml = rd('sitemap.xml')
    if '<sitemapindex' not in xml:
        return urls_of(xml)
    out = []
    for loc in re.findall(r'<loc>([^<]+)</loc>', xml):
        rel = html.unescape(loc)[len(BASE):]
        if os.path.exists(os.path.join(ROOT, rel)): out += urls_of(rd(rel))
    return out

SKIP = {'media', 'go', 'data', 'scripts', 'assets', 'fonts', 'sitemaps'}
# noindex stub pages (placeholder municipalities, no content): never list them. If the page file is checked out
# its own robots meta decides; otherwise the known stub pattern does.
STUB = re.compile(r'^okinawa/jis\d+/index\.html$')

def noindex(f):
    p = os.path.join(ROOT, f)
    if os.path.isfile(p):
        with open(p, encoding='utf-8', errors='ignore') as fh: return 'noindex' in fh.read(6000)
    return bool(STUB.match(f))

def from_git():
    ls = subprocess.run(['git', '-C', ROOT, 'ls-tree', '-r', '--name-only', 'HEAD'], capture_output=True, text=True, check=True).stdout.split('\n')
    log = subprocess.run(['git', '-C', ROOT, 'log', '--format=@%cs', '--name-only', '--invert-grep', '-E',
                          '--grep=\\[(ai|agent)-friendly\\]|AI-agent friendly site', 'HEAD'], capture_output=True, text=True).stdout
    dates, cur = {}, None
    for l in log.splitlines():
        if l.startswith('@'): cur = l[1:]
        elif l and l not in dates: dates[l] = cur
    old = {html.unescape(u): d or '' for u, d in collect()}
    out = []
    for f in ls:
        parts = f.split('/')
        if parts[0] in SKIP or not f.endswith('.html'): continue
        if noindex(f): continue
        if len(parts) == 1 and f != 'index.html' and f not in ('privacy.html', 'terms.html'): continue
        u = BASE + (f[:-10] if f.endswith('index.html') else f)
        out.append((u, max(old.get(u, ''), dates.get(f) or '')))
    for u in ('llms.txt', 'llms-full.txt', 'data/index.json'):
        out.append((BASE + u, old.get(BASE + u, '')))
    return out

def main():
    us = {}
    for u, d in (from_git() if '--from-git' in sys.argv else collect()):
        u = html.unescape(u)
        if u not in us or (d or '') > us[u]: us[u] = d or ''
    prefs = set()
    pj = os.path.join(ROOT, 'data/prefectures.json')
    if os.path.exists(pj):
        prefs = {p['slug'] for p in json.load(open(pj, encoding='utf-8'))['prefectures']}
    else:
        prefs = {u[len(BASE):].split('/')[0] for u in us if u.count('/') > 3}
    groups = {}
    for u in sorted(us):
        seg = u[len(BASE):].split('/')[0]
        groups.setdefault(seg if seg in prefs else 'site', []).append(u)
    sdir = os.path.join(ROOT, 'sitemaps'); os.makedirs(sdir, exist_ok=True)
    for old in os.listdir(sdir):
        if old.endswith('.xml'): os.remove(os.path.join(sdir, old))
    index = []
    for g in sorted(groups):
        L = groups[g]
        for i in range(0, len(L), LIMIT):
            part = L[i:i + LIMIT]
            name = f'sitemaps/{g}.xml' if len(L) <= LIMIT else f'sitemaps/{g}-{i // LIMIT + 1}.xml'
            body = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(
                f'<url><loc>{html.escape(u)}</loc>' + (f'<lastmod>{us[u]}</lastmod>' if us[u] else '') + '</url>\n' for u in part) + '</urlset>\n'
            with open(os.path.join(ROOT, name), 'w', encoding='utf-8') as f: f.write(body)
            index.append((name, max(us[u] for u in part)))
    body = '<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(
        f'<sitemap><loc>{BASE}{n}</loc>' + (f'<lastmod>{d}</lastmod>' if d else '') + '</sitemap>\n' for n, d in index) + '</sitemapindex>\n'
    with open(os.path.join(ROOT, 'sitemap.xml'), 'w', encoding='utf-8') as f: f.write(body)
    print(f'sitemap index: {len(index)} files, {len(us)} URLs')

main()
