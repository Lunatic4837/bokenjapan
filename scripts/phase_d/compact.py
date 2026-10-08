#!/usr/bin/env python3
"""Pages over 1.5 MiB: drop URLs from hidden comments when they repeat the card's own listing URL
(in its sources comment). Nothing visible changes; the URL stays once per card."""
import re, glob, os
REPO = '/workspace/p1/pr12-work'
LI = re.compile(r'<li\b[^>]*>.*?</li>', re.S)
for p in glob.glob(f'{REPO}/*/*/index.html'):
    s = open(p, encoding='utf-8').read()
    if len(s.encode()) < 1.5 * 1024 * 1024: continue
    before = len(s.encode())
    def f(m):
        li = m.group(0)
        src = re.search(r'<!-- sources: (.*?) -->', li)
        if not src: return li
        urls = set(re.findall(r'=(\S+)', src.group(1)))
        li = re.sub(r'<!-- desc-source: (\S+) -->', lambda mm: '<!-- desc-source: listing -->' if mm.group(1) in urls else mm.group(0), li)
        li = re.sub(r'(<!-- photo-credit: .*?· Source )(\S+)( -->)', lambda mm: mm.group(1) + 'listing' + mm.group(3) if mm.group(2) in urls else mm.group(0), li)
        return li
    s = LI.sub(f, s)
    open(p, 'w', encoding='utf-8').write(s)
    print(os.path.relpath(p, REPO), before, '->', len(s.encode()))
