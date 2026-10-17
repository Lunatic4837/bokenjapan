#!/usr/bin/env python3
"""bjlib.py - tiny shared helpers for the tools-south toolkit (stdlib + PIL + pykakasi optional).
No torch/CLIP, no paid APIs, no Tabelog data. ASCII output only for romanisation (no macrons)."""
import csv, html as H, json, os, re, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uff66-\uff9f]')
MACRON = re.compile('[\u0100-\u017f\u1e00-\u1eff]')
DEFAULT_TREE = os.environ.get('BJ_TREE', '/workspace/p1/fix-tottori')
MIN_BYTES = 5120

PREF_JA = dict(zip(
    'hokkaido aomori iwate miyagi akita yamagata fukushima ibaraki tochigi gunma saitama chiba tokyo kanagawa niigata toyama ishikawa fukui yamanashi nagano gifu shizuoka aichi mie shiga kyoto osaka hyogo nara wakayama tottori shimane okayama hiroshima yamaguchi tokushima kagawa ehime kochi fukuoka saga nagasaki kumamoto oita miyazaki kagoshima okinawa'.split(),
    '北海道 青森県 岩手県 宮城県 秋田県 山形県 福島県 茨城県 栃木県 群馬県 埼玉県 千葉県 東京都 神奈川県 新潟県 富山県 石川県 福井県 山梨県 長野県 岐阜県 静岡県 愛知県 三重県 滋賀県 京都府 大阪府 兵庫県 奈良県 和歌山県 鳥取県 島根県 岡山県 広島県 山口県 徳島県 香川県 愛媛県 高知県 福岡県 佐賀県 長崎県 熊本県 大分県 宮崎県 鹿児島県 沖縄県'.split()))

# ---- site food-genre tiles, in live hub order: slug -> (tile label, page-title label)
CATS = [('seafood', 'Japanese (seafood)'), ('meat', 'Japanese (meat)'), ('noodles', 'Japanese (noodles)'), ('european', 'European'),
        ('cafe', 'Cafe'), ('curry', 'Curry'), ('casual', 'Casual'), ('chinese-asian', 'Chinese & Asian'), ('izakaya-bars', 'Izakaya & bars'),
        ('sweets-bakeries', 'Sweets & bakeries'), ('other-japanese', 'Other Japanese'), ('other', 'Other')]
CAT_LABEL = dict(CATS); CAT_ORDER = {c: i for i, (c, _) in enumerate(CATS)}

# ---- targets (audit method given by Emma)
def _r(x): return int(x + 0.5)
def target_dining(pop):
    if pop is None: return 24
    if pop >= 50000: return max(50, min(100, _r(pop / 1000)))
    if pop >= 10000: return max(10, min(40, _r(pop / 750)))
    return max(3, min(15, _r(pop / 500)))
def target_stay(pop):
    if pop is None: return 12
    if pop < 20000: return 1
    if pop < 100000: return 3
    return max(3, min(30, _r(pop / 20000)))

_POP = None
def popmap():
    global _POP
    if _POP is None:
        f = Path(os.environ.get('BJ_POPMAP') or HERE / 'popmap.json')
        _POP = json.load(open(f)) if f.exists() else {}
    return _POP

def town_ja(pref, slug):
    return (popmap().get(f'{pref}/{slug}') or {}).get('ja')

# ---- text helpers
def nomacron(s):
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return MACRON.sub('', s)

def norm_name(s):
    """Normalised Japanese/Latin name for dedupe: NFKC, lowercase, drop spaces/punctuation and generic branch words."""
    s = unicodedata.normalize('NFKC', H.unescape(s or '')).lower()
    s = re.sub(r'[\s\u3000・･\-ー~〜～()（）\[\]【】「」『』\'"`.,!!?&＆/／|:：*#]+', '', s)
    return s

def strip_branch(n):
    return re.sub(r'(本店|支店|[^\s]{1,6}店)$', '', n) or n

_KKS = None
_WORDS = [('本店', 'Main Store'), ('ラーメン', 'Ramen'), ('らーめん', 'Ramen'), ('拉麺', 'Ramen'), ('中華そば', 'Chuka Soba'), ('居酒屋', 'Izakaya'),
          ('焼肉', 'Yakiniku'), ('焼鳥', 'Yakitori'), ('焼き鳥', 'Yakitori'), ('食堂', 'Shokudo'), ('珈琲', 'Coffee'), ('コーヒー', 'Coffee'),
          ('喫茶', 'Kissa'), ('カフェ', 'Cafe'), ('寿司', 'Sushi'), ('鮨', 'Sushi'), ('すし', 'Sushi'), ('うどん', 'Udon'), ('蕎麦', 'Soba'),
          ('そば', 'Soba'), ('カレー', 'Curry'), ('餃子', 'Gyoza'), ('お好み焼', 'Okonomiyaki'), ('とんかつ', 'Tonkatsu'), ('天ぷら', 'Tempura'),
          ('駅前', 'Ekimae'), ('砂丘', 'Sakyu'), ('米子', 'Yonago'), ('鳥取', 'Tottori'), ('境港', 'Sakaiminato'), ('倉吉', 'Kurayoshi'),
          ('皆生', 'Kaike'), ('店', 'Branch'), ('酒場', 'Sakaba'), ('食事処', 'Shokujidokoro'), ('料理', 'Ryori'), ('専門', 'Senmon')]
_WSPLIT = re.compile('(' + '|'.join(re.escape(k) for k, _ in sorted(_WORDS, key=lambda x: -len(x[0]))) + ')')
_WD = dict(_WORDS)
def _collapse(w):
    return re.sub(r'ou', 'o', re.sub(r'oo', 'o', re.sub(r'uu', 'u', w)))
def romanize(ja):
    """Clean Hepburn (passport style: no macrons, long vowels collapsed). '' when nothing sensible."""
    global _KKS
    if not ja: return ''
    s = unicodedata.normalize('NFKC', ja).strip()
    if not CJK.search(s): return nomacron(s)
    try:
        import pykakasi
        if _KKS is None: _KKS = pykakasi.kakasi()
    except Exception:
        return ''
    s = re.sub(r'[・･/／|]+', ' ', s)
    s = s.replace('ー', '').translate(str.maketrans('ぁぃぅぇぉ', 'あいうえお'))
    s = re.sub(r'([あ-ん])あ', r'\1', s)
    out = []
    for tok in _WSPLIT.split(s):
        if not tok: continue
        if tok in _WD: out.append(_WD[tok]); continue
        for part in re.split(r"([A-Za-z0-9&'\.\-+]+|\s+)", tok):
            if not part or part.isspace(): continue
            if re.fullmatch(r"[A-Za-z0-9&'\.\-+]+", part): out.append(part); continue
            run = ''
            for it in _KKS.convert(part):
                w = (it.get('passport') or it.get('hepburn') or '').strip()
                if w and re.fullmatch(r"[a-z' ]+", w): run += _collapse(w).replace(' ', '')
                elif not CJK.search(it['orig']) and it['orig'].strip(): run += it['orig'].strip()
            if run: out.append(run[:1].upper() + run[1:])
    r = re.sub(r'\s+', ' ', ' '.join(out)).strip()
    r = re.sub(r'(?<=[A-Za-z]) (?=[&\'])|(?<=[&\']) (?=[A-Za-z])', '', r)
    return nomacron(r)

def town_en(pref, slug, tree=DEFAULT_TREE):
    """English town + prefecture names from the town's own eat page h1; fallback to slug."""
    f = Path(tree) / pref / slug / 'eat' / 'index.html'
    try:
        m = re.search(r'Where to eat in ([^<,]+), ([^<]+)</h1>', f.read_text(encoding='utf-8'))
        if m: return H.unescape(m.group(1)), H.unescape(m.group(2))
    except OSError: pass
    return slug.replace('-', ' ').title(), pref.title()

def live_names(tree, pref, slug):
    """Japanese/Latin place-name strings already on the town's eat pages (hub + category pages)."""
    names = []
    base = Path(tree) / pref / slug / 'eat'
    for f in [base / 'index.html'] + sorted(base.glob('*/index.html')):
        try: t = f.read_text(encoding='utf-8')
        except OSError: continue
        names += [H.unescape(x) for x in re.findall(r'place-name">([^<]*)<', t)]
    return names

def plural(n, w='place'): return f'{n} {w}' if n == 1 else f'{n} {w}s'
def esc(s): return H.escape(s, quote=True)
