import re, json, subprocess, time, sys
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
def get(u):
    b=subprocess.run(['curl','-sL','-A',UA,u],capture_output=True).stdout
    return b.decode('cp932','replace')
res={}
for pj in ('070000','150000'):
    top=get(f'https://www.jalan.net/{pj}/')
    lrgs=sorted(set(re.findall(r'LRG_(\d{6})/',top)))
    for l in lrgs:
        h=get(f'https://www.jalan.net/{pj}/LRG_{l}/'); time.sleep(0.7)
        for cty,name in re.findall(r'CTY_(\d+)/\?[^"]*">([^<]+)<',h):
            res.setdefault(pj,{})[name]=f'CTY_{cty}'
    print(pj,len(lrgs),len(res.get(pj,{})))
json.dump(res,open('raw/jalan-cty.json','w'),ensure_ascii=False,indent=1)
