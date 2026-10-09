#!/usr/bin/env python3
"""Apply item-4 line-2 fixes (n4_align.json: listing's own reading; n4_rules.json: careful reading rules). Writes names-fixed-w5.csv."""
import sys, re, html, csv, json, collections
sys.path.insert(0, '/workspace/p1/phase-d/w3')
from cards_lib import *
fx = collections.defaultdict(dict)
for x in json.load(open('n4_align.json')):
    n = re.sub(r'(\w) An\b', r'\1-an', x['new_en']); n = re.sub(r'(\w) Ya$', r'\1ya', n)
    fx[x['page']][('Dining', x['idx'])] = (x['ja'], x['old_en'], n, 'tabelog listing reading: ' + x['reading'])
for x in json.load(open('n4_rules.json')):
    fx[x['page']][(x['section'], x['idx'])] = (x['ja'], x['old_en'], x['new_en'], 'careful reading (庵/処/家/園/寿司/々/志)')
rows = []; st = collections.Counter()
for page, p in pages():
    if page not in fx: continue
    s = open(p).read(); orig = s
    for sec in ('Stay', 'Dining'):
        m, d = section_cards(s, sec)
        if not d: continue
        body = m.group(2); lis = list(re.finditer(r'<li\b.*?</li>', body, re.S)); out = []; last = 0
        for i, mm in enumerate(lis):
            li = mm.group(0)
            if (sec, i) in fx[page]:
                ja, en, new, how = fx[page][(sec, i)]
                c = parse_li(li)
                if c['en'] != en: st['mismatch'] += 1
                else:
                    old = f'<p class="place-blurb">{html.escape(en, quote=True)}</p>'
                    if old in li:
                        li = li.replace(old, f'<p class="place-blurb">{html.escape(new, quote=True)}</p>', 1)
                        li = li.replace(f'alt="{html.escape(en, quote=True)}"', f'alt="{html.escape(new, quote=True)}"')
                        rows.append(dict(page=page, section=sec, name_ja=ja, old_en=en, new_en=new, basis=how)); st['fixed ' + sec] += 1
                    else: st['blurb not found'] += 1
            out.append(body[last:mm.start()] + li); last = mm.end()
        body = ''.join(out) + body[last:]; s = s[:m.start(2)] + body + s[m.end(2):]
    if s != orig: open(p, 'w').write(s); st['pages'] += 1
with open('names-fixed-w5.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['page', 'section', 'name_ja', 'old_en', 'new_en', 'basis']); w.writeheader(); w.writerows(rows)
print(dict(st))
