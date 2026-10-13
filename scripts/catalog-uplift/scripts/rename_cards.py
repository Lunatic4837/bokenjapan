#!/usr/bin/env python3
"""Post-pass for already-hubbed prefectures: re-derive natural English card names (Dining always, Stay when romaji is garbled)
and undo double-escaped entities across every page of a prefecture. Usage: rename_cards.py ROOT pref..."""
import sys, re, glob, html, collections, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from en_natural import natural_en
ROMAJI_BAD = re.compile(r'(\b[A-Z] [A-Z] [A-Z]\b|Hoteru|Ryokan [A-Z]|Sou\b|Paaku|Bijinesu|Purinsu|Shitei|ruutoin|Gurando|Nyuu|Rizooto|Penshon|Gesutohausu|Hausu|Puraza|Rooyaru|Sentaa|Onsenryokan|\( |aa|ii|uu|ee|oo|ou\b| Ya\b| Kan\b| En\b)', re.I)  # same as template_hub.ROMAJI_BAD (that module parses argv on import)
root = Path(sys.argv[1]); st = collections.Counter()
for pref in sys.argv[2:]:
    ovp = Path(__file__).parent.parent / 'data' / f'en-overrides-{pref}.json'  # optional per-pref JA name -> EN overrides
    OV = json.loads(ovp.read_text()) if ovp.exists() else {}
    for town in sorted(glob.glob(str(root / pref / '*' / 'index.html'))):
        tdir = Path(town).parent; src = Path(town).read_text()
        muni_ja = (re.search(r'<!-- muni-ja: ([^ ]+) -->', src) or [0, None])[1]
        muni_en = html.unescape(re.search(r'<h1 class="page-title">([^<]+)</h1>', src).group(1))
        for f in [town] + glob.glob(str(tdir / '**' / 'index.html'), recursive=True)[0:]:
            t = Path(f).read_text(); t0 = t
            t = re.sub(r'&amp;(amp|#\d+|#x[0-9a-fA-F]+|quot|lt|gt|apos);', r'&\1;', t)
            def fix(m):
                li = m.group(0); s = re.search(r'sources: [^>]*(jalan_url|ikkyu_url|tabelog_url|rakuten_url)=', li)
                b = re.search(r'class="place-blurb">([^<]*)</p>', li); n = re.search(r'class="place-name">(.*?)</p>', li)
                if not (b and n): return li
                ja = html.unescape(n.group(1)).strip()
                if ja in OV: new = OV[ja]
                elif not s: return li
                elif s.group(1) != 'tabelog_url' and not ROMAJI_BAD.search(b.group(1)): return li
                else: new = natural_en(html.unescape(n.group(1)), muni_ja, muni_en)
                if not new or html.escape(new, quote=True) == b.group(1): return li
                st['renamed'] += 1
                li = li.replace(b.group(0), f'<p class="place-blurb">{html.escape(new, quote=True)}</p>', 1)
                return re.sub(r'(<img class="thumb"[^>]*alt=")[^"]*', lambda m2: m2.group(1) + html.escape(new, quote=True), li, count=1)
            t = re.sub(r'<li>(?:(?!</li>).)*?class="place-name".*?</li>', fix, t, flags=re.S)
            if t != t0: Path(f).write_text(t); st['files'] += 1
print(dict(st))
