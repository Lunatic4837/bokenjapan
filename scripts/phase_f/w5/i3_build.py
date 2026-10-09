#!/usr/bin/env python3
"""Item 3 step 3: card data for confirmed inns (JA name, EN name, line 4 from the Jalan listing, photo candidates)."""
import sys, re, json, html, unicodedata, collections, os
sys.path.insert(0, '/workspace/p1/line4/work'); sys.path.insert(0, '/workspace/p1/phase-d/dining4'); sys.path.insert(0, '/workspace/p1/phase-d/w5'); sys.path.insert(0, '/workspace/p1/phase-d/w3')
os.chdir('/workspace/p1'); os.makedirs('/tmp/kd/scripts/phase_d/names', exist_ok=True); os.chdir('/tmp/kd'); os.path.exists('scripts/phase_d/names/kdict.json') or os.symlink('/workspace/p1/phase-d/names/kdict.json', 'scripts/phase_d/names/kdict.json'); sys.path.insert(0, '/workspace/p1/pr12-work/scripts/phase_d/names')
import gen as B
B.FETCH_LOGS.append('/workspace/p1/line4/work/fetch_w4tb.jsonl')
import generate as G
from maps import LODGING
import en2, n4_rules
from cards_lib import *
F = B.load_fetched()
OVERRIDE_OK = {('akita/semboku', '新玉川温泉'), ('miyagi/kesennuma', '旅館 明海荘'), ('miyagi/osakishi', '旅館なんぶ屋'), ('miyagi/zao', 'ペンションそらまめ'), ('oita/yufu', '開花亭')}
V = json.load(open('/workspace/p1/phase-d/w5/i3_verify.json'))
def cl(x): return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', x))).strip()
def field(s, th):
    m = re.search(r'<th[^>]*>\s*' + th + r'\s*</th>\s*(<td.*?</td>)', s, re.S); return cl(m.group(1)) if m else ''
exec(open('/workspace/p1/phase-d/stay4/gen.py').read().split('cards = json.load')[0].split('def rooms')[1].join(['def rooms', '']) if False else '')
src = open('/workspace/p1/phase-d/stay4/gen.py').read()
ns = {'__file__': '/workspace/p1/phase-d/stay4/gen.py'}; exec(src.split('cards = json.load')[0], ns)
rooms, walk_minutes = ns['rooms'], ns['walk_minutes']
def line4(s, pref):
    pj = G.PREF_JA[pref]
    m = re.search(r'<div class="yado-name">\[([^\]]+)\]', s); tja = m.group(1).strip() if m else None
    head = LODGING.get(tja)
    if not head: return None, tja
    head = head.split(' (')[0]
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
        n = r['総部屋数']; w = r.get('洋室', 0)
        style = 'Western-style ' if w == n else 'Japanese-style ' if r.get('和室', 0) == n else ''
        rp = f'{n} {style}room' + ('s' if n != 1 else '')
    park = field(s, 'パーキング'); free_park = park.startswith('有り（無料）') or park.startswith('有り(無料)')
    line = head
    if bath: line += ' with ' + bath
    for extra in [access, rp, 'free parking' if free_park else None]:
        if extra and G.words(line + ', ' + extra + '.') <= 14: line += ', ' + extra
    return line + '.', tja
def clean_name(n):
    n = unicodedata.normalize('NFKC', n).strip()
    n = re.sub(r'\s*[~〜～].*?[~〜～]\s*', ' ', n)
    n = re.sub(r'[［\[]([^］\]]+)[］\]]', r'\1', n)
    rd = re.search(r'\(([\u3041-\u309fー]+)\)', n); reading = rd.group(1) if rd else None
    n = re.sub(r'\s*\([\u3041-\u309f\u30a0-\u30ffー]+\)', '', n)
    n = re.sub(r'\s+', ' ', n).strip()
    return n, reading
def tb_hp(tb):
    h, r = B.page(F, tb)
    if not h: return None
    m = re.search(r'<th[^>]*>\s*ホームページ\s*</th>\s*<td[^>]*>(.*?)</td>', h, re.S)
    if not m: return None
    u = re.search(r'href="(https?://[^"]+)"', m.group(1)) or re.search(r'(https?://\S+)', cl(m.group(1)))
    return u.group(1) if u else None
idx = json.load(open('/workspace/p1/phase-d/w5/jalan_index.json'))
out = []; seen = set(); st = collections.Counter()
for c in V:
    ok = c['verdict'].startswith('confirmed') or (c['page'], c['name']) in OVERRIDE_OK
    if not ok or not c['jalan_url']: continue
    k = (c['page'], c['jalan_url'])
    if k in seen: continue
    seen.add(k)
    yid = re.search(r'yad(\d+)', c['jalan_url']).group(1)
    s = open(f'/workspace/p1/phase-d/stay4/html/{yid}.html', encoding='utf-8', errors='replace').read()
    m = re.search(r'class="yado-name">([^<]+)</a>', s)
    jn = m.group(1) if m else idx[c['jalan_url']]['name']
    name, reading = clean_name(jn)
    l4, tja = line4(s, c['page'].split('/')[0])
    og = re.search(r'og:image" content="([^"]+)', s)
    out.append(dict(page=c['page'], tb_name=c['name'], tabelog_url=c['tabelog_url'], jalan_url=c['jalan_url'], yid=yid, jalan_name_raw=jn, name=name, reading=reading,
                    type_ja=tja, line4=l4, order=idx.get(c['jalan_url'], {}).get('order'), jalan_img=idx.get(c['jalan_url'], {}).get('image'), og_img=og.group(1) if og else None, hp=tb_hp(c['tabelog_url'])))
json.dump(out, open('/workspace/p1/phase-d/w5/i3_cards.json', 'w'), ensure_ascii=False, indent=0)
print(len(out))
for x in out: print(x['page'], '|', x['name'], '|', x['reading'], '|', x['type_ja'], '|', x['line4'], '|', x['hp'])
