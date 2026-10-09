#!/usr/bin/env python3
"""Item 4: fix kakasi misreadings in Dining line 2 using the Tabelog listing's own reading (店名 cell '（よみ）').
Only segments whose kakasi reading disagrees with the listing reading are re-romanized; everything else in line 2 is kept.
Line 2 is only touched when it is still the plain kakasi romanization of the Japanese name (no hand-made English gloss)."""
import sys, re, json, collections, unicodedata
sys.path.insert(0, '/workspace/p1/line4/work'); sys.path.insert(0, '/workspace/p1/phase-d/dining4'); sys.path.insert(0, '/workspace/p1/phase-d/w3')
sys.path.insert(0, '/workspace/p1/data/catalog-uplift/.venv/lib/python3.13/site-packages')
import gen as B, parsers as P, pykakasi
B.FETCH_LOGS.append('/workspace/p1/line4/work/fetch_w4tb.jsonl')
from cards_lib import *
K = pykakasi.kakasi()
F = B.load_fetched()
def hira(s): return ''.join(chr(ord(ch) - 0x60) if '\u30a1' <= ch <= '\u30f6' else ch for ch in s)
def deacc(x): return unicodedata.normalize('NFKD', x).encode('ascii', 'ignore').decode()
def flat(x):
    x = re.sub(r'[^a-z0-9]', '', deacc(x).lower())
    for a, b in (('ou', 'o'), ('oo', 'o'), ('uu', 'u'), ('aa', 'a'), ('ii', 'i'), ('ee', 'e')): x = x.replace(a, b)
    return x
def romh(kana):
    h = ''.join(p.get('hepburn') or '' for p in K.convert(kana))
    for a, b in (('ou', 'o'), ('oo', 'o'), ('uu', 'u')): h = h.replace(a, b)
    return h
GEN2 = {'食堂', '商店', '酒造', '酒造店', '醸造店', '本舗', '温泉', '菓子店', '精肉店', '肉店', '魚店', '酒店', '飯店', '菜館', '酒場', '割烹', '料亭', '焼肉', '小料理', '和食', '喫茶', '寿司', '鮨', '寿し', 'すし', 'うどん', 'そば', '蕎麦', '茶屋', '茶店', '本店', '直売所', '加工所', '農園', '海鮮丼', '市場'}
GENERIC = {'割烹', '鮨処', '寿司処', 'すし処', '料亭', 'そば打ち', '手打ちそば', '手打そば', '居酒屋', '中華', '中華料理', '麺や', '麺屋', '炭火焼', '焼肉', '焼鳥', '鉄板焼', '旬菜', '酒房', 'しゃぶしゃぶ', 'らーめん', 'ラーメン', '和食', '食事処', 'お食事処', 'そば処', '蕎麦', 'そば', 'うどん', '喫茶', 'カフェ', '珈琲', '酒場', '大衆酒場', '天ぷら', 'とんかつ', '鮨', '寿司', 'すし', '料理', '旅館', 'れすとらん', 'レストラン'}
def segs(ja):
    out = []
    for p in K.convert(ja):
        o = p['orig']
        if not o.strip(): continue
        kana = bool(re.fullmatch(r'[\u3040-\u309f\u30a0-\u30ffー]+', o))
        out.append(dict(o=o, kana=kana, hira=hira(p.get('hira') or ''), hep=p.get('hepburn') or ''))
    return out
KJ = json.load(open('/workspace/p1/phase-d/w5/kanji.json'))
VOI = dict(zip('かきくけこさしすせそたちつてとはひふへほ', 'がぎぐげござじずぜぞだぢづでどばびぶべぼ'))
PV = dict(zip('はひふへほ', 'ぱぴぷぺぽ'))
def kread(ch):
    d = KJ.get(ch)
    if not d: return set()
    base = set()
    for r in (d.get('readings_on') or []) + (d.get('readings_kun') or []):
        r = hira(r.replace('-', ''))
        if '.' in r: a, b = r.split('.', 1); base |= {a, a + b}
        else: base.add(r)
    out = set()
    for r in base:
        if not r: continue
        vs = {r}
        if r[0] in VOI: vs.add(VOI[r[0]] + r[1:])
        if r[0] in PV: vs.add(PV[r[0]] + r[1:])
        for v in list(vs):
            if len(v) >= 2 and v[-1] in 'つくちき': vs.add(v[:-1] + 'っ')
        out |= vs
    return out
def seg_ok(o, rd, prev=None):
    """can kanji string o be read rd, each char taking a dictionary reading (with rendaku/gemination)?"""
    if not o: return rd == ''
    ch = o[0]
    if ch == '々' and prev: cands = kread(prev)
    elif re.fullmatch(r'[\u3040-\u309f]', ch): cands = {ch}
    elif re.fullmatch(r'[\u30a1-\u30f6]', ch): cands = {hira(ch)}
    else: cands = kread(ch)
    return any(rd.startswith(c) and seg_ok(o[1:], rd[len(c):], ch) for c in cands)
def align(S, R):
    n, m = len(S), len(R)
    best = {0: (0, [])}
    for i in range(n):
        nxt = {}
        for pos, (cost, path) in best.items():
            s = S[i]; opts = []
            if s['kana']:
                h = hira(s['o'])
                if R.startswith(h, pos): opts.append((pos + len(h), 0, None))
            else:
                if s['hira'] and R.startswith(s['hira'], pos): opts.append((pos + len(s['hira']), 0, None))
                for L in range(1, 3 * len(s['o']) + 2):
                    if pos + L <= m and R[pos:pos + L] != s['hira'] and seg_ok(s['o'], R[pos:pos + L]): opts.append((pos + L, 1, R[pos:pos + L]))
            for np_, c, new in opts:
                v = (cost + c, path + [new])
                if np_ not in nxt or v[0] < nxt[np_][0]: nxt[np_] = v
        best = nxt
    return best.get(m)
out = []; skip = []; st = collections.Counter()
for page, p in pages():
    if page.split('/')[0] not in ('miyagi', 'akita', 'fukuoka', 'yamaguchi', 'oita'): continue
    s = open(p).read(); m_, d = section_cards(s, 'Dining')
    for i, c in enumerate(d or []):
        if not c['tb']: continue
        ja = unicodedata.normalize('NFKC', c['name'] or '').strip()
        h, r = B.page(F, c['tb'])
        if not h: continue
        mm = re.search(r'<th[^>]*>\s*店名\s*</th>\s*<td[^>]*>(.*?)</td>', h, re.S)
        if not mm: continue
        cell = unicodedata.normalize('NFKC', P.clean(mm.group(1))).replace('\n', ' ')
        rm = re.match(r'^(.*?)\s*\(([\u3040-\u309f\u30a0-\u30ffー・\s]+)\)\s*$', cell)
        if not rm: continue
        name, reading = rm.group(1).strip(), rm.group(2).strip()
        if re.sub(r'\s', '', name) != re.sub(r'\s', '', ja): continue
        st['with reading'] += 1
        if re.search(r'[A-Za-z0-9]|[\u30a1-\u30faー]{2,}|\s', ja) or ('ー' in reading and 'ー' not in ja): st['latin/katakana/space name (kept)'] += 1; continue
        en = c['en'] or ''
        S = segs(ja)
        # line 2 must still be the plain per-segment kakasi romanization (otherwise it was hand-glossed: leave it)
        if flat(' '.join(x['hep'] for x in S)) != flat(en): st['line2 not kakasi (kept)'] += 1; continue
        R = hira(re.sub(r'[\s・]', '', reading))
        best = None
        for a in [0]:
            pre = ''.join(x['o'] for x in S[:a])
            if a and pre not in GENERIC: continue
            res = align(S[a:], R)
            if res and (best is None or res[0] < best[1][0]): best = (a, res)
            if best and a == 0: break
        if not best: st['reading not alignable (alias/partial)'] += 1; skip.append(dict(page=page, ja=ja, reading=reading, en=en)); continue
        a, (cost, path) = best
        if cost == 0: st['kakasi already right'] += 1; continue
        # rebuild line 2 from the listing reading: word units = kept multi-kanji words, generic words, particles; the rest joined
        rd = []
        for j, x in enumerate(S):
            new = path[j]
            rd.append(dict(o=x['o'], r=new if new is not None else (hira(x['o']) if x['kana'] else x['hira']), changed=new is not None, kana=x['kana']))
        # split segments that glue a trailing particle (kakasi 'うどんの')
        units = []
        for u in rd:
            mm = re.fullmatch(r'(.+?)([のにと])', u['o']) if u['kana'] and len(u['o']) > 2 else None
            if mm and u['r'].endswith(mm.group(2)):
                units.append(dict(u, o=mm.group(1), r=u['r'][:-1])); units.append(dict(o=mm.group(2), r=mm.group(2), changed=False, kana=True))
            else: units.append(u)
        def big(u): return (not u['changed'] and len(u['o']) >= 2 and not u['kana']) or u['o'] in GEN2
        words = []; cur = None; prev = None
        for k, u in enumerate(units):
            part = u['o'] in ('の', 'に', 'と') and 0 < k < len(units) - 1
            if part:
                if cur: words.append(cur)
                words.append(('p', romh(u['r']))); cur = None; prev = None; continue
            if cur is None: cur = dict(r=u['r']); prev = u; continue
            zushi = u['o'] in ('寿司', '鮨', '寿し', 'すし') and u['r'].startswith('ず')
            if (big(u) or big(prev)) and not zushi:
                words.append(cur); cur = dict(r=u['r'])
            else: cur = dict(r=cur['r'] + u['r'])
            prev = u
        if cur: words.append(cur)
        if len(ja) <= 4 and not any(u['o'] in GEN2 or (u['kana'] and u['o'] in ('の','に','と')) for u in units): words = [dict(r=''.join(u['r'] for u in units))]
        new_en = ' '.join(w[1] if isinstance(w, tuple) else romh(w['r']).capitalize() for w in words)
        new_en = re.sub(r'\s+', ' ', new_en).strip()
        if flat(new_en) == flat(en): st['same'] += 1; continue
        out.append(dict(page=page, idx=i, tb=c['tb'], ja=c['name'], reading=reading, old_en=en, new_en=new_en, segs_changed=cost))
        st['fix'] += 1
json.dump(out, open('n4_align.json', 'w'), ensure_ascii=False, indent=0)
json.dump(skip, open('n4_align_skip.json', 'w'), ensure_ascii=False, indent=0)
print(dict(st))
for x in out: print(x['ja'], '|', x['reading'], '|', x['old_en'], '->', x['new_en'])
