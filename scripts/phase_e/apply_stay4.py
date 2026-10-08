#!/usr/bin/env python3
"""Swap the generic 'A hotel in X' Stay sentences for the sourced Jalan lines in lines.json, and point desc-source at the listing."""
import json, re, os, html, collections
REPO = '/workspace/p1/pr12-work'
L = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lines.json')))
by = collections.defaultdict(dict)
for k, v in L.items():
    page, idx = k.split('|'); by[page][int(idx)] = v
st = collections.Counter()
for page, rows in by.items():
    p = f'{REPO}/{page}/index.html'; s = open(p, encoding='utf-8').read()
    m = re.search(r'(<section class="place-section"><h2>Stay</h2>)(.*?)(</section>)', s, re.S)
    body = m.group(2); i = [-1]
    def f(mm):
        i[0] += 1; li = mm.group(0); v = rows.get(i[0])
        if not v: return li
        d = re.search(r'<p class="place-desc">(.*?)</p>', li, re.S)
        if not d or html.unescape(d.group(1)) != v['old']: st['skipped (text changed)'] += 1; return li
        li = li.replace(d.group(0), f'<p class="place-desc">{html.escape(v["line"], quote=False)}</p>', 1)
        li = re.sub(r'<!-- desc-source: [^>]*-->', f'<!-- desc-source: {v["source"]} -->', li, count=1)
        st['replaced'] += 1; return li
    body = re.sub(r'<li\b.*?</li>', f, body, flags=re.S)
    s = s[:m.start(2)] + body + s[m.end(2):]
    open(p, 'w', encoding='utf-8').write(s)
print(dict(st))
