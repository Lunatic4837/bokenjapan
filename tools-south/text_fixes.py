#!/usr/bin/env python3
"""text_fixes.py - small, reversible content fixes for built pages (no deletions of cards or files).

  text_fixes.py --tree T --pref tottori sakyu            # rough romaji 'Sakyu' -> 'Sand Dunes' (whole word, not in URLs)
  text_fixes.py --tree T --pref shimane demote shimane/izumo/see   # move shop/food cards on a sights page to the end of the list
"""
import argparse, re
from pathlib import Path

SHOP_RE = re.compile(r'Suisan|Seafood Shop|Fish Market|Shokudo|Restaurant|Sushi|Sashimi|Ramen|Izakaya|水産|海鮮|食堂|市場|寿司|刺身|ラーメン')
LI = re.compile(r'<li><a href="[^"]*"><p class="place-name">.*?</li>', re.S)

def sakyu(tree, pref, dry):
    n = files = 0
    for f in sorted((Path(tree) / pref).rglob('index.html')):
        t = f.read_text(encoding='utf-8')
        t2, k = re.subn(r'(?<![\w/.\-])Sakyu(?![\w/\-])', 'Sand Dunes', t)
        if k:
            n += k; files += 1
            if not dry: f.write_text(t2, encoding='utf-8')
    print(f'sakyu: {n} replacements in {files} files')

def demote(tree, pages, dry):
    for p in pages:
        f = Path(tree) / p / 'index.html'
        t = f.read_text(encoding='utf-8'); m = re.search(r'<ul class="place-list">(.*?)</ul>', t, re.S)
        if not m: print('no list in', p); continue
        lis = LI.findall(m.group(1))
        keep = [x for x in lis if not SHOP_RE.search(re.search(r'place-name">([^<]*)', x).group(1))]
        move = [x for x in lis if x not in keep]
        if not move or keep == lis: print(p, ': nothing to move'); continue
        new = '<ul class="place-list">' + ''.join(keep + move) + '</ul>'
        print(p, f': moved {len(move)} shop/food card(s) to the end:', [re.search(r'place-name">([^<]*)', x).group(1) for x in move])
        if not dry: f.write_text(t[:m.start()] + new + t[m.end():], encoding='utf-8')

# ---- stay descriptions from the card's own name (added) ----
def staydesc_main(tree, pref):
    PN = pref.capitalize()
    import glob, re
    KW = [('旅館', 'Ryokan'), ('ホテル', 'Hotel'), ('HOTEL', 'Hotel'), ('宿屋', 'Inn'), ('ペンション', 'Pension'),
          ('民宿', 'Minshuku'), ('ゲストハウス', 'Guesthouse'), ('キャンプ', 'Campsite'), ('コテージ', 'Cottage')]
    n = 0
    for f in sorted(glob.glob(tree + '/%s/*/stay/index.html' % pref)):
        t = open(f, encoding='utf-8').read(); o = t
        town = f.split('/')[-3]
        te = re.search(r'<title>(?:Stays near |Stays in |Where to stay in )?([A-Za-z -]+?),', t)
        def card(m):
            nonlocal n
            li = m.group(0)
            if 'place-desc' in li: return li
            nm = re.search(r'place-name">([^<]*)', li).group(1)
            noun = next((v for k, v in KW if k in nm), None)
            if not noun: return li
            # the card's own town comes from its place-meta ("#7 ranked in Kurayoshi")
            tw = re.search(r'ranked in ([A-Za-z -]+)</p>', li)
            if not tw: return li
            n += 1
            d = '<p class="place-desc">%s in %s, %s.</p><!-- desc-source: card name keyword -->' % (noun, tw.group(1).strip(), PN)
            return li.replace('</p><!-- sources:', '</p>' + d + '<!-- sources:', 1) if '</p><!-- sources:' in li else li
        t = re.sub(r'<li><a href=.*?</li>', card, t, flags=re.S)
        t = t.replace('APA Hotel &lt; Tottori Ekimae &gt;', 'APA Hotel Tottori Ekimae').replace('APA Hotel &lt; Tottori Ekimae Minami &gt;', 'APA Hotel Tottori Ekimae Minami')
        if t != o:
            open(f, 'w', encoding='utf-8').write(t)
    print('stay descriptions added', n)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--tree', required=True); ap.add_argument('--pref', required=True); ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('op', choices=['sakyu', 'demote', 'staydesc']); ap.add_argument('pages', nargs='*')
    A = ap.parse_args()
    {'sakyu': lambda: sakyu(A.tree, A.pref, A.dry_run), 'demote': lambda: demote(A.tree, A.pages, A.dry_run), 'staydesc': lambda: staydesc_main(A.tree, A.pref)}[A.op]()


