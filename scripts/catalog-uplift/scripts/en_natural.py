"""Natural English display names for Japanese lodging/restaurant names (no invention: transliteration + loanword dictionary)."""
import re, unicodedata
import pykakasi
_K = pykakasi.kakasi()
_RAW = '''ホテル=Hotel スマイル=Smile ルートイン=Route Inn グランド=Grand ニュー=New プリンス=Prince シティ=City シティー=City パーク=Park リゾート=Resort イン=Inn ペンション=Pension ゲストハウス=Guesthouse ビジネス=Business プラザ=Plaza ロイヤル=Royal センター=Center パレス=Palace ヒルズ=Hills クラウン=Crown ステーション=Station ハウス=House ヴィラ=Villa ロッジ=Lodge コテージ=Cottage キャンプ=Camp ガーデン=Garden テラス=Terrace スパ=Spa ユースホステル=Youth Hostel ホステル=Hostel フォレスト=Forest エコー=Echo グリーン=Green ベル=Bell ベリーノ=Bellino ダイワロイネット=Daiwa Roynet コンフォート=Comfort ドーミーイン=Dormy Inn 東横イン=Toyoko Inn アパ=APA スーパー=Super サンルート=Sunroute メトロポリタン=Metropolitan キャピタル=Capital シンフォニー=Symphony パール=Pearl スロービレッジ=Slow Village フォルクローロ=Folkloro レイク=Lake ビュー=View オーシャン=Ocean サンライズ=Sunrise アネックス=Annex ハイツ=Heights ヴィレッジ=Village ビレッジ=Village マウンテン=Mountain ヒュッテ=Hutte クラブ=Club タワー=Tower ステイ=Stay ユニゾ=Unizo リッチモンド=Richmond ワシントン=Washington エクセル=Excel ファミリー=Family ログ=Log ペット=Pet ボックス=Box カプセル=Capsule ステイイン=Stay Inn サン=Sun ホワイト=White ブルー=Blue スカイ=Sky ベイ=Bay ポート=Port マリン=Marine シーサイド=Seaside ハイランド=Highland アルファ=Alpha ワン=One プレミア=Premier プレミアム=Premium セントラル=Central イースト=East ウエスト=West ノース=North サウス=South エース=Ace ユー=You スイート=Suite ルーム=Room トラベル=Travel ゲスト=Guest アパートメント=Apartment ターミナル=Terminal ワイナリー=Winery ファーム=Farm フラット=Flat サニー=Sunny モビリタ=Mobilita コート=Court シェーネスハイム=Schones Heim グリーンベル=Green Bell グラン=Gran ベッセル=Vessel エル=El パレ=Palais ラ=La フランス=France リバーサイド=Riverside リバー=River ヴィータ=Vita'''
LOAN = {}
_last = None
for _w in _RAW.split():
    if '=' in _w:
        _last, _v = _w.split('=', 1); LOAN[_last] = _v
    else:
        LOAN[_last] += ' ' + _w
LOAN_KEYS = sorted(LOAN, key=len, reverse=True)
FIX = {'月の': 'Tsuki no', '最上': 'Mogami', '上山': 'Kaminoyama', '雫石': 'Shizukuishi', '龍泉洞': 'Ryusendo', '浄土ヶ浜': 'Jodogahama', '肘折': 'Hijiori', '蔵王': 'Zao', '赤湯': 'Akayu', '鳥海': 'Chokai', '月山': 'Gassan', '寒河江': 'Sagae', '花巻': 'Hanamaki', '盛岡': 'Morioka', '一関': 'Ichinoseki', '宮古': 'Miyako', '釜石': 'Kamaishi', '天童': 'Tendo', '新庄': 'Shinjo', '酒田': 'Sakata', '鶴岡': 'Tsuruoka', '米沢': 'Yonezawa', '山形': 'Yamagata', '岩手': 'Iwate', '奥州': 'Oshu', '平泉': 'Hiraizumi', '北上': 'Kitakami', '金ケ崎': 'Kanegasaki', '久慈': 'Kuji', '二戸': 'Ninohe', '大船渡': 'Ofunato', '陸前高田': 'Rikuzentakata', '水沢': 'Mizusawa', '三陸': 'Sanriku', '駅前': 'Ekimae', '本館': 'Honkan', '別館': 'Bekkan', '国民宿舎': 'Kokumin Shukusha', '温泉': 'Onsen', '旅館': 'Ryokan', '民宿': 'Minshuku', '天然温泉': 'Natural Onsen'}
SUFFIX = {'月の': 'Tsuki no', '荘': 'so', '屋': 'ya', '館': 'kan', '亭': 'tei', '苑': 'en', '閣': 'kaku'}
def _hep(s):
    s = s.lower().replace('ou', 'o').replace('uu', 'u').replace('ee', 'e').replace('oo', 'o')
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
    s = re.sub(r'(.)[ゝヽ]', r'\1\1', s); s = re.sub(r'(.)々', r'\1\1', s)
    s = re.sub(r'[(（<＜【\[][^)）>＞】\]]*(グループ|ホテルズ|旧|開業|公式|楽天|じゃらん)[^)）>＞】\]]*[)）>＞】\]]', ' ', s)
    m = re.match(r'\s*【([^】]+)】', s)
    s = m.group(1) if m else re.sub(r'【[^】]*】', ' ', s)
    if muni_ja and muni_en: FIX.setdefault(re.sub(r'[市町村]$', '', muni_ja), muni_en)
    toks = []
    for run in re.findall(r'[ァ-ヴー]+|[A-Za-z0-9&\'.\-]+|[^\sァ-ヴーA-Za-z0-9&\'.\-]+', s):
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
