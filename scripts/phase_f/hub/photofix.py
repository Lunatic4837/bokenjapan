import re,json,collections,csv,html,shutil
NOPH=[]
src=open('daisen-orig.html').read()
res={r['i']:r for r in json.load(open('photomatch.json'))}
m=re.search(r'(<h2>Dining</h2><ul class="place-list">)(.*?)(</ul>)',src,re.S)
lis=re.findall(r'<li>.*?</li>',m.group(2),re.S)
dims={}
for li in lis:
    x=re.search(r'<img class="thumb" src="([^"]+)"[^>]*width="(\d+)" height="(\d+)"',li)
    if x: dims[x.group(1)]=(x.group(2),x.group(3))
ok={i:r for i,r in res.items() if r.get('dist') is not None and r['dist']<=4}
claimed={r['best'] for r in ok.values()}
out=[];log=[];st=collections.Counter()
for i,li in enumerate(lis):
    r=res[i]; nm=re.search(r'class="place-name">(.*?)</p>',li).group(1)
    tag=re.search(r'<img class="thumb"[^>]*>',li)
    if i in ok:
        new=r['best']
        if new!=r['cur']:
            w,h=dims[new]; t2=re.sub(r'src="[^"]+"',f'src="{new}"',tag.group(0)); t2=re.sub(r'width="\d+" height="\d+"',f'width="{w}" height="{h}"',t2)
            li=li.replace(tag.group(0),t2); st['moved']+=1; log.append([i+1,nm,r['cur'],new,'matched own listing photo'])
        else: st['correct']+=1
    elif tag and r['cur'] in claimed:
        li=re.sub(r'<!-- photo-credit:[^>]*-->','',li.replace(tag.group(0),'')); st['removed']+=1; NOPH.append([f'akita/daisen-05212|Dining|{i}',html.unescape(nm),'r2-hash-vs-listing:'+(r.get('src') or ''),'card photo belonged to another card (photo-shift fix); own listing photo not on R2','hubfix',html.unescape(nm),(re.search(r'(?:tabelog_url|ta_url)=(\S+)',li) or [0,''])[1]]); log.append([i+1,nm,r['cur'],'','photo belonged to another card; no own photo found'])
    elif tag: st['kept-unverified']+=1; log.append([i+1,nm,r['cur'],r['cur'],'kept (not verifiable against listing)'])
    else: st['no-photo']+=1
    out.append(li)
fixed=src[:m.start(2)]+''.join(out)+src[m.end(2):]
open('daisen-fixed.html','w').write(fixed)
with open('daisen-photo-fix.csv','w',newline='') as f:
    w=csv.writer(f); w.writerow(['rank','name','old_img','new_img','note']); w.writerows(log)
print(st)

NP='/workspace/p1/photos-5pref/no-photo-found.csv'
shutil.copy(NP,NP+'.bak-hub')
with open(NP,'a',newline='') as f: csv.writer(f).writerows(NOPH)
print('logged',len(NOPH))
