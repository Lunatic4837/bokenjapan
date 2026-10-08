#!/usr/bin/env python3
"""Count Dining place-desc lines still matching the generic 'A restaurant in X' pattern, and pages where any
Dining line repeats >3 times."""
import re, glob, html, collections, sys
REPO = sys.argv[1] if len(sys.argv) > 1 else '/workspace/p1/pr12-work'
GEN = re.compile(r"^(?:An? )?[A-Za-z'\- ]+ in [A-Za-z\-ōū' ]+, [A-Za-z]+(?: prefecture)?\.$")
tot = 0; pages = set(); dup = set()
for p in glob.glob(f'{REPO}/*/*/index.html'):
    s = open(p, encoding='utf-8').read()
    m = re.search(r'<section class="place-section"><h2>Dining</h2>(.*?)</section>', s, re.S)
    if not m: continue
    ds = [html.unescape(x) for x in re.findall(r'<p class="place-desc">(.*?)</p>', m.group(1), re.S)]
    g = [d for d in ds if GEN.match(d)]
    if g: tot += len(g); pages.add(p)
    if any(n > 3 for n in collections.Counter(ds).values()): dup.add(p)
print(f'generic dining lines: {tot} on {len(pages)} pages; pages with a dining line >3x: {len(dup)}')
