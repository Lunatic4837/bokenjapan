CAT=[('seafood','Japanese (seafood)'),('meat','Japanese (meat)'),('noodles','Japanese (noodles)'),('european','European'),('cafe','Cafe'),('curry','Curry'),('casual','Casual'),('chinese','Chinese & Asian'),('izakaya','Izakaya & bars'),('sweets','Sweets & bakeries'),('japanese','Other Japanese'),('other','Other')]
TB={}
for k,gs in {
 'seafood':'寿司 回転寿司 海鮮 魚介料理・海鮮料理 魚介料理 海鮮丼 ふぐ かに うなぎ あなご 牡蠣 魚料理 シーフード',
 'meat':'焼肉 ホルモン 焼き鳥 串焼き とんかつ かつ丼 すき焼き しゃぶしゃぶ ステーキ 鶏料理 肉料理 ジンギスカン もつ鍋 からあげ 牛タン 鉄板焼き 馬肉料理 ハンバーグ',
 'noodles':'ラーメン つけ麺 そば うどん 麺類 油そば・まぜそば 沖縄そば 冷麺 ちゃんぽん 担々麺 中華そば 立ち食いそば 焼きそば',
 'european':'イタリアン パスタ ピザ フレンチ ヨーロッパ料理 洋食 オムライス ビストロ バル スペイン料理 西洋料理 アメリカ料理 ステーキ・ハンバーグ',
 'cafe':'カフェ 喫茶店 コーヒースタンド ジューススタンド コーヒー専門店 紅茶専門店',
 'curry':'カレー インドカレー スープカレー インド料理 ネパール料理',
 'casual':'食堂 ファミレス 定食・食堂 定食 ハンバーガー 丼 天丼 弁当 おにぎり 惣菜・デリ ビュッフェ 牛丼 親子丼 お好み焼き たこ焼き もんじゃ焼き 揚げ物 コロッケ 売店 ケバブ',
 'chinese':'中華料理 餃子 台湾料理 韓国料理 東南アジア料理 タイ料理 ベトナム料理 アジア・エスニック トルコ料理',
 'izakaya':'居酒屋 バー ダイニングバー 焼酎バー ビアバー パブ 日本酒バー ワインバー 立ち飲み スナック カラオケ',
 'sweets':'ケーキ 洋菓子 和菓子 パン ベーグル たい焼き・大判焼き かき氷 ジェラート・アイスクリーム ソフトクリーム クレープ・ガレット チョコレート スイーツ どら焼き 甘味処 サンドイッチ ドーナツ パフェ',
 'japanese':'日本料理 郷土料理 きりたんぽ 天ぷら おでん 釜飯 鍋 創作料理 沖縄料理 和食 懐石・会席料理 割烹・小料理 野菜料理 すっぽん 串揚げ 豆腐料理 そうめん 創作和食 精進料理',
}.items():
    for g in gs.split(): TB.setdefault(g,k)
DAILY_TB={'コンビニ・スーパー'}
TA_ORDER=[('Sushi','seafood'),('Seafood','seafood'),('Ramen','noodles'),('Barbecue','meat'),('Steakhouse','meat'),('Italian','european'),('French','european'),('Pizza','european'),('European','european'),('Spanish','european'),('American','european'),('German','european'),('Cafe','cafe'),('Indian','curry'),('Chinese','chinese'),('Korean','chinese'),('Asian','chinese'),('Thai','chinese'),('Izakaya (Japanese Style Tavern)','izakaya'),('Bar','izakaya'),('Pub','izakaya'),('Dessert','sweets'),('Bakery','sweets'),('Fast Food','casual'),('Diner','casual'),('Japanese','japanese'),('Japanese - Other ','japanese')]
DESC=[(r'sweets|bakery|cake|confection','sweets'),(r'ramen|soba|udon|noodle','noodles'),(r'sushi|seafood','seafood'),(r'izakaya|\bbar\b|pub','izakaya'),(r'caf[eé]|coffee','cafe'),(r'curry','curry'),(r'yakiniku|yakitori|tonkatsu|grill','meat'),(r'italian|french|pizz|western','european'),(r'chinese|korean|asian','chinese'),(r'diner|canteen|family restaurant|bento','casual'),(r'japanese','japanese')]
CSLUG={'seafood':'seafood','meat':'meat','noodles':'noodles','european':'european','cafe':'cafe','curry':'curry','casual':'casual','chinese':'chinese-asian','izakaya':'izakaya-bars','sweets':'sweets-bakeries','japanese':'other-japanese','other':'other'}
