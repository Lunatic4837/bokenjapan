#!/usr/bin/env python3
"""Day-to-day candidates (railway stations, michi-no-eki) from Wikidata with a Commons photo -> JSONL for seedo_pages.py (kind day-to-day)."""
import json, sys, subprocess, argparse, urllib.parse, time
UA = 'BokenJapanBot/1.0 (https://bokenjapan.com)'
Q = '''SELECT DISTINCT ?item ?ja ?en ?desc ?img ?wp ?kind WHERE {
  ?muni rdfs:label "%s"@ja . ?muni wdt:P131+ ?pref . ?pref rdfs:label "%s"@ja .
  VALUES ?t { wd:Q55488 wd:Q4346602 wd:Q22808404 wd:Q4312270 wd:Q2142091 wd:Q1187691 wd:Q1339195 wd:Q11446004 } ?item wdt:P31 ?t .
  ?item wdt:P131 ?muni ; wdt:P18 ?img ; rdfs:label ?ja . FILTER(lang(?ja)="ja")
  FILTER NOT EXISTS { ?item wdt:P576 ?end } FILTER NOT EXISTS { ?item wdt:P31 wd:Q4663385 }
  OPTIONAL { ?item rdfs:label ?en . FILTER(lang(?en)="en") }
  OPTIONAL { ?item schema:description ?desc . FILTER(lang(?desc)="en") }
  OPTIONAL { ?wp schema:about ?item ; schema:isPartOf <https://en.wikipedia.org/> }
}'''
ap = argparse.ArgumentParser(); ap.add_argument('--pref-ja'); ap.add_argument('--town', nargs=2, action='append', metavar=('SLUG', 'JA')); ap.add_argument('--out'); A = ap.parse_args()
out = open(A.out, 'a')
for slug, ja in A.town:
    r = subprocess.run(['curl', '-s', '--max-time', '90', '-H', 'Accept: application/sparql-results+json', '-A', UA, '--data-urlencode', 'query=' + Q % (ja, A.pref_ja), 'https://query.wikidata.org/sparql'], capture_output=True, text=True).stdout
    try: bs = json.loads(r)['results']['bindings']
    except Exception: print(slug, 'ERR', r[:80], file=sys.stderr); continue
    seen = set(); n = 0
    for b in bs:
        q = b['item']['value'].rsplit('/', 1)[1]
        if q in seen or '信号場' in b['ja']['value']: continue
        seen.add(q)
        img = b['img']['value'].rsplit('/', 1)[1]
        d = (b.get('desc') or {}).get('value', '')
        desc = (d[:1].upper() + d[1:] + '.') if d and not d.endswith('.') else d
        out.write(json.dumps(dict(id=q.lstrip('Q'), url=(b.get('wp') or b['item'])['value'], name=(b.get('en') or b['ja'])['value'], name_ja=b['ja']['value'],
              og='https://commons.wikimedia.org/wiki/Special:FilePath/' + img + '?width=640', desc=desc, muni=slug, kind='day-to-day', in_town=True,
              credit='Wikimedia Commons'), ensure_ascii=False) + '\n'); n += 1
    print(slug, n, file=sys.stderr); time.sleep(1)
