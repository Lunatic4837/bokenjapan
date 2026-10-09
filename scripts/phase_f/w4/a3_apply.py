#!/usr/bin/env python3
"""Wave 4 item 3: line-2 English names where a kanji place name was romanized character by character
(亘理 -> 'Kou Ri', 苅田 -> 'Karida', 女川 -> 'Megawa', 小倉 -> 'Ogura'). The place's real English name comes from the
municipality table (geo.json) or the 5-prefecture station table (Wikidata). Only applied where the kanji is used as a
place: directly before 店/本店/支店/駅/空港/インター/営業所/前店, or it is the page's own town. Writes names-fixed.csv."""
import sys, re, html, csv, collections, unicodedata, json
sys.path.insert(0, '/workspace/p1/phase-d/w4'); sys.path.insert(0, '/workspace/p1/phase-d/w3')
from a3_lib import *; from cards_lib import *
PL = build_places(); geo = json.load(open('/workspace/p1/phase-d/nostay/geo.json'))
for k, v in geo.items():  # municipality short form: 大崎 -> Osaki (not 'Osakishi'), 柴田 -> Shibata
    b = re.sub(r'[市町村]$', '', v['ja'])
    if b in PL and b != v['ja']: PL[b] = re.sub(r'(?<=[a-z])(shi|cho|machi|mura|son)$', '', PL[b]) or PL[b]
for bad in ('市場', '上杉', '江崎', '本町', '中央', '駅前', '新町', '大町', '東口', '西口'): PL.pop(bad, None)
KEYS = sorted(PL, key=len, reverse=True)
CTX = re.compile(r'^(?:\s*)(?:本店|支店|店|駅|空港|インター|IC|営業所|前店|駅前店)')
st = collections.Counter(); rows = []
for page, p in pages():
    if page.split('/')[0] not in PREFS: continue
    s = open(p).read(); orig = s; own = re.sub(r'[市町村]$', '', geo.get(page, {}).get('ja', ''))
    for sec in ('Stay', 'Dining'):
        m, d = section_cards(s, sec)
        if not d: continue
        body = m.group(2); lis = list(re.finditer(r'<li\b.*?</li>', body, re.S)); out = []; last = 0
        for mm in lis:
            li = mm.group(0); c = parse_li(li); ja = unicodedata.normalize('NFKC', c['name'] or ''); en = c['en'] or ''; new = en
            rem = ja
            for k in KEYS:
                i = rem.find(k)
                if i < 0: continue
                rem = rem.replace(k, '\0' * len(k))
                if not (CTX.match(ja[i + len(k):]) or k == own): continue
                R = PL[k]
                if flat(R) in flat(new): continue
                rx = wrong_rx(k); f = rx.search(new) if rx else None
                if not f: st['place not found in EN'] += 1; continue
                new = new[:f.start()] + R + new[f.end():]
            if new != en:
                li = li.replace(f'<p class="place-blurb">{html.escape(en, quote=True)}</p>', f'<p class="place-blurb">{html.escape(new, quote=True)}</p>', 1) \
                    if f'<p class="place-blurb">{html.escape(en, quote=True)}</p>' in li else re.sub(r'<p class="place-blurb">.*?</p>', lambda x: f'<p class="place-blurb">{html.escape(new, quote=True)}</p>', li, count=1, flags=re.S)
                if '<img' in li: li = re.sub(r'(<img class="thumb"[^>]*alt=")' + re.escape(html.escape(en, quote=True)) + '"', lambda x: x.group(1) + html.escape(new, quote=True) + '"', li)
                st['fixed ' + sec] += 1; rows.append(dict(page=page, section=sec, name_ja=c['name'], old_en=en, new_en=new))
            out.append(body[last:mm.start()] + li); last = mm.end()
        body = ''.join(out) + body[last:]; s = s[:m.start(2)] + body + s[m.end(2):]
    if s != orig: open(p, 'w').write(s); st['pages'] += 1
with open('names-fixed.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['page', 'section', 'name_ja', 'old_en', 'new_en']); w.writeheader(); w.writerows(rows)
print(dict(st))
