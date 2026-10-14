#!/usr/bin/env python3
"""Usage: fn_render.py <pref> <pref_ja> <PrefEn> [dirs...]  -- renders collected data into the worktree."""
import json, re, sys, os, math, subprocess, html as H
from pathlib import Path
sys.path.insert(0, '/workspace/p1/partials-build')
from fn_lib import *
sys.path.insert(0, '/workspace/p1/partials-build/shared'); import bj_shared as S  # AUDIT-47 P5-P9
pref, pref_ja, PREF_EN = sys.argv[1:4]; only = sys.argv[4:]
WT = Path(os.environ.get('FN_WT') or f'/workspace/p1/wt-{pref}'); PD = WT / pref; MEDIA = WT / 'media'
meta = json.load(open(f'/workspace/p1/fn-uplift/hubs/{pref}-hub-codes.json')); hubs = meta['hubs']
DATA = Path(os.environ.get('BJ_DATA_DIR') or '/workspace/p1/partials-build/data') / pref
PHOTO_SEARCH = {}
REJECTS = Path(os.environ.get('BJ_REJECT_CSV') or str(DATA / 'no-photo-found.csv'))
SITE = 'https://bokenjapan.com'
E = lambda s: H.escape(s or '', quote=True)
recs = {d: json.load(open(DATA / f'{d}.json')) for d in hubs if (DATA / f'{d}.json').exists()}
slug = {d: r['slug'] for d, r in recs.items()}
for d in hubs: slug.setdefault(d, d)
assert len(set(slug.values())) == len(slug), 'slug collision'
STAY_EN = json.load(open(DATA / '_stay_desc_en.json')) if (DATA / '_stay_desc_en.json').exists() else {}
OFFICIAL = json.load(open(f'/workspace/p1/fn-uplift/hubs/{pref}-official.json')) if os.path.exists(f'/workspace/p1/fn-uplift/hubs/{pref}-official.json') else {}

def onsen_of(*txt):
    for t in txt:
        m = re.search(r'([一-龥ぁ-んァ-ヴ]{1,6}?)温泉', t or '')
        if m and m.group(1) not in ('天然', '源泉', '自家', '露天', '温泉'):
            r = romanize(m.group(1)).replace(' ', '')
            if r and not CJK.search(r): return f'{r.title()} Onsen'
    return ''

def photo(url, fname, maxw=560, kind='dining', alt='', town='', name=''):
    """P5 photo gate: source < 5 KB rejected for every image; Stay photos need >= 560 px source width,
    no food/promo alt or URL, and a pass from the CLIP judge. Rejects are logged to no-photo-found.csv."""
    if not url: return None
    dest = MEDIA / fname
    cands = [url.replace('320x320_square_', '640x640_rect_'), url] if 'tblg' in url else [S.jalan_big(url), url]
    reason = 'no-download'
    for u in dict.fromkeys(cands):
        if dest.exists() and dest.stat().st_size >= S.env_int('BJ_MIN_IMG_BYTES', 5120) and not os.environ.get('BJ_REGATE'):
            from PIL import Image
            w, hgt = Image.open(dest).size
            return (f'../../media/{fname}', w, hgt)
        r = subprocess.run(['curl', '-sL', '-A', UA, '--max-time', '25', u], capture_output=True); b = r.stdout
        if not b: continue
        tmp = Path('/tmp/bjleo/gate') / (fname + '.src'); tmp.parent.mkdir(parents=True, exist_ok=True); tmp.write_bytes(b)
        try:
            from PIL import Image
            sw = Image.open(tmp).size[0]
        except Exception: reason = 'undecodable'; continue
        reason = S.photo_gate(tmp, kind=kind, url=u, alt=alt, raw_bytes=len(b), raw_w=sw)
        if reason: continue
        try: to_webp(b, dest, maxw)
        except Exception as e: reason = f'convert:{e}'; continue
        if dest.stat().st_size < S.env_int('BJ_MIN_IMG_BYTES', 5120):
            to_webp(b, dest, maxw, q=60)
            if dest.stat().st_size < S.env_int('BJ_MIN_IMG_BYTES', 5120): reason = 'tiny-output'; dest.rename(dest.with_suffix('.rejected')); continue
        w, hgt = Image.open(dest).size
        return (f'../../media/{fname}', w, hgt)
    S.log_reject(REJECTS, f'{pref}/{town}', name, url, reason)
    return None

def card(href, ja, en, rank, muni_en, desc, ph, credit, sources, near=''):
    ja = re.sub(r'[（(][^）)]*開業[^）)]*[）)]', '', ja).strip()
    img = f'<img class="thumb" src="{E(ph[0])}" alt="{E(en)}" width="{ph[1]}" height="{ph[2]}" loading="lazy">' if ph else ''
    cm = f'<!-- photo-credit: {E(credit)} -->' if ph else ''
    src = ' | '.join(f'{k}={v}' for k, v in sources if v)
    if near:  # P6: neighbour-town stay -> visible label inside the English description (R4 keeps '#N ranked in {Town}' meta untouched)
        desc = f'{S.neighbour_label(near)}. ' + (desc or '')
    return (f'<li><a href="{E(href)}"><p class="place-name">{E(ja)}</p>{img}</a>{cm}'
            f'<p class="place-blurb">{E(en)}</p><p class="place-meta">#{rank} ranked in {E(muni_en)}</p>'
            + (f'<p class="place-desc">{E(desc)}</p><!-- desc-source: {E(href)} -->' if desc else '')
            + (f'<!-- neighbour: {E(near)} -->' if near else '') + f'<!-- sources: {src} --></li>')

def en_name(ja, official=''):
    """P7: official EN (Tabelog EN / Ikkyu) -> romaji dictionary -> legacy romanize."""
    ja = re.sub(r'[（(][^）)]*開業[^）)]*[）)]', '', ja)
    s = S.romanize_name(ja, official) or romanize(ja)
    return s if s and not CJK.search(s) else 'Local spot'

def town_en_of(ja_town):
    for hh in hubs.values():
        if hh['name_ja'] == ja_town: return hh['name_en']
    return S.romanize_name(re.sub(r'[市町村]$', '', ja_town)) or ja_town

def build_sections(d, h, r):
    muni_en, muni_ja, sl = h['name_en'], h['name_ja'], slug[d]
    stay_lis, din_lis, seen = [], [], set()
    for i, s in enumerate(r['stay']):
        k = jd_(s['name_ja'])
        if k in seen: continue
        seen.add(k)
        href = s.get('ikkyu_url') or s.get('jalan_url') or s.get('rakuten_url') or s.get('official_url')
        fn_ = f'{pref}-{sl}-s{len(stay_lis)+1}.webp'
        ph, s['photo_search'] = S.photo_search(s, lambda u, a: photo(u, fn_, kind='stay', alt=a, town=sl, name=s['name_ja']), fetch=fetch, kind='stay')
        PHOTO_SEARCH[s.get('ikkyu_url') or s.get('jalan_url') or s['name_ja']] = s['photo_search']
        nb = S.neighbour_of(s.get('addr', ''), muni_ja, pref_ja)  # P6
        near = town_en_of(nb) if nb else ''
        if not ph and s.get('jalan_url') and s.get('img_src') == 'ikkyu':
            pass
        src_label = {'ikkyu': '一休.com', 'jalan': 'じゃらんnet', 'rakuten': '楽天トラベル', 'official': 'Official'}.get(s.get('img_src') or '', '')
        if not src_label:
            src_label = '一休.com' if s.get('ikkyu_url') else 'じゃらんnet' if s.get('jalan_url') else '楽天トラベル' if s.get('rakuten_url') else 'Official'
        credit = f'{src_label} · Source {href}'
        place = place_from_addr(s.get('addr', ''), muni_ja, muni_en)
        if near: place = near  # neighbour-town stay: describe it where it is
        on = onsen_of(s['name_ja'], s.get('desc_ja'), s.get('addr'))
        kind = stay_kind(s['name_ja']); acc = access_en(s.get('desc_ja'))
        feats = stay_features(s.get('desc_ja'))
        if kind == 'Lodging': kind = 'Hotel' if 'ホテル' in s['name_ja'] else 'Inn'
        pm = re.match(r'([\d,]+)', s.get('price') or '')
        price = f'; plans from ¥{pm.group(1)} per person' if pm else ''
        if not on and not acc and not feats and not price:  # standing bar: every card has an English line
            desc = f"{kind} in {place}" + ('; listed on Ikkyu' if s.get('ikkyu_url') else '; listed on Jalan' if s.get('jalan_url') else '') + '.'
        else:
            desc = kind + (f' at {on}' if on else '') + f' in {place}' + (f' with {" and ".join(feats)}' if feats else '') + (f'; {acc}' if acc else '') + price + '.'
        desc = STAY_EN.get(href, desc)
        stay_lis.append(card(href, s['name_ja'], en_name(s['name_ja'], s.get('name_en_official', '')), len(stay_lis)+1, muni_en, desc, ph, credit,
                             [('ikkyu_url', s.get('ikkyu_url')), ('jalan_url', s.get('jalan_url')), ('rakuten_url', s.get('rakuten_url')), ('official_url', s.get('official_url'))], near=near))
    dseen = set()
    for x in r['dining']:
        if re.search(r'コンビニ|結婚式場|^その他$', x.get('genre','')): continue
        k = jd_(x['name_ja'])
        if k in dseen or k in seen: continue
        dseen.add(k)
        fn_ = f'{pref}-{sl}-d{x["rid"]}.webp'
        ph, x['photo_search'] = S.photo_search(x, lambda u, a: photo(u, fn_, kind='dining', town=sl, name=x['name_ja']), fetch=fetch, kind='dining')
        PHOTO_SEARCH[x['tabelog_url']] = x['photo_search']
        g = genre_en(x.get("genre","")); pl = place_from_addr(x["addr"].replace(pref_ja,""), muni_ja, muni_en)
        desc = S.dining_desc(x, muni_en) if x.get('area_ja') or x.get('genre') else ''  # P9 sourced from the Tabelog list row
        din_lis.append(card(x['tabelog_url'], x['name_ja'], en_name(x['name_ja'], x.get('name_en_official', '')), len(din_lis)+1, muni_en, desc, ph,
                            f'食べログ · Source {x["tabelog_url"]}', [('tabelog_url', x['tabelog_url'])]))
    return stay_lis, din_lis

def jd_(s): return re.sub(r'[\s\u3000・\-ー（）()]', '', s or '').lower()

def nearest_with_stay(d):
    h = hubs[d]; best = None
    for o, r in recs.items():
        if o == d or not r['stay']: continue
        ho = hubs[o]
        dist = math.hypot(float(h['lat']) - float(ho['lat']), (float(h['lng']) - float(ho['lng'])) * 0.8)
        if best is None or dist < best[0]: best = (dist, o)
    return best[1] if best else None

def fix_map_links(t):
    for d, h in hubs.items():
        sl = slug[d]
        if sl != d:
            t = t.replace(f'"../{d}/"', f'"../{sl}/"').replace(f'href="{d}/"', f'href="{sl}/"')
            t = t.replace(f'data-name="{d}"', f'data-name="{h["name_en"]}"').replace(f'aria-label="{d}"', f'aria-label="{h["name_en"]}"')
            t = t.replace(f'<title>{d}</title>', f'<title>{h["name_en"]}</title>')
            # media prefix rewrite for numbered dirs
            t = t.replace(f'/media/{d}-', f'/media/{sl}-')
        if d.startswith('jis'):
            code = d[3:]
            t = t.replace(f'JIS {code}', h['name_en'])
    return t

def render(d):
    h, r = hubs[d], recs[d]
    src = PD / d / 'index.html'
    if not src.exists(): src = PD / slug[d] / 'index.html'
    t = src.read_text(encoding='utf-8')
    muni_en = h['name_en']; sl = slug[d]
    t = re.sub(r'\s*<!--\s*Municipality boundaries:.*?-->', '', t, flags=re.S)
    t = re.sub(r'\s*<meta name="description"[^>]*>|\s*<link rel="canonical"[^>]*>|\s*<meta property="og:[^>]*>', '', t)
    t = fix_map_links(t)
    # sections
    stay_lis, din_lis = build_sections(d, h, r)
    main_s = t.index('<section class="meta-block">'); main_e = t.index('</main>')
    block = t[main_s:main_e]
    mb = re.search(r'<section class="meta-block">.*?</section>', block, re.S).group(0)
    sights = re.search(r'<section class="place-section"><h2>Sights</h2>.*?</section>', block, re.S)
    if sights:
        side = Path(f'/workspace/p1/partials-build/data/{pref}-sights-pending'); side.mkdir(exist_ok=True)
        (side / f'{sl}.html').write_text(sights.group(0), encoding='utf-8')
    sights_html = sights.group(0) if sights else ''
    # official link https + verified
    off = OFFICIAL.get(d) or h.get('official_lg') or ''
    if off:
        off = re.sub(r'^http://', 'https://', off)
        mb = re.sub(r'(<h2>Official</h2><p><a href=")[^"]*(">)[^<]*', lambda m: f'{m.group(1)}{E(off)}{m.group(2)}{E(muni_en)} {"City" if h["name_ja"].endswith("市") else "Town" if h["name_ja"].endswith("町") else "Village"} Hall', mb)
    if stay_lis:
        stay = f'<section class="place-section"><h2>Stay</h2><ul class="place-list">{"".join(stay_lis)}</ul></section>'
    else:
        n = nearest_with_stay(d)
        stay = (f'<section class="place-section"><h2>Stay</h2><p class="stay-none">No bookable places to stay found in {E(muni_en)} '
                f'— nearest options in <a href="/{pref}/{slug[n]}/">{E(hubs[n]["name_en"])}</a>.</p></section>')
    ex = r.get('source_exhausted') or {}
    dining = f'<section class="place-section"><h2>Dining</h2><ul class="place-list">{"".join(din_lis)}</ul></section>' if din_lis else ''
    # markers live OUTSIDE the sections (template_hub.lis_of needs '</ul></section>' adjacent); template_hub carries them to the hub index
    mk = ''.join(f'<!-- source-exhausted: {k} -->' for k in ('dining', 'stay') if ex.get(k))
    dining = mk + dining
    t = t[:main_s] + mb + stay + dining + sights_html + t[main_e:]
    # cover -> webp
    cm = re.search(r'<figure class="cover"><img src="([^"]+)"[^>]*>(<!--.*?-->)?</figure>', t)
    cover_rel = None
    if cm:
        old = WT / cm.group(1).replace('../../', '')
        if old.exists() and old.suffix != '.webp':
            from PIL import Image
            new = MEDIA / f'{pref}-{sl}-cover.webp'
            im = Image.open(old).convert('RGB')
            if im.width > 560: im = im.resize((560, int(im.height * 560 / im.width)))
            im.save(new, 'WEBP', quality=25, method=5)
            alt = re.search(r'alt="([^"]*)"', cm.group(0)).group(1)
            alt = alt if alt and not CJK.search(alt) else f'{muni_en}, {PREF_EN}'
            t = t.replace(cm.group(0), f'<figure class="cover"><img src="../../media/{new.name}" alt="{E(alt)}" width="{im.width}" height="{im.height}" loading="lazy">{cm.group(2) or ""}</figure>')
            cover_rel = new.name
        else:
            cover_rel = cm.group(1).replace('../../media/', '')
    else:
        first = re.search(r'<img class="thumb" src="\.\./\.\./media/([^"]+)"', t)
        if first:
            cover_rel = first.group(1)
            lic = re.search(r'src="\.\./\.\./media/' + re.escape(cover_rel) + r'".*?</a>(<!--.*?-->)', t)
            fig = f'<figure class="cover"><img src="../../media/{cover_rel}" alt="{E(muni_en)}, {PREF_EN}" loading="lazy">{lic.group(1) if lic else ""}</figure>'
            t = t.replace('<section class="meta-block">', fig + '<section class="meta-block">', 1)
    # head
    desc = f'{muni_en}, {PREF_EN}: where to stay and eat — ranked inns and restaurants, official links and map.'
    url = f'{SITE}/{pref}/{sl}/'
    headx = (f'\n  <meta name="description" content="{E(desc)}">\n  <link rel="canonical" href="{url}">\n'
             f'  <meta property="og:title" content="{E(muni_en)} · {PREF_EN} · BokenJapan">\n'
             f'  <meta property="og:description" content="{E(desc)}">\n  <meta property="og:url" content="{url}">\n  <meta property="og:type" content="website">\n'
             + (f'  <meta property="og:image" content="{SITE}/media/{cover_rel}">\n' if cover_rel else ''))
    t = re.sub(r'(<title>[^<]*</title>)', lambda m: m.group(1) + headx.rstrip('\n'), t, count=1)
    t = re.sub(r'<title>[^<]*</title>', f'<title>{E(muni_en)} · {PREF_EN} · BokenJapan</title>', t, count=1)
    dst = PD / sl / 'index.html'
    if src.parent != dst.parent:
        subprocess.run(['git', '-C', str(WT), 'mv', str(src.parent), str(dst.parent)], check=True)
    dst.write_text(t, encoding='utf-8')
    print(d, sl, 'stay', len(stay_lis), 'dining', len(din_lis), flush=True)

for d in hubs:
    if only and d not in only: continue
    if d not in recs: continue
    render(d)
json.dump(PHOTO_SEARCH, open(DATA / '_photo_search.json', 'w'), ensure_ascii=False, indent=0)  # per-card sources tried
# pref index + all pages map links
idx = PD / 'index.html'; idx.write_text(fix_map_links(idx.read_text(encoding='utf-8')), encoding='utf-8')
for d in hubs:
    p = PD / slug[d] / 'index.html'
    if not p.exists(): p = PD / d / 'index.html'
    if p.exists(): p.write_text(fix_map_links(p.read_text(encoding='utf-8')), encoding='utf-8')
