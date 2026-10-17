import json,os,sys
p=sys.argv[1]; rej=set(sys.argv[2].split('|')); why=sys.argv[3] if len(sys.argv)>3 else 'photo not of this venue'
out=f'/workspace/p1/ph/{p}/out'
last={}
for l in open(out+'/results.jsonl'):
    r=json.loads(l); last[r['key']]=r
with open(out+'/results.jsonl','a') as fh:
    for r in last.values():
        if r['photo'] and r['name'] in rej:
            try: os.remove(out+'/media/'+os.path.basename(r['photo']['file']))
            except OSError: pass
            ps=dict(r['photo_search']); ps['result']=None
            ps['notes']=dict(ps['notes'],**{'review':'rejected:'+why+':'+r['photo']['source'][:70]})
            fh.write(json.dumps(dict(r,photo=None,photo_search=ps),ensure_ascii=False)+'\n'); print('rejected',r['name'])
