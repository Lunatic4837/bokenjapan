#!/usr/bin/env python3
"""AUDIT-47 P8: replace scraped SEO page titles used as card names (｜ » 【公式】 HOME - … 観光協会) with the clean place name.
Usage: clean_titles.py ROOT pref [--dry]   (runs on see/ do/ day-to-day/ and town index pages)"""
import sys, re, glob, html as H
sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as S
root, pref = sys.argv[1], sys.argv[2]; dry = '--dry' in sys.argv; n = seen = 0
for f in glob.glob(f'{root}/{pref}/*/index.html') + glob.glob(f'{root}/{pref}/*/*/index.html'):
    t = open(f).read()
    def fx(m):
        global n, seen
        li = m.group(0); changed = li
        for cls in ('place-name', 'place-blurb'):
            for mm in re.finditer(rf'<p class="{cls}">([^<]*)</p>', li):
                nm = H.unescape(mm.group(1))
                if S.title_as_name(nm):
                    seen += 1; new = S.clean_title(nm)
                    if new and new != nm and not S.title_as_name(new):
                        n += 1; changed = changed.replace(mm.group(0), f'<p class="{cls}">{H.escape(new, quote=False)}</p>', 1)
                        changed = re.sub(r'(<img class="thumb"[^>]*alt=")' + re.escape(H.escape(nm)) + '"', lambda x: x.group(1) + H.escape(new) + '"', changed)
        return changed
    u = re.sub(r'<li>.*?</li>', fx, t, flags=re.S)
    if u != t and not dry: open(f, 'w').write(u)
print(pref, 'title-as-name found', seen, 'cleaned', n)
