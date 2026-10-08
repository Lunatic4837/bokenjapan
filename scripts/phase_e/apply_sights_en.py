#!/usr/bin/env python3
"""Replace machine-romanised Sights/experience names with English names (sights_en_map.json: old name + row link -> new)."""
import json, re, glob, html, collections, os
REPO = '/workspace/p1/pr12-work'
M = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'sights_en_map.json')))
by = {(x['old'], x['href']): x['new'] for x in M}
LI = re.compile(r'<li\b[^>]*>.*?</li>', re.S); st = collections.Counter()
for p in glob.glob(f'{REPO}/*/*/index.html'):
    if p.split('/')[-3] not in ('miyagi','akita','fukuoka','yamaguchi','oita'): continue
    s = open(p, encoding='utf-8').read(); o = s
    def f(m):
        li = m.group(0)
        nm = re.search(r'<p class="place-name">(.*?)</p>', li, re.S); hr = re.search(r'<a href="([^"]+)"', li)
        if not nm or not hr: return li
        new = by.get((html.unescape(nm.group(1)), html.unescape(hr.group(1))))
        if not new: return li
        st['renamed'] += 1
        e = html.escape(new, quote=False); ea = html.escape(new, quote=True)
        li = li.replace(nm.group(0), f'<p class="place-name">{e}</p>', 1)
        if new.startswith('Old-Map Town Walk'):
            li = re.sub(r'<p class="place-desc">(?:An? )?[Cc]astle in [^<]*</p>', '<p class="place-desc">A town walk following an old map of the area.</p>', li, count=1)
        return re.sub(r'(<img class="thumb"[^>]*?alt=")[^"]*(")', lambda mm: mm.group(1) + ea + mm.group(2), li, count=1)
    s = LI.sub(f, s)
    if s != o: open(p, 'w', encoding='utf-8').write(s); st['pages'] += 1
print(dict(st))
