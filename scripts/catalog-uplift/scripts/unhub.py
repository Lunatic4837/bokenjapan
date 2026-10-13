#!/usr/bin/env python3
"""Inverse of template_hub: rebuild flat Stay/Dining/Sights sections from a hubbed town's sub-pages so the hub can be
regenerated with a newer template. Usage: unhub.py ROOT pref [slug...]"""
import sys, re, glob, shutil
from pathlib import Path
root, pref = Path(sys.argv[1]), sys.argv[2]; only = sys.argv[3:]
def lis(p): return re.findall(r'<li>.*?</li>', p.read_text(), re.S) if p.exists() else []
def rank(li): m = re.search(r'#(\d+) ranked', li); return int(m.group(1)) if m else 9999
n = 0
for town in sorted((root / pref).glob('*/index.html')):
    d = town.parent
    if only and d.name not in only: continue
    t = town.read_text()
    if '<section class="hub">' not in t: continue
    stay = lis(d / 'stay' / 'index.html'); dining, sights, seen = [], [], set()
    for f in sorted(glob.glob(str(d / 'eat' / '*' / 'index.html'))) + [str(d / 'see' / 'index.html'), str(d / 'do' / 'index.html'), str(d / 'day-to-day' / 'index.html')]:
        for li in lis(Path(f)):
            if 'place-name' not in li or li in seen: continue
            seen.add(li); (dining if 'tabelog_url=' in li else sights).append(li)
    fix = lambda L: [x.replace('src="/media/', 'src="../../media/') for x in sorted(L, key=rank)]
    stay, dining, sights = fix(stay), fix(dining), fix(sights)
    sec = lambda h, L: f'<section class="place-section"><h2>{h}</h2><ul class="place-list">{"".join(L)}</ul></section>' if L else ''
    sn = re.search(r'<section class="place-section"><h2>Stay</h2><p class="stay-none">.*?</p></section>', t, re.S)
    hub = re.search(r'<section class="hub">.*?</ul></section>', t, re.S)
    flat = (sec('Stay', stay) or (sn.group(0) if sn else '')) + sec('Dining', dining) + sec('Sights', sights)
    if sn: t = t.replace(sn.group(0), '')
    t = t.replace(hub.group(0), flat).replace('<body class="hubbed">', '<body>', 1)
    town.write_text(t)
    for sub in d.iterdir():
        if sub.is_dir(): shutil.rmtree(sub)
    n += 1; print(d.name, len(stay), len(dining), len(sights))
print('unhubbed', n)
