#!/usr/bin/env python3
"""Drop thumbs that failed photo_check and leave a photo_search comment (no media file is deleted).

  photo_drop.py --tree TREE --report photo_check.json [--only tiny-bytes,narrow] [--exclude SRC,..] [--dry-run]
Card <img> is removed (credit comment replaced by a photo_search comment); hub tiles that use
the same src lose their <img> too.  Idempotent.
"""
import argparse, json, re, os, datetime

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--tree', required=True)
    ap.add_argument('--report', required=True)
    ap.add_argument('--only', default='')
    ap.add_argument('--exclude', default='')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    today = datetime.date.today().isoformat()
    only = [x for x in a.only.split(',') if x]
    excl = set(x for x in a.exclude.split(',') if x)
    todo = {}
    for r in json.load(open(a.report)):
        fl = r.get('flags') or []
        if not fl or r['src'] in excl: continue
        if only and not any(f.startswith(o) for f in fl for o in only): continue
        todo.setdefault(r['page'], {})[r['src']] = ';'.join(fl)
    n = 0
    for page, srcs in sorted(todo.items()):
        path = os.path.join(a.tree, page)
        t = open(path, encoding='utf-8').read(); o = t
        for src, why in srcs.items():
            cm = '<!-- photo_search: thumb %s dropped %s (%s); the listing offers no larger photo of its own; official/Commons search pending -->' % (os.path.basename(src), today, why)
            pat = re.compile(r'<img class="thumb" src="' + re.escape(src) + r'"[^>]*></a>(<!-- photo-credit:[^>]*-->)?')
            t, k = pat.subn('</a>' + cm, t, count=1)
            n += k
            t = re.sub(r'<img src="(?:\.\./\.\./|/)' + re.escape(src.lstrip('/')) + r'"[^>]*>', '', t)
        if t != o and not a.dry_run:
            open(path, 'w', encoding='utf-8').write(t)
        # hub tile in the town hub: swap to the first remaining >=560px card photo of this page, else no image
        hub = os.path.join(a.tree, os.path.dirname(os.path.dirname(page)), 'index.html')
        if os.path.exists(hub) and not a.dry_run:
            h = open(hub, encoding='utf-8').read(); ho = h
            for src in srcs:
                pat = re.compile(r'<img src="(?:\.\./\.\./|/)' + re.escape(src.lstrip('/')) + r'"[^>]*>')
                if not pat.search(h): continue
                alt = None
                for m in re.finditer(r'<img class="thumb" src="([^"]+)" alt="([^"]*)" width="(\d+)" height="(\d+)"', t):
                    if int(m.group(3)) >= 560:
                        alt = m; break
                rep = ('<img src="../../%s" alt="%s" width="%s" height="%s"  decoding="async">' % (alt.group(1).lstrip('/'), alt.group(2), alt.group(3), alt.group(4))) if alt else ''
                h = pat.sub(lambda m: rep, h, count=1)
            if h != ho:
                open(hub, 'w', encoding='utf-8').write(h); print('  hub updated', hub)
        print(page, len(srcs))
    print('cards dropped', n)
main()
