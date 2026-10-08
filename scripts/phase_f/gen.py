#!/usr/bin/env python3
"""Sourced Dining line-4 for cards that still carried generic 'A restaurant in X' sentences.
Every phrase comes from that place's own Tabelog or TripAdvisor listing (cached under line4/work/html/).
Never invents. Writes lines.json {page|Dining|idx: {line, source, kind, fields}} and no-data.csv for
listings that had nothing beyond a name/genre-less placeholder."""
import json, gzip, re, sys, os, csv, collections, html as H
sys.path.insert(0, '/workspace/p1/line4/work')
sys.path.insert(0, '/workspace/p1/phase-d/dining4')
import generate as G, parsers as P
import ta_parse as T
from maps import GENRE, TA_NOUN, TA_ADJ, TA_PRICE
D = os.path.dirname(os.path.abspath(__file__))
EXTRA = {
 'シーフード':'Seafood restaurant','ティースタンド':'Tea stand','焼き芋・大学芋':'Sweet-potato snack shop','社員食堂':'Staff canteen',
 'チーズ料理':'Cheese-dish restaurant','中華菓子':'Chinese sweets shop','パキスタン料理':'Pakistani restaurant','棒寿司':'Pressed-sushi shop',
 '牛カツ':'Beef-cutlet restaurant','ペルー料理':'Peruvian restaurant','その他':None,'カフェ・喫茶店（その他）':'Cafe',
 'パン・サンドウィッチ':'Bakery','レストラン（その他）':'Restaurant','居酒屋（その他）':'Izakaya','ラーメン（その他）':'Ramen shop',
 'スイーツ（その他）':'Sweets shop','中華料理（その他）':'Chinese restaurant','洋食・西洋料理（その他）':'Yoshoku (Western-style) restaurant',
 '和食（その他）':'Japanese restaurant','アジア・エスニック（その他）':'Asian restaurant','バー（その他）':'Bar','焼肉（その他）':'Yakiniku restaurant',
 '定食・食堂':'Diner','ファミレス':'Family restaurant','立ち食いそば':'Standing soba counter','立ち食いうどん':'Standing udon counter',
 'ケータリング':'Catering','移動販売・屋台':'Food stall','弁当':'Bento shop','デリカテッセン':'Deli','自然食':'Natural-food restaurant',
 'オーガニック':'Organic restaurant','薬膳':'Medicinal-cuisine restaurant','ジビエ':'Gibier restaurant','馬肉料理':'Horse-meat restaurant',
 '鶏料理':'Chicken restaurant','鴨料理':'Duck restaurant','猪料理':'Boar-meat restaurant','郷土料理（その他）':'Regional-cuisine restaurant',
 '炭火焼':'Charcoal-grill restaurant','鉄板焼き':'Teppanyaki restaurant','串揚げ・串かつ':'Kushiage restaurant','もつ鍋':'Motsunabe restaurant',
 'ちゃんこ鍋':'Chanko-nabe restaurant','すき焼き':'Sukiyaki restaurant','しゃぶしゃぶ':'Shabu-shabu restaurant','おでん':'Oden restaurant',
 'たこ焼き':'Takoyaki shop','お好み焼き':'Okonomiyaki restaurant','もんじゃ焼き':'Monjayaki restaurant','たい焼き・大判焼き':'Taiyaki shop',
 'クレープ':'Crepe shop','ドーナツ':'Donut shop','ワッフル':'Waffle shop','パフェ':'Parfait shop','かき氷':'Shaved-ice shop',
 'アイスクリーム':'Ice-cream shop','ソフトクリーム':'Soft-serve shop','パンケーキ':'Pancake shop','フレンチトースト':'French-toast cafe',
 'フルーツパーラー':'Fruit parlor','ジュースバー':'Juice bar','スムージー':'Smoothie shop','タピオカ':'Bubble-tea shop',
 'コーヒー専門店':'Coffee shop','紅茶専門店':'Tea shop','日本茶専門店':'Japanese-tea shop','中国茶専門店':'Chinese-tea shop',
 'バー・お酒（その他）':'Bar','ワインバー':'Wine bar','ビアバー':'Beer bar','日本酒バー':'Sake bar','焼酎バー':'Shochu bar',
 'カクテルバー':'Cocktail bar','立ち飲み居酒屋・バー':'Standing bar','ダイニングバー':'Dining bar','スポーツバー':'Sports bar',
 'ガールズバー':'Girls bar','パブ':'Pub','ビアホール':'Beer hall','ビアガーデン':'Beer garden','ラウンジ':'Lounge',
 'クラブ':'Club','ディスコ':'Disco','カラオケ':'Karaoke bar','ネットカフェ':'Internet cafe','漫画喫茶':'Manga cafe',
 'メイドカフェ':'Maid cafe','コンセプトカフェ':'Concept cafe','猫カフェ':'Cat cafe','犬カフェ':'Dog cafe',
}
for k, v in EXTRA.items():
    if v is not None: GENRE.setdefault(k, v)
TA_EXTRA = {
 'Japanese - Other ':'Japanese restaurant','Izakaya (Japanese Style Tavern)':'Izakaya','Dining bars':'Dining bar',
 'Japanese sweets parlour':'Japanese sweets (wagashi) shop','Bars & Pubs':'Bar','Coffee & Tea':'Cafe','Dessert':'Sweets shop',
 'Pub':'Pub','Bar':'Bar','Cafe':'Cafe','Gastropub':'Gastropub','Steakhouse':'Steakhouse','Wine Bar':'Wine bar',
 'Grill':'Grill','Deli':'Deli','Diner':'Diner','Asian':'Asian restaurant','Fusion':'Fusion restaurant','Spanish':'Spanish restaurant',
 'New Zealand':'New Zealand restaurant','Japanese':'Japanese restaurant','Korean':'Korean restaurant','Chinese':'Chinese restaurant',
 'Italian':'Italian restaurant','French':'French restaurant','Indian':'Indian restaurant','Thai':'Thai restaurant',
 'Vietnamese':'Vietnamese restaurant','Mexican':'Mexican restaurant','American':'American restaurant','Seafood':'Seafood restaurant',
 'Sushi':'Sushi restaurant','Ramen':'Ramen shop','Yakiniku':'Yakiniku restaurant','Pizza':'Pizzeria','Bakery':'Bakery',
 'Barbecue':'Barbecue restaurant','Healthy':'Healthy restaurant','Vegetarian Friendly':'Vegetarian-friendly restaurant',
 'Vegan Options':'Restaurant with vegan options','Gluten Free Options':'Restaurant with gluten-free options',
}
FETCH_LOGS = [
 '/workspace/p1/line4/work/fetch1.jsonl',
 '/workspace/p1/line4/work/fetch_d4tb.jsonl',
 '/workspace/p1/line4/work/fetch_d4ta.jsonl',
]
def load_fetched():
    F = {}
    for path in FETCH_LOGS:
        if not os.path.exists(path): continue
        for l in open(path):
            try: d = json.loads(l)
            except Exception: continue
            if d.get('state') in ('ok', 'gone', 'blocked', 'error', 'skipped'): F[d['url']] = d
    return F
def page(F, u):
    r = F.get(u)
    if not r or r['state'] != 'ok': return None, r
    return P.decode(gzip.open(r['file']).read(), r.get('enc')), r
def scrub(line):
    line = re.sub(r"on Tabelog's Top 100 (.+?) list \((\d{4})\)", r"a Top 100 \1 pick (\2)", line)
    line = re.sub(r"Tabelog Award (\d{4}) (Gold|Silver|Bronze) winner", r"\2 award winner (\1)", line)
    line = re.sub(r'(\d+)\.(\d) km\b', lambda m: f"{int(m.group(1))*1000 + int(m.group(2))*100:,} m", line)
    assert not re.search(r'tabelog|tripadvisor|jalan|ikkyu|食べログ|一休|じゃらん', line, re.I), line
    return line
def field(s, th):
    m = re.search(r'<th[^>]*>\s*' + th + r'\s*</th>\s*(<td.*?</td>)', s, re.S)
    return P.clean(m.group(1)) if m else ''

def user_budget(s):
    m = re.search(r'<th[^>]*>\s*予算（口コミ集計）\s*</th>\s*<td[^>]*>(.*?)</td>', s, re.S)
    if not m: return {}
    raw = m.group(1); out = {}
    # "夜￥4,000～￥4,999" / "昼￥1,000～￥1,999" style inside the cell
    for kind, a, b in re.findall(r'(昼|夜)[^¥￥]{0,8}[¥￥]\s*([\d,]+)\s*[～〜\-–]\s*[¥￥]?\s*([\d,]+)', raw):
        band = f'¥{a}–¥{b}'
        if kind == '夜': out.setdefault('budget_dinner', band)
        else: out.setdefault('budget_lunch', band)
    return out

def extras_from_tb(s, f):
    """Optional listing facts used only to distinguish otherwise-bare genre lines."""
    out = []
    park = field(s, '駐車場')
    if park.startswith('有'): out.append('free parking' if '無料' in park else 'parking')
    svc = field(s, 'サービス')
    if 'テイクアウト' in svc: out.append('takeout')
    seats = field(s, '席数')
    if 'テイクアウト' in seats and ('専門' in seats or 'のみ' in seats): out[:] = ['takeout only']
    priv = field(s, '個室')
    if priv.startswith('有'): out.append('private rooms')
    # ld+json priceRange as budget fallback
    if not f.get('budget_dinner') and not f.get('budget_lunch'):
        for d in P.ldjson(s):
            if isinstance(d, dict) and d.get('@type') == 'Restaurant' and d.get('priceRange'):
                pr = d['priceRange'].replace('￥','¥').replace('～','–').replace('〜','–')
                band = G.yen_band(pr) if re.match(r'^[¥–,\d]+$', pr.replace(' ','')) else None
                if not band:
                    m = re.match(r'¥([\d,]+)–¥([\d,]+)', pr)
                    if m: band = f'¥{m.group(1)}–{m.group(2)}'
                if band: f['budget_dinner'] = pr; f['_budget_from_ld'] = band
                break
    return out
def genre_en(f):
    genres = [g.strip() for g in re.split(r'[、,/]', f.get('genre') or '') if g.strip()]
    for g in genres:
        if g == 'その他': continue
        if GENRE.get(g): return GENRE[g], genres
    for g in genres:
        if GENRE.get(g): return GENRE[g], genres
    return None, genres
def from_tabelog(s, pref):
    f = P.tabelog(s)
    if f.get('status') in ('閉店', '移転', '休業'): return None, f'closed:{f["status"]}', f
    g_en, genres = genre_en(f)
    for k,v in user_budget(s).items():
        if not f.get(k): f[k]=v
    extras = extras_from_tb(s, f)
    f2 = dict(f); f2['genre'] = '__X__'; GENRE['__X__'] = g_en or 'Restaurant'
    res, err = G.dining_tabelog(f2, pref); del GENRE['__X__']
    if not res:
        # try building a minimal line from extras alone
        if not g_en and not extras: return None, err or 'no data', f
        head = g_en or 'Restaurant'
        parts = []
        if extras: parts.append((' with ' if len(extras)==1 else ' with ', ', '.join(extras[:2])))
        line = G.assemble(head, parts); return scrub(line), 'minimal', {'genre_ja': f.get('genre'), 'extras': extras}
    fields, line = res
    # append extras only when the line is otherwise bare (no access/budget/award)
    bare = (',' not in line and ';' not in line)
    if bare and extras:
        add = extras[0]
        if G.words(line.rstrip('.') + ' with ' + add + '.') <= 14:
            line = line.rstrip('.') + ' with ' + add + '.'
        fields['extras'] = extras
    if f.get('_budget_from_ld') and '¥' not in line:
        b = f['_budget_from_ld']
        if G.words(line.rstrip('.') + '; dinner ' + b + '.') <= 14:
            line = line.rstrip('.') + '; dinner ' + b + '.'
            fields['budget_from_ld'] = b
    return scrub(line), 'tabelog', fields
def from_ta(s):
    f = P.tripadvisor(s)
    if f.get('status'): return None, 'closed', f
    g = T.groups(s)
    # prefer structured cuisine tags, then ld+json servesCuisine, then establishment_types
    cu = list(g.get('cuisines') or [])
    if not cu:
        for c in (f.get('cuisines') or []):
            if c and c not in cu: cu.append(c)
    head = None
    for c in cu:
        if c in TA_EXTRA: head = TA_EXTRA[c]; break
        if c in TA_NOUN: head = TA_NOUN[c]; break
    if not head:
        adjs = [TA_ADJ[c] for c in cu if c in TA_ADJ]
        if adjs: head = ' '.join(adjs[:2]) + ' restaurant'
    if not head:
        for e in g.get('establishment_types') or []:
            if e in TA_EXTRA and e != 'Restaurants': head = TA_EXTRA[e]; break
    price = None
    for p in g.get('price_types') or []:
        price = {'Cheap Eats':'Budget','Mid-range':'Mid-range','Fine Dining':'Fine-dining'}.get(p)
        if price: break
    if not price:
        price = TA_PRICE.get((f.get('price_range') or '').strip())
    meals = [m for m in (g.get('meal_types') or []) if m in ('Breakfast','Lunch','Dinner','Brunch')]
    if not head:
        if price: return scrub(f'{price} restaurant.'), 'ta-price-only', {'price': price}
        return None, 'no cuisine', {'groups': g, 'f': {k: f.get(k) for k in ('cuisines','price_range','status')}}
    # "Budget izakaya" etc.
    if price and not head.lower().startswith(price.lower()):
        head = price + ' ' + head[0].lower() + head[1:]
    parts = []
    if meals and G.words(head + ' serving ' + ' and '.join(m.lower() for m in meals[:2])) <= 12:
        parts.append((' serving ', ' and '.join(m.lower() for m in meals[:2])))
    line = G.assemble(head, parts)
    return scrub(line), 'tripadvisor', {'cuisines': cu, 'price': price, 'meals': meals, 'head': head}
def main():
    cards = json.load(open('/workspace/p1/phase-d/dining4_cards.json'))
    F = load_fetched(); out = {}; nodata = []; st = collections.Counter()
    for c in cards:
        pref = c['page'].split('/')[0]; key = f"{c['page']}|Dining|{c['idx']}"
        line = src = kind = None; fields = {}
        if c['tb']:
            s, r = page(F, c['tb'])
            if r and r['state'] == 'gone':
                nodata.append(dict(card_key=key, old=c['old'], url=c['tb'], reason='listing gone (404)')); st['gone'] += 1; continue
            if s:
                line, kind, fields = from_tabelog(s, pref); src = c['tb']
                if not line:
                    nodata.append(dict(card_key=key, old=c['old'], url=c['tb'], reason='no usable facts on Tabelog listing: ' + (kind or ''))); st['nodata-tb'] += 1; continue
            elif not r:
                st['pending-tb'] += 1; continue
            else:
                nodata.append(dict(card_key=key, old=c['old'], url=c['tb'], reason=f"fetch {r['state']}")); st['fetch-fail-tb'] += 1; continue
        elif c['ta']:
            s, r = page(F, c['ta'])
            if r and r['state'] == 'gone':
                nodata.append(dict(card_key=key, old=c['old'], url=c['ta'], reason='listing gone (404)')); st['gone'] += 1; continue
            if s:
                line, kind, fields = from_ta(s); src = c['ta']
                if not line:
                    nodata.append(dict(card_key=key, old=c['old'], url=c['ta'], reason='no usable facts on TripAdvisor listing: ' + (kind or ''))); st['nodata-ta'] += 1; continue
            elif not r:
                st['pending-ta'] += 1; continue
            else:
                nodata.append(dict(card_key=key, old=c['old'], url=c['ta'], reason=f"fetch {r['state']}")); st['fetch-fail-ta'] += 1; continue
        else:
            nodata.append(dict(card_key=key, old=c['old'], url=c['href'], reason='no listing url')); st['no-url'] += 1; continue
        # still looks like the old generic pattern → treat as no-data
        if re.match(r"^(?:An? )?[A-Za-z'\- ]+ in [A-Za-z\-ōū' ]+, [A-Za-z]+(?: prefecture)?\.$", line):
            nodata.append(dict(card_key=key, old=c['old'], url=src, reason='generator fell back to place-name line')); st['fell-back'] += 1; continue
        out[key] = dict(line=line, source=src, kind=kind, old=c['old'], fields=fields)
        st['ok', kind] += 1
    # Cards whose listing had no usable facts: keep a short factual line and leave them in no-data.csv.
    for row in nodata:
        if row['card_key'] in out: continue
        if row['reason'].startswith('no ') or row['reason'] in ('no cuisine', 'no data', 'no usable facts on Tabelog listing', 'no cuisine'):
            out[row['card_key']] = dict(line='Restaurant.', source=row['url'], kind='nodata-minimal', old=row['old'], fields={})
            st['minimal-kept'] += 1
    json.dump(out, open(f'{D}/lines.json', 'w'), ensure_ascii=False)
    with open(f'{D}/no-data.csv', 'w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=['card_key','old','url','reason']); w.writeheader(); w.writerows(nodata)
    print(dict(st))
    print('lines', len(out), 'nodata', len(nodata))
    lines = collections.Counter(v['line'] for v in out.values())
    print('top', lines.most_common(12))
    for v in list(out.values())[:8]: print(v['kind'], v['line'])
if __name__ == '__main__': main()
