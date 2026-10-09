#!/usr/bin/env python3
"""Wave 3 item 1: Dining lines repeated >3x on a page (older cuisine-only lines such as 'Japanese restaurant.') get
facts from the card's own fetched listing (same gen2 builders: station/area, budget band, hours, closed days,
parking/takeout), adding facts until the line is no longer repeated >3x on the page. No listing fact -> line kept."""
import sys, re, html, json, csv, collections
sys.path.insert(0, '/workspace/p1/line4/work'); sys.path.insert(0, '/workspace/p1/phase-d/dining4'); sys.path.insert(0, '/workspace/p1/phase-d/w3')
import gen as B, gen2 as G2
from cards_lib import *
F = B.load_fetched(); st = collections.Counter(); log = []; plan = {}
for page, p in pages():
    if not re.match(r'(miyagi|akita|fukuoka|yamaguchi|oita)/', page): continue
    s = open(p).read(); m, d = section_cards(s, 'Dining')
    if not d: continue
    ds = [c['desc'] or '' for c in d]; cnt = collections.Counter(ds)
    items = {}
    for i, c in enumerate(d):
        if cnt[ds[i]] <= 3: continue
        st['target'] += 1
        u = c['tb'] or c['ta']; sp, r = B.page(F, u) if u else (None, None)
        if not sp: log.append((page, i, ds[i], u, 'listing not fetched/available')); continue
        line, extra, kind, fields = G2.tb_card(sp, page.split('/')[0]) if c['tb'] else G2.ta_card(sp)
        if not line: log.append((page, i, ds[i], u, f'no usable listing facts ({kind})')); continue
        items[i] = dict(base=line, extra=extra or [], alts=list((fields or {}).get('alts') or []), n=0 if (',' in line or ';' in line) else 1)
        items[i]['line'] = G2.join(items[i]['base'], items[i]['extra'], items[i]['n'])
    if not items: continue
    def cur(): return [items[i]['line'] if i in items else ds[i] for i in range(len(d))]
    for rnd in range(8):
        c2 = collections.Counter(cur()); ch = 0
        for i, it in items.items():
            if c2[it['line']] > 3:
                if it['n'] < len(it['extra']): it['n'] += 1
                elif it['alts']: it['base'] = it['alts'].pop(0)
                else: continue
                it['line'] = G2.join(it['base'], it['extra'], it['n']); ch += 1
        if not ch: break
    for i, it in items.items():
        l = B.scrub(it['line']); l = l[:1].upper() + l[1:]
        if len(l) < 15 or G2.GENERIC.match(l) or l == ds[i]: log.append((page, i, ds[i], d[i]['tb'] or d[i]['ta'], 'listing adds nothing beyond the current line')); continue
        plan.setdefault(page, {})[i] = l; st['enriched'] += 1
for page, rows in plan.items():
    p = f'{REPO}/{page}/index.html'; s = open(p).read(); m, d = section_cards(s, 'Dining'); body = m.group(2)
    lis = list(re.finditer(r'<li\b.*?</li>', body, re.S)); out = []; last = 0
    for i, mm in enumerate(lis):
        li = mm.group(0)
        if i in rows:
            li = re.sub(r'<p class="place-desc">.*?</p>', lambda x: f'<p class="place-desc">{html.escape(rows[i], quote=False)}</p>', li, count=1, flags=re.S)
        out.append(body[last:mm.start()] + li); last = mm.end()
    body = ''.join(out) + body[last:]; open(p, 'w').write(s[:m.start(2)] + body + s[m.end(2):])
with open('enrich-left.csv', 'w', newline='') as f:
    w = csv.writer(f); w.writerow(['page', 'idx', 'line', 'url', 'reason']); w.writerows(log)
print(dict(st), 'left', len(log), collections.Counter(x[4][:30] for x in log), 'pages', len(plan))
