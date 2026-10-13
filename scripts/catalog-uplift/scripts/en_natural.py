"""Natural English display names for Japanese lodging/restaurant names (no invention: transliteration + loanword dictionary)."""
import re, unicodedata
import pykakasi
_K = pykakasi.kakasi()
_RAW = '''ホテル=Hotel スマイル=Smile ルートイン=Route Inn グランド=Grand ニュー=New プリンス=Prince シティ=City シティー=City パーク=Park リゾート=Resort イン=Inn ペンション=Pension ゲストハウス=Guesthouse ビジネス=Business プラザ=Plaza ロイヤル=Royal センター=Center パレス=Palace ヒルズ=Hills クラウン=Crown ステーション=Station ハウス=House ヴィラ=Villa ロッジ=Lodge コテージ=Cottage キャンプ=Camp ガーデン=Garden テラス=Terrace スパ=Spa ユースホステル=Youth Hostel ホステル=Hostel フォレスト=Forest エコー=Echo グリーン=Green ベル=Bell ベリーノ=Bellino ダイワロイネット=Daiwa Roynet コンフォート=Comfort ドーミーイン=Dormy Inn 東横イン=Toyoko Inn アパ=APA スーパー=Super サンルート=Sunroute メトロポリタン=Metropolitan キャピタル=Capital シンフォニー=Symphony パール=Pearl スロービレッジ=Slow Village フォルクローロ=Folkloro レイク=Lake ビュー=View オーシャン=Ocean サンライズ=Sunrise アネックス=Annex ハイツ=Heights ヴィレッジ=Village ビレッジ=Village マウンテン=Mountain ヒュッテ=Hutte クラブ=Club タワー=Tower ステイ=Stay ユニゾ=Unizo リッチモンド=Richmond ワシントン=Washington エクセル=Excel ファミリー=Family ログ=Log ペット=Pet ボックス=Box カプセル=Capsule ステイイン=Stay Inn サン=Sun ホワイト=White ブルー=Blue スカイ=Sky ベイ=Bay ポート=Port マリン=Marine シーサイド=Seaside ハイランド=Highland アルファ=Alpha ワン=One プレミア=Premier プレミアム=Premium セントラル=Central イースト=East ウエスト=West ノース=North サウス=South エース=Ace ユー=You スイート=Suite ルーム=Room トラベル=Travel ゲスト=Guest アパートメント=Apartment ターミナル=Terminal ワイナリー=Winery ファーム=Farm フラット=Flat サニー=Sunny モビリタ=Mobilita コート=Court シェーネスハイム=Schones Heim グリーンベル=Green Bell グラン=Gran ベッセル=Vessel エル=El パレ=Palais ラ=La フランス=France リバーサイド=Riverside リバー=River ヴィータ=Vita'''
_RAW += ''' キムチ=Kimchi レストラン=Restaurant カフェ=Cafe ドライブイン=Drive-In ラーメン=Ramen インター=Interchange オレンジ=Orange コーナー=Corner クレープ=Crepe プチ=Petit イオン=AEON イオンモール=AEON Mall ローソン=Lawson セブンイレブン=7-Eleven ファミリーマート=FamilyMart ファミマ=FamilyMart セイコーマート=Seicomart マクドナルド=McDonald's ミスタードーナツ=Mister Donut ケンタッキーフライドチキン=KFC ケンタッキー=KFC マックスバリュ=MaxValu サービスエリア=Service Area パーキングエリア=Parking Area ビストロ=Bistro バー=Bar ダイニング=Dining ベーカリー=Bakery パン=Bread キッチン=Kitchen ファーム=Farm モール=Mall ショップ=Shop ピザ=Pizza パスタ=Pasta カレー=Curry ステーキ=Steak ハンバーグ=Hamburg Steak バーガー=Burger ハンバーガー=Hamburger スイーツ=Sweets ケーキ=Cake パティスリー=Patisserie ジェラート=Gelato ソフトクリーム=Soft Serve コーヒー=Coffee ティー=Tea ラウンジ=Lounge パブ=Pub ビアホール=Beer Hall ビアガーデン=Beer Garden ワイン=Wine ビール=Beer スナック=Snack グリル=Grill キッチンカー=Food Truck テイクアウト=Takeout ドライブ=Drive ガスト=Gusto ココス=COCO'S サイゼリヤ=Saizeriya スシロー=Sushiro はま寿司=Hama Sushi くら寿司=Kura Sushi 牛角=Gyukaku 吉野家=Yoshinoya すき家=Sukiya 松屋=Matsuya ジョイフル=Joyfull デニーズ=Denny's バーミヤン=Bamiyan スターバックス=Starbucks タリーズ=Tully's ドトール=Doutor コメダ=Komeda ロッテリア=Lotteria モスバーガー=MOS Burger サブウェイ=Subway ドミノ=Domino's ピザハット=Pizza Hut ツルハ=Tsuruha ドラッグ=Drug ストア=Store マート=Mart フード=Food フーズ=Foods ベーカリーカフェ=Bakery Cafe ブックカフェ=Book Cafe ハウス=House エリア=Area サウス=South ヒルズ=Hills'''
LOAN = {}
_last = None
for _w in _RAW.split():
    if '=' in _w:
        _last, _v = _w.split('=', 1); LOAN[_last] = _v
    else:
        LOAN[_last] += ' ' + _w
import json as _json, os as _os
try:
    _JM = _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'loan_jm.json')))  # JMdict (CC BY-SA, EDRDG) katakana loanwords, phonetically verified
except Exception: _JM = {}
for _k, _v in _JM.items():
    if _k not in LOAN and len(_k) >= 3: LOAN[_k] = ' '.join(w if w.isupper() else w.capitalize() for w in _v.split())
LOAN_KEYS = sorted([k for k in LOAN if re.fullmatch(r'[ァ-ヴー]+', k)], key=len, reverse=True)
ROMA2EN = {}
for _k in LOAN_KEYS:
    _h = ''.join(x['hepburn'] for x in _K.convert(_k)).lower()
    if len(_h) >= 5 and re.search(r'(aa|ii|uu|ee|oo)', _h): ROMA2EN.setdefault(_h, LOAN[_k])
KANJI_LOAN = {k: v for k, v in LOAN.items() if not re.fullmatch(r'[ァ-ヴー]+', k)}
FIX = {'月の': 'Tsuki no', '最上': 'Mogami', '上山': 'Kaminoyama', '雫石': 'Shizukuishi', '龍泉洞': 'Ryusendo', '浄土ヶ浜': 'Jodogahama', '肘折': 'Hijiori', '蔵王': 'Zao', '赤湯': 'Akayu', '鳥海': 'Chokai', '月山': 'Gassan', '寒河江': 'Sagae', '花巻': 'Hanamaki', '盛岡': 'Morioka', '一関': 'Ichinoseki', '宮古': 'Miyako', '釜石': 'Kamaishi', '天童': 'Tendo', '新庄': 'Shinjo', '酒田': 'Sakata', '鶴岡': 'Tsuruoka', '米沢': 'Yonezawa', '山形': 'Yamagata', '岩手': 'Iwate', '奥州': 'Oshu', '平泉': 'Hiraizumi', '北上': 'Kitakami', '金ケ崎': 'Kanegasaki', '久慈': 'Kuji', '二戸': 'Ninohe', '大船渡': 'Ofunato', '陸前高田': 'Rikuzentakata', '水沢': 'Mizusawa', '三陸': 'Sanriku', '駅前': 'Ekimae', '本館': 'Honkan', '別館': 'Bekkan', '国民宿舎': 'Kokumin Shukusha', '温泉': 'Onsen', '旅館': 'Ryokan', '民宿': 'Minshuku', '天然温泉': 'Natural Onsen', '食堂': 'Shokudo', '本店': 'main branch', '支店': 'branch', '商店': 'Shoten', '道の駅': 'Michi-no-Eki', '直売所': 'Farm Stand', '仏ヶ浦': 'Hotokegaura', '中央': 'Chuo', '寿司': 'Sushi', '焼肉': 'Yakiniku', '居酒屋': 'Izakaya', '蕎麦': 'Soba', 'そば処': 'Soba-dokoro', 'そば': 'Soba', 'うどん': 'Udon', '喫茶': 'Kissa', '珈琲': 'Coffee', '洋食': 'Yoshoku', '和食': 'Washoku', '水産': 'Suisan', '食べ処': 'Tabedokoro', 'お食事処': 'Oshokujidokoro', '食事処': 'Shokujidokoro', '仕出し': 'Shidashi', '販売所': 'Hanbaijo', '喫茶店': 'Kissaten', '珈琲店': 'Coffee Shop', 'の店': 'Shop', '店': 'Shop', 'れすとらん': 'Restaurant', 'ら～めん': 'Ramen', 'らーめん': 'Ramen', 'ら-めん': 'Ramen', 'かふぇ': 'Cafe', 'その他': 'Sonota', '拉麺': 'Ramen', 'らあめん': 'Ramen', 'らぁめん': 'Ramen', '麺屋': 'Menya', '売店': 'Shop', '代目': 'Daime', '二代目': 'Nidaime', '三代目': 'Sandaime', '四代目': 'Yondaime', '初代': 'Shodai'}
SUFFIX = {'月の': 'Tsuki no', '荘': 'so', '庵': 'an', '屋': 'ya', '館': 'kan', '亭': 'tei', '苑': 'en', '閣': 'kaku'}
FIX = {re.sub(r'([一-龥])[ケヶ]([一-龥])', '\\1\ue000\\2', k): v for k, v in FIX.items()}
def _hep(s):
    s = s.lower().replace("'", '').replace('ou', 'o').replace('uu', 'u').replace('ee', 'e').replace('oo', 'o')
    return s
def _seg(run):
    """full segmentation of a katakana run into loanwords, or None"""
    best = {0: []}
    for i in range(len(run)):
        if i not in best: continue
        for k in LOAN_KEYS:
            if run.startswith(k, i):
                j = i + len(k); cand = best[i] + [LOAN[k]]
                if j not in best or len(cand) <= len(best[j]): best[j] = cand
    return best.get(len(run))
def _kata(run):
    full = _seg(run)
    if full: return full
    for k in LOAN_KEYS:
        if len(k) >= 3 and run.startswith(k):
            return [LOAN[k]] + _kata(run[len(k):])
        if len(k) >= 3 and run.endswith(k) and len(run) > len(k):
            return _kata(run[:-len(k)]) + [LOAN[k]]
    return [_hep(''.join(x['hepburn'] for x in _K.convert(run))).replace('aa', 'a').replace('ii', 'i').title()]
try:
    import fugashi as _fg
    _TAG = _fg.Tagger()
except Exception: _TAG = None
def _read(seg):
    """one word per kanji compound / kana run: word-level readings (MeCab unidic) joined, not per-character tokens"""
    kana = ''
    if _TAG and re.search(r'[一-龥]', seg):
        try:
            ws = list(_TAG(seg))
            # trust MeCab only when it found real multi-character words; unknown proper nouns -> kakasi
            if all(len(w.surface) >= 2 or not re.match(r'[一-龥]', w.surface) for w in ws): kana = ''.join((w.feature.kana or w.surface) for w in ws)
        except Exception: kana = ''
    src = kana or seg
    if re.fullmatch(r'[ぁ-ゖー]+', src): src = src.replace('ー', '')
    return _hep(''.join(x['hepburn'] for x in _K.convert(src))).replace('-', '')
def _read_words(seg):
    """kanji compound: MeCab words, single-kanji affixes glued to a neighbour; short compounds stay one word"""
    if not (_TAG and len(seg) >= 4 and re.fullmatch(r'[一-龥々]+', seg)): return [_read(seg)]
    try: ws = [(w.surface, w.feature.kana or w.surface, w.feature.pos1) for w in _TAG(seg)]
    except Exception: return [_read(seg)]
    grp = []
    for sf, kn, pos in ws:
        if pos == '名詞' and len(ws) > 1 and re.fullmatch(r'[一二三四五六七八九十百千]', sf): pos = '接頭辞'
        if grp and grp[-1][2] == 'pre': grp[-1][1] += kn; grp[-1][0] += sf; grp[-1][2] = pos
        elif grp and (pos == '接尾辞' or (len(sf) == 1 and len(grp[-1][0]) >= 2)): grp[-1][1] += kn; grp[-1][0] += sf
        else: grp.append([sf, kn, 'pre' if pos == '接頭辞' else pos])
    return [_hep(''.join(x['hepburn'] for x in _K.convert(kn))) for sf, kn, _ in grp]
try: OVERRIDES = {k: v for k, v in _json.load(open(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'en_overrides.json'))).items() if not k.startswith('_')}
except Exception: OVERRIDES = {}
def natural_en(name, muni_ja=None, muni_en=None):
    if (name or '').strip() in OVERRIDES: return OVERRIDES[name.strip()]
    s = unicodedata.normalize('NFKC', name or '')
    s = re.sub(r'(.)[ゝヽ]', r'\1\1', s); s = re.sub(r'(.)々', r'\1\1', s)
    s = re.sub(r'[(（<＜【\[][^)）>＞】\]]*(グループ|ホテルズ|旧|開業|公式|楽天|じゃらん)[^)）>＞】\]]*[)）>＞】\]]', ' ', s)
    m = re.match(r'\s*【([^】]+)】', s)
    s = m.group(1) if m else re.sub(r'【[^】]*】', ' ', s)
    s = s.replace("'", "'")
    s = re.sub(r'[～〜~][^～〜~]{4,}[～〜~]', ' ', s)
    _segs = [x for x in re.split(r'[\s　]+', s.strip()) if x]
    _cut = max([k for k, x in enumerate(_segs[:-1]) if re.search(r'[を！!]|[一-龥]に[一-龥ぁ-ゖ]|[^\s]+の宿$', x)] or [-1])
    if _cut >= 0: s = ' '.join(_segs[_cut + 1:])
    s = re.sub(r'[(（](有|株)[)）]|有限会社|株式会社|合同会社', ' ', s)
    s = re.sub(r'([一-龥])[ケヶ]([一-龥])', '\\1\ue000\\2', s)
    s = re.sub(r'([一-龥])ノ([一-龥])', r'\1の\2', s).strip()
    s = re.sub(r'([一-龥])ツ([一-龥])', r'\1つ\2', s); s = re.sub(r'(?<![ぁ-ゖ])[ぁ-ゖ](?:[・･][ぁ-ゖ])+(?![ぁ-ゖ])', lambda m: re.sub('[・･]', '', m.group(0)), s)
    if not re.search(r'(本|支|商)店$', s): s = re.sub(r'([^\s　])店$', r'\1 BRANCHX' if re.search(r'[\s　]', s) else r'\1 SHOPX', s)
    for _k, _v in KANJI_LOAN.items(): FIX.setdefault(_k, _v)
    if muni_ja and muni_en: FIX.setdefault(re.sub(r'[市町村]$', '', muni_ja), muni_en)
    toks = []
    for run in re.findall(r'[ァ-ヴ][ァ-ヴー]*|[A-Za-z0-9&\'.\-]+|[^\sァ-ヴA-Za-z0-9&\'.\-]+', s):
        if re.match(r'[ァ-ヴー]', run): toks += _kata(run); continue
        if re.match(r'[A-Za-z]', run) and run.lower() in ROMA2EN: toks.append(ROMA2EN[run.lower()]); continue
        if re.match(r'[A-Za-z0-9]', run): toks.append(run if not run.isupper() or len(run) <= 4 else run.title()); continue
        i = 0
        while i < len(run):
            m = next((k for k in sorted(FIX, key=len, reverse=True) if run.startswith(k, i)), None)
            if m: toks.append(FIX[m]); i += len(m); continue
            ch = run[i]
            if run[i:] == 'と' and toks and re.match(r'[ァ-ヴー]', s[s.find(run)-1:s.find(run)] or 'x'): toks.append('&'); i += 1; continue
            if ch in SUFFIX and toks and not (i + 1 < len(run) and re.match(r'[一-龥]', run[i + 1])): toks[-1] += '-' + SUFFIX[ch]; i += 1; continue
            if re.match(r'[・、。,「」()（）〜~]', ch): i += 1; continue
            j = i + 1
            while j < len(run) and (run[j] not in SUFFIX or j - i == 1 or (j + 1 < len(run) and re.match(r'[一-龥]', run[j + 1]))) and not any(run.startswith(k, j) for k in FIX) and not re.match(r'[・、。,「」()（）〜~]', run[j]): j += 1
            _kk = ''.join(chr(ord(c) + 0x60) if 'ぁ' <= c <= 'ゖ' else c for c in run[i:j])
            if j - i >= 4 and re.fullmatch(r'[ァ-ヴー]+', _kk) and _seg(_kk) and all(len(w) >= 2 for w in _seg(_kk)):
                toks += _seg(_kk); i = j; continue
            if '\ue000' in run[i:j]:
                toks.append(_hep(''.join(x['hepburn'] for x in _K.convert(run[i:j].replace('\ue000', 'が')))).title()); i = j; continue
            _ch = run[i:j]
            _segs = ([_ch] if len(_ch) <= 4 and re.search(r'[一-龥]', _ch) and re.search(r'[ぁ-ゖ]', _ch) and not re.search(r'[のと]', _ch)
                     else re.findall(r'[一-龥々〆ヵヶ]+|(?<=[一-龥])の|(?<=[一-龥])と(?=[一-龥])|[ぁ-ゖー]+|.', _ch))
            for seg in _segs:
                if seg == 'の': toks.append('no'); continue
                if seg == 'と' and toks: toks.append('to'); continue
                for w in _read_words(seg):
                    if w.strip(): toks.append(w.title())
            i = j
    out = re.sub(r'\s+', ' ', ' '.join(toks)).strip(' -').replace('SHOPX', 'Shop').replace('Shopx', 'Shop').replace('BRANCHX', 'branch').replace('Branchx', 'branch')
    out = re.sub(r'\s+Mise$', ' branch', out); out = re.sub(r'\s+(Ten|Mise)\b(?=$)', ' branch', out)
    out = re.sub(r'\bMise\b', 'Shop', out)
    out = re.sub(r' (Chan|San|Kun)\b', lambda m: '-' + m.group(1).lower(), out); out = re.sub(r'\s-\s|\s-(?=\s|$)|^-\s', ' ', out)
    for _a, _b in (('Doraibuin', 'Drive-In'), ('Resutoran', 'Restaurant'), ('Kafe', 'Cafe'), ('Hoteru', 'Hotel'), ('Shokudou', 'Shokudo')): out = re.sub(r'\b%s\b' % _a, _b, out)
    out = re.sub(r'(?:\s+no)+$', '', out); out = re.sub(r'^no\s+', '', out)
    out = re.sub(r'\s*\(\s*', ' (', out); out = re.sub(r'\s*\)', ')', out); out = re.sub(r'[<>〈〉]', ' ', out)
    out = re.sub(r'\s+', ' ', out).strip()
    return out[:1].upper() + out[1:]
