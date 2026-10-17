#!/usr/bin/env python3
"""Re-romanise the English name of OSM-sourced cards with the current bjlib.romanize.

  romaji_fix.py --tree TREE --pref tottori [--dry-run]
Only cards with an osm_url source are touched (live cards are left alone).  A card is changed only when
the old English name is a near-variant of the new romanisation (so name:en values such as 'KFC' are kept).
Updates place-blurb, the thumb alt and JSON-LD alternateName on that page.
"""
import argparse, glob, html as H, re, sys, os, difflib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bjlib as L

# only repair known romanisation bugs; names that came from name:en / brand tags are kept as they are
BUG = re.compile(r' \( |Iommoru|Sho Branch|Chukahan|Bebifue|Yumike Hama|Bisutoro|Hanten|Pand E monium|Senmon Branch')

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--tree', required=True); ap.add_argument('--pref', required=True); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(); n = 0
    for f in sorted(glob.glob(f'{a.tree}/{a.pref}/*/eat/*/index.html')):
        t = open(f, encoding='utf-8').read(); o = t
        for li in re.findall(r'<li><a href=.*?</li>', t, re.S):
            if 'osm_url=' not in li: continue
            ja = H.unescape(re.search(r'place-name">([^<]*)', li).group(1))
            b = re.search(r'place-blurb">([^<]*)', li)
            if not b or not re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', ja): continue
            old = H.unescape(b.group(1)); new = L.romanize(ja)
            if not new or new == old: continue
            r = difflib.SequenceMatcher(None, re.sub(r'\W', '', old.lower()), re.sub(r'\W', '', new.lower())).ratio()
            if r < 0.6 or not BUG.search(old): continue
            ne = H.escape(new, quote=False); oe = b.group(1)
            li2 = li.replace(f'place-blurb">{oe}<', f'place-blurb">{ne}<').replace(f'alt="{oe}"', f'alt="{ne}"')
            t = t.replace(li, li2).replace(f'"alternateName": "{old}"', f'"alternateName": "{new}"'); n += 1
            print(f.split(a.pref + '/')[1].split('/eat')[0], '|', old, '->', new)
        if t != o and not a.dry_run: open(f, 'w', encoding='utf-8').write(t)
    print('renamed', n)
main()
