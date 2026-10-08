#!/usr/bin/env python3
"""Build line-4 text for every unsourced card: facts.jsonl (fact-based) + neutral fallbacks
derived only from the fetched source page (genre/category, station access, budget, price band) or,
when nothing is on the page, the section + municipality. Writes phase-d/line4_all.json."""
import sys, json, csv, gzip, re, collections, os
sys.path.insert(0, '/workspace/p1/line4/work')
import generate as G, parsers as P, sights as S
W = '/workspace/p1/line4/work'
EXTRA_GENRE = {'シーフード':'Seafood restaurant','ティースタンド':'Tea stand','焼き芋・大学芋':'Sweet-potato snack shop','社員食堂':'Staff canteen',
 'チーズ料理':'Cheese-dish restaurant','中華菓子':'Chinese sweets shop','パキスタン料理':'Pakistani restaurant','棒寿司':'Pressed-sushi shop',
 '牛カツ':'Beef-cutlet restaurant','ペルー料理':'Peruvian restaurant'}
CAT_EN = {'名所・史跡':'Historic site','自然':'Nature spot','体験':'Hands-on experience','花・紅葉・植物':'Flower and autumn-foliage spot',
 '観光案内':'Tourist information spot','観光案内所':'Tourist information center','観光ガイド':'Local guide service','観光案内・インフォメーション':'Tourist information center',
 '食・郷土料理':'Local food spot','神社・仏閣':'Shrine or temple','特産・お土産':'Local specialty and souvenir spot','アウトドア・スポーツ':'Outdoor and sports spot',
 '墓所':'Historic grave site','歴史的建造物':'Historic building','ガイドツアー・ガイドウォーク':'Guided tour','登山・ハイキング':'Hiking spot','ミュージアム':'Museum',
 '町並み':'Historic streetscape','工芸品':'Local craft spot','歴史的建造物・町並み・庭園':'Historic building or garden','花・植物':'Flower spot','食体験':'Food experience',
 '近代的建造物':'Modern landmark','旧宅・屋敷跡':'Former residence site','景勝地・展望施設':'Scenic viewpoint','生家・生誕地':'Birthplace site',
 '伝統文化・歴史体験':'Traditional culture experience','直売所・市場・朝市':'Local produce market','洞窟・地質':'Cave or geological site','収穫体験':'Fruit and vegetable picking',
 'ほたる':'Firefly-viewing spot','美術館・博物館・資料館':'Museum','自然・花':'Nature and flower spot','レジャースポット':'Leisure spot','レジャー施設':'Leisure facility',
 '博物館・学習館':'Museum','日帰り温泉・足湯':'Day-trip hot spring or footbath','観光スポット':'Sightseeing spot','観光施設':'Sightseeing facility','景勝地・天然記念物':'Scenic spot or natural monument',
 '山・高原':'Mountain or highland','史跡・古墳・遺跡':'Historic site or ancient tomb','グルメ・お土産':'Food and souvenir spot','祭り・伝統行事':'Festival or traditional event',
 '川・滝・湖・渓谷':'River, waterfall or gorge','宿泊案内所':'Lodging information desk','買い物':'Shopping spot','ショッピング':'Shopping spot','旅行プラン・ツアー':'Tour',
 '展示場・ホール・研修施設':'Hall and exhibition facility','海岸・岬・島':'Coast, cape or island','マリンスポーツ・ウォータースポーツ':'Water-sports spot','自然遊歩道':'Nature trail',
 'レジャー・レクリエーション施設':'Leisure facility','岬・海岸':'Cape or coast','郷土館・民族資料館':'Local history museum','自然公園':'Nature park','お土産・特産品販売':'Souvenir shop',
 'ものづくり体験':'Craft workshop','トレッキング・ハイキング':'Hiking spot'}
def scrub(line):
    line = re.sub(r"on Tabelog's Top 100 (.+?) list \((\d{4})\)", r"a Top 100 \1 pick (\2)", line)
    line = re.sub(r"Tabelog Award (\d{4}) (Gold|Silver|Bronze) winner", r"\2 award winner (\1)", line)
    assert not re.search(r'tabelog|tripadvisor|jalan|ikkyu|食べログ|一休|じゃらん', line, re.I), line
    return line
def km_to_m(line):
    # "1.3 km" reads like a review score to the checker; the listing gives metres, so state metres.
    return re.sub(r'(\d+)\.(\d) km\b', lambda m: f"{int(m.group(1))*1000 + int(m.group(2))*100:,} m", line)
def h1_of(page_cache, pg):
    if pg not in page_cache:
        s = open(f'/workspace/p1/pr12-work/{pg}', encoding='utf-8').read()
        m = re.search(r'<h1 class="page-title">(.*?)</h1>', s, re.S)
        page_cache[pg] = re.sub('<.*?>', '', m.group(1)).strip() if m else pg.split('/')[1].title()
    return page_cache[pg]
def main():
    cards = json.load(open(f'{W}/cards.json'))
    facts = {}
    for l in open('/workspace/p1/line4/facts.jsonl'):
        r = json.loads(l); facts[r['card_key']] = r
    fetched = {}
    for l in open(f'{W}/fetch1.jsonl'):
        try: r = json.loads(l)
        except Exception: continue
        fetched[r['url']] = r
    def page(u):
        r = fetched.get(u)
        if not r or r['state'] != 'ok': return None
        return P.decode(gzip.open(r['file']).read(), r.get('enc'))
    out = {}; st = collections.Counter(); pc = {}; lines = collections.Counter()
    for c in cards:
        ck = c['card_key']; pref = c['page'].split('/')[0]; sec = c['section']
        muni = h1_of(pc, c['page']); place = f"{muni}, {pref.title()}"
        if ck in facts:
            f = facts[ck]; ln = f['line4_en']
            acc = ((f.get('fields') or {}).get('access_ja') or '').translate(G.Z2H)
            mm = re.search(r'駅から\s*([\d,]+)\s*m', acc)
            if ' km from ' in ln and mm:
                ln = re.sub(r'\d+\.\d km from', f"{int(mm.group(1).replace(',', '')):,} m from", ln, count=1)
            out[ck] = {'line': scrub(km_to_m(ln)), 'src': f['source_url'], 'kind': 'fact', 'name_ja': c['name_ja']}; st['fact', sec] += 1; continue
        src = c['sources']; line = None; srcu = None
        if sec == 'Dining':
            u = src.get('tabelog_url')
            if u and (s := page(u)):
                f = P.tabelog(s)
                genres = [g.strip() for g in re.split(r'[、,]', f.get('genre') or '') if g.strip()]
                g_en = next((G.GENRE.get(g) or EXTRA_GENRE.get(g) for g in genres if (G.GENRE.get(g) or EXTRA_GENRE.get(g))), None)
                f2 = dict(f); f2['genre'] = ''
                res, _ = G.dining_tabelog(f2, pref) if f.get('status') not in ('閉店', '移転', '休業') else (None, None)
                # reuse access/budget from the fact parser by giving it a neutral genre
                f3 = dict(f); f3['genre'] = '__X__'
                G.GENRE['__X__'] = g_en or 'Food spot'
                res, _ = G.dining_tabelog(f3, pref) if f.get('status') not in ('閉店', '移転', '休業') else (None, None)
                del G.GENRE['__X__']
                if res: line = res[1]; srcu = u
                if line and line.rstrip('.') in ('Food spot',) or (line and g_en is None and ',' not in line and ';' not in line):
                    line = f'Food spot in {place}.'
            if not line and (u := src.get('ta_url')) and (s := page(u)):
                f = P.tripadvisor(s)
                res, _ = G.dining_ta(f)
                if res: line = res[1]
                else:
                    pr = G.TA_PRICE.get((f.get('price_range') or '').strip())
                    line = f'{pr} restaurant in {place}.' if pr else f'Restaurant in {place}.'
                srcu = u
            if not line:
                line = (f'Restaurant in {place}.' if src.get('ta_url') and not src.get('tabelog_url') else f'Food spot in {place}.')
                srcu = src.get('tabelog_url') or src.get('ta_url') or c['href']
            kind = 'fallback'
        elif sec == 'Stay':
            line = f'Lodging in {place}.'; srcu = src.get('jalan_url') or c['href']; kind = 'fallback'
        else:
            u = c['href']; s = page(u) if u else None; typ = None
            if s:
                sf = S.sight(s, u)
                for cat in sf.get('categories') or []:
                    if CAT_EN.get(cat): typ = CAT_EN[cat]; break
            line = f'{typ} in {place}.' if typ else f'Local sight in {place}.'
            srcu = u; kind = 'fallback-cat' if typ else 'fallback'
        out[ck] = {'line': scrub(km_to_m(line)), 'src': srcu, 'kind': kind, 'name_ja': c['name_ja']}; st[kind, sec] += 1; lines[line] += 1
    json.dump(out, open('/workspace/p1/phase-d/line4_all.json', 'w'), ensure_ascii=False)
    for k, v in sorted(st.items()): print(k, v)
    print(lines.most_common(8))
main()
