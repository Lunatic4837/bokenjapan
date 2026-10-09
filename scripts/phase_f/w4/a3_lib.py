import re, json, csv, sys, unicodedata, html
sys.path.insert(0, '/workspace/p1/data/catalog-uplift/.venv/lib/python3.13/site-packages')
import pykakasi
K = pykakasi.kakasi()
PREFS = {'miyagi': '宮城県', 'akita': '秋田県', 'fukuoka': '福岡県', 'yamaguchi': '山口県', 'oita': '大分県'}
KANJI = re.compile(r'[\u4e00-\u9fff々]')
def build_places():
    P = {}
    geo = json.load(open('/workspace/p1/phase-d/nostay/geo.json'))
    for k, v in geo.items():
        if k.split('/')[0] not in PREFS: continue
        ja = v['ja']; en = v['en']
        P.setdefault(ja, set()).add(en)
        b = re.sub(r'[市町村]$', '', ja)
        if len(b) >= 2: P.setdefault(b, set()).add(en)
    for r in csv.DictReader(open('/workspace/p1/line4/work/stations.csv')):
        if r['prefja'] not in PREFS.values(): continue
        ja = r['ja'][:-1] if r['ja'].endswith('駅') else r['ja']; en = re.sub(r' Station$', '', r['en'])
        if len(ja) >= 2 and KANJI.search(ja) and re.fullmatch(r"[A-Za-z\-ōūŌŪ' ]+", en): P.setdefault(ja, set()).add(en)
    for ja, en in [('宮城', 'Miyagi'), ('秋田', 'Akita'), ('福岡', 'Fukuoka'), ('山口', 'Yamaguchi'), ('大分', 'Oita'), ('博多', 'Hakata'), ('天神', 'Tenjin'), ('小倉', 'Kokura'), ('仙台', 'Sendai')]:
        P.setdefault(ja, set()).add(en)
    out = {}
    for ja, ens in P.items():
        ens = {unicodedata.normalize('NFKD', e).encode('ascii', 'ignore').decode() for e in ens}
        if len(ens) == 1 and KANJI.search(ja): out[ja] = next(iter(ens))
    return out
def flat(x): return re.sub(r'[^a-z]', '', unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode().lower()).replace('ou', 'o').replace('oo', 'o').replace('uu', 'u')
def kak_tokens(ja): return [p.get('hepburn') or '' for p in K.convert(ja)]
def wrong_rx(ja):
    """regex matching how per-token kakasi romanization of ja may appear in a line-2 name"""
    sy = ''.join(kak_tokens(ja)).lower()
    sy = re.sub(r'[^a-z]', '', sy)
    if len(sy) < 3: return None
    parts = []
    i = 0
    while i < len(sy):
        c = sy[i]
        if c in 'aeiou' and i + 1 < len(sy) and sy[i+1] == ('u' if c == 'o' else c): parts.append(re.escape(c) + '[ou]?' if c=='o' else re.escape(c) + c + '?'); i += 2; continue
        parts.append(re.escape(c)); i += 1
    return re.compile(r'(?<![A-Za-z])' + r"[\s\-']?".join(parts) + r'(?![a-z])', re.I)
