#!/usr/bin/env python3
"""Replace Dining place-desc text that still matches the generic 'A restaurant in X' pattern
with the sourced line from lines.json. Points desc-source at the listing. Leaves cards not in
lines.json unchanged (those are pending fetch or logged in no-data.csv)."""
import json, re, os, html, collections
REPO = '/workspace/p1/pr12-work'
L = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lines.json')))
by = collections.defaultdict(dict)
for k, v in L.items():
    page, sec, idx = k.split('|'); by[page][int(idx)] = v
W1 = {}
if os.path.exists(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lines_wave1.json')):
    W1 = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lines_wave1.json')))
GEN = re.compile(r"^(?:An? )?[A-Za-z'\- ]+ in [A-Za-z\-ōū' ]+, [A-Za-z]+(?: prefecture)?\.$")
st = collections.Counter()
for page, rows in by.items():
    p = f'{REPO}/{page}/index.html'; s = open(p, encoding='utf-8').read()
    m = re.search(r'(<section class="place-section"><h2>Dining</h2>)(.*?)(</section>)', s, re.S)
    if not m: continue
    body = m.group(2); i = [-1]
    def f(mm):
        i[0] += 1; li = mm.group(0); v = rows.get(i[0])
        if not v or len(v['line']) < 15: return li
        d = re.search(r'<p class="place-desc">(.*?)</p>', li, re.S)
        if not d: return li
        old = html.unescape(d.group(1))
        w1 = W1.get(f'{page}|Dining|{i[0]}', {}).get('line')
        if old != v['old'] and not GEN.match(old) and old != w1:
            st['skipped (already specific)'] += 1; return li
        li = li.replace(d.group(0), f'<p class="place-desc">{html.escape(v["line"], quote=False)}</p>', 1)
        # the card's own link is the listing the line was taken from; keep the compact marker (page weight)
        if not re.search(r'<!-- desc-source: .*?-->', li):
            li = li.replace('</li>', '<!-- desc-source: listing --></li>', 1)
        st['replaced'] += 1; return li
    body = re.sub(r'<li\b.*?</li>', f, body, flags=re.S)
    s = s[:m.start(2)] + body + s[m.end(2):]
    open(p, 'w', encoding='utf-8').write(s); st['pages'] += 1
print(dict(st))
