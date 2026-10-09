#!/usr/bin/env python3
"""Item 4 part B: careful-reading fixes for systematic kakasi misreadings of shop-name kanji that have no listing reading.
寿司/寿し -> sushi (kakasi 'Hisashi Shi', 'Kiju Tsukasa'); 処 -> dokoro; 庵 -> an; 家 as shop suffix -> ya;
園 after a kanji -> en; 々 -> repeat of the previous kanji (kakasi '(kurikaesi)'); 志 next to hiragana -> shi.
Only the kakasi segment(s) containing the kanji are re-romanized; the rest of line 2 is untouched."""
import sys, re, json, collections, unicodedata
sys.path.insert(0, '/workspace/p1/phase-d/w4'); sys.path.insert(0, '/workspace/p1/phase-d/w3')
from a3_lib import K, wrong_rx
from cards_lib import *
PREFS = ('miyagi', 'akita', 'fukuoka', 'yamaguchi', 'oita')
NOT_YA = ('農家', '隠家', '一家', '民家', '本家', '実家', '宗家', '武家', '名家', '旧家', '町家', '茶家', '画家', '作家', '国家', '分家', '商家', '良家', '大家', '王家', '家族', '家庭', '家系', '家具', '家電', '家紋', '家康', '豪家', '平家', '在家', '人家', '出家', '道家', '公家', '後家')
KAN = r'[\u4e00-\u9fff]'; HIR = r'[\u3041-\u309f]'
BAD = {'家': 'ie', '処': 'tokoro', '庵': 'iori', '園': 'sono', '志': 'kokorozashi'}
def chunks(ja, a, b):
    """reading chunks for ja[a:b]: ('ja', text) or ('rom', word, glue)"""
    out = []; i = a
    def add_ja(t):
        if out and out[-1][0] == 'ja': out[-1] = ('ja', out[-1][1] + t)
        else: out.append(('ja', t))
    while i < b:
        ch = ja[i]; prev = ja[i - 1] if i > 0 else ''; nxt = ja[i + 1] if i + 1 < len(ja) else ''
        if ja[i:i + 3] == '御食事' and i + 2 < b: out.append(('rom', 'O Shokuji', False)); i += 3; continue
        if ja[i:i + 2] in ('寿司', '寿し', '壽司') and i + 1 < b and not re.match(HIR, ja[i + 2:i + 3] or ' '): out.append(('rom', 'Sushi', False)); i += 2; continue
        if ch == '処' and prev and not prev.isspace() and prev != '此': out.append(('rom', 'Dokoro', False))
        elif ch == '庵' and prev and not prev.isspace(): out.append(('rom', 'an', True))
        elif ch == '家' and prev and not prev.isspace() and prev != 'の' and (prev + ch) not in NOT_YA and (ch + nxt) not in NOT_YA and not re.match(KAN, nxt or ' '): out.append(('rom', 'ya', True))
        elif ch == '園' and re.match(KAN, prev or ' ') and (prev + ch) not in ('公園', '庭園', '霊園', '農園', '茶園', '楽園', '田園', '学園', '菜園'): out.append(('rom', 'en', True))
        elif ch == '志' and (re.match(HIR, prev or ' ') or re.match(HIR, nxt or ' ')): add_ja('し')
        else: add_ja(ch)
        i += 1
    return out
def render(ch):
    words = []
    for c in ch:
        if c[0] == 'ja': words += [w.capitalize() for w in tok(c[1])]
        elif c[2]:
            j = '' if c[1] == 'ya' else '-'
            if words: words[-1] = words[-1] + j + c[1]
            else: words.append('\x00' + j + c[1])
        else: words.append(c[1])
    return ' '.join(words)
def tok(s):
    t = []
    for p in K.convert(s):
        h = p.get('hepburn') or ''
        if re.search(r'[\u3040-\u309f\u4e00-\u9fff]', p['orig']):
            for q, z in (('ou', 'o'), ('oo', 'o'), ('uu', 'u')): h = h.replace(q, z)
        if h.strip(): t.append(h.strip())
    return t
def fix(ja, en):
    segs = []; pos = 0
    for p in K.convert(ja):
        o = p['orig']; i = ja.find(o, pos)
        if i < 0: return en, []
        segs.append([i, i + len(o), o, (p.get('hepburn') or '').lower()]); pos = i + len(o)
    need = set()
    for k, (sa, sb, o, h) in enumerate(segs):
        for j in range(sa, sb):
            ch = ja[j]
            if ch in BAD and BAD[ch] in h: need.add(k)
            if ja[j:j + 3] == '御食事' and 'mike' in h: need.add(k)
            if ja[j:j + 2] in ('寿司', '寿し', '壽司') or (ch == '司' and j > 0 and ja[j - 1] in '寿壽'):
                if re.search(r'hisashi|tsukasa|kotobuki|ju', h) and 'sushi' not in h and 'zushi' not in h: need.add(k)
    changes = []; new = en
    for k in sorted(need):
        lo, hi = k, k + 1
        # extend over a split 寿|司
        if segs[k][1] < len(ja) and ja[segs[k][1] - 1] in '寿壽' and hi < len(segs): hi += 1
        if ja[segs[k][0]] == '司' and lo > 0: lo -= 1
        wa, wb = segs[lo][0], segs[hi - 1][1]
        if any(x in changes for x in [(wa, wb)]): continue
        if (not wrong_rx(ja[wa:wb]) or ja[wa] in '家庵園') and lo > 0 and segs[lo - 1][2].strip(): lo -= 1; wa = segs[lo][0]
        rx = wrong_rx(ja[wa:wb]); rep = render(chunks(ja, wa, wb))
        if not rx or not rep: continue
        f = rx.search(new)
        if not f or f.group(0).lower().replace(' ', '') == rep.lower().replace(' ', ''): continue
        new = new[:f.start()] + rep + new[f.end():]; changes.append((wa, wb))
        new = re.sub(r'\s*\x00', '', new)
    if '御食事' in ja: new = re.sub(r'\bMike Koto\b', 'O Shokuji', new)
    new = re.sub(r'\b(\w+) \(kurikaesi\)', lambda m: m.group(1) + ' ' + m.group(1), new)
    return new, changes
if __name__ == '__main__':
    fixed = {(x['page'], x['idx']) for x in json.load(open('n4_align.json'))}
    out = []; st = collections.Counter()
    for page, p in pages():
        if page.split('/')[0] not in PREFS: continue
        s = open(p).read()
        for sec in ('Stay', 'Dining'):
            m, d = section_cards(s, sec)
            for i, c in enumerate(d or []):
                if sec == 'Dining' and (page, i) in fixed: continue
                ja = unicodedata.normalize('NFKC', c['name'] or ''); en = c['en'] or ''
                if not re.search(r'[寿壽処庵家園々志]', ja): continue
                new, ch = fix(ja, en)
                if new != en: out.append(dict(page=page, section=sec, idx=i, ja=c['name'], old_en=en, new_en=new)); st['fix ' + sec] += 1
    json.dump(out, open('n4_rules.json', 'w'), ensure_ascii=False, indent=0)
    print(dict(st))
    for x in out: print(x['ja'], '|', x['old_en'], '=>', x['new_en'])
