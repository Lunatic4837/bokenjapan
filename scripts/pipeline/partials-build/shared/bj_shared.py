#!/usr/bin/env python3
"""bj_shared — shared pipeline fixes from AUDIT-47 (2026-10-15) fix plan P1–P10.
Import from any collector/renderer:  sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as S
Env vars (all optional):
  BJ_TARGET_MODE=pop|legacy   pop (default) = population-scaled targets; legacy = old 24/12 caps
  BJ_DINING_TARGET / BJ_STAY_TARGET   force a fixed target (int) for a run
  BJ_POPMAP                   population map (default quality/audit47/popmap.json)
  BJ_TABELOG_MAX_PAGES=60     hard page limit per Tabelog list (P2)
  BJ_JALAN_MAX_IDX=3000       hard limit for Jalan ?idx= pagination (P4)
  BJ_TABELOG_EN=1|0           look up the official English name on tabelog.com/en (P7, cached)
  BJ_PHOTO_JUDGE=1|0          CLIP food/promo judge for Stay photos (P5); needs /home/box/venvs/bjclip
  BJ_STAY_MIN_W=560           minimum Stay photo width;  BJ_MIN_IMG_BYTES=5120 minimum bytes for any image
"""
from __future__ import annotations
import json, math, os, re, subprocess, html as H, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
P1 = Path('/workspace/p1')
CJK = re.compile(r'[\u3040-\u30ff\u3400-\u9fff\uff00-\uffef\u3000-\u303f]')
def env_int(k, d):
    try: return int(os.environ.get(k, d))
    except ValueError: return d

# ---------------------------------------------------------------- P1 targets
_POP = None
def popmap():
    global _POP
    if _POP is None:
        f = Path(os.environ.get('BJ_POPMAP') or P1 / 'quality/audit47/popmap.json')
        _POP = json.load(open(f)) if f.exists() else {}
    return _POP

def town_pop(pref, *keys, name_ja=None, jis=None):
    pm = popmap()
    for k in keys:
        if k and f'{pref}/{k}' in pm: return pm[f'{pref}/{k}']['pop']
    for v in pm.values():
        if v.get('pref') != pref: continue
        if jis and str(v.get('code', ''))[:5] == str(jis)[:5]: return v['pop']
    for v in pm.values():
        if v.get('pref') == pref and name_ja and v.get('ja') == name_ja: return v['pop']
    return None

def _r(x): return int(x + 0.5)  # half-up, matches the audit's expectations

def target_dining(pop):
    """Audit Method: >=50k: pop/1000 cap 100; 10–50k: pop/750 floor 10 cap 40; <10k: pop/500 floor 3 cap 15."""
    if pop is None: return 24
    if pop >= 50000: return max(50, min(100, _r(pop / 1000)))
    if pop >= 10000: return max(10, min(40, _r(pop / 750)))
    return max(3, min(15, _r(pop / 500)))

def target_stay(pop):
    """Audit Method: >=1 under 20k, >=3 under 100k, otherwise pop/20k (cap 30)."""
    if pop is None: return 12
    if pop < 20000: return 1
    if pop < 100000: return 3
    return max(3, min(30, _r(pop / 20000)))

def targets(pref, d=None, h=None):
    """(dining_target, stay_target, pop) for a hub. h = hub-codes entry (name_ja, jis, slug)."""
    h = h or {}
    if os.environ.get('BJ_TARGET_MODE') == 'legacy': return 24, 12, None
    pop = town_pop(pref, h.get('slug'), d, name_ja=h.get('name_ja'), jis=h.get('jis'))
    td, ts = target_dining(pop), target_stay(pop)
    td = env_int('BJ_DINING_TARGET', td) if os.environ.get('BJ_DINING_TARGET') else td
    ts = env_int('BJ_STAY_TARGET', ts) if os.environ.get('BJ_STAY_TARGET') else ts
    return td, ts, pop

# Stay lists keep more than the minimum when the source has them (min target, but never cut below source)
# Standing bar (Michael, 2026-10-15): list ALL facilities in town. Targets are minimums for checks, never caps.
# BJ_COLLECT_ALL=1 (default) keeps every in-town row the source lists; 0 stops at the target (quick runs).
def collect_all(): return os.environ.get('BJ_COLLECT_ALL', '1') != '0' and os.environ.get('BJ_TARGET_MODE') != 'legacy'
def stay_keep(ts): return 10**6 if collect_all() else max(ts, env_int('BJ_STAY_KEEP_MIN', 12))
def dining_keep(td): return 10**6 if collect_all() else td

# ---------------------------------------------------------------- P2 Tabelog
def parse_tabelog_list(html, pref=None):
    rows = []
    for b in re.split(r'class="list-rst__rst-name-target', html)[1:]:
        m = re.search(r'href="(https://tabelog\.com/([a-z]+)/(A\d+)/(A\d+)/(\d+)/)"[^>]*>([^<]+)</a>', b)
        if not m: continue
        ag = re.search(r'list-rst__area-genre[^>]*>([^<]*)<', b)
        ag = re.sub(r'\s+', ' ', H.unescape(ag.group(1))).strip() if ag else ''
        area, _, genre = ag.partition(' / ')
        addr = re.search(r'list-rst__address[^>]*>\s*([^<]+)', b)
        sc = re.search(r'c-rating__val[^>]*>\s*([\d.]+)', b)
        rv = re.search(r'cpy-review-count">(\d+)', b)
        img = re.search(r'data-lazy="(https://tblg\.k-img\.com/[^"]+)"', b)
        bud = re.findall(r'aria-label="(夜|昼)の予算"[^>]*></i><span class="c-rating-v3__val">([^<]+)<', b)
        rows.append({'name_ja': H.unescape(m.group(6).strip()), 'tabelog_url': m.group(1), 'url': m.group(1), 'pref_tb': m.group(2),
                     'a1': m.group(3), 'a2': m.group(4), 'rid': m.group(5), 'rst_id': m.group(5), 'area_ja': area.strip(),
                     'genre': (genre.split('、')[0].strip()), 'genre_ja': genre.strip(), 'addr': addr.group(1).strip() if addr else '',
                     'score': float(sc.group(1)) if sc else 0.0, 'reviews': int(rv.group(1)) if rv else 0,
                     'img': img.group(1) if img else '', 'budget': {k: v.strip() for k, v in bud}})
    m = re.search(r'([\d,]+)\s*件', html)
    return rows, (int(m.group(1).replace(',', '')) if m else None)

LAST_TB = {'rows_seen': 0, 'reported': 0}
def tabelog_paginate(fetch, base, in_town, target, max_pages=None, log=None):
    """Loop /rstLst/<p>/ pages until len(in_town) >= target, reported exhausted, or max_pages (60).
    base = 'https://tabelog.com/<pref>/<code>/'. in_town(row)->bool keeps the strict area filter.
    Returns (items, reported, pages_fetched, rows_seen)."""
    max_pages = max_pages or env_int('BJ_TABELOG_MAX_PAGES', 60)
    items, seen, reported, pages, rows_seen = [], set(), None, 0, 0
    for pg in range(1, max_pages + 1):
        html = fetch(base + 'rstLst/' + (f'{pg}/' if pg > 1 else '') + '?SrtT=rt')
        pages += 1
        if not html: break
        rows, rep = parse_tabelog_list(html)
        if reported is None: reported = rep
        new = [r for r in rows if r['rid'] not in seen]
        if not new: break
        for r in new:
            seen.add(r['rid']); rows_seen += 1
            if in_town(r): items.append(r)
        if len(items) >= target and not collect_all(): break
        if reported and rows_seen >= reported: break
        if pg * 20 >= 1200: break  # Tabelog never serves beyond 60 pages
    LAST_TB['rows_seen'] += rows_seen; LAST_TB['reported'] += reported or 0
    if log: log(f'tabelog {base} pages={pages} rows={rows_seen} in_town={len(items)} reported={reported} target={target}')
    return items, reported, pages, rows_seen

def tabelog_collect(fetch, pref, code, in_town, target, log=None):
    """P2: C-code list first; when the C-code list is dominated by neighbours (<50% in town) and short,
    iterate the town's own sub-areas (A-codes seen on in-town rows)."""
    items, reported, pages, seen = tabelog_paginate(fetch, f'https://tabelog.com/{pref}/{code}/', in_town, target, log=log)
    if (len(items) < target or collect_all()) and seen and len(items) / seen < 0.5:
        have = {r['rid'] for r in items}
        areas = list(dict.fromkeys(f"{r['a1']}/{r['a2']}" for r in items))
        for a in areas:
            more, _, _, _ = tabelog_paginate(fetch, f'https://tabelog.com/{pref}/{a}/', in_town, target - len(items), log=log)
            for r in more:
                if r['rid'] not in have: have.add(r['rid']); items.append(r)
            if len(items) >= target: break
    items.sort(key=lambda r: (-r['score'], -r['reviews']))
    for i, r in enumerate(items): r['tabelog_rank'] = i + 1
    return (items if collect_all() else items[:target]), reported

_TB_EN = None
def tabelog_en_name(fetch, url):
    """P7: official English name from tabelog.com/en (title 'Gafuu An - Itami/Ramen | Tabelog')."""
    global _TB_EN
    if os.environ.get('BJ_TABELOG_EN', '1') == '0' or not url: return ''
    f = HERE / 'data' / 'tabelog_en.json'
    if _TB_EN is None:
        _TB_EN = json.load(open(f)) if f.exists() else {}
    if url in _TB_EN: return _TB_EN[url]
    t = fetch(url.replace('https://tabelog.com/', 'https://tabelog.com/en/'))
    m = re.search(r'<title>(.*?) - [^<]*\| Tabelog', t or '')
    en = H.unescape(m.group(1)).strip() if m else ''
    if en and (CJK.search(en) or len(en) > 70): en = ''
    _TB_EN[url] = en
    f.parent.mkdir(exist_ok=True); json.dump(_TB_EN, open(f, 'w'), ensure_ascii=False, indent=0)
    return en

# ---------------------------------------------------------------- P4 Jalan
def jalan_hotels(html):
    out = []
    for m in re.finditer(r'<script type="application/ld\+json">\s*(\[.*?\])\s*</script>', html or '', re.S):
        try: data = json.loads(m.group(1))
        except Exception: continue
        out += [el for el in data if isinstance(el, dict) and el.get('@type') == 'Hotel']
    return out

def jalan_paginate(fetch, url, max_idx=None, log=None):
    """P4 (ported from kyushu-uplift/jalan_area.py): follow ?idx=0,30,60… until no new hotels."""
    max_idx = max_idx or env_int('BJ_JALAN_MAX_IDX', 3000)
    out, seen, pages = [], set(), 0
    for idx in range(0, max_idx, 30):
        t = fetch(url + (f'?idx={idx}' if idx else ''))
        pages += 1
        new = [el for el in jalan_hotels(t) if el.get('url') not in seen]
        if not new: break
        for el in new: seen.add(el.get('url')); out.append(el)
    if log: log(f'jalan {url} pages={pages} hotels={len(out)}')
    return out

def jalan_in_town(el, muni_ja, pref_ja=None, match=None):
    """P4 address filter: locality must match the town; an empty locality passes only when the street address does."""
    a = el.get('address') or {}
    if pref_ja and a.get('addressRegion') and a.get('addressRegion') != pref_ja: return False
    loc, street = (a.get('addressLocality') or '').strip(), (a.get('streetAddress') or '').strip()
    match = match or (lambda s, n: s.replace(' ', '').replace('\u3000', '').startswith(n) or bool(re.match(r'^(?:[^\d市]{1,4}?|高市)郡' + re.escape(n), s)))
    if loc: return match(loc, muni_ja)
    return bool(street) and (muni_ja in street) and match(street[street.find(muni_ja) - 4 if street.find(muni_ja) >= 4 else 0:], muni_ja) or (bool(street) and street.startswith(muni_ja))

def jalan_photo(fetch, yad_url, enc='cp932'):
    """P5: facility photo (og:image = exterior, gallery index 0) upgraded to pict2L (600 px). Returns (url, alt)."""
    t = fetch(yad_url, enc=enc) if 'enc' in fetch.__code__.co_varnames else fetch(yad_url)
    m = re.search(r'og:image" content="([^"]+)"', t or '')
    if not m: return '', ''
    u = m.group(1); fn = u.rsplit('/', 1)[-1]
    alt = re.search(re.escape(fn) + r'" alt="([^"]*)"', t)
    return re.sub(r'/images/pict[^/]*/', '/images/pict2L/', u), (alt.group(1) if alt else '')

def jalan_big(u): return re.sub(r'/images/pict[^/]*/', '/images/pict2L/', u or '') if 'cdn.jalan.jp' in (u or '') else u

# ---------------------------------------------------------------- P4 Ikkyu
IKKYU_PREF = {'ibaraki': 'kanto/130406', 'chiba': 'kanto/pr12', 'tottori': 'chugoku/330830', 'shimane': 'chugoku/330840', 'miyazaki': 'kyushu/350903',
              'kagoshima': 'kyushu/350904', 'kumamoto': 'kyushu/350905', 'shiga': 'kansai/320704', 'nara': 'kansai/320705', 'wakayama': 'kansai/320706',
              'gifu': 'tokai/230601', 'aichi': 'tokai/230603', 'mie': 'tokai/230604', 'shizuoka': 'tokai/230612', 'toyama': 'hokuriku/220553',
              'ishikawa': 'hokuriku/220554', 'fukui': 'hokuriku/220556', 'kagawa': 'shikoku/340870', 'kochi': 'shikoku/340890', 'ehime': 'shikoku/340880',
              'tokushima': 'shikoku/340860', 'okayama': 'chugoku/330810', 'hiroshima': 'chugoku/330820', 'hyogo': 'kansai/320707',
              'fukushima': 'tohoku/120260', 'niigata': 'koshinetsu/210551'}

def ikkyu_pool(fetch, pref, cache_file, area=None, max_pages=80, log=None):
    """P4: real Ikkyu collector. Pref list pages (/<region>/<code>/pN/, Ikkyu recommended order) -> facility pages
    (name, JSON-LD addressRegion/Locality, og:image, description, official EN alternateName if any).
    Cached in cache_file; returns {'status', 'items'}; status=BLOCKED_403 when Ikkyu refuses the box (no silent empty)."""
    cache_file = Path(cache_file)
    if cache_file.exists():
        pool = json.load(open(cache_file))
        return {'status': 'cached', 'items': pool}
    area = area or IKKYU_PREF.get(pref)
    if not area: return {'status': 'NO_AREA_CODE', 'items': []}
    ids, first = [], None
    for p in range(1, max_pages + 1):
        t = fetch(f'https://www.ikyu.com/{area}/' + (f'p{p}/' if p > 1 else ''))
        if first is None: first = bool(t)
        got = [x for x in dict.fromkeys(re.findall(r'href="(?:https://www\.ikyu\.com)?/(\d{8})/', t or '')) if x not in ids]
        if not got: break
        ids.extend(got)
    if not ids:
        if log: log(f'ikkyu {pref} BLOCKED or empty list ({area})')
        return {'status': 'BLOCKED_403' if not first else 'EMPTY', 'items': []}
    pool = []
    for i, x in enumerate(ids):
        t = fetch(f'https://www.ikyu.com/{x}/')
        nm = re.search(r'<title>(.*?) - 宿泊予約', t or ''); loc = re.search(r'"addressLocality":"([^"]+)"', t or '')
        reg = re.search(r'"addressRegion":"([^"]+)"', t or ''); st = re.search(r'"streetAddress":"([^"]+)"', t or '')
        og = re.search(r'og:image" content="([^"]+)"', t or ''); ds = re.search(r'name="description" content="([^"]*)"', t or '')
        alt = re.search(r'"alternateName":"([^"]+)"', t or '')
        gal = re.findall(r'(https://www\.img-ikyu\.com/contents/dg/guide/[^"\s]+?/img/[^"\s]+?\.jpg)', t or '')
        if nm and loc:
            pool.append({'ikkyu_url': f'https://www.ikyu.com/{x}/', 'name_ja': H.unescape(nm.group(1)), 'region': reg.group(1) if reg else '',
                         'loc': loc.group(1), 'street': st.group(1) if st else '', 'img': H.unescape(og.group(1)) if og else '',
                         'gallery': list(dict.fromkeys(gal))[:6], 'name_en_official': (alt.group(1) if alt and not CJK.search(alt.group(1)) else ''),
                         'desc': H.unescape(ds.group(1)) if ds else '', 'order': i})
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    json.dump(pool, open(cache_file, 'w'), ensure_ascii=False, indent=1)
    if log: log(f'ikkyu {pref} ids={len(ids)} facilities={len(pool)}')
    return {'status': 'ok', 'items': pool}

# ---------------------------------------------------------------- P5 photo gate
FOOD_ALT = re.compile(r'料理|夕食|朝食|夕餉|会席|懐石|御膳|膳|食事|ディナー|ランチ|ビュッフェ|バイキング|朝ごはん|一例|プラン|特典|キャンペーン|ドリンク|ポイント|受賞|No\.?1|アワード|クーポン')
PROMO_URL = re.compile(r'banner|campaign|/plan/|coupon|award', re.I)
_J = None
def _judge():
    global _J
    if _J is False: return None
    if _J is None:
        py = '/home/box/venvs/bjclip/bin/python'
        if os.environ.get('BJ_PHOTO_JUDGE', '1') == '0' or not os.path.exists(py): _J = False; return None
        _J = subprocess.Popen([py, str(HERE / 'photo_judge.py')], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        _J.stdout.readline()
    return _J

def judge(path):
    j = _judge()
    if not j: return None
    j.stdin.write(str(path) + '\n'); j.stdin.flush()
    try: return json.loads(j.stdout.readline())
    except Exception: return None

def photo_gate(path, kind='stay', url='', alt='', raw_bytes=None, raw_w=None):
    """P5 gate. Returns None when OK, else a reject reason. Applies to the *downloaded source* (raw_bytes/raw_w)
    and the stored file: any image < BJ_MIN_IMG_BYTES (5 KB) is rejected; Stay photos must be >= BJ_STAY_MIN_W (560 px)
    wide at source, must not carry a food/promo alt text or URL, and must pass the CLIP judge (food/promo/pet/people)."""
    minb = env_int('BJ_MIN_IMG_BYTES', 5120)
    p = Path(path)
    size = raw_bytes if raw_bytes is not None else (p.stat().st_size if p.exists() else 0)
    if size < minb: return f'tiny<{minb}B'
    if kind != 'stay': return None
    if raw_w is None:
        try:
            from PIL import Image
            raw_w = Image.open(p).size[0]
        except Exception: return 'undecodable'
    if raw_w < env_int('BJ_STAY_MIN_W', 560): return f'narrow<{env_int("BJ_STAY_MIN_W", 560)}px'
    if alt and FOOD_ALT.search(alt) and not re.search(r'外観|客室|部屋|ロビー|外景|エントランス|玄関|露天|大浴場|館内', alt): return 'food/promo-alt'
    if url and PROMO_URL.search(url): return 'promo-url'
    v = judge(p)
    if v and v.get('reject'): return f"judge:{v['reject']}:{v.get('label','')}"
    return None

def log_reject(csv_path, town, name, url, reason):
    import csv
    new = not Path(csv_path).exists()
    with open(csv_path, 'a', newline='') as f:
        w = csv.writer(f)
        if new: w.writerow(['town', 'name', 'url', 'reason'])
        w.writerow([town, name, url, reason])

# ---------------------------------------------------------------- P6 neighbour stays
PREF_RX = r'^(北海道|青森県|岩手県|宮城県|秋田県|山形県|福島県|茨城県|栃木県|群馬県|埼玉県|千葉県|東京都|神奈川県|新潟県|富山県|石川県|福井県|山梨県|長野県|岐阜県|静岡県|愛知県|三重県|滋賀県|京都府|大阪府|兵庫県|奈良県|和歌山県|鳥取県|島根県|岡山県|広島県|山口県|徳島県|香川県|愛媛県|高知県|福岡県|佐賀県|長崎県|熊本県|大分県|宮崎県|鹿児島県|沖縄県)'
VARIANT = str.maketrans({'檮': '梼', '﨑': '崎', '澤': '沢', 'ヶ': 'ケ', 'ヵ': 'カ'})
def locality_town(addr, pref_ja=''):
    a = (addr or '').replace(' ', '').replace('\u3000', '')
    if pref_ja and a.startswith(pref_ja): a = a[len(pref_ja):]
    else: a = re.sub(PREF_RX, '', a)
    a = re.sub(r'^(?:[^\d市町村]{1,5}?|高市)郡', '', a)
    m = re.match(r'(.{1,6}?市|.{1,5}?[町村])', a)
    return m.group(1) if m else ''

def neighbour_of(addr, muni_ja, pref_ja=''):
    """'' when the stay is in this town, else the Japanese municipality name it is in."""
    a = (addr or '').replace(' ', '').replace('\u3000', '')
    if pref_ja and a.startswith(pref_ja): a = a[len(pref_ja):]
    else: a = re.sub(PREF_RX, '', a)
    a = a.translate(VARIANT); muni_ja = muni_ja.translate(VARIANT)
    if not a or a.startswith(muni_ja) or re.match(r'^(?:[^\d市]{1,4}?|高市)郡' + re.escape(muni_ja), a): return ''
    if muni_ja.endswith('市') and re.match(re.escape(muni_ja[:-1]) + r'市', a): return ''
    return locality_town(a) or ''

def neighbour_label(town_en): return f'In neighbouring {town_en}'
def stays_near(town_en): return f'Stays near {town_en}'

# ---------------------------------------------------------------- P7 romaji
DICT_FILE = HERE / 'romaji_dict.json'
_D = None
def rdict():
    global _D
    if _D is None: _D = json.load(open(DICT_FILE)) if DICT_FILE.exists() else {'exact': {}, 'words': {}}
    return _D

def expand_odoriji(s):
    out = []
    for ch in s:
        if ch == '々' and out: out.append(out[-1])
        elif ch in 'ゝヽ' and out: out.append(out[-1])
        elif ch in 'ゞヾ' and out:
            p = out[-1]; v = unicodedata.normalize('NFC', p + '\u3099'); out.append(v if len(v) == 1 else p)
        else: out.append(ch)
    return ''.join(out).replace('\u309b', '').replace('\u3099', '').replace('゙', '')

_K = None
def _kk():
    global _K
    if _K is None:
        try:
            import pykakasi; _K = pykakasi.kakasi()
        except Exception: _K = False
    return _K

KATA_EN = [('ホテルズ','Hotels'),('リゾーツ','Resorts'),('ルートイン','Route Inn'),('東横イン','Toyoko Inn'),('ドーミーイン','Dormy Inn'),('コンフォートホテル','Comfort Hotel'),
           ('スーパーホテル','Super Hotel'),('アパホテル','APA Hotel'),('グランド','Grand'),('ホテル','Hotel'),('リゾート','Resort'),('ペンション','Pension'),('ゲストハウス','Guesthouse'),
           ('ロッジ','Lodge'),('コテージ','Cottage'),('ヴィラ','Villa'),('ビジネス','Business'),('シティ','City'),('パーク','Park'),('プラザ','Plaza'),('ガーデン','Garden'),
           ('テラス','Terrace'),('ハウス','House'),('ステーション','Station'),('センター','Center'),('カフェ','Cafe'),('ダイニング','Dining'),('キッチン','Kitchen'),
           ('レストラン','Restaurant'),('ベーカリー','Bakery'),('ピッツェリア','Pizzeria'),('トラットリア','Trattoria'),('ビストロ','Bistro'),('ステーキ','Steak'),
           ('ハンバーグ','Hamburg'),('バーガー','Burger'),('ピザ','Pizza'),('パスタ','Pasta'),('スイーツ','Sweets'),('ワイン','Wine'),('ビール','Beer'),('コーヒー','Coffee'),
           ('イン','Inn'),('バー','Bar'),('パン','Bakery')]
def _script(ch):
    if re.match(r'[\u30a0-\u30ff]', ch): return 'K'
    if re.match(r'[\u3040-\u309f\u3400-\u9fff々]', ch): return 'J'
    return 'L'

def _rom_chunk(ja):
    """pykakasi without space-splitting inside one word: a kanji+hiragana run is one word, katakana runs are loanwords
    (dictionary first), Hepburn long vowels collapsed (Taishou -> Taisho)."""
    k = _kk()
    if not k: return ja
    runs, cur, cs = [], '', None
    for ch in ja:
        sc = _script(ch)
        if cs is not None and sc != cs: runs.append((cs, cur)); cur = ''
        cur += ch; cs = sc
    if cur: runs.append((cs, cur))
    out = []
    for sc, r in runs:
        if sc == 'L': out.append(r); continue
        if sc == 'K':
            for kk, v in KATA_EN:
                if r == kk: out.append(v); break
            else:
                hit = [(kk, v) for kk, v in KATA_EN if kk in r]
                if hit:
                    t = r
                    for kk, v in hit: t = t.replace(kk, f' {v} ')
                    out += [(_kana_rom(x) if CJK.search(x) else x) for x in t.split()]
                else: out.append(_kana_rom(r))
            continue
        w = ''.join((p.get('hepburn') or '') for p in k.convert(r)).replace("'", '')
        w = re.sub(r'ou', 'o', w); w = re.sub(r'([aiue])\1', r'\1', w); w = re.sub(r'oo(?!$)', 'o', w)
        out.append(w[:1].upper() + w[1:])
    return ' '.join(x for x in out if x)

def _kana_rom(r):
    w = ''.join((p.get('hepburn') or '') for p in _kk().convert(r))
    w = re.sub(r'(aa|ii|uu|ee|oo)', lambda m: m.group(0)[0], w)
    return w[:1].upper() + w[1:]

def romanize_name(ja, official_en=None):
    """P7 source order: official EN (Tabelog EN / Ikkyu alternateName / Jalan EN) -> exact dictionary ->
    word dictionary (本店→Main Store, 〜屋→-ya, 麺や→Menya, …) + pykakasi per word -> never kana debris."""
    if official_en and not CJK.search(official_en): return re.sub(r'\s+', ' ', official_en).strip()
    if not ja: return ''
    s = unicodedata.normalize('NFKC', expand_odoriji(ja)).strip()
    s = re.sub(r'([ぁ-ん])[ぁぃぅぇぉ]?[ー～〜~－-]+(?=[ぁ-ん一-龥]|$)', lambda m: m.group(1), s)  # らぁーめん / ら～めん -> らめん (long vowel)
    s = s.translate(str.maketrans('ぁぃぅぇぉ', 'あいうえお'))
    D = rdict()
    if s in D['exact']: return D['exact'][s]
    suf = ''
    for k, v in D.get('suffix', {}).items():
        if s.endswith(k) and len(s) > len(k): s, suf = s[:-len(k)].strip(), ' ' + v; break
    pre = ''
    for k, v in D.get('prefix', {}).items():
        if s.startswith(k) and len(s) > len(k): s, pre = s[len(k):].strip(), v + ' '; break
    words = []
    for w in re.split(r'[\s・/／]+', s):
        if not w: continue
        if w in D['exact']: words.append(D['exact'][w]); continue
        parts, i = [], 0
        keys = sorted(D['words'], key=len, reverse=True)
        buf = ''
        while i < len(w):
            hit = next((k for k in keys if w.startswith(k, i)), None)
            if hit:
                if buf: parts.append(_rom_chunk(buf)); buf = ''
                parts.append(D['words'][hit]); i += len(hit)
            else: buf += w[i]; i += 1
        if buf: parts.append(_rom_chunk(buf))
        tok = ''
        for p in parts:
            if p.startswith('-'): tok += p
            elif p.startswith('~'): tok += p[1:]
            else: tok += (' ' if tok else '') + p
        words.append(tok)
    out = pre + ' '.join(words) + suf
    out = re.sub(r'\s+', ' ', out).strip()
    out = ' '.join(x if (x.isupper() and len(x) > 1) or not x[:1].islower() or (i and x in ('no', 'to', 'ga', 'de')) else x[:1].upper() + x[1:] for i, x in enumerate(out.split(' ')))
    out = re.sub(r'[\u3040-\u30ff\u309b\u3099゙ゞゝ]', '', out).strip()
    return out if out and not CJK.search(out) else ''

ROUGH = [re.compile(p) for p in (r'\b(Men|Ya|Ga|No|Wo|Ni|Ha|Wa|O|Sho|Hon) [A-Z]', r'\b[A-Z][a-z]? [A-Z][a-z]? [A-Z]', r'[\u3040-\u30ff゙ゞゝ]', r'\bHon-ya\b', r'-ya [A-Z][a-z]?-')]
def rough_romaji(en):
    """P10 R4 heuristic: pykakasi split artefacts / kana debris."""
    return bool(en) and any(r.search(en) for r in ROUGH)

# ---------------------------------------------------------------- P8 title cleanup
SEO = re.compile(r'【[^】]*】|\[[^\]]*\]|《[^》]*》')
SITEWORDS = re.compile(r'(公式(ホームページ|サイト|HP|ウェブサイト)?|オフィシャル(サイト)?|ホームページ|観光協会|観光(情報|ガイド|ナビ)|トップページ|TOP|HOME|Home|Official (Web)?site|website)', re.I)
def clean_title(t, h1=None, og_title=None, town_ja=None):
    """P8: page <title> -> place name. Split on ｜|»【】-– and site names; prefer the h1/og:title when the
    title is clearly an SEO string. Returns the cleaned name."""
    cand = [x for x in (h1, og_title, t) if x]
    for raw in cand:
        s = H.unescape(raw).strip()
        s = SEO.sub(' ', s)
        s = re.sub(r'(公式)?(サイト|ホームページ|HP)「[^」]*」', '', s)
        s = re.sub(r'[\s\u3000]*\S*?(公式サイト|公式ホームページ|ホームページ|公式HP)$', '', s).strip() or s
        parts = [p.strip(' 　「」『』"\'') for p in re.split(r'\s*[｜|»«>＞\u3000]\s*|\s+[-–—:：]\s+|\s*[–—]\s*', s) if p.strip()]
        parts = [p for p in parts if not SITEWORDS.fullmatch(p) and not re.search(r'(公式|オフィシャル)(サイト|ホームページ|HP)|観光協会|市役所|町役場|村役場|ホームページ|Official Site|\.(com|jp)$', p, re.I)]
        parts = [re.sub(r'^(HOME|TOP|ホーム)\s*[-–]?\s*', '', p, flags=re.I) for p in parts]
        parts = [p for p in parts if p and not (town_ja and p == town_ja)]
        if not parts: continue
        # the place name is usually the most specific (shortest non-generic) segment; prefer the last '»' crumb
        if '»' in s: return parts[-1]
        return min(parts, key=len) if len(parts) > 1 and min(len(p) for p in parts) >= 2 else parts[0]
    return (t or '').strip()

def title_as_name(name):
    """P10 X12: name still looks like a scraped page title."""
    return bool(re.search(r'[｜|»【】]|公式(サイト|ホームページ|HP)|観光協会|HOME\s*[-–]|ホームページ|Official (Web)?site', name or '', re.I))

# ---------------------------------------------------------------- P9 dining descriptions
GENRE_EN = {'ラーメン': 'Ramen shop', 'つけ麺': 'Tsukemen shop', 'そば': 'Soba restaurant', 'うどん': 'Udon restaurant', '寿司': 'Sushi bar', '回転寿司': 'Conveyor-belt sushi',
            '焼肉': 'Yakiniku (grilled meat) restaurant', '焼き鳥': 'Yakitori bar', '焼鳥': 'Yakitori bar', '居酒屋': 'Izakaya', 'カフェ': 'Café', '喫茶店': 'Coffee house',
            'パン': 'Bakery', 'ケーキ': 'Cake shop', 'スイーツ': 'Sweets shop', '和菓子': 'Japanese sweets shop', 'イタリアン': 'Italian restaurant', 'フレンチ': 'French restaurant',
            'フランス料理': 'French restaurant', 'イタリア料理': 'Italian restaurant', 'ピザ': 'Pizzeria', 'パスタ': 'Pasta restaurant', '中華料理': 'Chinese restaurant',
            '餃子': 'Gyoza restaurant', '四川料理': 'Sichuan restaurant', '韓国料理': 'Korean restaurant', 'タイ料理': 'Thai restaurant', 'インド料理': 'Indian restaurant',
            'カレー': 'Curry restaurant', 'ハンバーガー': 'Burger joint', 'ハンバーグ': 'Hamburg-steak restaurant', 'ステーキ': 'Steakhouse', '洋食': 'Yoshoku (Western-style) restaurant',
            '和食': 'Japanese restaurant', '日本料理': 'Japanese restaurant', '懐石・会席料理': 'Kaiseki restaurant', '割烹・小料理': 'Kappo restaurant', '天ぷら': 'Tempura restaurant',
            'とんかつ': 'Tonkatsu restaurant', 'うなぎ': 'Eel (unagi) restaurant', '鍋': 'Hot-pot restaurant', 'もつ鍋': 'Motsunabe restaurant', 'しゃぶしゃぶ': 'Shabu-shabu restaurant',
            'すき焼き': 'Sukiyaki restaurant', 'お好み焼き': 'Okonomiyaki restaurant', 'たこ焼き': 'Takoyaki stand', '鉄板焼き': 'Teppanyaki restaurant', '串揚げ': 'Kushiage bar',
            '串カツ': 'Kushikatsu bar', '海鮮': 'Seafood restaurant', '魚介料理・海鮮料理': 'Seafood restaurant', '定食・食堂': 'Set-meal diner', '食堂': 'Diner', '定食': 'Set-meal diner',
            'バー': 'Bar', 'ダイニングバー': 'Dining bar', 'ビストロ': 'Bistro', 'スペイン料理': 'Spanish restaurant', 'ベトナム料理': 'Vietnamese restaurant', '丼': 'Rice-bowl (donburi) shop',
            '牛丼': 'Gyudon shop', '弁当': 'Bento shop', 'ジェラート・アイスクリーム': 'Gelato shop', 'アイスクリーム': 'Ice-cream shop', 'ドーナツ': 'Doughnut shop', '甘味処': 'Japanese sweets café',
            'ちゃんぽん': 'Champon noodle shop', '担々麺': 'Dandan noodle shop', '油そば・まぜそば': 'Mazesoba shop', 'ホルモン': 'Horumon grill', 'ジンギスカン': 'Genghis Khan lamb grill',
            'レストラン': 'Restaurant', 'ファミレス': 'Family restaurant', '創作料理': 'Creative cuisine restaurant', '郷土料理': 'Local-cuisine restaurant', 'ビアガーデン': 'Beer garden',
            '日本酒バー': 'Sake bar', 'ワインバー': 'Wine bar', 'たい焼き・大判焼き': 'Taiyaki stand', 'クレープ': 'Crêpe stand', 'サンドイッチ': 'Sandwich shop', '洋菓子': 'Patisserie'}
def genre_en(g):
    g = (g or '').split('、')[0].strip()
    return GENRE_EN.get(g) or next((v for k, v in GENRE_EN.items() if k in g), 'Restaurant')

def station_en(area_ja, romanize=None):
    m = re.match(r'(.+?)駅\s*([\d.,]+\s*k?m)', area_ja or '')
    if not m: return ''
    nm = m.group(1); line = re.search(r'[（(]([^）)]+)[）)]', nm); base = re.sub(r'[（(][^）)]*[）)]', '', nm)
    r = romanize or romanize_name
    en = r(base)
    if not en: return ''
    lin = {'阪急': 'Hankyu', 'JR': 'JR', '阪神': 'Hanshin', '近鉄': 'Kintetsu', '京阪': 'Keihan', '南海': 'Nankai', '名鉄': 'Meitetsu', '能勢電鉄': 'Nose Electric',
           '西鉄': 'Nishitetsu', '東急': 'Tokyu', '京急': 'Keikyu', '小田急': 'Odakyu', '京王': 'Keio', '西武': 'Seibu', '東武': 'Tobu', '市営地下鉄': 'subway',
           '地下鉄': 'subway', '山陽': 'Sanyo', '神戸電鉄': 'Kobe Electric', '伊予鉄': 'Iyotetsu', 'とさでん': 'Tosaden'}.get(line.group(1) if line else '', '')
    dist = m.group(2).replace(' ', '').replace(',', '')
    return f'{dist.replace("km", " km").replace("m", " m") if "km" not in dist else dist.replace("km", " km")} from {en} Station' + (f' ({lin})' if lin else '')

def dining_desc(row, town_en):
    """P9: sourced English line from Tabelog list data only: genre, nearest station + distance, budget, rating.
    e.g. 'Ramen shop 279 m from Itami Station (Hankyu), Itami; dinner ¥1,000–¥1,999. Tabelog 3.69 (1,070 reviews).'"""
    g = genre_en(row.get('genre') or row.get('genre_ja'))
    st = station_en(row.get('area_ja', ''))
    s = g + (f' {st}' if st else f' in {town_en}')
    if st: s += f', {town_en}'
    b = (row.get('budget') or {})
    bud = b.get('夜') or b.get('昼')
    if bud and re.search(r'\d', bud):
        bud = bud.replace('～', '–').replace('〜', '–').replace('￥', '¥')
        s += f"; {'dinner' if b.get('夜') else 'lunch'} {bud}"
    s += '.'
    if row.get('score'): s += f" Tabelog {row['score']:.2f}" + (f" ({row['reviews']:,} reviews)" if row.get('reviews') else '') + '.'
    return s

# ---------------------------------------------------------------- progress log
def progress(msg, path='/tmp/bjleo/shared-fixes-progress.txt'):
    import time
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'a') as f: f.write(time.strftime('%F %T JST ') + msg + '\n')

# ---------------------------------------------------------------- photo search cascade (standing bar)
PHOTO_SOURCES = ['source', 'official', 'google_places', 'tabelog', 'jalan', 'rakuten', 'ikkyu', 'tripadvisor', 'wikimedia', 'tourism']
def wikimedia_photo(query, fetch_json=None):
    """Wikimedia Commons file search (public API). Returns (url, credit) or ('', '')."""
    import urllib.parse, urllib.request
    u = ('https://commons.wikimedia.org/w/api.php?action=query&format=json&generator=search&gsrnamespace=6&gsrlimit=3&prop=imageinfo'
         '&iiprop=url|extmetadata&iiurlwidth=800&gsrsearch=' + urllib.parse.quote(query))
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers={'User-Agent': 'BokenJapanBot/1.0 (bokenjapan.com)'}), timeout=20).read())
    except Exception: return '', ''
    for p in (d.get('query') or {}).get('pages', {}).values():
        ii = (p.get('imageinfo') or [{}])[0]
        if ii.get('thumburl') and re.search(r'\.(jpe?g|png|webp)$', ii.get('url', ''), re.I):
            lic = ((ii.get('extmetadata') or {}).get('LicenseShortName') or {}).get('value', '')
            return ii['thumburl'], f"Wikimedia Commons · {lic} · {ii.get('descriptionurl', '')}"
    return '', ''

def og_image(fetch, url):
    t = fetch(url) if url else ''
    m = re.search(r'property="og:image"\s+content="([^"]+)"|content="([^"]+)"\s+property="og:image"', t or '')
    return H.unescape(m.group(1) or m.group(2)) if m else ''

def _f_enc(f, u, enc):
    try: return f(u, enc=enc)
    except TypeError: return f(u)

def photo_search(card, try_fn, fetch=None, kind='stay'):
    """Walk the sources in PHOTO_SOURCES order; try_fn(url, alt) -> photo tuple or None (applies the P5 gate).
    Returns (photo, record) where record = {'tried': [...], 'result': src|None, 'notes': {...}} -> stored as card['photo_search']."""
    rec = {'tried': [], 'result': None, 'notes': {}}
    def go(src, url, alt=''):
        rec['tried'].append(src)
        if not url: rec['notes'][src] = 'no-candidate'; return None
        ph = try_fn(url, alt)
        if ph: rec['result'] = src
        else: rec['notes'][src] = 'rejected-or-failed'
        return ph
    f = fetch or (lambda u: '')
    steps = [('source', lambda: (card.get('img'), card.get('img_alt', ''))),
             ('official', lambda: (og_image(f, card.get('official_url')), '')),
             ('google_places', lambda: ('', '')),  # needs a Places API key (BJ_GOOGLE_PLACES_KEY); recorded as tried
             ('tabelog', lambda: (og_image(f, card.get('tabelog_url')) if kind != 'stay' else '', '')),
             ('jalan', lambda: jalan_photo(lambda u, enc='cp932': _f_enc(f, u, 'cp932'), card['jalan_url']) if card.get('jalan_url') else ('', '')),
             ('rakuten', lambda: (og_image(f, card.get('rakuten_url')), '')),
             ('ikkyu', lambda: (og_image(f, card.get('ikkyu_url')), '')),
             ('tripadvisor', lambda: (og_image(f, card.get('ta_url')), '')),
             ('wikimedia', lambda: wikimedia_photo(card.get('name_ja') or card.get('name_en', ''))[0:1] + ('',)),
             ('tourism', lambda: (og_image(f, card.get('tourism_url')), ''))]
    for src, get in steps:
        if src == 'google_places' and not os.environ.get('BJ_GOOGLE_PLACES_KEY'):
            rec['tried'].append(src); rec['notes'][src] = 'no-api-key'; continue
        try: url, alt = get()
        except Exception as e: url, alt = '', ''; rec['notes'][src] = f'error:{str(e)[:60]}'
        ph = go(src, url, alt)
        if ph: return ph, rec
    return None, rec
