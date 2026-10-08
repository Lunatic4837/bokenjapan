import re, json, sys, difflib, unicodedata
sys.path.insert(0, '/workspace/p1/data/catalog-uplift/.venv/lib/python3.13/site-packages')
import pykakasi
K = pykakasi.kakasi()
KD = json.load(open('/workspace/p1/phase-d/names/kdict.json'))
OVR = {'グランド':'Grand','クラブ':'Club','ラーメン':'Ramen','カフェ':'Cafe','スーパー':'Super','カレー':'Curry','センター':'Center',
 'パン':'Pan','バレー':'Valley','イン':'Inn','レディース':'Ladies','ライトアップ':'Light-up','ステーキ':'Steak','ベーカリー':'Bakery',
 'キッチン':'Kitchen','ダイニング':'Dining','ハウス':'House','ゲストハウス':'Guesthouse','ホステル':'Hostel','ペンション':'Pension',
 'コテージ':'Cottage','ヴィラ':'Villa','ビラ':'Villa','テラス':'Terrace','ガーデン':'Garden','パーク':'Park','ロッジ':'Lodge','キャンプ':'Camp',
 'ホテル':'Hotel','リゾート':'Resort','スパ':'Spa','ステーション':'Station','シティ':'City','シティー':'City','セントラル':'Central','ロイヤル':'Royal',
 'プラザ':'Plaza','パレス':'Palace','ニュー':'New','サンライズ':'Sunrise','ビジネス':'Business','カプセル':'Capsule','アパートメント':'Apartment',
 'レストラン':'Restaurant','バー':'Bar','スナック':'Snack','ピザ':'Pizza','パスタ':'Pasta','うどん':'Udon','ベーグル':'Bagel','ケーキ':'Cake',
 'スイーツ':'Sweets','ショップ':'Shop','ストア':'Store','マート':'Mart','ファーム':'Farm','ベース':'Base','ハウスレストラン':'House Restaurant',
 'ドッグ':'Dog','ホット':'Hot','グリル':'Grill','ビストロ':'Bistro','トラットリア':'Trattoria','オステリア':'Osteria','バル':'Bar','ブルワリー':'Brewery',
 'コーヒー':'Coffee','珈琲':'Coffee','ティー':'Tea','ジェラート':'Gelato','ソフトクリーム':'Soft Serve','チキン':'Chicken','バーガー':'Burger',
 'ゴルフ':'Golf','サン':'Sun','ヒル':'Hill','ヒルズ':'Hills','ベイ':'Bay','ポート':'Port','シー':'Sea','ビーチ':'Beach','レイク':'Lake','マウンテン':'Mountain',
 'フォレスト':'Forest','グリーン':'Green','ブルー':'Blue','ホワイト':'White','レッド':'Red','ゴールド':'Gold','シルバー':'Silver','スター':'Star',
 'ルート':'Route','アーク':'Ark','エクセル':'Excel','キャッスル':'Castle','クイーン':'Queen','キング':'King','スマイル':'Smile','コンフォート':'Comfort',
 'ドーミー':'Dormy','リッチモンド':'Richmond','サンルート':'Sunroute','グランピング':'Glamping','ドミトリー':'Dormitory','ゲスト':'Guest',
 'ミッション':'Mission','ジャーマン':'German','モーテル':'Motel','ユース':'Youth','ホステル':'Hostel','食堂':None,'ガイア':'Gaia','シェフ':'Chef','カントリー':'Country','クラシック':'Classic','オーシャン':'Ocean','ビュー':'View','イタリアン':'Italian','フレンチ':'French','チャイニーズ':'Chinese','タイ':'Thai','インド':'India','ネパール':'Nepal','ベトナム':'Vietnam','コリアン':'Korean','とんかつ':'Tonkatsu','ちゃんぽん':'Champon','ホルモン':'Horumon','ドライブイン':'Drive-in','ワイン':'Wine','ビール':'Beer','ハンバーグ':'Hamburg Steak','オムライス':'Omurice','ベーカリーカフェ':'Bakery Cafe','ロック':'Rock','アルファ':'Alpha','ワン':'One','マクドナルド':"McDonald's",'ウエスト':'West','ガスト':'Gusto','ジョイフル':'Joyfull','サンリブ':'Sunlive','トレイル':'Trail',
 'メルシー':'Merci','セゾン':'Saison','スタンド':'Stand','スパイシー':'Spicy','プランタン':'Printemps','タンメン':'Tanmen','バーデン':'Baden','ソル':'Sol',
 'コート':'Court','パルコ':'Parco','ポール':'Paul','エスプリ':'Esprit','オープン':'Open','ランマン':'Ranman','ビル':'Building','ラパン':'Lapin','リストランテ':'Ristorante',
 'インドカレー':'Indian Curry','ログハウス':'Log House','ドーナツ':'Donut','ショッピングセンター':'Shopping Center','ジャポン':'Japon','コープ':'Co-op','ドミノピザ':"Domino's Pizza",
 'セブンイレブン':'7-Eleven','ドーミーイン':'Dormy Inn','タン':'Tongue','ミセス':'Mrs.','ドラ':None,'ガッツ':'Guts','ブロス':'Bros','メル':None,'カインド':'Kind',
 'ドンキー':'Donkey','インド':'India','セブン':'Seven','イレブン':'Eleven','ホルモン':'Horumon','タイム':'Time','ブランチ':'Brunch','ルイン':None,'トレイルイン':'Trail Inn','フローラルイン':'Floral Inn','タンタン':'Tantan','リバー':'River','ベント':None,'イオンモール':'Aeon Mall','イオン':'Aeon','ヨークベニマル':'York-Benimaru','インター':'Inter','ミニストップ':'Ministop','イオンタウン':'Aeon Town','モンペリエ':'Montpellier','シャトレーゼ':'Chateraise','サーティワンアイスクリーム':'31 Ice Cream','マックスバリュ':'MaxValu','モスバーガー':'MOS Burger','サービスエリア':'Service Area','トピコ':'Topico','マルシェ':'Marché','トリアス':'Trias','ピザハット':'Pizza Hut','ウジエスーパー':'Ujie Super','フレスコキクチ':'Fresco Kikuchi','ココス':"COCO'S",'リンガーハット':'Ringer Hut','アパホテル':'APA Hotel','ラウンジ':'Lounge','パーキングエリア':'Parking Area','タリーズコーヒー':"Tully's Coffee",'コーナー':'Corner','コージーコーナー':'Cozy Corner','イタリア':'Italia','フランス':'France','ハム':'Ham','トマト':'Tomato','ピッツェリア':'Pizzeria','ラグノオ':'Lagnoo','クック':'Cook','デイリーヤマザキ':'Daily Yamazaki','ジョリーパスタ':'Jolly Pasta','キムチ':'Kimchi','ナポリ':'Napoli','ニューデイズ':'NewDays','イオンスタイル':'Aeon Style','ナイス':'Nice','ハイツ':'Heights','ラボ':'Lab','アンジュ':'Ange','ピザクック':'Pizza Cook','ショッピングコーナー':'Shopping Corner','ストロベリーコーンズ':'Strawberry Cones','ピッツァ':'Pizza','イオンシネマ':'Aeon Cinema','ルミエール':'Lumière','ペッパーランチ':'Pepper Lunch','ダイレックス':'Direx','フードコート':'Food Court','ビッグエコー':'Big Echo','イオンスーパーセンター':'Aeon Super Center','メゾン':'Maison','ヒュッテ':'Hütte','プリンスホテル':'Prince Hotel','シフォン':'Chiffon','オーベルジュ':'Auberge','ジビエ':'Gibier','クレープ':'Crêpe','フード':'Food','グルメ':'Gourmet','カルディコーヒーファーム':'Kaldi Coffee Farm','カインズ':'Cainz','ビアードパパ':"Beard Papa's",'グラン':'Grand','ダイワロイネットホテル':'Daiwa Roynet Hotel','スパイス':'Spice','デリカ':'Delica','キリン':'Kirin','フェスタ':'Festa','ボン':'Bon','サンマルクカフェ':'St. Marc Café','コメリ':'Komeri','エンパイヤホテル':'Empire Hotel','プリン':'Pudding','プチ':'Petit','プティ':'Petit','インディゴ':'Indigo','アジアン':'Asian','パンダ':'Panda','アートホテル':'Art Hotel','センチュリーホテル':'Century Hotel','ドリア':'Doria','ブーランジェリー':'Boulangerie','ソレイユ':'Soleil','タベルナ':'Taverna','フォーシーズン':'Four Seasons','ショコラ':'Chocolat','コストコ':'Costco','オレンジ':'Orange','アイス':'Ice','ヤマザキショップ':'Yamazaki Shop','ハンバーガー':'Hamburger','ドミノ':"Domino's",'ポポロ':'Popolo','メルキュール':'Mercure','グランドメルキュール':'Grand Mercure','ディッパーダン':'Dipper Dan','ハッピー':'Happy','ホーム':'Home','ビッグボーイ':'Big Boy','ベネシアンホテル':'Venetian Hotel','サザンセト':'Southern Seto','ナチュラルグリーンパークホテル':'Natural Green Park Hotel','フジヤマコーヒーロースターズ':'Fujiyama Coffee Roasters','クインテッサホテル':'Quintessa Hotel','ベッカライ':'Bäckerei','ラトリエ':"L'Atelier",'アンシャンテ':'Enchanté','ジャンボ':'Jumbo','グランブッフェ':'Grand Buffet','ポットスチル':'Pot Still','ママ':'Mama','ジンギスカン':'Jingisukan','ロッヂ':'Lodge','パリ':'Paris','メルヘン':'Märchen','ウッド':'Wood','カシェット':'Cachette','アミュプラザ':'Amu Plaza','パピヨン':'Papillon','モロゾフ':'Morozoff','フロレスタ':'Floresta','ティファニー':'Tiffany','シーウェーブ':'Sea Wave','シーホース':'Seahorse','カトマンズ':'Kathmandu','コスタ':'Costa','ベッセル':'Vessel','シネマズ':'Cinemas','シネマ':'Cinema','ワシントンホテル':'Washington Hotel','ムッシュ':'Monsieur','スーパービバホーム':'Super Viva Home','アリストン':'Ariston','ロゼッタ':'Rosetta','カリー':'Curry','パフェ':'Parfait','ファーストフード':'Fast Food','マリオット':'Marriott','コナミ':'Konami','キャベツ':'Cabbage','バーベキュー':'Barbecue','エース':'Ace','ミュゼ':'Musée','マンマ':'Mamma','フェリーチェ':'Felice','シャルロット':'Charlotte','シュシュ':'Chouchou','ロマン':'Roman','モア':'More','ラーメンショップ':'Ramen Shop','デザート':'Dessert','フランソワ':'François','カラオケ':'Karaoke','ステーキハウス':'Steakhouse','ヴィレッジ':'Village','ビレッジ':'Village','スタジオ':'Studio','ギャラリー':'Gallery'}

OVR.update({'ファミリーマート':'FamilyMart','スターバックス':'Starbucks','スターバックスコーヒー':'Starbucks Coffee','ミスタードーナツ':'Mister Donut',
 'リンガーハット':'Ringer Hut','ドトール':'Doutor','ドトールコーヒーショップ':'Doutor Coffee Shop','タリーズ':"Tully's",'タリーズコーヒー':"Tully's Coffee",
 'サーティワンアイスクリーム':'31 Ice Cream','サーティワン':'31','ローソン':'Lawson','ミニストップ':'Ministop','マクドナルド':"McDonald's",
 'モスバーガー':'MOS Burger','ケンタッキーフライドチキン':'KFC','ケンタッキー':'KFC','ガスト':'Gusto','ジョイフル':'Joyfull','サイゼリヤ':'Saizeriya',
 'ロッテリア':'Lotteria','ホテルルートイン':'Hotel Route Inn','ルートイン':'Route Inn','グランティア':'Grantia','スーパーホテル':'Super Hotel',
 'アパホテル':'APA Hotel','ダイワロイネットホテル':'Daiwa Roynet Hotel','コンフォートホテル':'Comfort Hotel','アルバート':'Albert','アキタ':'Akita',
 'パールシティ':'Pearl City','グループ':'Group','セイコー':'Seiko','カウボーイ':'Cowboy','サービスエリア':'Service Area','ショッピング':'Shopping',
 'コーナー':'Corner','アイスクリーム':'Ice Cream','ブルーベリー':'Blueberry','リニューアル':'Renewal','インター':'Inter','ブックアンドカフェ':'Book and Cafe',
 'ラーメンショップ':'Ramen Shop','ファミリーレストラン':'Family Restaurant','東横イン':'Toyoko Inn','トーヨコイン':'Toyoko Inn','クインテッサ':'Quintessa',
 'ホテルリブマックス':'Hotel LiVEMAX','リブマックス':'LiVEMAX','メルキュール':'Mercure','バリュー・ザ・ホテル':'Value The Hotel','ワシントン':'Washington',
 'ユウベル':'Yubel','クレイン':'Crane','センチュリー':'Century','プリンス':'Prince','メトロポリタン':'Metropolitan','クラウン':'Crown','オーベルジュ':'Auberge',
 'ハイツ':'Heights','アネックス':'Annex','トラベル':'Travel','マイルーム':'My Room','ニューガイア':'New Gaia','ユーランド':'U-Land','ホテルニュー':'Hotel New'})
def kroma(k):
    return ''.join(p['hepburn'] for p in K.convert(k))
def skel(x):
    x = x.lower().replace('ph','f').replace('th','s').replace('ch','c').replace('sh','s').replace('ts','t')
    x = x.replace('l','r').replace('v','b').replace('q','k').replace('x','ks').replace('c','k')
    x = re.sub(r'[^a-z]', '', x)
    x = re.sub(r'[aeiouyhw]', '', x)
    return re.sub(r'(.)\1+', r'\1', x)
def ok_gloss(kana, g):
    a, b = skel(kroma(kana)), skel(g)
    return len(b) >= 2 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.8
def word(kana):
    if kana in OVR: return OVR[kana]
    if kana.endswith('ー') and kana[:-1] in OVR: return OVR[kana[:-1]]
    g = KD.get(kana)
    if g and not g.endswith('-') and ' ' not in g and ok_gloss(kana, g): return g.title() if g.islower() else g
    return None
def seg(run):
    n = len(run); best = [None]*(n+1); best[0] = []
    for i in range(n):
        if best[i] is None: continue
        for j in range(n, i+1, -1):
            piece = run[i:j]
            w = word(piece)
            if w and (j - i) < 3 and piece not in OVR and not (i == 0 and j == n): w = None
            if w and (best[j] is None or len(best[i])+1 < len(best[j])):
                best[j] = best[i] + [w]
    return best[n]

OVR.update({'タウン':'Town','ローズ':'Rose','セルリアン':'Cerulean','ルーラル':'Rural','ハーバー':'Harbor','スープ':'Soup','パッチワーク':'Patchwork',
 'ティールーム':'Tea Room','クレープ':'Crepe','パーティー':'Party','スペース':'Space','モンスター':'Monster','チャンポン':'Champon','スーパーセンター':'Supercenter',
 'イートイン':'Eat-in','カフェアンドキッチン':'Cafe and Kitchen','アンド':'and','ランチ':'Lunch','ファミリー':'Family','ブロート':'Brot','ベアーズ':'Bears','ベアー':'Bear','ステラ':None})
def seg2(run):
    # like seg(), but unknown stretches stay as romaji; used only when most of the run is known English
    n = len(run); INF = (10**9, 0)
    best = [None] * (n + 1); best[0] = (0, 0, [])
    for i in range(n):
        if best[i] is None: continue
        u, c, ws = best[i]
        for j in range(i + 1, n + 1):
            piece = run[i:j]; w = word(piece)
            if w and (j - i) < 3 and piece not in OVR: w = None
            if w: cand = (u, c + 1, ws + [w])
            elif j - i >= 3 and piece[0] not in 'ーッャュョァィゥェォン': cand = (u + (j - i), c + 1, ws + [None, piece])
            else: continue
            if best[j] is None or cand[:2] < best[j][:2]: best[j] = cand
    if best[n] is None: return None
    u, c, ws = best[n]
    if n < 5 or (n - u) < 3 or u * 10 > n * 7 or u == n: return None
    out = []; buf = ''
    for k in range(0, len(ws)):
        if ws[k] is None: continue
        if k > 0 and ws[k - 1] is None: buf += ws[k]; continue
        if buf: out.append(rom2(buf)); buf = ''
        out.append(ws[k])
    if buf: out.append(rom2(buf))
    return out
def rom2(k):
    r = re.sub(r'[^a-z]', '', kroma(k).lower())
    r = re.sub(r'([aiueo])\1', r'\1', r).replace('ou', 'o')
    return r.title()
KRUN = re.compile(r'[\u30a1-\u30faー]{2,}')
def old_rom(ja):
    s = ' '.join(p.get('hepburn') or '' for p in K.convert(ja))
    s = re.sub(r'\s+', ' ', s).strip()
    return s.title() if s else ja
def new_rom(ja):
    ja = unicodedata.normalize('NFKC', ja)
    out = []; changed = False
    for p in K.convert(ja):
        o = p['orig']
        if re.fullmatch(r'[\u30a1-\u30faー]+', o) and len(o) >= 2:
            ws = seg(o)
            if ws: out.append(' '.join(ws)); changed = True; continue
        h = p.get('hepburn') or ''
        if re.search(r'[\u3040-\u309f\u4e00-\u9fff]', o):
            h = h.replace('ou', 'o').replace('oo', 'o').replace('uu', 'u')
            if o == '店' and out: h = 'branch'
        out.append(h.title() if not re.search(r'[A-Z]', h) else h)
    s = re.sub(r'\s+', ' ', ' '.join(out)).strip().replace(' ,', ',').replace(' 、', ', ')
    s = re.sub(r'\b((?:[A-Z] ){1,}[A-Z])\b', lambda m: m.group(1).replace(' ', ''), s)  # "I N N" -> "INN"
    return s, changed
if __name__ == '__main__':
    for t in ['久留米ステーションホテル','ホテルレディースプラザ横手','ジャーマンベーカリー小竹店','ミッションバレーゴルフクラブ','東横ＩＮＮ大分中津駅前','ホテルニューガイア糸島','中津サンライズホテル','下関グランドホテル','映えるライトアップ、本格シェフのいる グランピング五感','みかん家','ラーメン一番']:
        print(t, '|', old_rom(t), '=>', new_rom(t))
