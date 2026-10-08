#!/usr/bin/env python3
"""Phase B renderer for the five in-scope prefectures.

Municipalities over 500,000 people, from the 2025 Population Census
(人口等基本集計), are capped at the top 20 Dining cards and the top 20
Stay cards. In these five prefectures that is Sendai (1,096,146),
Fukuoka city (1,662,793) and Kitakyushu (2025 preliminary 904,289; 2020
confirmed 939,029). Oita city is 470,076 and is not capped. Each of
those cities is one page: designated-city wards are not separate pages,
so the cap is applied once per city page.

English names that are missing or still Japanese are replaced with
Hepburn romanization of the Japanese name (pykakasi). Names built from
TripAdvisor URL slugs keep the facility token from that slug, with the
location suffix removed. Existing Latin names that are already English
are left as they are.

Line 4 is a deterministic sentence built only from a cuisine, lodging
type, price band, or area token found in the facility name or in the
facility portion of its listing URL. Cards with none of those facts are
listed and left without an invented sentence.

Photos, photo caps, and other prefectures are not touched.
"""
from __future__ import annotations

import argparse
import html
import re
import sys
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import pykakasi

ROOT = Path(__file__).resolve().parents[1]
PREFS = ("miyagi", "akita", "fukuoka", "yamaguchi", "oita")
PREF_EN = {
    "miyagi": "Miyagi",
    "akita": "Akita",
    "fukuoka": "Fukuoka",
    "yamaguchi": "Yamaguchi",
    "oita": "Oita",
}
# One page per city. Populations are census counts, not estimates.
# Sendai 1,096,146 and Fukuoka 1,662,793 are 令和7年国勢調査 確定値.
# Kitakyushu 904,289 is the 令和7年 要計表速報 (city and Fukuoka prefecture);
# the 2020 confirmed count is 939,029. All three are over 500,000.
# Oita city 470,076 (令和7年 確定値) is under 500,000 and is not listed.
CAP_PAGES = {
    ("miyagi", "sendai"),
    ("fukuoka", "fukuoka"),
    ("fukuoka", "kitakyushu"),
}
CAP_LIMIT = 20
NOTE = (
    '<p class="city-cap-note">Boken Japan is focused on helping people find places '
    "that frequent visitors to Japan are yet to explore. For that reason, for large "
    "cities we have limited the number of facilities to the top 20 — other sites can "
    "cater to those needs, or alternatively ask a question in our chat box.</p>"
)
UNSOURCED_PATH = Path(__file__).with_name("phase-b-unsourced-explanations.txt")

CJK_RE = re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]")
SLUG_JUNK_RE = re.compile(
    r"\bPrefecture (Kyushu|Tohoku|Kanto|Chubu|Kinki|Kansai|Chugoku|Shikoku|"
    r"Hokuriku|Koshinetsu|Tokai|Okinawa|Hokkaido)\b|_Prefecture_|Reviews-"
)
FULLWIDTH_RE = re.compile(r"[\u30fb\uff01-\uff5e\u3000-\u303f]")
LISTING_RE = re.compile(
    r"tabelog|食べログ|tripadvisor|トリップアドバイザー|ikkyu|一休|jalan|じゃらん",
    re.I,
)
SECTION_RE = re.compile(
    r"(<section class=\"place-section\">\s*<h2>([^<]+)</h2>)(.*?)(</section>)",
    re.S,
)
LI_RE = re.compile(r"<li>.*?</li>", re.S)
P_RE = {
    "place-name": re.compile(r'<p class="place-name">(.*?)</p>', re.S),
    "place-blurb": re.compile(r'<p class="place-blurb">(.*?)</p>', re.S),
    "place-meta": re.compile(r'<p class="place-meta">(.*?)</p>', re.S),
    "place-desc": re.compile(r'<p class="place-desc">(.*?)</p>', re.S),
}
FACILITY_SLUG_RE = re.compile(
    r"Reviews-(.+?)-([A-Za-z0-9]+(?:_[A-Za-z0-9]+)*)_Prefecture_"
)
H1_RE = re.compile(r'<h1 class="page-title">([^<]*)</h1>')
PLACEHOLDER_HOSTS = {
    "source.com",
    "www.source.com",
    "source.net",
    "www.source.net",
    "example.com",
    "www.example.com",
}
PARTICLES = {"no", "to", "ga", "wa", "de", "ni", "e", "o", "ya", "wo", "mo", "na"}
FW_TRANS = str.maketrans(
    {
        "　": " ",
        "・": " ",
        "･": " ",
        "～": " ",
        "〜": " ",
        "。": " ",
        "、": " ",
        "！": " ",
        "？": " ",
        "（": " ",
        "）": " ",
        "「": " ",
        "」": " ",
        "『": " ",
        "』": " ",
        "：": " ",
        "；": " ",
    }
)

# (term, label, tier). Higher tier wins; equal tier prefers the longer term.
DINING_JP = [
    ("回転寿司", "conveyor-belt sushi restaurant", 3),
    ("回転ずし", "conveyor-belt sushi restaurant", 3),
    ("回転鮨", "conveyor-belt sushi restaurant", 3),
    ("海鮮丼", "seafood donburi restaurant", 3),
    ("牛丼", "gyudon restaurant", 3),
    ("親子丼", "oyakodon restaurant", 3),
    ("カツ丼", "katsudon restaurant", 3),
    ("かつ丼", "katsudon restaurant", 3),
    ("天丼", "tendon restaurant", 3),
    ("うな丼", "eel donburi restaurant", 3),
    ("担々麺", "tantanmen shop", 3),
    ("担担麺", "tantanmen shop", 3),
    ("タンメン", "tanmen shop", 3),
    ("ちゃんぽん", "champon shop", 3),
    ("油そば", "abura soba shop", 3),
    ("まぜそば", "mazesoba shop", 3),
    ("焼きそば", "yakisoba shop", 3),
    ("焼そば", "yakisoba shop", 3),
    ("沖縄そば", "Okinawa soba shop", 3),
    ("沖縄蕎麦", "Okinawa soba shop", 3),
    ("らーめん", "ramen shop", 3),
    ("ラーメン", "ramen shop", 3),
    ("らー麺", "ramen shop", 3),
    ("拉麺", "ramen shop", 3),
    ("つけ麺", "tsukemen shop", 3),
    ("つけめん", "tsukemen shop", 3),
    ("うどん", "udon shop", 3),
    ("蕎麦", "soba shop", 3),
    ("そば", "soba shop", 3),
    ("そうめん", "somen shop", 3),
    ("素麺", "somen shop", 3),
    ("きしめん", "kishimen shop", 3),
    ("ほうとう", "hoto shop", 3),
    ("寿司", "sushi restaurant", 3),
    ("鮨", "sushi restaurant", 3),
    ("すし", "sushi restaurant", 3),
    ("ずし", "sushi restaurant", 3),
    ("スシ", "sushi restaurant", 3),
    ("焼肉", "yakiniku restaurant", 3),
    ("焼き肉", "yakiniku restaurant", 3),
    ("牛タン", "beef-tongue restaurant", 3),
    ("ホルモン", "offal grill", 3),
    ("もつ鍋", "motsunabe restaurant", 3),
    ("もつ", "offal restaurant", 3),
    ("モツ", "offal restaurant", 3),
    ("焼鳥", "yakitori restaurant", 3),
    ("焼き鳥", "yakitori restaurant", 3),
    ("やきとり", "yakitori restaurant", 3),
    ("串焼き", "kushiyaki restaurant", 3),
    ("串かつ", "kushikatsu restaurant", 3),
    ("串カツ", "kushikatsu restaurant", 3),
    ("串揚げ", "kushiage restaurant", 3),
    ("とんかつ", "tonkatsu restaurant", 3),
    ("トンカツ", "tonkatsu restaurant", 3),
    ("カツレツ", "cutlet restaurant", 3),
    ("天ぷら", "tempura restaurant", 3),
    ("天麩羅", "tempura restaurant", 3),
    ("てんぷら", "tempura restaurant", 3),
    ("餃子", "gyoza restaurant", 3),
    ("ぎょうざ", "gyoza restaurant", 3),
    ("ギョーザ", "gyoza restaurant", 3),
    ("カレーパン", "curry-bread bakery", 3),
    ("カレー", "curry restaurant", 3),
    ("ピザ", "pizza restaurant", 3),
    ("ピッツァ", "pizza restaurant", 3),
    ("パスタ", "pasta restaurant", 3),
    ("ハンバーグ", "hambagu restaurant", 3),
    ("ステーキ", "steak restaurant", 3),
    ("オムライス", "omurice restaurant", 3),
    ("ドリア", "doria restaurant", 3),
    ("グラタン", "gratin restaurant", 3),
    ("しゃぶしゃぶ", "shabu-shabu restaurant", 3),
    ("すき焼き", "sukiyaki restaurant", 3),
    ("すきやき", "sukiyaki restaurant", 3),
    ("うなぎ", "eel restaurant", 3),
    ("鰻", "eel restaurant", 3),
    ("刺身", "sashimi restaurant", 3),
    ("海鮮", "seafood restaurant", 3),
    ("鮮魚", "seafood restaurant", 3),
    ("魚介", "seafood restaurant", 3),
    ("魚や", "fish shop", 3),
    ("魚屋", "fish shop", 3),
    ("お好み焼き", "okonomiyaki restaurant", 3),
    ("もんじゃ", "monjayaki restaurant", 3),
    ("鉄板焼", "teppanyaki restaurant", 3),
    ("たこ焼き", "takoyaki shop", 3),
    ("たこ焼", "takoyaki shop", 3),
    ("たい焼き", "taiyaki shop", 3),
    ("たいやき", "taiyaki shop", 3),
    ("から揚げ", "karaage shop", 3),
    ("唐揚げ", "karaage shop", 3),
    ("ハンバーガー", "hamburger shop", 3),
    ("ホットドッグ", "hot-dog shop", 3),
    ("サンドイッチ", "sandwich shop", 3),
    ("ケーキ", "cake shop", 3),
    ("スイーツ", "sweets shop", 3),
    ("和菓子", "Japanese sweets shop", 3),
    ("洋菓子", "Western sweets shop", 3),
    ("ジェラート", "gelato shop", 3),
    ("ソフトクリーム", "soft-serve shop", 3),
    ("クレープ", "crepe shop", 3),
    ("ドーナツ", "doughnut shop", 3),
    ("アイス", "ice cream shop", 3),
    ("弁当", "bento shop", 3),
    ("おにぎり", "onigiri shop", 3),
    ("惣菜", "delicatessen", 3),
    ("和食", "Japanese restaurant", 3),
    ("洋食", "Western-style restaurant", 3),
    ("中国料理", "Chinese restaurant", 3),
    ("韓国料理", "Korean restaurant", 3),
    ("中華", "Chinese restaurant", 3),
    ("韓国", "Korean restaurant", 3),
    ("イタリア料理", "Italian restaurant", 3),
    ("イタリアン", "Italian restaurant", 3),
    ("フランス料理", "French restaurant", 3),
    ("フレンチ", "French restaurant", 3),
    ("インド料理", "Indian restaurant", 3),
    ("インド", "Indian restaurant", 3),
    ("台湾料理", "Taiwanese restaurant", 3),
    ("中華そば", "ramen shop", 3),
    ("支那そば", "ramen shop", 3),
    ("タイ料理", "Thai restaurant", 3),
    ("ベトナム料理", "Vietnamese restaurant", 3),
    ("創作料理", "creative restaurant", 3),
    ("郷土料理", "regional restaurant", 3),
    ("ビストロ", "bistro", 3),
    ("ダイニングバー", "dining bar", 2),
    ("ワインバー", "wine bar", 2),
    ("居酒屋", "izakaya", 2),
    ("いざかや", "izakaya", 2),
    ("食堂", "diner", 2),
    ("食事処", "diner", 2),
    ("お食事", "diner", 2),
    ("定食", "set-meal restaurant", 2),
    ("割烹", "kappo restaurant", 2),
    ("料亭", "ryotei", 2),
    ("カフェ", "cafe", 2),
    ("珈琲", "coffee shop", 2),
    ("コーヒー", "coffee shop", 2),
    ("喫茶", "kissaten", 2),
    ("茶房", "teahouse", 2),
    ("茶屋", "teahouse", 2),
    ("甘味", "sweets shop", 2),
    ("ベーカリー", "bakery", 2),
    ("ブーランジェリー", "bakery", 2),
    ("パンケーキ", "pancake shop", 3),
    ("パン屋", "bakery", 2),
    ("パン", "bakery", 2),
    ("道の駅", "roadside station", 3),
    ("酒場", "bar", 2),
    ("立ち飲み", "standing bar", 2),
    ("スナック", "snack bar", 2),
    ("ラウンジ", "lounge", 2),
    ("バー", "bar", 2),
    ("キッチン", "kitchen restaurant", 2),
    ("ダイニング", "dining restaurant", 2),
    ("鉄板", "teppanyaki restaurant", 2),
    ("丼", "donburi restaurant", 2),
    ("鍋", "hot-pot restaurant", 2),
    ("串", "skewers restaurant", 2),
    ("レストラン", "restaurant", 1),
    ("料理", "restaurant", 1),
    ("専門店", "specialty restaurant", 1),
    ("食事", "restaurant", 1),
    ("麺", "noodle shop", 1),
    ("めん", "noodle shop", 1),
    ("亭", "restaurant", 1),
    ("庵", "restaurant", 1),
]
STAY_JP = [
    ("ビジネスホテル", "business hotel", 3),
    ("温泉旅館", "onsen ryokan", 3),
    ("温泉ホテル", "onsen hotel", 3),
    ("ゲストハウス", "guesthouse", 3),
    ("ユースホステル", "youth hostel", 3),
    ("シティホテル", "city hotel", 3),
    ("ホテル", "hotel", 2),
    ("ホステル", "hostel", 2),
    ("旅館", "ryokan", 2),
    ("温泉", "onsen inn", 2),
    ("民宿", "minshuku", 2),
    ("ペンション", "pension", 2),
    ("コテージ", "cottage", 2),
    ("リゾート", "resort", 2),
    ("民泊", "minpaku", 2),
    ("ヴィラ", "villa", 2),
    ("ロッジ", "lodge", 2),
    ("キャンプ場", "campsite", 2),
    ("キャンプ", "campsite", 2),
    ("荘", "ryokan", 1),
    ("閣", "ryokan", 1),
]
DINING_EN = [
    ("conveyor-belt sushi", "conveyor-belt sushi restaurant", 3),
    ("kaiten sushi", "conveyor-belt sushi restaurant", 3),
    ("ice cream", "ice cream shop", 3),
    ("ice-cream", "ice cream shop", 3),
    ("hot dog", "hot-dog shop", 3),
    ("ramen", "ramen shop", 3),
    ("tsukemen", "tsukemen shop", 3),
    ("udon", "udon shop", 3),
    ("soba", "soba shop", 3),
    ("sushi", "sushi restaurant", 3),
    ("yakiniku", "yakiniku restaurant", 3),
    ("yakitori", "yakitori restaurant", 3),
    ("tonkatsu", "tonkatsu restaurant", 3),
    ("tempura", "tempura restaurant", 3),
    ("gyoza", "gyoza restaurant", 3),
    ("curry", "curry restaurant", 3),
    ("pizza", "pizza restaurant", 3),
    ("pasta", "pasta restaurant", 3),
    ("steak", "steak restaurant", 3),
    ("hamburger", "hamburger shop", 3),
    ("burger", "hamburger shop", 3),
    ("okonomiyaki", "okonomiyaki restaurant", 3),
    ("takoyaki", "takoyaki shop", 3),
    ("unagi", "eel restaurant", 3),
    ("eel", "eel restaurant", 3),
    ("sukiyaki", "sukiyaki restaurant", 3),
    ("shabu", "shabu-shabu restaurant", 3),
    ("seafood", "seafood restaurant", 3),
    ("noodle", "noodle shop", 3),
    ("washoku", "Japanese restaurant", 3),
    ("kappo", "kappo restaurant", 3),
    ("teahouse", "teahouse", 3),
    ("sweets", "sweets shop", 3),
    ("cake", "cake shop", 3),
    ("gelato", "gelato shop", 3),
    ("bento", "bento shop", 3),
    ("onigiri", "onigiri shop", 3),
    ("dumpling", "dumpling restaurant", 3),
    ("pakistani", "Pakistani restaurant", 3),
    ("pakistan", "Pakistani restaurant", 3),
    ("nepalese", "Nepalese restaurant", 3),
    ("nepali", "Nepalese restaurant", 3),
    ("vietnamese", "Vietnamese restaurant", 3),
    ("vietnam", "Vietnamese restaurant", 3),
    ("indian", "Indian restaurant", 3),
    ("italian", "Italian restaurant", 3),
    ("french", "French restaurant", 3),
    ("chinese", "Chinese restaurant", 3),
    ("korean", "Korean restaurant", 3),
    ("thai", "Thai restaurant", 3),
    ("mexican", "Mexican restaurant", 3),
    ("spanish", "Spanish restaurant", 3),
    ("izakaya", "izakaya", 2),
    ("cafe", "cafe", 2),
    ("coffee", "coffee shop", 2),
    ("bakery", "bakery", 2),
    ("bistro", "bistro", 2),
    ("grill", "grill restaurant", 2),
    ("pub", "pub", 2),
    ("bar", "bar", 2),
    ("restaurant", "restaurant", 1),
    ("diner", "diner", 1),
    ("kitchen", "kitchen restaurant", 1),
    ("dining", "restaurant", 1),
    ("lunch", "lunch restaurant", 1),
    ("cuisine", "restaurant", 1),
]
STAY_EN = [
    ("business hotel", "business hotel", 3),
    ("guest house", "guesthouse", 3),
    ("guesthouse", "guesthouse", 3),
    ("youth hostel", "youth hostel", 3),
    ("hot spring", "onsen inn", 3),
    ("minshuku", "minshuku", 2),
    ("ryokan", "ryokan", 2),
    ("onsen", "onsen inn", 2),
    ("hostel", "hostel", 2),
    ("pension", "pension", 2),
    ("resort", "resort", 2),
    ("villa", "villa", 2),
    ("lodge", "lodge", 2),
    ("cottage", "cottage", 2),
    ("campsite", "campsite", 2),
    ("campground", "campsite", 2),
    ("hotel", "hotel", 2),
    ("inn", "inn", 2),
]
SIGHT_EN = [
    ("observation deck", "observation deck", 3),
    ("observatory", "observatory", 3),
    ("castle ruins", "castle ruin", 3),
    ("hot spring", "hot spring", 3),
    ("hot-spring", "hot spring", 3),
    ("art museum", "art museum", 3),
    ("campground", "campground", 3),
    ("campsite", "campsite", 3),
    ("waterfall", "waterfall", 3),
    ("promenade", "promenade", 2),
    ("boardwalk", "boardwalk", 2),
    ("aquarium", "aquarium", 2),
    ("memorial", "memorial", 2),
    ("monument", "monument", 2),
    ("botanical", "botanical garden", 2),
    ("arboretum", "arboretum", 2),
    ("vineyard", "vineyard", 2),
    ("brewery", "brewery", 2),
    ("winery", "winery", 2),
    ("lookout", "lookout", 2),
    ("castle", "castle", 2),
    ("shrine", "shrine", 2),
    ("temple", "temple", 2),
    ("museum", "museum", 2),
    ("garden", "garden", 2),
    ("falls", "waterfall", 2),
    ("gorge", "gorge", 2),
    ("river", "river", 2),
    ("bridge", "bridge", 2),
    ("beach", "beach", 2),
    ("coast", "coast", 2),
    ("island", "island", 2),
    ("lake", "lake", 2),
    ("pond", "pond", 2),
    ("mountain", "mountain", 2),
    ("forest", "forest", 2),
    ("farm", "farm", 2),
    ("market", "market", 2),
    ("harbor", "harbor", 2),
    ("harbour", "harbour", 2),
    ("port", "port", 2),
    ("gallery", "gallery", 2),
    ("stadium", "stadium", 2),
    ("pagoda", "pagoda", 2),
    ("church", "church", 2),
    ("trail", "trail", 2),
    ("ruins", "ruin", 2),
    ("onsen", "hot spring", 2),
    ("park", "park", 2),
    ("hall", "hall", 2),
    ("tower", "tower", 2),
    ("cave", "cave", 2),
    ("gate", "gate", 2),
    ("dam", "dam", 2),
    ("zoo", "zoo", 2),
    ("golf", "golf course", 2),
    ("ski", "ski area", 2),
    ("pool", "pool", 2),
    ("spa", "spa", 2),
    ("cape", "cape", 2),
    ("cliff", "cliff", 2),
    ("marsh", "marsh", 2),
    ("wetland", "wetland", 2),
    ("plateau", "plateau", 2),
    ("peninsula", "peninsula", 2),
    ("kofun", "burial mound", 2),
    ("cemetery", "cemetery", 2),
    ("village", "village", 1),
    ("district", "district", 1),
    ("center", "center", 1),
    ("centre", "centre", 1),
]

_KKS = pykakasi.kakasi()


def muni_pages():
    for pref in PREFS:
        for path in sorted((ROOT / pref).rglob("index.html")):
            if path.parent.parent.name == pref:
                yield pref, path.parent.name, path


def p_inner(li: str, cls: str) -> str | None:
    m = P_RE[cls].search(li)
    return m.group(1) if m else None


def set_p(li: str, cls: str, raw_html: str) -> str:
    pat = P_RE[cls]
    if pat.search(li):
        return pat.sub(lambda m: f'<p class="{cls}">{raw_html}</p>', li, count=1)
    return li.replace("</li>", f'<p class="{cls}">{raw_html}</p></li>', 1)


def usable_source(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    host = urlparse(url).netloc.lower()
    return host not in PLACEHOLDER_HOSTS


def source_url(li: str) -> str:
    src = re.search(r"<!-- sources: (.*?)-->", li)
    if src:
        blob = src.group(1)
        for key in ("tabelog_url", "ta_url", "ikkyu_url", "jalan_url"):
            m = re.search(rf"{key}=(https?://\S+?)(?:\s*\||\s*$)", blob)
            if m and usable_source(m.group(1)):
                return m.group(1)
    href = re.search(r'<a href="(https?://[^"]+)"', li)
    if href and usable_source(href.group(1)):
        return href.group(1)
    cred = re.search(r"Source (https?://[^\s>]+)", li)
    if cred and usable_source(cred.group(1)):
        return cred.group(1)
    return ""


def facility_slug(li: str) -> str:
    m = FACILITY_SLUG_RE.search(li)
    if not m:
        return ""
    return m.group(1).replace("_", " ").strip()


def strip_slug_junk(name: str, muni: str) -> str:
    cleaned = SLUG_JUNK_RE.sub(" ", name)
    cleaned = re.sub(
        r"\b(Miyagi|Akita|Fukuoka|Yamaguchi|Oita)\b", " ", cleaned
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -_")
    suffix = " " + muni
    if cleaned.lower().endswith(suffix.lower()) and len(cleaned) > len(suffix):
        cleaned = cleaned[: -len(suffix)].strip()
    return cleaned


# Orthographic variants whose reading is the common kanji pykakasi already knows.
# This is not a translation; 髙/高, 濵/浜, 﨑/崎 and 德/徳 are the same names.
VARIANT_MAP = str.maketrans(
    {
        "\ufa11": "崎",
        "髙": "高",
        "濵": "浜",
        "濱": "浜",
        "德": "徳",
        "福": "福",
        "神": "神",
        "祥": "祥",
        "𠮷": "吉",
    }
)


def apply_macrons(token: str) -> str:
    token = token.replace("ou", "ō").replace("oo", "ō")
    token = token.replace("uu", "ū").replace("ii", "ī")
    token = token.replace("aa", "ā").replace("ee", "ē")
    return token


def fold_fullwidth(text: str) -> str:
    chars = []
    for ch in text.translate(FW_TRANS):
        code = ord(ch)
        if 0xFF01 <= code <= 0xFF5E:
            chars.append(chr(code - 0xFEE0))
        else:
            chars.append(ch)
    return "".join(chars)


def _runs(text: str):
    """Split into CJK runs and Latin runs. Symbols become spaces."""
    buf: list[str] = []
    kind = None

    def emit():
        nonlocal buf, kind
        if buf and kind:
            yield kind, "".join(buf)
        buf = []
        kind = None

    for ch in text:
        if ch.isspace():
            this = "space"
        elif CJK_RE.search(ch) or ch == "々":
            this = "cjk"
        elif re.match(r"[A-Za-z0-9Ā-ž&'.+-]", ch):
            this = "latin"
        else:
            this = "space"
        if this != kind:
            yield from emit()
            kind = this
        buf.append(ch)
    yield from emit()


_VOICED = {
    "か": "が", "き": "ぎ", "く": "ぐ", "け": "げ", "こ": "ご",
    "さ": "ざ", "し": "じ", "す": "ず", "せ": "ぜ", "そ": "ぞ",
    "た": "だ", "ち": "ぢ", "つ": "づ", "て": "で", "と": "ど",
    "は": "ば", "ひ": "び", "ふ": "ぶ", "へ": "べ", "ほ": "ぼ",
    "う": "ゔ",
}
_VOICED.update({voiced: voiced for voiced in list(_VOICED.values())})


def _prep_kana(text: str) -> str:
    """Normalize variants, iteration marks, and stray voicing marks.

    すゞき is the ordinary spelling of すずき. A voicing mark that does not
    combine with the previous kana is dropped rather than left in the
    English line.
    """
    text = unicodedata.normalize("NFKC", text).translate(VARIANT_MAP)
    out: list[str] = []
    for ch in text:
        if ch in ("\u3099", "\u309a", "\uff9e", "\uff9f") and out:
            combined = unicodedata.normalize("NFC", out[-1] + ch)
            if combined != out[-1] + ch and len(combined) == 1:
                out[-1] = combined
            continue
        if ch in ("ゝ", "ヽ", "ゞ", "ヾ") and out:
            prev = out[-1]
            code = ord(prev)
            is_hira = 0x3041 <= code <= 0x3096
            is_kata = 0x30A1 <= code <= 0x30F6
            if is_hira or is_kata:
                hira = chr(code - 0x60) if is_kata else prev
                if ch in ("ゞ", "ヾ"):
                    hira = _VOICED.get(hira, hira)
                out.append(chr(ord(hira) + 0x60) if is_kata else hira)
                continue
        out.append(ch)
    text = "".join(out)
    text = text.replace("・", " ").replace("･", " ").replace("·", " ")
    text = re.sub(r"[\uFE00-\uFE0F]", "", text)
    return re.sub(r"\s+", " ", text).strip()


def hepburn_name(ja: str) -> str | None:
    """Hepburn of a Japanese facility name.

    Latin runs already in the name stay. Returns None when any kanji has
    no dictionary reading, so a shortened name is not invented.
    """
    text = _prep_kana(ja)
    words: list[str] = []
    for kind, chunk in _runs(text):
        if kind == "space":
            words.append(" ")
            continue
        if kind == "latin":
            words.append(chunk)
            continue
        pieces = _KKS.convert(chunk)
        covered = "".join(piece["orig"] for piece in pieces)
        if "".join(covered.split()) != "".join(chunk.split()):
            return None
        for piece in pieces:
            orig = piece["orig"]
            if not orig or orig.isspace():
                words.append(" ")
                continue
            if not CJK_RE.search(orig):
                words.append(orig.strip())
                continue
            heb = "ten" if orig.strip() == "店" else piece["hepburn"]
            if not heb or CJK_RE.search(heb):
                return None
            words.append(apply_macrons(fold_fullwidth(heb)))
    raw = fold_fullwidth(" ".join(w for w in words if w != " "))
    tokens = [tok for tok in raw.split() if re.search(r"[0-9A-Za-zĀ-ž]", tok)]
    titled = []
    for i, tok in enumerate(tokens):
        if any(c.isupper() for c in tok):
            titled.append(tok)
        elif i and tok.casefold() in PARTICLES:
            titled.append(tok.casefold())
        else:
            titled.append(tok[:1].upper() + tok[1:])
    out = re.sub(r"\s+", " ", " ".join(titled)).strip()
    return out or None


def jp_term_in(text: str, term: str) -> bool:
    """Substring match. パン must not hit パンダ, パンフレット or パンツ."""
    if term != "パン":
        return term in text
    start = 0
    n = len(term)
    while True:
        i = text.find(term, start)
        if i < 0:
            return False
        prev = text[i - 1 : i]
        nxt = text[i + n : i + n + 1]
        if prev == "ン" or nxt in {"ダ", "フ", "ツ"}:
            start = i + 1
            continue
        return True


def best_rule(text: str, rules: list[tuple[str, str, int]], lang: str):
    if not text:
        return None
    best = None
    if lang == "jp":
        for term, label, tier in rules:
            if term and jp_term_in(text, term):
                cand = (tier, len(term), label)
                if best is None or cand > best:
                    best = cand
        return best
    folded = text.casefold()
    for term, label, tier in rules:
        if re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", folded):
            cand = (tier, len(term), label)
            if best is None or cand > best:
                best = cand
    return best


def price_band(*texts: str) -> str | None:
    blob = " ".join(texts)
    if "高級" in blob:
        return "high-end"
    if "格安" in blob or "激安" in blob:
        return "budget"
    return None


def area_phrase(ja: str, slug: str) -> str | None:
    # 道の駅 is a roadside station, not a railway station.
    if "道の駅" in ja:
        return None
    if "駅" in ja or re.search(r"(?<![a-z])station(?![a-z])", slug, re.I):
        return "by the station"
    if "空港" in ja or re.search(r"(?<![a-z])airport(?![a-z])", slug, re.I):
        return "at the airport"
    if "本店" in ja:
        return "the main branch"
    return None


def article_for(word: str) -> str:
    return "An" if word[:1].lower() in "aeiou" else "A"


def build_explanation(genre: str | None, price: str | None, area: str | None, muni: str, pref: str) -> str | None:
    if genre:
        first = price or genre
        head = article_for(first)
        if price:
            head += " " + price
        head += " " + genre
        if area:
            head += " " + area
        text = f"{head} in {muni}, {pref}."
    elif area == "by the station":
        text = f"By the station in {muni}, {pref}."
    elif area == "at the airport":
        text = f"At the airport in {muni}, {pref}."
    elif area == "the main branch":
        text = f"The main branch in {muni}, {pref}."
    else:
        return None
    words = re.sub(r"[.,]", "", text).split()
    if len(words) < 6 and text.endswith("."):
        text = text[:-1] + " prefecture."
        words = re.sub(r"[.,]", "", text).split()
    if len(words) > 15 and (area or price):
        return build_explanation(genre, None, None, muni, pref)
    if LISTING_RE.search(text) or CJK_RE.search(text) or FULLWIDTH_RE.search(text):
        return None
    if len(text) < 15:
        return None
    return text


def sourced_explanation(kind: str, ja: str, en_name: str, slug: str, muni: str, pref: str) -> str | None:
    if kind == "Stay":
        jp_rules, en_rules = STAY_JP, STAY_EN
    elif kind in ("Dining", "Stay"):
        jp_rules, en_rules = DINING_JP, DINING_EN
    else:
        jp_rules, en_rules = [], SIGHT_EN
    jp_hit = best_rule(ja, jp_rules, "jp") if kind in ("Dining", "Stay") else None
    en_blob = " ".join(part for part in (slug, en_name if not CJK_RE.search(en_name) else "") if part)
    en_hit = best_rule(en_blob, en_rules, "en")
    if kind not in ("Dining", "Stay"):
        en_hit = best_rule(en_name, SIGHT_EN, "en")
        jp_hit = None
    chosen = None
    if jp_hit and en_hit:
        chosen = jp_hit if jp_hit[0] >= en_hit[0] else en_hit
    else:
        chosen = jp_hit or en_hit
    genre = chosen[2] if chosen else None
    price = price_band(ja) if kind in ("Dining", "Stay") else None
    area = area_phrase(ja, slug) if kind in ("Dining", "Stay") else None
    return build_explanation(genre, price, area, muni, pref)


def fold_if_fullwidth(text: str) -> str:
    """ASCII-fold fullwidth letters and punctuation in an otherwise Latin name."""
    if not text or CJK_RE.search(text) or not FULLWIDTH_RE.search(text):
        return text
    return re.sub(r"\s+", " ", fold_fullwidth(text)).strip()


def blurb_needs_romanization(blurb: str) -> bool:
    if not blurb or CJK_RE.search(blurb) or SLUG_JUNK_RE.search(blurb):
        return True
    return False


def is_explanatory_blurb(blurb: str, name: str) -> bool:
    if not blurb or CJK_RE.search(blurb) or SLUG_JUNK_RE.search(blurb):
        return False
    if LISTING_RE.search(blurb):
        return False
    if blurb.casefold() == name.casefold():
        return False
    if "—" in blurb or " - " in blurb:
        return True
    return len(blurb.split()) >= 4


def good_existing_desc(desc: str | None) -> bool:
    if not desc:
        return False
    text = html.unescape(desc).strip()
    if len(text) < 15 or CJK_RE.search(text) or LISTING_RE.search(text):
        return False
    return True


def cap_section(body: str) -> tuple[str, int]:
    lis = LI_RE.findall(body)
    if len(lis) <= CAP_LIMIT:
        return body, 0
    first = body.find("<li>")
    last = body.rfind("</li>")
    if first < 0 or last < 0:
        return body, 0
    suffix = body[last + len("</li>") :]
    kept = "".join(lis[:CAP_LIMIT])
    return body[:first] + kept + suffix, len(lis) - CAP_LIMIT


def upsert_desc(li: str, desc: str, url: str) -> str:
    li = re.sub(r'<p class="place-desc">.*?</p>', "", li, flags=re.S)
    li = re.sub(r"<!-- desc-source:.*?-->", "", li, flags=re.S)
    block = f'<p class="place-desc">{html.escape(desc, quote=False)}</p>'
    if url and "--" not in url:
        block += f"<!-- desc-source: {url} -->"
    elif url:
        block += f"<!-- desc-source: {url.replace('--', '-')} -->"
    meta = re.search(r'<p class="place-meta">.*?</p>', li, flags=re.S)
    if not meta:
        return li.replace("</li>", block + "</li>", 1)
    return li[: meta.end()] + block + li[meta.end() :]


def _apply_hepburn(name: str, stats: dict, name_flags: list, page: str, kind: str, index: int) -> str | None:
    roman = hepburn_name(name)
    if roman and not CJK_RE.search(roman):
        stats["hepburn"] += 1
        return roman
    stats["hepburn_failed"] += 1
    name_flags.append(f"{page}\t{kind}\t{index}\t{name.replace(chr(9), ' ')}")
    return None


def transform_li(
    li: str,
    kind: str,
    index: int,
    muni: str,
    pref: str,
    stats: dict,
    unsourced: list,
    name_flags: list,
    page: str,
) -> str:
    name_raw = p_inner(li, "place-name") or ""
    blurb_raw = p_inner(li, "place-blurb")
    name = html.unescape(name_raw).strip()
    blurb = html.unescape(blurb_raw).strip() if blurb_raw is not None else ""
    slug = facility_slug(li)
    ranked = kind in ("Dining", "Stay")

    if ranked and (not name or not CJK_RE.search(name)):
        if SLUG_JUNK_RE.search(name) or SLUG_JUNK_RE.search(blurb):
            cleaned = facility_slug(li) or strip_slug_junk(name or blurb, muni)
            if cleaned:
                name = cleaned
                li = set_p(li, "place-name", html.escape(cleaned, quote=False))
                blurb = cleaned
                li = set_p(li, "place-blurb", html.escape(cleaned, quote=False))
                stats["slug_names"] += 1

    if ranked:
        if CJK_RE.search(name) and blurb_needs_romanization(blurb):
            roman = _apply_hepburn(name, stats, name_flags, page, kind, index)
            if roman:
                blurb = roman
                li = set_p(li, "place-blurb", html.escape(roman, quote=False))
        elif blurb_needs_romanization(blurb) and name and not CJK_RE.search(name):
            blurb = name
            li = set_p(li, "place-blurb", html.escape(name, quote=False))
        meta = p_inner(li, "place-meta") or ""
        meta_text = html.unescape(meta).strip()
        desired = f"#{index} ranked in {muni}"
        if meta_text != desired:
            li = set_p(li, "place-meta", html.escape(desired, quote=False))
            stats["renumbered"] += 1
    else:
        if is_explanatory_blurb(blurb, name):
            # The old line 2 is already a sourced English explanation.
            if CJK_RE.search(name):
                roman = _apply_hepburn(name, stats, name_flags, page, kind, index)
                if roman:
                    li = set_p(li, "place-blurb", html.escape(roman, quote=False))
            elif blurb != name:
                li = set_p(li, "place-blurb", html.escape(name, quote=False))
        elif CJK_RE.search(name) and blurb_needs_romanization(blurb):
            roman = _apply_hepburn(name, stats, name_flags, page, kind, index)
            if roman:
                li = set_p(li, "place-blurb", html.escape(roman, quote=False))

    current_blurb = html.unescape(p_inner(li, "place-blurb") or "")
    folded_blurb = fold_if_fullwidth(current_blurb)
    if folded_blurb != current_blurb:
        li = set_p(li, "place-blurb", html.escape(folded_blurb, quote=False))
        stats["fullwidth_folded"] += 1
        if ranked:
            blurb = folded_blurb
    current_name = html.unescape(p_inner(li, "place-name") or "")
    folded_name = fold_if_fullwidth(current_name)
    if folded_name and folded_name != current_name:
        name = folded_name
        li = set_p(li, "place-name", html.escape(name, quote=False))

    existing = p_inner(li, "place-desc")
    if good_existing_desc(existing):
        stats["desc_kept"] += 1
        return li

    migrated = (not ranked) and is_explanatory_blurb(blurb, name)
    if migrated:
        desc = blurb
        stats["desc_migrated"] += 1
    else:
        en_for_facts = blurb if blurb and not CJK_RE.search(blurb) else name
        desc = sourced_explanation(kind, name, en_for_facts, slug, muni, pref)
        if desc:
            stats["desc_templated"] += 1
        else:
            stats["desc_missing"] += 1
            label = name or blurb or "(unnamed)"
            unsourced.append(f"{page}\t{kind}\t{index}\t{label.replace(chr(9), ' ')}")
            return li
    url = source_url(li)
    if not url:
        stats["desc_no_url"] += 1
    li = upsert_desc(li, desc, url)
    return li


def process_html(text: str, pref: str, slug: str, stats: dict, unsourced: list, name_flags: list | None = None) -> str:
    if name_flags is None:
        name_flags = []
    h1 = H1_RE.search(text)
    if not h1:
        return text
    muni = html.unescape(h1.group(1)).strip()
    pref_en = PREF_EN[pref]
    page = f"{pref}/{slug}"
    capped = (pref, slug) in CAP_PAGES

    def repl(match: re.Match) -> str:
        head, title, body, tail = match.group(1), match.group(2), match.group(3), match.group(4)
        if capped and title in ("Dining", "Stay"):
            body, removed = cap_section(body)
            stats["capped_removed"] += removed
            stats["capped_sections"] += 1 if removed or True else 0
        lis = LI_RE.findall(body)
        if not lis:
            return match.group(0)
        new_lis = []
        for i, li in enumerate(lis, 1):
            stats["cards"] += 1
            if title in ("Dining", "Stay"):
                stats["ranked"] += 1
            new_lis.append(
                transform_li(li, title, i, muni, pref_en, stats, unsourced, name_flags, page)
            )
        first = body.find("<li>")
        last = body.rfind("</li>")
        body = body[:first] + "".join(new_lis) + body[last + len("</li>") :]
        return head + body + tail

    text = SECTION_RE.sub(repl, text)
    if capped and 'class="city-cap-note"' not in text:
        inserted = False

        def insert(match: re.Match) -> str:
            nonlocal inserted
            if inserted:
                return match.group(0)
            inserted = True
            stats["notes"] += 1
            return NOTE + match.group(0)

        text, _ = re.subn(
            r'<section class="place-section">\s*<h2>(?:Stay|Dining)</h2>',
            insert,
            text,
            count=1,
        )
    return text


def new_stats() -> dict:
    return {
        "cards": 0,
        "ranked": 0,
        "hepburn": 0,
        "hepburn_failed": 0,
        "slug_names": 0,
        "renumbered": 0,
        "desc_kept": 0,
        "desc_migrated": 0,
        "desc_templated": 0,
        "desc_missing": 0,
        "desc_no_url": 0,
        "capped_removed": 0,
        "capped_sections": 0,
        "notes": 0,
        "pages": 0,
        "fullwidth_folded": 0,
    }


def render(write: bool) -> dict:
    stats = new_stats()
    unsourced: list[str] = []
    name_flags: list[str] = []
    for pref, slug, path in muni_pages():
        original = path.read_text(encoding="utf-8")
        updated = process_html(original, pref, slug, stats, unsourced, name_flags)
        stats["pages"] += 1
        if write and updated != original:
            path.write_text(updated, encoding="utf-8")
        if stats["pages"] % 40 == 0:
            print(f"... {stats['pages']} pages", file=sys.stderr)
    if write:
        header = [
            f"# {len(unsourced)} cards had no cuisine, lodging-type, price, or area fact",
            "# in the facility name or the facility portion of its listing URL.",
            "# An explanation was not invented for these cards.",
            "# page\tsection\tposition\tname",
        ]
        body = "\n".join(header + unsourced)
        if name_flags:
            body += (
                "\n\n# "
                + str(len(name_flags))
                + " cards still have a Japanese line 2 because a kanji had no dictionary reading.\n"
                "# page\tsection\tposition\tname\n"
                + "\n".join(name_flags)
            )
        UNSOURCED_PATH.write_text(body + "\n", encoding="utf-8")
    stats["unsourced"] = len(unsourced)
    stats["name_flags"] = len(name_flags)
    return stats


def self_test() -> None:
    assert hepburn_name("一休") == "Ikkyū"
    assert hepburn_name("ホテル定禅寺") == "Hoteru Jōzenji"
    assert hepburn_name("HOTEL AZ 仙台") == "HOTEL AZ Sendai"
    assert CJK_RE.search(hepburn_name("焼肉龍王館 二日市店")) is None
    assert "Yakiniku" in hepburn_name("焼肉龍王館 二日市店")
    assert FULLWIDTH_RE.search(hepburn_name("ネギ・イタリ家")) is None
    assert hepburn_name("LAWSON 光島田1丁目店").startswith("LAWSON")
    assert hepburn_name("珉亭") is None
    assert hepburn_name("すゞき") == "Suzuki"
    assert hepburn_name("ピザﾞ・テン・フォー").startswith("Piza Ten")
    assert fold_if_fullwidth("ＳＯＮＩＣ　ＡＰＡＲＴＭＥＮＴ") == "SONIC APARTMENT"
    assert "<" in fold_if_fullwidth("Ryokan ＜ Kawatabi")
    assert hepburn_name("うどん・そば・おにぎり") == "Udon Soba Onigiri"
    assert "Takahashi" in (hepburn_name("髙橋菓子舗") or "")
    panda = sourced_explanation("Dining", "ファミリーレストラン パンダ", "", "", "Ogata", "Akita")
    assert panda == "A restaurant in Ogata, Akita prefecture."
    assert sourced_explanation("Dining", "道の駅東松島", "", "", "Higashimatsushima", "Miyagi") == (
        "A roadside station in Higashimatsushima, Miyagi."
    )

    assert sourced_explanation("Dining", "麺ハウス こもれ美", "", "", "Ohira", "Miyagi") == (
        "A noodle shop in Ohira, Miyagi."
    )
    assert sourced_explanation("Dining", "シャハジー", "Shahji", "", "Ohira", "Miyagi") is None
    assert (
        sourced_explanation(
            "Dining",
            "ハンバーガー屋",
            "",
            "",
            "Sendai",
            "Miyagi",
        )
        == "A hamburger shop in Sendai, Miyagi."
    )
    assert sourced_explanation("Stay", "ビジネスホテル新ばし", "", "", "Ohira", "Miyagi").startswith(
        "A business hotel"
    )
    assert sourced_explanation("Dining", "駅前食堂", "", "", "Sendai", "Miyagi") == (
        "A diner by the station in Sendai, Miyagi."
    )
    roman_bar = sourced_explanation("Dining", "居酒屋けん", "", "", "Sendai", "Miyagi")
    assert roman_bar == "An izakaya in Sendai, Miyagi prefecture."

    slug_li = (
        '<li><a href="https://www.tripadvisor.com/Restaurant_Review-g1-d2-Reviews-'
        'Wakamatsuya-Yanagawa_Fukuoka_Prefecture_Kyushu.html"><p class="place-name">'
        "Wakamatsuya Yanagawa Fukuoka Prefecture Kyushu</p></a>"
        '<p class="place-blurb">Wakamatsuya Yanagawa Fukuoka Prefecture Kyushu</p>'
        '<p class="place-meta">#3 ranked in Yanagawa</p>'
        "<!-- sources: ta_url=https://www.tripadvisor.com/Restaurant_Review-g1-d2-Reviews-"
        "Wakamatsuya-Yanagawa_Fukuoka_Prefecture_Kyushu.html --></li>"
    )
    stats = new_stats()
    unsourced: list[str] = []
    out = transform_li(
        slug_li, "Dining", 3, "Yanagawa", "Fukuoka", stats, unsourced, [], "fukuoka/yanagawa"
    )
    assert "Prefecture Kyushu" not in out
    assert ">Wakamatsuya</p>" in out
    assert stats["slug_names"] == 1
    assert unsourced, "a slug name with no cuisine fact must be flagged"

    page = """<h1 class="page-title">Sendai</h1>
<section class="place-section"><h2>Stay</h2><ul class="place-list">"""
    for n in range(1, 4):
        page += (
            f'<li><a href="https://www.jalan.net/yad{n}/"><p class="place-name">ホテル{n}</p></a>'
            f'<p class="place-blurb">ホテル{n}</p><p class="place-meta">#{n} ranked in Sendai</p>'
            f"<!-- sources: jalan_url=https://www.jalan.net/yad{n}/ --></li>"
        )
    page += "</ul></section><section class=\"place-section\"><h2>Dining</h2><ul class=\"place-list\">"
    for n in range(1, 23):
        page += (
            f'<li><a href="https://tabelog.com/miyagi/A0401/A040101/400{n:04d}/">'
            f'<p class="place-name">ラーメン{n}</p></a>'
            f'<p class="place-blurb">ラーメン{n}</p><p class="place-meta">#{n} ranked in Sendai</p>'
            f"<!-- sources: tabelog_url=https://tabelog.com/miyagi/A0401/A040101/400{n:04d}/ --></li>"
        )
    page += "</ul></section>"
    stats = new_stats()
    unsourced = []
    rendered = process_html(page, "miyagi", "sendai", stats, unsourced)
    assert rendered.count('class="city-cap-note"') == 1
    assert "chat box." in rendered
    dining = rendered.split("<h2>Dining</h2>", 1)[1]
    assert dining.count("<li>") == 20
    assert "#20 ranked in Sendai" in dining
    assert "#21 ranked in Sendai" not in rendered
    assert "A ramen shop in Sendai, Miyagi." in dining
    assert "desc-source: https://tabelog.com/" in dining
    stay = rendered.split("<h2>Stay</h2>", 1)[1].split("<h2>Dining</h2>", 1)[0]
    assert stay.count("<li>") == 3
    again = process_html(rendered, "miyagi", "sendai", new_stats(), [])
    assert again.count('class="city-cap-note"') == 1
    assert again.count("<li>") == rendered.count("<li>")

    plain = page.replace("Sendai", "Ohira")
    stats = new_stats()
    kept = process_html(plain, "miyagi", "ohira", stats, [])
    assert 'class="city-cap-note"' not in kept
    assert kept.count("<li>") == 3 + 22
    print("self-test ok")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--stats-only", action="store_true")
    args = parser.parse_args()
    self_test()
    if args.self_test:
        return
    stats = render(write=not args.stats_only)
    for key in sorted(stats):
        print(f"{key} {stats[key]}")


if __name__ == "__main__":
    main()
