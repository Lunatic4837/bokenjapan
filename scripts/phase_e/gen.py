#!/usr/bin/env python3
"""Sourced Stay lines for the cards that still carried a generic 'A hotel in X' sentence.
Every phrase comes from the property's own Jalan listing (cached in html/): lodging type, hot-spring/open-air bath,
station access minutes, room count and style, free parking. Output: lines.json {page|idx: {line, source, fields}}."""
import json, re, html, sys, os, collections
sys.path.insert(0, '/workspace/p1/line4/work')
import generate as G
from maps import LODGING
D = os.path.dirname(os.path.abspath(__file__))
def cl(x): return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', x))).strip()
def field(s, th):
    m = re.search(r'<th[^>]*>\s*' + th + r'\s*</th>\s*(<td.*?</td>)', s, re.S); return cl(m.group(1)) if m else ''
def rooms(s):
    i = s.find('総部屋数</th>')
    if i < 0: return None
    hdr = re.findall(r'<th[^>]*>\s*([^<]+?)\s*</th>', s[max(0, i - 800):i + 10])[-5:]
    vals = [cl(x) for x in re.findall(r'<td[^>]*>(.*?)</td>', s[i:i + 1500], re.S)[:5]]
    d = {}
    for h, v in zip(hdr, vals):
        m = re.match(r'(\d+)\s*室', v.translate(G.Z2H))
        if m: d[h] = int(m.group(1))
    return d if d.get('総部屋数') else None
def walk_minutes(acc, pj):
    acc = acc.translate(G.Z2H)
    for stja, en, end in G.find_station_in(acc, pj):
        m = re.match(r'^(?:[東西南北中央新]*口|前)?\s*(?:より|から|下車)?[、,\s]*(徒歩|車|車で|お車で|タクシー|タクシーで)\s*(?:約)?\s*(\d{1,3})\s*分', acc[end:end + 30])
        if m:
            n = int(m.group(2))
            if m.group(1) == '徒歩' and n <= 30: return f'{n}-minute walk from {en}'
            if m.group(1) != '徒歩' and n <= 40: return f'{n} minutes by car from {en}'
    return None
cards = json.load(open(f'{D}/cards.json')); out = {}; why = collections.Counter()
for c in cards:
    yid = re.search(r'yad(\d+)', c['jalan']).group(1); p = f'{D}/html/{yid}.html'
    if not os.path.exists(p): why['no page'] += 1; continue
    s = open(p, encoding='utf-8', errors='replace').read()
    if 'yado-name' not in s: why['not a listing'] += 1; continue
    pref = c['page'].split('/')[0]; pj = G.PREF_JA[pref]
    m = re.search(r'<div class="yado-name">\[([^\]]+)\]', s); tja = m.group(1).strip() if m else None
    head = (LODGING.get(tja) or (c['old'].split(' in ')[0].replace('An ', '').replace('A ', '').capitalize())).split(' (')[0]
    onsen = field(s, '温泉'); oab = field(s, '露天風呂')
    has_onsen = bool(onsen) and not onsen.startswith('無し') and onsen not in ('なし', '-')
    labels = set(x.strip() for x in re.findall(r'<span class="c-label">([^<]+)</span>', s))
    flowing = has_onsen and ('掛け流し' in onsen or '温泉掛け流し' in labels)
    oab_yes = oab.startswith('あり') or oab.startswith('有')
    bath = ('free-flowing hot-spring baths' if flowing else 'hot-spring baths' if has_onsen else None)
    if oab_yes: bath = (bath + ' and an open-air bath') if bath else 'an open-air bath'
    accs = [cl(x) for x in re.findall(r'<p class="access">(.*?)</p>', s, re.S)] + [field(s, 'アクセス')]
    access = None
    for a in accs:
        access = walk_minutes(a, pj)
        if access: break
    if not access and '駅から徒歩5分以内' in labels: access = 'within a 5-minute walk of a station'
    r = rooms(s); rp = None
    if r:
        n = r['総部屋数']; w, j = r.get('洋室', 0), r.get('和室', 0) + r.get('和洋室', 0)
        style = 'Western-style ' if w == n else 'Japanese-style ' if r.get('和室', 0) == n else ''
        rp = f'{n} {style}room' + ('s' if n != 1 else '')
    park = field(s, 'パーキング'); free_park = park.startswith('有り（無料）') or park.startswith('有り(無料)')
    parts = []
    line = head
    if bath: line += ' with ' + bath
    for extra in [access, rp, 'free parking' if free_park else None]:
        if extra and G.words(line + ', ' + extra + '.') <= 14: line += ', ' + extra
    line += '.'
    if line == head + '.': why['nothing sourced'] += 1; continue
    out[f"{c['page']}|{c['idx']}"] = dict(line=line, source=c['jalan'], old=c['old'],
        fields=dict(type_ja=tja, onsen_ja=onsen or None, open_air_ja=oab or None, rooms=r, parking_ja=park or None, access_en=access))
    why['ok'] += 1
json.dump(out, open(f'{D}/lines.json', 'w'), ensure_ascii=False, indent=1)
print(dict(why))
per = collections.Counter((k.split('|')[0], v['line']) for k, v in out.items())
print('max repeats per page:', per.most_common(5))
for v in list(out.values())[:12]: print(v['line'])
