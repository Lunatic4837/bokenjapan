#!/usr/bin/env python3
"""Check every 5-prefecture town-hall coordinate in nostay/geo.json against GSI (国土地理院) address search:
the feature titled '{municipality}役所/役場' whose addressCode is the municipality's own code."""
import json, time, math, urllib.parse, urllib.request
G = json.load(open('/workspace/p1/phase-d/nostay/geo.json'))
def km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 12742 * math.asin(math.sqrt(h))
res = {}
for k, v in sorted(G.items()):
    if k.split('/')[0] not in ('miyagi', 'akita', 'fukuoka', 'yamaguchi', 'oita'): continue
    if not v.get('ja'): res[k] = dict(err='no ja name'); continue
    code = str(int(v['code'][:5])); hit = None
    for suf in ('役所', '役場'):
        q = v['ja'] + suf
        r = json.load(urllib.request.urlopen('https://msearch.gsi.go.jp/address-search/AddressSearch?q=' + urllib.parse.quote(q), timeout=30)); time.sleep(0.5)
        for f in r:
            p = f['properties']
            if p.get('title') == q and p.get('addressCode') == code: hit = (f['geometry']['coordinates'][1], f['geometry']['coordinates'][0], q); break
        if hit: break
    d = km((v['lat'], v['lon']), hit[:2]) if hit and v.get('lat') else None
    res[k] = dict(ja=v['ja'], old=(v.get('lat'), v.get('lon'), v.get('src')), gsi=hit, km=None if d is None else round(d, 2))
    print(k, v['ja'], res[k]['km'], hit and hit[2], flush=True)
json.dump(res, open('gsi_check.json', 'w'), ensure_ascii=False, indent=0)
