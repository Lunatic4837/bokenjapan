"""Natural English display names for Japanese lodging/restaurant names (no invention: transliteration + loanword dictionary)."""
import re, unicodedata
import pykakasi
_K = pykakasi.kakasi()
_RAW = '''ホテル=Hotel スマイル=Smile ルートイン=Route Inn グランド=Grand ニュー=New プリンス=Prince シティ=City シティー=City パーク=Park リゾート=Resort イン=Inn ペンション=Pension ゲストハウス=Guesthouse ビジネス=Business プラザ=Plaza ロイヤル=Royal センター=Center パレス=Palace ヒルズ=Hills クラウン=Crown ステーション=Station ハウス=House ヴィラ=Villa ロッジ=Lodge コテージ=Cottage キャンプ=Camp ガーデン=Garden テラス=Terrace スパ=Spa ユースホステル=Youth Hostel ホステル=Hostel フォレスト=Forest エコー=Echo グリーン=Green ベル=Bell ベリーノ=Bellino ダイワロイネット=Daiwa Roynet コンフォート=Comfort ドーミーイン=Dormy Inn 東横イン=Toyoko Inn アパ=APA スーパー=Super サンルート=Sunroute メトロポリタン=Metropolitan キャピタル=Capital シンフォニー=Symphony パール=Pearl スロービレッジ=Slow Village フォルクローロ=Folkloro レイク=Lake ビュー=View オーシャン=Ocean サンライズ=Sunrise アネックス=Annex ハイツ=Heights ヴィレッジ=Village ビレッジ=Village マウンテン=Mountain ヒュッテ=Hutte クラブ=Club タワー=Tower ステイ=Stay ユニゾ=Unizo リッチモンド=Richmond ワシントン=Washington エクセル=Excel ファミリー=Family ログ=Log ペット=Pet ボックス=Box カプセル=Capsule ステイイン=Stay Inn サン=Sun ホワイト=White ブルー=Blue スカイ=Sky ベイ=Bay ポート=Port マリン=Marine シーサイド=Seaside ハイランド=Highland アルファ=Alpha ワン=One プレミア=Premier プレミアム=Premium セントラル=Central イースト=East ウエスト=West ノース=North サウス=South エース=Ace ユー=You スイート=Suite ルーム=Room トラベル=Travel ゲスト=Guest アパートメント=Apartment ターミナル=Terminal ワイナリー=Winery ファーム=Farm フラット=Flat サニー=Sunny モビリタ=Mobilita コート=Court シェーネスハイム=Schones Heim グリーンベル=Green Bell グラン=Gran ベッセル=Vessel エル=El パレ=Palais ラ=La フランス=France リバーサイド=Riverside リバー=River ヴィータ=Vita レストラン=Restaurant カフェ=Cafe カフェー=Cafe ラーメン=Ramen らーめん=Ramen ベーカリー=Bakery パン=Bread キッチン=Kitchen ダイニング=Dining バー=Bar ビストロ=Bistro トラットリア=Trattoria ピッツェリア=Pizzeria ピザ=Pizza パスタ=Pasta イタリアン=Italian フレンチ=French カレー=Curry ステーキ=Steak ハンバーグ=Hamburg Steak バーガー=Burger ハンバーガー=Hamburger ドライブイン=Drive-in コーヒー=Coffee スイーツ=Sweets ケーキ=Cake パティスリー=Patisserie ショップ=Shop ストア=Store マーケット=Market ベーカリーカフェ=Bakery Cafe グリル=Grill ハウス=House テーブル=Table デリ=Deli ジェラート=Gelato ソフトクリーム=Soft Serve アイス=Ice Cream チャイニーズ=Chinese タイ=Thai インド=Indian ネパール=Nepal キッチンカー=Food Truck ワイン=Wine ビール=Beer ブルワリー=Brewery サンド=Sandwich ドーナツ=Donuts クレープ=Crepe ファクトリー=Factory ラウンジ=Lounge ホルモン=Horumon チキン=Chicken ベーグル=Bagel カントリー=Country スナック=Snack パブ=Pub ハウス=House ガスト=Gusto バーミヤン=Bamiyan ジョイフル=Joyful デニーズ=Denny's ココス=Coco's サイゼリヤ=Saizeriya マクドナルド=McDonald's ケンタッキーフライドチキン=Kentucky Fried Chicken スターバックスコーヒー=Starbucks Coffee ドトールコーヒーショップ=Doutor Coffee Shop ミスタードーナツ=Mister Donut モスバーガー=MOS Burger すき家=Sukiya 吉野家=Yoshinoya 松屋=Matsuya びっくりドンキー=Bikkuri Donkey サービスエリア=Service Area フルーツ=Fruit パーラー=Parlor ジャージー=Jersey ミート=Meat ゼリー=Jelly ペコリーノ=Pecorino ボナール=Bonnard リンカーン=Lincoln スポット=Spot グルメ=Gourmet チアーズ=Cheers テイクアウト=Takeout ショッピング=Shopping コーナー=Corner フード=Food コート=Court スウィーツ=Sweets ブーランジェリー=Boulangerie ジュース=Juice ターキー=Turkey ウィザード=Wizard スープカレー=Soup Curry スープ=Soup ファースト=First ナイト=Night ポテト=Potato ベース=Base ジョイ=Joy レガーロ=Regalo マルティーノ=Martino ツリー=Tree クッチーナ=Cucina ダーラナ=Dalarna ロースター=Roaster ロースターズ=Roasters ファーム=Farm プラント=Plant ミルク=Milk チーズ=Cheese ソフト=Soft ドッグ=Dog ホット=Hot トマト=Tomato ハーブ=Herb ガーデン=Garden パティスリー=Patisserie ショコラ=Chocolat トラットリア=Trattoria オステリア=Osteria ダイナー=Diner キッチン=Kitchen ベーカリー=Bakery ブレッド=Bread ハンバーグ=Hamburg Steak ステーション=Station ビストロ=Bistro バル=Bar シャノアール=Chat Noir'''
LOAN = {}
_last = None
for _w in _RAW.split():
    if '=' in _w:
        _last, _v = _w.split('=', 1); LOAN[_last] = _v
    else:
        LOAN[_last] += ' ' + _w
LOAN_KEYS = sorted(LOAN, key=len, reverse=True)
FIX = {'月の': 'Tsuki no', '最上': 'Mogami', '上山': 'Kaminoyama', '雫石': 'Shizukuishi', '龍泉洞': 'Ryusendo', '浄土ヶ浜': 'Jodogahama', '肘折': 'Hijiori', '蔵王': 'Zao', '赤湯': 'Akayu', '鳥海': 'Chokai', '月山': 'Gassan', '寒河江': 'Sagae', '花巻': 'Hanamaki', '盛岡': 'Morioka', '一関': 'Ichinoseki', '宮古': 'Miyako', '釜石': 'Kamaishi', '天童': 'Tendo', '新庄': 'Shinjo', '酒田': 'Sakata', '鶴岡': 'Tsuruoka', '米沢': 'Yonezawa', '山形': 'Yamagata', '岩手': 'Iwate', '奥州': 'Oshu', '平泉': 'Hiraizumi', '北上': 'Kitakami', '金ケ崎': 'Kanegasaki', '久慈': 'Kuji', '二戸': 'Ninohe', '大船渡': 'Ofunato', '陸前高田': 'Rikuzentakata', '水沢': 'Mizusawa', '三陸': 'Sanriku', '駅前': 'Ekimae', '本館': 'Honkan', '別館': 'Bekkan', '国民宿舎': 'Kokumin Shukusha', '温泉': 'Onsen', '旅館': 'Ryokan', '民宿': 'Minshuku', '天然温泉': 'Natural Onsen', 'お好み焼き': 'Okonomiyaki', 'お好み焼': 'Okonomiyaki', 'もんじゃ': 'Monja', 'お食事処': 'Restaurant', '食事処': 'Restaurant', 'お食事': 'Restaurant', '食堂': 'Shokudo', '居酒屋': 'Izakaya', '手打ちそば': 'Handmade Soba', '手打そば': 'Handmade Soba', '手打ち蕎麦': 'Handmade Soba', '手打ちうどん': 'Handmade Udon', 'そば処': 'Soba', '蕎麦処': 'Soba', 'そば': 'Soba', '蕎麦': 'Soba', 'うどん': 'Udon', 'ラーメン': 'Ramen', 'らーめん': 'Ramen', '中華そば': 'Chuka Soba', '中華料理': 'Chinese Restaurant', '中華': 'Chinese', '寿司': 'Sushi', 'すし': 'Sushi', '鮨': 'Sushi', '焼肉': 'Yakiniku', '焼き肉': 'Yakiniku', '焼鳥': 'Yakitori', '焼き鳥': 'Yakitori', 'やきとり': 'Yakitori', 'とんかつ': 'Tonkatsu', '喫茶': 'Cafe', '珈琲': 'Coffee', '茶房': 'Saryo', '甘味処': 'Kanmi', '餃子': 'Gyoza', 'ぎょうざ': 'Gyoza', '天ぷら': 'Tempura', 'うなぎ': 'Unagi', '鰻': 'Unagi', '割烹': 'Kappo', '料亭': 'Ryotei', '料理': 'Cuisine', '丼': 'Don', '定食': 'Teishoku', '弁当': 'Bento', '酒場': 'Sakaba', '酒店': 'Liquor Store', '酒造': 'Brewery', '精肉店': 'Butcher', '本店': 'Main Store', '支店': 'Branch', '店': '', '吉野家': 'Yoshinoya', '商店': 'Shoten', '菓子舗': 'Kashiho', '菓子店': 'Confectionery', 'お菓子': 'Okashi', '菓子': 'Kashi', 'らぁ麺': 'Ramen', 'らぁめん': 'Ramen', '老麺': 'Ramen', '老麪': 'Ramen', '下り線': 'Outbound', '専門店': '', 'すぷかり': 'Soup Curry', 'くっちぃな': 'Cucina', 'ビール園': 'Beer Garden', '地ビール': 'Craft Beer', 'すき家': 'Sukiya', '松屋': 'Matsuya', '会津若松': 'Aizuwakamatsu', '会津': 'Aizu', '丸峰': 'Marumine', '喜多方': 'Kitakata', '郡山': 'Koriyama', 'いわき': 'Iwaki', '福島': 'Fukushima', '白河': 'Shirakawa', '須賀川': 'Sukagawa', '相馬': 'Soma', '二本松': 'Nihonmatsu', '南相馬': 'Minamisoma', '猪苗代': 'Inawashiro', '磐梯': 'Bandai', '裏磐梯': 'Urabandai', '只見': 'Tadami', '大内宿': 'Ouchijuku', '湯野上': 'Yunokami', '芦ノ牧': 'Ashinomaki', '東山': 'Higashiyama', '飯坂': 'Iizaka', '土湯': 'Tsuchiyu', '高湯': 'Takayu', '岳温泉': 'Dake Onsen', '磐梯熱海': 'Bandai-Atami', '湯本': 'Yumoto', '母畑': 'Bobata', '檜枝岐': 'Hinoemata', '尾瀬': 'Oze', '三春': 'Miharu', '浪江': 'Namie', '坂下': 'Bange'}
SUFFIX = {'月の': 'Tsuki no', '荘': 'so', '屋': 'ya', '館': 'kan', '亭': 'tei', '家': 'ya', '苑': 'en', '閣': 'kaku'}
def _hep(s):
    s = s.lower().replace('aa', 'a').replace('ii', 'i').replace('ou', 'o').replace('uu', 'u').replace('ee', 'e').replace('oo', 'o')
    return s
def _seg(run):
    """full segmentation of a katakana run into loanwords, or None"""
    best = {0: []}
    for i in range(len(run)):
        if i not in best: continue
        for k in LOAN_KEYS:
            if run.startswith(k, i) and i + len(k) not in best: best[i + len(k)] = best[i] + [LOAN[k]]
    return best.get(len(run))
def _kata(run):
    full = _seg(run)
    if full: return full
    for k in LOAN_KEYS:
        if len(k) >= 3 and run.startswith(k):
            return [LOAN[k]] + _kata(run[len(k):])
        if len(k) >= 3 and run.endswith(k) and len(run) > len(k):
            return _kata(run[:-len(k)]) + [LOAN[k]]
    return [_hep(''.join(x['hepburn'] for x in _K.convert(run))).title()]
def natural_en(name, muni_ja=None, muni_en=None):
    s = unicodedata.normalize('NFKC', name or '')
    s = s.replace('らーめん', 'ラーメン').replace('ら～めん', 'ラーメン')
    s = re.sub(r'(?<=[ぁ-ん])[ー〜～]+', '', s)  # hiragana long-vowel marks: drop (Hepburn without macrons)
    s = re.sub(r'(.)[ゝヽ]', r'\1\1', s); s = re.sub(r'(.)々', r'\1\1', s)
    s = re.sub(r'[(（<＜【\[][^)）>＞】\]]*(グループ|ホテルズ|旧|開業|公式|楽天|じゃらん)[^)）>＞】\]]*[)）>＞】\]]', ' ', s)
    m = re.match(r'\s*【([^】]+)】', s)
    s = m.group(1) if m else re.sub(r'【[^】]*】', ' ', s)
    if muni_ja and muni_en: FIX.setdefault(re.sub(r'[市町村]$', '', muni_ja), muni_en)
    toks = []
    for run in re.findall(r'[ァ-ヴ][ァ-ヴー]*|[A-Za-z0-9&\'.\-]+|[^\sァ-ヴーA-Za-z0-9&\'.\-]+', s):
        if re.match(r'[ァ-ヴー]', run): toks += _kata(run); continue
        if re.match(r'[A-Za-z0-9]', run): toks.append(run if not run.isupper() or len(run) <= 4 else run.title()); continue
        i = 0
        while i < len(run):
            m = next((k for k in sorted(FIX, key=len, reverse=True) if run.startswith(k, i)), None)
            if m: toks.append(FIX[m]); i += len(m); continue
            ch = run[i]
            if ch in SUFFIX and toks: toks[-1] += '-' + SUFFIX[ch]; i += 1; continue
            if re.match(r'[・、。,「」()（）〜~]', ch): i += 1; continue
            j = i + 1
            while j < len(run) and run[j] not in SUFFIX and not any(run.startswith(k, j) for k in FIX) and not re.match(r'[・、。,「」()（）〜~]', run[j]): j += 1
            for x in _K.convert(run[i:j]):
                w = _hep(x['hepburn'])
                if not w.strip(): continue
                if w.endswith('no') and len(w) > 3 and x['orig'].endswith('の'): toks += [w[:-2].title(), 'no']
                elif w == 'no': toks.append('no')
                else: toks.append(w.title())
            i = j
    out = re.sub(r'\s+', ' ', ' '.join(toks)).strip(' -')
    return out
