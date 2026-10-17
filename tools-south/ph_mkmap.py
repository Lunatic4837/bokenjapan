import json,re,sys
sys.path.insert(0,'/workspace/p1/partials-build/shared'); import bj_shared as S
p=sys.argv[1]
rough=json.load(open(f'{p}/rough.json'));m={}
for l in open(f'{p}/romaji.txt'):
    i,v=l.rstrip('\n').split('|',1); m[int(i)]=v
assert len(m)==len(rough),(len(m),len(rough))
print('still rough:',[(i,v) for i,v in m.items() if S.rough_romaji(v) or re.search('[\u0100-\u017f\u3040-\u9fff]',v)])
json.dump({f'{rough[i][0]}\t{rough[i][1]}':v for i,v in m.items()},open(f'{p}/romaji_map.json','w'),ensure_ascii=False)
