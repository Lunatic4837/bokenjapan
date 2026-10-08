#!/usr/bin/env python3
"""Photo-less cards: drop the leftover photo-credit comment (it pointed at a photo that is not on the page)."""
import re, glob, collections
REPO = '/workspace/p1/pr12-work'; st = collections.Counter()
for p in glob.glob(f'{REPO}/*/*/index.html'):
    if p.split('/')[-3] not in ('miyagi','akita','fukuoka','yamaguchi','oita'): continue
    s = open(p, encoding='utf-8').read(); o = s
    def f(m):
        li = m.group(0)
        if '<img' in li or 'photo-credit' not in li: return li
        st['stripped'] += 1
        return re.sub(r'<!-- photo-credit: .*?-->', '', li, flags=re.S)
    s = re.sub(r'<li\b[^>]*>.*?</li>', f, s, flags=re.S)
    if s != o: open(p, 'w', encoding='utf-8').write(s); st['pages'] += 1
print(dict(st))
