#!/usr/bin/env python3
"""Phase F Dining line 4. For each card that still carries a generic 'A restaurant in X' sentence, build a short
English line from the place's own Tabelog listing (TripAdvisor for TA-only cards): genre/cuisine, award or Top-100
status, station access, lunch/dinner budget band, opening hours, closed days, area (TA English address), parking/takeout.
Lines that would repeat >3 times on one page get more listing facts until they are distinct. Nothing is invented:
cards whose listing gives no usable fact keep a plain factual line and are logged in no-data.csv."""
import json, gzip, re, sys, os, csv, collections
sys.path.insert(0, '/workspace/p1/line4/work'); sys.path.insert(0, '/workspace/p1/phase-d/dining4')
import parsers as P, generate as G
import gen as B, facts_extra as X, ta_parse as T
D = os.path.dirname(os.path.abspath(__file__))
GENERIC = re.compile(r"^(?:An? )?[A-Za-z'\- ]+ in [A-Za-z\-ōū' ]+, [A-Za-z]+(?: prefecture)?\.$")
# JR Kesennuma/Ofunato BRT stations (bus rapid transit since 2011) missing from the rail station table
BRT = {'南気仙沼': 'Minami-Kesennuma', '不動の沢': 'Fudonosawa', '最知': 'Saichi', '鹿折唐桑': 'Shishiori-Karakuwa',
       '松岩': 'Matsuiwa', '陸前階上': 'Rikuzen-Hashikami', '小金沢': 'Koganezawa'}
HEP = re.compile(r"^(?:shi|chi|tsu|sh[aou]|ch[aou]|j[aiuo]|[kgsztdnhbpmr]y[aou]|[kgsztdnhbpmrwf]?[aiueo]|y[aou]|n)+$", re.I)
def clean_area(area):
    """Keep only romanized Japanese place-name words from TA's English address; machine-translated fragments
    (字 -> 'Character', building names, English words) are dropped. Aza/Oaza markers are removed."""
    if not area: return None
    ws = [w for w in area.split() if w not in ('Aza', 'Oaza', 'Character') and not w.startswith('Aza-')]
    ws = [w for i, w in enumerate(ws) if w not in ws[:i]]
    ok = lambda w: all(HEP.match(re.sub(r'([kstpgbdc])\1|t(?=ch)', r'\1', p.replace("'", ''), flags=re.I)) for p in w.split('-')) and w[:1].isupper()
    if ws and len(ws) <= 2 and all(ok(w) for w in ws): return ' '.join(ws)
    if ws and ok(ws[0]): return ws[0]
    return None
def W(x): return len(x.replace('–', ' ').split())
def tb_card(s, pref):
    line, kind, fields = B.from_tabelog(s, pref)
    if kind and str(kind).startswith('closed:'): return None, None, kind, {}
    h, cl = X.tb_hours(s)
    ext = []
    for k in ('free parking', 'parking', 'takeout only', 'takeout', 'private rooms'):
        if k in ((fields or {}).get('extras') or []) and not (line and k in line): ext.append(k)
    if not line:
        f = P.tabelog(s); g, _ = B.genre_en(f)
        if not (g or h or cl or ext): return None, None, 'no usable facts', {}
        line = (g or 'Restaurant') + '.'
        kind = 'tabelog-min'
    near = None
    if not (fields or {}).get('access_en'):
        m = re.search(r'<title>[^<]*? - ([^/<|]+)/[^<|]*\| 食べログ</title>', s)
        sj = re.sub(r'（[^）]*）$', '', m.group(1).strip()) if m else None
        en = (G.station_en(sj, G.PREF_JA[pref]) or BRT.get(sj)) if sj else None
        if en:
            en = en if en.endswith('Station') else en + ' Station'
            d = re.search(re.escape(sj) + r'駅から([\d,]+)m', P.tabelog(s).get('access') or '')
            near = f'{d.group(1)} m from {en}' if d and int(d.group(1).replace(',', '')) >= 1000 and int(d.group(1).replace(',', '')) < 10000 else (
                   f'{d.group(1)} m from {en}' if d else 'near ' + en)
    extra = [x for x in (near, h, cl) if x] + ext
    return line, extra, kind, dict(fields or {}, hours=h, closed=cl, near=near)
def ta_card(s):
    line, kind, fields = B.from_ta(s)
    if kind == 'closed': return None, None, kind, {}
    d = T.decoded(s); area = X.ta_area(d)
    area = clean_area(area)
    ld = next((x for x in P.ldjson(s) if isinstance(x, dict) and x.get('openingHoursSpecification')), {})
    h, cl = X.ta_hours(ld)
    if h and re.search(r'open (\d\d):\d\d–(\d\d):', h):
        o, c = map(int, re.search(r'open (\d\d):\d\d–(\d\d):', h).groups())
        if c < o and c > 6: h = None  # implausible overnight range; skip
    if not line:
        if not (area or h): return None, None, 'no usable facts', {}
        line = 'Restaurant.'; kind = 'ta-min'
    if area:
        head = line.rstrip('.')
        if ' serving ' in head:
            a, b = head.split(' serving ', 1); line = f'{a} in {area}, serving {b}.'
        elif ',' in head or ';' in head:
            a, b = re.split(r'(?=[,;])', head, 1); line = f'{a} in {area}{b}.'
        else: line = f'{head} in {area}.'
    extra = [x for x in (h, cl) if x]
    alt = None
    m = re.search(r'"localizedRealtimeAddress":"(\d+)-[^",]*? ' + re.escape(area) + r',', d) if area else None
    if m: alt = line.replace(f' in {area}', f' in {area} {m.group(1)}-chome', 1)
    return line, extra, kind, dict(fields or {}, area=area, hours=h, closed=cl, alt=alt)
def join(line, extra, n):
    out = line.rstrip('.')
    for e in extra[:n]:
        cand = out + ('; ' if ';' in out or ',' in out else ', ') + e
        if W(cand) > 18: break
        out = cand
    return out + '.'
def main():
    cards = json.load(open('/workspace/p1/phase-d/dining4_cards.json'))
    F = B.load_fetched(); st = collections.Counter(); nodata = []; items = {}
    for c in cards:
        pref = c['page'].split('/')[0]; key = f"{c['page']}|Dining|{c['idx']}"
        u = c['tb'] or c['ta']; host = 'tb' if c['tb'] else 'ta'
        if not u: nodata.append(dict(card_key=key, old=c['old'], url=c['href'], reason='no listing url')); continue
        s, r = B.page(F, u)
        if not r: st['pending', host] += 1; continue
        if r['state'] == 'gone': nodata.append(dict(card_key=key, old=c['old'], url=u, reason='listing gone (404)')); continue
        if not s: nodata.append(dict(card_key=key, old=c['old'], url=u, reason=f"fetch {r['state']}")); continue
        line, extra, kind, fields = (tb_card(s, pref) if host == 'tb' else ta_card(s))
        if kind and (kind == 'closed' or str(kind).startswith('closed:')):
            nodata.append(dict(card_key=key, old=c['old'], url=u, reason=f'listing marks the place {kind}')); continue
        if not line:
            nodata.append(dict(card_key=key, old=c['old'], url=u, reason=f'no usable facts on {"Tabelog" if host=="tb" else "TripAdvisor"} listing beyond the name'))
            continue
        items[key] = dict(page=c['page'], base=line, extra=extra, kind=kind, fields=fields, source=u, old=c['old'])
    # bare lines first get one extra fact; then de-duplicate per page
    for k, it in items.items():
        bare = (',' not in it['base'] and ';' not in it['base'])
        it['n'] = 1 if bare else 0
        it['line'] = join(it['base'], it['extra'], it['n'])
    for rnd in range(4):
        cnt = collections.Counter((it['page'], it['line']) for it in items.values())
        changed = 0
        for it in items.values():
            if cnt[(it['page'], it['line'])] > 3:
                if it['n'] < len(it['extra']): it['n'] += 1
                elif it['fields'].get('alt') and it['base'] != it['fields']['alt']: it['base'] = it['fields']['alt']
                else: continue
                it['line'] = join(it['base'], it['extra'], it['n']); changed += 1
        if not changed: break
    out = {}
    for k, it in items.items():
        line = B.scrub(it['line']); line = line[:1].upper() + line[1:]
        if len(line) < 15:  # e.g. 'Cafe.' - listing gives only the genre, which the existing line already says
            nodata.append(dict(card_key=k, old=it['old'], url=it['source'], reason='listing gives only a genre (line too short); kept existing line')); continue
        if GENERIC.match(line): nodata.append(dict(card_key=k, old=it['old'], url=it['source'], reason='only the place name/area on listing')); continue
        out[k] = dict(line=line, source=it['source'], kind=it['kind'], old=it['old'], fields=it['fields'])
        st['ok', it['kind']] += 1
    json.dump(out, open(f'{D}/lines.json', 'w'), ensure_ascii=False)
    with open(f'{D}/no-data.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['card_key', 'old', 'url', 'reason']); w.writeheader(); w.writerows(nodata)
    print(dict(st)); print('lines', len(out), 'no-data', len(nodata), collections.Counter(r['reason'][:40] for r in nodata).most_common(6))
    cnt = collections.Counter((v['line']) for v in out.values()); print('top', cnt.most_common(10))
    per = collections.Counter((k.split('|')[0], v['line']) for k, v in out.items())
    print('pages with a line >3x:', len({p for (p, l), n in per.items() if n > 3}), [(p, l, n) for (p, l), n in per.most_common(5)])
if __name__ == '__main__': main()
