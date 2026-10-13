#!/usr/bin/env python3
"""Generic: add the line-4 place-desc to Dining cards that lack one, from the card's own Tabelog genre
(cached tb.jsonl {u, genre}; first genre via cos_fix.GENRE) -> "{Genre} in {Town}, {Pref}." + desc-source comment.
Same format as live Iwate/Yamagata. No genre -> card left as is (omit beats filler).
  python3 card_desc.py --root <site> --pref aomori [--tb tb.jsonl]
"""
import re, glob, json, sys, os, html, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cos_fix.py')).read()
exec(src[src.index('GENRE = {'):src.index('def esc(')])   # GENRE map only (cos_fix has CLI side effects)
def run(root, pref, tbp):
    TB = {}
    for l in open(tbp):
        x = json.loads(l); TB[x['u']] = x
    st = collections.Counter()
    for f in glob.glob(f'{root}/{pref}/**/index.html', recursive=True):
        s = open(f).read()
        crumb = re.search(r'<p class="crumb"><a href="/">Japan</a> / <a href="[^"]*">([^<]+)</a> / <a href="[^"]*">([^<]+)</a>', s)
        if not crumb: continue
        P, T = html.unescape(crumb.group(1)), html.unescape(crumb.group(2))
        def one(m):
            li = m.group(0)
            if 'place-desc' in li or 'place-name' not in li: return li
            u = re.search(r'tabelog_url=(\S+?/)\s', li)
            g = u and TB.get(u.group(1), {}).get('genre')
            gs = [x.strip() for x in re.split(r'[、,]', g or '') if x.strip() and x.strip() != 'その他']
            lab = next((GENRE[x] for x in gs if x in GENRE), None)
            if not lab: st['no_genre'] += 1; return li
            st['added'] += 1
            d = f'<p class="place-desc">{html.escape(f"{lab} in {T}, {P}.")}</p><!-- desc-source: {u.group(1)} -->'
            return re.sub(r'(<p class="place-meta">[^<]*</p>)', lambda k: k.group(1) + d, li, count=1) if 'place-meta' in li else li.replace('</li>', d + '</li>')
        o = re.sub(r'<li>(?:(?!</li>).)*?</li>', one, s, flags=re.S)
        if o != s: open(f, 'w').write(o); st['files'] += 1
    return st
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--pref', action='append', required=True)
    ap.add_argument('--tb', default='/workspace/p1/data/template4/tb.jsonl'); A = ap.parse_args()
    for p in A.pref: print(p, dict(run(A.root, p, A.tb)), flush=True)
