#!/usr/bin/env python3
"""Usage: fn_build.py <pref> <pref_ja> collect|render [slugs...]"""
import json, re, sys, os, math, shutil, html as H
from pathlib import Path
sys.path.insert(0, '/workspace/p1/partials-build')
from fn_lib import *
sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as S  # AUDIT-47 shared fixes P1-P9
pref, pref_ja, mode = sys.argv[1], sys.argv[2], sys.argv[3]
only = sys.argv[4:]
WT = Path(os.environ.get('FN_WT') or f'/workspace/p1/wt-{pref}')
HUBF = Path(f'/workspace/p1/fn-uplift/hubs/{pref}-hub-codes.json')
DATA = Path(os.environ.get('BJ_DATA_DIR') or '/workspace/p1/partials-build/data') / pref; DATA.mkdir(parents=True, exist_ok=True)
meta = json.load(open(HUBF)); hubs = meta['hubs']
if os.environ.get('BJ_CACHE_ONLY'):  # resilience: never hit the network (use when a source blocks the box)
    _fetch_net = fetch
    def fetch(url, enc='utf-8', **kw):
        key = re.sub(r'[^A-Za-z0-9]+', '_', url)[:180]; f = CACHE / key
        if f.exists() and f.stat().st_size > 500: return f.read_bytes().decode(enc, 'replace')
        if os.environ.get('BJ_CACHE_ONLY') == 'tabelog,ikyu' and not re.search(r'tabelog\.com|ikyu\.com', url): return _fetch_net(url, enc=enc, **kw)
        return ''
IKKYU_PREF = {'ibaraki':'kanto/130406','chiba':'kanto/pr12','tottori':'chugoku/330830','shimane':'chugoku/330840','miyazaki':'kyushu/350903','kagoshima':'kyushu/350904','kumamoto':'kyushu/350905','shiga':'kansai/320704','nara':'kansai/320705','wakayama':'kansai/320706','gifu':'tokai/230601','aichi':'tokai/230603','mie':'tokai/230604','shizuoka':'tokai/230612','toyama':'hokuriku/220553','ishikawa':'hokuriku/220554','fukui':'hokuriku/220556','kagawa':'shikoku/340870','kochi':'shikoku/340890','ehime':'shikoku/340880','tokushima':'shikoku/340860','okayama':'chugoku/330810','hiroshima':'chugoku/330820','hyogo':'kansai/320707'}
IKKYU_AREAS = {'fukushima': ['tohoku/12026001','tohoku/12026002','tohoku/12026003','tohoku/12026004','tohoku/12026005','tohoku/12026006'], 'niigata': [f'koshinetsu/2105510{i}' for i in range(1,8)], 'gunma': [f'kanto/1304030{i}' for i in range(1,7)], 'ibaraki': [f'kanto/1304060{i}' for i in range(1,6)], 'saitama': [f'kanto/1304040{i}' for i in range(1,10)]}
DCAP, SCAP = 24, 12  # legacy only (BJ_TARGET_MODE=legacy); P1 targets come from S.targets()
def slug_of(d, h):
    return h.get('slug') or (re.sub(r'[^a-z0-9]+', '', h['name_en'].lower()) if d.startswith('jis') else d)
def disk_ok():
    st = os.statvfs('/workspace/p1'); g = st.f_bavail * st.f_frsize / 2**30
    if g < 8: print('PAUSE_DISK_UNDER_8GiB', g); sys.exit(3)
def inm(a, name):
    a = (a or '').replace(' ', '').replace('\u3000', '')
    a = a[len(pref_ja):] if a.startswith(pref_ja) else a
    return a.startswith(name) or bool(re.match(r'(?:[^\d市]{1,4}?|高市)郡' + re.escape(name), a))
def jd(s): return re.sub(r'[\s\u3000・\-ー（）()]', '', s or '').lower()

def _in_town(h):
    def ok(r):
        addr = r.get('addr', '')
        return r.get('pref_tb') == pref and addr.replace(' ', '').startswith(pref_ja) and inm(addr, h['name_ja'])  # strict in-town filter kept
    return ok

def tabelog(h, target):
    """P2: paginate until in-town >= target, reported exhausted or page 60; ward cities (C..100) per ward."""
    c = h['tabelog_c']; rep_tot = 0
    if c.endswith('100'):
        allit = []
        for w in range(1, 20):
            got, rep = S.tabelog_collect(fetch, pref, c[:-3] + f'1{w:02d}', _in_town(h), target, log=print)
            if rep is None and not got: continue
            allit += got; rep_tot += rep or 0
        allit.sort(key=lambda x: (-x.get('score', 0), -x.get('reviews', 0)))
        items = allit[:target]
    else:
        items, rep_tot = S.tabelog_collect(fetch, pref, c, _in_town(h), target, log=print)
    for i, x in enumerate(items):
        x['tabelog_rank'] = i + 1
        x['name_en_official'] = S.tabelog_en_name(fetch, x['tabelog_url'])  # P7
    return items, rep_tot

IKKYU_STATUS = {}
def ikkyu_pool():
    """P4: real Ikkyu collector (bj_shared.ikkyu_pool): pref list pages -> facility pages, cached per pref."""
    r = S.ikkyu_pool(fetch, pref, DATA / '_ikkyu_pool.json', area=IKKYU_PREF.get(pref) or S.IKKYU_PREF.get(pref), log=print)
    IKKYU_STATUS['status'] = r['status']
    return r['items']

def jalan_pool():
    f = DATA / '_jalan_pool.json'
    if f.exists(): return json.load(open(f))
    pj = meta['pref_jalan']; top = fetch(f'https://www.jalan.net/{pj}/', enc='cp932'); out = []
    for l in sorted(set(re.findall(r'LRG_(\d+)/', top))):
        lt = fetch(f'https://www.jalan.net/{pj}/LRG_{l}/', enc='cp932')
        for sm in sorted(set(re.findall(r'SML_(\d+)/', lt))):
            for idx in range(0, 600, 30):
                t = fetch(f'https://www.jalan.net/{pj}/LRG_{l}/SML_{sm}/?idx={idx}', enc='cp932')
                new = 0
                for m in re.finditer(r'<script type="application/ld\+json">\s*(\[.*?\])\s*</script>', t, re.S):
                    try: data = json.loads(m.group(1))
                    except Exception: continue
                    for el in data:
                        if isinstance(el, dict) and el.get('@type') == 'Hotel' and not any(o.get('url') == el.get('url') for o in out):
                            out.append(el); new += 1
                if not new: break
    json.dump(out, open(f, 'w'), ensure_ascii=False)
    print('jalan pool', len(out), flush=True)
    return out

def jalan(h):
    """P4: pref pool (LRG/SML ?idx= pagination) + the town's CTY page with full ?idx= pagination;
    address filter enforced (empty locality passes only when the street address matches)."""
    els = list(jalan_pool())
    if h.get('jalan_cty'):
        els = S.jalan_paginate(lambda u: fetch(u, enc='cp932'), f'https://www.jalan.net/{meta["pref_jalan"]}/{h["jalan_cty"]}/', log=print) + els
    out = []
    for el in els:
        if not S.jalan_in_town(el, h['name_ja'], pref_ja, match=lambda s_, n: inm(s_, n)): continue
        if any(o['jalan_url'] == el.get('url') for o in out): continue
        a = el.get('address') or {}
        out.append({'name_ja': el.get('name', ''), 'jalan_url': el.get('url', ''), 'img': el.get('image', ''),
                    'addr': (a.get('addressLocality') or '') + (a.get('streetAddress') or ''), 'desc': el.get('description', '')})
    return out

def stay_photo(e):
    """P5: facility photo over plan image. Jalan: yad page og:image (= gallery 0, exterior) at pict2L/600px; Ikkyu: og:image."""
    if e.get('img_src') == 'jalan' or (not e.get('img') and e.get('jalan_url')):
        u, alt = S.jalan_photo(lambda x, enc='cp932': fetch(x, enc='cp932'), e['jalan_url'])
        if u: e['img'], e['img_alt'], e['img_src'], e['img_kind'] = u, alt, 'jalan', 'facility'
        else: e['img'] = S.jalan_big(e.get('img'))
    return e

def collect(d, h):
    disk_ok()
    pool = ikkyu_pool()
    ik = [dict(p, addr=p['loc']) for p in pool if p['region'] == pref_ja and inm(p['loc'], h['name_ja'])]
    ik.sort(key=lambda p: p['order'])
    jl = jalan(h)
    stay = []
    for p in ik:
        e = {'name_ja': p['name_ja'], 'ikkyu_url': p['ikkyu_url'], 'img': p['img'], 'img_src': 'ikkyu', 'addr': p['addr'], 'desc_ja': p['desc'], 'name_en_official': p.get('name_en_official', '')}
        for j in jl:
            if jd(j['name_ja']) == jd(p['name_ja']) or (len(jd(p['name_ja'])) > 4 and jd(p['name_ja']) in jd(j['name_ja'])):
                e['jalan_url'] = j['jalan_url']; e['desc_ja'] = j['desc'] or e['desc_ja']; j['_used'] = 1
        stay.append(e)
    for j in jl:
        if j.get('_used') or any(jd(s['name_ja']) == jd(j['name_ja']) for s in stay): continue
        stay.append({'name_ja': j['name_ja'], 'jalan_url': j['jalan_url'], 'img': j['img'], 'img_src': 'jalan', 'addr': j['addr'], 'desc_ja': j['desc']})
    S.LAST_TB.update(rows_seen=0, reported=0)
    td, ts, pop = S.targets(pref, d, h)
    if os.environ.get('BJ_TARGET_MODE') == 'legacy': td, ts = DCAP, SCAP
    stay = [stay_photo(e) for e in stay[:S.stay_keep(ts)]]
    dining, reported = tabelog(h, td)
    rec = {'dir': d, 'slug': slug_of(d, h), 'stay': stay, 'dining': dining,
           'targets': {'pop': pop, 'dining': td, 'stay': ts}, 'tabelog_reported': reported, 'jalan_found': len(jl), 'ikkyu_found': len(ik),
           'ikkyu_status': IKKYU_STATUS.get('status'), 'source_exhausted': {'dining': len(dining) < td and bool(S.LAST_TB['reported']) and S.LAST_TB['rows_seen'] >= S.LAST_TB['reported'], 'stay': len(stay) < ts and bool(jl) and not IKKYU_STATUS.get('status', '').startswith('BLOCKED')}}
    json.dump(rec, open(DATA / f'{d}.json', 'w'), ensure_ascii=False, indent=1)
    print(d, h['name_en'], 'ikkyu', len(ik), 'jalan', len(jl), 'stay', len(rec['stay']), '/', ts, 'dining', len(dining), '/', td, 'reported', reported, flush=True)

if __name__ == '__main__' and mode == 'collect':
    for d, h in hubs.items():
        if only and d not in only: continue
        if (DATA / f'{d}.json').exists() and not only and not os.environ.get('BJ_RECOLLECT'): continue
        collect(d, h)
