#!/usr/bin/env python3
"""English-first card headings (Michael's decision 2026-10-17: English everywhere).

Converts every card whose headline (p.place-name) is Japanese into:

  <li><a href="..."><p class="place-name">ENGLISH HEADLINE</p><p class="place-name-ja" lang="ja">JAPANESE NAME</p>
      [<p class="place-pron">Romaji: ...</p>]<!-- name-en: line|alt|category --><img ...></a> <p class="place-meta">...</p> ...</li>

The headline and the subtitle stay inside the card link, so the whole card remains clickable. The Japanese
name becomes a small muted subtitle (lang="ja") directly under the headline; the old English line
(p.place-blurb) is removed. JSON-LD ItemList items on the same page get name = English headline,
alternateName = Japanese name. Nothing is regenerated and nothing is invented.

English name ladder (per card, first hit wins):
  line      the card's own English line (p.place-blurb) when it is a clean English or Hepburn name
            (passes rough_romaji() + the bj-romaji-check logic + token and katakana rules below)
  alt       the thumbnail alt text when it is English and passes the same checks (and the line did not)
  category  a category-led headline built only from facts on the card: "Ramen shop in Taira", category from the
            card description lead / Japanese name keyword / listing category, town from the "#N ranked in {Town}"
            meta. Colliding headlines in one town get a distinguishing fact: area ("in Kosei, Handa"), then
            station ("near X Station"), then rank "(#N)" (listing-order ordinal when the card has no rank).
  A rough English line replaced by a category-led headline survives only as a small "Romaji: ..." line when it
  passes the bj-romaji-check logic; otherwise it is dropped.

Deterministic and idempotent: converted cards (they carry place-name-ja) are never touched again.
Run it on a checkout AFTER regenerating, BEFORE scripts/ai_friendly.py:

  python3 scripts/english_first_headings.py --root . [--pref wakayama[,tottori]] [--check] [--dry-run]
                                              [--stats stats.json] [--report cards.tsv] [--include-tokyo]

--check   exit 1 if any page would change (0 changes on a converted tree), writes nothing
--dry-run compute and print stats, write nothing, always exit 0
Tokyo (tokyo/) is skipped unless --include-tokyo. pykakasi is optional (enables the katakana-loanword rule).
"""
import argparse, collections, difflib, html, json, os, re, sys

CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f]')
LI_RX = re.compile(r'<li>(?:(?!</li>).)*?</li>', re.S)
SECTIONS = ('eat', 'stay', 'see', 'do', 'day-to-day')

# ---------------------------------------------------------------- English name quality (same logic as the checkers)
ROUGH = [re.compile(p) for p in (r'\b(Men|Ya|Ga|No|Wo|Ni|Ha|Wa|O|Sho|Hon) [A-Z]', r'\b[A-Z][a-z]? [A-Z][a-z]? [A-Z]',
                                 r'[\u3040-\u30ff゙ゞゝ]', r'\bHon-ya\b', r'-ya [A-Z][a-z]?-')]  # = bj_shared.rough_romaji


def rough_romaji(en):
    return bool(en) and any(r.search(en) for r in ROUGH)


MAC = str.maketrans("ŌōŪūĀāĒēĪī", "OoUuAaEeIi")
ENG = set("shrine temple falls route park museum castle hall station street bridge garden heritage scenic japan japanese memorial lake river mountain hot spring springs onsen market "
          "sports works parks crafts bricks docks rocks shops stores streets strawberry strawberries brewery grill grills plaza resort restaurants hotels inns spots lodge lodges "
          "schools church kitchens burgers sandwiches smoothie smoothies world cocktails cocktail drinks".split())
SHORT_OK = {"A", "I", "An", "La", "Le", "De", "Du", "In", "On", "Of", "By", "To", "Mt", "St", "Dr", "Mr", "Ms", "Jr", "Co", "No", "Yu"}
GENERIC = set("cafe café coffee restaurant hotel inn bar pub shop store ramen sushi udon soba izakaya bakery diner ryokan minshuku pension lodge guesthouse onsen spa".split())
CL3_OK = re.compile(r"^(str|spr|scr|thr|chr|sch|shr|phr|spl|squ)")


def cluster_bad(w):
    """Run of 3+ consonants in a word that ends like Hepburn (vowel or n). Real Hepburn only has tch/ssh;
    English words (Sightseeing, Craftsmanship, Resorts) end in other letters or start with str/chr/sch and pass."""
    wl = w.lower()
    if wl in ENG or (len(w) > 1 and w.isupper()) or not re.search(r"[aeiouyn]$", wl): return False
    for m in re.finditer(r"[bcdfghjkmprstvz]{3,}", wl.replace("tch", "t").replace("ssh", "s").replace("ght", "t")):
        if not CL3_OK.search(wl): return True
    return False


def camel_bad(w):
    """Garbled join: a lower-to-Upper boundary with a segment shorter than 3 letters (InterContinental passes, DoCheChe / LiVEMAX do not)."""
    w = re.sub(r"^(Mc|Mac)(?=[A-Z])", "", w)
    if not re.search(r"[a-z][A-Z]", w): return False
    return any(len(x) < 3 for x in re.findall(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])", w))


def romaji_issues(raw):
    """bj-romaji-check logic (workflows/bj-romaji-check/romaji_check.py checks()), minus the html-entity note.
    Looser than the original only where the original false-flags English: consonant clusters in English words and
    all-caps brands, and CamelCase brands whose segments are real words."""
    s = html.unescape(raw); out = []
    if re.search(r"[A-Za-z]'[A-Z]", s): out.append("bad caps after apostrophe")
    if any(cluster_bad(w) for w in re.findall(r"[A-Za-z]+", s)): out.append("consonant cluster")
    if re.search(r"(ou|uu)\b", s.lower()) and not re.search(r"[ōū]", s): out.append("wapuro long vowel")
    if re.search(r"\b(Shi|Chi|Tsu)(?=[A-Z])", s) or any(camel_bad(w) for w in re.findall(r"[A-Za-z]+", s)): out.append("camel/garbled join")
    if re.search(r"[^\x00-\x7FŌōŪūĀāĒēĪī’'&().,\-\u2013 0-9]", s): out.append("non-romaji chars")
    return out


def token_flags(s):
    """Extra rules for pykakasi split debris that the detectors above let through (Toriten Ku, Kogure Ya, Oteru Do Yoshino)."""
    out = []
    for t in s.split():
        if (re.fullmatch(r"[BCDFGHJKMNPRSTWYZ][aiueo]", t) and t not in SHORT_OK) or (re.fullmatch(r"[B-HJ-Z]", t) and t not in SHORT_OK): out.append("syllable token " + t)
    if re.search(r"\b(Shi|Chi|Tsu)\b", s) or re.search(r"\bHon$", s): out.append("syllable token")
    if s.strip().lower() in GENERIC or len(s.strip()) < 2: out.append("generic or empty")
    if re.search(r"\bLocal (spot|sight)\b", s): out.append("placeholder")
    return out


try:
    import pykakasi
    _KKS = pykakasi.kakasi()
except Exception:  # optional: without pykakasi the katakana rule is skipped
    _KKS = None


def _norm(x):
    x = x.translate(MAC).lower()
    x = re.sub(r"ou|oo|uu|aa|ii|ee", lambda m: m.group(0)[0], x)
    return re.sub(r"[^a-z]", "", x)


def kata_translit(ja, en):
    """True when the English text is just the katakana in the Japanese name read aloud (Hot Ea Koporeshon for
    ホット・エアー・コーポレーション, Foresutopia for フォレストピア): a loanword, not an English name.
    Whole-name test for all-katakana names, plus a token test against each katakana run for mixed names."""
    if _KKS is None: return False
    core = re.sub(r"[\s・ー\-&＆（）()]", "", ja)
    if not core: return False
    hep = lambda t: "".join(w["hepburn"] for w in _KKS.convert(t))
    realish = lambda t: re.search(r"[lqx]|c(?!h)|th|\d", t.lower())  # Hepburn has no l/q/x/c/th: genuine English letters
    if sum(1 for ch in core if "\u30a0" <= ch <= "\u30ff") >= 0.8 * len(core) and not realish(en):
        if difflib.SequenceMatcher(None, _norm(hep(ja)), _norm(en)).ratio() >= 0.8: return True
    for run in re.findall(r"[\u30a1-\u30fa\u30fc]{5,}", ja):
        if len(run.replace("ー", "")) < 5: continue
        rn = _norm(hep(run))
        for tok in re.findall(r"[A-Za-zŌōŪū]{7,}", en):
            tn = _norm(tok)
            if not realish(tok) and (difflib.SequenceMatcher(None, rn, tn).ratio() >= 0.86 or (len(tn) >= 8 and tn in rn)): return True
    return False


FRAGMENT = re.compile(r"^[-–]|\s[-–][A-Za-z]|[-–]\s*$|\s[-–]\s[A-Za-z]{1,3}$|\s[’'`]\s|\s[-–]\s(?!(?:The|Inn|Spa|One|Two|Bar|Pub|Zen|Day|Sun|Sea|Bay|Pro|Eco|Art|Pet|Dog|Cat|New|Old|Big|Hot|Jr|JR|Co|No|Ex|My|Us|Go|Be|By|In|On|At|To|An|Ai|II|III)\b)[A-Z][a-z]{1,2}\b")


def en_ok(raw, ja=''):
    """True when the English text may headline a card (raw = text as it sits in the page)."""
    s = html.unescape(raw or '').strip()
    if not s or CJK.search(s): return False
    if FRAGMENT.search(s): return False  # truncated katakana ('-ya Kitori', 'Hotel Arufa - Wan', 'Farmam ’ s cafe')
    return not (rough_romaji(s) or romaji_issues(s) or token_flags(s) or (ja and kata_translit(ja, s)))


def pron_ok(raw):
    """May a demoted English line survive as a small 'Romaji:' line? bj-romaji-check logic only."""
    s = html.unescape(raw or '').strip()
    return bool(s) and not CJK.search(s) and not romaji_issues(s) and s.lower() not in GENERIC and not re.search(r"\bLocal (spot|sight)\b", s)


# ---------------------------------------------------------------- category from facts on the card
GENERIC_LEAD = {"Restaurant", "Food spot", "Accommodation", "Lodging", "Lodging facility", "Accommodation facility", "Casual restaurant", "Diner"}
BAD_LEAD = re.compile(r'^(A|An|The|In|Opened|Built|Founded|Located|Said|Seen|About|Moved|Completed|One|Introduces|Official|Temple no|Pines|Tenkai|Kites|Cultivates|Shinmaiko)\b|\d', re.I)
FOLDER_EN = {'noodles': 'Noodle restaurant', 'cafe': 'Café', 'sweets-bakeries': 'Sweets and bakery shop', 'izakaya-bars': 'Izakaya or bar', 'seafood': 'Seafood restaurant',
             'meat': 'Meat restaurant', 'curry': 'Curry restaurant', 'european': 'European restaurant', 'chinese-asian': 'Chinese or Asian restaurant',
             'other-japanese': 'Japanese restaurant', 'casual': 'Casual restaurant', 'other': 'Restaurant'}
JA_KEYS = {  # keyword in the Japanese name -> English category (translation of a generic word, never a name)
    'eat': [('ラーメン', 'Ramen shop'), ('らーめん', 'Ramen shop'), ('拉麺', 'Ramen shop'), ('中華そば', 'Ramen shop'), ('つけ麺', 'Tsukemen shop'), ('蕎麦', 'Soba restaurant'), ('そば', 'Soba restaurant'),
            ('うどん', 'Udon restaurant'), ('寿司', 'Sushi restaurant'), ('鮨', 'Sushi restaurant'), ('すし', 'Sushi restaurant'), ('焼肉', 'Yakiniku restaurant'), ('焼鳥', 'Yakitori restaurant'),
            ('焼き鳥', 'Yakitori restaurant'), ('居酒屋', 'Izakaya'), ('酒場', 'Izakaya'), ('珈琲', 'Coffee shop'), ('コーヒー', 'Coffee shop'), ('カフェ', 'Café'), ('喫茶', 'Coffee house'),
            ('ベーカリー', 'Bakery'), ('パン', 'Bakery'), ('パティスリー', 'Cake shop'), ('ケーキ', 'Cake shop'), ('菓子', 'Sweets shop'), ('食堂', 'Diner'), ('カレー', 'Curry restaurant'),
            ('ピザ', 'Pizzeria'), ('中華', 'Chinese restaurant'), ('餃子', 'Gyoza restaurant'), ('天ぷら', 'Tempura restaurant'), ('天婦羅', 'Tempura restaurant'), ('うなぎ', 'Eel restaurant'),
            ('鰻', 'Eel restaurant'), ('とんかつ', 'Tonkatsu restaurant'), ('お好み焼', 'Okonomiyaki restaurant'), ('ステーキ', 'Steakhouse'), ('ハンバーガー', 'Burger shop'), ('ハンバーグ', 'Hamburg-steak restaurant'),
            ('バー', 'Bar'), ('BAR', 'Bar'), ('Bar', 'Bar'), ('スナック', 'Snack bar'), ('レストラン', 'Restaurant'), ('ビストロ', 'Bistro'), ('イタリアン', 'Italian restaurant'), ('海鮮', 'Seafood restaurant')],
    'stay': [('ホテル', 'Hotel'), ('ドーミーイン', 'Hotel'), ('旅館', 'Ryokan'), ('民宿', 'Minshuku'), ('ペンション', 'Pension'), ('ゲストハウス', 'Guesthouse'), ('ロッジ', 'Lodge'), ('コテージ', 'Cottage'),
             ('キャンプ', 'Campground'), ('ユースホステル', 'Youth hostel'), ('ホステル', 'Hostel'), ('別荘', 'Villa'), ('の湯', 'Onsen inn'), ('荘', 'Inn'), ('館', 'Inn'), ('宿', 'Inn'), ('イン', 'Inn'),
             ('温泉', 'Onsen inn'), ('リゾート', 'Resort')],
    'see': [('神社', 'Shrine'), ('大社', 'Shrine'), ('寺', 'Temple'), ('公園', 'Park'), ('城', 'Castle'), ('美術館', 'Art museum'), ('博物館', 'Museum'), ('資料館', 'Museum'), ('滝', 'Waterfall'),
            ('湖', 'Lake'), ('庭園', 'Garden'), ('山', 'Mountain'), ('海岸', 'Coast'), ('橋', 'Bridge'), ('駅', 'Station'), ('跡', 'Historic site'), ('古墳', 'Burial mound'), ('井戸', 'Historic well'),
            ('墓', 'Grave'), ('碑', 'Monument'), ('関所', 'Historic checkpoint'), ('温泉', 'Hot spring')],
    'do': [('温泉', 'Hot spring'), ('公園', 'Park'), ('キャンプ', 'Campground'), ('スキー', 'Ski area'), ('体験', 'Hands-on experience'), ('農園', 'Farm'), ('牧場', 'Ranch'), ('酒造', 'Brewery'),
           ('動物園', 'Zoo'), ('水族館', 'Aquarium'), ('ゴルフ', 'Golf course'), ('道の駅', 'Roadside station'), ('美術館', 'Art museum'), ('博物館', 'Museum')],
    'day-to-day': [('役場', 'Town office'), ('市役所', 'City hall'), ('町役場', 'Town office'), ('村役場', 'Village office'), ('コンビニ', 'Convenience store'), ('ローソン', 'Convenience store'),
                   ('セブン', 'Convenience store'), ('ファミリーマート', 'Convenience store'), ('スーパー', 'Supermarket'), ('郵便局', 'Post office'), ('病院', 'Hospital'), ('駅', 'Station'),
                   ('観光案内', 'Tourist information'), ('観光協会', 'Tourist information')],
}
SECTION_DEFAULT = {'eat': 'Restaurant', 'stay': 'Accommodation', 'see': 'Local sight', 'do': 'Activity spot', 'day-to-day': 'Local service'}
DESC_LEAD_SPLIT = re.compile(r',|;|:|\. |\.$| in | at | from | with | near | on | by ')
LEAD_ONE = set("hotel inn ryokan minshuku pension guesthouse hostel lodge villa cottage cottages glamping resort izakaya ramen cafe café bakery bar pub diner restaurant shokudo steakhouse bistro "
               "accommodation lodging ryotei sushi soba udon yakiniku yakitori bento pizzeria brewery winery".split())
LEAD_ADJ = re.compile(r'(ese|ian|ish)$')


def lead_category(desc, town='', name_en=''):
    """Category phrase from the start of the English description, only when it is a plain category noun phrase
    (no proper nouns, no sentence, not the venue's own name)."""
    t = html.unescape(desc or '').strip()
    if not t: return ''
    h = DESC_LEAD_SPLIT.split(t)[0].strip()
    bare = re.sub(r'\([^)]*\)', '', h).strip()
    w = bare.split()
    if not w or len(w) > 4 or BAD_LEAD.search(h) or CJK.search(h) or re.search(r'\b(is|are|was|has|offers)\b', h): return ''
    if any(x[:1].isupper() for x in w[1:]) or (town and town in bare) or (name_en and bare and bare in name_en): return ''
    if len(w) == 1 and w[0].lower() not in LEAD_ONE:
        return (w[0] + ' restaurant') if LEAD_ADJ.search(w[0]) and w[0][:1].isupper() else ''
    return h[0].upper() + h[1:]


def category_of(section, ja, desc, folder, town='', name_en=''):
    lead = lead_category(desc, town, name_en)
    if lead and lead not in GENERIC_LEAD: return lead
    for k, v in JA_KEYS.get(section, []):
        if k in ja: return v
    if section == 'eat' and folder in FOLDER_EN and folder != 'other': return FOLDER_EN[folder]
    return lead or SECTION_DEFAULT.get(section, 'Place')


AREA_RX = re.compile(r"^[^,;:.]*? in ([A-Z][\w'’\-. ]+?)(?:, ([A-Z][\w'’\-. ]+?))?(?:,| with | founded|;|:|\.|$)")
STATION_RX = re.compile(r"(?:from|near|beside|in front of) ([A-Z][\w'’\-. ]*? Station)")


def facts_of(desc, town):
    d = html.unescape(desc or '')
    area = ''
    m = AREA_RX.match(d)
    if m:
        a, b = m.group(1).strip(), (m.group(2) or '').strip()
        if b and b == town and a != town: area = a
        elif a and a != town and not b and len(a.split()) <= 3 and 'neighbouring' not in a and 'Aichi' not in a: area = a
    st = STATION_RX.search(d)
    return area, (st.group(1) if st else '')


def esc(s):
    return html.escape(s, quote=True)


# ---------------------------------------------------------------- card parsing
def fld(rx, li):
    m = re.search(rx, li, re.S)
    return m.group(1) if m else None


def parse_card(li):
    name = fld(r'<p class="place-name">(.*?)</p>', li)
    if name is None: return None
    return {'name': name, 'blurb': fld(r'<p class="place-blurb">(.*?)</p>', li), 'alt': fld(r'<img[^>]*?\salt="([^"]*)"', li),
            'href': fld(r'<a href="([^"]*)"', li) or '', 'meta': fld(r'<p class="place-meta">(.*?)</p>', li) or '',
            'desc': fld(r'<p class="place-desc">(.*?)</p>', li) or '', 'converted': 'place-name-ja' in li}


def town_of(card, slug):
    m = re.search(r'ranked in (.+)$', html.unescape(card['meta']))
    if m: return m.group(1).strip().rsplit(' in ', 1)[-1]
    m = re.match(r'([^,·]+?)(?:,|\s·|$)', html.unescape(card['meta']))
    if m and m.group(1).strip(): return m.group(1).strip().rsplit(' in ', 1)[-1]
    return slug.replace('-', ' ').title()


def rank_of(card):
    m = re.match(r'#(\d+)', html.unescape(card['meta']))
    return m.group(1) if m else ''


def decide(card, section, folder, town):
    """-> (headline unescaped, provenance, pron unescaped or '', facts) for a not-yet-converted JA-headline card."""
    ja = html.unescape(card['name'])
    bl = html.unescape(card['blurb'] or '').strip()
    alt = html.unescape(card['alt'] or '').strip()
    if en_ok(bl, ja): return bl, 'line', '', None
    if en_ok(alt, ja): return alt, 'alt', '', None
    cat = category_of(section, ja, card['desc'], folder, town, bl or alt)
    return f'{cat} in {town}', 'category', (bl if pron_ok(bl) else ''), (cat, town, facts_of(card['desc'], town), rank_of(card))


def disambiguate(entries, used):
    """entries: dicts with base, cat, town, area, station, rank, key. Sets e['head'], unique within the town (also vs `used`)."""
    for e in entries: e['head'] = e['base']
    byb = collections.defaultdict(list)
    for e in entries: byb[e['base']].append(e)
    for g in byb.values():
        for i, e in enumerate(sorted(g, key=lambda x: x['key']), 1): e['ord'] = i  # listing-order ordinal, only for cards without a rank
    for level in ('area', 'station', 'rank'):
        cnt = collections.Counter([e['head'] for e in entries] + list(used))
        bad = {h for h, n in cnt.items() if n > 1}
        for e in entries:
            if e['head'] not in bad or (e['head'] != e['base'] and level != 'rank'): continue
            if level == 'area' and e['area']: e['head'] = f"{e['cat']} in {e['area']}, {e['town']}"
            elif level == 'station' and e['station']: e['head'] = f"{e['cat']} in {e['town']}, near {e['station']}"
            elif level == 'rank': e['head'] = f"{e['head']} (#{e['rank'] or e['ord']})"
    fin = collections.defaultdict(list)  # same rank on two cards (ranks restart per section): number the extras
    for e in entries: fin[e['head']].append(e)
    for h, g in fin.items():
        for i, e in enumerate(sorted(g, key=lambda x: x['key'])):
            if i and h.endswith(')'): e['head'] = f"{h[:-1]}, {i + 1})"
    return entries


def convert_li(li, c, head, prov, pron):
    """Headline stays first inside the link; Japanese subtitle (+ optional romaji line) directly under it, also inside the link."""
    ja_raw = c['name']
    en_raw = esc(head)  # same text for every card of the same venue in the town (head was decided once per venue)
    sub = f'<p class="place-name-ja" lang="ja">{ja_raw}</p>'
    if pron: sub += f'<p class="place-pron">Romaji: {esc(pron)}</p>'
    sub += f'<!-- name-en: {prov} -->'
    out = li.replace(f'<p class="place-name">{ja_raw}</p>', f'<p class="place-name">{en_raw}</p>' + sub, 1)
    if c['blurb'] is not None: out = out.replace(f'<p class="place-blurb">{c["blurb"]}</p>', '', 1)
    if c['alt'] is not None and (CJK.search(html.unescape(c['alt'])) or not en_ok(c['alt'])):
        out = out.replace(f'alt="{c["alt"]}"', f'alt="{en_raw}"', 1)  # alt text = headline when the old alt was Japanese or rough
    return out


def _txt(x):
    """Same normalisation as ai_friendly.txt(): strip tags, unescape, collapse whitespace (U+3000 included)."""
    return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', x or ''))).strip()


def jsonld_swap(text, swaps):
    """swaps: list of (ja_raw, old_en_raw, href_raw, new_en). name/alternateName are exchanged inside JSON-LD ItemList items,
    matching the strings the way ai_friendly.py writes them, so a later ai_friendly run reproduces the same JSON-LD."""
    for ja_raw, old_raw, href, new_en in swaps:
        ja, old_en, new_en = _txt(ja_raw), _txt(old_raw), re.sub(r'\s+', ' ', new_en).strip()
        for ascii_ in (False, True):  # pages carry JSON-LD either with raw UTF-8 or \uXXXX escapes
            j = lambda x: json.dumps(x, ensure_ascii=ascii_)
            done = False
            for tail in (f', "url": {j(href)}', ''):
                old = f'"name": {j(ja)}, "alternateName": {j(old_en)}{tail}'
                if old in text:
                    text = text.replace(old, f'"name": {j(new_en)}, "alternateName": {j(ja)}{tail}', 1); done = True; break
            if not done:  # alternateName is stale (the English line was edited after the JSON-LD was written): match name + the same item's url
                rx = re.compile(r'"name": ' + re.escape(j(ja)) + r', "alternateName": "(?:[^"\\]|\\.)*"(?=[^{}]*"url": ' + re.escape(j(href)) + ')')
                text, n = rx.subn(lambda m: f'"name": {j(new_en)}, "alternateName": {j(ja)}', text, count=1); done = n > 0
            if not done:
                old = f'"name": {j(ja)}, "url": {j(href)}'
                if old in text: text = text.replace(old, f'"name": {j(new_en)}, "alternateName": {j(ja)}, "url": {j(href)}', 1); done = True
            if done: break
    return text


# ---------------------------------------------------------------- tree walk
def page_ctx(rel):
    parts = rel.split('/')[:-1]
    sec = parts[2] if len(parts) >= 3 and parts[2] in SECTIONS else ''
    folder = parts[3] if sec == 'eat' and len(parts) >= 4 else ''
    return parts, sec, folder


def town_groups(root, prefs, include_tokyo):
    groups = collections.defaultdict(list)
    for pref in sorted(os.listdir(root)):
        if prefs and pref not in prefs: continue
        if pref == 'tokyo' and not include_tokyo: continue
        pd = os.path.join(root, pref)
        if not os.path.isdir(pd) or pref in ('scripts', 'data', 'media', 'assets', 'go', 'fonts', 'sitemaps'): continue
        for dp, dn, fn in os.walk(pd):
            dn.sort()
            if 'index.html' not in fn: continue
            rel = os.path.relpath(os.path.join(dp, 'index.html'), root)
            parts = rel.split('/')
            if len(parts) < 4: continue  # pref hub or pref/index.html: no cards
            groups[(pref, parts[1])].append(rel)
    return groups


def process_town(root, key, rels, write, stats, report):
    pages = {}
    for rel in sorted(rels):
        with open(os.path.join(root, rel), encoding='utf8') as f: pages[rel] = f.read()
    # pass 1: one decision per venue (href + name) so it gets the same headline on every page of the town
    todo, used = collections.OrderedDict(), set()
    for rel, s in pages.items():
        parts, sec, folder = page_ctx(rel)
        if not sec: continue
        for m in LI_RX.finditer(s):
            c = parse_card(m.group(0))
            if not c: continue
            if c['converted'] or not CJK.search(html.unescape(c['name'])):
                used.add(html.unescape(c['name'])); continue
            k = (c['href'], c['name'])
            if k in todo: continue
            town = town_of(c, key[1])
            head, prov, pron, fx = decide(c, sec, folder, town)
            todo[k] = {'head': head, 'prov': prov, 'pron': pron, 'fx': fx, 'base': head, 'c': c, 'sec': sec}
    cat_entries = []
    for k, v in todo.items():
        if v['prov'] == 'category':
            cat, town, (area, station), rank = v['fx']
            v.update(cat=cat, town=town, area=area, station=station, rank=rank, key=k); cat_entries.append(v)
    disambiguate(cat_entries, used | {v['head'] for v in todo.values() if v['prov'] != 'category'})
    # pass 2: rewrite
    changed = 0
    for rel, s in pages.items():
        parts, sec, folder = page_ctx(rel)
        if not sec: continue
        swaps = []

        def sub(m):
            li = m.group(0); c = parse_card(li)
            if not c or c['converted'] or not CJK.search(html.unescape(c['name'])): return li
            v = todo[(c['href'], c['name'])]
            swaps.append((c['name'], c['blurb'] or '', c['href'], v['head']))
            stats[(key[0], v['sec'], v['prov'])] += 1
            if v['prov'] == 'category' and v['pron']: stats[(key[0], v['sec'], 'pron')] += 1
            if report is not None: report.append((rel, v['sec'], v['prov'], v['head'], html.unescape(c['name']), html.unescape(c['blurb'] or '')))
            return convert_li(li, c, v['head'], v['prov'], v['pron'])
        new = LI_RX.sub(sub, s)
        if new != s:
            new = jsonld_swap(new, swaps); changed += 1
            if write:
                with open(os.path.join(root, rel), 'w', encoding='utf8') as f: f.write(new)
    return changed, len(pages)


def final_stats(root, prefs, include_tokyo):
    """Whole-tree state: per pref/section card counts (JA headline left, provenance) and duplicate headlines per town."""
    out = collections.defaultdict(collections.Counter)
    for (pref, town), rels in town_groups(root, prefs, include_tokyo).items():
        heads, allheads, seen = collections.Counter(), collections.Counter(), set()
        for rel in sorted(rels):
            parts, sec, folder = page_ctx(rel)
            if not sec: continue
            with open(os.path.join(root, rel), encoding='utf8') as f: s = f.read()
            for m in LI_RX.finditer(s):
                c = parse_card(m.group(0))
                if not c: continue
                k = (c['href'], html.unescape(c['name']))
                out[pref][f'{sec}_cards'] += 1
                if CJK.search(html.unescape(c['name'])): out[pref][f'{sec}_ja_headline'] += 1
                if k in seen: continue
                seen.add(k)
                prov = fld(r'<!-- name-en: (\w+) -->', m.group(0))
                if prov: out[pref][f'{sec}_{prov}'] += 1
                if c['converted'] and prov == 'category': heads[html.unescape(c['name'])] += 1
                allheads[html.unescape(c['name'])] += 1
        out[pref]['category_duplicates'] += sum(n - 1 for n in heads.values() if n > 1)
        out[pref]['headline_duplicates_any'] += sum(n - 1 for n in allheads.values() if n > 1)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--root', default='.'); ap.add_argument('--pref', default='', help='slug or comma-separated slugs')
    ap.add_argument('--check', action='store_true'); ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--include-tokyo', action='store_true'); ap.add_argument('--stats', default=''); ap.add_argument('--report', default='')
    a = ap.parse_args()
    prefs = {p for p in a.pref.split(',') if p}
    root = os.path.abspath(a.root)
    groups = town_groups(root, prefs, a.include_tokyo)
    stats, report, changed, npages = collections.Counter(), ([] if a.report else None), 0, 0
    for key in sorted(groups):
        c, n = process_town(root, key, groups[key], not (a.check or a.dry_run), stats, report); changed += c; npages += n
    cnt = lambda p: sum(v for k, v in stats.items() if k[2] == p)
    print(f'{npages} pages scanned, {changed} pages {"would change" if (a.check or a.dry_run) else "changed"}, '
          f'{cnt("line") + cnt("alt") + cnt("category")} cards converted (line {cnt("line")}, alt {cnt("alt")}, category {cnt("category")}, romaji line kept {cnt("pron")})')
    if a.report:
        with open(a.report, 'w', encoding='utf8') as f:
            f.write('page\tsection\tprovenance\theadline\tjapanese\told_english_line\n')
            for r in report: f.write('\t'.join(x.replace('\t', ' ') for x in r) + '\n')
    if a.stats:
        per = collections.defaultdict(collections.Counter)
        for (p, sec, prov), v in stats.items(): per[p][f'{sec}_{prov}'] += v
        res = {'converted': {p: dict(v) for p, v in per.items()}, 'pages_changed': changed}
        if not (a.check or a.dry_run): res['state'] = {p: dict(v) for p, v in final_stats(root, prefs, a.include_tokyo).items()}
        with open(a.stats, 'w') as f: json.dump(res, f, indent=1, ensure_ascii=False, sort_keys=True)
    if a.check and changed:
        print('FAIL: --check found pages that still need conversion', file=sys.stderr); sys.exit(1)


if __name__ == '__main__':
    main()
