#!/usr/bin/env python3
"""Generic post-pass: natural English names (place-blurb) for Dining/Stay/Sight cards built by template_hub.py.

  python3 dining_en.py --root <site> --pref iwate [--pref ...] [--dry] [--report out.json]

A blurb is rewritten only when it is a mechanical katakana/kanji romanization of the JA name (or trips the
stiff-romaji detector) -- real English names from sources are kept. Also repairs double-escaped HTML entities
(e.g. "Kan&amp;#x27;Ichi"). Rewrite = en_natural.natural_en (loanword dict + JMdict loanwords + Hepburn).
"""
import re, glob, html, json, sys, os, argparse, collections
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from en_natural import natural_en, _K
KATA_ROMAJI = (r'Resutoran|Kafe|Doraibuin|Hoteru|Bijinesu|Raamen|Intaa|Sentaa|Kyapitaru|Orenji|Bukku|Keeki|Pabu|Sausu|Hiruzu|'
               r'Famirii|Sutoa|Dainingu|Kicchin|Shokudou|Chuuou|Choudou|Bisutoro|Pasuta|Karee|Makudonarudo|Doraibu|Paaku|Hausu|'
               r'Shoppu|Mooru|Gaaden|Faamu|Biiru|Kureepu|Penshon|Gesutohausu|Rizooto|Sebun|Rooson|Ionmooru')
BAD = re.compile(r'(\b(%s)|[a-z](aa|uu|ee)|\b(No|Ke|Ga|Wo|Ni)$|\bMise\b|&#x?\w+;|&amp;|&quot;)' % KATA_ROMAJI)
import json as _j
_EN = set()
for _v in _j.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'loan_jm.json'))).values(): _EN.update(w.lower() for w in re.findall(r"[A-Za-z]+", _v))
_SHORT_OK = {'no', 'to', 'yu', 'ya', 'an', 'the', 'and', 'of', 'de', 'la', 'le', 'du', 'bar', 'inn', 'spa', 'pub', 'cafe', 'by', 'in', 'at', 'a', 'bbq', 'kan', 'tei', 'so', 'en'}
def split_hits(b):
    """strict rule: broken word splits = 2+ adjacent short (1-3 letter) capitalised romaji tokens that are not English"""
    t = re.findall(r"[A-Za-z]+(?:-[a-z]+)?", b or '')
    sh = [bool(re.fullmatch(r'[A-Z][a-z]{0,2}', x)) and x.lower() not in _SHORT_OK and x.lower() not in _EN for x in t]
    return any(sh[k] and sh[k + 1] for k in range(len(sh) - 1))
from en_natural import OVERRIDES
_OK = set(OVERRIDES.values())
def is_stiff(b, n=''):
    if b in _OK: return False
    if split_hits(b): return True
    for t in re.findall(r"[A-Za-z&#;0-9]+", b or ''):
        if BAD.search(t) or (t in ('No', 'Ke', 'Ga', 'Wo', 'Ni') and b.endswith(' ' + t)):
            if t.lower() in _EN or t.lower() in (n or '').lower(): continue
            return True
    return bool(re.search(r'&#x?\w+;|&amp;|&quot;', b or ''))
def unesc(s):
    for _ in range(4):
        t = html.unescape(s)
        if t == s: break
        s = t
    return s
def skel(s): return re.sub(r'(.)\1+', r'\1', re.sub(r'[aeiou]', '', re.sub(r'[^a-z]', '', s.lower())))
def mechanical(n, b):
    if not re.search(r'[ぁ-んァ-ヴ一-龥]', n): return False
    k = ''.join(x['hepburn'] for x in _K.convert(n))
    return skel(k) == skel(b)
_OLD = []
for _f in ('/tmp/oldnat/en_natural_old.py', '/tmp/oldnat/en_natural_old0.py'):
    try:
        import importlib.util as _iu
        _sp = _iu.spec_from_file_location(os.path.basename(_f)[:-3], _f); _m = _iu.module_from_spec(_sp); _sp.loader.exec_module(_m); _OLD.append(_m.natural_en)
    except Exception: pass
def _was_generated(n, b):  # output of an earlier natural_en version -> safe to regenerate with the current one
    return any(f(n) == b for f in _OLD)
def fix_card(li, muni_ja, muni_en, st):
    m = re.search(r'<p class="place-name">([^<]*)</p>', li); mb = re.search(r'<p class="place-blurb">([^<]*)</p>', li)
    if not m or not mb: return li
    n = unesc(m.group(1)); b = unesc(mb.group(1))
    new = b
    if n.strip() in OVERRIDES: new = OVERRIDES[n.strip()]
    elif not re.search(r'[ぁ-んァ-ヴ一-龥]', n) and re.search(r'(aa|ii|uu|ee|oo)|Doraibuin|Resutoran|Kafe|Hoteru|\bMise\b', b):
        cand = natural_en(b)
        if cand and cand != b: new = cand
    elif mechanical(n, b) or is_stiff(b, n) or _was_generated(n, b):
        cand = natural_en(n, muni_ja, muni_en)
        if cand and re.search(r'[A-Za-z]', cand): new = cand
    if not re.search(r'[ぁ-んァ-ヴ一-龥]', n) and re.search(r'Doraibuin|Resutoran|Kafe|Hoteru|\bMise\b', n):
        nn = natural_en(n)
        li = li.replace(m.group(0), f'<p class="place-name">{html.escape(nn, quote=True)}</p>', 1).replace(f'alt="{m.group(1)}"', f'alt="{html.escape(nn, quote=True)}"')
        st['name_fixed'] += 1
    if html.escape(new, quote=True) != mb.group(1):
        st['changed'] += 1
        li = li.replace(mb.group(0), f'<p class="place-blurb">{html.escape(new, quote=True)}</p>', 1)
    if is_stiff(new, n): st['residual'] += 1; st.setdefault('samples', []).append((n, new)) if len(st.get('samples', [])) < 60 else None
    st['cards'] += 1
    return li
def run(root, pref, dry=False):
    st = collections.Counter(); st['samples'] = []
    seen = {}
    for f in sorted(glob.glob(f'{root}/{pref}/**/index.html', recursive=True)):
        src = open(f).read()
        muni_ja = (re.search(r'<!-- muni-ja: ([^ ]+) -->', src) or [0, None])[1]
        mm = re.search(r'<p class="crumb">.*?<a href="/%s/[^/]+/">([^<]+)</a>' % pref, src) or re.search(r'<h1 class="page-title">([^<]+)</h1>', src)
        muni_en = unesc(mm.group(1)) if mm else None
        out = re.sub(r'<li>(?:(?!</li>).)*?class="place-name".*?</li>', lambda x: fix_card(x.group(0), muni_ja, muni_en, st), src, flags=re.S)
        out = re.sub(r'&amp;(#x?[0-9a-fA-F]+|amp|quot|lt|gt);', r'&\1;', out) if False else out
        if out != src and not dry: open(f, 'w').write(out)
    return st
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--pref', action='append', required=True)
    ap.add_argument('--dry', action='store_true'); ap.add_argument('--report'); A = ap.parse_args()
    rep = {}
    for p in A.pref:
        st = run(A.root, p, A.dry); rep[p] = dict(st)
        print(p, {k: v for k, v in st.items() if k != 'samples'}, flush=True)
    if A.report: json.dump(rep, open(A.report, 'w'), ensure_ascii=False, indent=1)
