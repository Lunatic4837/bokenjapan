#!/usr/bin/env python3
"""Wave 4 item 2: Dining cards whose Tabelog listing's primary genre is lodging (旅館・民宿 / 料理旅館 / オーベルジュ / ペンション)
are the inn itself, not a separate restaurant -> removed from Dining (ranks renumbered). Hotel-genre listings (hotel restaurants)
are not touched. Each removed inn is looked up in the cached Jalan prefecture crawls (name + municipality); inns with a
Jalan listing that are not already in Stay are written to inns-not-in-stay.csv (not added to Stay this wave)."""
import sys, re, json, csv, glob, unicodedata, collections
sys.path.insert(0, '/workspace/p1/phase-d/w3'); sys.path.insert(0, '/workspace/p1/phase-d')
from cards_lib import *
C = json.load(open('/workspace/p1/phase-d/w4/a2_candidates.json'))
PRIMARY = ('旅館・民宿', '料理旅館', 'オーベルジュ', 'ペンション')
geo = json.load(open('/workspace/p1/phase-d/nostay/geo.json'))
def norm(x): return re.sub(r'[\s・\-－ー()（）「」]', '', unicodedata.normalize('NFKC', x or '')).lower()
def hotels(s):
    out = []
    for m in re.finditer(r'<script type="application/ld\+json">\s*(.*?)\s*</script>', s, re.S):
        try: d = json.loads(m.group(1), strict=False)
        except Exception: continue
        for el in (d if isinstance(d, list) else [d]):
            if isinstance(el, dict) and el.get('@type') == 'Hotel': out.append(el)
    return out
J = []
for f in glob.glob('/workspace/p1/phase-d/jalan/*.html'):
    for h in hotels(open(f, 'rb').read().decode('cp932', 'replace')):
        a = h.get('address') or {}; J.append((norm(h.get('name')), h.get('name'), h.get('url'), a.get('addressLocality') or ''))
JPREFS = {f.split('/')[-1].split('-')[0].split('_')[0] for f in glob.glob('/workspace/p1/phase-d/jalan/*.html')}
rm = collections.defaultdict(set); rows = []; st = collections.Counter()
for c in C:
    g = c['genre']
    if not g.split('、')[0] in PRIMARY: continue
    rm[c['page']].add(c['url']); st['removed'] += 1
    muni = geo.get(c['page'], {}).get('ja', ''); n = norm(re.sub(r'^(民宿|旅館|料理旅館|ペンション)\s*', '', c['name']))
    hit = [j for j in J if j[3].endswith(muni) or muni in j[3]] if muni else []
    hit = [j for j in hit if n and (n in j[0] or (len(j[0]) >= 3 and j[0] in norm(c['name'])))]
    rows.append(dict(page=c['page'], name=c['name'], tabelog_url=c['url'], tabelog_genre=g,
                     jalan_url=('https:' + hit[0][2] if hit and hit[0][2].startswith('//') else (hit[0][2] if hit else '')),
                     jalan_name=hit[0][1] if hit else '',
                     jalan_checked='yes' if c['page'].split('/')[0] in JPREFS else 'no (no cached Jalan crawl for this prefecture)'))
# not-in-Stay check + apply
for page, urls in rm.items():
    p = f'{REPO}/{page}/index.html'; s = open(p).read(); m, d = section_cards(s, 'Dining'); _, stay = section_cards(s, 'Stay')
    sn = {norm(x['name']) for x in stay}; su = {(x['href'] or '').rstrip('/') for x in stay}
    for r in rows:
        if r['page'] == page: r['in_stay'] = 'yes' if (norm(r['name']) in sn or (r['jalan_url'] and r['jalan_url'].rstrip('/') in su)) else 'no'
    body = m.group(2); n = 0
    def drop(mm):
        c = parse_li(mm.group(0))
        return '' if c['tb'] in urls else mm.group(0)
    body = re.sub(r'<li\b.*?</li>', drop, body, flags=re.S)
    k = [0]
    def ren(x): k[0] += 1; return re.sub(r'#\d+ ranked in', f'#{k[0]} ranked in', x.group(0), count=1)
    body = re.sub(r'<p class="place-meta">#\d+ ranked in [^<]*</p>', ren, body)
    open(p, 'w').write(s[:m.start(2)] + body + s[m.end(2):])
with open('inns-removed-from-dining.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
cand = [r for r in rows if r['jalan_url'] and r['in_stay'] == 'no']
with open('inns-not-in-stay.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(cand)
print(dict(st), 'pages', len(rm), 'jalan matched', sum(1 for r in rows if r['jalan_url']), 'in stay', sum(r['in_stay'] == 'yes' for r in rows), 'csv (jalan, not in Stay)', len(cand), 'oita/unchecked', sum(r['jalan_checked'] != 'yes' for r in rows))
