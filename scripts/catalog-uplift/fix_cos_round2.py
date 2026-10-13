#!/usr/bin/env python3
"""Round-2 CoS: Hokkaido locality/NT/map/alts/slugs/filler + Aomori filler; docs helpers."""
from __future__ import annotations
import html as H, json, re, shutil
from pathlib import Path

ROOT = Path('/workspace/p1/bokenjapan-cutover')
HUB_HK = Path('/workspace/p1/data/catalog-uplift/hubs/hokkaido-hub-codes.json')
HUB_AO = Path('/workspace/p1/data/catalog-uplift/hubs/aomori-hub-codes.json')
LOCALITY = json.loads(Path('/tmp/hokkaido-locality.json').read_text())
PAD_IDS = {'1078057','1010286','1052973','1063584','1003087','1060055','1037483','1085074','1004112','1064014'}
NT = {'shikotan','tomari-nt','ruyobetsu','ryubetsu','shana','shibetoro'}
RENAMES = {
    'hidakacho-01601': ('hidakacho', 'Hidaka'),
    'ikedacho-01644': ('ikedacho', 'Ikeda'),
    'kitahiroshima-01234': ('kitahiroshima', 'Kitahiroshima'),
    'moricho-01345': ('moricho', 'Mori'),
    'shimizucho-01636': ('shimizucho', 'Shimizu'),
    'taiki-01641': ('taiki', 'Taiki'),
    # keep esashi-01514
}
MAP_CREDIT = (
    '<!-- map-credit: Municipality boundaries from MLIT National Land Numerical Information '
    'N03 2026 (CC BY 4.0). Dataset. https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html -->'
)
MAP_BLOCK = '''<!--
  Municipality boundaries: MLIT National Land Numerical Information N03 2026, vintage N03-20260101.
  Source URL: https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html
  License: CC BY 4.0
  Citation (JA): 「国土数値情報（行政区域データ）」（国土交通省）（https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html）を加工して作成
  Multipart only where N03 polygons are multipart. Rings were simplified independently; no gaps bridged.
-->'''
DRAFT_RE = re.compile(
    r'Note:\s*local unpublished draft only;[^\n<]*',
    re.I,
)
DRAFT_BLOCK_RE = re.compile(
    r'<!--\s*Municipality boundaries:.*?-->',
    re.S,
)
FILLER_RE = re.compile(
    r'<p class="place-desc">(Restaurant|Lodging) in ([^<]+), (Hokkaido|Aomori)\.</p>'
)
FW_RE = re.compile(r'[・･～〜　]')
OPENING_RE = re.compile(r'（[^）]*開業[^）]*）|\([^)]*opened[^)]*\)', re.I)
CJK = re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')


def esc(s): return H.escape(s or '', quote=True)


def fw_clean(s: str) -> str:
    s = H.unescape(s or '')
    s = re.sub(r'\s*[・･]\s*', ' / ', s)
    s = s.replace('～', '-').replace('〜', '-').replace('　', ' ')
    return re.sub(r'\s{2,}', ' ', s).strip()


def lis(sec):
    m = re.search(r'<ul class="place-list">(.*)</ul>', sec, re.S)
    return re.findall(r'<li>.*?</li>', m.group(1), re.S) if m else []


def renumber(items, town):
    out = []
    for i, li in enumerate(items, 1):
        out.append(re.sub(
            r'<p class="place-meta">#\d+ ranked in [^<]*</p>',
            f'<p class="place-meta">#{i} ranked in {esc(town)}</p>',
            li,
        ))
    return out


def strip_draft_notes(html: str) -> str:
    html = DRAFT_RE.sub('', html)
    # Replace bulky boundary comment with clean Miyagi-style block + map-credit
    if 'N03-2026' in html or '国土数値情報' in html:
        html = DRAFT_BLOCK_RE.sub(MAP_BLOCK, html, count=1)
        if 'map-credit:' not in html:
            # insert after first boundary block
            html = html.replace(MAP_BLOCK, MAP_BLOCK + '\n' + MAP_CREDIT, 1)
    html = html.replace('local unpublished draft only;', '')
    html = html.replace('GSI reproduction filing gates public redistribute', '')
    # collapse leftover empty note lines inside comments
    html = re.sub(r'\n\s*\n\s*-->', '\n-->', html)
    return html


def fix_cover_alt(html: str, town: str, pref_en: str) -> str:
    def repl(m):
        tag = m.group(0)
        alt_m = re.search(r'alt="([^"]*)"', tag)
        alt = alt_m.group(1) if alt_m else ''
        bad = (not alt or 'span' in alt.lower() or 'lang=' in alt or 'mw-page-title' in alt
               or CJK.search(alt) or alt.startswith('<'))
        if bad:
            new_alt = f'{town}, {pref_en}'
            if alt_m:
                tag = re.sub(r'alt="[^"]*"', f'alt="{esc(new_alt)}"', tag, count=1)
            else:
                tag = tag.replace('<img ', f'<img alt="{esc(new_alt)}" ', 1)
        return tag
    return re.sub(r'<figure class="cover"><img[^>]*>', repl, html, count=1)


def fix_filler_desc(li: str, town: str, pref_en: str) -> str:
    """Replace identical Restaurant/Lodging filler with per-card EN-name line, or drop if empty."""
    blurb = H.unescape((re.search(r'place-blurb">([^<]*)', li) or [None, ''])[1]).strip()
    name = H.unescape((re.search(r'place-name">([^<]*)', li) or [None, ''])[1]).strip()
    en = fw_clean(blurb) if blurb and not CJK.search(blurb) else ''
    def repl(m):
        kind, _t, pref = m.group(1), m.group(2), m.group(3)
        if en and len(en.split()) >= 1:
            # unique per card, not the banned identical filler
            label = 'restaurant' if kind == 'Restaurant' else 'lodging'
            return f'<p class="place-desc">{esc(en)} — {label} in {town}, {pref}.</p>'
        # no usable EN: omit line 4 (3-line card)
        return ''
    return FILLER_RE.sub(repl, li)


def fix_dining_locality(html: str, slug: str, town: str, muni_ja: str, loc_map: dict) -> str:
    m = re.search(r'(<section class="place-section"><h2>Dining</h2>)(.*?)(</section>)', html, re.S)
    if not m:
        return html
    items = lis(m.group(0))
    keep = []
    for li in items:
        rid = (re.search(r'tabelog\.com/[a-z]+/A\d+/A\d+/(\d+)/', li) or [None, None])[1]
        if rid in PAD_IDS:
            continue
        info = loc_map.get(rid) if loc_map else None
        if info is not None and not info.get('in_town'):
            continue
        # attach locality comment when known
        if info and info.get('area') and 'locality-addr:' not in li:
            addr = re.sub(r'\s+', ' ', info['area']).strip()
            li = li.replace('</li>', f'<!-- locality-addr: {esc(addr)} --></li>')
        li = re.sub(r'<p class="place-blurb">([^<]*)</p>',
                    lambda mm: f'<p class="place-blurb">{esc(fw_clean(mm.group(1)))}</p>', li)
        li = fix_filler_desc(li, town, 'Hokkaido')
        keep.append(li)
    keep = renumber(keep, town)
    new_sec = f'<section class="place-section"><h2>Dining</h2><ul class="place-list">{"".join(keep)}</ul></section>'
    return html[:m.start()] + new_sec + html[m.end():]


def ensure_head_pref_index(html: str, pref: str, title_en: str) -> str:
    url = f'https://bokenjapan.com/{pref}/'
    desc = f'{title_en}, Japan. Places to stay, eat, and visit.'
    html = re.sub(r'\s*<link rel="canonical"[^>]*>', '', html)
    html = re.sub(r'\s*<meta name="description"[^>]*>', '', html)
    html = re.sub(r'\s*<meta property="og:[^"]+"[^>]*>', '', html)
    block = (
        f'\n  <link rel="canonical" href="{url}">'
        f'\n  <meta name="description" content="{esc(desc)}">'
        f'\n  <meta property="og:type" content="website">'
        f'\n  <meta property="og:url" content="{url}">'
        f'\n  <meta property="og:title" content="{esc(title_en)} · BokenJapan">'
        f'\n  <meta property="og:description" content="{esc(desc)}">'
        f'\n  <meta property="og:image" content="https://img.bokenjapan.com/og.png">'
    )
    html = re.sub(r'(<title>.*?</title>)', r'\1' + block, html, count=1, flags=re.S)
    return html


def inject_muni_ja(html: str, muni_ja: str) -> str:
    html = re.sub(r'\s*<!-- muni-ja: [^>]*-->', '', html)
    if 'muni-ja:' not in html:
        html = html.replace('</title>', f'</title>\n  <!-- muni-ja: {muni_ja} -->', 1)
    return html


def unlink_nt_from_maps(html: str) -> str:
    for slug in NT:
        for href in (f'{slug}/', f'../{slug}/', f'/hokkaido/{slug}/'):
            html = re.sub(
                rf'<a href="{re.escape(href)}"([^>]*)>(.*?)</a>',
                lambda m: f'<span{re.sub(rchr(92)+r"s*href="+chr(34)+r"[^"+chr(34)+r"]*"+chr(34), "", m.group(1))}>{m.group(2)}</span>',
                html,
                flags=re.S,
            )
    return html


def rename_slug(pref: str, old: str, new: str, new_en: str, hubs: dict):
    old_dir = ROOT / pref / old
    new_dir = ROOT / pref / new
    if old_dir.exists() and not new_dir.exists():
        old_dir.rename(new_dir)
    elif old_dir.exists() and new_dir.exists():
        shutil.rmtree(old_dir)
    # media files
    for f in list((ROOT / 'media').glob(f'{old}-*')):
        dest = ROOT / 'media' / (new + '-' + f.name[len(old) + 1:])
        if dest.exists():
            f.unlink()
        else:
            f.rename(dest)
    if old in hubs:
        hb = hubs.pop(old)
        hb['name_en'] = new_en
        hb['slug'] = new
        hubs[new] = hb
    # rewrite refs in pref html
    for p in (ROOT / pref).rglob('*.html'):
        t = p.read_text(encoding='utf-8')
        o = t
        t = t.replace(f'href="{old}/"', f'href="{new}/"')
        t = t.replace(f'href="../{old}/"', f'href="../{new}/"')
        t = t.replace(f'href="/{pref}/{old}/"', f'href="/{pref}/{new}/"')
        t = t.replace(f'/{pref}/{old}/', f'/{pref}/{new}/')
        t = t.replace(f'media/{old}-', f'media/{new}-')
        t = t.replace(f'../../media/{old}-', f'../../media/{new}-')
        if p.parent.name == new:
            t = re.sub(r'<h1 class="page-title">.*?</h1>', f'<h1 class="page-title">{esc(new_en)}</h1>', t, count=1)
            # head
            title = f'{new_en} · Hokkaido · BokenJapan'
            t = re.sub(r'<title>.*?</title>', f'<title>{esc(title)}</title>', t, count=1)
            canon = f'https://bokenjapan.com/{pref}/{new}/'
            t = re.sub(r'<link rel="canonical"[^>]*>', f'<link rel="canonical" href="{canon}">', t)
            t = re.sub(r'property="og:url"[^>]*>', f'property="og:url" content="{canon}">', t)
            t = re.sub(r'property="og:title"[^>]*>', f'property="og:title" content="{esc(title)}">', t)
        if t != o:
            p.write_text(t, encoding='utf-8')


def fix_pref_pages(pref: str, hubs: dict, pref_en: str, do_locality: bool):
    for slug, hb in sorted(hubs.items()):
        if slug in NT or hb.get('nt'):
            # leave NT pages on disk but unlinked; still strip draft notes if present
            path = ROOT / pref / slug / 'index.html'
            if path.exists():
                t = strip_draft_notes(path.read_text(encoding='utf-8'))
                path.write_text(t, encoding='utf-8')
            continue
        path = ROOT / pref / slug / 'index.html'
        if not path.exists():
            continue
        town = hb.get('name_en') or slug
        muni_ja = hb.get('name_ja') or ''
        html = path.read_text(encoding='utf-8')
        html = strip_draft_notes(html)
        html = fix_cover_alt(html, town, pref_en)
        html = inject_muni_ja(html, muni_ja)
        html = OPENING_RE.sub('', html)
        # fw clean blurbs/descs
        def clean_en_field(m):
            return f'<p class="{m.group(1)}">{esc(fw_clean(m.group(2)))}</p>'
        html = re.sub(r'<p class="(place-blurb|place-desc)">([^<]*)</p>', clean_en_field, html)
        if do_locality:
            loc_map = {rid: v for rid, v in (LOCALITY.get(slug) or {}).items()}
            # Also drop PAD_IDS everywhere even without loc_map
            html = fix_dining_locality(html, slug, town, muni_ja, loc_map if slug in LOCALITY else {rid: {'in_town': False, 'area': ''} for rid in PAD_IDS})
        # filler on stay too
        def fix_stay_sec(m):
            sec = m.group(0)
            if 'stay-none' in sec:
                return sec
            items = [fix_filler_desc(li, town, pref_en) for li in lis(sec)]
            items = renumber(items, town)
            return f'<section class="place-section"><h2>Stay</h2><ul class="place-list">{"".join(items)}</ul></section>'
        html = re.sub(r'<section class="place-section"><h2>Stay</h2>.*?</section>', fix_stay_sec, html, count=1, flags=re.S)
        # dining filler for non-locality path
        if not do_locality or slug not in LOCALITY:
            def fix_din_sec(m):
                sec = m.group(0)
                items = []
                for li in lis(sec):
                    rid = (re.search(r'tabelog\.com/[a-z]+/A\d+/A\d+/(\d+)/', li) or [None, None])[1]
                    if rid in PAD_IDS:
                        continue
                    li = fix_filler_desc(li, town, pref_en)
                    items.append(li)
                items = renumber(items, town)
                return f'<section class="place-section"><h2>Dining</h2><ul class="place-list">{"".join(items)}</ul></section>'
            html = re.sub(r'<section class="place-section"><h2>Dining</h2>.*?</section>', fix_din_sec, html, count=1, flags=re.S)
        path.write_text(html, encoding='utf-8')


def main():
    data_hk = json.loads(HUB_HK.read_text())
    hubs_hk = data_hk['hubs']
    # Renames first
    for old, (new, en) in RENAMES.items():
        if (ROOT / 'hokkaido' / old).exists() or old in hubs_hk:
            print('rename', old, '->', new)
            rename_slug('hokkaido', old, new, en, hubs_hk)
    data_hk['hubs'] = hubs_hk
    HUB_HK.write_text(json.dumps(data_hk, ensure_ascii=False, indent=2) + '\n')
    # copy hub into repo scripts
    dest = ROOT / 'scripts/catalog-uplift/hubs/hokkaido-hub-codes.json'
    if dest.parent.exists():
        dest.write_text(HUB_HK.read_text())

    # Pref index: head tags, unlink NT, draft notes
    idx = ROOT / 'hokkaido' / 'index.html'
    t = idx.read_text(encoding='utf-8')
    t = strip_draft_notes(t)
    t = ensure_head_pref_index(t, 'hokkaido', 'Hokkaido')
    # ensure NT are spans not links
    for slug in NT:
        t = re.sub(
            rf'<a href="{slug}/"([^>]*)>(.*?)</a>',
            lambda m: f'<span{re.sub(r"\s*href=\"[^\"]*\"", "", m.group(1))}>{m.group(2)}</span>',
            t,
            flags=re.S,
        )
    # rewrite renamed slugs in index (already done in rename_slug)
    idx.write_text(t, encoding='utf-8')

    # All hokkaido munis
    fix_pref_pages('hokkaido', hubs_hk, 'Hokkaido', do_locality=True)

    # Aomori filler + draft notes + fw
    if HUB_AO.exists():
        hubs_ao = json.loads(HUB_AO.read_text())['hubs']
    else:
        hubs_ao = {d.name: {'name_en': d.name.title(), 'name_ja': ''} for d in (ROOT/'aomori').iterdir() if d.is_dir()}
    fix_pref_pages('aomori', hubs_ao, 'Aomori', do_locality=False)
    # aomori index draft notes
    aidx = ROOT / 'aomori' / 'index.html'
    if aidx.exists():
        at = strip_draft_notes(aidx.read_text(encoding='utf-8'))
        if 'rel="canonical"' not in at:
            at = ensure_head_pref_index(at, 'aomori', 'Aomori')
        aidx.write_text(at, encoding='utf-8')

    # Strip draft notes sitewide under cutover (sparse prefs)
    for p in ROOT.rglob('*.html'):
        if '/.git/' in str(p):
            continue
        t = p.read_text(encoding='utf-8', errors='replace')
        if 'local unpublished draft' in t or 'GSI reproduction' in t:
            p.write_text(strip_draft_notes(t), encoding='utf-8')

    print('done')
    # sanity
    for slug in ['kamisunagawa','utashinai','tomari','kitahiroshima','hidakacho']:
        p = ROOT/'hokkaido'/slug/'index.html'
        if not p.exists():
            print(slug, 'MISSING'); continue
        t = p.read_text()
        n = len(re.findall(r'<h2>Dining</h2>.*?<li>', t, re.S))
        # count lis properly
        m = re.search(r'<h2>Dining</h2>(.*?)</section>', t, re.S)
        n = len(re.findall(r'<li>', m.group(1))) if m else 0
        print(slug, 'dining', n, 'draft', 'unpublished draft' in t, 'pad', any(x in t for x in PAD_IDS))

if __name__ == '__main__':
    main()
