"""Fukushima/Niigata uplift helpers (own copy; does not touch shared clone)."""
import json, re, subprocess, time, os, io, html as H
from pathlib import Path
import sys
sys.path.insert(0, '/workspace/p1/fn-uplift/.venv/lib/python3.12/site-packages')
for p in Path('/workspace/p1/fn-uplift/.venv/lib').glob('python*/site-packages'): sys.path.insert(0, str(p))
import pykakasi
KK = pykakasi.kakasi()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
CACHE = Path('/workspace/p1/fn-uplift/cache')
CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uff00-\uffef\u3000-\u303f]')

def fetch(url, enc='utf-8', delay=1.2, ttl_days=7):
    key = re.sub(r'[^A-Za-z0-9]+', '_', url)[:180]
    f = CACHE / key
    if f.exists() and f.stat().st_size > 500:
        return f.read_bytes().decode(enc, 'replace')
    if 'tabelog.com' in url: delay = max(delay, 3.0)
    for att in range(6):
        time.sleep(delay)
        r = subprocess.run(['curl', '-sL', '-A', UA, '--max-time', '35', '-H', 'Accept-Language: ja,en;q=0.8', '-w', '\n%{http_code}', url], capture_output=True)
        body, _, code = r.stdout.rpartition(b'\n')
        if code.strip() in (b'429', b'503', b'000'):
            print('RATE', code.strip().decode(), url, flush=True); time.sleep(90 * (att + 1)); continue
        break
    if code.strip() != b'200':
        return ''
    CACHE.mkdir(parents=True, exist_ok=True); f.write_bytes(body)
    return body.decode(enc, 'replace')

LOAN = {'raamen':'Ramen','ramen':'Ramen','dainingu':'Dining','kafe':'Cafe','kafee':'Cafe','hoteru':'Hotel','resutoran':'Restaurant','baa':'Bar','izakaya':'Izakaya','shokudou':'Shokudo','sushi':'Sushi','yakiniku':'Yakiniku','sutaa':'Star','supageti':'Spaghetti','pizza':'Pizza','piza':'Pizza','beekarii':'Bakery','kicchin':'Kitchen','gurirru':'Grill','guriru':'Grill','biru':'Building','biiru':'Beer','wain':'Wine','ten':'','sobadokoro':'Sobadokoro','in':'Inn','onsen':'Onsen','ryokan':'Ryokan','pansho':'Pension','penshon':'Pension','rojji':'Lodge','koteeji':'Cottage','gesutohausu':'Guesthouse','burikku':'Brick','sutoa':'Store','taun':'Town','sentaa':'Center','paaku':'Park','puraza':'Plaza','sukii':'Ski','rizooto':'Resort','tei':'Tei','kanko':'Kanko'}
KATA = [('ホテルズ','Hotels'),('リゾーツ','Resorts'),('ルートイン','Route Inn'),('東横イン','Toyoko Inn'),('ドーミーイン','Dormy Inn'),('コンフォートホテル','Comfort Hotel'),('スーパーホテル','Super Hotel'),('アパホテル','APA Hotel'),('ワシントンホテル','Washington Hotel'),('ワシントン','Washington'),('オリックス','Orix'),('グランド','Grand'),('ホテル','Hotel'),('リゾート','Resort'),('ペンション','Pension'),('ゲストハウス','Guesthouse'),('ロッジ','Lodge'),('コテージ','Cottage'),('ヴィラ','Villa'),('ビジネス','Business'),('イン ',' Inn '),('シティ','City'),('パーク','Park'),('プラザ','Plaza'),('ガーデン','Garden'),('テラス','Terrace'),('ハウス','House'),('ステーション','Station'),('センター','Center'),('ラーメン','Ramen'),('らーめん','Ramen'),('カフェ','Cafe'),('ダイニング','Dining'),('キッチン','Kitchen'),('レストラン','Restaurant'),('ベーカリー','Bakery'),('ピッツェリア','Pizzeria'),('トラットリア','Trattoria'),('ビストロ','Bistro'),('バー ','Bar '),('食堂','Shokudo'),('珈琲','Coffee'),('コーヒー','Coffee'),('ステーキ','Steak'),('ハンバーグ','Hamburg'),('バーガー','Burger'),('ピザ','Pizza'),('パスタ','Pasta'),('スイーツ','Sweets'),('パン','Bakery'),('ワイン','Wine'),('ビール','Beer'),('ガスト','Gusto'),('マクドナルド','McDonald\'s'),('スターバックス','Starbucks'),('コーヒー','Coffee'),('ミスタードーナツ','Mister Donut'),('ケンタッキーフライドチキン','KFC'),('モスバーガー','MOS Burger'),('サイゼリヤ','Saizeriya'),('くら寿司','Kura Sushi'),('スシロー','Sushiro'),('はま寿司','Hama Sushi'),('かっぱ寿司','Kappa Sushi'),('温泉',' Onsen '),('旅館',' Ryokan ')]
def romanize(ja):
    ja = ja or ''
    for k, v in KATA: ja = ja.replace(k, f' {v} ')
    return _romanize(ja)
def _romanize(ja):
    ja = (ja or '').replace('・', ' ').replace('　', ' ')
    ja = re.sub(r'店$', '', ja.strip())
    ja = re.sub(r'店(\s|$)', r'\1', ja)
    ja = ja.translate(str.maketrans('ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ０１２３４５６７８９（）＆！？－～＠＃',
        'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789()&!?-~@#'))
    out = []
    for p in KK.convert(ja):
        orig, w = p['orig'], (p.get('hepburn') or '')
        if re.fullmatch(r'[\x00-\x7f]+', orig): out.append(orig); continue
        w = re.sub(r'([aeiou])\1', r'\1', w).replace('ou', 'o') if not re.search(r'[ァ-ヴー]', orig) else w
        lw = w.lower().strip()
        if lw in LOAN: w = LOAN[lw]
        elif re.search(r'[ァ-ヴー]', orig): w = re.sub(r'(aa|ii|uu|ee|oo)', lambda m: m.group(0)[0], w)
        out.append(w.title() if w else '')
    s = ' '.join(x for x in out if x)
    s = re.sub(r'\s+([,.)!?])', r'\1', s); s = re.sub(r'\(\s+', '(', s)
    s = re.sub(r'[^\x00-\x7f]', '', s)
    s = re.sub(r'\s+', ' ', s).strip(' -')
    return s

GENRE = [('旅館・民宿','Inn dining'),('料理旅館','Ryokan cuisine'),('道の駅','Roadside-station food court'),('売店','Food stand'),('コロッケ','Croquettes'),('ビュッフェ','Buffet'),('おにぎり','Rice balls'),('四川料理','Sichuan'),('惣菜・デリ','Deli'),('鳥料理','Chicken dishes'),('からあげ','Fried chicken'),('ジューススタンド','Juice stand'),('どら焼き','Dorayaki'),('パブ','Pub'),('オーベルジュ','Auberge'),('牛料理','Beef dishes'),('麺類','Noodles'),('オーガニック','Organic'),('揚げ物','Fried dishes'),('ヨーロッパ料理','European'),('台湾料理','Taiwanese'),('ホテル','Hotel restaurant'),('回転寿司','Conveyor-belt sushi'),('寿司','Sushi'),('ラーメン','Ramen'),('つけ麺','Tsukemen noodles'),('そば','Soba noodles'),('うどん','Udon noodles'),('焼肉','Yakiniku grill'),('ホルモン','Offal grill'),('焼き鳥','Yakitori'),('焼鳥','Yakitori'),('居酒屋','Izakaya'),('ダイニングバー','Dining bar'),('バー','Bar'),('カフェ','Cafe'),('喫茶店','Coffee shop'),('パン','Bakery'),('スイーツ','Sweets'),('ケーキ','Cake shop'),('和菓子','Japanese sweets'),('洋菓子','Pastry shop'),('イタリアン','Italian'),('パスタ','Pasta'),('ピザ','Pizza'),('フレンチ','French'),('ビストロ','Bistro'),('洋食','Western-style'),('ハンバーグ','Hamburg steak'),('ステーキ','Steak'),('中華料理','Chinese'),('中華','Chinese'),('餃子','Gyoza'),('韓国料理','Korean'),('インド料理','Indian'),('カレー','Curry'),('タイ料理','Thai'),('アジア','Asian'),('とんかつ','Tonkatsu'),('天ぷら','Tempura'),('うなぎ','Eel'),('海鮮','Seafood'),('魚介','Seafood'),('割烹','Kappo'),('日本料理','Japanese'),('懐石','Kaiseki'),('郷土料理','Local cuisine'),('定食','Set-meal diner'),('食堂','Diner'),('お好み焼き','Okonomiyaki'),('もんじゃ','Monja'),('たこ焼き','Takoyaki'),('鍋','Hotpot'),('しゃぶしゃぶ','Shabu-shabu'),('すき焼き','Sukiyaki'),('牛タン','Beef tongue'),('ジンギスカン','Lamb grill'),('丼','Rice bowls'),('弁当','Bento'),('ハンバーガー','Burgers'),('ファミレス','Family restaurant'),('レストラン','Restaurant'),('ビアガーデン','Beer garden'),('ワインバー','Wine bar'),('日本酒バー','Sake bar'),('スナック','Snack bar'),('アイス','Ice cream'),('ジェラート','Gelato'),('たい焼き','Taiyaki'),('鉄板焼き','Teppanyaki'),('串揚げ','Kushiage'),('串カツ','Kushikatsu'),('おでん','Oden'),('もつ鍋','Motsu hotpot'),('ちゃんぽん','Champon'),('冷麺','Cold noodles'),('ソフトクリーム','Soft-serve'),('ドーナツ','Donuts'),('クレープ','Crepes'),('甘味処','Japanese sweets cafe'),('創作料理','Creative cuisine'),('無国籍料理','Fusion'),('ろばた焼き','Robatayaki'),('魚料理','Fish dishes'),('鶏料理','Chicken dishes'),('肉料理','Meat dishes'),('野菜料理','Vegetable dishes'),('豆腐料理','Tofu dishes'),('焼きそば','Yakisoba'),('ベーカリー','Bakery'),('コーヒー','Coffee'),('紅茶','Tea'),('日本茶','Japanese tea'),('シーフード','Seafood'),('スペイン料理','Spanish'),('ベトナム料理','Vietnamese'),('メキシコ料理','Mexican'),('ダイニング','Dining')]
def genre_en(g):
    found = []
    for ja, en in GENRE:
        if ja in g and not any(en.lower() in f.lower() for f in found):
            found.append(en)
        if len(found) >= 2: break
    return ' and '.join(found) if found else ''

def place_from_addr(addr, muni_ja, muni_en):
    rest = addr.split(muni_ja, 1)[-1] if muni_ja in addr else ''
    m = re.match(r'(?:大字)?([^\d０-９\-－‐ー丁字番]+?)(?:町|丁目|字|大字|\d|０|１|２|３|４|５|６|７|８|９|-|$)', rest)
    dist = romanize(m.group(1)) if m and m.group(1) else ''
    dist = dist.replace(' ', '') .title() if dist else ''
    if dist and len(dist) > 2 and not CJK.search(dist) and dist.lower() != muni_en.lower():
        return f'{dist}, {muni_en}'
    return muni_en

def station_en(tok):
    """Romanise the Japanese text captured before 駅/IC. Marketing copy glued in front ("令和6年4月開業）JR御坊駅") is cut at the
    last bracket/space/punctuation, "JR" is kept as "JR " (never "Jrgobo"), and names still holding digits return ''."""
    import unicodedata
    t = unicodedata.normalize('NFKC', tok or '')
    t = re.split(r'[)\]」』】〉>!~〜:,、。\s]', t)[-1]
    jr = t.startswith('JR')
    if jr: t = t[2:]
    if not t or re.search(r'[0-9]', t): return ''
    st = romanize(t).replace(' ', '')
    if not st or CJK.search(st): return ''
    return ('JR ' if jr else '') + st.title()

def access_en(desc):
    m = re.search(r'([^\s、。◆/／・]{1,12}?)(?:駅|IC|ＩＣ)(?:から|より)?\s*(?:お)?(徒歩|車|バス|タクシー)?(?:で)?(?:約)?\s*([0-9０-９]+)\s*分', desc or '')
    if not m: return ''
    st = station_en(m.group(1))
    if not st: return ''
    mode = {'徒歩':'walk','車':'drive','バス':'bus ride','タクシー':'taxi ride',None:'drive'}[m.group(2)]
    n = m.group(3).translate(str.maketrans('０１２３４５６７８９','0123456789'))
    kind = 'IC' if 'IC' in m.group(0) or 'ＩＣ' in m.group(0) else 'Station'
    return f'{n}-minute {mode} from {st} {kind}'

def stay_kind(name):
    for k, v in (('旅館','Ryokan inn'),('民宿','Family-run minshuku'),('ペンション','Pension'),('ゲストハウス','Guesthouse'),('ロッジ','Mountain lodge'),('コテージ','Cottages'),('キャンプ','Campground lodging'),('グランピング','Glamping'),('荘','Inn'),('リゾート','Resort hotel'),('ホテル','Hotel'),('宿','Inn')):
        if k in name: return v
    return 'Lodging'

def to_webp(src_bytes, dest, maxw=560, q=25):
    from PIL import Image
    im = Image.open(io.BytesIO(src_bytes)); im = im.convert('RGB')
    if min(im.size) < 200: raise ValueError('too small')
    if im.width > maxw: im = im.resize((maxw, int(im.height * maxw / im.width)))
    dest.parent.mkdir(parents=True, exist_ok=True)
    im.save(dest, 'WEBP', quality=q, method=5)
    return im.size

def download_img(url, dest, maxw=560):
    if dest.exists() and dest.stat().st_size > 1500: return True
    time.sleep(0.4)
    r = subprocess.run(['curl', '-sL', '-A', UA, '--max-time', '25', url], capture_output=True)
    if len(r.stdout) < 2500: return False
    try:
        to_webp(r.stdout, dest, maxw); return dest.stat().st_size > 1500
    except Exception:
        return False

FEAT = [(r'源泉かけ流し|かけ流し', 'free-flowing hot spring baths'), (r'露天', 'open-air baths'), (r'貸切風呂|貸切露天', 'private baths'), (r'囲炉裏|いろり', 'an irori hearth dining room'), (r'部屋食|お部屋食', 'in-room dining'), (r'会席', 'kaiseki dinners'), (r'ビュッフェ|バイキング', 'buffet meals'), (r'朝食', 'breakfast available'), (r'Ｗｉ|Wi-?Fi|ＷＩ', 'Wi-Fi'), (r'駐車場', 'parking'), (r'渓流|川沿い|渓谷', 'riverside setting'), (r'絶景|眺望|展望', 'scenic views'), (r'1日1組|一日一組', 'one group per day'), (r'ペット', 'pet-friendly rooms'), (r'素泊', 'room-only plans'), (r'サウナ', 'a sauna'), (r'大浴場', 'a large communal bath'), (r'古民家', 'a renovated traditional house'), (r'地魚|海の幸|海鮮', 'local seafood dinners'), (r'郷土料理', 'local cuisine'), (r'お子様|子供|ファミリー|家族', 'family-friendly stays'), (r'ビジネス|お仕事|出張', 'business travelers'), (r'長期', 'long stays'), (r'合宿|団体', 'groups'), (r'リトリート', 'a retreat concept'), (r'高原|里山|緑に囲まれ', 'a quiet countryside setting'), (r'バス.?トイレ別', 'separate bath and toilet'), (r'スキー|ゲレンデ', 'ski access'), (r'湖', 'lakeside location')]
def stay_features(desc):
    out = []
    for rx, en in FEAT:
        if re.search(rx, desc or '') and en not in out: out.append(en)
        if len(out) >= 2: break
    return out
