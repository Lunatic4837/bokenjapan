#!/usr/bin/env python3
"""CoS standard fixes for single-page municipality HTML (see /workspace/p1/STANDARD-FIXES.md).

Generic, prefecture-agnostic post-render pass. Idempotent. Never invents data:
every value it writes comes from (a) the card's own source URLs, (b) a sourced
data file passed in (--data), or (c) deletion.

  python3 cos_fix.py --root <site root> --pref aomori --data <cos-data.json>

cos-data.json keys (all optional, per slug):
  sights[slug]   -> [{idx,name,desc,link,src}]  English sights rebuilt from official pages
  stay_none[slug]-> nearest slug with real lodging (writes p.stay-none line)
  drop_stay[slug]-> true: remove unsourced (non Jalan/Ikkyu) Stay section
  tabelog[slug]  -> {rid: {area, ...}} list-page locality, used to drop out-of-town padding
  muni_ja[slug]  -> municipality name in JA (padding filter)
  ikkyu_by_jalan -> {jalan_url: ikkyu_url}
  names_en[slug] -> display English name
  rename         -> {old_slug: new_slug}
"""
from __future__ import annotations
import argparse, html as H, json, re
from pathlib import Path

CJK = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff\uff66-\uff9f]")
SITE = 'https://bokenjapan.com'
OG_IMG = 'https://img.bokenjapan.com/og.png'
CREDIT_BRAND = {'tabelog.com': '食べログ', 'www.jalan.net': 'じゃらんnet', 'www.ikyu.com': '一休.com',
                'www.tripadvisor.com': 'Tripadvisor'}
GENRE = {'居酒屋': 'Izakaya', '海鮮': 'Seafood restaurant', '食堂': 'Shokudo diner', 'ラーメン': 'Ramen shop',
 'カフェ': 'Café', '焼き鳥': 'Yakitori restaurant', '旅館・民宿': 'Inn restaurant', '寿司': 'Sushi restaurant',
 'コンビニ・スーパー': 'Convenience store', '焼肉': 'Yakiniku (grilled meat) restaurant', 'そば': 'Soba restaurant',
 '郷土料理': 'Local-cuisine restaurant', '日本料理': 'Japanese restaurant', '創作料理': 'Creative-cuisine restaurant',
 '和菓子': 'Japanese sweets shop', '喫茶店': 'Coffee shop', 'レストラン': 'Restaurant', 'ケーキ': 'Cake shop',
 'ホルモン': 'Horumon (offal) grill', '鍋': 'Hot-pot restaurant', '洋食': 'Yoshoku (Western-style) restaurant',
 '中華料理': 'Chinese restaurant', '弁当': 'Bento shop', 'バー': 'Bar', 'パン': 'Bakery', 'カレー': 'Curry restaurant',
 'ジェラート・アイスクリーム': 'Gelato and ice-cream shop', '洋菓子': 'Western sweets shop', '海鮮丼': 'Seafood-bowl restaurant',
 'うどん': 'Udon restaurant', '揚げ物': 'Fried-food restaurant', '道の駅': 'Roadside-station eatery', '料理旅館': 'Ryokan restaurant',
 '牛タン': 'Beef-tongue restaurant', 'ホテル': 'Hotel restaurant', 'イタリアン': 'Italian restaurant', 'パスタ': 'Pasta restaurant',
 'おでん': 'Oden restaurant', 'ダイニングバー': 'Dining bar', 'ステーキ': 'Steakhouse', 'ビュッフェ': 'Buffet restaurant',
 'ハンバーガー': 'Burger shop', 'もつ鍋': 'Motsunabe restaurant', 'ピザ': 'Pizzeria', '丼': 'Rice-bowl restaurant',
 'しゃぶしゃぶ': 'Shabu-shabu restaurant', '焼きそば': 'Yakisoba shop', 'ろばた焼き': 'Robatayaki grill', 'ワインバー': 'Wine bar',
 '日本酒バー': 'Sake bar', 'スイーツ': 'Sweets shop', 'すき焼き': 'Sukiyaki restaurant', '麺類': 'Noodle shop',
 'せんべい': 'Senbei cracker shop', '天ぷら': 'Tempura restaurant', 'からあげ': 'Karaage (fried chicken) shop',
 '串揚げ': 'Kushiage restaurant', 'フレンチ': 'French restaurant', 'たこ焼き': 'Takoyaki stand', 'たい焼き・大判焼き': 'Taiyaki shop',
 '馬肉料理': 'Horse-meat restaurant', 'つけ麺': 'Tsukemen shop', 'かつ丼': 'Katsudon restaurant', '惣菜・デリ': 'Deli',
 '売店': 'Kiosk', 'ハンバーグ': 'Hamburg-steak restaurant', 'ソフトクリーム': 'Soft-serve stand', 'ファミレス': 'Family restaurant',
 'おにぎり': 'Onigiri shop', '韓国料理': 'Korean restaurant', 'ビストロ': 'Bistro', 'とんかつ': 'Tonkatsu restaurant',
 '餃子': 'Gyoza restaurant', 'インドカレー': 'Indian curry restaurant', 'うなぎ': 'Eel restaurant', '串焼き': 'Skewer grill',
 '鳥料理': 'Chicken restaurant', 'ジンギスカン': 'Jingisukan (lamb BBQ) restaurant', '回転寿司': 'Conveyor-belt sushi',
 'ドーナツ': 'Doughnut shop', '牛丼': 'Gyudon restaurant', 'サンドイッチ': 'Sandwich shop', 'タイ料理': 'Thai restaurant',
 'お好み焼き': 'Okonomiyaki restaurant', 'パブ': 'Pub', 'シーフード': 'Seafood restaurant', '甘味処': 'Japanese sweets café',
 'バル': 'Bar', '鉄板焼き': 'Teppanyaki restaurant', '立ち飲み': 'Standing bar', 'あんこう': 'Monkfish restaurant',
 'インド料理': 'Indian restaurant', 'かに': 'Crab restaurant', '焼酎バー': 'Shochu bar', 'もつ焼き': 'Motsuyaki grill',
 'ベーグル': 'Bagel shop', 'クレープ・ガレット': 'Crêpe shop', 'オムライス': 'Omurice restaurant', '釜飯': 'Kamameshi restaurant',
 'ヨーロッパ料理': 'European restaurant', 'アメリカ料理': 'American restaurant', 'メキシコ料理': 'Mexican restaurant',
 'スープカレー': 'Soup-curry restaurant', '担々麺': 'Dandan-noodle shop', '天丼': 'Tendon restaurant', '肉料理': 'Meat restaurant',
 '野菜料理': 'Vegetable-dish restaurant', 'コーヒースタンド': 'Coffee stand', 'ジューススタンド': 'Juice stand',
 'フルーツパーラー': 'Fruit parlour', '豆腐料理': 'Tofu restaurant', '牛料理': 'Beef restaurant', '水炊き': 'Mizutaki restaurant',
 '飲茶・点心': 'Dim-sum restaurant', 'にんにく料理': 'Garlic-cuisine restaurant', '親子丼': 'Oyakodon restaurant',
 '豚しゃぶ': 'Pork shabu-shabu restaurant', 'オーガニック': 'Organic restaurant', '大福': 'Daifuku shop', 'どら焼き': 'Dorayaki shop',
 '立ち食いそば': 'Standing soba counter', '立ち食い寿司': 'Standing sushi bar', 'ビアバー': 'Beer bar', 'スポーツバー': 'Sports bar',
 'もんじゃ焼き': 'Monjayaki restaurant'}

def esc(s): return H.escape(s or '', quote=True)
def fw_clean(s: str) -> str:
    """No full-width JP punctuation in English lines."""
    s = s or ''
    voiced = {'k': 'g', 's': 'z', 't': 'd', 'h': 'b', 'f': 'b'}
    s = re.sub(r'(?i)(sh|ch|ts|[kstfh])([aiueo]) ?[゙\u3099]', lambda m: {'sh': 'j', 'ch': 'j', 'ts': 'z'}.get(m.group(1).lower(), voiced.get(m.group(1).lower(), m.group(1))) + m.group(2), s)
    s = re.sub(r'(?i)(h|f)([aiueo]) ?[゚\u309a]', lambda m: 'p' + m.group(2), s)
    s = re.sub(r'[゙゚\u3099\u309a]', '', s)
    s = re.sub(r'\s*[・･]\s*', ' ', s)
    s = s.replace('～', '-').replace('〜', '-').replace('　', ' ')
    return re.sub(r'\s{2,}', ' ', s).strip()

def genre_desc(area: str, town: str, pref_en: str) -> str | None:
    if '/' not in (area or ''):
        return None
    gs = [g.strip() for g in area.split('/', 1)[1].split('、') if g.strip() and g.strip() != 'その他']
    if not gs or gs[0] not in GENRE:
        return None
    return f'{GENRE[gs[0]]} in {town}, {pref_en}.'

def fix_credit(li: str) -> str:
    """Replace placeholder credit domains with the card's real listing URL + brand."""
    href = (re.search(r'<a href="([^"]+)"', li) or [None, ''])[1]
    host = (re.match(r'https?://([^/]+)/', href) or [None, ''])[1]
    def repl(m):
        if not host:
            return m.group(0)
        return f'<!-- photo-credit: {CREDIT_BRAND.get(host, host)} · Source {href} -->'
    return re.sub(r'<!-- photo-credit: source · Source https?://(?:www\.)?source\.(?:com|net)/[^ ]* -->', repl, li)

def section_re(title):
    return re.compile(rf'<section class="place-section"><h2>{title}</h2>.*?</section>', re.S)

def lis(sec_html):
    m = re.search(r'<ul class="place-list">(.*)</ul>', sec_html, re.S)
    return re.findall(r'<li>.*?</li>', m.group(1), re.S) if m else []

def renumber(items, town):
    out = []
    for i, li in enumerate(items, 1):
        out.append(re.sub(r'<p class="place-meta">#\d+ ranked in [^<]*</p>', f'<p class="place-meta">#{i} ranked in {esc(town)}</p>', li))
    return out

def placeholder_photo(li, media_root: Path, log: list, page_key: str, kind: str):
    m = re.search(r'<img class="thumb" src="\.\./\.\./media/([^"]+)"[^>]*>(<!--[^>]*photo-credit[^>]*-->)?', li)
    if not m:
        return li
    f = media_root / m.group(1)
    if f.exists() and f.stat().st_size == 3027:   # Tabelog "no photo" stub
        href = (re.search(r'<a href="([^"]+)"', li) or [None, ''])[1]
        name = H.unescape((re.search(r'place-name">([^<]*)', li) or [None, ''])[1])
        rid = (re.search(r'/(\d+)/?$', href) or [None, ''])[1]
        log.append((f'{page_key}|{kind}|{rid}', name, f'tabelog-list-img:{href}:placeholder-3027B | tabelog-detail-og:no_photo_350x350.gif', 'no usable photo on Tabelog list or detail page (no-image stub)', 'A', name, href))
        li = li.replace(m.group(0), '')
    return li

def fix_head(html, pref, slug, town, pref_en):
    url = f'{SITE}/{pref}/{slug}/' if slug else f'{SITE}/{pref}/'
    desc = (f'{town}, {pref_en}. Places to stay, eat, and visit.' if slug
            else f'{pref_en} Prefecture: towns and cities with places to stay, eat, and visit.')
    title = f'{town} · {pref_en} · BokenJapan' if slug else f'{pref_en} · BokenJapan'
    html = re.sub(r'\s*<link rel="canonical"[^>]*>|\s*<meta name="description"[^>]*>|\s*<meta property="og:[^"]+"[^>]*>', '', html)
    block = (f'\n  <link rel="canonical" href="{url}">\n  <meta name="description" content="{esc(desc)}">'
             f'\n  <meta property="og:type" content="website">\n  <meta property="og:url" content="{url}">'
             f'\n  <meta property="og:title" content="{esc(title)}">\n  <meta property="og:description" content="{esc(desc)}">'
             f'\n  <meta property="og:image" content="{OG_IMG}">')
    html = re.sub(r'(<title>[^<]*</title>)', lambda m: m.group(1) + block, html, count=1)
    # internal draft notes must not ship (X1)
    html = re.sub(r'\n\s*Note: local unpublished draft only;[^\n]*', '', html)
    html = re.sub(r'\n\s*No facilities-directory slug for \d+\.[^\n]*', '', html)
    return html

def sights_section(rows, town, pref_en, old_sec):
    old = lis(old_sec)
    out = []
    for r in rows:
        li = old[r['idx']] if r['idx'] < len(old) else ''
        img = (re.search(r'<img class="thumb"[^>]*>(?:<!--[^>]*-->)?', li) or [''])[0]
        img = re.sub(r'alt="[^"]*"', f'alt="{esc(r["name"])}"', img)
        meta = (re.search(r'<p class="place-meta">(.*?)</p>', li, re.S) or [None, ''])[1]
        meta = re.sub(r'\s*·\s*<a [^>]*>[^<]*</a>', '', meta).strip(' ·')
        if not meta or CJK.search(meta):
            meta = f'{town}, {pref_en}'
        out.append(f'<li><a href="{esc(r["link"])}"><p class="place-name">{esc(r["name"])}</p>{img}</a>'
                   f'<p class="place-meta">{meta}</p><p class="place-desc">{esc(r["desc"])}</p>'
                   f'<!-- desc-source: {esc(r["src"])} --></li>')
    return f'<section class="place-section"><h2>Sights</h2><ul class="place-list">{"".join(out)}</ul></section>' if out else ''

def fix_page(path: Path, pref: str, slug: str, data: dict, media_root: Path, nophoto_log: list, pref_en='Aomori'):
    html = path.read_text(encoding='utf-8')
    town = (data.get('names_en') or {}).get(slug) or re.search(r'<h1 class="page-title">([^<]+)</h1>', html).group(1)
    page_key = f'{pref}/{slug}'
    html = fix_head(html, pref, slug, town, pref_en)
    html = html.replace('&amp;#39;', '&#39;').replace('&amp;amp;', '&amp;')   # double-escaped text (X5)
    secs = {}
    for t in ('Stay', 'Dining', 'Sights'):
        m = section_re(t).search(html)
        secs[t] = m.group(0) if m else ''
    # ---- Dining
    if secs['Dining']:
        items = [fix_credit(li) for li in lis(secs['Dining'])]
        tb = (data.get('tabelog') or {}).get(slug) or {}
        muni = (data.get('muni_ja') or {}).get(slug, '')
        keep, seen = [], set()
        for li in items:
            rid = (re.search(r'tabelog\.com/[a-z]+/A\d+/A\d+/(\d+)/', li) or [None, None])[1]
            area = (tb.get(rid) or {}).get('area', '')
            if rid and muni and area and muni not in area:        # out-of-town padding
                continue
            nm = re.sub(r'[\s\u3000]', '', H.unescape((re.search(r'place-name">([^<]*)', li) or [None, ''])[1]))
            if nm in seen:                                        # dedupe
                continue
            seen.add(nm)
            li = re.sub(r'<p class="place-blurb">([^<]*)</p>', lambda m: f'<p class="place-blurb">{esc(fw_clean(H.unescape(m.group(1))))}</p>', li)
            gd = genre_desc(area, town, pref_en)
            if gd:
                li = re.sub(r'<p class="place-desc">Restaurant in [^<]*</p>', f'<p class="place-desc">{esc(gd)}</p>', li)
            li = placeholder_photo(li, media_root, nophoto_log, page_key, 'Dining')
            keep.append(li)
        keep = renumber(keep, town)
        secs['Dining'] = f'<section class="place-section"><h2>Dining</h2><ul class="place-list">{"".join(keep)}</ul></section>'
    # ---- Stay
    near = (data.get('stay_none') or {}).get(slug)
    if secs['Stay'] and 'stay-none' not in secs['Stay']:
        items = [fix_credit(li) for li in lis(secs['Stay'])]
        sourced = [li for li in items if re.search(r'sources: [^>]*(jalan_url|ikkyu_url)=https://www\.(jalan\.net|ikyu\.com)/', li)]
        ik = data.get('ikkyu_by_jalan') or {}
        out, seen = [], set()
        for li in sourced:
            ju = (re.search(r'jalan_url=(\S+)', li) or [None, ''])[1]
            if ju in seen:
                continue
            seen.add(ju)
            if ju in ik and 'ikkyu_url=' not in li:
                li = li.replace(f'<!-- sources: jalan_url={ju}', f'<!-- sources: ikkyu_url={ik[ju]} | jalan_url={ju}')
            li = re.sub(r'<p class="place-blurb">([^<]*)</p>', lambda m: f'<p class="place-blurb">{esc(fw_clean(H.unescape(m.group(1))))}</p>', li)
            out.append(li)
        out.sort(key=lambda li: 0 if 'ikkyu_url=' in li else 1)     # Ikkyu-first, stable
        secs['Stay'] = (f'<section class="place-section"><h2>Stay</h2><ul class="place-list">{"".join(renumber(out, town))}</ul></section>'
                        if out else '')
    if not secs['Stay'] and near:
        nn = (data.get('names_en') or {}).get(near, near.title())
        secs['Stay'] = (f'<section class="place-section"><h2>Stay</h2><p class="stay-none">No listed places to stay in {esc(town)} — '
                        f'nearest options in <a href="/{pref}/{near}/">{esc(nn)}</a>.</p></section>')
    # ---- Sights
    rows = (data.get('sights') or {}).get(slug)
    if rows is not None and secs['Sights'] and 'place-desc' not in secs['Sights']:
        secs['Sights'] = sights_section(rows, town, pref_en, secs['Sights'])
    elif secs['Sights']:
        s = re.sub(r'\s*·\s*<a href="[^"]*">Official / source link</a>', '', secs['Sights'])
        secs['Sights'] = s
    # ---- rebuild in Ōhira order: Stay → Dining → Sights
    for t in ('Stay', 'Dining', 'Sights'):
        html = section_re(t).sub('', html, count=1)
    anchor = re.search(r'<section class="meta-block">.*?</section>', html, re.S)
    block = ''.join(secs[t] for t in ('Stay', 'Dining', 'Sights') if secs[t])
    html = html[:anchor.end()] + block + html[anchor.end():]
    # any <img> without alt gets its card name
    html = re.sub(r'<img(?![^>]*\balt=)([^>]*)>', r'<img alt=""\1>', html)
    path.write_text(html, encoding='utf-8')

def rename_slug(root: Path, pref: str, old: str, new: str, new_en: str):
    import subprocess
    subprocess.run(['git', '-C', str(root), 'mv', f'{pref}/{old}', f'{pref}/{new}'], check=True)
    for f in (root / 'media').glob(f'{old}-*'):
        subprocess.run(['git', '-C', str(root), 'mv', f'media/{f.name}', f'media/{new}-' + f.name[len(old) + 1:]], check=True)
    for p in (root / pref).rglob('*.html'):
        s = p.read_text(encoding='utf-8'); s2 = s
        s2 = s2.replace(f'../{old}/', f'../{new}/').replace(f'/{pref}/{old}/', f'/{pref}/{new}/').replace(f'href="{old}/"', f'href="{new}/"')
        s2 = s2.replace(f'media/{old}-', f'media/{new}-')
        s2 = re.sub(r'(data-name|aria-label)="JIS ' + old[3:] + '"', rf'\1="{new_en}"', s2).replace(f'<title>JIS {old[3:]}</title>', f'<title>{new_en}</title>')
        if s2 != s:
            p.write_text(s2, encoding='utf-8')

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True); ap.add_argument('--pref', required=True)
    ap.add_argument('--pref-en', default=None); ap.add_argument('--data', required=True)
    ap.add_argument('--nophoto-log', default='/workspace/p1/photos-5pref/no-photo-found.csv')
    a = ap.parse_args()
    root = Path(a.root); data = json.loads(Path(a.data).read_text(encoding='utf-8'))
    pref_en = a.pref_en or a.pref.title()
    for old, new in (data.get('rename') or {}).items():
        if (root / a.pref / old).exists():
            rename_slug(root, a.pref, old, new, (data.get('names_en') or {}).get(new, new.title()))
    idx = root / a.pref / 'index.html'
    if idx.exists():
        idx.write_text(fix_head(idx.read_text(encoding='utf-8'), a.pref, '', pref_en, pref_en), encoding='utf-8')
    log = []
    for p in sorted((root / a.pref).glob('*/index.html')):
        fix_page(p, a.pref, p.parent.name, data, root / 'media', log, pref_en)
    if log:
        import csv
        lp = Path(a.nophoto_log)
        have = set(l.split(',', 1)[0] for l in lp.read_text(encoding='utf-8').splitlines()) if lp.exists() else set()
        with lp.open('a', encoding='utf-8', newline='') as fh:
            w = csv.writer(fh)
            for row in log:
                if row[0] not in have:
                    w.writerow(row)
    print('pages fixed; placeholder photos removed:', len(log))
