#!/usr/bin/env python3
"""osm_extract.py - stream a Geofabrik .osm.pbf (no Overpass needed) and keep named amenity/shop/tourism/... elements that carry a
website / wikidata / wikimedia_commons tag, inside a lat/lon box.  Output JSON list: osmid,name,name_en,site,wikidata,commons,addr,lat,lon.
  osm_extract.py kyushu.osm.pbf 33.0,130.0,34.0,131.1 out.json
"""
import json, sys, osmium
KEYS = ('amenity', 'shop', 'tourism', 'leisure', 'craft', 'office')
pbf, box, out = sys.argv[1], [float(x) for x in sys.argv[2].split(',')], sys.argv[3]
s, w, n, e = box
res = []
fp = osmium.FileProcessor(pbf, osmium.osm.NODE | osmium.osm.WAY).with_locations().with_filter(osmium.filter.KeyFilter('name'))
for o in fp:
    t = {k: v for k, v in ((x.k, x.v) for x in o.tags)}
    if not any(k in t for k in KEYS): continue
    site = t.get('website') or t.get('contact:website') or t.get('url') or ''
    if not (site or t.get('wikidata') or t.get('wikimedia_commons')): continue
    try:
        if o.is_node(): lat, lon = o.location.lat, o.location.lon
        else:
            nd = [x for x in o.nodes if x.location.valid()]
            if not nd: continue
            lat = sum(x.lat for x in nd) / len(nd); lon = sum(x.lon for x in nd) / len(nd)
    except Exception: continue
    if not (s <= lat <= n and w <= lon <= e): continue
    res.append(dict(osmid=('n' if o.is_node() else 'w') + str(o.id), name=t['name'], name_en=t.get('name:en', ''), site=site, wikidata=t.get('wikidata', ''),
                    commons=t.get('wikimedia_commons', ''), addr=' '.join(t.get(k, '') for k in ('addr:province', 'addr:city', 'addr:suburb', 'addr:full')).strip(),
                    lat=round(lat, 5), lon=round(lon, 5), tags={k: t[k] for k in ('brand', 'brand:wikidata', 'amenity', 'shop', 'tourism') if k in t}))
json.dump(res, open(out, 'w'), ensure_ascii=False)
print(len(res))
