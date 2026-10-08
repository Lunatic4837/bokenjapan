#!/usr/bin/env python3
"""Line 2 fixes that a rule can't make: names written as Japanese phrases or misread by the romaniser get a proper
English rendering (keyed by the exact Japanese card name), and spaced-out Latin letters ('P R I M E') are rejoined
using the Latin words in the Japanese name itself."""
import re, glob, html, unicodedata, collections
REPO = '/workspace/p1/pr12-work'
FIX = {
 '元気が出る居酒屋よだれ屋': 'Genki ga Deru Izakaya Yodareya',
 '玄界灘を望む”食”の宿　魚屋別館': 'Sakanaya Bekkan, a Food Inn Overlooking the Genkai Sea',
 '映えるライトアップ、本格シェフのいる グランピング五感': 'Glamping Gokan, with Light-ups and a Professional Chef',
 '海の見えるカウンター寿司 鮨屋台 岡垣総本店': 'Sea-View Counter Sushi Sushi Yatai, Okagaki Main Branch',
 '【おおむたハイツ】有明海や雲仙、夕日を眺める絶景の宿': 'Omuta Heights, an Inn with Sunset Views over the Ariake Sea and Unzen',
 '肉のさつま屋 今古賀店': 'Niku no Satsumaya Imakoga Branch',
 'カフェ レスト 家電住まいる館YAMADA福岡志免本店': 'Cafe Rest, Kaden Sumairu-kan YAMADA Fukuoka Shime Main Store',
 '泊まれる学び舎&ジビエBBQ 「ひみつ基地小塩」': 'Himitsu Kichi Koshio, Stay-In Schoolhouse & Gibier BBQ',
 '黒毛和牛と生牛タンが旨い店 焼肉炙家 八女店': 'Yakiniku Aburiya Yame Branch (Kuroge Wagyu and Fresh Beef Tongue)',
 '追波湾テラス～考える葦～': 'Oppa Bay Terrace "Thinking Reed"',
 '三陸の恵みを食す 石巻酒場 団欒 石巻駅前店': 'Ishinomaki Sakaba Danran, Ishinomaki Ekimae Branch (Sanriku Seafood)',
 '白松がモナカ本舗': 'Shiramatsu ga Monaka Honpo', '白松がモナカ本舗 松島店': 'Shiramatsu ga Monaka Honpo Matsushima Branch',
 '白松がモナカ本舗 仙台南店': 'Shiramatsu ga Monaka Honpo Sendai Minami Branch', '白松がモナカ本舗 古川店': 'Shiramatsu ga Monaka Honpo Furukawa Branch',
 '白松がモナカ本舗 本塩釜店': 'Shiramatsu ga Monaka Honpo Hon-Shiogama Branch', '白松がモナカ本舗 西塩釜店': 'Shiramatsu ga Monaka Honpo Nishi-Shiogama Branch',
 '居酒屋春が来た': 'Izakaya Haru ga Kita', '自家製麺 ラーメンが止マラナイ': 'Homemade Noodles Ramen ga Tomaranai',
 'る ぱん こなこな': 'Le Pain Konakona',
 '気仙沼湾一望　新鮮な海の幸を頂く宿【気仙沼プラザホテル】': 'Kesennuma Plaza Hotel, Fresh Seafood and Kesennuma Bay Views',
 '星逢える宿～森のコテージ気仙沼': 'Hoshi Aeru Yado, Forest Cottage Kesennuma',
 '日の出の見える宿　ニュー泊崎荘': 'New Tomarizaki-so, an Inn with Sunrise Views',
 '旬の海鮮膳が食べられる宿　女川温泉　華夕美': 'Onagawa Onsen Kayumi, an Inn Serving Seasonal Seafood',
 'しあんくれ～る': 'Chiaroscuro (Shiankure-ru)',
 '個室食事処と貸切風呂が愉しめる宿　かっぱの宿旅館三治郎': 'Kappa no Yado Ryokan Sanjiro (Private Dining Rooms and Private Baths)',
 '【小京都の湯　みくまホテル】全客室から三隈川を眺める絶景宿': 'Mikuma Hotel, Every Room Overlooking the Mikuma River',
 '宝泉寺温泉　ペットと泊まれる宿　季の郷　山の湯': 'Hosenji Onsen Ki no Sato Yama no Yu, Pet-Friendly Inn',
 '新鮮な魚と大分名物とり天が自慢の居酒屋 みどり屋 大分中央町店': 'Izakaya Midoriya Oita Chuo-machi Branch (Fresh Fish and Toriten)',
 '自然を五感で楽しむリゾートホテル　レゾネイトクラブくじゅう': 'Resonate Club Kuju Resort Hotel',
 'ホテルパブリック21　夕食＆朝食が無料サービス！': 'Hotel Public 21 (Free Dinner & Breakfast)',
 '鉄道と山の見える家': 'House with Railway and Mountain Views',
 '由布岳を身近に感じる -柚富の郷　彩岳館-': 'Yufu no Sato Saigakukan, Close to Mount Yufu',
 '豊後水道絶品海鮮が自慢の料理宿　木蓮': 'Mokuren, Inn Known for Bungo Channel Seafood',
 '海が奏でる癒しの宿　リゾートホテル美萩': 'Resort Hotel Bihagi, a Seaside Healing Inn',
 '萩の風を感じる宿～レンタルハウス　はぎ風鈴': 'Rental House Hagi Furin',
 '焼肉・ホルモン 冨まる  平生店': 'Yakiniku Horumon Tomimaru Hirao Branch', '焼肉・ホルモン冨まる 柳井店': 'Yakiniku Horumon Tomimaru Yanai Branch',
 '【錦帯橋温泉 岩国国際観光ホテル】～錦帯橋を望む絶景温泉～': 'Iwakuni Kokusai Kanko Hotel, Kintaikyo Onsen with Kintaikyo Bridge Views',
 '乃が美はなれ 下松販売店': 'Nogami Hanare Kudamatsu Store',
 'レッサーパンダが見えるレストラン': 'Red Panda View Restaurant',
 '下関で一年中新鮮なふぐ料理を堪能できる旅館　みもすそ川別館': 'Mimosusogawa Bekkan, Ryokan Serving Fresh Fugu Year-Round',
 '本格ふぐ料理が自慢　関門の宿　源平荘': 'Kanmon no Yado Genpeiso (Authentic Fugu Cuisine)',
 '割烹旅館寿美礼　～下関で本場のとらふぐ料理を愉しむ宿～': 'Kappo Ryokan Sumire (Shimonoseki Tiger Fugu Cuisine)',
 '関門海峡を一望できる絶景の宿　満珠荘': 'Manjuso, an Inn Overlooking the Kanmon Straits',
 'カフェ・菓子工房 ぼんじゅ～る': 'Cafe & Patisserie Bonjour',
 '味処和が家': 'Ajidokoro Wagaya', '豆が辻': 'Mamegatsuji', 'ます田や': 'Masudaya',
}
st = collections.Counter()
for p in glob.glob(f'{REPO}/*/*/index.html'):
    if p.split('/')[-3] not in ('miyagi','akita','fukuoka','yamaguchi','oita'): continue
    s = open(p, encoding='utf-8').read(); o = s
    def f(m):
        li = m.group(0)
        nm = re.search(r'<p class="place-name">(.*?)</p>', li, re.S); bl = re.search(r'<p class="place-blurb">(.*?)</p>', li, re.S)
        if not nm or not bl: return li
        ja = html.unescape(nm.group(1)); cur = html.unescape(bl.group(1)); new = FIX.get(ja.strip(), cur)
        if new == cur:
            for w in re.findall(r"[A-Za-z][A-Za-z0-9'&.]+", unicodedata.normalize('NFKC', ja)):
                if len(w) < 2: continue
                rx = re.compile(r'(?<![A-Za-z])' + r' '.join(map(re.escape, w)) + r'(?![A-Za-z])', re.I)
                new = rx.sub(lambda _: w, new)
            new = re.sub(r'\s+', ' ', new).strip()
        if new == cur: return li
        st['fixed'] += 1
        return li.replace(bl.group(0), f'<p class="place-blurb">{html.escape(new, quote=False)}</p>', 1)
    s = re.sub(r'<li\b[^>]*>.*?</li>', f, s, flags=re.S)
    if s != o: open(p, 'w', encoding='utf-8').write(s); st['pages'] += 1
print(dict(st))
