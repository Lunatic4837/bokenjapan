import json, re, glob, time, urllib.parse, requests, html
REPO = '/workspace/p1/pr12-work'
wd = [{k: v['value'] for k, v in x.items()} for x in json.load(open('wd.json'))['results']['bindings']]
host = lambda u: re.sub(r'^www\.', '', urllib.parse.urlparse(u).netloc.lower())
byhost = {}; byen = {}
for x in wd:
    if len(x['code']) == 6 and x['code'][2:5] == '000': continue  # prefecture
    if x.get('site'): byhost.setdefault(host(x['site']), x)
    if x.get('en'): byen.setdefault((x['code'][:2], x['en'].lower()), x)
PC = {'miyagi': '04', 'akita': '05', 'yamaguchi': '35', 'fukuoka': '40', 'oita': '44'}
out = json.load(open('geo.json')) if __import__('os').path.exists('geo.json') else {}
S = requests.Session(); S.headers['User-Agent'] = 'bokenjapan-geo/1.0 (town-hall distance for nearest-stay links)'
for p in sorted(glob.glob(f'{REPO}/*/*/index.html')):
    pref, slug = p.split('/')[-3:-1]
    if pref not in PC: continue
    key = f'{pref}/{slug}'
    if key in out: continue
    s = open(p, encoding='utf-8').read()
    m = re.search(r'<h2>Official</h2><p><a href="([^"]+)">([^<]+)</a>', s)
    title = re.search(r'<h1[^>]*>(.*?)</h1>', s, re.S)
    en = html.unescape(re.sub('<.*?>', '', title.group(1))).strip() if title else slug
    x = byhost.get(host(m.group(1))) if m else None
    if not x: x = byen.get((PC[pref], en.lower()))
    if not x:
        out[key] = {'en': en, 'err': 'no wikidata match', 'hall': m.group(2) if m else None}; print(key, 'NO MATCH', en); continue
    ja = x['ja']; suffix = '役所' if ja.endswith('市') else '役場'
    lat = lon = None; src = None
    for q in (f'{ja}{suffix}', f'{ja}役場', f'{ja}役所'):
        r = S.get('https://nominatim.openstreetmap.org/search', params={'format': 'json', 'limit': 5, 'countrycodes': 'jp', 'q': q}, timeout=30); time.sleep(1.1)
        for c in r.json():
            if c.get('type') == 'townhall' and ja in c.get('display_name', '') and '跡' not in c['display_name'].split(',')[0] and '支所' not in c['display_name'].split(',')[0]:
                lat, lon, src = float(c['lat']), float(c['lon']), 'osm:' + c['display_name'].split(',')[0]; break
        if lat: break
    if not lat and x.get('coord'):
        lo, la = map(float, re.findall(r'[-\d.]+', x['coord'])); lat, lon, src = la, lo, 'wikidata P625'
    out[key] = {'en': en, 'ja': ja, 'code': x['code'], 'lat': lat, 'lon': lon, 'src': src}
    print(key, ja, lat, lon, src, flush=True)
    json.dump(out, open('geo.json', 'w'), ensure_ascii=False, indent=0)
json.dump(out, open('geo.json', 'w'), ensure_ascii=False, indent=0)
