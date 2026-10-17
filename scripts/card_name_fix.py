#!/usr/bin/env python3
"""X12.title-as-name (+ one R4.other listing-label case): a card's place name is a scraped SEO page title
('曼陀羅寺公園 – 江南市観光協会', '蒲郡市観光協会公式サイト「がまごおり、ナビ」 » 竹島', '足湯かにえの郷 - 愛知県蟹江町公式ホームページ', 'HOME - KAKAMIGAHARA PARK BRIDGE').

Nothing is invented.  The clean name is a piece OF THE SAME SCRAPED STRING with only site/organisation parts removed:
  * ad / site tags 【公式】【公式サイト】【伊東園ホテルズ】【大人専用…】【全館禁煙】【旧…】 and a leading 【…温泉】 area tag,
  * a leading HOME / TOP, a trailing TOP, site-word tokens (観光協会, 公式サイト, ホームページ, ウェブサイト, 観光案内 ...),
  * separator segments (｜ | » ' – ' ' - ') that are site names, a bare municipality name, or site words.
A card is rewritten ONLY if exactly one content segment is left (with '»' breadcrumbs: the last crumb), it contains no title marker, no remaining 【】,
no slogan punctuation (！ ？ 〜 。) and is 2..30 chars, and every dropped site segment stood AFTER it (or was a leading HOME/TOP/breadcrumb).
Everything else (several content segments, slogans, generic category cards) is listed in --report for the owning lane.
The old string is replaced inside that page (visible card, JSON-LD alternateName/name), in data/<pref>.json strings and in llms*.txt.
Also: ', bookable on Jalan|Ikkyu.' (listing-site wording in a card description, R4.other 'listing label') -> '.'.
tokyo/ skipped.  Idempotent (second run = zero diff).  --check exits 1 if a change is needed; --dry-run; --report CSV (pref,page,old,new,status,reason).
Usage: python3 scripts/card_name_fix.py --root . [--pref slug] [--check|--dry-run] [--report out.csv]
"""
import argparse, csv, html, json, re, sys
from pathlib import Path
SKIP = {'media', 'assets', 'data', 'scripts', 'go', 'fonts', 'sitemaps', 'photo-credits', 'tokyo'}
TITLE_AS_NAME = re.compile(r'[｜|»【】]|公式(サイト|ホームページ|HP)|観光協会|HOME\s*[-–]|ホームページ|Official (Web)?site', re.I)  # == bj_shared.title_as_name
SITE = re.compile(r'観光協会|観光(?:情報|ガイド|ナビ|サイト|案内|スポット)|公式|オフィシャル|ホームページ|ウェブサイト|トップページ|^(?:TOP|HOME|ホーム)$|役場|市役所|旅ガイド|e-izu|\.(?:com|jp)\b', re.I)
MUNI = re.compile(r'^(?:[^\s]{2,4}県)?[^\s]{1,5}[市町村]$')
SITE_TOKEN = re.compile(r'^(?:[^\s]{2,6}[市町村県](?:公式)?(?:ホームページ|ウェブサイト|観光協会(?:公式(?:サイト|ウェブサイト))?)|公式サイト|公式ホームページ|公式HP|TOP|HOME)$', re.I)  # a municipality's / the venue's own site-name token
GENERIC = {'一般社団法人', '社団法人', '公益社団法人', '株式会社', '温泉'}
AD_TAG = re.compile(r'^(?:公式(?:サイト)?|伊東園ホテルズ|全館禁煙|大人専用.*|旧(?!店名).+)$')
GENERIC_PREFIX = ('施設案内', '施設紹介')
SEP = re.compile(r'\s*[｜|]\s*|\s+[–—-]\s+|\s*[–—]\s*')
SLOGAN = re.compile(r'[！？!?〜。]|です|ます|できる|楽しめる|見渡せる|おすすめ')
BOOKABLE = re.compile(r', bookable on (?:Jalan|Ikkyu)(?=\.)')
LI = re.compile(r'<li>.*?</li>', re.S)

def clean(old):
    """-> (new, '') or (None, reason)"""
    s = old.strip()
    if not TITLE_AS_NAME.search(s): return None, 'not a title string'
    tags = re.findall(r'【[^】]*】', s)
    for tg in tags:
        inner = tg[1:-1]
        if AD_TAG.match(inner): s = s.replace(tg, ' ', 1)
        elif s.startswith(tg) and re.match(r'^[^\s\u3000]{2,5}温泉$', inner) and s[len(tg):].strip(): s = s[len(tg):]  # leading area tag '【四万温泉】'
    s = re.sub(r'^(?:HOME|TOP|ホーム)\s*[-–｜|]\s*', '', s.strip(), flags=re.I)
    if '»' in s:
        segs = [x.strip() for x in s.split('»') if x.strip()]; cand = segs[-1]
        if SITE.search(cand) or MUNI.match(cand): return None, 'last breadcrumb is a site name'
        segs = [cand]; dropped_before_ok = True
    else:
        segs = [x.strip() for x in SEP.split(s) if x.strip()]
        if not segs: return None, 'empty after splitting'
        kept = []; seen_site_before = False
        for x in segs:
            toks = re.split(r'[\s\u3000]+', x)
            while len(toks) > 1 and SITE_TOKEN.match(toks[-1]): toks.pop()
            while len(toks) > 1 and SITE_TOKEN.match(toks[0]): toks.pop(0)
            x2 = ' '.join(toks)
            if SITE.search(x2) or MUNI.match(x2):
                if not kept: seen_site_before = True
                continue
            kept.append(x2)
        if len(kept) != 1: return None, f'{len(kept)} content segments after dropping site parts (needs a lane decision)'
        if seen_site_before: return None, 'site name stands before the kept segment (kept part may be a slogan)'
        segs = kept
    cand = segs[0].strip(' 　-–—:：')
    for g in GENERIC_PREFIX:
        if cand.startswith(g) and len(cand) > len(g): cand = cand[len(g):].strip(' 　')
    cand = re.sub(r'[\s\u3000]+', ' ', cand)
    if cand in GENERIC: return None, 'only a generic word is left'
    if '【' in cand or '】' in cand: return None, 'remaining bracket tag'
    if SLOGAN.search(cand): return None, 'looks like a slogan'
    if not (2 <= len(cand) <= 30): return None, f'length {len(cand)}'
    if TITLE_AS_NAME.search(cand) or SITE.search(cand): return None, 'still title-like'
    return cand, ''

def forms(t):
    j = json.dumps(t, ensure_ascii=False)[1:-1]
    return {t, html.escape(t, quote=False), html.escape(t, quote=True), j}

def sub_all(text, old, new):
    fo = [(o, n) for o, n in zip(sorted(forms(old), key=len, reverse=True), sorted(forms(new), key=len, reverse=True))]
    # map each old form to the same kind of new form
    pairs = [(old, new), (html.escape(old, quote=False), html.escape(new, quote=False)), (html.escape(old, quote=True), html.escape(new, quote=True)),
             (json.dumps(old, ensure_ascii=False)[1:-1], json.dumps(new, ensure_ascii=False)[1:-1])]
    for o, n in sorted(set(pairs), key=lambda x: -len(x[0])): text = text.replace(o, n)
    return text

def fixjson(o, old, new):
    if isinstance(o, str): return o.replace(old, new)
    if isinstance(o, list): return [fixjson(x, old, new) for x in o]
    if isinstance(o, dict): return {k: fixjson(v, old, new) for k, v in o.items()}
    return o

def names_of(li):
    ja = re.search(r'<p class="place-name-ja"[^>]*>(.*?)</p>', li, re.S)
    if ja: return html.unescape(re.sub(r'<[^>]+>', '', ja.group(1))).strip()
    m = re.search(r'<p class="place-name"[^>]*>(.*?)</p>', li, re.S)
    return html.unescape(re.sub(r'<[^>]+>', '', m.group(1))).strip() if m else ''

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--root', default='.'); ap.add_argument('--pref')
    ap.add_argument('--check', action='store_true'); ap.add_argument('--dry-run', action='store_true'); ap.add_argument('--report')
    a = ap.parse_args(); root = Path(a.root).resolve(); write = not (a.check or a.dry_run)
    prefs = [a.pref] if a.pref else sorted(d.name for d in root.iterdir() if d.is_dir() and not d.name.startswith('.') and d.name not in SKIP)
    rows, files, changes, per = [], set(), {}, {}
    llm = {n: (root / n).read_text(encoding='utf-8') for n in ('llms-full.txt', 'llms.txt') if (root / n).is_file()}; llm0 = dict(llm)
    for pref in prefs:
        pdir = root / pref; djs = {}
        for p in sorted(pdir.rglob('index.html')):
            t = p.read_text(encoding='utf-8', errors='replace')
            if 'place-list' not in t: continue
            t2 = BOOKABLE.sub('', t) if BOOKABLE.search(t) else t
            if t2 != t:
                changes['bookable'] = changes.get('bookable', 0) + len(BOOKABLE.findall(t))
                rows.append((pref, str(p.relative_to(root)), 'bookable on Jalan/Ikkyu', '(removed)', 'fixed', 'listing-site wording in card description'))
                djs[('bk',)] = True
            for li in LI.findall(t):
                if 'place-name' not in li: continue
                old = names_of(li)
                if not old or not TITLE_AS_NAME.search(old): continue
                new, why = clean(old)
                rel = str(p.relative_to(root))
                ne = re.search(r'<!-- name-en: ([^>]*?) -->', li)
                if new is not None and ne and ne.group(1).strip() == 'category':
                    new, why = None, 'English headline is a generic category placeholder (name-en: category): lane must supply the real name'
                if new is None:
                    rows.append((pref, rel, old, '', 'undecided', why)); continue
                if new == old: continue
                t2 = sub_all(t2, old, new); changes['x12'] = changes.get('x12', 0) + 1; djs[old] = new
                rows.append((pref, rel, old, new, 'fixed', 'site/org parts removed from the scraped title'))
            if t2 != t:
                files.add(p); per[pref] = per.get(pref, 0) + 1
                if write: p.write_text(t2, encoding='utf-8')
        dj = root / 'data' / f'{pref}.json'
        if djs and dj.is_file():
            d0 = dj.read_text(encoding='utf-8'); d = json.loads(d0)
            for old, new in djs.items():
                if old == ('bk',): d = json.loads(BOOKABLE.sub('', json.dumps(d, ensure_ascii=False)))
                else: d = fixjson(d, old, new)
            out = json.dumps(d, ensure_ascii=False, indent=1) + '\n'
            if out != d0:
                files.add(dj)
                if write: dj.write_text(out, encoding='utf-8')
        for old, new in djs.items():
            if old == ('bk',): continue
            for n in llm: llm[n] = llm[n].replace(old, new)
    for n in llm:
        if llm[n] != llm0[n]:
            files.add(root / n)
            if write: (root / n).write_text(llm[n], encoding='utf-8')
    print(' '.join(f'{k}:{v}' for k, v in sorted(per.items())))
    print(f'cards {"to fix" if not write else "fixed"}: {changes.get("x12", 0)}; listing-label descs: {changes.get("bookable", 0)}; files: {len(files)}; undecided (listed): {sum(1 for r in rows if r[4] == "undecided")}')
    if a.report:
        with open(a.report, 'w', newline='') as f: w = csv.writer(f); w.writerow(['pref', 'page', 'old_name', 'new_name', 'status', 'reason']); w.writerows(rows)
    sys.exit(1 if (a.check and files) else 0)
if __name__ == '__main__': main()
