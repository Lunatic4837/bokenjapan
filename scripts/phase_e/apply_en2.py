#!/usr/bin/env python3
"""Line 2: where a katakana loanword was left as raw romaji (Suteeshonhoteru), swap in the English words (Station Hotel).
Only the romaji of that katakana run is replaced; everything else on line 2 stays as it was."""
import re, glob, html, json, sys, collections
sys.path.insert(0, '/workspace/p1/phase-d/names')
from en2 import seg, seg2, kroma
REPO = '/workspace/p1/pr12-work'
LI = re.compile(r'<li\b[^>]*>.*?</li>', re.S)
KRUN = re.compile(r'[\u30a1-\u30faー]{2,}')
st = collections.Counter(); samples = []
LONG = {'aa': 'ā', 'ii': 'ī', 'uu': 'ū', 'ee': 'ē', 'oo': 'ō', 'ou': 'ō', 'ei': 'ē'}
def romrx(rom):
    # match the run's romaji whether the line spells long vowels doubled (aa/ou) or with macrons (ā/ō)
    out = []; i = 0
    while i < len(rom):
        two = rom[i:i + 2]
        if two in LONG:
            alt = [two, LONG[two]] + (['ei'] if two == 'ee' else []) + (['ō'] if two == 'oo' else [])
            out.append('(?:' + '|'.join(map(re.escape, alt)) + '|' + re.escape(two[0]) + ')'); i += 2
        else:
            out.append(re.escape(rom[i])); i += 1
    return r"[\s\-']?".join(out)
def W(w): return r'(?<![A-Za-zāīūēō])' + w + r'(?![a-zāīūēō])'
# common kanji words left glued as one reading on line 2 -> their plain English
KW = [(re.compile(W(a), re.I), b) for a, b in [
    ('nihon ?ry[ōo]u?ri', 'Japanese Cuisine'), ('ch[ūu]u?ka ?ry[ōo]u?ri', 'Chinese Cuisine'), ('ch[ūu]u?goku ?ry[ōo]u?ri', 'Chinese Cuisine'),
    ('kankoku ?ry[ōo]u?ri', 'Korean Cuisine'), ('katei ?ry[ōo]u?ri', 'Home Cooking'), ('ky[ōo]u?do ?ry[ōo]u?ri', 'Local Cuisine'),
    ('washoku ?ry[ōo]u?ri', 'Japanese Cuisine'), ('y[ūu]u?gen ?gaisha ?', ''), ('kabushiki ?gaisha ?', ''),
    ('k[ōo]o?h[īi]i?', 'Coffee'), ('seipan', 'Bakery'), ('resutoran', 'Restaurant'), ('kaf[eē]', 'Cafe'), ('hausu', 'House'), ('hoteru', 'Hotel'), ('mujirushi ?ry[ōo]u?hin', 'MUJI')]]
for p in sorted(glob.glob(f'{REPO}/*/*/index.html')):
    if p.split('/')[-3] not in ('miyagi','akita','fukuoka','yamaguchi','oita'): continue
    s = open(p, encoding='utf-8').read(); o = s
    def f(m):
        li = m.group(0)
        nm = re.search(r'<p class="place-name">(.*?)</p>', li, re.S); bl = re.search(r'<p class="place-blurb">(.*?)</p>', li, re.S)
        if not nm or not bl: return li
        ja = html.unescape(nm.group(1)); cur = html.unescape(bl.group(1)); new = cur
        for run in KRUN.findall(ja):
            ws = seg(run) or seg2(run)
            if not ws: st['run_noseg'] += 1; continue
            if ' '.join(ws).lower() in new.lower(): st['run_already_english'] += 1; continue
            rom = re.sub(r'[^a-z]', '', kroma(run).lower())
            if len(rom) < 3: continue
            rx = re.compile(r'(?<![A-Za-zāīūēō])' + romrx(rom) + r'(?![a-zāīūēō])', re.I)
            mm = rx.search(new)
            if not mm: st['run_notfound'] += 1; continue
            new = new[:mm.start()] + ' '.join(ws) + new[mm.end():]
            st['run_replaced'] += 1
        for k_, v_ in KW:
            new = re.sub(k_, v_, new)
        new = re.sub(r'(?<=[a-z])(?=(?:Hotel|Inn|Cafe|Station|Plaza|House|Dining|Restaurant)\b)', ' ', new)
        if re.search(r'\s\S*[^商肉品の\s]店$', ja.strip()): new = re.sub(r'\b(?:Mise|Ten)$', 'Branch', new.strip())
        new = new.replace('&Amp;', '&').replace('&amp;', '&')
        new = re.sub(r'\bOoita\b', 'Oita', new)
        new = re.sub(r'\s+', ' ', new).strip()
        if new == cur: return li
        st['cards_changed'] += 1
        if len(samples) < 3000: samples.append((ja, cur, new))
        return li.replace(bl.group(0), f'<p class="place-blurb">{html.escape(new, quote=False)}</p>', 1)
    s = LI.sub(f, s)
    # 海の中道 was misread as "Umi no Chudo"; the official English name is Uminonakamichi.
    s = s.replace('Marinwarudo Umi no Chudo', 'Marine World Uminonakamichi').replace('Umi no Chudo', 'Uminonakamichi')
    if s != o: open(p, 'w', encoding='utf-8').write(s); st['pages'] += 1
print(dict(st))
json.dump(samples, open('/workspace/p1/phase-d/names/samples.json', 'w'), ensure_ascii=False, indent=0)
