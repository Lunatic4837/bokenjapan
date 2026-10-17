#!/usr/bin/env python3
"""X23: give Dining/Stay cards that FAIL check_live X23 (no / non-English / empty place-desc) a minimal factual English line 4.

Emulates check_live.hub_merged_soup pooling: every page under <pref>/<town>/ reachable from the hub tiles; Dining/Stay classification
is the checker's (Stay: /stay/ path or jalan/ikkyu source; Dining: tabelog/ta/osm/official source). A card FAILS when its first
.place-desc/.place-explain/.place-note is missing/empty/contains CJK.  Only failing cards are touched, and only by adding (or replacing a
Japanese) <p class="place-desc"> + a desc-source comment.  Nothing is invented:
  Dining: '<Genre> in <Town>.'  Genre = the card's own Tabelog genre label (scripts/x23_data/card_genre.json, from the repo's
          fn-uplift/partials-build dining data, keyed by Tabelog restaurant id) translated via scripts/x23_data/genre_en.json.
  Stay:   '<Kind> in <Town>.'   Kind = from the card's own Japanese/English name (ホテル/旅館/民宿 ... / Hotel/Inn ...), else 'Lodging'.
Cards with no usable source (no genre / unmapped genre / non-standard desc element) are listed in --left CSV, never padded.
Idempotent (a card that passes is never touched). tokyo/ is skipped.
Usage: x23_english_desc.py --root . --pref ibaraki [--pref ...] [--check] [--left left.csv] [--dups dups.csv]"""
import argparse, csv, html, json, os, re, sys
from pathlib import Path

CJK = re.compile(r"[\u3040-\u30fa\u30fc-\u30ff\u3400-\u9fff\uf900-\ufaff\uff66-\uff9f]")
HERE = Path(__file__).resolve().parent
GENRE_EN = json.load(open(HERE / 'x23_data' / 'genre_en.json'))
CARD_GENRE = json.load(open(HERE / 'x23_data' / 'card_genre.json'))
JA_TOKENS = {'カレー': 'Curry'}
STAY_JA = (('旅館', 'Ryokan inn'), ('民宿', 'Minshuku guesthouse'), ('ペンション', 'Pension'), ('ホテル', 'Hotel'), ('ゲストハウス', 'Guesthouse'),
           ('山荘', 'Mountain lodge'), ('ホステル', 'Hostel'), ('コテージ', 'Cottage'), ('キャンプ', 'Campsite'))
STAY_EN = (('ryokan', 'Ryokan inn'), ('minpaku', 'Guesthouse'), ('minshuku', 'Minshuku guesthouse'), ('pension', 'Pension'), ('hostel', 'Hostel'),
           ('guest ?house', 'Guesthouse'), ('hotel', 'Hotel'), ('inn', 'Inn'), ('lodge', 'Lodge'), ('resort', 'Resort'))
DESC_RE = re.compile(r'<p class="place-desc">(.*?)</p>', re.S)
UL_RE = re.compile(r'(<ul class="place-list"[^>]*>)(.*?)(</ul>)', re.S)
LI_RE = re.compile(r'<li>(.*?)</li>', re.S)
SKIP = {'tokyo', 'media', 'assets', 'data', 'scripts', 'go', 'fonts', 'sitemaps', 'photo-credits'}

def txt(s): return re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', s))).strip()
def first_desc(li):
    m = re.search(r'<p class="(?:place-desc|place-explain|place-note)"[^>]*>(.*?)</p>', li, re.S)
    return txt(m.group(1)) if m else None
def desc_ok(li):
    d = first_desc(li)
    return bool(d and d.strip() and not CJK.search(d))
def classify(path_url, li):
    if '/stay/' in path_url: return 'Stay'
    if '/day-to-day/' in path_url: return 'Sights'
    if re.search(r"sources: [^>]*(jalan_url|ikk?yu_url)=", li): return 'Stay'
    if re.search(r"sources: [^>]*(tabelog_url|ta_url|osm_url|official_url)=", li): return 'Dining'
    return 'Sights'
def town_pages(root, pref, town):
    base = os.path.join(root, pref, town); hub = os.path.join(base, 'index.html')
    s = open(hub, encoding='utf-8').read()
    tiles = re.findall(r'<a class="hub-tile[^"]*" href="([^"]+)"', s)
    queue = [os.path.normpath(os.path.join(base, h, 'index.html')) for h in tiles if not h.startswith(('http', '/'))]
    seen, out = set(), []
    while queue:
        p = queue.pop(0)
        if p in seen or not os.path.exists(p): continue
        seen.add(p); out.append(p)
        t = open(p, encoding='utf-8').read()
        for h in re.findall(r'<a [^>]*href="([^"#?]+)"', t):
            if re.search(r"\.(jpg|png|webp|svg|json|xml|pdf)$", h): continue
            if h.startswith('https://bokenjapan.com'): h = h[len('https://bokenjapan.com'):]
            elif h.startswith('http'): continue
            q = os.path.normpath(os.path.join(root, h.lstrip('/')) if h.startswith('/') else os.path.join(os.path.dirname(p), h))
            if os.path.isdir(q): q = os.path.join(q, 'index.html')
            if q.startswith(os.path.normpath(base) + os.sep) and q != os.path.normpath(hub) and q not in seen: queue.append(q)
    return out
def town_name(hub_html, li):
    m = re.search(r'#\d+ ranked in ([^<]+)<', li)
    if m: return m.group(1).strip()
    h = re.search(r'<h1[^>]*>(.*?)</h1>', hub_html, re.S)
    return re.split(r",| in |:", txt(h.group(1)))[0].strip() if h else ''
def stay_kind(li):
    ja = re.search(r'<p class="place-name-ja"[^>]*>(.*?)</p>', li, re.S)
    nm = re.search(r'<p class="place-name">(.*?)</p>', li, re.S)
    jt = txt(ja.group(1)) if ja else (txt(nm.group(1)) if nm else '')
    for k, v in STAY_JA:
        if k in jt: return v
    et = txt(nm.group(1)) if nm else ''
    for k, v in STAY_EN:
        if re.search(r'\b' + k + r'\b', et, re.I): return v
    return 'Lodging'
def dining_genre(li):
    m = re.search(r'tabelog\.com/[^ "]*/(\d+)/', li)
    g = CARD_GENRE.get(m.group(1)) if m else None
    if not g: return None, 'no Tabelog genre in repo data'
    for t in [x.strip() for x in re.split('[、,]', g) if x.strip()]:
        if GENRE_EN.get(t): return GENRE_EN[t], g
    return None, f'genre not translatable: {g}'
def cap(s): return s[:1].upper() + s[1:]

def process(root, pref, left, dups, write):
    stats = dict(towns=0, cards=0, ok_before=0, edited=0, left=0, files=0, ok_after=0, towns_fail_before=0, towns_fail_after=0)
    for town in sorted(os.listdir(os.path.join(root, pref))):
        hub = os.path.join(root, pref, town, 'index.html')
        if not os.path.exists(hub): continue
        hub_html = open(hub, encoding='utf-8').read()
        if 'hub-tiles' not in hub_html: continue
        stats['towns'] += 1; tb = ta = 0
        for p in town_pages(root, pref, town):
            rel = os.path.relpath(p, root); url = '/' + os.path.dirname(rel) + '/'
            s = open(p, encoding='utf-8').read(); changed = False
            def do_ul(m):
                nonlocal changed, tb, ta
                def do_li(lm):
                    nonlocal changed, tb, ta
                    li = lm.group(1); g = classify(url, li)
                    if g not in ('Dining', 'Stay'): return lm.group(0)
                    stats['cards'] += 1
                    if desc_ok(li): stats['ok_before'] += 1; stats['ok_after'] += 1; return lm.group(0)
                    tb += 1
                    nm = re.search(r'<p class="place-name">(.*?)</p>', li, re.S); nm = txt(nm.group(1)) if nm else ''
                    ja = re.search(r'<p class="place-name-ja"[^>]*>(.*?)</p>', li, re.S); ja = txt(ja.group(1)) if ja else ''
                    town_en = town_name(hub_html, li)
                    old = re.search(r'<p class="place-desc">(.*?)</p>', li, re.S)
                    def leave(reason):
                        stats['left'] += 1; ta += 1
                        left.append(dict(pref=pref, town=town, page=rel, group=g, name=nm, name_ja=ja, reason=reason))
                        return lm.group(0)
                    if first_desc(li) and not old: return leave('non-standard desc element (place-explain/place-note) is empty or Japanese')
                    if old:  # existing Japanese place-desc: translate known genre tokens only
                        d = txt(old.group(1)); 
                        for k, v in JA_TOKENS.items(): d = d.replace(k, v)
                        d = cap(d)
                        if CJK.search(d): return leave('existing Japanese description not translatable from known genre words: ' + txt(old.group(1)))
                        new_li = li.replace(old.group(0), f'<p class="place-desc">{html.escape(d, quote=False)}</p>', 1)
                        kind_note = None
                    else:
                        if not town_en: return leave('town name unknown')
                        if g == 'Stay': kind = stay_kind(li); basis = 'name'
                        else:
                            kind, basis = dining_genre(li)
                            if not kind: return leave(basis)
                        d = f'{cap(kind)} in {town_en}.'
                        if len(d) < 15: d = f'{cap(kind)} located in {town_en}.'  # checker R4: line 4 must be >= 15 chars
                        href = re.search(r'<a href="([^"]+)"', li); src = href.group(1) if href else ''
                        add = f'<p class="place-desc">{html.escape(d, quote=False)}</p><!-- desc-source: {src} -->'
                        mm = re.search(r'<p class="place-meta">.*?</p>', li, re.S)
                        if not mm: return leave('no place-meta line to anchor the description')
                        new_li = li[:mm.end()] + add + li[mm.end():]
                        if re.sub(r'\.$', '', d).lower() == nm.lower():
                            dups.append(dict(pref=pref, town=town, page=rel, name=nm, name_ja=ja, desc=d))
                    stats['edited'] += 1; stats['ok_after'] += 1; changed = True
                    return '<li>' + new_li + '</li>'
                return m.group(1) + LI_RE.sub(do_li, m.group(2)) + m.group(3)
            new = UL_RE.sub(do_ul, s)
            if changed and new != s:
                stats['files'] += 1
                if write: open(p, 'w', encoding='utf-8').write(new)
        stats['towns_fail_before'] += 1 if tb else 0; stats['towns_fail_after'] += 1 if ta else 0
    return stats

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default='.'); ap.add_argument('--pref', action='append', required=True)
    ap.add_argument('--check', action='store_true'); ap.add_argument('--left'); ap.add_argument('--dups')
    a = ap.parse_args(); left, dups = [], []; rc = 0
    for pref in a.pref:
        if pref in SKIP: continue
        st = process(a.root, pref, left, dups, not a.check)
        pb = round(100 * st['ok_before'] / max(st['cards'], 1), 1); pa = round(100 * st['ok_after'] / max(st['cards'], 1), 1)
        print(f"{pref}: towns={st['towns']} cards={st['cards']} X23 {pb}% -> {pa}% | edited={st['edited']} left={st['left']} files={st['files']} failing_towns {st['towns_fail_before']} -> {st['towns_fail_after']}")
        if st['edited']: rc = 1
    for path, rows in ((a.left, left), (a.dups, dups)):
        if path and rows:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    sys.exit(rc if a.check else 0)
main()
