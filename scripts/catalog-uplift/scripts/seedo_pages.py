#!/usr/bin/env python3
"""Generic: add missing See / Do hub sections (tile + list page) from a collected official-tourism JSONL
(rows: muni, kind see|do, url, name (EN or JA), og, desc (EN) or cat (JA category block), tel, in_town).
List page is cloned from the town's own Stay/Eat list page (same head/mast/foot, beacon kept).
  python3 seedo_pages.py --root <site> --pref yamagata --data seedo/yamagata.jsonl [--max 10]
"""
import re, os, io, sys, json, html, glob, argparse, subprocess, collections
from PIL import Image, ImageStat
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from en_natural import natural_en
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36'
JA_CAT = {'ホテル、旅館': 'Hotel', '体験観光-産業': 'Factory tour and local products', '交流等': 'Hands-on community experience', 'スポーツ施設・公園': 'Sports facility or park', '遊園地、テーマパーク': 'Amusement park', '動・植物園、水族館': 'Zoo, botanical garden or aquarium', '工芸': 'Craft workshop', '自然・スポーツ': 'Outdoor activity', '朝市・産直': 'Morning market and farm-direct stand', '観光案内所': 'Tourist information center', '体験工房・ものづくり': 'Hands-on craft workshop', 'アウトドア・アクティビティ': 'Outdoor activity site', 'アウトドア・スポーツ': 'Outdoor sports site',
 'スキー場': 'Ski area', '海水浴場': 'Swimming beach', 'キャンプ場': 'Campground', 'ゴルフ場': 'Golf course', '登山・ロープウェイ': 'Mountain trail and ropeway',
 '観光施設': 'Visitor facility', '動植物園・水族館・テーマパーク': 'Zoo, aquarium or theme park', '体験': 'Hands-on experience', '舟下り・遊覧船': 'River boat or sightseeing cruise',
 'ワイナリー・酒蔵見学・ビール': 'Winery or brewery tour', 'フルーツ狩り': 'Fruit-picking farm', '農村体験': 'Farm-stay experience', '児童遊戯施設': "Children's play facility",
 'ウィンタースポーツ': 'Winter sports site', '温泉': 'Hot spring', '日帰り温泉': 'Day-trip hot spring', 'スパ・足湯': 'Spa or footbath', '温泉地': 'Hot-spring area',
 '自然・景観': 'Natural scenery', '花・植物': 'Flower and plant spot', '山・高原': 'Mountain and highland area', '湖沼・河川・渓谷・滝': 'Lake, river, gorge or waterfall',
 '海岸・岬・島': 'Coast, cape or island', '景勝地・天然記念物': 'Scenic spot or natural monument', '展望台・展望施設': 'Observation point', '歴史・文化': 'History and culture spot',
 '歴史的建築物・町並み': 'Historic building or streetscape', '寺院': 'Buddhist temple', '神社': 'Shinto shrine', '史跡・名勝・庭園': 'Historic site or garden', '城・城跡': 'Castle or castle ruins',
 '美術館・博物館・科学館': 'Museum', '文化ホール': 'Cultural hall', '公園': 'Park', '資料館': 'Local history museum'}
def curl(u):
    return subprocess.run(['curl', '-sL', '--max-time', '30', '-A', UA, u], capture_output=True).stdout
def photo(root, slug, r):
    if not r.get('og') or re.search(r'ogp_|no_?image|noimage', r['og']): return None
    name = f'{slug}-sd{re.sub(r"[^0-9]", "", str(r.get("id", ""))) or abs(hash(r["url"])) % 10**8}.webp'; dest = os.path.join(root, 'media', name)
    if not os.path.exists(dest):
        try:
            im = Image.open(io.BytesIO(curl(r['og']))).convert('RGB')
            if min(im.size) < 200 or ImageStat.Stat(im.convert('L').resize((64, 64))).stddev[0] < 15: return None
            if im.width > 640: im = im.resize((640, round(im.height * 640 / im.width)))
            im.save(dest, 'WEBP', quality=74, method=5)
        except Exception: return None
    with Image.open(dest) as im: return name, im.width, im.height
def first_sentence(t, lim=170):
    t = re.sub(r'``|\'\'', '"', t or '').strip()
    m = re.match(r'(.{30,%d}?[.!?])(\s|$)' % lim, t)
    return (m.group(1) if m else (t[:lim].rsplit(' ', 1)[0] + '…' if len(t) > lim else t)).strip()
def card(root, slug, town, pref, r):
    ja = not re.search(r'[A-Za-z]', r['name'])
    en = natural_en(r['name']) if ja else r['name']
    if ja:
        sub = [c for c in JA_CAT if c in (r.get('cat') or '')]
        sub = sorted(sub, key=lambda c: (r['cat'].rfind(c)), reverse=True)
        desc = f'{JA_CAT[sub[0]]} in {town}, {pref}.' if sub else ''
    else: desc = first_sentence(r.get('desc'))
    ph = photo(root, slug, r); host = re.sub(r'^https?://([^/]+).*', r'\1', r['url'])
    img = (f'<img class="thumb" src="/media/{ph[0]}" alt="{html.escape(en)}" width="{ph[1]}" height="{ph[2]}" loading="lazy">' +
           (f'<!-- photo-credit: {r["credit"]} · Source {r["og"].split("?")[0]} -->' if r.get('credit') else f'<!-- photo-credit: {host} · Source {r["url"]} -->')) if ph else ''
    tel = re.sub(r'[（(].*', '', r.get('tel') or '').strip()
    meta = f'{town}, {pref}' + (f' · {tel}' if re.fullmatch(r'0\d{1,4}-\d{1,4}-\d{3,4}', tel) else '')
    blurb = f'<p class="place-blurb">{html.escape(en)}</p>' if ja else ''
    nm = html.escape(r['name']) if ja else html.escape(en)
    d = f'<p class="place-desc">{html.escape(desc)}</p><!-- desc-source: {r["url"]} -->' if desc else ''
    return f'<li><a href="{r["url"]}"><p class="place-name">{nm}</p>{img}</a>{blurb}<p class="place-meta">{meta}</p>{d}</li>', ph
def run(root, pref, data, mx):
    rows = collections.defaultdict(list)
    for l in open(data):
        x = json.loads(l)
        if x.get('in_town') and x.get('name'): rows[(x['muni'], x['kind'])].append(x)
    st = collections.Counter()
    LAB = {'see': 'See', 'do': 'Do', 'day-to-day': 'Day to day', 'stay': 'Stay'}
    for (slug, kind) in sorted(rows):
        base = f'{root}/{pref}/{slug}'
        if os.path.exists(f'{base}/{kind}/index.html'): continue
        hub = open(f'{base}/index.html').read()
        used = set(re.findall(r'<a href="(https?://[^"]+)"', ' '.join(open(f).read() for f in glob.glob(f'{base}/*/**/index.html', recursive=True))))
        other = {'do': 'see', 'see': 'do'}.get(kind, 'none')
        taken = {x['url'] for x in rows.get((slug, other), [])} if os.path.exists(f'{base}/{other}/index.html') is False else set()
        pick, seen = [], set()
        for r in rows[(slug, kind)]:
            if r['url'] in used or r['name'] in seen: continue
            if kind == 'see' and r['url'] in {x['url'] for x in rows.get((slug, 'do'), [])} and not os.path.exists(f'{base}/do/index.html'): continue
            seen.add(r['name']); pick.append(r)
        pick = pick[:mx]
        if not pick: st['empty_' + kind] += 1; continue
        tmpl = next((f'{base}/{k}/index.html' for k in ('stay', 'see', 'do', 'day-to-day') if os.path.exists(f'{base}/{k}/index.html')), None)
        t = open(tmpl).read(); old = tmpl.split('/')[-2]; OLD = {'stay': 'Stay', 'see': 'See', 'do': 'Do', 'day-to-day': 'Day to day'}[old]
        town = html.unescape(re.search(r'<h1 class="page-title">' + OLD + r' in ([^<]+)</h1>', t).group(1)); P = html.unescape(re.search(r'<a href="/' + pref + r'/">([^<]+)</a>', t).group(1))
        lis, phs = zip(*[card(root, slug, town, P, r) for r in pick])
        n = len(lis); cnt = f'{n} place' if n == 1 else f'{n} places'; L = LAB[kind]
        t = t.replace(f'/{slug}/{old}/', f'/{slug}/{kind}/').replace(f'<title>{OLD} · ', f'<title>{L} · ').replace(f'content="{OLD} · ', f'content="{L} · ')
        t = re.sub(r'(<meta (?:name="description"|property="og:description") content=")[^"]*', lambda m: m.group(1) + f'{L} in {html.escape(town)}, {html.escape(P)}: places from the official tourism guide.', t)
        t = re.sub(r'(<p class="crumb">.*?</a> / )' + re.escape(OLD) + r'</p>', lambda m: m.group(1) + L + '</p>', t)
        t = re.sub(r'<h1 class="page-title">[^<]*</h1>', f'<h1 class="page-title">{L} in {html.escape(town)}</h1>', t)
        t = re.sub(r'<p class="page-sub">[^<]*</p>', f'<p class="page-sub">{html.escape(town)} · {html.escape(P)} · {cnt}</p>', t)
        t = re.sub(r'<section class="place-section">.*</section>', f'<section class="place-section"><h2 class="visually-hidden">{L}</h2><ul class="place-list">{"".join(lis)}</ul></section>', t, flags=re.S)
        os.makedirs(f'{base}/{kind}', exist_ok=True); open(f'{base}/{kind}/index.html', 'w').write(t)
        ph = next((p for p in phs if p), None); alt = html.escape(natural_en(pick[[i for i, p in enumerate(phs) if p][0]]['name'])) if ph else ''
        pic = f'<img src="../../media/{ph[0]}" alt="{alt}" width="{ph[1]}" height="{ph[2]}"  loading="lazy" decoding="async">' if ph else ''
        tile = f'<li><a class="hub-tile" href="{kind}/">{pic}<span class="hub-tile-label"><span class="hub-tile-name">{L}</span><span class="hub-tile-count">{cnt}</span></span></a></li>'
        # insert in Ohira order: Stay, Eat, Do, See, Day to day
        order = ['stay/', 'eat/', 'do/', 'see/', 'day-to-day/']; me = order.index(kind + '/')
        ul = re.search(r'<ul class="hub-tiles">(.*?)</ul>', hub, re.S)
        items = re.findall(r'<li(?: style="[^"]*")?><a class="hub-tile"[^>]*href="([^"]+)".*?</li>', ul.group(1), re.S)
        tiles = re.findall(r'<li(?: style="[^"]*")?><a class="hub-tile".*?</li>', ul.group(1), re.S)
        pos = next((k for k, h in enumerate(items) if h in order and order.index(h) > me), len(tiles))
        tiles.insert(pos, tile)
        hub = hub[:ul.start(1)] + ''.join(tiles) + hub[ul.end(1):]
        open(f'{base}/index.html', 'w').write(hub); st[kind] += 1; st['cards'] += n; st['photo'] += sum(1 for p in phs if p)
    return st
if __name__ == '__main__':
    ap = argparse.ArgumentParser(); ap.add_argument('--root', required=True); ap.add_argument('--pref', required=True); ap.add_argument('--data', required=True); ap.add_argument('--max', type=int, default=10); A = ap.parse_args()
    print(A.pref, dict(run(A.root, A.pref, A.data, A.max)))
