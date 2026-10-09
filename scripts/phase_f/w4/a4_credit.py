#!/usr/bin/env python3
"""Covers with no photo-credit metadata: the page already names the photo's source in the HTML comment right before the
cover ('<!-- Photo: {what} — {site label} {url} -->'). Copy it into the standard hidden credit inside the figure."""
import re, json, collections
REPO = '/workspace/p1/pr12-work'; st = collections.Counter()
todo = json.load(open('/workspace/p1/phase-d/w4/covers_todo.json'))
for page, v in sorted(todo.items()):
    if not any('no-credit' in x for x in v): continue
    p = f'{REPO}/{page}/index.html'; s = open(p).read()
    m = re.search(r'<!-- Photo: ([^>]*?) -->\s*(<figure class="cover">)(.*?)(</figure>)', s, re.S)
    if not m: print('no Photo comment', page); st['no source comment'] += 1; continue
    mm = re.match(r'(.*?)\s+[—-]\s+(.*?)\s+(https?://\S+)$', m.group(1).strip())
    if not mm or 'photo-credit' in m.group(3): print('unparsed', page, m.group(1)[:120]); st['unparsed'] += 1; continue
    credit = f'<!-- photo-credit: {mm.group(2)} · Source {mm.group(3)} -->'
    s = s[:m.start(4)] + credit + s[m.start(4):]; open(p, 'w').write(s); st['credited'] += 1
    print(page, '|', credit)
print(dict(st))
