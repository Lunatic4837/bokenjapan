import json,sys,re
sys.path.insert(0,'/workspace/p1/partials-build/shared'); import bj_shared as S
pref=sys.argv[1]
r=json.load(open(f'{pref}/inv.json'))
JP=re.compile(r'[\u3040-\u30ff\u4e00-\u9fff]')
seen={};
for x in r:
    if x['sec'] in('eat','stay') and x['blurb'] and (S.rough_romaji(x['blurb']) or JP.search(x['blurb'])):
        seen.setdefault((x['name'],x['blurb']),x)
L=sorted(seen)
json.dump([[a,b] for a,b in L],open(f'{pref}/rough.json','w'),ensure_ascii=False)
print(len(L))
for i,(a,b) in enumerate(L): print(i,a,'|',b)
