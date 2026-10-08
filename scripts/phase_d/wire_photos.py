#!/usr/bin/env python3
"""Phase D: wire newly sourced facility photos (photos-5pref/manifest.csv) into PR #12 cards.
Idempotent. Only cards without an <img class="thumb"> get one. Credit stays in a hidden comment."""
import csv, html, re, sys, os, collections, json
REPO = sys.argv[1] if len(sys.argv) > 1 else '/workspace/p1/pr12-work'
MAN = '/workspace/p1/photos-5pref/manifest.csv'
R2 = 'https://img.bokenjapan.com'
UPLOADED = {r['key'] for r in csv.DictReader(open('/workspace/p1/r2/manifest-5pref-photos-now.csv'))}
SEC = re.compile(r'(<section class="place-section">\s*<h2>([^<]+)</h2>)(.*?)(</section>)', re.S)
LI = re.compile(r'<li\b[^>]*>.*?</li>', re.S)
by_page = collections.defaultdict(list)
for r in csv.DictReader(open(MAN)):
    pg, sec, idx = r['card_key'].split('|')
    by_page[pg].append((sec, int(idx), r))
st = collections.Counter(); log = []
for pg, items in sorted(by_page.items()):
    p = f'{REPO}/{pg}/index.html'
    if not os.path.exists(p): st['no_page'] += len(items); continue
    s = open(p, encoding='utf-8').read(); orig = s
    want = collections.defaultdict(dict)
    for sec, idx, r in items: want[sec][idx] = r
    def fix_sec(m):
        sec = m.group(2).strip()
        if sec not in want: return m.group(0)
        lis = list(LI.finditer(m.group(3))); body = m.group(3); out = []; last = 0
        for i, lm in enumerate(lis):
            li = lm.group(0)
            r = want[sec].get(i)
            if r is not None:
                key = r['repo_path']
                name_m = re.search(r'<p class="place-name">(.*?)</p>', li, re.S)
                name = html.unescape(name_m.group(1)) if name_m else ''
                lu = r['listing_url'] or ''
                ok_id = (lu and (lu in html.unescape(li))) or name == r['card_name_on_page']
                if not ok_id:
                    st['mismatch'] += 1; log.append(('mismatch', pg, sec, i, name, r['card_name_on_page']))
                elif key not in UPLOADED:
                    st['not_uploaded'] += 1
                elif 'class="thumb"' in li:
                    st['already_has_img'] += 1
                elif not name_m:
                    st['no_name'] += 1
                else:
                    w, h = (r['width_x_height'].split('x') + ['', ''])[:2]
                    alt = html.escape(name, quote=True)
                    img = f'<img class="thumb" src="{R2}/{key}" alt="{alt}" loading="lazy" decoding="async" width="{w}" height="{h}">'
                    new = li.replace('<!-- photo-missing -->', '', 1)
                    new = new.replace(name_m.group(0), name_m.group(0) + img, 1)
                    credit = r['credit'].replace('--', '–')
                    if re.search(r'<!-- photo-credit:.*?-->', new, re.S):
                        new = re.sub(r'<!-- photo-credit:.*?-->', lambda _: f'<!-- photo-credit: {credit} -->', new, count=1, flags=re.S)
                    else:
                        new = new.replace('</li>', f'<!-- photo-credit: {credit} --></li>')
                    li = new; st['wired'] += 1
            out.append(body[last:lm.start()]); out.append(li); last = lm.end()
        out.append(body[last:])
        return m.group(1) + ''.join(out) + m.group(4)
    s = SEC.sub(fix_sec, s)
    if s != orig:
        open(p, 'w', encoding='utf-8').write(s); st['pages_changed'] += 1
print(dict(st))
json.dump(log, open('/workspace/p1/phase-d/wire_log.json', 'w'), ensure_ascii=False, indent=0)
