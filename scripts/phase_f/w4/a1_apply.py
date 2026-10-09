#!/usr/bin/env python3
"""Wave 4 item 1: TripAdvisor-only Dining cards whose Japanese name (and photo) were taken from a Tabelog listing that is
>500 m from the TripAdvisor place are unmatched: line 1 and line 2 become the TripAdvisor listing's own name, and the
borrowed Tabelog photo + credit are removed (TripAdvisor has no photo of its own for these: placeholder only). The
photo-less cards are logged in photos-5pref/no-photo-found.csv (accepted state, rule 3)."""
import sys, re, json, csv, html, collections
sys.path.insert(0, '/workspace/p1/line4/work'); sys.path.insert(0, '/workspace/p1/phase-d/dining4'); sys.path.insert(0, '/workspace/p1/phase-d/w3')
import gen as B, parsers as P
from cards_lib import *
F = B.load_fetched()
C = [x for x in json.load(open('/workspace/p1/phase-d/w4/a1_candidates.json')) if x['dist'] and x['dist'] > 500]
byp = collections.defaultdict(dict)
for x in C:
    s, r = B.page(F, x['ta'])
    nm = next((e.get('name') for e in P.ldjson(s or '') if isinstance(e, dict) and e.get('@type') in ('FoodEstablishment', 'Restaurant')), None)
    if nm: byp[x['page']][x['ta']] = dict(x, ta_name=html.unescape(nm).strip())
rows = []; st = collections.Counter()
for page, cards in byp.items():
    p = f'{REPO}/{page}/index.html'; s = open(p).read(); m, d = section_cards(s, 'Dining'); body = m.group(2)
    def f(mm):
        li = mm.group(0); c = parse_li(li)
        if c['tb'] or c['ta'] not in cards: return li
        x = cards[c['ta']]; n = html.escape(x['ta_name'], quote=False)
        li = re.sub(r'<p class="place-name">.*?</p>', lambda _: f'<p class="place-name">{n}</p>', li, count=1, flags=re.S)
        li = re.sub(r'<p class="place-blurb">.*?</p>', lambda _: f'<p class="place-blurb">{n}</p>', li, count=1, flags=re.S)
        li = re.sub(r'<img class="thumb"[^>]*>', '', li, count=1)
        li = re.sub(r'<!-- photo-credit: .*? -->', '', li, count=1)
        idx = [parse_li(z)['ta'] for z in re.findall(r'<li\b.*?</li>', body, re.S)].index(c['ta'])
        rows.append({'card_key': f'{page}|Dining|{idx}', 'name_ja': '', 'urls_tried': f"ta-page:{c['ta']}:200 | ta-img-placeholder | tabelog-match:{x['tb']} rejected ({x['dist']} m from the TripAdvisor place)",
                     'reason': 'matched Tabelog listing (and its photo) is a different place >500 m away; TripAdvisor listing has only a placeholder image',
                     'group': 'W4', 'card_name_on_page': x['ta_name'], 'listing_url': c['ta']})
        st['unmatched'] += 1; return li
    body = re.sub(r'<li\b.*?</li>', f, body, flags=re.S)
    open(p, 'w').write(s[:m.start(2)] + body + s[m.end(2):])
NP = '/workspace/p1/photos-5pref/no-photo-found.csv'
hdr = next(csv.reader(open(NP)))
with open(NP, 'a', newline='') as fh:
    w = csv.DictWriter(fh, fieldnames=hdr); w.writerows(rows)
with open('/workspace/p1/phase-d/w4/ta-unmatched.csv', 'w', newline='') as fh:
    w = csv.writer(fh); w.writerow(['page', 'old_name_ja', 'old_en', 'new_name', 'ta_url', 'rejected_tabelog', 'dist_m'])
    for pg, cs in byp.items():
        for x in cs.values(): w.writerow([pg, x['name'], x['en'], x['ta_name'], x['ta'], x['tb'], x['dist']])
print(dict(st), 'logged', len(rows))
